import json
import os
import requests
import logging

import bs4 as bs
import pandas as pd

import config
import utils


VENUE_CLASS = "smm-studio-snippet b-studio-item"
TITLE_CLASS = "smm-studio-snippet__title"
DISCIPLINE_CLASS = "disciplines"
PLAN_CLASS = "smm-studio-snippet__studio-plan"
ADDRESS_CLASS = "smm-studio-snippet__address"
PLUS_CLASS = 'usc-studio-status-label plus-checkins label'
LINK_CLASS = 'smm-studio-snippet__studio-link'
CITY_FILTERS_CLASS = 'usc-studio-filters dashboard-title'


logger = logging.getLogger(__name__)
logging.basicConfig(level = logging.INFO)


def download_cities():
    headers = {'user-agent': config.USER_AGENT}
    url = f"{config.BASE_LINK}/en/venues?city_id=1&plan_type=6"
    logger.info(f"Downloading cities from {url}")
    response = requests.get(url, headers=headers)
    page_source = response.content
    soup = bs.BeautifulSoup(page_source,'html.parser')
    divs_filters = soup.find_all('div', class_='usc-studio-filters dashboard-title')
    assert len(divs_filters) == 1
    div_filter = divs_filters[0]
    cities = {}
    for country in div_filter.find_all('optgroup'):
        country_name = country['label']
        for city in country.find_all('option'):
            city_name = city.text.strip()
            cities[f"{city_name} - {country_name}"] = city['value']
    with open(os.path.join(config.DATA_DIR, 'cities.json'), 'w') as fp:
        json.dump(cities, fp)
    return cities


def download_venues_source(city_id):
    headers = {'user-agent': config.USER_AGENT}
    url = f"{config.BASE_LINK}/en/venues?city_id={city_id}&plan_type=6&page={config.MAX_PAGES}&previous-pages"
    logger.info(f"Downloading venues from {url}")
    response = requests.get(url, headers=headers)
    page_source = response.content
    return page_source


def get_name(venue):
    titles = venue.find_all('p', class_=TITLE_CLASS)
    assert len(titles) == 1
    title = titles[0]
    a = title.find_next('a')
    venue_name = a.text.strip()
    return venue_name


def get_disciplines(venue):
    disciplines_divs = venue.find_all('div', class_=DISCIPLINE_CLASS)
    assert len(disciplines_divs) == 1
    disciplines_div = disciplines_divs[0]
    disciplines = [d.strip() for d in disciplines_div.text.split('·')]
    return disciplines


def get_plans(venue):
    plan_spans = venue.find_all('span', class_=PLAN_CLASS)
    return [p.text.strip() for p in plan_spans]


def get_address(venue):
    address_ps = venue.find_all('p', class_=ADDRESS_CLASS)
    assert len(address_ps) == 1
    address_p = address_ps[0]
    district = address_p.contents[0].strip()[:-1]
    street = address_p.contents[1].text.strip()
    return district, street


def get_plus_checkins(venue):
    plus_spans = venue.find_all('span', class_=PLUS_CLASS)
    assert len(plus_spans) <= 1
    if len(plus_spans) == 1:
        if plus_spans[0].text.strip() == 'PLUS':
            return True
        else:
            raise Exception('Unexpected text')
    else:
        return False


def get_link(venue):
    links = venue.find_all('a', class_=LINK_CLASS)
    assert len(links) == 1
    a = links[0]
    return config.BASE_LINK + a['href']


def extract_venues(venues_source):
    soup = bs.BeautifulSoup(venues_source, 'html.parser')
    venues = soup.find_all('div', class_=VENUE_CLASS)
    venues_list = []
    for idx, venue in enumerate(venues):
        district, street = get_address(venue)
        plans = get_plans(venue)
        venues_list.append({
            'name': get_name(venue),
            'disciplines': get_disciplines(venue),
            'plus_options': get_plus_checkins(venue),
            'plans': plans,
            'min_plan': plans[0] if len(plans)>0 else None,
            'district': district,
            'street': street,
            'link': get_link(venue)
        })
    df = pd.DataFrame(venues_list)
    return df


def download_metadata(venue_link):
    headers = {'user-agent': config.USER_AGENT}
    page_source = requests.get(venue_link, headers=headers).content
    venue_soup = bs.BeautifulSoup(page_source, 'html.parser')
    script_section = venue_soup.find('script', type='application/ld+json')
    return json.loads(script_section.text.replace("\\", ""), strict=False)


def get_metadata_from_df(df, name):
    prev_metadata = df[df.name == name].metadata.values[0]
    prev_metadata = prev_metadata.replace("'", '"').replace("\\", "")
    return json.loads(prev_metadata, strict=False)


def add_venue_metadata(venues, city_id):
    logger.info("Adding metadata")
    previous_venues, _ = utils.load_previous_csv(city_id)
    previous_venue_names = [] if previous_venues is None else previous_venues['name'].values
    new_venues = set(venues.name) - set(previous_venue_names)
    lost_venues = set(previous_venue_names) - set(venues.name)
    logger.info(f"I found {len(new_venues)} new venues, "
                f"and I found that {len(lost_venues)} were dropped")
    metadata_list = []
    for i, row in venues.iterrows():
        if row['name'] in previous_venue_names:
            metadata = get_metadata_from_df(previous_venues, row['name'])
        else:
            logger.info(f"Downloading metadata {i+1}/{len(venues)}")
            metadata = download_metadata(row.link)
        metadata_list.append(metadata)
    df = venues.join(pd.Series(metadata_list, name='metadata'))
    df['latitude'] = df['metadata'].apply(lambda x: float(x['geo']['latitude']))
    df['longitude'] = df['metadata'].apply(lambda x: float(x['geo']['longitude']))
    df['description'] = df['metadata'].apply(lambda x: x['description'])
    return df


def store_csv(df, filepath):
    logger.info(f"Storing into {filepath}")
    df.to_csv(filepath, index=False)


def main():
    download_date = pd.Timestamp.today().date()
    cities = download_cities()
    for city_name, city_id in cities.items():
        filename = f'venues_{download_date}_city{city_id}_maxpages{config.MAX_PAGES}.csv'
        filepath = os.path.join(config.DATA_DIR, filename)
        if os.path.exists(filepath):
            logger.info(f"csv file for {city_name} already exists, skipping...")
            continue
        logger.info(f"Starting to scrape city {city_name}...")
        venues_source = download_venues_source(city_id)
        venues = extract_venues(venues_source)
        if not venues.empty:
            venues_w_metadata = add_venue_metadata(venues, city_id)
            store_csv(venues_w_metadata, filepath)
        logger.info(f"Scraping city {city_name} finished!")


if __name__ == '__main__':
    main()

