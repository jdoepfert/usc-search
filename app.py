import os

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium


DATE = '2023-10-30'
CITY_ID = 1  # Berlin
MAX_PAGES = 44
FILENAME = f'venues_{DATE}_city{CITY_ID}_maxpages{MAX_PAGES}.csv'
FILEPATH = os.path.join('data', FILENAME)
PLANS = ('S', 'M', 'L')
DISPLAY_COLUMNS = ['name', 'disciplines', 'min_plan', 'plus_options',
                   'district', 'link']
DEFAULT_DISCIPLINES = ['Sauna', 'Wellness', 'Massage', 'Spa']
LOCATIONS = {"Berlin": [52.5200, 13.4050]}
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


@st.cache_data  # 👈 Add the caching decorator
def load_data(filepath):
    df = pd.read_csv(filepath, converters={"plans": parse_list,
                                           "disciplines": parse_list})
    return df


@st.cache_data  # 👈 Add the caching decorator
def verify_data(df):
    assert set(df['min_plan'].unique()) == set(PLANS)
    return None


@st.cache_data  # 👈 Add the caching decorator
def get_disciplines(df):
    flattened = [item for row in df['disciplines'].values
                 for item in row]
    return sorted(list(set(flattened)))


def render_sidebar(disciplines):
    # ----------------- SIDEBAR -----------------
    st.sidebar.subheader("Urban Sports Club Search")

    st.sidebar.write("City")
    st.sidebar.selectbox("City", ["Berlin"], 0,
                         label_visibility="collapsed"
                         )

    st.sidebar.markdown('###')

    st.sidebar.write("Minimum Plan")
    select_plan = st.sidebar.radio(
        'Minimum Plan', list(PLANS) + ['All'], 1,
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
        st.session_state.select_disciplines = DEFAULT_DISCIPLINES

    select_disciplines = st.sidebar.multiselect(
        "Discipline(s)", disciplines,
        key='select_disciplines',
        label_visibility="collapsed"
    )
    st.sidebar.caption(f"Last updated: {DATE}")
    return select_disciplines, select_plus, select_plan


def render_map(df):
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
            popup=f"<a href={row['link']}>{row['name']} target='blank'</a><br>{'/'.join(row['disciplines'])}<br><b>{row['min_plan']}",
            icon=folium.Icon(icon=icon, color=color),
        ).add_to(m)

    st_map = st_folium(m, height=400, use_container_width=True,
                       zoom=ZOOM_START,
                       center=LOCATIONS['Berlin'],
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
    df = load_data(FILEPATH)
    verify_data(df)
    disciplines = get_disciplines(df)
    select_disciplines, select_plus, select_plan = render_sidebar(disciplines)
    filtered_df = filter_df(df, select_disciplines, select_plus, select_plan)
    render_map(filtered_df)
    render_table(filtered_df)


if __name__ == '__main__':
    main()
