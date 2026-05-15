import time
import requests
from bs4 import BeautifulSoup

import pandas as pd

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)


###############################################################################
# consts & exceptions
###############################################################################

URL = 'https://www.cndc.bo/eventos/eventos_mes.php'
DATA = {
    'tipo': 63,
    'mesx': 9,
    'aniox': 2025,
    'btn': 'Buscar',
}
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


class RequestException(Exception):
    'Max Retry Exception'
    pass


class ProcessException(Exception):
    'No table exception'
    pass


###############################################################################
# fetch & process
###############################################################################

MAXRETRY = 3
def do_request(data, _retry=1):
    if _retry > MAXRETRY:
        raise RequestException('max retry reached for {}.'.format(data))

    try:
        return requests.post(URL, data=data, timeout=60)
    except:
        time.sleep(2 ** _retry)
        return do_request(data, _retry + 1)


def do_process(req, tipo):
    soup = BeautifulSoup(req.content, 'lxml')
    for th in soup.find_all('th'):
        th.name = 'td'

    try:
        df = pd.read_html(str(soup), header=None)[2]
    except Exception as e:
        raise ProcessException(e)

    df = df.T.dropna(how='all').T.dropna(how='all')
    df.columns = COLUMNS[tipo]

    if not df.iloc[0, 0][0].isdigit():
        df = df.iloc[1:]

    df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True)

    return df


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


def do_update(year, month):
    data = DATA.copy()

    data['aniox'] = year
    data['mesx'] = month

    for tipo in TIPOS.keys():
        data['tipo'] = tipo
        try:
            req = do_request(data)
            dft = do_process(req, tipo)

        except RequestException as e:
            print('Max requests reached for {}'.format(data['tipo']))
            continue

        except ProcessException as e:
            print('No `{tipo}` data available for {aniox}/{mesx}'.format(**data))
            continue

        do_merge(dft, tipo)


###############################################################################
# run
###############################################################################

if __name__ == '__main__':
    now = pd.to_datetime('now') - pd.DateOffset(days=1)
    do_update(now.year, now.month)
