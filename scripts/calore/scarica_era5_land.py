#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Riempie la cache locale di ERA5-Land (data/raw/calore/era5_land/, gitignored) per un periodo, un mese e una
statistica alla volta, **riprendibile**: i mesi già in cache si saltano. Ogni richiesta al CDS è un mese
ritagliato sul Salento; l'API locale (localhost/server) legge poi dalla cache senza richiamare il CDS.

    uv run --env-file .env scripts/calore/scarica_era5_land.py --da 2024-07 --a 2024-07
    uv run --env-file .env scripts/calore/scarica_era5_land.py --da 2024-06 --a 2024-08 --statistiche massima minima
    uv run --env-file .env scripts/calore/scarica_era5_land.py --intervalli 2024-09:2024-12 2026-08:2026-10

Ogni richiesta aspetta minuti nella coda del CDS: `--paralleli N` ne tiene N attive insieme.

Condizioni d'uso del sito CDS e licenza del dataset vanno accettate a mano (v. data/dataset/calore/era5_land/ERA5_Land.md).
"""

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from api.aria.copernicus_cams import CopernicusError  # noqa: E402
from api.calore.era5_land import STATISTICHE, celle_mese, per_comune  # noqa: E402


def mese(testo):
    anno, m = testo.split("-")
    return int(anno), int(m)


def elenco_mesi(da, a):
    (ya, ma), (yb, mb) = da, a
    while (ya, ma) <= (yb, mb):
        yield ya, ma
        ya, ma = (ya + 1, 1) if ma == 12 else (ya, ma + 1)


def scarica(compito):
    stat, anno, m = compito
    inizio = time.time()
    try:
        celle = celle_mese(stat, anno, m)
        comuni = per_comune(celle, stat, anno, m)
        con_valore = int((comuni["stato"] == "VALORE").sum())
        return compito, False, (f"ok, {len(celle)} celle, {con_valore}/{len(comuni)} celle comune×giorno con valore "
                                f"({time.time() - inizio:.0f} s)")
    except CopernicusError as exc:
        return compito, True, f"ERRORE: {exc}"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Scarica in cache locale la temperatura ERA5-Land per un periodo.")
    p.add_argument("--da", type=mese, help="primo mese, AAAA-MM")
    p.add_argument("--a", type=mese, help="ultimo mese, AAAA-MM")
    p.add_argument("--intervalli", nargs="+", metavar="DA:A", help="più intervalli di mesi, es. 2024-09:2024-12 2026-08:2026-10")
    p.add_argument("--statistiche", nargs="+", default=list(STATISTICHE), choices=list(STATISTICHE))
    p.add_argument("--paralleli", type=int, default=1, help="richieste contemporanee al CDS (default 1)")
    args = p.parse_args()
    if args.intervalli:
        intervalli = [tuple(mese(x) for x in i.split(":")) for i in args.intervalli]
    elif args.da and args.a:
        intervalli = [(args.da, args.a)]
    else:
        p.error("indicare --da e --a, oppure --intervalli")
    compiti = [(stat, anno, m) for da, a in intervalli for anno, m in elenco_mesi(da, a) for stat in args.statistiche]
    errori = 0
    with ThreadPoolExecutor(max_workers=max(1, args.paralleli)) as pool:
        for futuro in as_completed([pool.submit(scarica, c) for c in compiti]):
            (stat, anno, m), fallito, esito = futuro.result()
            errori += fallito
            print(f"{stat:8} {anno}-{m:02d}: {esito}", flush=True)
    sys.exit(1 if errori else 0)


if __name__ == "__main__":
    main()
