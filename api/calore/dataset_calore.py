#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dataset calore (terzo dominio, docs/Regole_dei_dati.md): temperatura giornaliera per comune e indicatori di caldo,
con le stesse regole del dataset aria (§4bis): **un valore per fonte**, nessuna media fra fonti, stati
`VALORE`/`NULL`/`NO_DATA` su ogni cella, mai una cella vuota.

Grana: **comune × giorno**. JSON annidato come l'aria
    provincia → distretto → comune → stazione → giorno → fonte → indicatore
Fonti (una chiave sorella per fonte sotto lo stesso giorno):
  * `ERA5-Land` — rianalisi 0,1° (modellata): una **stazione virtuale per comune** `ERA5L-<id_comune>`, come
    `CAMS-<id_comune>` per l'aria; dà un valore a tutti i 145 comuni (api/calore/era5_land.py).
  * `ARPA-Meteo` — temperatura misurata (api/calore/arpa_meteo.py): le stazioni reali `meteo.<id_station>`
    (15 nel Salento, 2020 → ieri). I comuni senza stazioni hanno la stazione fittizia `nessuna_stazione` con
    tutte le celle `NO_DATA`, come per l'aria. Serve a **validare** ERA5-Land, non a sostituirlo.
Indicatori: `temperatura_media|massima|minima` in °C e gli 0/1 di api/calore/soglie.py, calcolati per ogni
fonte e stazione dalla propria temperatura (stesso stato).

Si legge **solo la cache locale**: un mese/anno non scaricato diventa `NULL` con la nota di come scaricarlo
(stessa scelta di CAMS), perché una richiesta al CDS dura minuti.
"""

import hashlib
from datetime import date, datetime, timedelta
from functools import lru_cache

import pandas as pd

from api.calore import arpa_meteo, era5_land
from api.calore.soglie import SOGLIE, UNITA_SOGLIA, UNITA_TEMPERATURA
from api.aria.copernicus_cams import CopernicusError
from api.comune.anagrafiche import FILE_ANAGRAFICHE, leggi_anagrafica
from api.comune.stati import LEGENDA_STATI, STATO_NO_DATA, STATO_NULL, STATO_VALORE

FONTE_ERA5, FONTE_ARPA = "ERA5-Land", "ARPA-Meteo"
NESSUNA_STAZIONE = "nessuna_stazione"
STRUTTURA = ["provincia", "distretto", "comune", "stazione", "giorno", "fonte", "indicatore"]
TEMPERATURE = {f"temperatura_{s}": s for s in era5_land.STATISTICHE}  # indicatore -> statistica
COLONNE_FONTE = ["comune", "stazione", "giorno", "valore", "stato", "nota"]


def impronta_territorio(id_comuni):
    return hashlib.sha1(",".join(sorted(id_comuni)).encode("utf-8")).hexdigest()[:12]


def _territorio():
    """DataFrame (comune, distretto, provincia) dei comuni dell'anagrafica."""
    _, _, t = leggi_anagrafica(FILE_ANAGRAFICHE["territorio"])
    prov = {d["id_distretto"]: d["id_provincia"] for d in t["distretti"]}
    return pd.DataFrame([{"comune": c["id_comune"], "distretto": c["id_distretto"], "provincia": prov[c["id_distretto"]]}
                         for c in t["comuni"]])


def _giorni(anno, mese):
    return [(date(anno, mese, 1) + timedelta(days=n)).isoformat() for n in range(era5_land._fine_mese(anno, mese).day)]


def _cella_fissa(comuni, stazione_di, giorni, stato, nota):
    """Una riga per comune (o per (comune, stazione)) e giorno, tutte con lo stesso stato e la stessa nota."""
    base = pd.DataFrame({"comune": comuni, "stazione": [stazione_di(c) for c in comuni]})
    df = base.merge(pd.DataFrame({"giorno": giorni}), how="cross")
    df["valore"], df["stato"], df["nota"] = float("nan"), stato, nota
    return df[COLONNE_FONTE]


# ---------------------------------------------------------------- ERA5-Land
def _era5(territorio, anno, mese):
    """{statistica: DataFrame COLONNE_FONTE} per ERA5-Land e gli indicatori non in cache."""
    per_stat, mancanti = {}, []
    for ind, stat in TEMPERATURE.items():
        try:
            df = era5_land.temperatura_comuni(stat, anno, mese, scarica=False)
        except CopernicusError as exc:
            df = _cella_fissa(list(territorio["comune"]), lambda c: c, _giorni(anno, mese), STATO_NULL, str(exc))
            mancanti.append(f"{FONTE_ERA5}:{ind}")
        df = df.assign(stazione="ERA5L-" + df["comune"])
        per_stat[stat] = df[COLONNE_FONTE]
    return per_stat, mancanti


