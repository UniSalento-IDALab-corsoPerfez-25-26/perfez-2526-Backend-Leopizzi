#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client per Copernicus ERA5-Land (Climate Data Store, via `cdsapi`): temperatura dell'aria a 2 m,
componente 1 dell'UHRI. Scheda, licenza e limiti: data/dataset/calore/era5_land/ERA5_Land.md.

Si usa il dataset *derived-era5-land-daily-statistics* (statistiche giornaliere già calcolate dal CDS):
media, massima e minima del giorno, **già nel fuso UTC+1** del progetto (docs/Regole_dei_dati.md), senza scaricare
le 24 ore. Una richiesta = un mese per una statistica, ritagliata sul Salento con `area` (a differenza
della rianalisi CAMS, il CDS lo consente). In cache (data/raw/calore/era5_land/, gitignored) resta un
parquet per statistica e mese con le celle 0,1° (~9 km) in °C.

Da cella a comune: **media pesata sull'area** (api/comune/celle_comuni.py, stessa regola di CAMS, decisa
il 02/10/2026). Le celle marine sono prive di dato: la media di un comune costiero si calcola sulle sole
celle con dato, rinormalizzando i pesi (la nota dice su quante celle e su quale quota di superficie);
se nessuna cella del comune ha dato → `NULL` con nota, mai silenzio.

Accesso: stessa chiave di CAMS (`COPERNICUS_API_KEY`, `uv run --env-file .env`), ma **le condizioni d'uso
del sito CDS e la licenza del dataset vanno accettate a mano** dal proprio account (altrimenti 403
"user didn't accept all required site policies", verificato il 09/10/2026).

