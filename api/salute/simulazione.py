#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dati sanitari **simulati** (decisione di Matteo del 25/10/2026): ricoveri per causa, accessi in pronto
soccorso e accessi in PS degli assistiti in ADI, per **comune × giorno** (dal 25/10/2026, prima distretto ×
giorno), in due scenari selezionabili. Ogni riga porta anche il distretto, per aggregare con le regole di
api/comune/aggregazione.py (somma, perché sono conteggi).

Perché: i dati richiesti ad AReSS Puglia (via prof. Patrono) e a Parsec 3,26 non sono arrivati, e nessuna
fonte pubblica dà ricoveri, PS o ADI sotto la provincia con passo inferiore all'anno
(data/dataset/Inventario_Dati.md §3). Questi valori sono **dati di partenza** per costruire e collaudare la
piattaforma: hanno la forma che avrebbero i dati reali. Dal 03/11/2026 (scelta di Matteo) il progetto non aspetta
altri dati: i simulati restano, sempre dichiarati. **Non descrivono la
situazione sanitaria del Salento.** Scheda, dicitura e limiti: data/dataset/salute/simulati/Dati_Simulati.md.

Come si generano (tutti i numeri sono in `PARAMETRI`, ciascuno con la sua fonte o marcato come ipotesi):

- **livello annuo** calibrato su dati pubblici reali: ricoveri dalle dimissioni ISTAT Health for All per
  provincia × anno (2025-2026 = livello 2024), ripartiti sui comuni in proporzione ai residenti; PS dal tasso
  nazionale di accesso (Annuario SSN 2023); ADI dalla quota nazionale di over 65 assistiti;
- **stagionalità** dal profilo medio dei decessi ISTAT reali del Salento 2011-2019 (due armoniche), uguale in
  entrambi gli scenari: per questo anche lo scenario nullo mostra una correlazione grezza con l'aria, che in
  inverno è più inquinata (confondimento stagionale, v. il report);
