#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fonte Copernicus CAMS per il dataset aria (client: api/aria/copernicus_cams.py;
scheda: data/dataset/aria/copernicus_cams/Copernicus_CAMS.md).

È l'unica fonte **modellata** (griglia europea 0,1°, ~10 km, con assimilazione di
osservazioni): non ha stazioni. Decisione del 02/10/2026: ogni comune ha una
**stazione virtuale** `CAMS-<id_comune>` (fonte CAMS, `id_fonte` = id_comune, comune
dichiarato, coordinate del centroide), il cui valore è la **media pesata sull'area**
delle celle che intersecano il confine comunale (v. api/comune/celle_comuni.py). Così
CAMS sta nello stesso livello comune → stazione degli altri dati e dà un valore anche ai
comuni (e distretti) senza stazioni fisiche.
Le stazioni virtuali si riconoscono dalla `fonte_riferimento` = CAMS nell'anagrafica
stazioni: **non entrano nella media delle stazioni fisiche di un comune** (v. docs/Regole_dei_dati.md).

Prodotto: rianalisi europea per gli anni già consegnati (validata, o interim dove la
validata non c'è), analisi europea (`type=analysis`) per l'anno in corso e, se la
rianalisi non è scaricabile, per i mesi dal 23/09/2023; la nota di ogni cella dice quale.
Copertura da 2016-01-01: CO e SO2 mancano nella rianalisi 2013-2015 (v. scheda).

Il generatore del dataset **non chiama l'ADS**: la fonte legge solo la cache locale
(`solo_cache=True`, data/raw/aria/copernicus_cams/) e i mesi non ancora scaricati
diventano celle NULL con la nota di come scaricarli; la cache si riempie a parte con
scripts/aria/scarica_cams.py (una richiesta all'ADS dura minuti e porta giù tutta l'Europa).

Valore giornaliero (regola del 29/09/2026 per le fonti sub-giornaliere): media delle ore
valide del giorno (ora locale UTC+1 come ARPA ed EEA), senza soglia minima, con la
completezza nella nota ("media oraria su n/24 ore"). L'ora UTC 23:00 del giorno prima
appartiene al primo giorno locale: se il mese precedente non è già in cache la prima
giornata del periodo risulta su 23/24 ore (dichiarato in nota). CO convertito da µg/m³ a
mg/m³ (unità ARPA).
"""

from datetime import date

import numpy as np
import pandas as pd

from api.aria.anagrafica_aria import carica_comuni
from api.aria.arpa_puglia import STATO_VALORE
from api.aria.copernicus_cams import (
    INIZIO_ANALISI,
    INIZIO_RIANALISI,
    VARIABILI,
    CopernicusError,
    ore_analisi,
    ore_rianalisi,
)
from api.aria.fonti.base import FonteAria, RisultatoFonte, consolida_misure, df_capacita, df_stazioni
from api.comune.celle_comuni import copertura_celle, pesi_celle

UNITA_ARPA = {"CO": "mg/m³"}  # per gli altri µg/m³, come CAMS
FATTORE = {"CO": 1 / 1000}  # CAMS dà µg/m³ per tutto, ARPA il CO in mg/m³
STATISTICA = "media oraria del giorno, media pesata sull'area delle celle CAMS 0,1° del comune"
UTC_PIU_UNO = pd.Timedelta(hours=1)


def _mesi(da, a):
    m = date(da.year, da.month, 1)
    while m <= a:
        yield m.year, m.month
        m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)


def _mese_prima(anno, mese):
    return (anno - 1, 12) if mese == 1 else (anno, mese - 1)


class FonteCAMS(FonteAria):
    nome = "CAMS"
    copertura_da = INIZIO_RIANALISI
    modellata = True
    stazioni_virtuali = True

    def __init__(self, solo_cache=True, inquinanti=None):
        """`solo_cache` (default): non chiama l'ADS: usa i mesi già in
        data/raw/aria/copernicus_cams/ e segna NULL quelli mancanti, perché una
        richiesta all'ADS dura minuti e scarica tutta l'Europa — la cache si
        riempie a parte con scripts/aria/scarica_cams.py.
        `inquinanti`: sigle da raccogliere (default: tutte quelle del modello)."""
        self.solo_cache = solo_cache
        self.inquinanti = list(inquinanti) if inquinanti else list(VARIABILI)

    def raccogli(self, data_inizio, data_fine):
        errori, falliti = [], []
        note = {"statistiche": {s: STATISTICA for s in self.inquinanti}, "prodotti_usati": {}, "abbinamenti": []}
        inizio = max(data_inizio, self.copertura_da)
        if inizio > data_fine:
            return RisultatoFonte(df_stazioni([]), df_capacita([]), consolida_misure([]), note=note)

        comuni = carica_comuni()
        per_confine = {}
        for c in comuni:
            per_confine.setdefault(c["nome_confine"], []).append(c)
        stazioni = [{
            "stazione": f"CAMS-{c['id_comune']}", "fonte": self.nome, "id_fonte": c["id_comune"],
            "denominazione": f"CAMS (modello, griglia 0,1°) — {c['denominazione']}",
            "comune": c["denominazione"], "provincia": c["id_distretto"][:2], "lat": c["lat"], "lon": c["lon"],
            "id_distretto": c["id_distretto"], "attiva_da": None, "attiva_a": None,
            "abbinamento": "stazione virtuale: media pesata sull'area delle celle CAMS che intersecano il comune",
        } for c in comuni]

        capacita, misure, unita = set(), [], {}
        pesi_cache = {}
        anno_corrente = date.today().year
        for sigla in self.inquinanti:
            for anno, mese in _mesi(inizio, data_fine):
                primo, ultimo = max(inizio, date(anno, mese, 1)), min(data_fine, (pd.Timestamp(anno, mese, 1) + pd.offsets.MonthEnd(0)).date())
                try:
                    ore, prodotto = self._ore_del_mese(sigla, anno, mese, anno_corrente, note,
                                                       scarica=not self.solo_cache)
                    precedente = ore_mese_precedente(sigla, anno, mese)
                    giornalieri = self._giornalieri_per_comune(ore, precedente, sigla, primo, ultimo, prodotto, pesi_cache)
                except CopernicusError as exc:
                    tipo = "cache_mancante" if "cache locale" in str(exc) else "errore_api"
                    errori.append({"fonte": self.nome, "chiamata": f"{sigla} {anno}-{mese:02d}", "tipo": tipo,
                                   "errore": str(exc)})
                    falliti.append({"da": primo, "a": ultimo, "stazione": None, "inquinante": sigla,
                                    "messaggio": f"{sigla} {anno}-{mese:02d}: {exc}"})
                    capacita.update((s["stazione"], sigla) for s in stazioni)
                    unita.setdefault(sigla, UNITA_ARPA.get(sigla, "µg/m³"))
                    continue
                unita.setdefault(sigla, UNITA_ARPA.get(sigla, "µg/m³"))
                capacita.update((s["stazione"], sigla) for s in stazioni)
                for confine, per_giorno in giornalieri.items():
                    for comune in per_confine.get(confine, []):
                        for giorno, (valore, nota) in per_giorno.items():
                            misure.append({"stazione": f"CAMS-{comune['id_comune']}", "giorno": giorno, "inquinante": sigla,
                                           "valore": valore, "stato": STATO_VALORE, "nota": nota})
        if not capacita:
            stazioni = []
        return RisultatoFonte(
            stazioni=df_stazioni(stazioni), capacita=df_capacita(capacita), misure=consolida_misure(misure),
            unita=unita, periodi_falliti=falliti, errori=errori, note=note,
        )

    @staticmethod
    def _ore_del_mese(sigla, anno, mese, anno_corrente, note, scarica=True):
        """(ore del mese, prodotto usato): rianalisi per gli anni consegnati, analisi per l'anno in corso
        o come ripiego se la rianalisi non c'è e il mese è nell'archivio dell'analisi.
        Con `scarica=False` si usa solo la cache locale: se il mese non c'è, CopernicusError."""
        fine_mese = (pd.Timestamp(anno, mese, 1) + pd.offsets.MonthEnd(0)).date()
        if anno < anno_corrente:
            try:
                trovato = ore_rianalisi(sigla, anno, mese, scarica=scarica)
            except CopernicusError as exc:
                if fine_mese < INIZIO_ANALISI:
                    raise
                trovato = ore_analisi(sigla, anno, mese, scarica=scarica)
                note.setdefault("ripiego_su_analisi", []).append(f"{sigla} {anno}-{mese:02d}: {str(exc)[:120]}")
            if trovato is None and fine_mese >= INIZIO_ANALISI:
                trovato = ore_analisi(sigla, anno, mese, scarica=scarica)
        else:
            if fine_mese < INIZIO_ANALISI:
                raise CopernicusError("mese precedente all'archivio dell'analisi e anno non consegnato nella rianalisi")
            trovato = ore_analisi(sigla, anno, mese, scarica=scarica)
        if trovato is None:  # solo con scarica=False: il mese non è in cache
            # solo la frase: questa nota arriva nei tooltip della dashboard; il comando per scaricarlo è nel README
            raise CopernicusError(f"{sigla} CAMS di {anno}-{mese:02d} non ancora scaricato in locale")
        ore, prodotto = trovato
        note["prodotti_usati"].setdefault(prodotto, []).append(f"{sigla} {anno}-{mese:02d}")
        return ore, prodotto

    @staticmethod
    def _giornalieri_per_comune(ore, precedente, sigla, primo, ultimo, prodotto, pesi_cache):
        """{nome_confine: {giorno_iso: (valore, nota)}} per i giorni [primo, ultimo]."""
        if precedente is not None:
            ore = pd.concat([precedente, ore], ignore_index=True).drop_duplicates(["ora_utc", "lat", "lon"])
        griglia = ore.pivot(index="ora_utc", columns=["lat", "lon"], values="valore")
        celle = list(griglia.columns)
        chiave_griglia = tuple(celle)
        if chiave_griglia not in pesi_cache:
            lat, lon = sorted({c[0] for c in celle}), sorted({c[1] for c in celle})
            pesi = pesi_celle(lat, lon)
            scoperti = [n for n, q in copertura_celle(lat, lon).items() if q < 0.999]
            if scoperti:
                raise CopernicusError(f"la griglia del file non copre tutta la superficie di: {', '.join(scoperti[:5])}")
            pesi_cache[chiave_griglia] = pesi
        pesi = pesi_cache[chiave_griglia]
        confini = sorted(pesi)
        indice = {c: i for i, c in enumerate(celle)}
        W = np.zeros((len(confini), len(celle)))
        for r, confine in enumerate(confini):
            for lat, lon, peso in pesi[confine]:
                chiave = (round(lat, 4), round(lon, 4))
                if chiave in indice:
                    W[r, indice[chiave]] = peso
        V = griglia.to_numpy(dtype=float)
        valido = ~np.isnan(V)
        peso_valido = valido.astype(float) @ W.T  # quota di area con un valore, per ora e comune
        medie = np.where(peso_valido > 0, np.nan_to_num(V) @ W.T / np.where(peso_valido > 0, peso_valido, 1), np.nan)
        orario = pd.DataFrame(medie * FATTORE.get(sigla, 1.0), index=griglia.index + UTC_PIU_UNO, columns=confini)
        orario["giorno"] = orario.index.date
        orario = orario[(orario["giorno"] >= primo) & (orario["giorno"] <= ultimo)]
        risultato = {c: {} for c in confini}
        for giorno, gruppo in orario.groupby("giorno"):
            ore_valide = gruppo[confini].notna().sum()
            medie_giorno = gruppo[confini].mean()
            for confine in confini:
                n = int(ore_valide[confine])
                if n == 0:
                    continue
                n_celle = len(pesi[confine])
                risultato[confine][giorno.isoformat()] = (
                    round(float(medie_giorno[confine]), 3),
                    f"media oraria su {n}/24 ore (UTC+1), media pesata sull'area di {n_celle} "
                    f"{'cella' if n_celle == 1 else 'celle'} CAMS 0,1°; dato modellato, {prodotto}",
                )
        return risultato


def ore_mese_precedente(sigla, anno, mese):
    """Ore del mese precedente se già in cache (non si scarica): servono solo per l'ora 23:00 UTC
    dell'ultimo giorno, che è la prima ora del primo giorno locale (UTC+1)."""
    a, m = _mese_prima(anno, mese)
    for funzione in (ore_rianalisi, ore_analisi):
        try:
            trovato = funzione(sigla, a, m, scarica=False)
        except CopernicusError:
            trovato = None
        if trovato is not None:
            return trovato[0]
    return None
