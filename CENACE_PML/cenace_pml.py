#!/usr/bin/env python3
"""Descarga PML del MDA (mercado del día en adelanto) desde el SW-PML de CENACE.

Uso:
  python cenace_pml.py probe                       # 1 llamada, imprime la estructura del JSON
  python cenace_pml.py download                    # baja todo en bloques de 7 días -> data/raw/
  python cenace_pml.py build                       # une los JSON crudos -> data/pml_mda.csv

Los JSON crudos se guardan tal cual; si ya existen, no se vuelven a bajar
(puedes interrumpir y reanudar sin perder nada).

Formato de la URL (del ejemplo oficial del SW-PML):
  https://ws01.cenace.gob.mx:8082/SWPML/SIM/{SISTEMA}/{PROCESO}/{NODOS}/{AAAA}/{MM}/{DD}/{AAAA}/{MM}/{DD}/JSON
"""
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

# ----------------------------- CONFIGURACIÓN ------------------------------
BASE = "https://ws01.cenace.gob.mx:8082/SWPML/SIM"
SISTEMA = "SIN"
PROCESO = "MDA"          # mercado del día en adelanto
# Claves tal como vienen en el catálogo de NodosP (sin guion tras los 2 primeros dígitos
# no aplica: la clave del catálogo ya es la que va en la URL, p. ej. 01OLI-230).
NODOS = [
    "01OLI-230",  # Olivar, CDMX sur
    "06HUI-230",  # Huinala, Monterrey
    "03SMR-230",  # San Martín, Guadalajara
    "08IZI-115",  # Itzimná, Mérida
    "05CHU-230",  # Chuviscar, Chihuahua
    "02IPO-230",  # Ixtepec Potencia, Istmo (zona eólica)
]
FECHA_INICIO = date(2022, 1, 1)
FECHA_FIN = date(2026, 10, 31)
DIAS_POR_LLAMADA = 7     # límite que indicaste
NODOS_POR_LLAMADA = 1    # sube a varios (separados por coma) solo si confirmas que el servicio lo permite
PAUSA_SEG = 0.5
REINTENTOS = 4
RAW = Path("data/raw")
SALIDA = Path("data/pml_mda.csv")
# --------------------------------------------------------------------------


def bloques(inicio, fin, n):
    d = inicio
    while d <= fin:
        h = min(d + timedelta(days=n - 1), fin)
        yield d, h
        d = h + timedelta(days=1)


def grupos(lista, n):
    for i in range(0, len(lista), n):
        yield lista[i:i + n]


def url(nodos, d1, d2):
    return (f"{BASE}/{SISTEMA}/{PROCESO}/{','.join(nodos)}/"
            f"{d1:%Y/%m/%d}/{d2:%Y/%m/%d}/JSON")


def archivo(nodos, d1, d2):
    return RAW / f"{'+'.join(nodos)}_{d1:%Y%m%d}_{d2:%Y%m%d}.json"


def pedir(u):
    ultimo = None
    for i in range(REINTENTOS):
        try:
            r = requests.get(u, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # red, HTTP o JSON inválido
            ultimo = e
            time.sleep(2 ** i)
    raise RuntimeError(f"Falló {u}: {ultimo}")


def probe():
    d1 = FECHA_INICIO
    d2 = d1 + timedelta(days=DIAS_POR_LLAMADA - 1)
    u = url(NODOS[:1], d1, d2)
    print("GET", u)
    datos = pedir(u)
    print(json.dumps(datos, indent=2, ensure_ascii=False)[:3000])


def download():
    RAW.mkdir(parents=True, exist_ok=True)
    tareas = [(g, d1, d2)
              for g in grupos(NODOS, NODOS_POR_LLAMADA)
              for d1, d2 in bloques(FECHA_INICIO, FECHA_FIN, DIAS_POR_LLAMADA)]
    fallidas = []
    for k, (g, d1, d2) in enumerate(tareas, 1):
        f = archivo(g, d1, d2)
        if f.exists():
            continue
        try:
            datos = pedir(url(g, d1, d2))
            f.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            fallidas.append((g, d1, d2, str(e)))
            print("FALLÓ", g, d1, d2)
        if k % 50 == 0:
            print(f"{k}/{len(tareas)}")
        time.sleep(PAUSA_SEG)
    if fallidas:
        Path("data").mkdir(exist_ok=True)
        Path("data/fallidas.json").write_text(
            json.dumps([[g, str(a), str(b), e] for g, a, b, e in fallidas], ensure_ascii=False, indent=1))
        print(f"{len(fallidas)} bloques fallaron; vuelve a correr 'download' para reintentarlos.")


def _filas(obj, nodo=None):
    """Recorre el JSON y devuelve diccionarios que tengan 'hora' (una fila = una hora).
    Hereda la clave del nodo de los diccionarios padre, sea cual sea su nombre exacto."""
    if isinstance(obj, dict):
        nodo = next((obj[k] for k in obj
                     if k.lower() in ("clv_nodo", "nodo", "clave", "clave_nodo", "zona") and isinstance(obj[k], str)),
                    nodo)
        if "hora" in {k.lower() for k in obj}:
            yield {**obj, "_nodo": nodo}
        else:
            for v in obj.values():
                yield from _filas(v, nodo)
    elif isinstance(obj, list):
        for v in obj:
            yield from _filas(v, nodo)


def build():
    filas = []
    for f in sorted(RAW.glob("*.json")):
        filas.extend(_filas(json.loads(f.read_text(encoding="utf-8"))))
    if not filas:
        sys.exit("No se encontraron filas con 'hora'. Corre 'probe' y ajusta _filas() a la estructura real.")
    df = pd.DataFrame(filas)
    df.columns = [c.lower() for c in df.columns]
    # columnas numéricas de precio, vengan como texto o número
    for c in df.columns:
        if c.startswith("pml") or c == "hora":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # Si el JSON trae una columna de fecha, intenta parsearla; la hora de CENACE va de 1 a 24.
    col_fecha = next((c for c in ("dia", "fecha", "fecha_ano") if c in df.columns), None)
    if col_fecha:
        df["fecha"] = pd.to_datetime(df[col_fecha], errors="coerce")
        df["timestamp"] = df["fecha"] + pd.to_timedelta(df["hora"] - 1, unit="h")
    df = df.drop_duplicates()
    orden = [c for c in ("_nodo", "timestamp") if c in df.columns]
    df = df.sort_values(orden).reset_index(drop=True)
    SALIDA.parent.mkdir(exist_ok=True)
    df.to_csv(SALIDA, index=False)
    print(f"{len(df):,} filas -> {SALIDA}")
    if "timestamp" in df.columns and "_nodo" in df.columns:
        esperado = pd.date_range(df.timestamp.min(), df.timestamp.max(), freq="h")
        for n, g in df.groupby("_nodo"):
            print(f"{n}: {len(g):,} filas, faltan {len(esperado.difference(g.timestamp)):,} horas")


if __name__ == "__main__":
    {"probe": probe, "download": download, "build": build}.get(
        sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