- **giorno della settimana** (ipotesi);
- **effetto dell'ambiente**, solo nello scenario `letteratura`: log-lineare, un inquinante per esito per non
  sommare stime *single-pollutant* correlate (PM10 lag 0-5 sui respiratori, NO2 lag 0 sui cardiovascolari,
  EpiAir2) più il caldo oltre i 30 °C di T max (lag 0-3, Michelozzi et al. 2009). Esposizione del comune:
  **CAMS** (l'unica aria che copre tutti i 145 comuni, dato modellato) e **ERA5-Land**;
- **conteggi di Poisson** con seme fisso; i due scenari usano lo **stesso seme** (numeri casuali comuni), così
  la differenza fra i due è dovuta all'effetto e non al caso;
- **ADI**: coorte sintetica di assistiti per comune, con fragilità individuale gamma (sovradispersione presa da
  Campagna et al. 2021) ricampionata ogni anno; da qui accessi, ritorni entro 30 giorni e accessi a bassa urgenza.

Gli stati sono quelli del progetto: ogni cella è `VALORE` con nota «simulato»; i giorni senza esposizione nello
scenario `letteratura` restano generati senza effetto, con la nota che lo dice.
"""

import json
import math
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from api.calore import era5_land
from api.comune.aggregazione import carica_pesi_comuni
from api.comune.stati import STATO_VALORE

RADICE = Path(__file__).resolve().parents[2]
DIR_ARIA = RADICE / "data" / "interim" / "aria"
FILE_DECESSI = RADICE / "data" / "interim" / "salute" / "istat" / "decessi_giornalieri_salento.csv"
FILE_HFA = RADICE / "data" / "interim" / "salute" / "istat_hfa" / "dimissioni_province.csv"
DIR_USCITA = RADICE / "data" / "interim" / "salute" / "simulati"
MODELLO_ARIA = re.compile(r"dataset_aria_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.json$")

VERSIONE = "1.1"
SEME = 20261025
SCENARI = ("nullo", "letteratura")

DICITURA = (
    "Dati sanitari simulati. Ricoveri, accessi in pronto soccorso e accessi degli assistiti in ADI sono generati "
    "da un modello statistico calibrato su aggregati pubblici (ISTAT, Health for All, Annuario SSN) e servono come "
    "dati di partenza per sviluppare e collaudare la piattaforma: i dati richiesti ad AReSS Puglia e a Parsec 3,26 "
    "non sono arrivati e il progetto usa solo quelli che ha già. Non descrivono la situazione sanitaria reale del Salento: non vanno usati "
    "per decisioni né citati come risultati. Nello scenario «letteratura» l'effetto di aria e caldo è imposto da "
    "noi con coefficienti tratti dalla letteratura: le correlazioni che ne risultano riflettono queste ipotesi."
)

# Ogni parametro: valore + fonte (o "ipotesi"). Le citazioni complete, in stile Chicago, sono in
# Bibliografia.md del repository Presentation; i motivi delle scelte in data/dataset/salute/simulati/Dati_Simulati.md.
PARAMETRI = {
    "ricoveri": {
        "fonte": "ISTAT Health for All, dimissioni per provincia di residenza × anno (respiratorio, circolatorio); "
                 "anni successivi all'ultimo pubblicato = ultimo livello; ripartizione sui distretti per residenti",
        "gruppi": {"ricoveri_respiratori": "respiratorio", "ricoveri_circolatori": "circolatorio"},
    },
    "ps": {
        "tasso_annuo_per_1000": 311.0,
        "fonte_tasso": "Annuario statistico del SSN 2023 (18,35 milioni di accessi, 311 ogni 1.000 abitanti), "
                       "riportato da Quotidiano Sanità; dato nazionale applicato al Salento",
        "quote_causa": {"ps_respiratori": 0.08, "ps_cardiovascolari": 0.06},
        "fonte_quote": "ipotesi (ordine di grandezza): da sostituire con la quota per diagnosi del flusso EMUR",
    },
    "adi": {
        "quota_over65": 0.245,
        "fonte_quota_over65": "ipotesi (ordine di grandezza della quota ISTAT di residenti con 65 anni e più "
                              "nelle tre province, da verificare sul dato per comune)",
        "quota_assistiti_over65": 0.04,
        "fonte_quota_assistiti": "circa 4% degli over 65 in ADI nel 2023 (dato nazionale riportato da Italpress; "
                                 "il Ministero dichiara oltre l'8% con un altro denominatore): ipotesi da verificare "
                                 "sul flusso SIAD per la Puglia",
        "accessi_ps_per_assistito_anno": 0.66,
        "dispersione_k": 0.38,
        "fonte_accessi": "Campagna et al. 2021 (Piemonte, 66.433 episodi di ADI): 0,66 accessi in PS per paziente "
                         "(DS 1,34); k della gamma ricavato da media e varianza (var = μ + μ²/k). Applicato come "
                         "tasso annuo: ipotesi",
        "quota_bassa_urgenza": 0.60,
        "fonte_bassa_urgenza": "Campagna et al. 2021: 60,1% degli accessi a bassa urgenza al triage",
        "finestra_ritorno_giorni": 30,
    },
    "stagionalita": {
        "fonte": "profilo medio giornaliero dei decessi ISTAT reali del Salento 2011-2019 (prima del COVID), "
                 "due armoniche annuali, media 1",
        "anni": (2011, 2019),
    },
    "giorno_settimana": {
        # lun..dom, normalizzati a media 1 nel codice
        "ricoveri": [1.15, 1.08, 1.05, 1.03, 1.00, 0.86, 0.83],
        "ps": [1.12, 1.02, 1.00, 0.99, 0.99, 0.94, 0.94],
        "adi": [1.0] * 7,
        "fonte": "ipotesi (ricoveri urgenti più bassi nel fine settimana, picco di PS il lunedì)",
    },
    "effetti": {
        # coefficiente log-lineare per unità di esposizione
        "pm10_lag05": {"per_10": 0.75, "fonte": "EpiAir2 (Scarinzi et al. 2013), ricoveri respiratori, PM10 lag 0-5: "
                                                "+0,75% per 10 µg/m³ (IC95% 0,25-1,25)"},
        "no2_lag0": {"per_10": 0.57, "fonte": "EpiAir2 (Scarinzi et al. 2013), ricoveri cardiaci, NO2 lag 0: "
                                              "+0,57% per 10 µg/m³ (IC95% 0,13-1,02)"},
        "caldo_lag03": {"per_grado": 4.5, "soglia": 30.0,
                        "fonte": "Michelozzi et al. 2009 (PHEWE), ricoveri respiratori 75+ nelle città mediterranee: "
                                 "+4,5% per °C di temperatura apparente massima oltre la soglia (IC95% 1,9-7,3). "
                                 "Qui: T max ERA5-Land, soglia fissa 30 °C (api/calore/soglie.py), lag 0-3 e "
                                 "applicato a tutte le età: ipotesi"},
    },
    # esito -> esposizioni con effetto nello scenario `letteratura`; lo scenario `nullo` le azzera tutte
    "esiti": {
        "ricoveri_respiratori": ["pm10_lag05", "caldo_lag03"],
        "ricoveri_circolatori": ["no2_lag0"],  # Michelozzi 2009: nessun effetto significativo del caldo
        "ps_respiratori": ["pm10_lag05", "caldo_lag03"],
        "ps_cardiovascolari": ["no2_lag0"],
        "ps_altre_cause": [],
        "adi_accessi_ps": ["pm10_lag05", "caldo_lag03"],
    },
}

INDICATORI = {
    "ricoveri_respiratori": "ricoveri per malattie respiratorie",
    "ricoveri_circolatori": "ricoveri per malattie del sistema circolatorio",
    "ps_accessi": "accessi in pronto soccorso, tutte le cause",
    "ps_respiratori": "accessi in pronto soccorso per cause respiratorie",
    "ps_cardiovascolari": "accessi in pronto soccorso per cause cardiovascolari",
    "adi_assistiti": "assistiti in ADI (over 65)",
    "adi_accessi_ps": "accessi in pronto soccorso degli assistiti in ADI",
    "adi_accessi_bassa_urgenza": "accessi in PS degli assistiti in ADI a bassa urgenza (potenzialmente gestibili a domicilio)",
    "adi_ritorni_30g": "accessi in PS di assistiti in ADI già passati dal PS nei 30 giorni precedenti",
}


def coefficiente(nome):
    """β log-lineare per unità di esposizione (µg/m³ o °C oltre soglia)."""
    e = PARAMETRI["effetti"][nome]
    if "per_10" in e:
        return math.log1p(e["per_10"] / 100) / 10
    return math.log1p(e["per_grado"] / 100)


# --- territorio e calibrazione --------------------------------------------------------------------------------

def comuni():
    """DataFrame (id_comune, id_distretto, provincia, residenti) e quota di residenti del comune nella sua provincia."""
    pesi = carica_pesi_comuni()
    df = pd.DataFrame([(c, d, r) for c, (d, r) in pesi.items()], columns=["id_comune", "id_distretto", "residenti"])
    df["provincia"] = df["id_distretto"].str[:2]
    df["quota_provincia"] = df["residenti"] / df.groupby("provincia")["residenti"].transform("sum")
    return df.sort_values("id_comune").reset_index(drop=True)


def livelli_ricoveri():
    """{(provincia, anno, indicatore): dimissioni annue} dalle dimissioni HFA reali."""
    hfa = pd.read_csv(FILE_HFA)
    hfa = hfa[hfa["stato"] == STATO_VALORE]
    out = {}
    for indicatore, gruppo in PARAMETRI["ricoveri"]["gruppi"].items():
        for r in hfa[hfa["gruppo"] == gruppo].itertuples():
            out[(r.provincia, int(r.anno), indicatore)] = float(r.dimissioni)
    return out


def livello_ricoveri(livelli, provincia, anno, indicatore):
    """Livello dell'anno, o dell'ultimo anno pubblicato se l'anno è oltre (nota nel risultato)."""
    anni = sorted(a for p, a, i in livelli if p == provincia and i == indicatore)
    usato = anno if anno in anni else max(a for a in anni if a <= anno)
    return livelli[(provincia, usato, indicatore)], usato


def profilo_stagionale():
    """Funzione giorno dell'anno (1-366) → fattore stagionale con media 1, dai decessi reali 2011-2019."""
    da, a = PARAMETRI["stagionalita"]["anni"]
    d = pd.read_csv(FILE_DECESSI, dtype={"id_comune": str}, usecols=["data", "decessi", "stato"])
    d = d[d["stato"] == STATO_VALORE]
    d["data"] = pd.to_datetime(d["data"])
    d = d[d["data"].dt.year.between(da, a)]
    giornalieri = d.groupby("data")["decessi"].sum()
    t = 2 * np.pi * giornalieri.index.dayofyear.to_numpy() / 365.25
    X = np.column_stack([np.ones_like(t), np.sin(t), np.cos(t), np.sin(2 * t), np.cos(2 * t)])
    b, *_ = np.linalg.lstsq(X, giornalieri.to_numpy(dtype=float), rcond=None)
    b = b / b[0]

    def fattore(giorno_anno):
        tt = 2 * np.pi * np.asarray(giorno_anno) / 365.25
        return b[0] + b[1] * np.sin(tt) + b[2] * np.cos(tt) + b[3] * np.sin(2 * tt) + b[4] * np.cos(2 * tt)
    return fattore


def fattore_settimana(gruppo, giorni):
    f = np.asarray(PARAMETRI["giorno_settimana"][gruppo], dtype=float)
    return (f / f.mean())[pd.DatetimeIndex(giorni).dayofweek]


# --- esposizione ----------------------------------------------------------------------------------------------

def _file_aria_per_mese():
    """{'AAAA-MM': percorso} del file d'archivio più recente che copre il mese."""
    scelti = {}
    for p in DIR_ARIA.glob("dataset_aria_*.json"):
        m = MODELLO_ARIA.search(p.name)
        if m:
            mese = m.group(1)[:7]
            if mese not in scelti or p.stat().st_mtime > scelti[mese].stat().st_mtime:
                scelti[mese] = p
    return scelti


def esposizione_comuni(da, a):
    """DataFrame (id_comune, id_distretto, data, pm10, no2, tmax): PM10 e NO2 della stazione virtuale CAMS del
    comune e T max ERA5-Land del comune, per ogni giorno del periodo. Legge solo file locali."""
    pesi = carica_pesi_comuni()
    mesi = pd.period_range(pd.Timestamp(da).to_period("M"), pd.Timestamp(a).to_period("M"), freq="M")
    file_aria = _file_aria_per_mese()
    righe = []
    for mese in mesi:
        chiave = str(mese)
        if chiave in file_aria:
            with open(file_aria[chiave], encoding="utf-8") as f:
                dati = json.load(f)["dati"]
            for distretti_prov in dati.values():
                for comuni in distretti_prov.values():
                    for comune, stazioni in comuni.items():
                        for giorno, fonti in stazioni.get(f"CAMS-{comune}", {}).items():
                            cams = fonti.get("CAMS", {})
                            for inq, col in (("PM10", "pm10"), ("NO2", "no2")):
                                cella = cams.get(inq)
                                if cella and cella["stato"] == STATO_VALORE:
                                    righe.append((comune, giorno, col, cella["valore"]))
        try:
            t = era5_land.temperatura_comuni("massima", mese.year, mese.month, scarica=False)
            t = t[t["stato"] == STATO_VALORE]
            righe.extend((r.comune, r.giorno, "tmax", r.valore) for r in t.itertuples())
        except era5_land.CopernicusError:
            pass  # mese assente dalla cache: tmax NaN, la nota delle celle lo dirà
    lunga = pd.DataFrame(righe, columns=["id_comune", "data", "variabile", "valore"])
    larga = lunga.pivot_table(index=["id_comune", "data"], columns="variabile", values="valore",
                              aggfunc="first").reset_index()
    larga.columns.name = None
    larga["data"] = pd.to_datetime(larga["data"])
    griglia = pd.MultiIndex.from_product([sorted(pesi), pd.date_range(da, a)],
                                         names=["id_comune", "data"]).to_frame(index=False)
    esp = griglia.merge(larga, on=["id_comune", "data"], how="left")
    esp["id_distretto"] = esp["id_comune"].map(lambda c: pesi[c][0])
    for col in ("pm10", "no2", "tmax"):
        if col not in esp:
            esp[col] = np.nan
    return esp[["id_comune", "id_distretto", "data", "pm10", "no2", "tmax"]]


def esposizioni_con_lag(esp):
    """Aggiunge le esposizioni del modello: PM10 media lag 0-5, NO2 lag 0, gradi di T max (media lag 0-3) oltre
    la soglia. I primi giorni del periodo usano la parte di finestra disponibile."""
    esp = esp.sort_values(["id_comune", "data"]).reset_index(drop=True)
    per = esp.groupby("id_comune", group_keys=False)
    esp["pm10_lag05"] = per["pm10"].transform(lambda s: s.rolling(6, min_periods=1).mean())
    esp["no2_lag0"] = esp["no2"]
    soglia = PARAMETRI["effetti"]["caldo_lag03"]["soglia"]
    tmax03 = per["tmax"].transform(lambda s: s.rolling(4, min_periods=1).mean())
    esp["caldo_lag03"] = (tmax03 - soglia).clip(lower=0)
    return esp


def _log_effetto(esp, esito, scenario, moltiplicatore):
    """(log del moltiplicatore dell'esito, esposizioni mancanti per riga: "" se nessuna, altrimenti i nomi separati
    da virgola). Un'esposizione mancante non applica il **suo** effetto; quello delle altre resta."""
    nomi = PARAMETRI["esiti"][esito] if scenario == "letteratura" else []
    log_rr = np.zeros(len(esp))
    mancante = np.full(len(esp), "", dtype=object)
    for nome in nomi:
        x = esp[nome].to_numpy(dtype=float)
        vuoto = np.isnan(x)
        mancante = np.where(vuoto, np.where(mancante == "", nome, mancante + ", " + nome), mancante)
        log_rr += moltiplicatore * coefficiente(nome) * np.nan_to_num(x)
    return log_rr, mancante


# --- simulazione ----------------------------------------------------------------------------------------------

def simula(esp, scenario, seme=SEME, moltiplicatore=1.0):
    """Celle lunghe (scenario, id_comune, id_distretto, data, indicatore, valore, stato, nota) dello scenario."""
    if scenario not in SCENARI:
        raise ValueError(f"scenario '{scenario}' sconosciuto: {', '.join(SCENARI)}")
    rng = np.random.default_rng(seme)
    com = comuni().set_index("id_comune")
    esp = esp.merge(com[["provincia", "residenti", "quota_provincia"]], left_on="id_comune", right_index=True)
    giorni = pd.DatetimeIndex(esp["data"])
    giorni_anno = np.where(giorni.is_leap_year, 366, 365)
    stagione = profilo_stagionale()(giorni.dayofyear)
    livelli = livelli_ricoveri()
    nota_base = f"simulato, scenario {scenario}"
    uscite = []

    def aggiungi(indicatore, valori, mancante=None, extra=None):
        nota = np.full(len(esp), nota_base, dtype=object)
        if extra is not None:
            nota = np.where(extra != "", nota_base + "; " + extra, nota)
        if mancante is not None and (mancante != "").any():
            nota = np.where(mancante != "", nota + "; esposizione mancante (" + mancante + "): il suo effetto non è applicato",
                            nota)
        uscite.append(pd.DataFrame({
            "scenario": scenario, "id_comune": esp["id_comune"].to_numpy(), "id_distretto": esp["id_distretto"].to_numpy(),
            "data": giorni.strftime("%Y-%m-%d"),
            "indicatore": indicatore, "valore": valori, "stato": STATO_VALORE, "nota": nota}))

    # ricoveri: livello HFA della provincia × quota di residenti del comune, distribuito sui giorni
    coppie = list(zip(esp["provincia"], giorni.year))
    for indicatore in PARAMETRI["ricoveri"]["gruppi"]:
        livello = {c: livello_ricoveri(livelli, c[0], int(c[1]), indicatore) for c in set(coppie)}
        annui = np.array([livello[c][0] for c in coppie])
        anni_usati = np.array([livello[c][1] for c in coppie])
        base = annui * esp["quota_provincia"].to_numpy() / giorni_anno
        log_rr, mancante = _log_effetto(esp, indicatore, scenario, moltiplicatore)
        lam = base * stagione * fattore_settimana("ricoveri", giorni) * np.exp(log_rr)
        etichette = {a: f"livello HFA {a} (ultimo pubblicato)" for a in set(anni_usati)}
        extra = np.where(anni_usati != giorni.year, [etichette[a] for a in anni_usati], "")
        aggiungi(indicatore, rng.poisson(lam), mancante, extra)

    # pronto soccorso: tasso nazionale per residenti, diviso per causa; il totale è la somma delle cause
    ps = PARAMETRI["ps"]
    base_ps = esp["residenti"].to_numpy() * ps["tasso_annuo_per_1000"] / 1000 / giorni_anno
    quote = dict(ps["quote_causa"])
    quote["ps_altre_cause"] = 1 - sum(quote.values())
    per_causa = {}
    for esito, quota in quote.items():
        log_rr, mancante = _log_effetto(esp, esito, scenario, moltiplicatore)
        stag = stagione if esito != "ps_altre_cause" else 1 + (stagione - 1) * 0.5  # ipotesi: altre cause meno stagionali
        per_causa[esito] = (rng.poisson(base_ps * quota * stag * fattore_settimana("ps", giorni) * np.exp(log_rr)),
                            mancante)
    aggiungi("ps_accessi", sum(v for v, _ in per_causa.values()), per_causa["ps_respiratori"][1])
    aggiungi("ps_respiratori", *per_causa["ps_respiratori"])
    aggiungi("ps_cardiovascolari", *per_causa["ps_cardiovascolari"])

    for nome, valori in simula_adi(esp, giorni, stagione, scenario, rng, moltiplicatore).items():
        aggiungi(nome, valori[0], valori[1])
    return pd.concat(uscite, ignore_index=True)


def simula_adi(esp, giorni, stagione, scenario, rng, moltiplicatore):
    """Coorte sintetica di assistiti in ADI per comune: ogni assistito ha una fragilità gamma (media 1, forma k)
    ricampionata a inizio anno; ogni giorno accede al PS con probabilità tasso × fragilità × stagione × effetto.
    {indicatore: (valori allineati a `esp`, esposizioni mancanti per riga, "" se nessuna)}."""
    adi = PARAMETRI["adi"]
    ordine = esp.reset_index(drop=True)
    com = comuni().set_index("id_comune")
    codici = sorted(ordine["id_comune"].unique())
    n_assistiti = {c: int(round(com.loc[c, "residenti"] * adi["quota_over65"] * adi["quota_assistiti_over65"]))
                   for c in codici}
    appartenenza = np.concatenate([np.full(n_assistiti[d], i) for i, d in enumerate(codici)])
    log_rr, mancante = _log_effetto(ordine, "adi_accessi_ps", scenario, moltiplicatore)
    fattore = np.asarray(stagione) * fattore_settimana("adi", giorni) * np.exp(log_rr)
    # matrice giorno × comune dei fattori, per scorrere i giorni in ordine
    tab = pd.DataFrame({"data": giorni, "d": ordine["id_comune"].map({c: i for i, c in enumerate(codici)}),
                        "f": fattore, "riga": np.arange(len(ordine))})
    date_ord = np.sort(tab["data"].unique())
    F = tab.pivot(index="data", columns="d", values="f").reindex(date_ord).to_numpy()
    R = tab.pivot(index="data", columns="d", values="riga").reindex(date_ord).to_numpy()
    k = adi["dispersione_k"]
    h0 = adi["accessi_ps_per_assistito_anno"] / 365.25
    finestra = adi["finestra_ritorno_giorni"]
    accessi = np.zeros(len(ordine), dtype=np.int64)
    ritorni = np.zeros(len(ordine), dtype=np.int64)
    bassa = np.zeros(len(ordine), dtype=np.int64)
    ultimo = np.full(len(appartenenza), -10**6)
    fragilita, anno_corrente = None, None
    for t, giorno in enumerate(pd.DatetimeIndex(date_ord)):
        if giorno.year != anno_corrente:
            fragilita = rng.gamma(k, 1 / k, size=len(appartenenza))
            anno_corrente = giorno.year
        p = np.minimum(h0 * fragilita * F[t, appartenenza], 1.0)
        chi = np.flatnonzero(rng.random(len(appartenenza)) < p)
        if chi.size:
            per_d = np.bincount(appartenenza[chi], minlength=len(codici))
            rit_d = np.bincount(appartenenza[chi[t - ultimo[chi] <= finestra]], minlength=len(codici))
            righe = R[t].astype(int)
            accessi[righe] = per_d
            ritorni[righe] = rit_d
            bassa[righe] = rng.binomial(per_d, adi["quota_bassa_urgenza"])
            ultimo[chi] = t
    assistiti = ordine["id_comune"].map(n_assistiti).to_numpy()
    nessuna = np.full(len(ordine), "", dtype=object)
    return {
        "adi_assistiti": (assistiti, nessuna),
        "adi_accessi_ps": (accessi, mancante),
        "adi_accessi_bassa_urgenza": (bassa, mancante),
        "adi_ritorni_30g": (ritorni, mancante),
    }


# --- verifica -------------------------------------------------------------------------------------------------

def poisson_irls(y, X, iterazioni=50):
    """Regressione di Poisson (legame log) con IRLS: (coefficienti, errori standard)."""
    b = np.zeros(X.shape[1])
    b[0] = math.log(max(y.mean(), 1e-9))
    for _ in range(iterazioni):
        eta = X @ b
        mu = np.exp(eta)
        z = eta + (y - mu) / mu
        XtW = X.T * mu
        nuovo = np.linalg.solve(XtW @ X, XtW @ z)
        if np.max(np.abs(nuovo - b)) < 1e-9:
            b = nuovo
            break
        b = nuovo
    cov = np.linalg.inv((X.T * np.exp(X @ b)) @ X)
    return b, np.sqrt(np.diag(cov))


def stima_effetti(celle, esp, indicatore, esposizioni):
    """Ristima, con un modello di serie temporali standard (comune, anno, stagione con due armoniche, giorno
    della settimana), gli effetti percentuali delle esposizioni sull'indicatore. Serve a verificare che il
    generatore imponga l'effetto dichiarato nello scenario `letteratura` e nessuno nello scenario `nullo`.
    {esposizione: (stima %, IC95% basso, IC95% alto, unità)}."""
    d = celle[celle["indicatore"] == indicatore].merge(
        esp.assign(data=esp["data"].dt.strftime("%Y-%m-%d")).drop(columns="id_distretto"), on=["id_comune", "data"])
    d = d.dropna(subset=esposizioni)
    giorni = pd.DatetimeIndex(d["data"])
    t = 2 * np.pi * giorni.dayofyear.to_numpy() / 365.25
    parti = [np.ones(len(d)), np.sin(t), np.cos(t), np.sin(2 * t), np.cos(2 * t)]
    for col in (pd.get_dummies(d["id_comune"], drop_first=True, dtype=float),
                pd.get_dummies(giorni.year, drop_first=True, dtype=float),
                pd.get_dummies(giorni.dayofweek, drop_first=True, dtype=float)):
        parti.extend(col.to_numpy().T)
    parti.extend(d[e].to_numpy(dtype=float) for e in esposizioni)
    X = np.column_stack(parti)
    b, se = poisson_irls(d["valore"].to_numpy(dtype=float), X)
    out = {}
    for i, e in enumerate(esposizioni):
        j = X.shape[1] - len(esposizioni) + i
        scala = 10 if e.startswith(("pm10", "no2")) else 1
        unita = "per 10 µg/m³" if scala == 10 else "per °C oltre soglia"
        out[e] = tuple(round((math.exp(scala * v) - 1) * 100, 2) for v in (b[j], b[j] - 1.96 * se[j], b[j] + 1.96 * se[j])) + (unita,)
    return out


def correlazione_grezza(celle, esp, indicatore, esposizione):
    """Correlazione di Pearson a distretto × mese fra l'esposizione (media pesata sui residenti dei comuni) e il
    tasso giornaliero dell'indicatore per 100.000 residenti (somma dei comuni), **senza** aggiustare per la
    stagione: è la lettura che darebbe una dashboard ingenua."""
    d = celle[celle["indicatore"] == indicatore].merge(
        esp.assign(data=esp["data"].dt.strftime("%Y-%m-%d")).drop(columns="id_distretto"), on=["id_comune", "data"])
    d["mese"] = d["data"].str[:7]
    com = comuni()
    d["xr"] = d[esposizione] * d["id_comune"].map(com.set_index("id_comune")["residenti"])
    m = d.groupby(["id_distretto", "mese"]).agg(valore=("valore", "sum"), xr=("xr", "sum"),
                                                giorni=("data", "nunique")).reset_index()
    residenti = m["id_distretto"].map(com.groupby("id_distretto")["residenti"].sum())
    m["x"] = m["xr"] / (residenti * m["giorni"])
    m["tasso"] = m["valore"] / m["giorni"] / residenti * 1e5
    return round(float(m[["tasso", "x"]].corr().iloc[0, 1]), 3)
