#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client per due canali ISTAT dei decessi (v. data/dataset/salute/istat/ISTAT.md),
entrambi senza causa di morte:

  **canale A** — decessi comunali giornalieri (comune × giorno), il dato su cui si
  costruisce il dataset salute;
  **canale D** — bilancio demografico mensile di demo.istat.it (comune × mese), che
  serve a **validare per ridondanza** il canale A: due pubblicazioni ISTAT distinte,
  due flussi diversi (schede di morte / anagrafe), quindi un controllo vero. A
  differenza del canale A ha un URL stabile e prevedibile.

Canale A. Non è un'API: ISTAT pubblica uno ZIP con un CSV nazionale
(~830 MB) a ogni rilascio, e l'URL contiene il mese del rilascio. Qui:

  1. `trova_rilascio_corrente()` legge la pagina ISTAT e pesca il link più recente
     (l'URL non va mai salvato nel codice);
  2. `scarica_zip()` lo scarica una volta in data/raw/salute/istat/ (gitignored);
  3. `leggi_decessi()` legge il CSV a blocchi, tiene i comuni richiesti, somma le 22
     classi di età e sesso (decisione del 01/10/2026: solo il totale giornaliero)
     e restituisce una tabella lunga con gli stati VALORE / NULL / NO_DATA.

Mappatura sugli stati del canale A (v. docs/Regole_dei_dati.md e ISTAT.md canale A):
  - riga assente per comune/giorno  -> VALORE = 0 (nessun decesso, non dato mancante);
  - `n.d.` (solo anno 2026)         -> NO_DATA (la fonte non copre ancora quel giorno);
  - valore non numerico/negativo    -> NULL (la fonte copre ma il valore non è usabile);
  - giorni dopo la fine del rilascio e comuni con TIPO_COMUNE = 2 nel 2026 -> NO_DATA.

Controllo a monte: lo ZIP deve contenere un CSV con le colonne attese. Nessun database.
"""

import re
import time
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

RADICE = Path(__file__).resolve().parents[2]
URL_PAGINA = "https://www.istat.it/notizia/dati-di-mortalita-cosa-produce-listat/"
DIR_CACHE = RADICE / "data" / "raw" / "salute" / "istat"
TIMEOUT = 120
ANNO_INIZIO = 2011  # primo anno del file (colonne T_11 ...)
CODIFICA = "latin-1"  # il CSV ISTAT non è UTF-8 (nomi con accenti)
# Comuni fusi (es. Presicce-Acquarica, 2019): ISTAT pubblica da sempre il solo codice del
# comune fuso (075098) e dal 14/10/2026 anche l'anagrafica territorio lo tiene come un solo
# comune (v. scripts/territorio/costruisci_anagrafica_territorio.py, FUSIONI_COMUNE): il
# codice del file e quello dell'anagrafica coincidono sempre, senza bisogno di una mappa.
INTESTAZIONI = {"User-Agent": "Mozilla/5.0 (OneHealth; ricerca universitaria)"}

# canale D — bilancio demografico mensile: URL stabile, un file per anno, CSV ';' in UTF-8
URL_BILANCIO = "https://demo.istat.it/data/d7b/D7B{anno}.csv.zip"
ANNI_BILANCIO = range(2019, 2025)  # verificati uno per uno il 01/10/2026: 2019-2024 (gli altri 404)
COLONNE_BILANCIO = {"Anno", "Mese", "Sesso", "Morti", "Codice comune",
                    "Popolazione inizio periodo", "Popolazione fine periodo"}
SESSO_TOTALE = "Totale"

COLONNE_BASE = {"COD_PROVCOM", "TIPO_COMUNE", "CL_ETA", "GE"}
MESI = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7,
        "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12}

# cartella di rilascio + file dei decessi giornalieri, es. .../giugno-2026/decessi-comunali-giornalieri-provvisori-4.zip
_RE_LINK = re.compile(r'href="(https://www\.istat\.it/storage/dati_mortalita/([a-z]+)-(\d{4})/'
                      r'[^"]*giornalieri[^"]*\.zip)"', re.IGNORECASE)


class IstatError(RuntimeError):
    """Errore nel prelievo o nella lettura dei decessi ISTAT."""


def trova_rilascio_corrente():
    """(url, "mese-anno") dello ZIP dei decessi comunali giornalieri più recente sulla pagina ISTAT."""
    try:
        risposta = requests.get(URL_PAGINA, timeout=TIMEOUT, headers=INTESTAZIONI)
    except requests.RequestException as exc:
        raise IstatError(f"Pagina ISTAT non raggiungibile: {URL_PAGINA} ({exc})") from exc
    if risposta.status_code != 200:
        raise IstatError(f"ISTAT ha risposto {risposta.status_code} a {URL_PAGINA}")
    trovati = []
    for url, mese, anno in _RE_LINK.findall(risposta.text):
        if mese.lower() in MESI:
            trovati.append(((int(anno), MESI[mese.lower()]), url, f"{mese.lower()}-{anno}"))
    if not trovati:
        raise IstatError("Nessun link ai decessi comunali giornalieri sulla pagina ISTAT: la pagina è cambiata?")
    _, url, etichetta = max(trovati)
    return url, etichetta


def scarica_zip(url=None, etichetta=None, forza=False):
    """Scarica lo ZIP (o riusa la copia in cache dello stesso rilascio) e restituisce il percorso.
    Il nome in cache include il mese del rilascio, perché il nome del file ISTAT non cambia tra i rilasci."""
    if url is None:
        url, etichetta = trova_rilascio_corrente()
    etichetta = etichetta or "rilascio"
    destinazione = DIR_CACHE / f"{etichetta}_{url.rsplit('/', 1)[-1]}"
    if destinazione.exists() and not forza:
        return destinazione
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    temporaneo = destinazione.with_suffix(".tmp")
    try:
        with requests.get(url, timeout=TIMEOUT, headers=INTESTAZIONI, stream=True) as r:
            if r.status_code != 200:
                raise IstatError(f"ISTAT ha risposto {r.status_code} al download di {url}")
            with open(temporaneo, "wb") as f:
                for blocco in r.iter_content(1 << 20):
                    f.write(blocco)
    except requests.RequestException as exc:
        temporaneo.unlink(missing_ok=True)
        raise IstatError(f"Download fallito: {url} ({exc})") from exc
    temporaneo.replace(destinazione)
    return destinazione


def _mappa_comuni(ids_comuni):
    """{codice ISTAT nel file: [id dell'anagrafica]}, identità: v. nota sui comuni fusi sopra."""
    ids = {str(i).zfill(6) for i in ids_comuni}
    return {i: [i] for i in ids}


def scarica_bilancio_mensile(anno, forza=False):
    """Scarica (o riusa dalla cache) lo ZIP del bilancio demografico mensile di un anno
    — canale D, URL stabile — e restituisce il percorso."""
    destinazione = DIR_CACHE / f"bilancio_mensile_{anno}.csv.zip"
    if destinazione.exists() and not forza:
        return destinazione
    url = URL_BILANCIO.format(anno=anno)
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    temporaneo = destinazione.with_suffix(".tmp")
    try:
        with requests.get(url, timeout=TIMEOUT, headers=INTESTAZIONI, stream=True) as r:
            if r.status_code == 404:
                raise IstatError(f"il bilancio mensile {anno} non è scaricabile (404): come CSV ISTAT "
                                 f"pubblica solo {ANNI_BILANCIO.start}-{ANNI_BILANCIO.stop - 1}")
            if r.status_code != 200:
                raise IstatError(f"ISTAT ha risposto {r.status_code} al download di {url}")
            with open(temporaneo, "wb") as f:
                for blocco in r.iter_content(1 << 20):
                    f.write(blocco)
    except requests.RequestException as exc:
        temporaneo.unlink(missing_ok=True)
        raise IstatError(f"Download fallito: {url} ({exc})") from exc
    temporaneo.replace(destinazione)
    return destinazione


def leggi_bilancio_mensile(percorso_zip, ids_comuni):
    """Morti per comune e mese dal bilancio demografico mensile (canale D), solo le righe
    `Sesso = Totale` (già sommate dalla fonte, coerente con la decisione di non usare le
    classi d'età).

    Restituisce un DataFrame id_comune, anno, mese, morti, popolazione_inizio,
    popolazione_fine, stato, nota: una riga per comune e per ciascuno dei 12 mesi
    dell'anno del file. Un comune/mese assente dal file è `NO_DATA`; un valore non
    numerico o negativo è `NULL`.
    """
    mappa = _mappa_comuni(ids_comuni)
    try:
        with zipfile.ZipFile(percorso_zip) as z:
            nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(nome) as f:
                d = pd.read_csv(f, sep=";", dtype=str, na_filter=False, encoding="utf-8")
    except (zipfile.BadZipFile, StopIteration) as exc:
        raise IstatError(f"ZIP del bilancio mensile illeggibile o senza CSV: {percorso_zip} ({exc})") from exc
    mancanti = COLONNE_BILANCIO - set(d.columns)
    if mancanti:
        raise IstatError(f"CSV del bilancio mensile senza le colonne attese: {sorted(mancanti)}")

    d = d[d["Sesso"].str.strip() == SESSO_TOTALE].copy()
    d["id_file"] = d["Codice comune"].str.zfill(6)
    d = d[d["id_file"].isin(mappa)]
    if d.empty:
        raise IstatError("Nessuna riga per i comuni richiesti nel bilancio mensile: codici diversi o file cambiato?")
    anni = sorted(set(pd.to_numeric(d["Anno"], errors="coerce").dropna().astype(int)))
    if len(anni) != 1:
        raise IstatError(f"atteso un solo anno nel file del bilancio mensile, trovati {anni}")
    anno = anni[0]
    d["mese"] = pd.to_numeric(d["Mese"], errors="coerce")
    d["morti"] = pd.to_numeric(d["Morti"], errors="coerce")
    for colonna, nuova in (("Popolazione inizio periodo", "popolazione_inizio"),
                           ("Popolazione fine periodo", "popolazione_fine")):
        d[nuova] = pd.to_numeric(d[colonna], errors="coerce")

    righe = []
    for id_file, ids_anagrafica in mappa.items():
        del_comune = d[d["id_file"] == id_file].set_index("mese")
        for id_comune in ids_anagrafica:
            for mese in range(1, 13):
                base = {"id_comune": id_comune, "anno": anno, "mese": mese}
                if mese not in del_comune.index:
                    righe.append({**base, "morti": None, "popolazione_inizio": None, "popolazione_fine": None,
                                  "stato": "NO_DATA", "nota": "comune/mese assente nel file del bilancio"})
                    continue
                r = del_comune.loc[mese]
                morti = r["morti"]
                if pd.isna(morti):
                    righe.append({**base, "morti": None, "popolazione_inizio": None, "popolazione_fine": None,
                                  "stato": "NULL", "nota": "valore dei morti non numerico nella fonte"})
                elif morti < 0:
                    righe.append({**base, "morti": None, "popolazione_inizio": None, "popolazione_fine": None,
                                  "stato": "NULL", "nota": f"valore negativo: {morti}"})
                else:
                    righe.append({**base, "morti": int(morti),
                                  "popolazione_inizio": None if pd.isna(r["popolazione_inizio"]) else int(r["popolazione_inizio"]),
                                  "popolazione_fine": None if pd.isna(r["popolazione_fine"]) else int(r["popolazione_fine"]),
                                  "stato": "VALORE", "nota": None})
    out = pd.DataFrame(righe).sort_values(["id_comune", "mese"]).reset_index(drop=True)
    out["morti"] = out["morti"].astype("Int64")
    out.attrs.update(anno=anno, file=Path(percorso_zip).name)
    return out


def _valore(testo):
    """(valore, stato, nota) di una cella T_aa."""
    if testo == "n.d.":
        return None, "NO_DATA", "informazione non ancora disponibile"
    try:
        v = int(testo)
    except (TypeError, ValueError):
        return None, "NULL", f"valore non numerico: {testo!r}"
    if v < 0:
        return None, "NULL", f"valore negativo: {v}"
    return v, "VALORE", None


def leggi_decessi(percorso_zip, ids_comuni, blocco=500_000):
    """Decessi giornalieri totali per comune (somma di sesso e classi di età), solo `ids_comuni`.

    Restituisce un DataFrame lungo con colonne id_comune, data, decessi, stato, nota: una riga per
    comune e per giorno dal 01/01/2011 al 31/12 dell'ultimo anno del file; i giorni oltre la fine
    della copertura sono NO_DATA. Negli `attrs` del DataFrame: `fine_copertura` (ultimo giorno con
    dato) e `rilascio` (nome dello ZIP). `ids_comuni` sono i codici ISTAT dell'anagrafica territorio.
    """
    mappa = _mappa_comuni(ids_comuni)
    try:
        with zipfile.ZipFile(percorso_zip) as z:
            nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(nome) as f:
                intestazione = pd.read_csv(f, nrows=0, dtype=str, encoding=CODIFICA).columns
    except (zipfile.BadZipFile, StopIteration) as exc:
        raise IstatError(f"ZIP ISTAT illeggibile o senza CSV: {percorso_zip} ({exc})") from exc
    colonne_t = sorted(c for c in intestazione if re.fullmatch(r"T_\d\d", c))
    mancanti = COLONNE_BASE - set(intestazione)
    if mancanti or not colonne_t:
        raise IstatError(f"CSV ISTAT senza le colonne attese: {sorted(mancanti)} / T_aa: {len(colonne_t)}")

    pezzi = []
    with zipfile.ZipFile(percorso_zip) as z, z.open(nome) as f:
        for chunk in pd.read_csv(f, dtype=str, usecols=sorted(COLONNE_BASE | set(colonne_t)),
                                 chunksize=blocco, na_filter=False, encoding=CODIFICA):
            chunk = chunk[chunk["COD_PROVCOM"].str.zfill(6).isin(mappa)]
            if not chunk.empty:
                pezzi.append(chunk)
    if not pezzi:
        raise IstatError("Nessuna riga per i comuni richiesti: codici ISTAT diversi o file cambiato?")
    d = pd.concat(pezzi, ignore_index=True)
    d["COD_PROVCOM"] = d["COD_PROVCOM"].str.zfill(6)
    senza_righe = set(mappa) - set(d["COD_PROVCOM"])  # nessun decesso in 15 anni: tutti zeri, non un errore

    # formato largo -> lungo: una riga per comune x classe x giorno x anno
    lungo = d.melt(id_vars=["COD_PROVCOM", "TIPO_COMUNE", "GE"], value_vars=colonne_t,
                   var_name="anno", value_name="testo")
    lungo["anno"] = 2000 + lungo["anno"].str[2:].astype(int)
    lungo["numero"] = pd.to_numeric(lungo["testo"], errors="coerce")
    lungo["nd"] = lungo["testo"] == "n.d."
    lungo["invalido"] = lungo["numero"].isna() & ~lungo["nd"] | (lungo["numero"] < 0)
    # somma sulle classi di età; una cella è NO_DATA/NULL se lo è una qualunque delle sue righe
    cella = (lungo.groupby(["COD_PROVCOM", "anno", "GE"])
             .agg(decessi=("numero", "sum"), nd=("nd", "any"), invalido=("invalido", "any"),
                  tipo2=("TIPO_COMUNE", lambda t: (t == "2").any()))
             .reset_index())
    ultimo_anno = max(lungo["anno"])
    nd_ultimo = cella[(cella["anno"] == ultimo_anno) & cella["nd"]]
    if len(nd_ultimo):  # primo giorno non coperto = il più piccolo MMGG con n.d.
        mm, gg = divmod(int(nd_ultimo["GE"].astype(int).min()), 100)
        fine = date(ultimo_anno, mm, gg).toordinal() - 1
        fine_copertura = date.fromordinal(fine)
    else:
        fine_copertura = date(ultimo_anno, 12, 31)

    # griglia completa: tutti i giorni reali (niente 29/02 negli anni non bisestili) per ogni comune
    giorni = pd.date_range(f"{ANNO_INIZIO}-01-01", f"{ultimo_anno}-12-31", freq="D")
    base = pd.DataFrame({"data": giorni})
    base["anno"], base["GE"] = base["data"].dt.year, base["data"].dt.strftime("%m%d")
    righe = []
    for codice, id_anagrafica in mappa.items():
        g = base.merge(cella[cella["COD_PROVCOM"] == codice].drop(columns="COD_PROVCOM"),
                       on=["anno", "GE"], how="left")
        g["decessi"] = g["decessi"].fillna(0)  # riga assente = nessun decesso
        for col in ("nd", "invalido", "tipo2"):
            g[col] = g[col].eq(True)
        fuori = g["data"] > pd.Timestamp(fine_copertura)
        stato = pd.Series("VALORE", index=g.index)
        nota = pd.Series(None, index=g.index, dtype=object)
        stato[g["invalido"]] = "NULL"
        nota[g["invalido"]] = "valore non numerico o negativo nella fonte"
        stato[g["nd"] | fuori | (g["tipo2"] & (g["anno"] == ultimo_anno))] = "NO_DATA"
        nota[stato == "NO_DATA"] = "oltre la fine della copertura del rilascio"
        g["decessi"] = g["decessi"].where(stato == "VALORE").astype("Int64")
        g["stato"], g["nota"] = stato, nota
        for i in id_anagrafica:
            righe.append(g.assign(id_comune=i)[["id_comune", "data", "decessi", "stato", "nota"]])
    out = pd.concat(righe, ignore_index=True).sort_values(["id_comune", "data"]).reset_index(drop=True)
    out["data"] = out["data"].dt.date
    out.attrs.update(fine_copertura=fine_copertura, rilascio=Path(percorso_zip).name,
                     comuni_senza_righe=sorted(senza_righe))
    return out
