#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Riempie la cache locale della rete meteo ARPA Puglia (data/raw/calore/arpa_meteo/, gitignored): un CSV per
stazione del Salento e per anno. Riprendibile: gli anni chiusi già in cache si saltano.

    uv run scripts/calore/scarica_arpa_meteo.py                  # tutte le stazioni, 2020 → anno corrente
    uv run scripts/calore/scarica_arpa_meteo.py --da 2024 --a 2025
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from api.calore.arpa_meteo import ANNI, ArpaMeteoError, csv_anno, giornaliero, stazioni_salento  # noqa: E402


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Scarica in cache locale la temperatura misurata da ARPA Puglia.")
    p.add_argument("--da", type=int, default=ANNI[0])
    p.add_argument("--a", type=int, default=ANNI[-1])
    args = p.parse_args()
    stazioni = stazioni_salento()
    print(f"{len(stazioni)} stazioni meteo in LE/BR/TA; senza comune: {int(stazioni['id_comune'].isna().sum())}")
    errori = 0
    for s in stazioni.itertuples():
        for anno in range(args.da, args.a + 1):
            try:
                csv_anno(s.rete, s.id_station, anno)
                g = giornaliero(s.rete, s.id_station, anno, scarica=False)
                n = g[g["statistica"] == "media"]
                print(f"{s.rete:6} {s.id_station:3} {anno}: {len(n)} giorni, {int((n['stato'] == 'VALORE').sum())} con valore", flush=True)
            except ArpaMeteoError as exc:
                errori += 1
                print(f"{s.rete:6} {s.id_station:3} {anno}: ERRORE {exc}", flush=True)
    sys.exit(1 if errori else 0)


if __name__ == "__main__":
    main()
