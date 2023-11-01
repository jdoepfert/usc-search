import json
import os
import requests
import glob
import logging

import bs4 as bs
import pandas as pd

import config


VENUE_CLASS = "smm-studio-snippet b-studio-item"
TITLE_CLASS = "smm-studio-snippet__title"
DISCIPLINE_CLASS = "disciplines"
PLAN_CLASS = "smm-studio-snippet__studio-plan"
ADDRESS_CLASS = "smm-studio-snippet__address"
PLUS_CLASS = 'usc-studio-status-label plus-checkins label'
LINK_CLASS = 'smm-studio-snippet__studio-link'


logger = logging.getLogger(__name__)
logging.basicConfig(level = logging.INFO)


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


def get_all_csv_paths(city_id):
    return glob.glob(os.path.join(config.DATA_DIR, f'venues_*_city{city_id}*_maxpages*.csv'))


def parse_info_from_csv_name(csv):
    _, date, city, maxpages = csv.split('_')
    date = pd.to_datetime(date).date()
    maxpages = int(maxpages.split('maxpages')[1].split('.')[0])
    return date, maxpages


def get_all_csvs_w_date(city_id):
    csvs = []
    paths = get_all_csv_paths(city_id)
    if paths is None or len(paths) == 0:
        return None
    else:
        for p in paths:
            date, maxpages = parse_info_from_csv_name(p)
            csvs.append({'date': date, 'maxpages': maxpages, 'file': p})
        return pd.DataFrame(csvs).sort_values('date', ascending=False)


def load_previous_csv(city_id):
    df = get_all_csvs_w_date(city_id)
    if df is None:
        return None
    else:
        path = df.iloc[0].file  # 0 would be the current file, 1 is the previous file
        logger.info(f"load previous csv: {path}")
        return pd.read_csv(path)


def download_metadata(venue_link):
    headers = {'user-agent': config.USER_AGENT}
    page_source = requests.get(venue_link, headers=headers).content
    venue_soup = bs.BeautifulSoup(page_source, 'html.parser')
    script_section = venue_soup.find('script', type='application/ld+json')
    return json.loads(script_section.text, strict=False)


def get_metadata_from_df(df, name):
    prev_metadata = df[df.name == name].metadata.values[0]
    prev_metadata = prev_metadata.replace("'", '"').replace("\\", "")
    return json.loads(prev_metadata, strict=False)


def add_venue_metadata(venues, city_id):
    logger.info("Adding metadata")
    previous_venues = load_previous_csv(city_id)
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


def store_csv(df, date, city_id):
    filename = f'venues_{date}_city{city_id}_maxpages{config.MAX_PAGES}.csv'
    logger.info(f"Storing into {filename}")
    df.to_csv(os.path.join(config.DATA_DIR, filename), index=False)


def main():
    download_date = pd.Timestamp.today().date()
    for city_id, city_name in config.CITY_IDS.items():
        logger.info(f"Starting to scrape city {city_name}...")
        venues_source = download_venues_source(city_id)
        venues = extract_venues(venues_source)
        venues_w_metadata = add_venue_metadata(venues, city_id)
        store_csv(venues_w_metadata, download_date, city_id)
        logger.info(f"Scraping city {city_name} finished!")


if __name__ == '__main__':
    main()

