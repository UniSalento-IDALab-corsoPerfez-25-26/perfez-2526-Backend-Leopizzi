#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Riscarica l'anagrafica completa delle stazioni ARPA Puglia e sovrascrive la
copia locale usata da api/comune/distretti_salento.py.

La prima copia era stata fornita a mano da Matteo il 27/09/2026; da quando è
stato trovato l'host old.arpa.puglia.it (v. api/aria/arpa_puglia.py) la si
può riscaricare direttamente dalla fonte.

Input:
  ARPA Puglia, old.arpa.puglia.it/ARPA_ARIA/centraline.jsp (GeoJSON, tutta la
  Puglia, con le foto delle centraline in base64: alcuni MB)

Output:
  data/dataset/aria/arpa_puglia/stazioni_di_monitoraggio.json

`centraline.jsp` non elenca le centraline private non regolatorie (es. le 6
VERSALIS del petrolchimico di Brindisi, id_station 114-119, aggiunte a mano
il 01/10/2026 — decisione di Matteo: trattarle come tutte le altre stazioni):
le stazioni presenti nel file locale ma assenti dalla risposta fresca vengono
quindi mantenute, non cancellate (v. `_preservate`).

Dopo averlo eseguito, rilanciare scripts/aria/copertura_distretti_arpa.py per
aggiornare la tabella stazioni -> distretti.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # radice del repo, per il package api
from api.aria.arpa_puglia import ArpaPugliaError, get_stazioni  # noqa: E402

RADICE = Path(__file__).resolve().parents[2]
FILE_OUTPUT = RADICE / "data" / "dataset" / "aria" / "arpa_puglia" / "stazioni_di_monitoraggio.json"


def _id_stazioni(geojson):
    return {f["properties"]["id_station"] for f in geojson["features"]}


def main():
    try:
        nuovo = get_stazioni()
    except ArpaPugliaError as exc:
        print(f"ERRORE nel contattare ARPA Puglia: {exc}", file=sys.stderr)
        return 1

    if not nuovo.get("features"):
        print("ATTENZIONE: risposta senza stazioni, file locale NON sovrascritto.", file=sys.stderr)
        return 1

    precedenti_geojson = None
    precedenti = set()
    if FILE_OUTPUT.exists():
        with open(FILE_OUTPUT, encoding="utf-8") as f:
            precedenti_geojson = json.load(f)
        precedenti = _id_stazioni(precedenti_geojson)

    attuali = _id_stazioni(nuovo)
    # Stazioni private non elencate da centraline.jsp (es. VERSALIS, aggiunte a
    # mano): si mantengono dal file precedente invece di cancellarle.
    _preservate = (
        [f for f in precedenti_geojson["features"] if f["properties"]["id_station"] not in attuali]
        if precedenti_geojson else []
    )
    nuovo["features"] = nuovo["features"] + _preservate

    with open(FILE_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(nuovo, f, ensure_ascii=False)

    finali = _id_stazioni(nuovo)
    print(f"Scritto: {FILE_OUTPUT}")
    print(f"Stazioni: {len(finali)} (prima: {len(precedenti)})")
    if precedenti:
        aggiunte = sorted(attuali - precedenti, key=lambda x: (len(x), x))
        print(f"  aggiunte: {aggiunte or 'nessuna'}")
        print(f"  mantenute dal file precedente (non in centraline.jsp): "
              f"{sorted((f['properties']['id_station'] for f in _preservate), key=lambda x: (len(x), x)) or 'nessuna'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
