import os

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium


DATE = '2023-10-23'
CITY_ID = 1  # Berlin
MAX_PAGES = 42
FILENAME = f'venues_{DATE}_city{CITY_ID}_maxpages{MAX_PAGES}.csv'
FILEPATH = os.path.join('data', FILENAME)
PLANS = ('S', 'M', 'L')
DISPLAY_COLUMNS = ['name', 'disciplines', 'min_plan', 'plus_options',
                   'district', 'link']
DEFAULT_DISCIPLINES = ['Sauna', 'Fitness', 'Massage']
LOCATIONS = {"Berlin": [52.5200, 13.4050]}
ZOOM_START = 10


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


def main():
    df = load_data(FILEPATH)
    verify_data(df)
    disciplines = get_disciplines(df)

    # ----------------- SIDEBAR -----------------
    st.sidebar.subheader("Urban Sports Club Search")

    st.sidebar.write("City")
    st.sidebar.selectbox("City", ["Berlin"], 0,
                         label_visibility="collapsed"
    )

    st.sidebar.markdown('###')

    st.sidebar.write("Minimum Plan")
    col1, col2 = st.sidebar.columns([0.6, 0.4])
    select_plan = col1.radio(
        'Minimum Plan', PLANS, 1,
        horizontal=True,
        label_visibility="collapsed"
    )
    select_plus = col2.checkbox('Plus Only')

    st.sidebar.markdown('###')

    st.sidebar.write("Discipline(s)")
    if st.sidebar.button("Select all"):
        st.session_state.select_disciplines = disciplines

    select_disciplines = st.sidebar.multiselect(
        "Discipline(s)", disciplines, DEFAULT_DISCIPLINES,
        key='select_disciplines',
        label_visibility="collapsed"
    )

    # ----------------- MAIN FRAME -----------------

    tab_map, tab_table = st.tabs(["Map", "Table"])

    disciplines_filter = df['disciplines'].apply(
        lambda x: not set(select_disciplines).isdisjoint(set(x))
    )
    plus_filter = df['plus_options'] if select_plus else True
    plan_filter = df['min_plan'] == select_plan

    filtered_df = df[plus_filter & disciplines_filter & plan_filter]

    with tab_map:

        m = folium.Map(tiles="OpenStreetMap")

        for i, row in filtered_df.iterrows():
            if row.plus_options:
                icon = 'glyphicon glyphicon-plus'
            else:
                icon = "glyphicon glyphicon-heart-empty"

            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=f"<a href={row['link']}>{row['name']}</a><br>{'/'.join(row['disciplines'])}<br><b>{row['min_plan']}",
                icon=folium.Icon(icon=icon)
            ).add_to(m)
        st_map = st_folium(m, width=800, height=400,
                  use_container_width=True,
                  center=LOCATIONS["Berlin"],
                  zoom= ZOOM_START,
                  returned_objects=[]
                  )


    with tab_table:
        st.dataframe(filtered_df[DISPLAY_COLUMNS],
                     hide_index=True,
                     column_config={
                         "disciplines": st.column_config.Column("Disciplines", width="medium"),
                         "name":  st.column_config.Column("Studio Name", width="medium"),
                         "min_plan": "Min. Plan",
                         "plus_options": "Plus?",
                         "district": "District",
                         'link': st.column_config.LinkColumn("Link", width='small')
                     }
                     )


if __name__ == '__main__':
    main()