# ---------------------------------------------------------------- ARPA meteo
@lru_cache(maxsize=None)
def _arpa_anno(rete, id_station, anno):
    """(DataFrame giornaliero|None, errore|None) di una stazione e di un anno, dalla sola cache."""
    try:
        return arpa_meteo.giornaliero(rete, id_station, anno, scarica=False), None
    except arpa_meteo.ArpaMeteoError as exc:
        return None, str(exc)


def _arpa(territorio, stazioni, anno, mese):
    """{statistica: DataFrame COLONNE_FONTE} per ARPA meteo e gli indicatori non in cache. Giorni fuori dal
    periodo servito (prima del 2020 o dopo l'ultimo giorno pubblicato) → NO_DATA; giorno mancante dentro il
    file di una stazione → NULL; comune senza stazioni → stazione fittizia con tutto NO_DATA."""
    giorni = _giorni(anno, mese)
    per_stat = {s: [] for s in arpa_meteo.STATISTICHE}
    mancanti = []
    primo = f"{arpa_meteo.ANNI[0]}-01-01"
    for r in stazioni.itertuples():
        stazione = f"meteo.{r.id_station}"
        g, errore = (None, None) if anno not in arpa_meteo.ANNI else _arpa_anno(r.rete, r.id_station, anno)
        ultimo = g["giorno"].max() if g is not None and len(g) else None
        if errore:
            mancanti.append(f"{FONTE_ARPA}:{stazione}")
        for s in arpa_meteo.STATISTICHE:
            gs = {} if g is None else g[g["statistica"] == s].set_index("giorno")
            righe = []
            for d in giorni:
                if anno not in arpa_meteo.ANNI or d < primo:
                    righe.append((d, float("nan"), STATO_NO_DATA, f"fuori dal periodo servito da ARPA meteo ({arpa_meteo.ANNI[0]} → ieri)"))
                elif errore:
                    righe.append((d, float("nan"), STATO_NULL, errore))
                elif d in gs.index:
                    x = gs.loc[d]
                    righe.append((d, x["valore"], x["stato"], x["nota"]))
                elif ultimo is None or d > ultimo:
                    righe.append((d, float("nan"), STATO_NO_DATA, "giorno non ancora pubblicato da ARPA meteo"))
                else:
                    righe.append((d, float("nan"), STATO_NULL, "giorno assente dal file della stazione"))
            df = pd.DataFrame(righe, columns=["giorno", "valore", "stato", "nota"])
            df.insert(0, "stazione", stazione)
            df.insert(0, "comune", r.id_comune)
            per_stat[s].append(df)
    senza = sorted(set(territorio["comune"]) - set(stazioni["id_comune"].dropna()))
    for s in arpa_meteo.STATISTICHE:
        per_stat[s].append(_cella_fissa(senza, lambda c: NESSUNA_STAZIONE, giorni, STATO_NO_DATA,
                                        "nessuna stazione meteo ARPA nel comune"))
    return {s: pd.concat(v, ignore_index=True)[COLONNE_FONTE] for s, v in per_stat.items()}, mancanti


# ---------------------------------------------------------------- indicatori
def _soglia(df, soglia, nome, statistica):
    """0/1 dalla temperatura: eredita stato e (se non è VALORE) la nota della temperatura."""
    out = df.copy()
    ok = out["stato"] == STATO_VALORE
    out["valore"] = (out["valore"] >= soglia).astype(float).where(ok)
    out["nota"] = out["nota"].where(~ok, [f"{nome}: T {statistica} {v:.1f} °C {'≥' if v >= soglia else '<'} {soglia:g} °C"
                                          for v in df["valore"]])
    return out


def _indicatori(per_stat, fonte):
    """Dalle tre temperature di una fonte a tutte le righe (temperature + soglie), con colonna `fonte`."""
    parti = [per_stat[stat].assign(indicatore=ind) for ind, stat in TEMPERATURE.items()]
    parti += [_soglia(per_stat[stat], soglia, nome, stat).assign(indicatore=nome) for nome, (stat, soglia, _) in SOGLIE.items()]
    return pd.concat(parti, ignore_index=True).assign(fonte=fonte)