Il formato del NetCDF delle statistiche giornaliere (nomi di variabile e coordinate) è letto in modo
tollerante da `leggi_netcdf` di CAMS ma **va riconfermato al primo download reale**.
"""

import shutil
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from api.aria.copernicus_cams import AREA_SALENTO, CopernicusError, _retrieve, leggi_netcdf
from api.comune.anagrafiche import FILE_ANAGRAFICHE, leggi_anagrafica
from shapely.geometry import Point

from api.comune.celle_comuni import _confini_shapely, copertura_celle, pesi_celle
from api.comune.stati import STATO_NO_DATA, STATO_NULL, STATO_VALORE

RADICE = Path(__file__).resolve().parents[2]
DIR_CACHE = RADICE / "data" / "raw" / "calore" / "era5_land"
URL_CDS = "https://cds.climate.copernicus.eu/api"
DATASET = "derived-era5-land-daily-statistics"
VARIABILE = "2m_temperature"
INIZIO = date(1950, 1, 1)
# statistica del progetto -> nome della statistica CDS
STATISTICHE = {"media": "daily_mean", "massima": "daily_maximum", "minima": "daily_minimum"}
# ultimo giorno chiesto = oggi - 6: misurato il 03/11/2026 (catalogo CDS e richiesta oltre il limite: ultimo giorno il
# 28/10, i giorni non ancora pubblicati il CDS li omette senza errore). v. data/dataset/calore/era5_land/ERA5_Land.md
LATENZA_GIORNI = 6
ETA_MAX_MESE_IN_CORSO_S = 6 * 3600
KELVIN = 273.15


def _fine_mese(anno, mese):
    return (pd.Timestamp(anno, mese, 1) + pd.offsets.MonthEnd(0)).date()


def _file_cache(statistica, anno, mese):
    return DIR_CACHE / f"{statistica}_{anno}-{mese:02d}.parquet"


def _cache_valida(percorso, anno, mese):
    if not percorso.exists():
        return False
    if _fine_mese(anno, mese) < date.today() - timedelta(days=LATENZA_GIORNI):
        return True  # mese chiuso e ormai consolidato
    return time.time() - percorso.stat().st_mtime < ETA_MAX_MESE_IN_CORSO_S


def celle_mese(statistica, anno, mese, scarica=True):
    """Celle ERA5-Land del mese per la `statistica` ('media', 'massima', 'minima'): DataFrame
    (giorno, lat, lon, valore in °C), NaN sulle celle marine. Solleva CopernicusError se il mese non
    è in cache e `scarica` è False, o se il CDS non risponde."""
    if statistica not in STATISTICHE:
        raise ValueError(f"statistica '{statistica}' sconosciuta: {', '.join(STATISTICHE)}")
    primo, ultimo = date(anno, mese, 1), min(_fine_mese(anno, mese), date.today() - timedelta(days=LATENZA_GIORNI))
    if primo < INIZIO or ultimo < primo:
        raise CopernicusError(f"{anno}-{mese:02d} fuori dalla copertura di ERA5-Land (dal {INIZIO} a oggi - {LATENZA_GIORNI} giorni)")
    cache = _file_cache(statistica, anno, mese)
    # solo cache: il file del mese in corso «scade» dopo 6 ore perché lo scarico lo rinnovi, ma chi legge e basta
    # (server, dataset) deve usarlo lo stesso; i giorni che mancano diventano NO_DATA in per_comune (28/10/2026)
    if _cache_valida(cache, anno, mese) or (not scarica and cache.exists()):
        return pd.read_parquet(cache)
    if not scarica:
        # solo la frase: questa nota arriva nei tooltip della dashboard; il comando per scaricarla è nel README
        raise CopernicusError(f"temperatura {statistica} ERA5-Land di {anno}-{mese:02d} non ancora scaricata in locale")
    richiesta = {
        "variable": [VARIABILE], "year": str(anno), "month": f"{mese:02d}",
        "day": [f"{g:02d}" for g in range(1, ultimo.day + 1)],
        "daily_statistic": STATISTICHE[statistica], "time_zone": "utc+01:00", "frequency": "1_hourly",
        "area": AREA_SALENTO,
    }
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    temporanea = DIR_CACHE / f"{cache.stem}.tmp"
    temporanea.mkdir(exist_ok=True)
    try:
        grezzo = temporanea / "download"
        _retrieve(DATASET, richiesta, grezzo, url=URL_CDS)
        df = leggi_netcdf(grezzo)  # ora_utc = giorno (asse dei tempi giornaliero), valore in K, negativi/non finiti → NaN
    finally:
        shutil.rmtree(temporanea, ignore_errors=True)
    df = df.rename(columns={"ora_utc": "giorno"})  # le celle marine restano, con valore NaN: la griglia deve essere intera
    df["giorno"] = pd.to_datetime(df["giorno"]).dt.date.astype(str)
    df["valore"] = (df["valore"] - KELVIN).round(2)
    if df["valore"].isna().all():
        raise CopernicusError(f"{DATASET} {statistica} {anno}-{mese:02d}: il file non contiene celle con dato")
    df.to_parquet(cache, index=False)
    return df


def _comuni_per_confine():
    """{nome_confine: [id_comune, ...]} dall'anagrafica del territorio (un solo id per poligono dal
    14/10/2026, dopo l'unificazione di Presicce e Acquarica del Capo in Presicce-Acquarica, 075098)."""
    _, _, tabelle = leggi_anagrafica(FILE_ANAGRAFICHE["territorio"])
    per_confine = {}
    for c in tabelle["comuni"]:
        per_confine.setdefault(c["nome_confine"], []).append(c["id_comune"])
    return per_confine


