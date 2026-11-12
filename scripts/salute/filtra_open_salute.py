#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open Salute Puglia: tiene dai CSV scaricati a mano solo i comuni del Salento
(i 146 dell'anagrafica territorio) e li unisce in un file per misura.

Ingresso : data/raw/salute/open_puglia_salute/{incidenza,prevalenza}/<Misura>_BPCO_Comuni_<anno>.csv
Uscita   : data/interim/salute/open_salute/<misura>_BPCO_salento.csv (gitignored)

Il collegamento all'anagrafica è per nome (il file non ha il codice ISTAT): prima
con `denominazione`, poi con `nome_confine` (comuni fusi, es. Presicce-Acquarica,
il cui valore si ripete su entrambi i comuni con una nota). I comuni del file che non
corrispondono a nessun comune dell'anagrafica sono fuori Salento e si scartano; i comuni
dell'anagrafica senza riga in un anno si segnalano in uscita.

Uso (dalla radice del repo):
  uv run scripts/salute/filtra_open_salute.py
"""

import glob
import json
import re
import sys
from pathlib import Path

import pandas as pd

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))

RAW = RADICE / "data" / "raw" / "salute" / "open_puglia_salute"
OUT = RADICE / "data" / "interim" / "salute" / "open_salute"
TERRITORIO = RADICE / "data" / "territorio" / "anagrafica" / "territorio.json"

COLONNE = {
    "Area Geografica": "comune_fonte",
    "Anno": "anno",
    "Casi": "casi",
    "Popolazione": "popolazione",
    "Tasso standardizzato": "tasso_std",
    "lcl": "tasso_std_lcl",
    "ucl": "tasso_std_ucl",
    "Tasso grezzo": "tasso_grezzo",
    "lcl.1": "tasso_grezzo_lcl",
    "ucl.1": "tasso_grezzo_ucl",
    "Rischio relativo": "rr",
    "lcl.2": "rr_lcl",
    "ucl.2": "rr_ucl",
}


def chiave(nome):
    return re.sub(r"\s+", " ", nome.strip().lower())


def carica_comuni():
    tab = json.loads(TERRITORIO.read_text(encoding="utf-8"))["tabelle"]
    distretti = {d["id_distretto"]: d["id_provincia"] for d in tab["distretti"]}
    per_nome = {}
    per_confine = {}
    for c in tab["comuni"]:
        c = {**c, "id_provincia": distretti[c["id_distretto"]]}
        per_nome[chiave(c["denominazione"])] = c
        per_confine.setdefault(chiave(c["nome_confine"]), []).append(c)
    return per_nome, per_confine


def filtra(misura, per_nome, per_confine):
    righe = []
    for f in sorted(glob.glob(str(RAW / misura / "*.csv"))):
        d = pd.read_csv(f, sep=";", encoding="utf-8", dtype=str)
        mancanti = [c for c in COLONNE if c not in d.columns]
        if mancanti:
            raise SystemExit(f"{f}: colonne attese assenti: {mancanti}")
        d = d.rename(columns=COLONNE)[list(COLONNE.values())]
        for r in d.to_dict("records"):
            k = chiave(r["comune_fonte"])
            if k in per_nome:
                comuni, nota = [per_nome[k]], None
            elif k in per_confine and len(per_confine[k]) > 1:
                comuni = per_confine[k]
                nota = "comune fuso: valore unico per Presicce-Acquarica, ripetuto sui due comuni"
            else:
                continue
            for c in comuni:
                righe.append({
                    "id_provincia": c["id_provincia"], "id_distretto": c["id_distretto"],
                    "id_comune": c["id_comune"], "comune": c["denominazione"], **r, "nota": nota,
                })
    df = pd.DataFrame(righe)
    # `(*)` = cella oscurata dalla fonte -> vuoto + stato
    df["stato"] = df["casi"].map(lambda x: "NULL" if x == "(*)" else "VALORE")
    for col in COLONNE.values():
        if col not in ("comune_fonte", "anno"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["anno"] = df["anno"].astype(int)
    return df.sort_values(["anno", "id_comune"]).reset_index(drop=True)


def main():
    per_nome, per_confine = carica_comuni()
    ids_attesi = {c["id_comune"] for c in per_nome.values()}
    OUT.mkdir(parents=True, exist_ok=True)
    for misura in ("incidenza", "prevalenza"):
        df = filtra(misura, per_nome, per_confine)
        dest = OUT / f"{misura}_BPCO_salento.csv"
        df.to_csv(dest, sep=";", index=False, encoding="utf-8")
        anni = sorted(df["anno"].unique())
        print(f"{misura}: {len(df)} righe, anni {anni[0]}-{anni[-1]} ({len(anni)}), "
              f"oscurate {int((df['stato'] == 'NULL').sum())} -> {dest.relative_to(RADICE)}")
        for anno, g in df.groupby("anno"):
            assenti = ids_attesi - set(g["id_comune"])
            if assenti:
                print(f"  {anno}: {len(assenti)} comuni dell'anagrafica senza riga: {sorted(assenti)}")


if __name__ == "__main__":
    main()
