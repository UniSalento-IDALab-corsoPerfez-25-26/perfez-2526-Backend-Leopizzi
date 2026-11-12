#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aggregazione delle celle dei dataset da una zona/grana alla successiva.
Condiviso da aria, salute e calore: i dataset restano **non aggregati** (un
valore per fonte, stazione e giorno, v. docs/Regole_dei_dati.md), l'aggregazione si fa
solo per la mappa, per le analisi e per il confronto fra domini.

Decisioni del 02/10/2026 (docs/Regole_dei_dati.md):

- **stazione → comune** (solo mappa e analisi su un comune): media delle
  **stazioni fisiche** con `VALORE`. Le stazioni virtuali (CAMS, una per comune)
  non entrano nella media: restano una serie a parte, perché sono dato modellato.
- **comune → distretto**: **media pesata sui residenti** dei comuni con `VALORE`
  per le grandezze intensive (concentrazioni, temperature); **somma** per i
  conteggi (decessi, ricoveri), dove la media non avrebbe senso.
- **grana del confronto fra domini**: aria, salute e calore si confrontano alla
  grana minima comune a tutti e tre, oggi **distretto × mese** (l'aria resta
  giornaliera per comune nel dataset, la salute e il calore si presentano a
  distretto × mese anche per la privacy, v. docs/Regole_dei_dati.md).

Gli stati si propagano così, a ogni livello:
  `VALORE`  — almeno una zona/stazione figlia ha un valore (la nota dice quante);
  `NULL`    — nessun valore, ma almeno una figlia copre la cella;
  `NO_DATA` — nessuna figlia copre la cella.
"""

import pandas as pd

from api.comune.anagrafiche import FILE_ANAGRAFICHE, leggi_anagrafica
from api.comune.stati import STATO_NO_DATA, STATO_NULL, STATO_VALORE

CHIAVI_ARIA = ["fonte", "inquinante"]  # dimensioni che restano accanto a zona e tempo

# Note strutturali: dicono che una zona non ha (e non avrà, cambiando periodo) stazioni fisiche,
# a differenza di un buco temporale. Si propagano salendo di grana (v. _nota_uniforme).
NOTA_COMUNE_SENZA_STAZIONI = "nessuna stazione fisica nel comune"
NOTA_DISTRETTO_SENZA_STAZIONI = "nessuna stazione fisica nel distretto"


def _plurale(n, singolare, plurale):
    return f"{n} {singolare if n == 1 else plurale}"


def _nota_uniforme(d, chiave):
    """Per ogni gruppo di `chiave`: la nota delle sue celle `NO_DATA` se è la stessa per tutte, altrimenti
    None. Serve a non perdere il **motivo** di un vuoto salendo di grana: un comune senza stazioni resta
    "nessuna stazione fisica nel comune" anche a mese o a finestra, invece di diventare un generico
    "nessun giorno coperto", che fa pensare a un buco temporale (decisione del 14/10/2026)."""
    if "nota" not in d.columns:
        return None
    nd = d[d["stato"] == STATO_NO_DATA]
    if nd.empty:
        return None
    return nd.groupby(chiave, dropna=False)["nota"].agg(
        lambda s: s.iloc[0] if s.notna().all() and s.nunique() == 1 else None)


def _testo(x, ripiego):
    """`x` se è una nota non vuota, altrimenti `ripiego` (NaN e None compresi)."""
    return x if isinstance(x, str) and x else ripiego


def carica_pesi_comuni():
    """{id_comune: (id_distretto, residenti)} dall'anagrafica del territorio."""
    _, _, tabelle = leggi_anagrafica(FILE_ANAGRAFICHE["territorio"])
    return {c["id_comune"]: (c["id_distretto"], c["residenti"] or 0) for c in tabelle["comuni"]}


def _stati(gruppi, valori, descrizione_valore, descrizione_null, descrizione_no_data):
    """Assembla valore/stato/nota per ogni cella aggregata.

    `gruppi`: DataFrame indicizzato sulla chiave della cella con le colonne
    `figlie` (quante zone/stazioni figlie), `coperte` (quante non sono NO_DATA) e
    `con_valore`; `valori`: Serie del valore aggregato (NaN dove non c'è)."""
    out = gruppi.copy()
    out["valore"] = valori
    con_valore = out["con_valore"] > 0
    coperte = out["coperte"] > 0
    out["stato"] = pd.Series(STATO_NO_DATA, index=out.index, dtype=object)
    out.loc[coperte, "stato"] = STATO_NULL
    out.loc[con_valore, "stato"] = STATO_VALORE
    out.loc[~con_valore, "valore"] = float("nan")
    out["nota"] = [
        descrizione_valore(r) if r.stato == STATO_VALORE
        else descrizione_null(r) if r.stato == STATO_NULL
        else descrizione_no_data(r)
        for r in out.itertuples()
    ]
    return out.reset_index()


