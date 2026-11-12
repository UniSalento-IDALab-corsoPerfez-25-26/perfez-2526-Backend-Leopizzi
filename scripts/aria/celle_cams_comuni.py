#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scrive il mapping celle CAMS → comuni (pesi sull'area) in
data/dataset/aria/copernicus_cams/Celle_Comuni.json, per ispezionarlo senza scaricare
nulla. Usa la griglia nominale CAMS Europa (centri a xx,x5° con passo 0,1°); i pesi usati
davvero dall'adattatore sono ricalcolati dalle coordinate del file scaricato
(api/aria/fonti/cams.py), quindi questo file è solo documentazione.

    uv run scripts/aria/celle_cams_comuni.py
"""

import json
import sys
from pathlib import Path

import numpy as np

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))

from api.aria.anagrafica_aria import carica_comuni  # noqa: E402
from api.comune.celle_comuni import copertura_celle, pesi_celle  # noqa: E402

USCITA = RADICE / "data" / "dataset" / "aria" / "copernicus_cams" / "Celle_Comuni.json"


def main():
    lat = np.round(np.arange(39.65, 41.06, 0.1), 2)
    lon = np.round(np.arange(16.65, 18.66, 0.1), 2)
    pesi, copertura = pesi_celle(lat, lon), copertura_celle(lat, lon)
    comuni = {}
    for c in carica_comuni():
        celle = pesi[c["nome_confine"]]
        comuni[c["id_comune"]] = {
            "comune": c["denominazione"], "distretto": c["id_distretto"], "nome_confine": c["nome_confine"],
            "n_celle": len(celle),
            "celle": [{"lat": la, "lon": lo, "peso": round(p, 4)} for la, lo, p in sorted(celle, key=lambda x: -x[2])],
        }
    USCITA.write_text(json.dumps({
        "descrizione": "Celle CAMS 0,1° che intersecano ogni comune, con peso = quota della superficie comunale "
                       "dentro la cella (somma 1). Griglia nominale CAMS Europa, da riconfermare sul primo file reale.",
        "metodo": "media pesata sull'area (api/comune/celle_comuni.py)",
        "copertura_minima_griglia": round(min(copertura.values()), 4),
        "comuni": comuni,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    n = [v["n_celle"] for v in comuni.values()]
    print(f"{len(comuni)} comuni, celle per comune: min {min(n)}, max {max(n)}, mediana {int(np.median(n))}; "
          f"comuni in una sola cella: {sum(x == 1 for x in n)} → {USCITA.relative_to(RADICE)}")


if __name__ == "__main__":
    main()
