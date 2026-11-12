#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interfaccia comune delle fonti del dataset aria.

Per aggiungere una fonte: creare in questo package una sottoclasse di
FonteAria che implementi `raccogli(data_inizio, data_fine)` e registrarla in
`api/aria/fonti/__init__.py` (FONTI_ARIA). Il generatore
(api/aria/dataset_aria.py) non conosce i dettagli delle singole fonti: si
basa solo su RisultatoFonte.

Convenzioni che ogni fonte deve rispettare:
- `stazione` è la chiave unificata della stazione: l'id ARPA se la stazione
  coincide con una stazione ARPA (v. abbinamento), altrimenti
  "<fonte>-<id nella fonte>". Due fonti che misurano nella stessa stazione
  devono usare la stessa chiave, perché nel dataset la stazione sta sopra la
  fonte.
- i valori sono già convertiti nell'unità di misura usata da ARPA e calcolati
  con la stessa statistica giornaliera di ARPA (v. Parametri_Qualita_Aria.md);
- `misure` contiene solo celle che la fonte ha restituito (stato VALORE o
  NULL): NO_DATA lo decide il generatore.
"""

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from api.aria.arpa_puglia import STATO_NULL, STATO_VALORE

COLONNE_STAZIONI = [
    "stazione",  # chiave unificata
    "fonte",
    "id_fonte",  # id della stazione nella fonte
    "denominazione",
    "comune",
    "provincia",
    "lat",
    "lon",
    "id_distretto",  # None se fuori dal Salento o non assegnabile
    "attiva_da",  # date o None (= nessun limite noto)
    "attiva_a",
    "abbinamento",  # come la stazione è stata ricondotta a chiave e distretto
]
COLONNE_CAPACITA = ["stazione", "inquinante"]
COLONNE_MISURE = ["stazione", "giorno", "inquinante", "valore", "stato", "nota"]


@dataclass
class RisultatoFonte:
    stazioni: pd.DataFrame
    capacita: pd.DataFrame  # coppie (stazione, inquinante) che la fonte misura
    misure: pd.DataFrame
    unita: dict = field(default_factory=dict)  # inquinante -> unità di misura
    # chiamate fallite: dict(da, a, stazione|None, inquinante|None, messaggio)
    periodi_falliti: list = field(default_factory=list)
    # errori e righe malformate: dict(fonte, chiamata, tipo, errore)
    errori: list = field(default_factory=list)
    # informazioni per il report (stazioni escluse, abbinamenti, statistiche...)
    note: dict = field(default_factory=dict)


class FonteAria:
    nome = None
    copertura_da = None  # prima data per cui la fonte ha dati reali (date)
    # periodi dentro la copertura che la fonte non ha (es. un anno mancante):
    # (data_inizio, data_fine, nota) → celle NO_DATA con quella nota
    periodi_non_coperti = ()
    # True se il valore non è misurato ma prodotto da un modello su griglia (CAMS):
    # il report tiene queste fonti separate dalle misurate e lo dichiara (docs/Regole_dei_dati.md)
    modellata = False
    # True se le "stazioni" della fonte non esistono sul campo (CAMS: una per comune):
    # non entrano nella media delle stazioni fisiche di un comune
    stazioni_virtuali = False

    def raccogli(self, data_inizio: date, data_fine: date) -> RisultatoFonte:
        raise NotImplementedError


def df_stazioni(righe):
    return pd.DataFrame(righe, columns=COLONNE_STAZIONI)


def df_capacita(coppie):
    return pd.DataFrame(sorted(set(coppie)), columns=COLONNE_CAPACITA)


def medie_giornaliere(misure, data_inizio, data_fine):
    """Un valore al giorno da misure sub-giornaliere (decisione del 29/09/2026, v. docs/Regole_dei_dati.md):
    media pesata sul tempo di tutte le misure valide del giorno, senza soglia minima di
    completezza; la nota riporta quante ore del giorno sono coperte da almeno una misura valida.

    `misure`: DataFrame con `inizio`, `fine` (Timestamp senza fuso, in UTC+1 come ARPA ed EEA),
    `valore` (float), `valida` (bool) e, facoltativa, `marca` (testo da riportare nella nota,
    es. "non verificato (E2a)", se almeno una misura valida del giorno la porta).
    Le misure più lunghe di un giorno o a cavallo di due giorni sono ignorate.
    Restituisce dict giorno/valore/stato/nota per i giorni del periodo con almeno una misura."""
    if misure.empty:
        return []
    m = misure.copy()
    durata_h = (m["fine"] - m["inizio"]).dt.total_seconds() / 3600
    dentro_un_giorno = (durata_h > 0) & (m["inizio"].dt.normalize() == (m["fine"] - pd.Timedelta(microseconds=1)).dt.normalize())
    m = m[dentro_un_giorno].assign(durata_h=durata_h[dentro_un_giorno], giorno=lambda d: d["inizio"].dt.date)
    m = m[(m["giorno"] >= data_inizio) & (m["giorno"] <= data_fine)]
    if "marca" not in m.columns:
        m["marca"] = None

    risultati = []
    for giorno, gruppo in m.groupby("giorno"):
        valide = gruppo[gruppo["valida"]]
        if valide.empty:
            risultati.append({"giorno": giorno.isoformat(), "valore": None, "stato": STATO_NULL,
                              "nota": f"nessuna misura valida nel giorno ({len(gruppo)} non valide)"})
            continue
        valore = float((valide["valore"] * valide["durata_h"]).sum() / valide["durata_h"].sum())
        # ore del giorno coperte da almeno una misura valida
        ore = set()
        for inizio, fine in zip(valide["inizio"], valide["fine"]):
            ore.update(range(inizio.hour, 24 if fine.normalize() > inizio.normalize()
                             else max(fine.hour + (fine.minute > 0 or fine.second > 0), inizio.hour + 1)))
        nota = f"media pesata sul tempo su {len(ore)}/24 ore"
        marche = sorted({x for x in valide["marca"] if isinstance(x, str)})
        if marche:
            nota += ", " + ", ".join(marche)
        risultati.append({"giorno": giorno.isoformat(), "valore": round(valore, 3), "stato": STATO_VALORE, "nota": nota})
    return risultati


def consolida_misure(righe):
    """DataFrame delle misure con una sola riga per stazione/giorno/inquinante.
    Se la stessa cella arriva più volte (es. due id della stessa stazione in
    OpenAQ): valori validi uguali → uno; diversi → NULL "valori discordanti";
    uno valido e altri NULL → quello valido."""
    df = pd.DataFrame(righe, columns=COLONNE_MISURE)
    if df.empty:
        return df
    chiave = ["stazione", "giorno", "inquinante"]
    df = df.sort_values(chiave, kind="stable")
    validi = df[df["stato"] == STATO_VALORE]
    n_distinti = validi.groupby(chiave)["valore"].nunique()
    discordanti = n_distinti[n_distinti > 1].index

    # a parità di cella, le righe valide vengono prima di quelle NULL
    df["_ordine"] = (df["stato"] != STATO_VALORE).astype(int)
    df = df.sort_values(chiave + ["_ordine"], kind="stable").drop_duplicates(chiave).drop(columns="_ordine")

    if len(discordanti):
        valori = validi.groupby(chiave)["valore"].apply(lambda s: ", ".join(f"{v:g}" for v in sorted(s.unique())))
        indice = df.set_index(chiave).index
        maschera = indice.isin(discordanti)
        df.loc[maschera, "stato"] = STATO_NULL
        df.loc[maschera, "nota"] = [
            f"valori discordanti dalla fonte: {valori[k]}" for k in indice[maschera]
        ]
        df.loc[maschera, "valore"] = None
    return df.reset_index(drop=True)
