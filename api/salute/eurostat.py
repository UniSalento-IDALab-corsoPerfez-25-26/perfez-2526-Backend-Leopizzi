#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client Eurostat per i decessi settimanali per provincia (NUTS 3), dataset
`demo_r_mwk3_t` (scheda: data/dataset/salute/eurostat/Eurostat.md).

Serve alla **validazione per ridondanza** del canale A di ISTAT (decessi comunali
giornalieri): Eurostat ridistribuisce i decessi che ISTAT gli trasmette, quindi la
somma settimanale dei decessi comunali per provincia deve coincidere. Payload di
pochi KB, nessuna chiave, nessuna registrazione.

Controllo a monte (docs/Regole_dei_dati.md): la risposta deve essere JSON-stat 2.0 con le
dimensioni attese; ogni cella si classifica subito in VALORE / NULL (le settimane
senza valore pubblicato restano fuori e diventano NO_DATA quando si costruisce la
griglia delle settimane del periodo).

Le settimane sono ISO (`2024-W23`), come la settimana ISO dei giorni ISTAT.
"""

import requests

import pandas as pd

from api.comune.stati import STATO_NO_DATA, STATO_NULL, STATO_VALORE

BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
DATASET_DECESSI = "demo_r_mwk3_t"
TIMEOUT = 120
# province del Salento: codice NUTS 3 Eurostat -> id dell'anagrafica territorio
NUTS_SALENTO = {"ITF43": "TA", "ITF44": "BR", "ITF45": "LE"}
INTESTAZIONI = {"User-Agent": "Mozilla/5.0 (OneHealth; ricerca universitaria)"}


class EurostatError(RuntimeError):
    """Errore nella chiamata a Eurostat o risposta con struttura inattesa."""


def _chiama(dataset, parametri):
    url = f"{BASE}/{dataset}"
    try:
        risposta = requests.get(url, params=parametri, timeout=TIMEOUT, headers=INTESTAZIONI)
    except requests.RequestException as exc:
        raise EurostatError(f"Eurostat non raggiungibile: {url} ({exc})") from exc
    if risposta.status_code != 200:
        raise EurostatError(f"Eurostat ha risposto {risposta.status_code} a {url} ({parametri})")
    try:
        dati = risposta.json()
    except ValueError as exc:
        raise EurostatError(f"risposta non JSON da {url}: {exc}") from exc
    if "value" not in dati or "dimension" not in dati or "id" not in dati or "size" not in dati:
        raise EurostatError(f"risposta non in formato JSON-stat 2.0 (chiavi: {sorted(dati)[:8]})")
    return dati


def _celle(dati):
    """Righe {dimensione: categoria, 'valore': numero|None} da una risposta JSON-stat 2.0.

    I valori stanno in un dizionario indicizzato sulla posizione nell'array appiattito:
    la posizione si decodifica a radice mista con le dimensioni dichiarate in `size`."""
    dimensioni, dimensioni_size = dati["id"], dati["size"]
    if len(dimensioni) != len(dimensioni_size):
        raise EurostatError("dimensioni e size di lunghezza diversa nella risposta")
    categorie = []
    for d in dimensioni:
        indice = dati["dimension"][d]["category"]["index"]
        if isinstance(indice, dict):  # {codice: posizione}
            categorie.append([c for c, _ in sorted(indice.items(), key=lambda kv: kv[1])])
        else:  # già una lista ordinata
            categorie.append(list(indice))
    passi = [1] * len(dimensioni_size)
    for i in range(len(dimensioni_size) - 2, -1, -1):
        passi[i] = passi[i + 1] * dimensioni_size[i + 1]
    righe = []
    for posizione, valore in dati["value"].items():
        resto = int(posizione)
        riga = {}
        for i, d in enumerate(dimensioni):
            riga[d], resto = categorie[i][resto // passi[i]], resto % passi[i]
        riga["valore"] = valore
        righe.append(riga)
    return righe


def decessi_settimanali(nuts=None, da_settimana=None, a_settimana=None):
    """Decessi per provincia e settimana ISO da `demo_r_mwk3_t`.

    `nuts`: codici NUTS 3 (default: le tre province del Salento); `da_settimana` e
    `a_settimana`: settimane ISO `AAAA-Wss` per ritagliare il periodo (il filtro `time`
    di Eurostat accetta un elenco di periodi, quindi il taglio si fa qui dopo la
    risposta: la serie intera è comunque di pochi KB).

    Restituisce un DataFrame id_provincia, settimana, decessi, stato, nota: una riga
    per ogni settimana restituita da Eurostat. Le settimane presenti ma senza valore
    (pubblicazione in ritardo) sono `NULL`; quelle fuori dalla serie non compaiono e
    diventano `NO_DATA` quando si costruisce la griglia (v. `griglia_settimane`).
    """
    codici = list(nuts or NUTS_SALENTO)
    dati = _chiama(DATASET_DECESSI, [("format", "JSON"), ("lang", "en")] + [("geo", c) for c in codici])
    righe = []
    for cella in _celle(dati):
        provincia = NUTS_SALENTO.get(cella.get("geo"), cella.get("geo"))
        settimana = cella.get("time")
        if settimana is None:
            raise EurostatError("risposta senza dimensione `time`")
        valore = cella["valore"]
        if valore is None:
            righe.append({"id_provincia": provincia, "settimana": settimana, "decessi": None,
                          "stato": STATO_NULL, "nota": "settimana nella serie ma senza valore pubblicato"})
            continue
        try:
            numero = int(valore)
        except (TypeError, ValueError):
            righe.append({"id_provincia": provincia, "settimana": settimana, "decessi": None,
                          "stato": STATO_NULL, "nota": f"valore non numerico: {valore!r}"})
            continue
        if numero < 0:
            righe.append({"id_provincia": provincia, "settimana": settimana, "decessi": None,
                          "stato": STATO_NULL, "nota": f"valore negativo: {numero}"})
            continue
        righe.append({"id_provincia": provincia, "settimana": settimana, "decessi": numero,
                      "stato": STATO_VALORE, "nota": None})
    df = pd.DataFrame(righe, columns=["id_provincia", "settimana", "decessi", "stato", "nota"])
    # le settimane di Eurostat sono ISO: l'ordinamento alfabetico è anche cronologico
    if da_settimana:
        df = df[df["settimana"] >= da_settimana]
    if a_settimana:
        df = df[df["settimana"] <= a_settimana]
    df = df.sort_values(["id_provincia", "settimana"]).reset_index(drop=True)
    df.attrs["dataset"] = DATASET_DECESSI
    df.attrs["aggiornato_il"] = dati.get("updated")
    return df


def griglia_settimane(df, province, da_settimana, a_settimana):
    """Completa la serie con le settimane del periodo che Eurostat non restituisce
    affatto: diventano `NO_DATA` (la fonte non copre), non celle vuote."""
    settimane = sorted(set(df["settimana"]) | _settimane_iso(da_settimana, a_settimana))
    settimane = [s for s in settimane if da_settimana <= s <= a_settimana]
    completa = pd.MultiIndex.from_product([sorted(province), settimane],
                                          names=["id_provincia", "settimana"]).to_frame(index=False)
    out = completa.merge(df, on=["id_provincia", "settimana"], how="left")
    manca = out["stato"].isna()
    out.loc[manca, "stato"] = STATO_NO_DATA
    out.loc[manca, "nota"] = "settimana non presente nella serie Eurostat"
    return out


def _settimane_iso(da_settimana, a_settimana):
    """Settimane ISO da `AAAA-Wss` a `AAAA-Wss` comprese (per la griglia)."""
    def parti(s):
        anno, settimana = s.split("-W")
        return int(anno), int(settimana)

    (anno_a, sett_a), (anno_b, sett_b) = parti(da_settimana), parti(a_settimana)
    fuori = []
    for anno in range(anno_a, anno_b + 1):
        ultima = pd.Timestamp(year=anno, month=12, day=28).isocalendar()[1]  # il 28/12 è sempre nell'ultima ISO
        for settimana in range(1, int(ultima) + 1):
            etichetta = f"{anno}-W{settimana:02d}"
            if (anno, settimana) >= (anno_a, sett_a) and (anno, settimana) <= (anno_b, sett_b):
                fuori.append(etichetta)
    return set(fuori)
