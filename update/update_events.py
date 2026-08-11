import time
import requests
from bs4 import BeautifulSoup

import pandas as pd

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)


###############################################################################
# consts & exceptions
###############################################################################

BASE_URL = 'https://www.cndc.bo/wp-json/cndc/v1/eventos'

TIPOS = {
    45: 'eventos_mayores',
    62: 'instalaciones_en_mantenimiento',
    24: 'fallas_durante_la_operacion',
    23: 'instalaciones_no_disponibles_por_otras_causas',
    63: 'operacion_con_potencia_limitada',
    61: 'regimen_de_restriccion_por_transmision',
    26: 'reemplazos_carga_base_otros',
    65: 'redespacho',
    66: 'otros_eventos'
}
TIPOS_IMAP = {
    'eventos_mayores': 45,
    'mantenimiento': 62,
    'fallas': 24,
    'no_disponibles': 23,
    'potencia_limitada': 63,
    'restriccion_transmision': 61,
    'reemplazos': 26,
    'redespacho': 65,
    'otros': 66
}

COLUMNS = {
    23: ['fecha', 'agente', 'cat', 'componente', 'de_hrs', 'a_hrs', 'causa'],
    26: ['fecha', 'agente', 'cat', 'componente', 'de_hrs', 'a_hrs', 'descripcion'],
    62: ['fecha', 'agente', 'cat', 'componente', 'de_hrs', 'a_hrs', 'tipo', 'trabajo'],
    65: ['fecha', 'agente', 'cat', 'componente', 'de_hrs', 'a_hrs', 'descripcion'],
    61: ['fecha', 'agente', 'cat', 'componente', 'de_hrs', 'a_hrs', 'causa'],
    63: ['fecha', 'agente', 'cat', 'componente', 'de_hrs', 'a_hrs', 'potencia', 'causa'],
    45: ['fecha', 'descripcion', 'area', 'agente_afectado', 'cat', 'de_hrs', 'a_hrs', 'mw_desc', 'causa'],
    66: ['fecha', 'de_hrs', 'a_hrs', 'descripcion'],
    24: ['fecha', 'agente', 'cat', 'componente', 'de_hrs', 'a_hrs', 'causa', 'tipo', 'edac', 'n_inf', 'agente_afectado'],
}
DAY_DIFF = 1


###############################################################################
# fetch & process
###############################################################################

def do_merge(dft, tipo):
    dft = dft.convert_dtypes()
    fn = './data/{}.csv'.format(TIPOS[tipo])

    dfs = pd.read_csv(fn)
    dfs['fecha'] = pd.to_datetime(dfs['fecha'])

    dfs = dfs[dfs['fecha'] < dft['fecha'].min()]
    dfs = pd.concat([dfs, dft], ignore_index=True)

    dfs = dfs.convert_dtypes()

    dfs = dfs.sort_values(['fecha', 'de_hrs', 'a_hrs'])
    dfs.to_csv(fn, index=False)


def latest_date():
    fn = './data/otros_eventos.csv'
    nrows = sum(1 for _ in open(fn, 'r'))
    lrow = pd.read_csv(filename, skiprows=nrows - 1, header=None)

    return pd.to_datetime(lrow.iloc[0, 0])


def do_update():
    ldate = latest_date() - pd.Timedelta(days=1)

    events_df = []
    for cdate in pd.date_range(
        pd.to_datetime(last_row.iloc[0, 0]) - pd.Timedelta(days=DAY_DIFF),
        pd.to_datetime('now') - pd.Timedelta(days=DAY_DIFF),
        freq='D'
    ):
        req = requests.get(
            BASE_URL, params={'fecha', cdate.strftime('%Y-%m-%d')}
        )

        dated_events_df = {
            TIPOS_IMAP[_['seccion']]: pd.DataFrame(_['filas']).assign(fecha=cdate)
            for _ in req.json()['secciones']
        }
        events_df.append(dated_events_df)

    events_df = pd.DataFrame(events_df)

    for event_type in events_df.columns:
        event_df = events_df[event_type]
        event_df = pd.concat(event_df.values, ignore_index=True)

        if event_type in [26, 65, 66]:
            event_df = event_df.drop(
                columns='descripcion'
            ).rename(columns={'causa': 'descripcion'})

        if event_type == 65:
            event_df = event_df.drop(
                columns='componente'
            ).rename(columns={'central_sistema': 'componente'})

        event_df = event_df.reindex(COLUMNS[event_type], axis=1)

        do_merge(event_df, event_type)


###############################################################################
# run
###############################################################################

if __name__ == '__main__':
    do_update()
