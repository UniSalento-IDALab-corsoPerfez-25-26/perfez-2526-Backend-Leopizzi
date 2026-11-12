#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client per i dati di qualità dell'aria di ARPA Puglia.

Le API "ufficiali" documentate (dominio cloud.arpa.puglia.it, v.
data/dataset/aria/arpa_puglia/API_ARPA.pdf) sono risultate IRRAGGIUNGIBILI
(timeout) in più tentativi il 27/09/2026, sia dall'ambiente di sviluppo sia
dalla rete dell'autore.

Lo stesso contratto (stessi campi, stessi parametri: measurement_date, year,
month, id_station, network, format...) è però raggiungibile su un dominio
"legacy" con lo stesso backend, trovato per tentativi il 27/09/2026 (NON
documentato ufficialmente da nessuna guida ARPA in nostro possesso — usare
con questa consapevolezza, e ricontrollare periodicamente se cloud.arpa.puglia.it
torna raggiungibile):

  http://old.arpa.puglia.it/ARPA_ARIA/dati.jsp         ~ QualitaAria
  http://old.arpa.puglia.it/ARPA_ARIA/centraline.jsp   ~ QualitaAria/Stations
  http://old.arpa.puglia.it/ARPA_ARIA/inquinanti.jsp   ~ QualitaAria/Pollutants

Copertura verificata il 27/09/2026 (valori non-null, non solo HTTP 200):
2012 -> oggi (aggiornato quotidianamente: la chiamata senza measurement_date
restituisce il giorno precedente). Nessun limite noto simile al 2021 del
servizio documentato.

Il mirror CKAN su dati.puglia.it (client in api/comune/dati_puglia_ckan.py)
resta nel repo e i dati 2023 già scaricati
(data/raw/aria/arpa_puglia/qualita_aria_2023_salento.json, v.
scripts/aria/scarica_qualita_aria_2023.py) restano un riscontro indipendente
per quell'anno, ma non è più la fonte primaria: copriva solo il 2023.

