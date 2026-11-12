#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Decessi comunali giornalieri ISTAT per i 145 comuni del Salento (146 fino al 14/10/2026,
prima che Presicce e Acquarica del Capo fossero unificati in Presicce-Acquarica, 075098).

Trova il rilascio più recente sulla pagina ISTAT, scarica lo ZIP nazionale (~50 MB) in
data/raw/salute/istat/ se non è già in cache, e scrive la serie giornaliera per comune
(totale di sesso e classi di età) in data/interim/salute/istat/decessi_giornalieri_salento.csv
(gitignored). Colonne: id_comune, data, decessi, stato (VALORE/NULL/NO_DATA), nota.
Client e regole sugli stati: api/salute/istat.py; scheda: data/dataset/salute/istat/ISTAT.md.

Uso (dalla radice del repo):
  uv run scripts/salute/scarica_decessi_istat.py            # rilascio corrente, usa la cache
  uv run scripts/salute/scarica_decessi_istat.py --forza    # riscarica lo ZIP
  uv run scripts/salute/scarica_decessi_istat.py --zip PERCORSO   # usa uno ZIP già scaricato (nessuna rete)
"""

import argparse
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))

from api.salute import istat  # noqa: E402

TERRITORIO = RADICE / "data" / "territorio" / "anagrafica" / "territorio.json"
USCITA = RADICE / "data" / "interim" / "salute" / "istat" / "decessi_giornalieri_salento.csv"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--forza", action="store_true", help="riscarica lo ZIP anche se è in cache")
    ap.add_argument("--zip", type=Path, help="usa questo ZIP invece di cercare il rilascio sulla pagina ISTAT")
    args = ap.parse_args()

    ids = [c["id_comune"] for c in json.loads(TERRITORIO.read_text(encoding="utf-8"))["tabelle"]["comuni"]]
    try:
        percorso = args.zip or istat.scarica_zip(forza=args.forza)
        print(f"ZIP: {percorso}")
        df = istat.leggi_decessi(percorso, ids)
    except istat.IstatError as exc:
        sys.exit(f"Errore ISTAT: {exc}")

    USCITA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(USCITA, index=False, encoding="utf-8")
    fine = df.attrs["fine_copertura"]
    print(f"{len(df)} righe, {df['id_comune'].nunique()} comuni, "
          f"{df['data'].min()} -> {df['data'].max()} (copertura fino al {fine}) -> {USCITA.relative_to(RADICE)}")
    print("stati:", df["stato"].value_counts().to_dict())
    if df.attrs["comuni_senza_righe"]:
        print("comuni senza alcun decesso in tutto il file (tutti zeri):", df.attrs["comuni_senza_righe"])


if __name__ == "__main__":
    main()
