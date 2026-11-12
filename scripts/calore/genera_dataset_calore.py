#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera il dataset calore (comune × giorno, ERA5-Land) in data/interim/calore/, **un mese per file** come
l'archivio aria: i mesi completi (tutte le statistiche in cache, nessun giorno in latenza, stesso elenco di
comuni) si saltano, gli altri si rigenerano. Legge solo la cache: riempirla con scarica_era5_land.py.

    uv run scripts/calore/genera_dataset_calore.py --da 2024-01 --a 2025-12
    uv run scripts/calore/genera_dataset_calore.py --rigenera --da 2024-07 --a 2024-07

Default: dal primo al più recente mese con una statistica in cache.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from api.calore import era5_land  # noqa: E402
from api.calore.dataset_calore import STRUTTURA, _territorio, a_json, costruisci_dataset_calore, impronta_territorio  # noqa: E402

DIR_OUTPUT = era5_land.RADICE / "data" / "interim" / "calore"
FILE_CACHE = re.compile(r"^(?:media|massima|minima)_(\d{4})-(\d{2})\.parquet$")


def mese(testo):
    anno, m = testo.split("-")
    return int(anno), int(m)


def elenco_mesi(da, a):
    (ya, ma), (yb, mb) = da, a
    while (ya, ma) <= (yb, mb):
        yield ya, ma
        ya, ma = (ya + 1, 1) if ma == 12 else (ya, ma + 1)


def mesi_in_cache():
    trovati = sorted({(int(m.group(1)), int(m.group(2))) for f in era5_land.DIR_CACHE.glob("*.parquet")
                      if (m := FILE_CACHE.match(f.name))})
    return trovati


def file_mese(anno, m):
    fine = era5_land._fine_mese(anno, m)
    return DIR_OUTPUT / f"dataset_calore_{date(anno, m, 1)}_{fine}.json"


def gia_buono(percorso, impronta):
    if not percorso.exists():
        return False
    try:
        with open(percorso, encoding="utf-8") as f:
            testata = json.load(f)
    except (OSError, ValueError):
        return False
    return (bool(testata.get("completo")) and testata["territorio"]["impronta"] == impronta
            and testata.get("struttura") == STRUTTURA)  # un file con struttura vecchia si rifà


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Genera il dataset calore mensile da ERA5-Land (solo cache).")
    p.add_argument("--da", type=mese, help="primo mese, AAAA-MM")
    p.add_argument("--a", type=mese, help="ultimo mese, AAAA-MM")
    p.add_argument("--rigenera", action="store_true", help="rifà anche i mesi già completi")
    args = p.parse_args()
    in_cache = mesi_in_cache()
    if not in_cache and not (args.da and args.a):
        p.error("nessun mese in cache: scaricare con scarica_era5_land.py o indicare --da e --a")
    da, a = args.da or in_cache[0], args.a or in_cache[-1]
    DIR_OUTPUT.mkdir(parents=True, exist_ok=True)
    impronta = impronta_territorio(_territorio()["comune"])
    fatti = saltati = incompleti = 0
    for anno, m in elenco_mesi(da, a):
        percorso = file_mese(anno, m)
        if not args.rigenera and gia_buono(percorso, impronta):
            saltati += 1
            continue
        try:
            griglia, mancanti = costruisci_dataset_calore(anno, m)
        except Exception as exc:  # mese fuori copertura o dato illeggibile: non ferma gli altri mesi
            print(f"{anno}-{m:02d}: SALTATO ({exc})")
            continue
        js = a_json(griglia, date(anno, m, 1), era5_land._fine_mese(anno, m), mancanti)
        with open(percorso, "w", encoding="utf-8") as f:
            json.dump(js, f, ensure_ascii=False)
        fatti += 1
        incompleti += not js["completo"]
        print(f"{anno}-{m:02d}: {js['riepilogo']['per_fonte_e_stato']}"
              + (f"  [incompleto: non in cache {mancanti[:4]}...]" if mancanti else ""))
    print(f"\nGenerati {fatti} mesi ({incompleti} incompleti), saltati {saltati} già completi → {DIR_OUTPUT}")


if __name__ == "__main__":
    main()