def per_comune(celle, statistica, anno, mese):
    """Dalle celle del mese al valore per comune × giorno: DataFrame (comune, giorno, valore, stato, nota)
    con una riga per ognuno dei 145 comuni e per ogni giorno del mese. I giorni assenti dal file (latenza)
    sono NO_DATA; i comuni senza alcuna cella con dato in quel giorno sono NULL."""
    lat, lon = sorted(celle["lat"].unique()), sorted(celle["lon"].unique())
    pesi = pesi_celle(lat, lon)
    scoperti = [n for n, q in copertura_celle(lat, lon).items() if q < 0.999]
    if scoperti:
        raise CopernicusError(f"la griglia del file non copre tutta la superficie di: {', '.join(scoperti[:5])}")
    griglia = celle.pivot(index="giorno", columns=["lat", "lon"], values="valore")
    colonne = {c: i for i, c in enumerate(griglia.columns)}
    confini = sorted(pesi)
    W = np.zeros((len(confini), len(colonne)))
    for r, confine in enumerate(confini):
        for la, lo, peso in pesi[confine]:
            W[r, colonne[(round(la, 4), round(lo, 4))]] = peso
    V = griglia.to_numpy(dtype=float)
    valido = ~np.isnan(V)
    quota = valido.astype(float) @ W.T  # quota di superficie comunale con dato, per giorno e comune
    medie = np.where(quota > 0, np.nan_to_num(V) @ W.T / np.where(quota > 0, quota, 1), np.nan)
    celle_valide = valido.astype(float) @ (W > 0).T.astype(float)
    n_celle = (W > 0).sum(axis=1)

    # Ripiego (09/10/2026): un comune le cui celle sono tutte marine (Corsano, Patù) prende il valore della cella
    # di terra più vicina al suo confine; la nota lo dichiara. La maschera terra/mare è fissa: si cerca fra le
    # celle con dato in almeno un giorno.
    terra = [j for j in range(V.shape[1]) if valido[:, j].any()]
    vicina = {}  # riga del comune -> (colonna della cella, distanza in gradi)
    geometrie = _confini_shapely()
    for r, confine in enumerate(confini):
        if terra and not any(valido[:, j].any() for j in np.flatnonzero(W[r] > 0)):
            elenco = list(colonne)
            j = min(terra, key=lambda k: geometrie[confine].distance(Point(elenco[k][1], elenco[k][0])))
            vicina[r] = (j, geometrie[confine].distance(Point(elenco[j][1], elenco[j][0])))

    per_confine = _comuni_per_confine()
    giorni_mese = [(date(anno, mese, 1) + timedelta(days=n)).isoformat() for n in range(_fine_mese(anno, mese).day)]
    indice_giorno = {g: i for i, g in enumerate(griglia.index)}
    righe = []
    for g in giorni_mese:
        i = indice_giorno.get(g)
        for r, confine in enumerate(confini):
            for comune in per_confine.get(confine, []):
                if i is None:
                    righe.append((comune, g, np.nan, STATO_NO_DATA,
                                  "giorno non ancora in ERA5-Land (latenza di qualche giorno) o non ancora scaricato"))
                elif np.isnan(medie[i, r]) and r in vicina and not np.isnan(V[i, vicina[r][0]]):
                    j, dist = vicina[r]
                    la, lo = list(colonne)[j]
                    righe.append((comune, g, round(float(V[i, j]), 2), STATO_VALORE,
                                  f"temperatura {statistica} a 2 m (UTC+1) della cella di terra ERA5-Land 0,1° più vicina "
                                  f"({la:.1f}°N {lo:.1f}°E, a ~{dist * 111:.0f} km dal confine): le celle del comune "
                                  "sono tutte marine; dato modellato (rianalisi)"))
                elif np.isnan(medie[i, r]):
                    righe.append((comune, g, np.nan, STATO_NULL,
                                  f"nessuna delle {n_celle[r]} celle ERA5-Land del comune ha dato (celle marine)"))
                else:
                    righe.append((comune, g, round(float(medie[i, r]), 2), STATO_VALORE,
                                  f"temperatura {statistica} a 2 m (UTC+1), media pesata sull'area di "
                                  f"{int(celle_valide[i, r])}/{n_celle[r]} celle ERA5-Land 0,1° ({quota[i, r]:.0%} "
                                  "della superficie con dato); dato modellato (rianalisi)"))
    return pd.DataFrame(righe, columns=["comune", "giorno", "valore", "stato", "nota"])


def temperatura_comuni(statistica, anno, mese, scarica=True):
    """Temperatura giornaliera per comune del mese (v. `per_comune`)."""
    return per_comune(celle_mese(statistica, anno, mese, scarica=scarica), statistica, anno, mese)
