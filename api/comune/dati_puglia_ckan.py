#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client generico per l'API CKAN del portale Open Data della Regione Puglia
(dati.puglia.it), usata per interrogare i dataset "datastore" (tabellari)
pubblicati sul portale.

A differenza delle API di interoperabilità dirette di ARPA Puglia
(cloud.arpa.puglia.it, v. api/aria/arpa_puglia.py), alcuni dataset ARPA sono
mirrorati/caricati anche qui: quando lo sono (`datastore_active: true` in
un resource_show), sono interrogabili con questo client senza dipendere
dalla disponibilità di cloud.arpa.puglia.it.

Riferimento API CKAN: https://docs.ckan.org/en/latest/maintaining/datastore.html
"""

import json

import requests

BASE_URL = "https://dati.puglia.it/ckan/api/3/action"
TIMEOUT = 30
DIMENSIONE_PAGINA = 1000  # righe per chiamata, per paginare risultati grandi


class CkanError(RuntimeError):
    """Errore nella chiamata alle API CKAN di dati.puglia.it."""


def _action(nome_azione, **params):
    url = f"{BASE_URL}/{nome_azione}"
    try:
        risposta = requests.get(url, params=params, timeout=TIMEOUT)
        risposta.raise_for_status()
    except requests.RequestException as exc:
        raise CkanError(f"Chiamata fallita: {url} ({exc})") from exc
    # Controllo a monte del payload (v. docs/Regole_dei_dati.md): un errore del
    # portale può arrivare come pagina HTML con HTTP 200.
    try:
        corpo = risposta.json()
    except ValueError as exc:
        raise CkanError(f"Payload malformato da {url}: non è JSON ({risposta.text[:120]!r})") from exc
    if not isinstance(corpo, dict) or not corpo.get("success"):
        errore = corpo.get("error") if isinstance(corpo, dict) else corpo
        raise CkanError(f"API CKAN ha risposto con errore: {errore}")
    if "result" not in corpo:
        raise CkanError(f"Payload malformato da {url}: manca 'result'")
    return corpo["result"]


def datastore_search(resource_id, filters=None, q=None, fields=None, limit=100, offset=0):
    """Una singola pagina di datastore_search.

    `filters` è un dict {campo: valore} per un match esatto; il valore può
    essere una lista per un match "IN" (es. {"provincia": ["Lecce", "Taranto"]}).
    """
    params = {"resource_id": resource_id, "limit": limit, "offset": offset}
    if filters is not None:
        params["filters"] = json.dumps(filters, ensure_ascii=False)
    if q is not None:
        params["q"] = q
    if fields is not None:
        params["fields"] = ",".join(fields)
    return _action("datastore_search", **params)


def datastore_search_tutti(resource_id, filters=None, q=None, fields=None):
    """Scarica tutte le righe di una risorsa (o del sottoinsieme filtrato),
    paginando automaticamente. Da usare con giudizio: su una risorsa grande
    senza filtro richiede molte chiamate."""
    righe = []
    offset = 0
    totale = None
    while totale is None or offset < totale:
        pagina = datastore_search(
            resource_id, filters=filters, q=q, fields=fields,
            limit=DIMENSIONE_PAGINA, offset=offset,
        )
        if not isinstance(pagina.get("records"), list) or not isinstance(pagina.get("total"), int):
            raise CkanError(f"Payload malformato da datastore_search ({resource_id}): mancano 'records' o 'total'")
        righe.extend(pagina["records"])
        totale = pagina["total"]
        offset += DIMENSIONE_PAGINA
    return righe
