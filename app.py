import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

import utils


PLANS = ('S', 'M', 'L', 'XL')
DISPLAY_COLUMNS = ['city_name', 'name', 'disciplines', 'plans',
                   'plus_options', 'district', 'link']
DEFAULT_DISCIPLINES = ['Sauna', 'Wellness', 'Massage', 'Spa']


st.set_page_config(
    page_title="Urban Sports Club Search",
    page_icon=":muscle:",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "# Urban Sports Club Search"
    }
)


def parse_list(x):
    return x.strip("[]").replace("'", '').split(", ")


@st.cache_data
def load_data(filepath):
    df = pd.read_csv(filepath, converters={"plans": parse_list,
                                           "disciplines": parse_list})
    return df


@st.cache_data
def verify_data(df):
    assert set(PLANS).issubset(set(df['min_plan'].unique()))
    return None


@st.cache_data
def get_center_coords_and_zoom(df):
    if len(df) == 0:
        # No venues selected
        lat, lon =  [0, 0]
        zoom = 2
    else:
        # Get location of city w/ most venues
        city = df.city_name.value_counts().index[0]
        subdf = df[df.city_name == city]
        lat, lon = subdf.latitude.mean(), subdf.longitude.mean()
        zoom = 11
    return [lat, lon], zoom


@st.cache_data
def get_disciplines(df):
    flattened = [item for row in df['disciplines'].values
                 for item in row]
    return sorted(list(set(flattened)))


load_previous_csv = st.cache_data(utils.load_previous_csv)
combine_most_recent_csvs = st.cache_data(utils.combine_most_recent_csvs)


def render_sidebar(disciplines, cities, date):
    st.sidebar.subheader("Urban Sports Club Search")

    st.sidebar.write("Cities")
    if st.sidebar.button("Select all", key='btn_cities'):
        st.session_state.select_cities = cities

    # Set defaults like this to avoid warning, see https://discuss.streamlit.io/t/why-do-default-values-cause-a-session-state-warning/15485/6
    if "select_cities" not in st.session_state:
        st.session_state.select_cities = ["Berlin - Deutschland"]
    select_cities = st.sidebar.multiselect(
        "City", cities,
        key='select_cities', label_visibility="collapsed"
    )
    st.sidebar.markdown('###')

    st.sidebar.write("Plans")
    check_cols = st.sidebar.columns(len(PLANS))
    check_plans = []
    for i, p in enumerate(PLANS):
        with check_cols[i]:
            check_plans.append(st.checkbox(p, p in PLANS[1:-1]))

    select_plus = st.sidebar.toggle('Plus Only')

    st.sidebar.markdown('###')

    st.sidebar.write("Disciplines")
    if st.sidebar.button("Select all", key='btn_disciplines'):
        st.session_state.select_disciplines = disciplines

    # Set defaults like this to avoid warning, see https://discuss.streamlit.io/t/why-do-default-values-cause-a-session-state-warning/15485/6
    if "select_disciplines" not in st.session_state:
        st.session_state.select_disciplines = set(disciplines).intersection(DEFAULT_DISCIPLINES)
    select_disciplines = st.sidebar.multiselect(
        "Discipline(s)", disciplines,
        key='select_disciplines',
        label_visibility="collapsed"
    )
    st.sidebar.caption(f"Last updated: {date}")
    return select_cities, select_disciplines, select_plus, check_plans


def render_map(df, location_coords, zoom):
    m = folium.Map(tiles="OpenStreetMap")
    for i, row in df.iterrows():
        if row.plus_options:
            icon = 'glyphicon glyphicon-plus'
        else:
            icon = "glyphicon glyphicon-heart-empty"

        if row.min_plan == 'S':
            color = 'lightgreen'
        elif row.min_plan == 'M':
            color = 'lightblue'
        elif row.min_plan == 'L':
            color = 'lightred'
        elif row.min_plan == 'XL':
            color = 'darkred'

        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=f"<a target='blank' href={row['link']}>{row['name']}</a><br>{'/'.join(row['disciplines'])}<br><b>{row['plans']}",
            icon=folium.Icon(icon=icon, color=color),
        ).add_to(m)

    st_map = st_folium(m, height=400, use_container_width=True,
                       zoom=zoom,
                       center=location_coords,
                       key='st_folium_map',
                       returned_objects=[])


def render_table(df):
    st.dataframe(df[DISPLAY_COLUMNS],
                 hide_index=True,
                 column_config={
                     "city_name": st.column_config.Column("City", width="small"),
                     "disciplines": st.column_config.Column("Disciplines", width="medium"),
                     "name": st.column_config.Column("Studio Name", width="medium"),
                     "plans": "Plans",
                     "plus_options": "Plus",
                     "district": "District",
                     'link': st.column_config.LinkColumn("Link", width='small')
                 }
                 )


def filter_df(df, select_disciplines, select_plus, check_plans, select_cities):
    disciplines_filter = df['disciplines'].apply(
        lambda x: not set(select_disciplines).isdisjoint(set(x))
    )
    plus_filter = df['plus_options'] if select_plus else True
    selected_plans = [plan for plan, c in zip(PLANS, check_plans) if c]
    plan_filter = df['plans'].apply(
        lambda x: not set(selected_plans).isdisjoint(set(x))
    )
    min_plan_filter = df['min_plan'].isin(selected_plans)
    cities_filter = df['city_name'].isin(select_cities)
    return df[plus_filter & disciplines_filter & plan_filter & cities_filter & min_plan_filter].sort_values(['city_name', 'name'])


def main():
    df, date = combine_most_recent_csvs()
    verify_data(df)
    disciplines = get_disciplines(df)
    cities = sorted(list(set(df['city_name'])))
    select_cities, select_disciplines, select_plus, check_plans = \
        render_sidebar(disciplines, cities, date)

    filtered_df = filter_df(df, select_disciplines, select_plus,
                            check_plans, select_cities)
    center_coords, zoom = get_center_coords_and_zoom(filtered_df)
    render_map(filtered_df, center_coords, zoom)
    render_table(filtered_df)


if __name__ == '__main__':
    main()