def media_per_comune(griglia, escludi_stazioni=(), chiavi=CHIAVI_ARIA, soglie_plausibilita=None, colonna_soglia="inquinante"):
    """Media delle stazioni fisiche di ogni comune, per giorno e per `chiavi`.

    `griglia`: celle del dataset aria (colonne comune, stazione, giorno, valore,
    stato + `chiavi`), **tutte**, non solo quelle con `VALORE`: servono anche le
    altre per distinguere `NULL` da `NO_DATA`.
    `escludi_stazioni`: chiavi di stazione da non considerare — le stazioni
    fittizie dei comuni senza stazioni e le stazioni virtuali di CAMS, che sono
    dato modellato e vanno tenute come serie a parte (docs/Regole_dei_dati.md).
    `soglie_plausibilita`: {valore di `colonna_soglia`: massimo plausibile}. Una
    cella di una stazione fisica che lo supera **non entra nella media del
    comune** (diventa NULL solo ai fini di questo calcolo: il valore originale
    resta intatto nel dataset per-fonte, "niente filtri silenziosi" — v. docs/Regole_dei_dati.md;
    caso OpenAQ Torchiarolo del 02/10/2026, chiuso il 14/10/2026). `None`
    (default) non filtra nulla.
    """
    g = griglia[~griglia["stazione"].isin(set(escludi_stazioni))]
    chiave = ["comune", "giorno", *chiavi]
    if g.empty:
        return pd.DataFrame(columns=chiave + ["valore", "stato", "nota", "stazioni", "stazioni_con_valore"])
    if soglie_plausibilita and colonna_soglia in g.columns:
        soglia = g[colonna_soglia].map(soglie_plausibilita)
        implausibile = (g["stato"] == STATO_VALORE) & soglia.notna() & (g["valore"] > soglia)
        if implausibile.any():
            g = g.copy()
            g.loc[implausibile, ["stato", "valore"]] = STATO_NULL, float("nan")
    gruppi = g.groupby(chiave, dropna=False).agg(
        figlie=("stazione", "nunique"),
        coperte=("stato", lambda s: (s != STATO_NO_DATA).sum()),
        con_valore=("stato", lambda s: (s == STATO_VALORE).sum()),
    )
    medie = g[g["stato"] == STATO_VALORE].groupby(chiave, dropna=False)["valore"].mean()
    out = _stati(
        gruppi, medie,
        lambda r: f"media di {_plurale(r.con_valore, 'stazione fisica', 'stazioni fisiche')} su {r.figlie} del comune",
        lambda r: f"{_plurale(r.coperte, 'stazione copre', 'stazioni coprono')} la cella, nessuna con un valore"
                  + (" (o superava la soglia di plausibilità)" if soglie_plausibilita else ""),
        lambda _: "nessuna stazione fisica copre la cella",
    )
    return out.rename(columns={"figlie": "stazioni", "con_valore": "stazioni_con_valore"}).drop(columns="coperte")


