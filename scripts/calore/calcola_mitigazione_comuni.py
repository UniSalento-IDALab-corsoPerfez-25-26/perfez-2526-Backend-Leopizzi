#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calcola per ogni comune del Salento i due fattori di mitigazione dell'UHRI (copertura arborea e suolo
impermeabile, CLMS High Resolution Layer 2018 a 10 m) e li scrive in
data/dataset/calore/clms/mitigazione_comuni.json, **dato autorevole** da cui
scripts/territorio/costruisci_anagrafica_territorio.py riporta le colonne in territorio.json.

    uv run scripts/calore/calcola_mitigazione_comuni.py
    uv run scripts/calore/calcola_mitigazione_comuni.py --comuni Lecce Gallipoli --paralleli 2

Sorgente: i raster scaricati a mano in data/raw/calore/clms/locale/ (se presenti) hanno la precedenza sul servizio EEA.
Riprendibile: i ritagli EEA scaricati restano in data/raw/calore/clms/ (gitignored) e non si richiedono due volte.
Nessuna chiave. Un errore su un raster rende `NULL` quel comune e prodotto, non interrompe il calcolo.
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from api.calore.clms import PRODOTTI, media_zonale, sorgente  # noqa: E402

RADICE = Path(__file__).resolve().parents[2]
FILE_TERRITORIO = RADICE / "data" / "territorio" / "anagrafica" / "territorio.json"
FILE_OUTPUT = RADICE / "data" / "dataset" / "calore" / "clms" / "mitigazione_comuni.json"
LICENZA = ("Copernicus Land Monitoring Service: accesso pieno, libero e gratuito (Reg. delegato UE 1159/2013); "
           "obbligo di citare la fonte e di dichiarare le modifiche.")


def comuni_territorio():
    with open(FILE_TERRITORIO, encoding="utf-8") as f:
        return json.load(f)["tabelle"]["comuni"]


def calcola(comune):
    inizio = time.time()
    riga = {p: media_zonale(p, comune["nome_confine"]) for p in PRODOTTI}
    return comune, riga, time.time() - inizio


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--comuni", nargs="*", help="solo questi comuni (denominazione); default: tutti")
    ap.add_argument("--paralleli", type=int, default=4)
    args = ap.parse_args()

    comuni = comuni_territorio()
    if args.comuni:
        richiesti = {c.lower() for c in args.comuni}
        comuni = [c for c in comuni if c["denominazione"].lower() in richiesti]
        if not comuni:
            print("Nessun comune corrisponde.", file=sys.stderr)
            return 1

    risultati = {}
    with ThreadPoolExecutor(max_workers=args.paralleli) as pool:
        for i, (comune, riga, secondi) in enumerate(pool.map(calcola, comuni), 1):
            risultati[comune["id_comune"]] = {"denominazione": comune["denominazione"], **riga}
            sintesi = "  ".join(f"{p}={riga[p]['valore']}" for p in PRODOTTI)
            print(f"[{i}/{len(comuni)}] {comune['denominazione']}: {sintesi} ({secondi:.0f} s)")

    # con --comuni si fonde nel file esistente invece di sovrascriverlo
    if args.comuni and FILE_OUTPUT.exists():
        with open(FILE_OUTPUT, encoding="utf-8") as f:
            esistenti = json.load(f)["comuni"]
        esistenti.update(risultati)
        risultati = esistenti

    FILE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(FILE_OUTPUT, "w", encoding="utf-8") as f:
        json.dump({
            "descrizione": "Fattori di mitigazione dell'UHRI per comune: media % sui pixel da 10 m del confine comunale. "
                           "Generato da scripts/calore/calcola_mitigazione_comuni.py.",
            "generato_il": date.today().isoformat(),
            "licenza": LICENZA,
            "prodotti": {p: {**PRODOTTI[p], "usato": sorgente(p)} for p in PRODOTTI},
            "comuni": dict(sorted(risultati.items())),
        }, f, ensure_ascii=False, indent=1)

    nulli = [(r["denominazione"], p) for r in risultati.values() for p in PRODOTTI if r[p]["stato"] != "VALORE"]
    print(f"{len(risultati)} comuni → {FILE_OUTPUT.relative_to(RADICE)}; celle NULL: {len(nulli)}")
    for nome, p in nulli:
        print(f"  NULL {nome} / {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
