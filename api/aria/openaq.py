#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client per l'API OpenAQ v3. Scheda completa del servizio (link, autenticazione,
licenze, copertura verificata per il Salento): data/dataset/aria/openaq/OpenAQ.md.

Seconda fonte per la pipeline multi-fonte di qualita' dell'aria (v. docs/Regole_dei_dati.md), indipendente da ARPA Puglia (api/aria/arpa_puglia.py). Dal 27/09/2026
ARPA copre da sola 2012->oggi (host old.arpa.puglia.it), quindi OpenAQ non
serve piu' a tappare buchi temporali: resta un riscontro indipendente sullo
stesso periodo (copertura reale OpenAQ: 2020-05-06->oggi). I valori delle due
fonti vanno tenuti separati per distretto/periodo/inquinante, non aggregati
(v. docs/Regole_dei_dati.md).

Richiede una API key gratuita (registrazione su explore.openaq.org/register),
passata come variabile d'ambiente OPENAQ_API_KEY (es. in un file .env in
root, gitignored - v. .gitignore). Nessuna chiave e' hardcoded qui.

Nessuna chiamata scrive su un database: solo richieste dirette alle fonti
pubbliche (v. docs/Architettura.md).
"""

import os
import time
from datetime import date, timedelta

import requests

BASE_URL = "https://api.openaq.org/v3"
TIMEOUT = 30
DIMENSIONE_PAGINA = 100  # massimo consigliato per /locations; /days puo' usare fino a 1000

# Bounding box che copre le tre province del Salento (Lecce, Brindisi,
# Taranto): minLon, minLat, maxLon, maxLat, WGS84. Volutamente largo (include
# un margine attorno ai confini reali): serve solo a interrogare /locations,
# il filtro preciso per distretto/comune va fatto sui risultati.
BBOX_SALENTO = "16.70,39.75,18.55,40.95"

# ID dei parametri OpenAQ per i 5 inquinanti di riferimento della dashboard
# (v. repository Frontend, docs/Specifiche_Design.md), verificati il
# 27/09/2026 via GET /v3/parameters. OpenAQ espone piu' id per lo stesso
# inquinante a seconda dell'unita' (mass in ug/m3, concentrazione in ppm/ppb):
# qui si sceglie sempre la variante in ug/m3, la stessa unita' usata da ARPA
# Puglia, per poter confrontare/unire le serie senza conversioni.
PARAMETRI_RIFERIMENTO = {
    "pm25": 2,
    "o3": 3,
    "co": 4,
    "no2": 5,
    "so2": 6,
}


class OpenAQError(RuntimeError):
    """Errore nella chiamata all'API OpenAQ."""


def _api_key():
    chiave = os.environ.get("OPENAQ_API_KEY")
    if not chiave:
        raise OpenAQError(
            "OPENAQ_API_KEY non impostata: registrati su "
            "explore.openaq.org/register e imposta la chiave come variabile "
            "d'ambiente (es. in un file .env in root, gia' in .gitignore)."
        )
    return chiave


def _get(path, **params):
    url = f"{BASE_URL}{path}"
    headers = {"X-API-Key": _api_key()}
    try:
        risposta = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise OpenAQError(f"Chiamata fallita: {url} ({exc})") from exc
    if risposta.status_code == 429:
        raise OpenAQError(
            "Rate limit OpenAQ superato (free tier: 60 richieste/minuto, "
            "2000/ora). Riprovare piu' tardi."
        )
    try:
        risposta.raise_for_status()
    except requests.HTTPError as exc:
        raise OpenAQError(f"OpenAQ ha risposto {risposta.status_code}: {risposta.text[:300]}") from exc
    # Controllo a monte del payload (v. docs/Regole_dei_dati.md): tutti gli endpoint
    # v3 usati qui rispondono con un oggetto JSON che contiene 'results'.
    try:
        corpo = risposta.json()
    except ValueError as exc:
        raise OpenAQError(f"Payload malformato da {url}: non è JSON ({risposta.text[:120]!r})") from exc
    if not isinstance(corpo, dict) or not isinstance(corpo.get("results"), list):
        raise OpenAQError(f"Payload malformato da {url}: manca l'elenco 'results'")
    return corpo


def get_parametri():
    """Anagrafica completa dei parametri OpenAQ (id, nome, unita' di misura)."""
    return _get("/parameters", limit=1000)["results"]


def get_stazioni_salento(parametri_id=None, pagina_singola=False):
    """Stazioni OpenAQ nel bounding box del Salento (LE+BR+TA).

    `parametri_id`: lista di id parametro per filtrare (default: nessun
    filtro, tutte le stazioni nel bbox). `pagina_singola=True` restituisce
    solo la prima pagina (utile per un controllo rapido)."""
    params = {"bbox": BBOX_SALENTO, "limit": DIMENSIONE_PAGINA}
    if parametri_id:
        params["parameters_id"] = ",".join(str(p) for p in parametri_id)

    stazioni = []
    pagina = 1
    while True:
        params["page"] = pagina
        corpo = _get("/locations", **params)
        stazioni.extend(corpo["results"])
        if pagina_singola or len(corpo["results"]) < DIMENSIONE_PAGINA:
            break
        pagina += 1
        time.sleep(1)  # margine sul rate limit (60 richieste/minuto)
    return stazioni


def get_orario_sensore(sensore_id, data_inizio, data_fine):
    """Valori orari per un singolo sensore tra data_inizio e data_fine
    (stringhe 'YYYY-MM-DD'). Serve dove la statistica ARPA non si ricava
    dall'aggregato giornaliero (es. CO: massimo della media mobile su 8 ore).

    Usa GET /v3/sensors/{id}/measurements (misure grezze, per queste stazioni
    orarie) e non /hours: il 27/09/2026 /hours andava in timeout (408) anche
    su 7 giorni, /measurements risponde in pochi secondi su un mese intero.
    datetime_to è un istante (mezzanotte): per includere data_fine si passa
    la mezzanotte del giorno dopo."""
    fine_esclusa = (date.fromisoformat(data_fine) + timedelta(days=1)).isoformat()
    righe = []
    pagina = 1
    while True:
        corpo = _get(
            f"/sensors/{sensore_id}/measurements",
            datetime_from=data_inizio,
            datetime_to=fine_esclusa,
            limit=1000,
            page=pagina,
        )
        righe.extend(corpo["results"])
        if len(corpo["results"]) < 1000:
            break
        pagina += 1
        time.sleep(1)
    return righe


def get_giornaliero_sensore(sensore_id, data_inizio, data_fine):
    """Aggregati giornalieri per un singolo sensore (un sensore = una
    stazione + un parametro), tra data_inizio e data_fine (stringhe
    'YYYY-MM-DD', incluse), via GET /v3/sensors/{id}/days."""
    righe = []
    pagina = 1
    while True:
        corpo = _get(
            f"/sensors/{sensore_id}/days",
            date_from=data_inizio,
            date_to=data_fine,
            limit=1000,
            page=pagina,
        )
        righe.extend(corpo["results"])
        if len(corpo["results"]) < 1000:
            break
        pagina += 1
        time.sleep(1)
    return righe
