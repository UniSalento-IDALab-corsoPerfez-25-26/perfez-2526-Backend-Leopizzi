#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Riempie la cache locale di Copernicus CAMS (data/raw/aria/copernicus_cams/, gitignored) per un
periodo, un mese e un inquinante alla volta, **riprendibile**: i mesi già in cache si saltano, quindi
si può interrompere e rilanciare. Ogni richiesta all'ADS dura ~1-2 minuti (la rianalisi scarica tutta
l'Europa e si ritaglia sul Salento): per questo si scarica il periodo che serve al confronto, a blocchi,
invece di tutto 2016 → oggi. `genera_dataset_aria.py` poi legge dalla cache senza richiamare l'ADS.

    uv run --env-file .env scripts/aria/scarica_cams.py --da 2024-01 --a 2024-12
    uv run --env-file .env scripts/aria/scarica_cams.py --da 2024-01 --a 2024-12 --inquinanti CO NO2 --paralleli 2

Le licenze dei due dataset ADS vanno accettate a mano (v. data/dataset/aria/copernicus_cams/Copernicus_CAMS.md).
"""

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from api.aria.copernicus_cams import VARIABILI, CopernicusError  # noqa: E402
from api.aria.fonti.cams import FonteCAMS  # noqa: E402

RIFERIMENTO = ["CO", "NO2", "O3", "PM2.5", "SO2"]  # docs/Regole_dei_dati.md


def mese(testo):
    anno, m = testo.split("-")
    return int(anno), int(m)


def elenco_mesi(da, a):
    (ya, ma), (yb, mb) = da, a
    while (ya, ma) <= (yb, mb):
        yield ya, ma
        ya, ma = (ya + 1, 1) if ma == 12 else (ya, ma + 1)


def scarica(compito):
    sigla, anno, m = compito
    inizio = time.time()
    try:
        _, prodotto = FonteCAMS._ore_del_mese(sigla, anno, m, date.today().year, {"prodotti_usati": {}})
        return compito, f"ok ({prodotto}, {time.time() - inizio:.0f} s)"
    except CopernicusError as exc:
        return compito, f"ERRORE: {exc}"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Scarica in cache locale i dati CAMS per un periodo.")
    p.add_argument("--da", required=True, type=mese, help="primo mese, AAAA-MM")
    p.add_argument("--a", required=True, type=mese, help="ultimo mese, AAAA-MM")
    p.add_argument("--inquinanti", nargs="+", default=RIFERIMENTO, choices=sorted(VARIABILI))
    p.add_argument("--paralleli", type=int, default=1, help="richieste contemporanee all'ADS (default 1)")
    args = p.parse_args()

    compiti = [(s, y, m) for y, m in elenco_mesi(args.da, args.a) for s in args.inquinanti]
    print(f"{len(compiti)} richieste (mese × inquinante); quelle già in cache si saltano.", flush=True)
    errori = 0
    with ThreadPoolExecutor(args.paralleli) as pool:
        for (sigla, y, m), esito in pool.map(scarica, compiti):
            print(f"{y}-{m:02d} {sigla:5s} {esito}", flush=True)
            errori += esito.startswith("ERRORE")
    print(f"Finito: {len(compiti) - errori} ok, {errori} errori.")
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
