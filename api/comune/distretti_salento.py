#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper condivisi (lato "territorio", comuni ad aria e salute) per associare
comuni e stazioni ARPA Puglia ai distretti socio-sanitari del Salento. Usato
sia dagli script di report (scripts/aria/copertura_distretti_arpa.py) sia
dalle funzioni "endpoint" di api/aria/arpa_puglia.py, per non duplicare la
logica di normalizzazione dei nomi comune (già usata in
scripts/territorio/costruisci_distretti_salento.py). I futuri dataset salute
useranno le stesse funzioni per ricondurre i dati comunali ai distretti.

Fonti:
  data/territorio/lista_presidi/Distretti_Salento.json
    Comuni per distretto (v. scripts/territorio/costruisci_distretti_salento.py).
  data/dataset/aria/arpa_puglia/stazioni_di_monitoraggio.json
    Anagrafica stazioni ARPA (GeoJSON; rigenerabile con
    api.aria.arpa_puglia.get_stazioni()).
"""

import json
import unicodedata
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
FILE_STAZIONI = RADICE / "data" / "dataset" / "aria" / "arpa_puglia" / "stazioni_di_monitoraggio.json"
FILE_DISTRETTI = RADICE / "data" / "territorio" / "lista_presidi" / "Distretti_Salento.json"

PROVINCE_SALENTO = {"Lecce", "Brindisi", "Taranto", "ILVA"}  # ILVA = rete privata ADI a Taranto


def chiave(nome):
    """Maiuscolo, senza accenti, senza punteggiatura, spazi normalizzati —
    stessa normalizzazione di scripts/territorio/costruisci_distretti_salento.py, per
    confrontare nomi di comune scritti in modo diverso ("Nardò" / "NARDO'")."""
    n = unicodedata.normalize("NFD", nome)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    n = n.upper()
    n = "".join(c if c.isalnum() or c.isspace() else " " for c in n)
    return " ".join(n.split())


def carica_distretti():
    """Elenco distretti del Salento, con i comuni afferenti (v. Distretti_Salento.json)."""
    with open(FILE_DISTRETTI, encoding="utf-8") as f:
        return json.load(f)["distretti"]


def _mappa_comune_distretto(distretti):
    mappa = {}
    for d in distretti:
        for comune in d["comuni"]:
            mappa[chiave(comune)] = d["id_distretto"]
    return mappa


def distretto_del_comune(comune, _cache={}):
    """id_distretto a cui appartiene il comune (nomi confrontati con
    chiave()), o None se il comune non è in nessun distretto del Salento."""
    if not _cache:
        _cache.update(_mappa_comune_distretto(carica_distretti()))
    return _cache.get(chiave(comune or ""))


def carica_stazioni_salento():
    """Tutte le stazioni ARPA nelle tre province del Salento (incluse le 6
    private ex-ILVA/ADI di Taranto), con il distretto assegnato in base al
    comune (id_distretto = None se il comune non è in nessun distretto)."""
    with open(FILE_STAZIONI, encoding="utf-8") as f:
        dati = json.load(f)

    mappa_comuni = _mappa_comune_distretto(carica_distretti())

    stazioni = []
    for feat in dati["features"]:
        p = feat["properties"]
        if p.get("provincia") not in PROVINCE_SALENTO:
            continue
        lon, lat = feat["geometry"]["coordinates"]
        stazioni.append(
            {
                "id_station": p["id_station"],
                "denominazione": p["denominazione"],
                "comune": p["comune"],
                "provincia": p["provincia"],
                "rete": p["rete"],
                "interesse_rete": p["interesse_rete"],
                "lon": lon,
                "lat": lat,
                "id_distretto": mappa_comuni.get(chiave(p["comune"])),
            }
        )
    return stazioni


def stazioni_per_distretto(id_distretti=None):
    """{id_distretto: [stazioni]} per tutti i distretti del Salento, o solo
    per quelli in `id_distretti` se specificato.

    Solleva ValueError se `id_distretti` contiene un id sconosciuto, invece
    di ignorarlo in silenzio."""
    validi = {d["id_distretto"] for d in carica_distretti()}
    if id_distretti is not None:
        richiesti = set(id_distretti)
        sconosciuti = richiesti - validi
        if sconosciuti:
            raise ValueError(f"Distretti sconosciuti: {sorted(sconosciuti)}")
        validi = richiesti

    risultato = {d: [] for d in validi}
    for s in carica_stazioni_salento():
        if s["id_distretto"] in risultato:
            risultato[s["id_distretto"]].append(s)
    return risultato
