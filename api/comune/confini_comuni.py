#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Geometria dei comuni del Salento (condivisa aria/salute): centroidi e
assegnazione di un punto (es. una stazione di misura) al comune.

Fonte: data/territorio/confini/comuni_salento.geojson (v.
scripts/territorio/estrai_confini_comuni.py). I confini sono semplificati: vanno
bene per assegnare un punto a un comune, non per misure di precisione.

Assegnazione di un punto (`comune_da_coordinate`):
  1. dentro il confine di un comune → quel comune (distanza 0);
  2. fuori da tutti i confini → il comune con il confine più vicino, ma solo
     entro SOGLIA_COMUNE_VICINO_KM: oltre, il punto non è nel Salento e il comune
     resta None (non si "spinge" a intuito una stazione di Monopoli a Fasano).
"""

import json
import math
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
FILE_CONFINI = RADICE / "data" / "territorio" / "confini" / "comuni_salento.geojson"

SOGLIA_COMUNE_VICINO_KM = 5.0
KM_PER_GRADO_LAT = 111.32


def carica_confini(_cache={}):
    """{nome_confine: multipoligono}, dove il multipoligono è una lista di poligoni
    e ogni poligono una lista di anelli [(lon, lat), ...] (il primo è l'esterno,
    gli altri sono buchi)."""
    if not _cache:
        with open(FILE_CONFINI, encoding="utf-8") as f:
            for feat in json.load(f)["features"]:
                geom = feat["geometry"]
                poligoni = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
                _cache[feat["properties"]["nome"]] = poligoni
    return _cache


def _area_e_centroide(anello):
    """Area con segno e centroide (formula del poligono, piano lon/lat: a questa
    scala l'errore rispetto a un calcolo sferico è trascurabile)."""
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(anello, anello[1:] + anello[:1]):
        t = x0 * y1 - x1 * y0
        a += t
        cx += (x0 + x1) * t
        cy += (y0 + y1) * t
    a /= 2
    return a, (cx / (6 * a), cy / (6 * a)) if a else (0.0, (anello[0][0], anello[0][1]))


def centroide(poligoni):
    """(lat, lon) del centroide di un multipoligono, con i buchi sottratti."""
    area_tot = sx = sy = 0.0
    for poligono in poligoni:
        for i, anello in enumerate(poligono):
            a, (cx, cy) = _area_e_centroide([tuple(p) for p in anello])
            a = abs(a) * (1 if i == 0 else -1)
            area_tot += a
            sx += a * cx
            sy += a * cy
    return sy / area_tot, sx / area_tot


def _dentro_anello(lon, lat, anello):
    dentro = False
    for (x0, y0), (x1, y1) in zip(anello, anello[1:] + anello[:1]):
        if (y0 > lat) != (y1 > lat) and lon < (x1 - x0) * (lat - y0) / (y1 - y0) + x0:
            dentro = not dentro
    return dentro


def contiene(poligoni, lat, lon):
    for poligono in poligoni:
        anelli = [[tuple(p) for p in a] for a in poligono]
        if _dentro_anello(lon, lat, anelli[0]) and not any(_dentro_anello(lon, lat, b) for b in anelli[1:]):
            return True
    return False


def _distanza_km_da_confine(poligoni, lat, lon):
    """Distanza minima (km) dal punto ai segmenti dei contorni, in proiezione
    equirettangolare centrata sul punto."""
    kx = KM_PER_GRADO_LAT * math.cos(math.radians(lat))
    ky = KM_PER_GRADO_LAT
    migliore = float("inf")
    for poligono in poligoni:
        for anello in poligono:
            punti = [((x - lon) * kx, (y - lat) * ky) for x, y in anello]
            for (x0, y0), (x1, y1) in zip(punti, punti[1:] + punti[:1]):
                dx, dy = x1 - x0, y1 - y0
                lung2 = dx * dx + dy * dy
                t = 0.0 if lung2 == 0 else max(0.0, min(1.0, -(x0 * dx + y0 * dy) / lung2))
                migliore = min(migliore, math.hypot(x0 + t * dx, y0 + t * dy))
    return migliore


def confine_da_coordinate(lat, lon):
    """(nome_confine, distanza_km, dentro): confine che contiene il punto (distanza 0)
    o quello più vicino; (None, distanza_km, False) se il più vicino supera la soglia."""
    confini = carica_confini()
    for nome, poligoni in confini.items():
        if contiene(poligoni, lat, lon):
            return nome, 0.0, True
    distanze = {nome: _distanza_km_da_confine(p, lat, lon) for nome, p in confini.items()}
    nome = min(distanze, key=distanze.get)
    if distanze[nome] > SOGLIA_COMUNE_VICINO_KM:
        return None, round(distanze[nome], 2), False
    return nome, round(distanze[nome], 2), False
