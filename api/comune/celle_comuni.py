#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Da celle di una griglia regolare (CAMS 0,1°, ERA5-Land 0,1°) ai comuni del Salento
(condiviso aria/calore). Decisione del 02/10/2026: **media pesata sull'area**, non
cella del centroide. Per ogni comune si intersecano i quadrati delle celle con il
suo confine (data/territorio/confini/comuni_salento.geojson) e il peso di ogni cella
è la quota di superficie comunale che ci cade dentro (la somma dei pesi di un comune
fa 1). Un comune piccolo dentro una sola cella ha quindi peso 1 su quella cella; uno
a cavallo di più celle ne media i valori in proporzione all'area.

Il calcolo è nel piano lon/lat: a questa scala (≈ 1° di lato) la distorsione è la
stessa per tutte le celle e non cambia le proporzioni fra loro.

Il geojson ha 145 confini per 145 comuni (un confine per comune, dal 14/10/2026: prima
Presicce e Acquarica del Capo condividevano un confine come due comuni separati). I pesi
sono comunque calcolati per `nome_confine`, per i casi in cui più comuni ne condividano uno.
"""

import json

import numpy as np
import shapely
from shapely.geometry import shape
from shapely.validation import make_valid

from api.comune.confini_comuni import FILE_CONFINI


def _confini_shapely(_cache={}):
    """{nome_confine: geometria shapely valida}."""
    if not _cache:
        with open(FILE_CONFINI, encoding="utf-8") as f:
            for feat in json.load(f)["features"]:
                _cache[feat["properties"]["nome"]] = make_valid(shape(feat["geometry"]))
    return _cache


def passo_griglia(centri):
    """Passo (gradi) di un asse di centri cella equispaziati, da array con almeno 2 valori."""
    centri = np.unique(np.round(np.asarray(centri, dtype=float), 6))
    if len(centri) < 2:
        raise ValueError("servono almeno due celle per ricavare il passo della griglia")
    passi = np.diff(centri)
    if not np.allclose(passi, passi[0], atol=1e-4):
        raise ValueError(f"griglia non regolare: passi {np.unique(np.round(passi, 4))}")
    return float(passi[0])


def pesi_celle(lat_centri, lon_centri):
    """Pesi cella → confine comunale per una griglia regolare.

    `lat_centri`, `lon_centri`: centri delle celle (gradi) lungo i due assi; il passo
    si ricava dai centri. Restituisce {nome_confine: [(lat_centro, lon_centro, peso), ...]}
    con pesi > 0 e somma 1; i confini che non intersecano nessuna cella mancano.
    Le celle contano per l'intersezione con il confine: se la griglia non copre tutto il
    comune i pesi sono comunque normalizzati su quanto è coperto (la copertura è in
    `copertura_celle`)."""
    lat_centri = np.unique(np.round(np.asarray(lat_centri, dtype=float), 6))
    lon_centri = np.unique(np.round(np.asarray(lon_centri, dtype=float), 6))
    d_lat, d_lon = passo_griglia(lat_centri) / 2, passo_griglia(lon_centri) / 2
    risultato = {}
    for nome, geom in _confini_shapely().items():
        minx, miny, maxx, maxy = geom.bounds
        lats = lat_centri[(lat_centri + d_lat >= miny) & (lat_centri - d_lat <= maxy)]
        lons = lon_centri[(lon_centri + d_lon >= minx) & (lon_centri - d_lon <= maxx)]
        celle = [(la, lo) for la in lats for lo in lons]
        if not celle:
            continue
        quadrati = shapely.box([lo - d_lon for _, lo in celle], [la - d_lat for la, _ in celle],
                               [lo + d_lon for _, lo in celle], [la + d_lat for la, _ in celle])
        aree = shapely.area(shapely.intersection(quadrati, geom))
        totale = aree.sum()
        if totale <= 0:
            continue
        risultato[nome] = [(float(la), float(lo), float(a / totale)) for (la, lo), a in zip(celle, aree) if a > 0]
    return risultato


def copertura_celle(lat_centri, lon_centri):
    """{nome_confine: quota (0-1) della superficie comunale coperta dalla griglia}."""
    lat_centri = np.unique(np.round(np.asarray(lat_centri, dtype=float), 6))
    lon_centri = np.unique(np.round(np.asarray(lon_centri, dtype=float), 6))
    d_lat, d_lon = passo_griglia(lat_centri) / 2, passo_griglia(lon_centri) / 2
    area_griglia = shapely.box(lon_centri.min() - d_lon, lat_centri.min() - d_lat,
                               lon_centri.max() + d_lon, lat_centri.max() + d_lat)
    return {nome: float(geom.intersection(area_griglia).area / geom.area)
            for nome, geom in _confini_shapely().items()}