Nessuna chiamata scrive su un database: solo richieste dirette alle fonti
pubbliche (v. docs/Architettura.md). Chi usa questo modulo per generare
report può salvare le risposte grezze sotto data/raw/aria/ (gitignored) per
non ripetere chiamate lente.
"""

import csv
import io
import json
import math
import time
from datetime import date as _date, timedelta

import requests

from api.comune.dati_puglia_ckan import datastore_search_tutti
from api.comune.distretti_salento import stazioni_per_distretto, carica_distretti
# gli stati sono condivisi da aria, salute e calore (api/comune/stati.py) e si
# ri-esportano da qui, dove li importa il resto del codice dell'aria
from api.comune.stati import STATO_NO_DATA, STATO_NULL, STATO_VALORE  # noqa: F401

BASE_URL = "http://old.arpa.puglia.it/ARPA_ARIA"
TIMEOUT = 60  # un mese intero, tutta la Puglia, ha impiegato ~12s il 27/09/2026; margine ampio

PROVINCE_SALENTO = ["Lecce", "Brindisi", "Taranto"]


class ArpaPugliaError(RuntimeError):
    """Errore nella chiamata ai dati di ARPA Puglia (host legacy)."""


TENTATIVI = 3  # l'host a volte chiude la connessione (osservato il 27/09/2026, 1 volta su ~10)


def _get(pagina, params=None):
    url = f"{BASE_URL}/{pagina}"
    for tentativo in range(1, TENTATIVI + 1):
        try:
            risposta = requests.get(url, params=params, timeout=TIMEOUT)
            risposta.raise_for_status()
            return risposta
        except requests.RequestException as exc:
            if tentativo == TENTATIVI:
                raise ArpaPugliaError(f"Chiamata fallita dopo {TENTATIVI} tentativi: {url} ({exc})") from exc
            time.sleep(2 * tentativo)


# ---------------------------------------------------------------------------
# Controllo a monte delle risposte (v. docs/Regole_dei_dati.md): subito dopo ogni
# risposta si verifica che il payload abbia la struttura attesa (altrimenti
# ArpaPugliaError) e si classifica ogni valore in VALORE / NULL. Lo stato
# NO_DATA (la fonte non copre la combinazione) non si decide qui ma quando si
# costruisce la griglia del dataset, perché dipende da cosa manca, non da cosa
# è arrivato.
# ---------------------------------------------------------------------------

CAMPI_MISURAZIONI = {
    "data_di_misurazione", "id_station", "denominazione", "comune", "provincia",
    "inquinante_misurato", "valore_inquinante_misurato",
}
CAMPI_INQUINANTI = {"sigla", "unita_misura"}

_TOKEN_NULL = {"", "null", "none", "nan", "n/a", "-"}


class RispostaArpa(list):
    """Righe di misurazione già controllate. Si usa come una lista; in più
    `anomalie` elenca le righe scartate perché malformate (campi chiave
    mancanti o data non valida), una descrizione per riga."""

    def __init__(self, righe=(), anomalie=None):
        super().__init__(righe)
        self.anomalie = list(anomalie or [])


def _csv_a_dizionari(testo, campi_attesi, origine):
    lettore = csv.DictReader(io.StringIO(testo))
    mancanti = set(campi_attesi) - set(lettore.fieldnames or [])
    if mancanti:
        inizio = testo[:120].replace("\n", " ")
        raise ArpaPugliaError(
            f"Payload malformato da {origine}: colonne mancanti {sorted(mancanti)} "
            f"(inizio risposta: {inizio!r})"
        )
    return list(lettore)


def classifica_valore(grezzo):
    """(valore, stato, nota) per un valore di concentrazione così come
    arriva dalla fonte: VALORE se è un numero finito e non negativo,
    altrimenti NULL con il motivo."""
    if grezzo is None or str(grezzo).strip().lower() in _TOKEN_NULL:
        return None, STATO_NULL, "valore null dalla fonte"
    try:
        valore = float(str(grezzo).strip().replace(",", "."))
    except ValueError:
        return None, STATO_NULL, f"valore non numerico dalla fonte: {grezzo!r}"
    if not math.isfinite(valore):
        return None, STATO_NULL, f"valore non finito dalla fonte: {grezzo!r}"
    if valore < 0:
        return None, STATO_NULL, f"valore negativo dalla fonte: {valore:g}"
    return valore, STATO_VALORE, None


def _controlla_misurazioni(righe, origine):
    """Normalizza, classifica e deduplica le righe di misurazione.

    - Tipi incoerenti tra mesi (id_station intero o stringa, date con o senza
      orario, osservati il 27/09/2026) vengono uniformati.
    - Righe senza stazione, inquinante o data valida vengono scartate e
      riportate in `anomalie`.
    - Ogni riga riceve `valore` (float o None), `stato` (VALORE/NULL), `nota`.
    - Più righe per la stessa stazione/giorno/inquinante (la sorgente ne
      contiene di duplicate, es. PM10 di Arnesano ripetuto 5 volte): se i
      valori validi coincidono se ne tiene una; se sono diversi la cella è
      NULL ("valori discordanti"); se una è valida e le altre null vale
      quella valida.
    """
    if righe:
        mancanti = CAMPI_MISURAZIONI - set(righe[0])
        if mancanti:
            raise ArpaPugliaError(f"Payload malformato da {origine}: campi mancanti {sorted(mancanti)}")

    anomalie = []
    gruppi = {}
    for r in righe:
        id_station = str(r.get("id_station") or "").strip()
        inquinante = str(r.get("inquinante_misurato") or "").strip()
        data = str(r.get("data_di_misurazione") or "")[:10]
        try:
            _date.fromisoformat(data)
        except ValueError:
            data = None
        if data is None or id_station.lower() in _TOKEN_NULL or inquinante.lower() in _TOKEN_NULL:
            chiave = {k: r.get(k) for k in ("data_di_misurazione", "id_station", "inquinante_misurato")}
            anomalie.append(f"{origine}: riga scartata (stazione, inquinante o data mancanti/non validi): {chiave}")
            continue
        r["id_station"], r["inquinante_misurato"], r["data_di_misurazione"] = id_station, inquinante, data
        r["valore"], r["stato"], r["nota"] = classifica_valore(r.get("valore_inquinante_misurato"))
        gruppi.setdefault((id_station, data, inquinante), []).append(r)

    risultato = RispostaArpa(anomalie=anomalie)
    for gruppo in gruppi.values():
        validi = sorted({g["valore"] for g in gruppo if g["stato"] == STATO_VALORE})
        if len(validi) > 1:
            riga = dict(
                gruppo[0], valore=None, stato=STATO_NULL,
                nota="valori discordanti dalla fonte: " + ", ".join(f"{v:g}" for v in validi),
            )
        elif validi:
            riga = next(g for g in gruppo if g["stato"] == STATO_VALORE)
        else:
            riga = gruppo[0]
        risultato.append(riga)
    return risultato


def _filtra_province(righe, province):
    if not province:
        return righe
    province = set(province)
    return [r for r in righe if r.get("provincia") in province]


# ---------------------------------------------------------------------------
# Inquinanti monitorati (anagrafica statica, con limiti ufficiali)
# ---------------------------------------------------------------------------


def get_inquinanti():
    """Elenco degli inquinanti monitorati da ARPA Puglia, con periodo di
    misurazione, valore limite, soglia di allarme e unità di misura
    ufficiali (10 inquinanti verificati il 27/09/2026)."""
    return _csv_a_dizionari(_get("inquinanti.jsp").text, CAMPI_INQUINANTI, "inquinanti.jsp")


# ---------------------------------------------------------------------------
# Stazioni di monitoraggio
# ---------------------------------------------------------------------------


def get_stazioni():
    """Anagrafica completa delle stazioni ARPA (GeoJSON, tutta la Puglia,
    incluse le foto delle centraline in base64: risposta di alcuni MB).
    Usata per rigenerare data/dataset/aria/arpa_puglia/stazioni_di_monitoraggio.json
    (v. scripts/aria/aggiorna_stazioni_arpa.py); per l'uso quotidiano preferire
    quel file già scaricato, via api/comune/distretti_salento.py."""
    testo = _get("centraline.jsp").text
    try:
        geojson = json.loads(testo)
    except ValueError as exc:
        raise ArpaPugliaError(f"Payload malformato da centraline.jsp: non è JSON ({exc})") from exc
    if not isinstance(geojson.get("features"), list):
        raise ArpaPugliaError("Payload malformato da centraline.jsp: manca l'elenco 'features'")
    return geojson


# ---------------------------------------------------------------------------
# Monitoraggi giornalieri. Ogni riga restituita ha, oltre ai campi della
# fonte, `valore` (float o None), `stato` (VALORE/NULL) e `nota`; il risultato
# è una RispostaArpa, con le righe scartate in `.anomalie`.
# ---------------------------------------------------------------------------


def get_qualita_aria_giorno(data, province=PROVINCE_SALENTO):
    """Monitoraggi di qualità dell'aria per un singolo giorno (oggetto date
    o stringa 'YYYY-MM-DD'; se omesso, ARPA restituisce il giorno precedente
    a oggi). Filtra per provincia (default: le tre del Salento)."""
    data = _a_data(data) if data is not None else None
    params = {}
    if data is not None:
        params["measurement_date"] = data.strftime("%d/%m/%Y")
    origine = f"dati.jsp {params or 'ultimo giorno'}"
    righe = _csv_a_dizionari(_get("dati.jsp", params or None).text, CAMPI_MISURAZIONI, origine)
    return _controlla_misurazioni(_filtra_province(righe, province), origine)


def get_qualita_aria_mensile(anno, mese, province=PROVINCE_SALENTO):
    """Monitoraggi giornalieri di qualità dell'aria per un mese/anno
    qualsiasi (non solo 2023, a differenza della variante CKAN qui sotto).
    Filtra per provincia (default: le tre del Salento), controlla e
    deduplica. Fonte primaria: old.arpa.puglia.it."""
    if not (1 <= mese <= 12):
        raise ValueError("mese deve essere un intero 1-12")
    origine = f"dati.jsp {anno}-{mese:02d}"
    righe = _csv_a_dizionari(_get("dati.jsp", {"year": anno, "month": mese}).text, CAMPI_MISURAZIONI, origine)
    return _controlla_misurazioni(_filtra_province(righe, province), origine)


# ---------------------------------------------------------------------------
# Variante CKAN (dati.puglia.it), solo 2023: non più la fonte primaria (v.
# sopra), ma tenuta come riscontro indipendente — una fonte diversa da
# old.arpa.puglia.it per lo stesso anno, utile a validare in tesi che le due
# concordino. Usata da scripts/aria/scarica_qualita_aria_2023.py.
# ---------------------------------------------------------------------------

RISORSE_CKAN_2023 = {
    1: "0e63c4c7-79d4-4dc5-9443-76b6c650f124",
    2: "d675a187-e4bc-4155-ae5a-c5a103a5981c",
    3: "a832f74f-ee8e-4934-841d-d21c5899318a",
    4: "0abe5e66-94cc-4bd3-9806-a4bd466d505a",
    5: "34807aa7-1b42-44e8-935c-8bc5291a9196",
    6: "8a4a59ac-cf34-4315-ab43-c05bdb0e1317",
    7: "504c1f94-fed3-4994-8895-38df59928800",
    8: "a56e2e01-dd21-4875-9954-7d5acfb5c8a9",
    9: "e66e99f6-769a-4cb6-8ae6-59b6040e7661",
    10: "69b0951e-6d48-4a00-9d08-fd38209b6aae",
    11: "cc9c173a-a199-47e5-9ec7-5e8746cbd774",
    12: "80190494-5a47-4229-9df3-eff9af5d0213",
}


def get_qualita_aria_mensile_2023_ckan(mese, province=PROVINCE_SALENTO):
    """Come get_qualita_aria_mensile(2023, mese), ma dal mirror CKAN su
    dati.puglia.it invece che da old.arpa.puglia.it: stessa deduplica e
    normalizzazione, fonte indipendente per lo stesso anno."""
    if mese not in RISORSE_CKAN_2023:
        raise ValueError("mese deve essere un intero 1-12")
    filtri = {"provincia": list(province)} if province else None
    righe = datastore_search_tutti(RISORSE_CKAN_2023[mese], filters=filtri)
    return _controlla_misurazioni(righe, f"CKAN dati-qualita-aria-2023 mese {mese:02d}")



# ---------------------------------------------------------------------------
# "Endpoint": monitoraggi per un elenco di distretti e un periodo di date.
# ---------------------------------------------------------------------------


def _a_data(valore):
    if isinstance(valore, _date):
        return valore
    return _date.fromisoformat(str(valore))


def _mesi_nel_periodo(data_inizio, data_fine):
    mesi = set()
    anno, mese = data_inizio.year, data_inizio.month
    while (anno, mese) <= (data_fine.year, data_fine.month):
        mesi.add((anno, mese))
        anno, mese = (anno + 1, 1) if mese == 12 else (anno, mese + 1)
    return sorted(mesi)


def get_qualita_aria_periodo(distretti, data_inizio, data_fine):
    """Tutti i monitoraggi di qualità dell'aria per un elenco di distretti
    socio-sanitari del Salento (es. ["LE-53", "TA-08"]), in un intervallo di
    date [data_inizio, data_fine] incluso (oggetti date o stringhe 'YYYY-MM-DD').

    Ogni riga del risultato include id_distretto e denominazione_distretto,
    oltre ai campi originali del monitoraggio (stazione, inquinante, valore,
    limite, indice/classe di qualità...).

    Solleva ValueError se:
    - un id_distretto non esiste (v. distretti_salento.stazioni_per_distretto);
    - data_fine è nel futuro (il dato di "ieri" è il più recente disponibile).
    """
    data_inizio = _a_data(data_inizio)
    data_fine = _a_data(data_fine)
    if data_inizio > data_fine:
        raise ValueError("data_inizio deve precedere (o coincidere con) data_fine")
    ieri = _date.today() - timedelta(days=1)
    if data_fine > ieri:
        raise ValueError(
            f"data_fine ({data_fine.isoformat()}) è nel futuro: il dato più recente "
            f"disponibile è quello di ieri ({ieri.isoformat()})"
        )

    per_distretto = stazioni_per_distretto(distretti)  # solleva ValueError se un id non esiste
    id_stazione_a_distretto = {
        s["id_station"]: id_distretto for id_distretto, stazioni in per_distretto.items() for s in stazioni
    }
    if not id_stazione_a_distretto:
        return []  # nessuna stazione nei distretti richiesti (es. tutti "non coperti")

    denominazioni = {d["id_distretto"]: d["denominazione"] for d in carica_distretti() if d["id_distretto"] in per_distretto}

    righe = []
    for anno, mese in _mesi_nel_periodo(data_inizio, data_fine):
        for r in get_qualita_aria_mensile(anno, mese):
            if r["id_station"] not in id_stazione_a_distretto:
                continue
            data_riga = _date.fromisoformat(r["data_di_misurazione"])
            if not (data_inizio <= data_riga <= data_fine):
                continue
            id_distretto = id_stazione_a_distretto[r["id_station"]]
            righe.append(
                {
                    **r,
                    "id_distretto": id_distretto,
                    "denominazione_distretto": denominazioni[id_distretto],
                }
            )

    return righe
