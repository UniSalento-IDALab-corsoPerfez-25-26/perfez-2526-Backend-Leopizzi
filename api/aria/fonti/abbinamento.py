#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Abbinamento delle stazioni di una fonte alle stazioni ARPA, per coordinate
(usato da OpenAQ ed EEA, che non danno un comune affidabile):
  1. stazione ARPA entro 250 m → stessa chiave della stazione ARPA;
  2. stazione ARPA entro 1 km il cui comune compare nel nome della stazione
     → stessa chiave (es. "brindisi SISRI" a 557 m da "Brindisi - SISRI");
  3. altrimenti chiave "<fonte>-<id>", distretto dal comune se questo compare
     nel nome (es. "Surbo ENEL");
  4. altrimenti non assegnabile (id_distretto None → segnalata nel report).
Una stazione abbinata a una stazione ARPA fuori dal Salento (es. Monopoli, BA)
resta con id_distretto None: il generatore la segnala come zona non elencata.
"""

import json
import math

from api.comune.distretti_salento import FILE_STAZIONI, carica_distretti, chiave, distretto_del_comune

DISTANZA_ABBINAMENTO = 250  # m
DISTANZA_ABBINAMENTO_COMUNE = 1000  # m, se il comune ARPA compare nel nome della stazione


def distanza_m(lat1, lon1, lat2, lon2):
    la1, lo1, la2, lo2 = map(math.radians, (lat1, lon1, lat2, lon2))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


def _contiene_parola(testo_chiave, parola_chiave):
    return bool(parola_chiave) and f" {parola_chiave} " in f" {testo_chiave} "


def anagrafica_arpa():
    """Stazioni ARPA di tutta la Puglia (id, denominazione, comune, provincia, lat, lon)."""
    with open(FILE_STAZIONI, encoding="utf-8") as f:
        features = json.load(f)["features"]
    return [
        {
            "id": f["properties"]["id_station"], "denominazione": f["properties"]["denominazione"].strip(),
            "comune": f["properties"]["comune"], "provincia": f["properties"]["provincia"],
            "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1],
        }
        for f in features
    ]


def comuni_salento():
    """Comuni del Salento, dal nome più lungo (per cercarli nel nome di una stazione)."""
    return sorted({c for d in carica_distretti() for c in d["comuni"]}, key=len, reverse=True)


def abbina_ad_arpa(fonte, id_fonte, denominazione, testo, lat, lon, anagrafica, comuni):
    """Riga stazione (colonne di COLONNE_STAZIONI, senza attiva_da/attiva_a) per la
    stazione `id_fonte` della `fonte`. `testo`: nome ed eventuale località della
    stazione, dove cercare il comune."""
    testo = chiave(testo or "")
    vicina = min(anagrafica, key=lambda s: distanza_m(lat, lon, s["lat"], s["lon"]))
    distanza = round(distanza_m(lat, lon, vicina["lat"], vicina["lon"]))
    base = {"fonte": fonte, "id_fonte": str(id_fonte), "denominazione": denominazione, "lat": lat, "lon": lon}

    comune_arpa_nel_nome = _contiene_parola(testo, chiave(vicina["comune"]))
    if distanza <= DISTANZA_ABBINAMENTO or (distanza <= DISTANZA_ABBINAMENTO_COMUNE and comune_arpa_nel_nome):
        criterio = f"stazione ARPA {vicina['id']} ({vicina['denominazione']}) a {distanza} m"
        if distanza > DISTANZA_ABBINAMENTO:
            criterio += ", stesso comune nel nome"
        return dict(base, stazione=vicina["id"], comune=vicina["comune"], provincia=vicina["provincia"],
                    id_distretto=distretto_del_comune(vicina["comune"]), abbinamento=criterio)

    chiave_propria = f"{fonte}-{id_fonte}"
    comune = next((c for c in comuni if _contiene_parola(testo, chiave(c))), None)
    if comune:
        return dict(base, stazione=chiave_propria, comune=comune, provincia=None,
                    id_distretto=distretto_del_comune(comune),
                    abbinamento=f"nessuna stazione ARPA entro {DISTANZA_ABBINAMENTO_COMUNE} m (la più vicina a "
                                f"{distanza} m); distretto dal comune nel nome ({comune})")
    return dict(base, stazione=chiave_propria, comune=None, provincia=None, id_distretto=None,
                abbinamento=f"non assegnabile: stazione ARPA più vicina a {distanza} m, nessun comune nel nome")