def media_per_distretto(per_comune, pesi=None, colonna_tempo="giorno", chiavi=CHIAVI_ARIA):
    """Media **pesata sui residenti** dei comuni con `VALORE`, per distretto.

    Regola per le grandezze intensive (concentrazioni, temperature): un comune di
    100.000 abitanti non può pesare come uno di 1.000. Per i conteggi si usa
    `somma_per_distretto`. `per_comune`: celle a grana comune (colonne comune,
    `colonna_tempo`, valore, stato + `chiavi`); `pesi`: {id_comune: (id_distretto,
    residenti)}, per default dall'anagrafica del territorio.
    """
    pesi = pesi or carica_pesi_comuni()
    d = per_comune.copy()
    d["distretto"] = d["comune"].map(lambda c: pesi.get(c, (None, 0))[0])
    d["residenti"] = d["comune"].map(lambda c: pesi.get(c, (None, 0))[1]).astype(float)
    chiave = ["distretto", colonna_tempo, *chiavi]
    if d.empty:
        return pd.DataFrame(columns=chiave + ["valore", "stato", "nota", "comuni", "comuni_con_valore",
                                              "quota_residenti"])
    gruppi = d.groupby(chiave, dropna=False).agg(
        figlie=("comune", "nunique"),
        coperte=("stato", lambda s: (s != STATO_NO_DATA).sum()),
        con_valore=("stato", lambda s: (s == STATO_VALORE).sum()),
        residenti_totali=("residenti", "sum"),
    )
    validi = d[d["stato"] == STATO_VALORE]
    # nessun comune con un valore (es. ARPA meteo in un mese senza dati): apply() su un gruppo vuoto darebbe un
    # DataFrame, non una Serie, e _stati non saprebbe assegnarlo
    medie = (pd.Series(dtype=float) if validi.empty else
             validi.assign(_p=validi["valore"] * validi["residenti"]).groupby(chiave, dropna=False)
             .apply(lambda x: x["_p"].sum() / x["residenti"].sum() if x["residenti"].sum() else float("nan"),
                    include_groups=False))
    residenti_coperti = validi.groupby(chiave, dropna=False)["residenti"].sum()
    gruppi["quota_residenti"] = (residenti_coperti / gruppi["residenti_totali"]).fillna(0.0)
    gruppi["nota_no_data"] = _nota_uniforme(d, chiave)
    out = _stati(
        gruppi, medie,
        lambda r: (f"media pesata sui residenti di {_plurale(r.con_valore, 'comune', 'comuni')} su {r.figlie} "
                   f"({r.quota_residenti:.0%} dei residenti del distretto)"),
        lambda r: f"{_plurale(r.coperte, 'comune copre', 'comuni coprono')} la cella, nessuno con un valore",
        lambda r: (NOTA_DISTRETTO_SENZA_STAZIONI if r.nota_no_data == NOTA_COMUNE_SENZA_STAZIONI
                   else "nessun comune del distretto copre la cella"),
    )
    return (out.rename(columns={"figlie": "comuni", "con_valore": "comuni_con_valore"})
            .drop(columns=["coperte", "residenti_totali", "nota_no_data"]))


def somma_per_distretto(per_comune, pesi=None, colonna_tempo="giorno", chiavi=()):
    """Somma dei comuni per distretto: per i **conteggi** (decessi, ricoveri), dove
    la media pesata non ha senso. La somma è parziale se qualche comune non ha
    valore: la nota lo dichiara, insieme alla quota di residenti coperta."""
    pesi = pesi or carica_pesi_comuni()
    d = per_comune.copy()
    d["distretto"] = d["comune"].map(lambda c: pesi.get(c, (None, 0))[0])
    d["residenti"] = d["comune"].map(lambda c: pesi.get(c, (None, 0))[1]).astype(float)
    chiave = ["distretto", colonna_tempo, *chiavi]
    if d.empty:
        return pd.DataFrame(columns=chiave + ["valore", "stato", "nota", "comuni", "comuni_con_valore",
                                              "quota_residenti"])
    gruppi = d.groupby(chiave, dropna=False).agg(
        figlie=("comune", "nunique"),
        coperte=("stato", lambda s: (s != STATO_NO_DATA).sum()),
        con_valore=("stato", lambda s: (s == STATO_VALORE).sum()),
        residenti_totali=("residenti", "sum"),
    )
    validi = d[d["stato"] == STATO_VALORE]
    somme = validi.groupby(chiave, dropna=False)["valore"].sum()
    gruppi["quota_residenti"] = (validi.groupby(chiave, dropna=False)["residenti"].sum()
                                 / gruppi["residenti_totali"]).fillna(0.0)
    out = _stati(
        gruppi, somme,
        lambda r: (f"somma di {_plurale(r.con_valore, 'comune', 'comuni')} su {r.figlie} "
                   f"({r.quota_residenti:.0%} dei residenti del distretto)"),
        lambda r: f"{_plurale(r.coperte, 'comune copre', 'comuni coprono')} la cella, nessuno con un valore",
        lambda _: "nessun comune del distretto copre la cella",
    )
    return (out.rename(columns={"figlie": "comuni", "con_valore": "comuni_con_valore"})
            .drop(columns=["coperte", "residenti_totali"]))