def costruisci_dataset_calore(anno, mese):
    """Griglia (STRUTTURA, valore, stato, nota) di un mese di calendario più gli input non in cache."""
    territorio = _territorio()
    stazioni = arpa_meteo_stazioni()
    era5, manc_era5 = _era5(territorio, anno, mese)
    arpa, manc_arpa = _arpa(territorio, stazioni, anno, mese)
    griglia = pd.concat([_indicatori(era5, FONTE_ERA5), _indicatori(arpa, FONTE_ARPA)], ignore_index=True)
    griglia = griglia.merge(territorio, on="comune")
    return griglia[STRUTTURA + ["valore", "stato", "nota"]], manc_era5 + manc_arpa


@lru_cache(maxsize=None)
def arpa_meteo_stazioni():
    """Stazioni meteo del Salento: dal file in cache se c'è, altrimenti dall'anagrafica di ARPA (una chiamata)."""
    percorso = arpa_meteo.DIR_CACHE / "stazioni_salento.csv"
    if percorso.exists():
        return pd.read_csv(percorso, dtype={"id_comune": str})
    df = arpa_meteo.stazioni_salento()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(percorso, index=False)
    return df


def completo(griglia, mancanti):
    """Un mese è «completo» (non si rigenera più) se tutti gli input erano in cache e nessun giorno dopo
    l'inizio della copertura è NO_DATA per latenza di una fonte."""
    if mancanti:
        return False
    nd = griglia[(griglia["stato"] == STATO_NO_DATA) & (griglia["nota"] != "nessuna stazione meteo ARPA nel comune")]
    fuori = nd["nota"].str.startswith("fuori dal periodo servito")
    return not (~fuori).any()


def a_json(griglia, da, a, mancanti, generato_il=None):
    dati = {}
    for r in griglia.itertuples(index=False):
        foglia = {"valore": None if pd.isna(r.valore) else float(r.valore), "stato": r.stato,
                  "nota": r.nota if isinstance(r.nota, str) else None}
        (dati.setdefault(r.provincia, {}).setdefault(r.distretto, {}).setdefault(r.comune, {})
             .setdefault(r.stazione, {}).setdefault(r.giorno, {}).setdefault(r.fonte, {}))[r.indicatore] = foglia
    stazioni = {}
    for s in arpa_meteo_stazioni().itertuples():
        stazioni[f"meteo.{s.id_station}"] = {"fonte": FONTE_ARPA, "rete": s.rete, "denominazione": s.indirizzo,
                                             "comune": s.id_comune, "lat": s.lat, "lon": s.lon}
    conteggi = griglia.groupby(["fonte", "stato"]).size()
    indicatori = {i: {"unita": UNITA_TEMPERATURA, "descrizione": f"temperatura {s} a 2 m"} for i, s in TEMPERATURE.items()}
    indicatori.update({n: {"unita": UNITA_SOGLIA, "descrizione": d, "da": f"temperatura_{s}", "soglia": t}
                       for n, (s, t, d) in SOGLIE.items()})
    return {
        "descrizione": "Dataset calore — Salento (LE, BR, TA), temperatura giornaliera per comune e indicatori di caldo, "
                       "multi-fonte, non aggregato né tra fonti né tra stazioni",
        "generato_il": generato_il or datetime.now().isoformat(timespec="seconds"),
        "periodo": {"da": da.isoformat(), "a": a.isoformat()},
        "territorio": {"comuni": int(griglia["comune"].nunique()), "impronta": impronta_territorio(griglia["comune"].unique())},
        "completo": completo(griglia, mancanti),
        "struttura": STRUTTURA,
        "stati": LEGENDA_STATI,
        "fonti": {FONTE_ERA5: {"modellata": True, "stazioni_virtuali": True, "copertura_da": era5_land.INIZIO.isoformat()},
                  FONTE_ARPA: {"modellata": False, "copertura_da": f"{arpa_meteo.ANNI[0]}-01-01"}},
        "indicatori": indicatori,
        "stazioni": stazioni,
        "riepilogo": {"celle": int(len(griglia)),
                      "per_fonte_e_stato": {f: {s: int(n) for s, n in conteggi[f].items()} for f in conteggi.index.levels[0]},
                      "input_non_in_cache": mancanti},
        "dati": dati,
    }
