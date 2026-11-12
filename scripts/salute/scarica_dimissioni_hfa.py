#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dimissioni ospedaliere per gruppo di patologia, provincia (LE, BR, TA) × anno, da ISTAT Health for All.

Scarica lo ZIP HFA (~26 MB) in data/raw/salute/istat_hfa/ se non è in cache e scrive
data/interim/salute/istat_hfa/dimissioni_province.csv (gitignored): provincia, anno, gruppo,
dimissioni (somma M+F), tasso (per 10.000 ab.), stato (VALORE/NULL/NO_DATA), nota.
Client e formato: api/salute/istat_hfa.py; scheda: data/dataset/salute/istat/ISTAT.md canale C.
Solo informativo: grana provinciale e annuale, fuori dalle correlazioni.

Uso (dalla radice del repo):
  uv run scripts/salute/scarica_dimissioni_hfa.py            # usa la cache
  uv run scripts/salute/scarica_dimissioni_hfa.py --forza    # riscarica lo ZIP
  uv run scripts/salute/scarica_dimissioni_hfa.py --zip PERCORSO
"""

import argparse
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))

from api.salute import istat_hfa  # noqa: E402

USCITA = RADICE / "data" / "interim" / "salute" / "istat_hfa" / "dimissioni_province.csv"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--forza", action="store_true", help="riscarica lo ZIP anche se è in cache")
    ap.add_argument("--zip", type=Path, help="usa questo ZIP invece di cercarlo sulla pagina ISTAT")
    args = ap.parse_args()
    try:
        percorso = args.zip or istat_hfa.scarica_zip(forza=args.forza)
        print(f"ZIP: {percorso}")
        df = istat_hfa.leggi_dimissioni(percorso)
    except istat_hfa.HfaError as exc:
        sys.exit(f"Errore HFA: {exc}")
    USCITA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(USCITA, index=False, encoding="utf-8")
    con = df[df["stato"] == "VALORE"]
    print(f"{len(df)} righe, anni {con['anno'].min()}-{con['anno'].max()} con valore -> {USCITA.relative_to(RADICE)}")
    print("stati:", df["stato"].value_counts().to_dict())


if __name__ == "__main__":
    main()
