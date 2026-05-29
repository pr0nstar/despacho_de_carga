import os
import io
import glob
import zipfile
import unidecode

import requests

import numpy as np
import pandas as pd


###############################################################################
# consts
###############################################################################

URL = 'https://www.cndc.bo/media/archivos/boletindiario/deener_{:02n}{:02n}{}.zip'
FN = './dump/demanda/{}{:02n}{:02n}.zip'
DATA = './data_demanda'
CSV = './data_demanda/{}.csv'


###############################################################################
# fetch & process
###############################################################################

def download(down_date):
    down_url = URL.format(down_date.day, down_date.month, str(down_date.year)[-2:])
    down_fn = FN.format(str(down_date.year)[-2:], down_date.month, down_date.day)

    if os.path.isfile(down_fn):
        return down_fn

    try:
        req = requests.get(down_url, timeout=30)
        req.raise_for_status()

        with open(down_fn, 'wb') as f:
            f.write(req.content)

        return down_fn

    except KeyboardInterrupt:
        raise

    except Exception as e:
        return None


def do_process(fn):
    with zipfile.ZipFile(fn, 'r') as original_zip:
        file_list = original_zip.namelist()
        with original_zip.open(file_list[0], 'r') as first_file_handle:
            ff_content = first_file_handle.read()

    df = pd.read_excel(io.BytesIO(ff_content), header=None)
    df = df.iloc[6:]

    df = df.T.dropna(how='all').T.dropna(how='all')
    df = df.loc[:(df.iloc[:, 0] == 'TOTAL').idxmax()]

    df_tmask = df.iloc[:, 0].str.contains('TOTAL -')

    if df_tmask.any():
        df.iloc[:, 0] = (
            df.loc[df_tmask, 0].str.split(' - ').str[1].str.strip().reindex(df.index).bfill() + ' - '
        ).fillna('') + df.iloc[:, 0].str.replace(' - ', ' ')
        df = df[~df_tmask]

    df_tmask = df.iloc[:, 0].str.contains(' - C. No')
    df.loc[df_tmask, 0] = df.loc[df_tmask, 0].str.split(' - ').str[0].str.strip()

    df.loc[:, 0] = df.loc[:, 0].apply(unidecode.unidecode)

    df.columns = df.iloc[0].str.strip()
    df = df.iloc[1:]

    df.index = df.iloc[:, 0].str.strip()
    df = df.iloc[:, 1:]

    df = df.iloc[:-1, :24]
    df.columns = pd.to_datetime(
        fn.split('/')[-1].split('.')[0] + df.columns.str.replace('24:00', '23:59'),
        format='%y%m%d%H:%M'
    )

    df.index.name = 'agente'
    df.columns.name = 'hora'

    return df.stack().rename('demanda')


def process(fn):
    try:
        return do_process(fn)
    except Exception as e:
        print(fn)
        raise(e)


###############################################################################
# update
###############################################################################

def read_latest_date():
    fn = sorted(glob.glob(os.path.join(DATA, '*.csv')))[-1]
    df = pd.read_csv(fn, usecols=['hora'])
    df['hora'] = pd.to_datetime(df['hora'])

    return df['hora'].max()


def do_merge(df):
    df['hora'] = pd.to_datetime(df['hora'])

    for year, dft in df.groupby(df['hora'].dt.year):
        fn = CSV.format(year)

        if os.path.isfile(fn):
            dfs = pd.read_csv(fn)
            dfs['hora'] = pd.to_datetime(dfs['hora'])
            dfs = dfs[dfs['hora'] < dft['hora'].min()]
            dfs = pd.concat([dfs, dft], ignore_index=True)
        else:
            dfs = dft

        dfs = dfs.sort_values(['hora', 'agente'])
        dfs.to_csv(fn, index=False)


def do_update():
    base_date = read_latest_date().normalize()
    end_date = pd.to_datetime('now').normalize() - pd.DateOffset(days=1)

    if base_date > end_date:
        return

    os.makedirs(os.path.dirname(FN), exist_ok=True)

    fns = []
    for _ in np.arange((end_date - base_date).days + 1):
        down_date = base_date + pd.DateOffset(days=_)
        down_fn = download(down_date)
        if down_fn is not None:
            fns.append(down_fn)

    fns = sorted(fns)

    if len(fns) == 0:
        return

    df = [process(_) for _ in fns]
    df = pd.concat(df)
    df = df.astype(float)
    df = df.rename('demanda').reset_index()

    do_merge(df)


###############################################################################
# run
###############################################################################

if __name__ == '__main__':
    do_update()
