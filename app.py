import os

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

from utils import load_previous_csv

import config


PLANS = ('S', 'M', 'L')
DISPLAY_COLUMNS = ['name', 'disciplines', 'min_plan', 'plus_options',
                   'district', 'link']
DEFAULT_DISCIPLINES = ['Sauna', 'Wellness', 'Massage', 'Spa']
ZOOM_START = 11


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
def get_average_coords(df):
    return df.latitude.mean(), df.longitude.mean()


@st.cache_data
def get_disciplines(df):
    flattened = [item for row in df['disciplines'].values
                 for item in row]
    return sorted(list(set(flattened)))


load_previous_csv = st.cache_data(load_previous_csv)


def render_beginning_sidebar():
    st.sidebar.subheader("Urban Sports Club Search")

    st.sidebar.write("City")
    select_city = st.sidebar.selectbox("City",
                                       config.CITIES, 0,
                                       label_visibility="collapsed"
    )
    return select_city


def render_remaining_sidebar(disciplines, date):
    st.sidebar.markdown('###')

    st.sidebar.write("Minimum Plan")
    select_plan = st.sidebar.radio(
        'Minimum Plan', list(PLANS) + ['All'], 4,
        horizontal=True,
        label_visibility="collapsed"
    )
    select_plus = st.sidebar.checkbox('Plus Only')

    st.sidebar.markdown('###')

    st.sidebar.write("Discipline(s)")
    if st.sidebar.button("Select all"):
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
    return select_disciplines, select_plus, select_plan


def render_map(df, location_coords):
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

        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=f"<a target='blank' href={row['link']}>{row['name']}</a><br>{'/'.join(row['disciplines'])}<br><b>{row['min_plan']}",
            icon=folium.Icon(icon=icon, color=color),
        ).add_to(m)

    st_map = st_folium(m, height=400, use_container_width=True,
                       zoom=ZOOM_START,
                       center=location_coords,
                       key='st_folium_map',
                       returned_objects=[])


def render_table(df):
    st.dataframe(df[DISPLAY_COLUMNS],
                 hide_index=True,
                 column_config={
                     "disciplines": st.column_config.Column("Disciplines", width="medium"),
                     "name":  st.column_config.Column("Studio Name", width="medium"),
                     "min_plan": "Min. Plan",
                     "plus_options": "Plus",
                     "district": "District",
                     'link': st.column_config.LinkColumn("Link", width='small')
                 }
                 )

def filter_df(df, select_disciplines, select_plus, select_plan):
    disciplines_filter = df['disciplines'].apply(
        lambda x: not set(select_disciplines).isdisjoint(set(x))
    )
    plus_filter = df['plus_options'] if select_plus else True
    plan_filter = True if select_plan == 'All' else df['min_plan'] == select_plan
    return df[plus_filter & disciplines_filter & plan_filter].sort_values(['name'])


def main():
    select_city = render_beginning_sidebar()
    df, date = load_previous_csv(config.CITIES[select_city])
    city_coords = get_average_coords(df)
    verify_data(df)
    disciplines = get_disciplines(df)
    select_disciplines, select_plus, select_plan = \
        render_remaining_sidebar(disciplines, date)

    filtered_df = filter_df(df, select_disciplines, select_plus, select_plan)
    render_map(filtered_df, city_coords)
    render_table(filtered_df)


if __name__ == '__main__':
    main()
