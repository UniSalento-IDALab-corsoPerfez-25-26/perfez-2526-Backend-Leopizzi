#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client per Copernicus CAMS (Atmosphere Data Store, via `cdsapi`). Scheda del
servizio, licenze e limiti: data/dataset/aria/copernicus_cams/Copernicus_CAMS.md.

Due prodotti europei a 0,1° (~10 km), concentrazioni orarie di superficie in µg/m³:
  - rianalisi `cams-europe-air-quality-reanalyses` (storico 2016 →, validata fino
    all'anno consegnato, poi `interim`): **non ha il parametro `area`**, ogni richiesta
    è un mese di tutta l'Europa per una variabile. Il file si apre, si ritaglia sul
    Salento e si butta: in cache (data/raw/aria/copernicus_cams/, gitignored) resta
    solo la fetta del Salento, in parquet;
  - analisi `cams-europe-air-quality-forecasts` con `type=analysis` (dal 2023-09-23 a
    ieri, archivio mobile): ha `area`, quindi il ritaglio è nella richiesta.

Accesso: serve un account ADS gratuito e il token in `COPERNICUS_API_KEY` (.env, si
carica con `uv run --env-file .env`); le **licenze di ogni dataset vanno accettate a
mano una volta** dalla pagina del dataset (tab Download), altrimenti l'ADS risponde
403 "required licences not accepted" (verificato il 02/10/2026).

Controllo a monte (v. docs/Regole_dei_dati.md): il NetCDF deve avere una sola variabile dati,
gli assi latitudine e longitudine e un asse del tempo; valori non numerici, non finiti
o negativi diventano NaN (→ ora non valida). Qualunque difformità solleva
CopernicusError, che l'adattatore (api/aria/fonti/cams.py) trasforma in celle NULL e in
una riga di errori_api.csv.

**Non verificato su un file reale** (le licenze non erano ancora accettate): nomi di
coordinate e variabili sono letti in modo tollerante (`valid_time`/`time`,
`latitude`/`lat`...), ma al primo download vanno riconfermati.
"""

import os
import shutil
import time
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

RADICE = Path(__file__).resolve().parents[2]
DIR_CACHE = RADICE / "data" / "raw" / "aria" / "copernicus_cams"
URL_ADS = "https://ads.atmosphere.copernicus.eu/api"

DATASET_RIANALISI = "cams-europe-air-quality-reanalyses"
DATASET_ANALISI = "cams-europe-air-quality-forecasts"

# sigla del progetto -> nome della variabile ADS. Unità CAMS: µg/m³ per tutte.
VARIABILI = {
    "CO": "carbon_monoxide",
    "NO2": "nitrogen_dioxide",
    "O3": "ozone",
    "PM2.5": "particulate_matter_2.5um",
    "PM10": "particulate_matter_10um",
    "SO2": "sulphur_dioxide",
}
INIZIO_RIANALISI = date(2016, 1, 1)  # CO e SO2 esistono solo dal 2016 (v. scheda)
INIZIO_ANALISI = date(2023, 9, 23)  # archivio mobile dell'analisi europea

# Riquadro del Salento [Nord, Ovest, Sud, Est] per le richieste con `area` (come BBOX_SALENTO di
# OpenAQ ed EEA) e ritaglio locale della rianalisi, con un margine di mezza cella.
AREA_SALENTO = [40.95, 16.70, 39.75, 18.55]
RITAGLIO = {"lat": (39.65, 41.05), "lon": (16.60, 18.65)}

ETA_MAX_S = {"analisi_mese_in_corso": 6 * 3600, "interim": 60 * 86400}  # età oltre cui si riscarica
TENTATIVI, ATTESA_S = 2, 20


class CopernicusError(RuntimeError):
    """Errore nella chiamata all'ADS o file con struttura inattesa."""


def _client(url=None):
    """Client `cdsapi`: ADS per CAMS; `url` lo punta altrove (il CDS di ERA5-Land, api/calore/era5_land.py)."""
    import cdsapi  # import tardivo: serve solo a chi scarica

    chiave = os.environ.get("COPERNICUS_API_KEY") or os.environ.get("CDSAPI_KEY")
    if not chiave:
        raise CopernicusError("manca COPERNICUS_API_KEY: lanciare con `uv run --env-file .env`")
    return cdsapi.Client(url=url or os.environ.get("CDSAPI_URL", URL_ADS), key=chiave, quiet=True, progress=False)


def _retrieve(dataset, richiesta, destinazione, url=None):
    """Esegue la richiesta con un nuovo tentativo; solleva CopernicusError."""
    ultimo = None
    for tentativo in range(1, TENTATIVI + 1):
        try:
            _client(url).retrieve(dataset, richiesta, str(destinazione))
            return
        except CopernicusError:
            raise
        except Exception as exc:  # noqa: BLE001 — cdsapi solleva requests/HTTP/RuntimeError eterogenei
            ultimo = exc
            testo = str(exc)
            if "licences not accepted" in testo or "site policies" in testo or "403" in testo or "400" in testo:
                break  # inutile riprovare: licenza non accettata o richiesta non valida
            if tentativo < TENTATIVI:
                time.sleep(ATTESA_S)
    raise CopernicusError(f"{dataset}: {str(ultimo).strip().splitlines()[-1][:300]}")


def _apri_file_scaricato(percorso):
    """Percorsi dei .nc del file scaricato (che può essere un NetCDF o uno zip di NetCDF)."""
    percorso = Path(percorso)
    if zipfile.is_zipfile(percorso):
        cartella = percorso.parent / "estratto"
        with zipfile.ZipFile(percorso) as z:
            z.extractall(cartella)
        nc = sorted(cartella.rglob("*.nc"))
        if not nc:
            raise CopernicusError("lo zip scaricato non contiene file .nc")
        return nc
    return [percorso]


def _asse(nomi, ds, descrizione):
    trovati = [n for n in nomi if n in ds.dims or n in ds.coords]
    if not trovati:
        raise CopernicusError(f"asse {descrizione} non trovato (cercati {nomi}; presenti {list(ds.coords)})")
    return trovati[0]


def leggi_netcdf(percorso):
    """DataFrame (ora_utc, lat, lon, valore) con le ore del NetCDF ritagliate sul Salento.
    Valori non numerici, non finiti o negativi → NaN. Solleva CopernicusError se la struttura
    non è quella attesa."""
    import xarray as xr

    righe = []
    for nc in _apri_file_scaricato(percorso):
        try:
            ds = xr.open_dataset(nc)
        except Exception as exc:  # noqa: BLE001
            raise CopernicusError(f"NetCDF illeggibile ({nc.name}): {exc}") from exc
        with ds:
            variabili = [v for v in ds.data_vars if {"latitude", "longitude"} <= set(ds[v].dims) or {"lat", "lon"} <= set(ds[v].dims)]
            if len(variabili) != 1:
                raise CopernicusError(f"attesa una variabile dati con latitudine/longitudine, trovate {list(ds.data_vars)}")
            lat_n, lon_n = _asse(["latitude", "lat"], ds, "latitudine"), _asse(["longitude", "lon"], ds, "longitudine")
            da = ds[variabili[0]].squeeze(drop=True)
            altri = [d for d in da.dims if d not in (lat_n, lon_n)]
            if len(altri) != 1:
                raise CopernicusError(f"atteso un solo asse oltre a lat/lon (il tempo), trovati {altri}")
            tempo_n = altri[0]
            if "valid_time" in ds.coords and ds["valid_time"].dims == (tempo_n,):
                da = da.assign_coords({tempo_n: ds["valid_time"].values})
            lats, lons = da[lat_n].values.astype(float), da[lon_n].values.astype(float)
            lons = np.where(lons > 180, lons - 360, lons)
            ok_lat = np.flatnonzero((lats >= RITAGLIO["lat"][0]) & (lats <= RITAGLIO["lat"][1]))
            ok_lon = np.flatnonzero((lons >= RITAGLIO["lon"][0]) & (lons <= RITAGLIO["lon"][1]))
            if not len(ok_lat) or not len(ok_lon):
                raise CopernicusError("il file non contiene celle del Salento")
            fetta = da.isel({lat_n: ok_lat, lon_n: ok_lon}).transpose(tempo_n, lat_n, lon_n).load()
            tempi = pd.to_datetime(fetta[tempo_n].values)
            valori = fetta.values.astype(float)
            n_t, n_la, n_lo = valori.shape
            righe.append(pd.DataFrame({
                "ora_utc": np.repeat(tempi, n_la * n_lo),
                "lat": np.tile(np.repeat(np.round(lats[ok_lat], 4), n_lo), n_t),
                "lon": np.tile(np.round(lons[ok_lon], 4), n_t * n_la),
                "valore": valori.ravel(),
            }))
    df = pd.concat(righe, ignore_index=True).drop_duplicates(["ora_utc", "lat", "lon"])
    df.loc[~np.isfinite(df["valore"]) | (df["valore"] < 0), "valore"] = np.nan
    return df


def _cache_valida(percorso, eta_max_s):
    return percorso.exists() and (eta_max_s is None or time.time() - percorso.stat().st_mtime < eta_max_s)


def _scarica_e_leggi(dataset, richiesta, cache):
    """Scarica in una cartella temporanea propria della richiesta (così più richieste in parallelo non si
    cancellano i file a vicenda), ritaglia sul Salento, salva in cache la sola fetta e butta il resto."""
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    temporanea = DIR_CACHE / f"{cache.stem}.tmp"
    temporanea.mkdir(exist_ok=True)
    try:
        grezzo = temporanea / "download"
        _retrieve(dataset, richiesta, grezzo)
        df = leggi_netcdf(grezzo)
    finally:
        shutil.rmtree(temporanea, ignore_errors=True)
    df.to_parquet(cache, index=False)
    return df


def ore_rianalisi(sigla, anno, mese, scarica=True):
    """Ore del mese (UTC) sul Salento dalla rianalisi europea per l'inquinante `sigla`.
    Prova prima la rianalisi validata, poi l'interim. Restituisce (DataFrame, prodotto) con
    prodotto 'rianalisi validata' | 'rianalisi interim'; None se `scarica` è False e il mese non è in cache."""
    base = f"rianalisi_{sigla}_{anno}-{mese:02d}"
    for tipo, etichetta in (("validated_reanalysis", "rianalisi validata"), ("interim_reanalysis", "rianalisi interim")):
        cache = DIR_CACHE / f"{base}_{tipo.split('_')[0]}.parquet"
        if _cache_valida(cache, ETA_MAX_S["interim"] if tipo.startswith("interim") and scarica else None):
            return pd.read_parquet(cache), etichetta
    if not scarica:
        return None
    errori = []
    for tipo, etichetta in (("validated_reanalysis", "rianalisi validata"), ("interim_reanalysis", "rianalisi interim")):
        cache = DIR_CACHE / f"{base}_{tipo.split('_')[0]}.parquet"
        richiesta = {"variable": [VARIABILI[sigla]], "model": ["ensemble"], "level": ["0"],
                     "type": [tipo], "year": [str(anno)], "month": [f"{mese:02d}"]}
        try:
            return _scarica_e_leggi(DATASET_RIANALISI, richiesta, cache), etichetta
        except CopernicusError as exc:
            errori.append(str(exc))
    raise CopernicusError(" | ".join(errori))


def _ripara_ore_analisi(df, inizio):
    """Il NetCDF dell'analisi (`type=analysis`) non porta una data vera sull'asse del tempo: `leggi_netcdf`
    ne ricava 0, 1, 2, … (ore dall'inizio della richiesta) che pandas legge come nanosecondi dal 1970.
    Qui l'indice diventa `inizio` + k ore. Si ripara solo se gli indici sono ore consecutive da 0 e
    piene (multiplo di 24), altrimenti non si può sapere a quale ora appartiene un valore e si solleva
    CopernicusError. Un DataFrame con date già vere passa invariato (la riparazione è idempotente)."""
    if df["ora_utc"].min() >= pd.Timestamp("2000-01-01"):
        return df
    k = df["ora_utc"].astype("int64")
    ore = np.sort(k.unique())
    if len(ore) % 24 or not np.array_equal(ore, np.arange(len(ore))):
        raise CopernicusError(f"orari dell'analisi non ricostruibili: {len(ore)} indici, "
                              f"da {ore.min()} a {ore.max()}, non sono ore consecutive e piene")
    df = df.copy()
    df["ora_utc"] = pd.Timestamp(inizio) + pd.to_timedelta(k, unit="h")
    return df


def ore_analisi(sigla, anno, mese, scarica=True):
    """Ore del mese (UTC) sul Salento dall'analisi europea (`type=analysis`, ora per ora).
    Restituisce (DataFrame, 'analisi') o None come `ore_rianalisi`."""
    inizio = max(date(anno, mese, 1), INIZIO_ANALISI)
    fine_mese = (pd.Timestamp(anno, mese, 1) + pd.offsets.MonthEnd(0)).date()
    fine = min(fine_mese, date.today())
    cache = DIR_CACHE / f"analisi_{sigla}_{anno}-{mese:02d}.parquet"
    in_corso = fine_mese >= date.today()
    # L'età massima serve a forzare il *ri-download*: senza download (`solo_cache`) una cache vecchia
    # è meglio di nessun dato, quindi non si scarta (altrimenti il mese aperto uscirebbe tutto NULL).
    if _cache_valida(cache, ETA_MAX_S["analisi_mese_in_corso"] if in_corso and scarica else None):
        df = pd.read_parquet(cache)
        if df["ora_utc"].min() < pd.Timestamp("2000-01-01"):  # cache scritta prima della riparazione
            df = _ripara_ore_analisi(df, inizio)
            df.to_parquet(cache, index=False)
        return df, "analisi"
    if not scarica:
        return None
    richiesta = {"variable": [VARIABILI[sigla]], "model": ["ensemble"], "level": ["0"], "type": ["analysis"],
                 "date": [f"{inizio.isoformat()}/{fine.isoformat()}"], "time": [f"{h:02d}:00" for h in range(24)],
                 "leadtime_hour": ["0"], "data_format": "netcdf_zip", "area": AREA_SALENTO}
    df = _ripara_ore_analisi(_scarica_e_leggi(DATASET_ANALISI, richiesta, cache), inizio)
    df.to_parquet(cache, index=False)
    return df, "analisi"
