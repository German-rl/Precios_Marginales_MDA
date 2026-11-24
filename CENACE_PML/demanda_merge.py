#!/usr/bin/env python3
"""Une los CSV de Demanda Real (Balance) de CENACE en un solo archivo.

Cada CSV es un día de operación y NO trae la fecha dentro; la fecha va en el nombre:
  Demanda Real Balance_0_v3 Dia Operacion 2022-01-01 v2022 01 15_12 25 01.csv
                                           ^^^^^^^^^^   ^^^^^^^^^^^^^^^^^^^
                                           día          versión (cuándo se generó)

Si hay varias versiones del mismo día, se queda la más reciente.

Uso:
  1) Pon el ZIP (o los CSV) en la carpeta data/demanda/ junto a este script. No hace falta extraerlo.
  2) python demanda_merge.py
Resultado: data/demanda_balance.csv
"""
import io
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

# ----------------------------- CONFIGURACIÓN ------------------------------
# Las rutas son relativas a la carpeta del script, no a la carpeta desde la que lo ejecutes.
DATA = Path(__file__).resolve().parent / "data"
ENTRADA = DATA / "Demanda"                    # aquí va el ZIP o los CSV (se busca en subcarpetas)
SALIDA = DATA / "demanda_balance.csv"
# --------------------------------------------------------------------------

RE_DIA = re.compile(r"Dia Operaci.n\s+(\d{4})-(\d{2})-(\d{2})", re.I)
RE_FECHA = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_VERSION = re.compile(r"v(\d{4}) (\d{2}) (\d{2})_(\d{2}) (\d{2}) (\d{2})")


def sin_acentos(s):
    s = str(s).strip().lower()
    for a, b in zip("áéíóúñ", "aeioun"):
        s = s.replace(a, b)
    return s


def archivos():
    """Devuelve (nombre, bytes) de cada CSV, ya sea suelto o dentro de un ZIP."""
    if not ENTRADA.exists():
        sys.exit(f"No existe la carpeta {ENTRADA}. Créala y pon ahí el ZIP o los CSV.")
    for p in sorted(ENTRADA.rglob("*")):
        if p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p) as z:
                for info in z.infolist():
                    nombre = Path(info.filename).name
                    if info.filename.lower().endswith(".csv") and not nombre.startswith("._"):
                        yield nombre, z.read(info)
        elif p.suffix.lower() == ".csv" and not p.name.startswith("._"):
            yield p.name, p.read_bytes()


def leer(datos):
    """Lee un CSV tolerando BOM, codificación, separador y filas de título arriba del encabezado."""
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texto = datos.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    lineas = texto.splitlines()
    ini = next((i for i, l in enumerate(lineas)
                if "hora" in sin_acentos(l) and "area" in sin_acentos(l)), 0)
    enc_linea = lineas[ini]
    sep = max((",", ";", "\t"), key=enc_linea.count)
    d = pd.read_csv(io.StringIO("\n".join(lineas[ini:])), sep=sep, skipinitialspace=True)
    d.columns = [sin_acentos(c) for c in d.columns]
    # la columna de valores se llama "Pronostico (MWh)" aunque el archivo sea Demanda Real
    col_val = next((c for c in d.columns if c.startswith(("pronostico", "demanda", "retiro", "valor"))),
                   d.columns[-1])
    d = d.rename(columns={col_val: "demanda_mwh"})
    v = d["demanda_mwh"].astype(str).str.strip()
    v = v.str.replace(",", ".", regex=False) if sep == ";" else v.str.replace(",", "", regex=False)
    d["demanda_mwh"] = pd.to_numeric(v, errors="coerce")
    d["hora"] = pd.to_numeric(d["hora"], errors="coerce")
    for c in ("sistema", "area"):
        d[c] = d[c].astype(str).str.strip()
    return d[["sistema", "area", "hora", "demanda_mwh"]]


def main():
    frames, sin_fecha, con_error = [], [], []
    for nombre, datos in archivos():
        m = RE_DIA.search(nombre) or RE_FECHA.search(nombre)
        if not m:
            sin_fecha.append(nombre)
            continue
        fecha = pd.Timestamp(int(m[1]), int(m[2]), int(m[3]))
        v = RE_VERSION.search(nombre)
        version = pd.Timestamp(*(int(x) for x in v.groups())) if v else pd.NaT
        try:
            d = leer(datos)
        except Exception as e:
            con_error.append((nombre, str(e)))
            continue
        d["fecha"], d["version"] = fecha, version
        frames.append(d)

    if not frames:
        sys.exit(f"No encontré CSV en {ENTRADA}.")
    print(f"{len(frames):,} archivos leídos.")
    if sin_fecha:
        print(f"AVISO: {len(sin_fecha)} archivos sin fecha en el nombre, ignorados. Ej.: {sin_fecha[:2]}")
    if con_error:
        print(f"AVISO: {len(con_error)} archivos no se pudieron leer. Ej.: {con_error[:2]}")

    df = pd.concat(frames, ignore_index=True)

    # Varias versiones del mismo día: me quedo con la más reciente
    clave = ["fecha", "sistema", "area", "hora"]
    antes = len(df)
    df = (df.sort_values("version", na_position="first")
            .drop_duplicates(clave, keep="last"))
    print(f"Filas duplicadas por versiones descartadas: {antes - len(df):,}")

    # La hora de CENACE va de 1 a 24; la 25 solo existe el día del cambio de horario (oct. 2022)
    extra = df["hora"] > 24
    if extra.any():
        print(f"AVISO: {int(extra.sum())} filas con hora 25 descartadas (cambio de horario); "
              "haz lo mismo con los precios (df['hora'] <= 24) antes de unir.")
        df = df[~extra]

    df["timestamp"] = df["fecha"] + pd.to_timedelta(df["hora"] - 1, unit="h")
    df = (df[["timestamp", "fecha", "hora", "sistema", "area", "demanda_mwh"]]
          .sort_values(["sistema", "area", "timestamp"]).reset_index(drop=True))
    SALIDA.parent.mkdir(exist_ok=True)
    df.to_csv(SALIDA, index=False)
    print(f"{len(df):,} filas -> {SALIDA}")

    # ------------------------------ revisión -------------------------------
    print(f"\nRango de fechas: {df['fecha'].min():%Y-%m-%d} a {df['fecha'].max():%Y-%m-%d}")
    print("Áreas por sistema:")
    for s, g in df.groupby("sistema"):
        print(f"  {s}: {sorted(g['area'].unique())}")
    dias = pd.date_range(df["fecha"].min(), df["fecha"].max(), freq="D")
    faltan = dias.difference(df["fecha"].unique())
    print(f"Días sin archivo en el rango: {len(faltan)}" + (f"  (ej.: {[f'{d:%Y-%m-%d}' for d in faltan[:5]]})" if len(faltan) else ""))
    horas = df.groupby(["sistema", "area", "fecha"]).size()
    raros = horas[horas != 24]
    print(f"Días-área con número de horas distinto de 24: {len(raros)}")
    if len(raros):
        print(raros.head(5).to_string())
    print(f"Valores vacíos o no numéricos en demanda_mwh: {int(df['demanda_mwh'].isna().sum())}")
    print(f"Mínimo y máximo de demanda_mwh: {df['demanda_mwh'].min():,.0f} / {df['demanda_mwh'].max():,.0f}")


if __name__ == "__main__":
    main()
