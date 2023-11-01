import glob
import os
import logging

import pandas as pd

import config


logger = logging.getLogger(__name__)
logging.basicConfig(level = logging.INFO)



def parse_list(x):
    return x.strip("[]").replace("'", '').split(", ")


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
    csvs_df = get_all_csvs_w_date(city_id)
    if csvs_df is None:
        return None, None
    else:
        first_row = csvs_df.iloc[0]
        path = first_row.file  # 0 would be the current file, 1 is the previous file
        logger.info(f"load previous csv: {path}")
        df = pd.read_csv(path, converters={"plans": parse_list, "disciplines": parse_list})
        return df, first_row.date