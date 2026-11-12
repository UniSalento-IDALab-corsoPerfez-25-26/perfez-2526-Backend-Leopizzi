#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client per l'Air Quality Download Service dell'EEA (European Environment
Agency). Scheda completa del servizio (link, licenza, formato, copertura
verificata per il Salento): data/dataset/aria/eea/EEA.md.

Accesso scelto (28/09/2026): lista di URL. `POST /ParquetFile/urls` restituisce
un URL per punto di campionamento (stazione × inquinante × metodo); si
scaricano solo i file delle stazioni del Salento, che contengono l'intera serie
oraria del punto. Nessuna API key. I file scaricati restano in cache in
data/raw/aria/eea/ (gitignored): i parquet E1a cambiano una volta l'anno, gli
E2a (non verificati, anno in corso) più volte al giorno.

Controllo a monte (v. docs/Regole_dei_dati.md): la lista di URL deve avere la colonna
`ParquetFileUrl`, i parquet le colonne attese; qui non si classificano i
singoli valori (lo fa l'adattatore api/aria/fonti/eea.py, ora per ora).

Nessuna chiamata scrive su un database (v. docs/Architettura.md).
"""

import io
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

RADICE = Path(__file__).resolve().parents[2]
BASE_URL = "https://eeadmz1-downloads-api-appservice.azurewebsites.net"
URL_METADATI = "https://discomap.eea.europa.eu/App/AQViewer/download?fqn=Airquality_Dissem.b2g.measurements&f=csv"
DIR_CACHE = RADICE / "data" / "raw" / "aria" / "eea"
TIMEOUT = 120

# valori del campo `dataset` dell'API (guida "How to use Air Quality Downloads" v. 1.2)
DATASET_E2A = 1  # non verificati, trasmessi in continuo (oggi: anno in corso)
DATASET_E1A = 2  # verificati, consegnati entro il 30/09 per l'anno precedente (oggi: 2013-2025)

# notazione EEA dei 6 inquinanti tracciati -> codice Eionet (nel nome file e nella colonna Pollutant)
INQUINANTI = {"SO2": 1, "PM10": 5, "O3": 7, "NO2": 8, "CO": 10, "PM2.5": 6001}

# Bounding box del Salento, lo stesso di OpenAQ (api/aria/openaq.py): minLon, minLat, maxLon, maxLat.
# Largo di proposito: il filtro preciso per comune/distretto si fa sui risultati.
BBOX_SALENTO = (16.70, 39.75, 18.55, 40.95)

COLONNE_PARQUET = {"Samplingpoint", "Pollutant", "Start", "End", "Value", "Unit", "AggType", "Validity", "Verification"}
COLONNE_METADATI = {"Country", "Air Quality Station EoI Code", "Air Quality Station Name", "Sampling Point Id",
                    "Air Pollutant", "Longitude", "Latitude"}

# età massima di un file in cache prima di riscaricarlo (s)
ETA_MAX = {DATASET_E1A: 7 * 86400, DATASET_E2A: 3 * 3600, "metadati": 7 * 86400}


class EEAError(RuntimeError):
    """Errore nella chiamata al servizio EEA o payload inatteso."""


def _post(endpoint, corpo):
    url = f"{BASE_URL}/{endpoint}"
    try:
        risposta = requests.post(url, json=corpo, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise EEAError(f"Chiamata fallita: {url} ({exc})") from exc
    if risposta.status_code != 200:
        raise EEAError(f"EEA ha risposto {risposta.status_code} a {endpoint}: {risposta.text[:300]}")
    return risposta


def _scarica(url, destinazione, eta_max):
    """Scarica `url` in `destinazione`, salvo che la copia in cache sia più recente di `eta_max` secondi."""
    if destinazione.exists() and time.time() - destinazione.stat().st_mtime < eta_max:
        return destinazione
    try:
        risposta = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise EEAError(f"Download fallito: {url} ({exc})") from exc
    if risposta.status_code != 200:
        raise EEAError(f"EEA ha risposto {risposta.status_code} al download di {url}")
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = destinazione.with_suffix(destinazione.suffix + ".tmp")
    temporaneo.write_bytes(risposta.content)
    temporaneo.replace(destinazione)
    return destinazione


def get_urls(dataset, paese="IT", inquinanti=tuple(INQUINANTI)):
    """URL dei parquet (uno per punto di campionamento) di un paese per il `dataset` (DATASET_E1A/E2A).
    Il servizio ignora qui date e tipo di aggregazione: ogni file ha l'intera serie.
    `cities` va passato vuoto esplicitamente: senza il campo l'API risponde "Processing error"."""
    corpo = {"countries": [paese], "cities": [], "pollutants": list(inquinanti), "dataset": dataset, "source": "API"}
    righe = _post("ParquetFile/urls", corpo).content.decode("utf-8-sig").splitlines()
    if not righe or righe[0].strip() != "ParquetFileUrl":
        raise EEAError(f"Payload malformato da ParquetFile/urls: intestazione {righe[:1]!r} invece di 'ParquetFileUrl'")
    return [r.strip() for r in righe[1:] if r.strip()]


def get_metadati(paese="Italy"):
    """Anagrafica EEA dei punti di campionamento di un paese (DataExtract.csv, una riga per punto e anno)."""
    file_zip = _scarica(URL_METADATI, DIR_CACHE / "metadati" / "DataExtract.zip", ETA_MAX["metadati"])
    try:
        with zipfile.ZipFile(file_zip) as z:
            nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            df = pd.read_csv(io.BytesIO(z.read(nome)), low_memory=False)
    except (zipfile.BadZipFile, StopIteration, ValueError) as exc:
        file_zip.unlink(missing_ok=True)
        raise EEAError(f"Metadati EEA illeggibili ({exc})") from exc
    mancanti = COLONNE_METADATI - set(df.columns)
    if mancanti:
        raise EEAError(f"Metadati EEA senza le colonne attese: {sorted(mancanti)}")
    return df[df["Country"] == paese].reset_index(drop=True)


def stazioni_nel_riquadro(metadati, bbox=BBOX_SALENTO):
    """Una riga per stazione (codice EoI) con nome e coordinate, solo nel riquadro `bbox`."""
    min_lon, min_lat, max_lon, max_lat = bbox
    m = metadati[metadati["Longitude"].between(min_lon, max_lon) & metadati["Latitude"].between(min_lat, max_lat)]
    # l'ultimo anno di riferimento prevale (nome e coordinate aggiornati)
    m = m.sort_values("Year", na_position="first") if "Year" in m.columns else m
    return (m.groupby("Air Quality Station EoI Code")
             .agg(nome=("Air Quality Station Name", "last"), lat=("Latitude", "last"), lon=("Longitude", "last"))
             .reset_index().rename(columns={"Air Quality Station EoI Code": "codice_eoi"}))


def info_da_url(url):
    """(codice EoI della stazione, codice Eionet dell'inquinante) dal nome del file,
    es. .../SPO.IT1665A_8_chemi_2004-05-01_00_00_00.parquet -> ("IT1665A", 8)."""
    nome = url.rsplit("/", 1)[-1]
    parti = nome.removeprefix("SPO.").split("_")
    try:
        return parti[0], int(parti[1])
    except (IndexError, ValueError):
        return None, None


def leggi_parquet(url, dataset):
    """DataFrame del parquet di un punto di campionamento (scaricato o dalla cache)."""
    contenitore = url.split("/")[-3]  # airquality-p (E2a) / airquality-p-e1a (E1a)
    destinazione = DIR_CACHE / contenitore / url.rsplit("/", 1)[-1].replace(":", "_")
    _scarica(url, destinazione, ETA_MAX[dataset])
    try:
        df = pd.read_parquet(destinazione)
    except Exception as exc:  # noqa: BLE001 — file corrotto o non parquet: si riscarica al prossimo giro
        destinazione.unlink(missing_ok=True)
        raise EEAError(f"Parquet illeggibile {url} ({type(exc).__name__}: {exc})") from exc
    mancanti = COLONNE_PARQUET - set(df.columns)
    if mancanti:
        raise EEAError(f"Parquet {url} senza le colonne attese: {sorted(mancanti)}")
    return df
