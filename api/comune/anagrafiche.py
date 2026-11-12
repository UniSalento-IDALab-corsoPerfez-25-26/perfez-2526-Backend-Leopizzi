#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anagrafiche relazionali (condivise aria/salute): file JSON che si comportano
come tabelle SQL, con chiavi primarie ed esterne (v. data/dataset/Anagrafiche_relazionali.md).

Ogni file ha la forma
    {"descrizione": ..., "schema": {tabella: {chiave_primaria, chiavi_esterne, colonne}},
     "tabelle": {tabella: [riga, ...]}}
e i nomi delle tabelle sono univoci fra tutti i file, così una chiave esterna si
scrive "tabella.colonna" anche fra file diversi.

Questo modulo carica i file, verifica l'integrità (chiavi primarie uniche, chiavi
esterne che puntano a righe esistenti) e li apre come tabelle SQLite *in memoria*
per interrogarli in SQL. Non c'è un database persistente (docs/Architettura.md): i JSON
restano la fonte, lo SQLite si ricrea a ogni apertura.
"""

import json
import sqlite3
from pathlib import Path

import pandas as pd

RADICE = Path(__file__).resolve().parents[2]
FILE_ANAGRAFICHE = {
    "territorio": RADICE / "data" / "territorio" / "anagrafica" / "territorio.json",
    "stazioni": RADICE / "data" / "dataset" / "aria" / "anagrafica" / "stazioni.json",
    "inquinanti": RADICE / "data" / "dataset" / "aria" / "anagrafica" / "inquinanti.json",
}


def leggi_anagrafica(percorso):
    """(descrizione, schema, tabelle) di un file; le tabelle sono liste di righe (dict)."""
    with open(percorso, encoding="utf-8") as f:
        dati = json.load(f)
    return dati.get("descrizione", ""), dati["schema"], dati["tabelle"]


def scrivi_anagrafica(percorso, descrizione, schema, tabelle):
    """Scrive un file di anagrafica con una riga di tabella per riga di testo
    (diff leggibili in git). Le colonne di ogni riga seguono l'ordine dello schema."""
    def j(x):
        return json.dumps(x, ensure_ascii=False)

    blocchi_schema = []
    for nome, d in schema.items():
        colonne = ",\n".join(f"    {j(c)}: {j(testo)}" for c, testo in d["colonne"].items())
        blocchi_schema.append(
            f"  {j(nome)}: {{\n"
            f'   "chiave_primaria": {j(d["chiave_primaria"])},\n'
            f'   "chiavi_esterne": {j(d["chiavi_esterne"])},\n'
            f'   "colonne": {{\n{colonne}\n   }}\n  }}'
        )
    blocchi_tabelle = []
    for nome, righe in tabelle.items():
        colonne = list(schema[nome]["colonne"])
        righe_json = ",\n".join(f"   {j({c: r.get(c) for c in colonne})}" for r in righe)
        blocchi_tabelle.append(f"  {j(nome)}: [\n{righe_json}\n  ]")
    testo = (
        "{\n"
        f' "descrizione": {j(descrizione)},\n'
        ' "schema": {\n' + ",\n".join(blocchi_schema) + "\n },\n"
        ' "tabelle": {\n' + ",\n".join(blocchi_tabelle) + "\n }\n}\n"
    )
    Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    Path(percorso).write_text(testo, encoding="utf-8")


def carica_anagrafiche(file=None):
    """(schema, tabelle): schema {tabella: definizione} e tabelle {tabella: DataFrame}
    di tutti i file di anagrafica esistenti (o solo di quelli in `file`: {nome: percorso})."""
    schema, tabelle = {}, {}
    for nome_file, percorso in (file or FILE_ANAGRAFICHE).items():
        if not Path(percorso).exists():
            continue
        _, s, t = leggi_anagrafica(percorso)
        doppie = (set(s) | set(t)) & (set(schema) | set(tabelle))
        if doppie:
            raise ValueError(f"{nome_file}: tabelle già definite in un altro file: {sorted(doppie)}")
        schema.update(s)
        for nome, righe in t.items():
            # dtype=object: i valori restano quelli del JSON (nessuna coercione di int/bool a float/NaN)
            tabelle[nome] = pd.DataFrame(righe, columns=list(s[nome]["colonne"]), dtype=object)
    return schema, tabelle


def verifica_integrita(schema, tabelle):
    """Elenco dei problemi (stringhe); vuoto se le anagrafiche sono coerenti:
    colonne come da schema, chiavi primarie uniche e non nulle, chiavi esterne
    (se non nulle) che puntano a una riga esistente."""
    problemi = []
    for nome, df in tabelle.items():
        pk = schema[nome]["chiave_primaria"]
        if df.duplicated(pk).any():
            problemi.append(f"{nome}: chiave primaria {pk} duplicata: "
                            f"{df.loc[df.duplicated(pk, keep=False), pk].drop_duplicates().values.tolist()[:5]}")
        if df[pk].isna().any().any():
            problemi.append(f"{nome}: chiave primaria {pk} con valori nulli")
        for colonna, riferimento in schema[nome]["chiavi_esterne"].items():
            tabella_rif, colonna_rif = riferimento.split(".")
            if tabella_rif not in tabelle:
                problemi.append(f"{nome}.{colonna}: la tabella {tabella_rif} non è caricata")
                continue
            valori = df[colonna].dropna()
            mancanti = sorted(set(valori) - set(tabelle[tabella_rif][colonna_rif]))
            if mancanti:
                problemi.append(f"{nome}.{colonna} → {riferimento}: valori senza riga collegata: {mancanti[:5]}")
    return problemi


def _tipo_sql(serie):
    valori = [v for v in serie if not pd.isna(v)]
    if not valori:
        return "TEXT"
    if all(isinstance(v, (bool, int)) for v in valori):
        return "INTEGER"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in valori):
        return "REAL"
    return "TEXT"


def apri_sqlite(file=None):
    """Connessione SQLite in memoria con tutte le anagrafiche come tabelle vere,
    con PRIMARY KEY e FOREIGN KEY. Solleva ValueError se l'integrità non torna."""
    schema, tabelle = carica_anagrafiche(file)
    problemi = verifica_integrita(schema, tabelle)
    if problemi:
        raise ValueError("Anagrafiche incoerenti:\n  " + "\n  ".join(problemi))
    conn = sqlite3.connect(":memory:")
    for nome, df in tabelle.items():
        definizione = schema[nome]
        colonne = [f'"{c}" {_tipo_sql(df[c])}' for c in df.columns]
        vincoli = ["PRIMARY KEY (" + ", ".join(f'"{c}"' for c in definizione["chiave_primaria"]) + ")"]
        for colonna, rif in definizione["chiavi_esterne"].items():
            t, c = rif.split(".")
            vincoli.append(f'FOREIGN KEY ("{colonna}") REFERENCES "{t}" ("{c}")')
        conn.execute(f'CREATE TABLE "{nome}" ({", ".join(colonne + vincoli)})')
    # dopo la creazione di tutte le tabelle: alcune chiavi esterne sono circolari o puntano avanti
    for nome, df in tabelle.items():
        righe = [tuple(None if pd.isna(v) else v for v in r) for r in df.itertuples(index=False, name=None)]
        conn.executemany(f'INSERT INTO "{nome}" VALUES ({", ".join("?" * len(df.columns))})', righe)
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