def per_mese(celle, funzione="media", colonna_tempo="giorno", chiavi=CHIAVI_ARIA, colonna_zona="distretto"):
    """Dal giorno al mese (`AAAA-MM`): `media` per le grandezze intensive (aria,
    calore), `somma` per i conteggi (decessi). È la grana del confronto fra
    domini decisa il 02/10/2026, insieme al distretto."""
    if funzione not in ("media", "somma"):
        raise ValueError("funzione: 'media' o 'somma'")
    d = celle.copy()
    d["mese"] = pd.to_datetime(d[colonna_tempo]).dt.strftime("%Y-%m")
    chiave = [colonna_zona, "mese", *chiavi]
    if d.empty:
        return pd.DataFrame(columns=chiave + ["valore", "stato", "nota", "giorni", "giorni_con_valore"])
    gruppi = d.groupby(chiave, dropna=False).agg(
        figlie=(colonna_tempo, "nunique"),
        coperte=("stato", lambda s: (s != STATO_NO_DATA).sum()),
        con_valore=("stato", lambda s: (s == STATO_VALORE).sum()),
    )
    validi = d[d["stato"] == STATO_VALORE]
    aggregati = validi.groupby(chiave, dropna=False)["valore"].agg("mean" if funzione == "media" else "sum")
    etichetta = "media" if funzione == "media" else "somma"
    gruppi["nota_no_data"] = _nota_uniforme(d, chiave)
    out = _stati(
        gruppi, aggregati,
        lambda r: f"{etichetta} di {_plurale(r.con_valore, 'giorno', 'giorni')} su {r.figlie} del mese",
        lambda r: f"{_plurale(r.coperte, 'giorno coperto', 'giorni coperti')}, nessuno con un valore",
        lambda r: _testo(r.nota_no_data, "nessun giorno del mese è coperto"),
    )
    return (out.rename(columns={"figlie": "giorni", "con_valore": "giorni_con_valore"})
            .drop(columns=["coperte", "nota_no_data"]))


def per_finestra(celle, giorni, funzione="media", colonna_tempo="giorno", chiavi=CHIAVI_ARIA,
                 colonna_zona="distretto"):
    """Dal giorno a una **finestra di giorni qualsiasi**, con le stesse regole di
    `per_mese`: `media` per le grandezze intensive, `somma` per i conteggi.

    Serve alla barra temporale della dashboard, che scorre giorno per giorno su una
    finestra scelta dall'utente (settimanale per default) invece che sul mese di
    calendario. `giorni`: tutti i giorni della finestra in ISO, compresi quelli che il
    dataset non copre — entrano nel conteggio della nota, così si vede subito se la
    media è su 7 giorni o su 2."""
    if funzione not in ("media", "somma"):
        raise ValueError("funzione: 'media' o 'somma'")
    giorni = list(giorni)
    d = celle[celle[colonna_tempo].isin(giorni)]
    chiave = [colonna_zona, *chiavi]
    colonne = chiave + ["valore", "stato", "nota", "giorni", "giorni_con_valore"]
    if d.empty:
        return pd.DataFrame(columns=colonne)
    gruppi = d.groupby(chiave, dropna=False).agg(
        presenti=(colonna_tempo, "nunique"),
        coperte=("stato", lambda s: (s != STATO_NO_DATA).sum()),
        con_valore=("stato", lambda s: (s == STATO_VALORE).sum()),
    )
    gruppi["figlie"] = len(giorni)  # la finestra richiesta, non solo i giorni presenti nel dataset
    validi = d[d["stato"] == STATO_VALORE]
    aggregati = validi.groupby(chiave, dropna=False)["valore"].agg("mean" if funzione == "media" else "sum")
    etichetta = "media" if funzione == "media" else "somma"
    gruppi["nota_no_data"] = _nota_uniforme(d, chiave)
    out = _stati(
        gruppi, aggregati,
        lambda r: f"{etichetta} di {_plurale(r.con_valore, 'giorno', 'giorni')} su {r.figlie} della finestra",
        lambda r: f"{_plurale(r.coperte, 'giorno coperto', 'giorni coperti')}, nessuno con un valore",
        lambda r: _testo(r.nota_no_data, "nessun giorno della finestra è coperto"),
    )
    return (out.rename(columns={"figlie": "giorni", "con_valore": "giorni_con_valore"})
               .drop(columns=["coperte", "presenti", "nota_no_data"]))


def quota_residenti_coperta(celle, pesi=None, colonna_zona="distretto"):
    """{zona: quota di residenti che vive in un comune con almeno un `VALORE`}:
    serve a dichiarare quanta parte di una zona è coperta da dato reale (e quanta
    solo da dato modellato) invece di mostrare una media che sembra completa."""
    pesi = pesi or carica_pesi_comuni()
    residenti_zona, residenti_comune = {}, {}
    for id_comune, (zona, residenti) in pesi.items():
        residenti_zona[zona] = residenti_zona.get(zona, 0) + (residenti or 0)
        residenti_comune[id_comune] = residenti or 0
    con_valore = set(celle.loc[celle["stato"] == STATO_VALORE, "comune"])
    coperti = {}
    for id_comune, (zona, _) in pesi.items():
        if id_comune in con_valore:
            coperti[zona] = coperti.get(zona, 0) + residenti_comune[id_comune]
    if colonna_zona != "distretto":
        raise ValueError("per ora solo la quota per distretto")
    return {zona: (coperti.get(zona, 0) / totale if totale else 0.0) for zona, totale in residenti_zona.items()}
