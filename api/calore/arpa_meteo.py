#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client per la rete meteo di ARPA Puglia (temperatura misurata): **validazione per ridondanza** di ERA5-Land.
Scheda: data/dataset/calore/arpa_meteo/ARPA_Meteo.md.

Accesso (verificato il 14/10/2026): i CSV annuali per stazione stanno su `dati.arpa.puglia.it/Meteo/` — è
l'host a cui puntano le risorse CKAN di dati.puglia.it, **diverso** da `cloud.arpa.puglia.it` (irraggiungibile).
Serve gli anni **2020 → 2026** (fino a ieri; fuori da questo intervallo risponde HTTP 400), quindi il vecchio
limite «solo 2023-2024» è superato. Nessuna chiave.

    stazioni.jsp                              GeoJSON delle 27 stazioni (rete "Meteo" id 1-5, rete "RRQA" id 6-27)
    dati_rrqa.jsp?id_station=<id>&year=<aaaa> rete RRQA: una riga all'ora, `temperatura` istantanea
    dati.jsp?id_station=<id>&year=<aaaa>      rete dedicata: una riga ogni 30 minuti, `temperatura_min|avg|max`

L'orario `data_ora` è in **UTC+1 fisso** (verificato sul ciclo diurno: minimo poco dopo l'alba CET), come il resto
del progetto. Codici di validazione `cod_validazione_temperatura`: 1 corretto, 5 ricostruito → `VALORE`; 2 sospetto,
3 errato, 4 non valido, 6 mancante → `NULL` (v. ARPA_Meteo.md §3).

