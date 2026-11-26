import io
import re
import sys
import unicodedata

import pandas as pd

MESES = {'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
         'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12}
# nombre en el CSV de generación (ya sin acentos y en mayúsculas) -> nombre en el catálogo de nodos
ALIAS = {'ESTADO DE MEXICO': 'MEXICO',
         'COAHUILA': 'COAHUILA DE ZARAGOZA',
         'MICHOACAN': 'MICHOACAN DE OCAMPO',
         'VERACRUZ': 'VERACRUZ DE IGNACIO DE LA LLAVE'}


def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s).strip().upper()


def preparar_generacion(ruta_csv, ruta_catalogo):
    # ---------- 1) CSV: quitar metadatos y pasar a formato largo ----------
    for enc in ('utf-8-sig', 'latin-1'):
        try:
            with open(ruta_csv, encoding=enc) as f:
                lineas = f.read().splitlines()
            break
        except UnicodeDecodeError:
            continue
    ini = next(i for i, l in enumerate(lineas) if re.search(r'\bENE/\d{4}', l))   # fila de encabezado
    raw = pd.read_csv(io.StringIO('\n'.join(lineas[ini:])))
    raw = raw.rename(columns={raw.columns[0]: 'estado'})
    meses = [c for c in raw.columns[1:] if re.fullmatch(r'[A-Z]{3}/\d{4}', str(c).strip())]
    raw = raw.dropna(subset=meses, how='all')            # fuera filas vacías y notas al pie
    raw['estado'] = raw['estado'].astype(str).str.replace(r'[¹²³]', '', regex=True).str.strip()

    largo = raw.melt(id_vars='estado', value_vars=meses, var_name='mes_txt', value_name='generacion_mwh')
    largo['generacion_mwh'] = pd.to_numeric(largo['generacion_mwh'], errors='coerce')
    largo = largo.dropna(subset=['generacion_mwh'])      # quita los meses sin dato (p. ej. sep–oct 2026 vacíos)
    mm = largo['mes_txt'].str.strip().str.split('/', expand=True)
    largo['fecha'] = pd.to_datetime({'year': mm[1].astype(int), 'month': mm[0].map(MESES), 'day': 1})
    largo = largo.drop(columns='mes_txt')

    total = largo[largo['estado'] == 'Total'].set_index('fecha')['generacion_mwh']
    gen = largo[largo['estado'] != 'Total'].copy()

    # ---------- 2) Catálogo: zona (centro de control regional) de cada estado ----------
    cat = pd.read_excel(ruta_catalogo, sheet_name=0, header=1)
    cat.columns = [str(c).strip() for c in cat.columns]
    ent, reg = 'ENTIDAD FEDERATIVA (INEGI)', 'CENTRO DE CONTROL REGIONAL'
    cat = cat[(cat[reg] != 'No Aplica') & (cat[ent] != 'No Aplica')].copy()
    cat['_estado'] = cat[ent].map(norm)
    n = cat.groupby(['_estado', reg]).size().rename('nodos').reset_index()
    n['pct'] = n['nodos'] / n.groupby('_estado')['nodos'].transform('sum')
    zonas = (n.sort_values('nodos', ascending=False)
              .drop_duplicates('_estado')                # zona dominante = la que tiene más nodos en el estado
              .rename(columns={reg: 'zona', 'pct': 'zona_pct_nodos'})
              [['_estado', 'zona', 'zona_pct_nodos']])

    gen['_estado'] = gen['estado'].map(norm).replace(ALIAS)
    gen = gen.merge(zonas, on='_estado', how='left').drop(columns='_estado')
    gen = (gen[['fecha', 'estado', 'zona', 'zona_pct_nodos', 'generacion_mwh']]
           .sort_values(['estado', 'fecha']).reset_index(drop=True))

    # ---------- 3) Revisión ----------
    print(f"{len(gen):,} filas; {gen['fecha'].min():%Y-%m} a {gen['fecha'].max():%Y-%m}")
    print('Sin zona:', sorted(gen.loc[gen['zona'].isna(), 'estado'].unique()))
    dividen = gen.loc[gen['zona_pct_nodos'] < 1, ['estado', 'zona', 'zona_pct_nodos']].drop_duplicates()
    print('Estados repartidos en varias zonas (se usó la dominante):')
    print(dividen.assign(zona_pct_nodos=lambda d: (d['zona_pct_nodos'] * 100).round(0)).to_string(index=False))
    dif = (gen.groupby('fecha')['generacion_mwh'].sum() - total).abs().max()
    print(f'Máxima diferencia entre la suma de estados y la fila Total: {dif:,.1f} MWh')
    return gen, total


if __name__ == '__main__':
    g, t = preparar_generacion(sys.argv[1], sys.argv[2])
    print(g.head())
    print(g.groupby('zona')['generacion_mwh'].sum().round(0))