Valore giornaliero (regola di OpenAQ/EEA, docs/Regole_dei_dati.md): media pesata uguale sulle misure valide del giorno,
nessuna soglia minima di ore, completezza nella nota. Le statistiche sono le stesse di ERA5-Land (`media`,
`massima`, `minima`), ma **massima e minima non sono identiche fra le due reti**: la RRQA vede solo le 24
letture orarie, la rete dedicata il massimo/minimo di ogni mezz'ora.
"""

import io
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from api.comune.confini_comuni import confine_da_coordinate
from api.comune.stati import STATO_NULL, STATO_VALORE

RADICE = Path(__file__).resolve().parents[2]
DIR_CACHE = RADICE / "data" / "raw" / "calore" / "arpa_meteo"
BASE_URL = "https://dati.arpa.puglia.it/Meteo"
ANNI = range(2020, 2027)
TIMEOUT = 180
ETA_MAX_ANNO_IN_CORSO_S = 6 * 3600
PROVINCE = ("LE", "BR", "TA")
TEMPERATURA_MIN, TEMPERATURA_MAX = -30.0, 55.0  # fuori da qui il valore è un errore del sensore, non meteo
CODICI_VALORE = {1: "", 5: "dato ricostruito dalla fonte"}
CODICI_NULL = {2: "dato sospetto (cod. 2)", 3: "dato errato (cod. 3)", 4: "dato non valido (cod. 4)", 6: "dato mancante (cod. 6)"}
STATISTICHE = ("media", "massima", "minima")
RETE_DEDICATA, RETE_RRQA = "Meteo", "RRQA"
COLONNE_GIORNALIERE = ["stazione", "giorno", "statistica", "valore", "stato", "nota"]


class ArpaMeteoError(RuntimeError):
    """Errore nella chiamata ai servizi meteo di ARPA Puglia."""


def _get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as exc:
        raise ArpaMeteoError(f"Chiamata fallita: {url} ({exc})") from exc
    return r


def stazioni_salento(rete_comuni=None):
    """Stazioni meteo di LE, BR e TA: DataFrame (id_station, rete, indirizzo, provincia, lat, lon, id_comune).
    Il comune è quello che contiene le coordinate (l'anagrafica meteo dichiara solo il nome); una stazione
    fuori da ogni confine entro soglia ha id_comune vuoto."""
    from api.calore.era5_land import _comuni_per_confine  # evita l'import circolare a livello di modulo
    try:
        corpo = _get(f"{BASE_URL}/stazioni.jsp").json()
        features = corpo["features"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ArpaMeteoError(f"Payload malformato da stazioni.jsp: {exc}") from exc
    per_confine = rete_comuni or _comuni_per_confine()
    righe = []
    for f in features:
        p = f.get("properties", {})
        if p.get("provincia") not in PROVINCE:
            continue
        lon, lat = (float(x) for x in f["geometry"]["coordinates"])
        confine, _, _ = confine_da_coordinate(lat, lon)
        comuni = per_confine.get(confine, [])
        righe.append({"id_station": int(p["id_station"]), "rete": p["rete"], "indirizzo": p.get("indirizzo"),
                      "provincia": p["provincia"], "lat": lat, "lon": lon,
                      "id_comune": comuni[0] if comuni else None})
    return pd.DataFrame(righe).sort_values("id_station", ignore_index=True)


def _file_cache(rete, id_station, anno):
    return DIR_CACHE / f"{rete}_{id_station}_{anno}.csv"


def _cache_valida(percorso, anno):
    if not percorso.exists():
        return False
    if anno < time.localtime().tm_year:
        return True  # anno chiuso
    return time.time() - percorso.stat().st_mtime < ETA_MAX_ANNO_IN_CORSO_S


def csv_anno(rete, id_station, anno, scarica=True):
    """CSV grezzo (DataFrame) di una stazione e di un anno, con cache in data/raw/calore/arpa_meteo/ (gitignored).
    Solleva ArpaMeteoError se non è in cache e `scarica` è False, o se la fonte non risponde / risponde un errore."""
    if anno not in ANNI:
        raise ArpaMeteoError(f"anno {anno} non servito dalla fonte (dal {ANNI[0]} al {ANNI[-1]})")
    cache = _file_cache(rete, id_station, anno)
    if _cache_valida(cache, anno) or (not scarica and cache.exists()):  # solo cache: un file vecchio vale più di nulla
        return pd.read_csv(cache, parse_dates=["data_ora"])
    if not scarica:
        # solo la frase: questa nota arriva nei tooltip della dashboard; il comando per scaricarla è nel README
        raise ArpaMeteoError(f"stazione meteo ARPA {id_station} ({rete}): {anno} non ancora scaricato in locale")
    pagina = "dati.jsp" if rete == RETE_DEDICATA else "dati_rrqa.jsp"
    r = _get(f"{BASE_URL}/{pagina}", params={"id_station": id_station, "year": anno})
    try:
        df = pd.read_csv(io.StringIO(r.text), parse_dates=["data_ora"])
    except (ValueError, pd.errors.ParserError) as exc:
        raise ArpaMeteoError(f"Payload malformato da {pagina} ({id_station}, {anno}): {r.text[:80]!r}") from exc
    attese = {"data_ora", "id_station", "cod_validazione_temperatura"} | (
        {"temperatura_min", "temperatura_avg", "temperatura_max"} if rete == RETE_DEDICATA else {"temperatura"})
    if not attese <= set(df.columns):
        raise ArpaMeteoError(f"Payload con campi inattesi da {pagina} ({id_station}, {anno}): mancano {sorted(attese - set(df.columns))}")
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache, index=False)
    return df


def _classifica(df, colonne):
    """Controllo a monte: ogni riga è `VALORE` solo se il codice è 1/5 e tutte le `colonne` sono numeri finiti
    e plausibili; altrimenti `NULL` (la stazione copre l'istante ma il valore non è usabile)."""
    valori = df[colonne].apply(pd.to_numeric, errors="coerce")
    plausibile = valori.notna().all(axis=1) & np.isfinite(valori).all(axis=1) & \
        valori.ge(TEMPERATURA_MIN).all(axis=1) & valori.le(TEMPERATURA_MAX).all(axis=1)
    codice = pd.to_numeric(df["cod_validazione_temperatura"], errors="coerce")
    return codice.isin(CODICI_VALORE) & plausibile, codice


def giornaliero(rete, id_station, anno, scarica=True):
    """Temperatura giornaliera (media, massima, minima) di una stazione in un anno: DataFrame
    COLONNE_GIORNALIERE, una riga per giorno presente nel file e per statistica. `VALORE` se c'è almeno una
    misura valida nel giorno (la nota dice su quante), `NULL` se il giorno c'è ma nessuna misura è usabile.
    I giorni assenti dal file non compaiono: NO_DATA lo decide chi costruisce la griglia."""
    df = csv_anno(rete, id_station, anno, scarica=scarica)
    if rete == RETE_DEDICATA:
        colonne, attese, unita = ["temperatura_min", "temperatura_avg", "temperatura_max"], 48, "intervalli da 30 minuti"
    else:
        colonne, attese, unita = ["temperatura"], 24, "ore"
    valido, codice = _classifica(df, colonne)
    df = df.assign(giorno=df["data_ora"].dt.date.astype(str), valido=valido)
    righe = []
    for giorno, g in df.groupby("giorno", sort=True):
        buone = g[g["valido"]]
        if buone.empty:
            motivo = "; ".join(sorted({CODICI_NULL.get(int(c), "valore non utilizzabile") if pd.notna(c) else "codice assente"
                                       for c in codice.loc[g.index]}))
            for s in STATISTICHE:
                righe.append((id_station, giorno, s, np.nan, STATO_NULL, f"nessuna misura valida nel giorno ({motivo})"))
            continue
        ricostruite = int((codice.loc[buone.index] == 5).sum())
        nota = f"{len(buone)}/{attese} {unita} valide"
        if ricostruite:
            nota += f", di cui {ricostruite} ricostruite dalla fonte"
        if rete == RETE_DEDICATA:
            v = {"media": buone["temperatura_avg"].mean(), "massima": buone["temperatura_max"].max(),
                 "minima": buone["temperatura_min"].min()}
        else:
            v = {"media": buone["temperatura"].mean(), "massima": buone["temperatura"].max(), "minima": buone["temperatura"].min()}
        for s in STATISTICHE:
            righe.append((id_station, giorno, s, round(float(v[s]), 2), STATO_VALORE, f"temperatura {s} a 2 m (UTC+1), {nota}"))
    return pd.DataFrame(righe, columns=COLONNE_GIORNALIERE)
