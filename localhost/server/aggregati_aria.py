"""Aggregati dell'aria per la dashboard, calcolati al volo dai dataset JSON: i dataset restano
**non aggregati** (docs/Regole_dei_dati.md), le medie esistono solo qui, per mappa, grafici e confronti.

Regole decise il 02/10/2026 e scritte in api/comune/aggregazione.py, che qui si usa senza ritoccarla:

- stazione → comune: media delle **stazioni fisiche** con VALORE, per fonte e inquinante. Le fonti a
  stazioni virtuali (CAMS, una "stazione" per comune) non entrano in quella media: il loro valore
  di comune resta una serie a parte, perché è dato modellato;
- comune → distretto: media **pesata sui residenti** dei comuni con VALORE;
- giorno → mese: media dei giorni con VALORE (il mese è la grana del confronto fra domini).

Ai comuni senza stazioni fisiche si aggiungono celle NO_DATA prima di salire al distretto: così la nota
del distretto conta tutti i suoi comuni ("1 comune su 10") e la quota di residenti è sull'intero distretto.

Un mese si calcola una volta (circa 8 s per un mese completo con tre fonti) e resta in memoria finché
i file del dataset che lo coprono non cambiano.
"""

import importlib
import logging
import threading
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import pandas as pd

from api.aria.anagrafica_aria import SOGLIE_PLAUSIBILITA
from api.comune.aggregazione import (
    NOTA_COMUNE_SENZA_STAZIONI,
    NOTA_DISTRETTO_SENZA_STAZIONI,
    carica_pesi_comuni,
    media_per_comune,
    media_per_distretto,
    per_mese,
)
from api.comune.stati import STATO_NO_DATA, STATO_VALORE
from localhost.server import consuntivi

NESSUNA_STAZIONE = "nessuna_stazione"  # stazione fittizia dei comuni senza stazioni (api/aria/dataset_aria.py)
PREFISSO_VIRTUALE = "CAMS-"  # stazioni virtuali per comune delle fonti a griglia (docs/Regole_dei_dati.md, CAMS)
SOGLIA_CONCORDANZA = 1.0  # come la sezione 9 del report aria: due valori concordano se distano al più 1 unità
MESI_IN_MEMORIA = 6
log = logging.getLogger(__name__)

# Vista «tutte le fonti» (decisione del 14/10/2026): per comune e giorno, la media delle fonti **concordi**, scartando
# quella che si discosta troppo dalle altre (es. OpenAQ a Torchiarolo). Solo presentazione: il dataset resta per fonte.
FONTE_ACCORPATA = "Tutte"
TOLLERANZA_ASSOLUTA = {"CO": 0.1}  # nell'unità di inquinanti.json (CO in mg/m³)
TOLLERANZA_ASSOLUTA_PREDEFINITA = 3.0  # µg/m³: "qualche punto"
TOLLERANZA_RELATIVA = 0.2  # oltre i 15 µg/m³ circa conta la quota: 20% della mediana
# spareggio quando nessuna fonte è vicina alla mediana (di solito: due fonti discordi): misurate validate prima, modello per ultimo
PRIORITA_ACCORPATA = ["EEA", "ARPA", "OpenAQ", "CAMS"]

# Licenze come dichiarate nelle schede delle fonti (data/dataset/aria/*/*.md, Lista_dataset_aria.md)
LICENZE = {
    "ARPA": "CC BY 4.0 (assunta come per i dataset ARPA su dati.puglia.it, da confermare con ARPA Puglia)",
    "OpenAQ": "ODC-BY per le stazioni EEA/EEA Italy; nessuna licenza dichiarata per le 2 stazioni HabitatMap",
    "EEA": "CC BY 4.0 (politica di riuso EEA)",
    "CAMS": "CC BY 4.0 (citazione con DOI richiesta da Copernicus)",
    FONTE_ACCORPATA: "quelle delle fonti accorpate (ARPA, OpenAQ, EEA, CAMS)",
}


def _statistiche_dichiarate():
    """{fonte: statistica giornaliera} dagli adattatori (ARPA ne ha una per inquinante). Un adattatore che
    non si importa (es. perché in modifica) non ferma il server: la sua statistica risulta non dichiarata."""
    out = {}
    for fonte, modulo, nome in (("ARPA", "api.aria.fonti.arpa", "STATISTICHE"),
                                ("OpenAQ", "api.aria.fonti.openaq", "STATISTICA"),
                                ("EEA", "api.aria.fonti.eea", "STATISTICA"),
                                ("CAMS", "api.aria.fonti.cams", "STATISTICA")):
        try:
            out[fonte] = getattr(importlib.import_module(modulo), nome)
        except Exception:  # noqa: BLE001
            out[fonte] = None
    return out


_STATISTICHE = _statistiche_dichiarate()
_STATISTICHE[FONTE_ACCORPATA] = "media delle fonti concordi a media giornaliera (ARPA solo per PM10 e PM2.5)"


def statistica(fonte, inquinante):
    """Statistica del valore giornaliero dichiarata dalla fonte per l'inquinante, o None."""
    s = _STATISTICHE.get(fonte)
    return s.get(inquinante) if isinstance(s, dict) else s


def tipo_statistica(s):
    """Come api/aria/report_aria.py: "media" per ogni media giornaliera, altrimenti la statistica così com'è."""
    if not s:
        return None
    return "media" if s.startswith("media") else s


@dataclass
class AggregatiMese:
    mese: str
    firma: tuple  # (nome file, mtime) dei file che coprono il mese: se cambiano, si ricalcola
    meta: dict
    fonti_virtuali: set
    comune_giorno: pd.DataFrame  # comune, giorno, fonte, inquinante, valore, stato, nota, stazioni, stazioni_con_valore
    distretto_giorno: pd.DataFrame  # distretto, giorno, fonte, inquinante, valore, stato, nota, comuni, ...
    comune_mese: pd.DataFrame  # comune, mese, fonte, inquinante, valore, stato, nota, giorni, giorni_con_valore
    distretto_mese: pd.DataFrame  # distretto, mese, ...
    copertura_comune: pd.DataFrame  # comune, fonte, inquinante, totale, con_valore (stazioni fisiche)
    copertura_distretto: pd.DataFrame  # distretto, fonte, inquinante, totale, con_valore, quota_residenti
    valori_fisici: pd.DataFrame  # celle VALORE delle stazioni fisiche, per la concordanza fra fonti
    inquinanti_per_stazione: dict = field(default_factory=dict)  # stazione -> fonte -> [inquinanti con VALORE]
    uso_fonti: pd.DataFrame = field(default_factory=pd.DataFrame)  # vista «tutte»: comune, giorno, inquinante, fonte_usata, usata, esclusa


def _fonti_virtuali(celle, meta):
    dichiarate = {f for f, p in meta["fonti"].items() if (p or {}).get("stazioni_virtuali")}
    if dichiarate:
        return dichiarate
    # dataset generati prima del 02/10: la fonte virtuale è quella che ha valori sulle stazioni CAMS-*
    virt = celle["stazione"].str.startswith(PREFISSO_VIRTUALE) & (celle["stato"] != STATO_NO_DATA)
    return set(celle.loc[virt, "fonte"].unique())


def _completa(comune_giorno, comuni, giorni, fonti, inquinanti, fonti_virtuali):
    """Aggiunge una cella NO_DATA per ogni (comune, giorno, fonte, inquinante) che manca."""
    chiave = ["comune", "giorno", "fonte", "inquinante"]
    tutte = pd.MultiIndex.from_product([comuni, giorni, fonti, inquinanti], names=chiave).to_frame(index=False)
    mancanti = tutte.merge(comune_giorno[chiave], on=chiave, how="left", indicator=True)
    mancanti = mancanti[mancanti["_merge"] == "left_only"].drop(columns="_merge")
    if mancanti.empty:
        return comune_giorno
    mancanti = mancanti.assign(
        valore=float("nan"), stato=STATO_NO_DATA,
        nota=mancanti["fonte"].map(lambda f: "nessun valore del modello per il comune" if f in fonti_virtuali
                                   else NOTA_COMUNE_SENZA_STAZIONI),
        stazioni=0, stazioni_con_valore=0)
    return pd.concat([comune_giorno, mancanti], ignore_index=True)


def _copertura(comune_giorno, celle_fisiche, pesi):
    """Quante zone figlie hanno dato almeno un VALORE nel mese, per fonte e inquinante."""
    con_valore = comune_giorno[comune_giorno["stato"] == STATO_VALORE][["comune", "fonte", "inquinante"]].drop_duplicates()
    con_valore = con_valore.assign(distretto=con_valore["comune"].map(lambda c: pesi.get(c, (None, 0))[0]),
                                   residenti=con_valore["comune"].map(lambda c: pesi.get(c, (None, 0))[1] or 0))
    per_distretto = (con_valore.groupby(["distretto", "fonte", "inquinante"])
                     .agg(con_valore=("comune", "nunique"), residenti_coperti=("residenti", "sum")).reset_index())
    totali = pd.DataFrame([(d, r or 0) for d, r in pesi.values()], columns=["distretto", "residenti"])
    totali = totali.groupby("distretto").agg(totale=("residenti", "size"), residenti_totali=("residenti", "sum")).reset_index()
    combinazioni = comune_giorno[["fonte", "inquinante"]].drop_duplicates()
    cop_d = totali.merge(combinazioni, how="cross").merge(per_distretto, on=["distretto", "fonte", "inquinante"], how="left")
    cop_d[["con_valore", "residenti_coperti"]] = cop_d[["con_valore", "residenti_coperti"]].fillna(0)
    cop_d["quota_residenti"] = (cop_d["residenti_coperti"] / cop_d["residenti_totali"]).where(cop_d["residenti_totali"] > 0, 0.0)
    cop_d = cop_d.drop(columns=["residenti_coperti", "residenti_totali"])

    stazioni_tot = (celle_fisiche.groupby(["comune", "fonte", "inquinante"])["stazione"].nunique()
                    .rename("totale").reset_index())
    stazioni_val = (celle_fisiche[celle_fisiche["stato"] == STATO_VALORE].groupby(["comune", "fonte", "inquinante"])["stazione"]
                    .nunique().rename("con_valore").reset_index())
    cop_c = stazioni_tot.merge(stazioni_val, on=["comune", "fonte", "inquinante"], how="left").fillna({"con_valore": 0})
    return cop_c, cop_d


def _tolleranza(inquinante, mediana):
    return max(TOLLERANZA_ASSOLUTA.get(inquinante, TOLLERANZA_ASSOLUTA_PREDEFINITA), TOLLERANZA_RELATIVA * abs(mediana))


def accorpa_fonti(comune_giorno):
    """Vista «tutte le fonti»: per ogni comune × giorno × inquinante la **media delle fonti concordi**.

    1. Entrano solo le fonti con una **media** giornaliera: ARPA pubblica il massimo per NO2, O3, SO2 e CO e mediarlo
       con delle medie falserebbe il valore (docs/Regole_dei_dati.md), quindi ARPA entra
       solo per PM10 e PM2.5. Le celle sono già al netto delle soglie di plausibilità (media_per_comune).
    2. Si tengono le fonti entro la tolleranza dalla **mediana** delle fonti disponibili (max fra "qualche punto" e il
       20% della mediana): una fonte che si discosta troppo (es. OpenAQ a Torchiarolo) resta fuori.
    3. Se nessuna fonte è vicina alla mediana (due fonti discordi), vince la prima di PRIORITA_ACCORPATA.
    Dove non ci sono stazioni fisiche l'unica fonte è CAMS: la mappa è colorata ovunque, ma quel valore è modellato.

    Restituisce (righe nel formato di comune_giorno con fonte = FONTE_ACCORPATA, uso delle fonti: comune, giorno,
    inquinante, fonte_usata, usata 0/1, esclusa 0/1 — per il tooltip)."""
    chiave = ["comune", "giorno", "inquinante"]
    cg = comune_giorno[comune_giorno["fonte"] != FONTE_ACCORPATA]
    stat = {(f, i): tipo_statistica(statistica(f, i)) for f, i in cg[["fonte", "inquinante"]].drop_duplicates().itertuples(index=False)}
    ammessa = np.array([stat.get((f, i)) == "media" for f, i in zip(cg["fonte"], cg["inquinante"])], dtype=bool)
    v = cg[ammessa & (cg["stato"] == STATO_VALORE).to_numpy()][chiave + ["fonte", "valore"]].copy()

    if len(v):
        g = v.groupby(chiave)["valore"]
        v["mediana"] = g.transform("median")
        tol = np.array([_tolleranza(i, m) for i, m in zip(v["inquinante"], v["mediana"])])
        v["ok"] = (v["valore"] - v["mediana"]).abs().to_numpy() <= tol
        rango = {f: n for n, f in enumerate(PRIORITA_ACCORPATA)}
        v["prio"] = v["fonte"].map(lambda f: rango.get(f, len(rango)))
        nessuna = v.groupby(chiave)["ok"].transform("sum") == 0
        v.loc[nessuna, "ok"] = v.loc[nessuna, "prio"] == v[nessuna].groupby(chiave)["prio"].transform("min")
        usate = v[v["ok"]]
        valori = usate.groupby(chiave)["valore"].mean().rename("valore")
        nomi_usate = usate.groupby(chiave)["fonte"].agg(lambda s: ", ".join(sorted(s))).rename("usate")
        nomi_escluse = v[~v["ok"]].groupby(chiave)["fonte"].agg(lambda s: ", ".join(sorted(s))).rename("escluse")
        uso = v[chiave + ["fonte"]].rename(columns={"fonte": "fonte_usata"}).assign(
            usata=v["ok"].astype(int), esclusa=(~v["ok"]).astype(int))
        # riga "*" = una per cella con valore: è la base delle percentuali di distretto (comuni × giorni con valore)
        base = valori.index.to_frame(index=False).assign(fonte_usata="*", usata=1, esclusa=0)
        uso = pd.concat([uso, base], ignore_index=True)
    else:
        valori = nomi_usate = nomi_escluse = pd.Series(dtype=object)
        uso = pd.DataFrame(columns=chiave + ["fonte_usata", "usata", "esclusa"])

    # griglia completa: ogni comune × giorno × inquinante del mese, con lo stato più informativo
    stati = cg.groupby(chiave)["stato"].agg(lambda s: "NULL" if (s != STATO_NO_DATA).any() else STATO_NO_DATA)
    out = stati.rename("stato").to_frame().join(valori).join(nomi_usate).join(nomi_escluse).reset_index()
    con_valore = out["valore"].notna()
    out.loc[con_valore, "stato"] = STATO_VALORE

    def nota(r):
        if r.stato == STATO_VALORE:
            usate_ = r.usate.split(", ")
            testo = ("solo CAMS (modellato: nessuna misura utilizzabile quel giorno)" if usate_ == ["CAMS"]
                     else f"media di {', '.join(usate_)}" if len(usate_) > 1 else f"solo {usate_[0]}")
            return testo + (f"; esclusa per scarto: {r.escluse}" if isinstance(r.escluse, str) else "")
        if r.stato == "NULL":
            return "le fonti coprono la cella ma nessuna ha un valore utilizzabile a media giornaliera"
        return "nessuna fonte copre la cella"

    out["nota"] = [nota(r) for r in out.itertuples()]
    out = out.assign(fonte=FONTE_ACCORPATA, stazioni=pd.NA, stazioni_con_valore=pd.NA)
    return (out[["comune", "giorno", "fonte", "inquinante", "valore", "stato", "nota", "stazioni", "stazioni_con_valore"]],
            uso.reset_index(drop=True))


def calcola_mese(mese, celle, meta, pesi, firma=()):
    """Tutti gli aggregati di un mese, per ogni fonte e inquinante del dataset."""
    # rete di sicurezza: un dataset generato prima di un cambio dell'anagrafica (es. i codici 075001/075062 prima della
    # fusione Presicce-Acquarica, 14/10/2026) ha comuni senza distretto, che finirebbero in un distretto NaN e
    # romperebbero le risposte. Si scartano dagli aggregati; il rimedio vero è rigenerare il mese.
    ignoti = sorted(set(celle["comune"].unique()) - set(pesi))
    if ignoti:
        log.warning("dataset aria %s: comuni assenti dall'anagrafica %s, esclusi dagli aggregati "
                    "(rigenerare il mese con scripts/aria/genera_dataset_aria.py --rigenera)", mese, ", ".join(ignoti))
        celle = celle[celle["comune"].isin(pesi)]
    fonti_virtuali = _fonti_virtuali(celle, meta)
    virtuale = celle["stazione"].str.startswith(PREFISSO_VIRTUALE)
    fittizia = celle["stazione"] == NESSUNA_STAZIONE
    misurate = ~celle["fonte"].isin(fonti_virtuali)
    celle_fisiche = celle[~virtuale & ~fittizia & misurate]

    parti = []
    if not celle_fisiche.empty:
        parti.append(media_per_comune(celle_fisiche, soglie_plausibilita=SOGLIE_PLAUSIBILITA))
    celle_virtuali = celle[virtuale & ~misurate]
    if not celle_virtuali.empty:  # il valore modellato del comune, così com'è nel dataset
        parti.append(celle_virtuali[["comune", "giorno", "fonte", "inquinante", "valore", "stato", "nota"]]
                     .assign(stazioni=pd.NA, stazioni_con_valore=pd.NA))
    comune_giorno = pd.concat(parti, ignore_index=True) if parti else pd.DataFrame(
        columns=["comune", "giorno", "fonte", "inquinante", "valore", "stato", "nota", "stazioni", "stazioni_con_valore"])
    comune_giorno = _completa(comune_giorno, sorted(pesi), sorted(celle["giorno"].unique()), sorted(celle["fonte"].unique()),
                              sorted(celle["inquinante"].unique()), fonti_virtuali)
    accorpata, uso_fonti = accorpa_fonti(comune_giorno)
    comune_giorno = pd.concat([comune_giorno, accorpata], ignore_index=True)

    distretto_giorno = media_per_distretto(comune_giorno, pesi=pesi)
    comune_mese = per_mese(comune_giorno, funzione="media", colonna_zona="comune")
    distretto_mese = per_mese(distretto_giorno, funzione="media", colonna_zona="distretto")
    copertura_comune, copertura_distretto = _copertura(comune_giorno, celle_fisiche, pesi)

    valori_fisici = celle_fisiche[celle_fisiche["stato"] == STATO_VALORE][
        ["comune", "stazione", "giorno", "fonte", "inquinante", "valore"]].reset_index(drop=True)
    inquinanti_per_stazione = {}
    for (stazione, fonte), gruppo in valori_fisici.groupby(["stazione", "fonte"]):
        inquinanti_per_stazione.setdefault(stazione, {})[fonte] = sorted(gruppo["inquinante"].unique())

    return AggregatiMese(mese=mese, firma=firma, meta=meta, fonti_virtuali=fonti_virtuali,
                         comune_giorno=comune_giorno, distretto_giorno=distretto_giorno, comune_mese=comune_mese,
                         distretto_mese=distretto_mese, copertura_comune=copertura_comune,
                         copertura_distretto=copertura_distretto, valori_fisici=valori_fisici,
                         inquinanti_per_stazione=inquinanti_per_stazione, uso_fonti=uso_fonti)


def confronti_fonti(agg, inquinante, comuni_zona):
    """Concordanza fra coppie di fonti nella zona, sulle sole celle in cui entrambe hanno un VALORE.

    Fonti misurate fra loro: **stazione × giorno** (la stessa stazione, lo stesso giorno: è la validazione
    per ridondanza del report aria). Fonte modellata contro misurata: **comune × giorno** (valore del
    modello contro media delle stazioni fisiche del comune), perché il modello non ha stazioni."""
    comuni_zona = set(comuni_zona)
    out = []
    fis = agg.valori_fisici[(agg.valori_fisici["inquinante"] == inquinante) & agg.valori_fisici["comune"].isin(comuni_zona)]
    larga = fis.pivot_table(index=["stazione", "giorno"], columns="fonte", values="valore", aggfunc="first")
    cg = agg.comune_giorno[(agg.comune_giorno["inquinante"] == inquinante) & agg.comune_giorno["comune"].isin(comuni_zona)
                           & (agg.comune_giorno["stato"] == STATO_VALORE)]
    larga_comune = cg.pivot_table(index=["comune", "giorno"], columns="fonte", values="valore", aggfunc="first")
    fonti = sorted(set(agg.comune_giorno["fonte"].unique()) - {FONTE_ACCORPATA})  # la vista accorpata non è una fonte
    for a, b in combinations(fonti, 2):
        virtuale = a in agg.fonti_virtuali or b in agg.fonti_virtuali
        if a in agg.fonti_virtuali and b in agg.fonti_virtuali:
            continue
        tabella = larga_comune if virtuale else larga
        livello = "comune × giorno" if virtuale else "stazione × giorno"
        coppia = tabella[[a, b]].dropna() if {a, b} <= set(tabella.columns) else pd.DataFrame(columns=[a, b])
        s_a, s_b = statistica(a, inquinante), statistica(b, inquinante)
        stessa = None if not (s_a and s_b) else tipo_statistica(s_a) == tipo_statistica(s_b)
        if stessa is False:
            nota = ("statistiche giornaliere diverse: la differenza misura la distanza fra due statistiche "
                    "(es. un massimo e una media), non un disaccordo fra fonti")
        elif stessa is None:
            nota = "statistica giornaliera non dichiarata da almeno una delle due fonti"
        else:
            nota = "stessa statistica giornaliera: la concordanza è leggibile come validazione"
        if virtuale:
            nota += "; modello a griglia contro media delle stazioni fisiche del comune (misura la qualità del modello)"
        diff = coppia[b] - coppia[a] if len(coppia) else pd.Series(dtype=float)
        out.append({
            "fonte_a": a, "fonte_b": b, "livello": livello, "celle_comuni": int(len(coppia)),
            "quota_concordanti": float((diff.abs() <= SOGLIA_CONCORDANZA).mean()) if len(coppia) else None,
            "differenza_media": float(diff.mean()) if len(coppia) else None,
            "differenza_massima": float(diff.abs().max()) if len(coppia) else None,
            "statistica_a": s_a, "statistica_b": s_b, "stessa_statistica": stessa, "nota": nota,
        })
    return out


@dataclass
class RiassuntoMese:
    """Le parti piccole di un AggregatiMese (circa 1 MB invece di circa 50): restano in memoria per tutti i mesi
    calcolati, così una finestra che copre un mese intero si legge già pronta, senza ricalcolare i giorni.
    Ha gli stessi campi che usano `_stazioni_mappa`, `_info_fonti` e `_modellata` in main.py."""
    mese: str
    firma: tuple
    meta: dict
    fonti_virtuali: set
    fonti: list
    inquinanti: list
    giorni: set
    comune_mese: pd.DataFrame
    distretto_mese: pd.DataFrame
    copertura_comune: pd.DataFrame
    inquinanti_per_stazione: dict
    uso_mese: pd.DataFrame = field(default_factory=pd.DataFrame)  # vista «tutte»: comune, inquinante, fonte_usata, usata, esclusa


COLONNE_USO = ["comune", "inquinante", "fonte_usata", "usata", "esclusa"]


def _somma_uso(uso):
    """Giorni in cui ogni fonte è entrata / è stata scartata nella vista accorpata, per comune e inquinante."""
    if uso is None or uso.empty:
        return pd.DataFrame(columns=COLONNE_USO)
    return uso.groupby(["comune", "inquinante", "fonte_usata"])[["usata", "esclusa"]].sum().reset_index()


def riassumi(agg: AggregatiMese) -> RiassuntoMese:
    cg = agg.comune_giorno
    return RiassuntoMese(mese=agg.mese, firma=agg.firma, meta=agg.meta, fonti_virtuali=agg.fonti_virtuali,
                         fonti=sorted(cg["fonte"].unique()), inquinanti=sorted(cg["inquinante"].unique()),
                         giorni=set(cg["giorno"].unique()), comune_mese=agg.comune_mese, distretto_mese=agg.distretto_mese,
                         copertura_comune=agg.copertura_comune, inquinanti_per_stazione=agg.inquinanti_per_stazione,
                         uso_mese=_somma_uso(agg.uso_fonti))


def testi_uso(uso, pesi, inquinante=None):
    """{("comune"|"distretto", zona, inquinante): testo} con le fonti entrate e scartate nella vista accorpata, da
    aggiungere alla nota della cella (tooltip della mappa). Comune: giorni; distretto: comuni × giorni, in percentuale."""
    out = {}
    if uso is None or uso.empty:
        return out
    u = uso if inquinante is None else uso[uso["inquinante"] == inquinante]
    ordine = {f: n for n, f in enumerate(PRIORITA_ACCORPATA)}

    def testo(tot, unita):
        """`tot`: DataFrame indicizzato su fonte_usata con usata/esclusa; la riga "*" è la base."""
        base = int(tot.loc["*", "usata"]) if "*" in tot.index else 0
        righe = sorted(((f, int(r.usata), int(r.esclusa)) for f, r in tot.iterrows() if f != "*"),
                       key=lambda r: ordine.get(r[0], 99))
        usate = [f"{f} {unita(n, base)}" for f, n, _ in righe if n]
        escluse = [f"{f} {unita(e, base)}" for f, _, e in righe if e]
        return ("fonti: " + ", ".join(usate) if usate else "") + ("; scartate per scarto: " + ", ".join(escluse) if escluse else "")

    for (comune, inq), g in u.groupby(["comune", "inquinante"]):
        tot = g.groupby("fonte_usata")[["usata", "esclusa"]].sum()
        out[("comune", comune, inq)] = testo(tot, lambda n, b: f"{n}/{b} g")
    d = u.assign(distretto=u["comune"].map(lambda c: pesi.get(c, (None, 0))[0]))
    for (distretto, inq), g in d.groupby(["distretto", "inquinante"]):
        tot = g.groupby("fonte_usata")[["usata", "esclusa"]].sum()
        out[("distretto", distretto, inq)] = testo(tot, lambda n, b: f"{round(100 * n / b) if b else 0}%")
    return out


@dataclass
class FinestraAria:
    """Aggregati di una finestra di giorni, per **tutte** le fonti (colonna `fonte`)."""
    comune: pd.DataFrame  # comune, fonte, inquinante, valore, stato, nota, giorni, giorni_con_valore
    distretto: pd.DataFrame  # distretto, fonte, inquinante, ...
    copertura_comune: pd.DataFrame  # comune, fonte, inquinante, totale, con_valore (stazioni fisiche)
    copertura_distretto: pd.DataFrame  # distretto, fonte, inquinante, con_valore, totale, quota_residenti
    mesi: list  # RiassuntoMese dei mesi toccati che hanno un dataset, in ordine
    giorni_coperti: int
    fonti: list
    inquinanti: list
    uso: pd.DataFrame = field(default_factory=pd.DataFrame)  # vista «tutte»: comune, inquinante, fonte_usata, usata, esclusa


def _combina(parti, colonna, giorni_finestra):
    """Somma delle parti (mesi interi già mediati + giorni dei mesi di bordo) in un valore della finestra.

    Ogni parte porta `n` = giorni con VALORE: la media della finestra è Σ(valore·n)/Σn, che è **esattamente** la
    media dei giorni con VALORE (la regola giorno → periodo di api/comune/aggregazione.py), perché il valore di un
    mese è a sua volta la media dei suoi giorni con VALORE."""
    chiave = [colonna, "fonte", "inquinante"]
    colonne = chiave + ["valore", "stato", "nota", "giorni", "giorni_con_valore"]
    if not parti:
        return pd.DataFrame(columns=colonne)
    d = pd.concat(parti, ignore_index=True)
    valido = d["stato"] == STATO_VALORE
    d = d.assign(_p=d["valore"].where(valido, 0.0).fillna(0.0) * d["n"].where(valido, 0),
                 _n=d["n"].where(valido, 0), _c=(d["stato"] != STATO_NO_DATA).astype(int))
    g = d.groupby(chiave, dropna=False).agg(somma=("_p", "sum"), con_valore=("_n", "sum"), coperte=("_c", "sum")).reset_index()
    # motivo di un vuoto: se tutte le parti NO_DATA dicono la stessa cosa (es. "nessuna stazione fisica nel comune"),
    # la finestra lo ripete invece di un generico "nessun giorno coperto" (decisione del 14/10/2026)
    nd = d[d["stato"] == STATO_NO_DATA]
    if "nota" in d.columns and not nd.empty:
        uniforme = (nd.groupby(chiave, dropna=False)["nota"]
                    .agg(lambda s: s.iloc[0] if s.notna().all() and s.nunique() == 1 else None)
                    .rename("nota_nd").reset_index())
        g = g.merge(uniforme, on=chiave, how="left")
    else:
        g["nota_nd"] = None
    g["valore"] = (g["somma"] / g["con_valore"]).where(g["con_valore"] > 0)
    g["stato"] = STATO_NO_DATA
    g.loc[g["coperte"] > 0, "stato"] = "NULL"
    g.loc[g["con_valore"] > 0, "stato"] = STATO_VALORE
    g["giorni"] = giorni_finestra
    g["giorni_con_valore"] = g["con_valore"].astype(int)
    g["nota"] = [f"media di {r.giorni_con_valore} {'giorno' if r.giorni_con_valore == 1 else 'giorni'} su {giorni_finestra} della finestra"
                 if r.stato == STATO_VALORE else
                 "giorni coperti nella finestra, nessuno con un valore" if r.stato == "NULL" else
                 r.nota_nd if isinstance(r.nota_nd, str) and r.nota_nd else
                 "nessun giorno della finestra è coperto" for r in g.itertuples()]
    return g[colonne]


def aggregati_periodo(cache, giorni, fonte=None) -> FinestraAria | None:
    """Aggregati di una finestra di giorni qualsiasi, per una fonte o per tutte.

    I mesi **interamente** dentro la finestra si leggono dal loro riassunto (comune_mese, distretto_mese); dei mesi
    di bordo si leggono i soli giorni della finestra dagli aggregati completi. Stesse regole di sempre: comune =
    media delle stazioni fisiche, distretto = media pesata sui residenti, finestra = media dei giorni con VALORE.
    None se nessun mese della finestra ha un dataset."""
    giorni = sorted(giorni)
    per_mese = {}
    for g in giorni:
        per_mese.setdefault(g[:7], []).append(g)
    parti_c, parti_d, cop, riassunti, coperti = [], [], [], [], 0
    parti_uso = []
    serve_uso = fonte in (None, FONTE_ACCORPATA)
    for m, gg in per_mese.items():
        r = cache.riassunto(m)
        if r is None:
            continue
        riassunti.append(r)
        coperti += len(r.giorni & set(gg))
        anno, num = int(m[:4]), int(m[5:])
        intero = len(gg) == pd.Timestamp(anno, num, 1).days_in_month
        if intero:
            cm, dm, cc = r.comune_mese, r.distretto_mese, r.copertura_comune
            if fonte:
                cm, dm, cc = cm[cm["fonte"] == fonte], dm[dm["fonte"] == fonte], cc[cc["fonte"] == fonte]
            parti_c.append(cm[["comune", "fonte", "inquinante", "valore", "stato", "nota"]].assign(n=cm["giorni_con_valore"]))
            parti_d.append(dm[["distretto", "fonte", "inquinante", "valore", "stato", "nota"]].assign(n=dm["giorni_con_valore"]))
            cop.append(cc[["comune", "fonte", "inquinante", "totale", "con_valore"]])
            if serve_uso:
                parti_uso.append(r.uso_mese)
        else:
            agg = cache.mese(m)
            cg = agg.comune_giorno[agg.comune_giorno["giorno"].isin(gg)]
            dg = agg.distretto_giorno[agg.distretto_giorno["giorno"].isin(gg)]
            if fonte:
                cg, dg = cg[cg["fonte"] == fonte], dg[dg["fonte"] == fonte]
            parti_c.append(cg[["comune", "fonte", "inquinante", "valore", "stato", "nota"]].assign(n=(cg["stato"] == STATO_VALORE).astype(int)))
            parti_d.append(dg[["distretto", "fonte", "inquinante", "valore", "stato", "nota"]].assign(n=(dg["stato"] == STATO_VALORE).astype(int)))
            cop.append(cg.groupby(["comune", "fonte", "inquinante"])
                         .agg(totale=("stazioni", "max"), con_valore=("stazioni_con_valore", "max")).reset_index())
            if serve_uso and not agg.uso_fonti.empty:
                parti_uso.append(_somma_uso(agg.uso_fonti[agg.uso_fonti["giorno"].isin(gg)]))
    if not riassunti:
        return None
    uso = _somma_uso(pd.concat(parti_uso, ignore_index=True)) if parti_uso else pd.DataFrame(columns=COLONNE_USO)
    comune = _combina(parti_c, "comune", len(giorni))
    distretto = _combina(parti_d, "distretto", len(giorni))
    cop_c = (pd.concat(cop, ignore_index=True).groupby(["comune", "fonte", "inquinante"])
             .agg(totale=("totale", "max"), con_valore=("con_valore", "max")).reset_index())

    # copertura del distretto: comuni con almeno un VALORE nella finestra e quota di residenti che rappresentano
    pesi = cache.pesi()
    residenti_distretto, totale_comuni = {}, {}
    for zona, residenti in pesi.values():
        residenti_distretto[zona] = residenti_distretto.get(zona, 0) + (residenti or 0)
        totale_comuni[zona] = totale_comuni.get(zona, 0) + 1
    con_valore = comune[comune["stato"] == STATO_VALORE][["comune", "fonte", "inquinante"]]
    con_valore = con_valore.assign(distretto=con_valore["comune"].map(lambda c: pesi.get(c, (None, 0))[0]),
                                   residenti=con_valore["comune"].map(lambda c: pesi.get(c, (None, 0))[1] or 0))
    cop_d = (con_valore.groupby(["distretto", "fonte", "inquinante"])
             .agg(con_valore=("comune", "nunique"), residenti_coperti=("residenti", "sum")).reset_index())
    cop_d["totale"] = cop_d["distretto"].map(totale_comuni)
    cop_d["quota_residenti"] = [r.residenti_coperti / residenti_distretto[r.distretto] if residenti_distretto.get(r.distretto) else 0.0
                                for r in cop_d.itertuples()]
    return FinestraAria(comune=comune, distretto=distretto, copertura_comune=cop_c,
                        copertura_distretto=cop_d.drop(columns="residenti_coperti"), mesi=riassunti, giorni_coperti=coperti,
                        fonti=sorted({f for r in riassunti for f in r.fonti}),
                        inquinanti=sorted({i for r in riassunti for i in r.inquinanti}), uso=uso)


class CacheAria:
    """Aggregati per mese, calcolati alla prima richiesta: quelli completi restano in memoria al più per
    MESI_IN_MEMORIA mesi, i riassunti (piccoli) per tutti i mesi calcolati."""

    def __init__(self, archivio):
        self.archivio = archivio
        self._mesi = {}
        self._riassunti = {}
        self._blocchi = {}
        self._blocco = threading.Lock()
        self._pesi = None

    def riassunto(self, mese, tieni=True):
        """RiassuntoMese del mese 'AAAA-MM', o None se nessun dataset aria lo copre. `tieni=False` (preriscaldamento):
        se va calcolato, gli aggregati completi non entrano in memoria e non spingono fuori i mesi in uso."""
        firma = self._firma(mese)
        if not firma:
            return None
        r = self._riassunti.get(mese)
        if r is not None and r.firma == firma:
            return r
        salvato = consuntivi.leggi(f"aria_{mese}", firma)  # consuntivo mensile su disco: niente JSON da 20 MB né ricalcolo
        if salvato is not None:
            r = RiassuntoMese(**salvato)
            with self._blocco:
                self._riassunti[mese] = r
            return r
        agg = self.mese(mese, tieni=tieni)
        return self._riassunti.get(mese) if agg is not None else None

    def pesi(self):
        if self._pesi is None:
            self._pesi = carica_pesi_comuni()
        return self._pesi

    def _firma(self, mese):
        anno, num = (int(x) for x in mese.split("-"))
        primo, ultimo = pd.Timestamp(anno, num, 1).date(), (pd.Timestamp(anno, num, 1) + pd.offsets.MonthEnd(0)).date()
        return tuple(sorted((p.name, mtime) for da, a, mtime, p in self.archivio.periodi() if da <= ultimo and a >= primo))

    def mese(self, mese, tieni=True):
        """AggregatiMese del mese 'AAAA-MM', o None se nessun dataset aria lo copre. In memoria restano gli ultimi
        MESI_IN_MEMORIA mesi **usati** (non i più vecchi per data): i mesi di bordo di una finestra lunga restano."""
        firma = self._firma(mese)
        if not firma:
            return None
        with self._blocco:
            blocco = self._blocchi.setdefault(mese, threading.Lock())
        with blocco:  # due richieste sullo stesso mese non lo calcolano due volte
            agg = self._mesi.get(mese)
            if agg is not None and agg.firma == firma:
                with self._blocco:  # usato ora: in fondo alla coda
                    self._mesi[mese] = self._mesi.pop(mese, agg)
                return agg
            trovato = self.archivio.celle_mese(mese)
            if trovato is None:
                return None
            celle, meta = trovato
            agg = calcola_mese(mese, celle, meta, self.pesi(), firma)
            with self._blocco:
                self._riassunti[mese] = riassumi(agg)
                consuntivi.scrivi(f"aria_{mese}", firma, consuntivi.riassunto_in_dict(self._riassunti[mese]))
                if tieni:
                    self._mesi.pop(mese, None)
                    self._mesi[mese] = agg
                    while len(self._mesi) > MESI_IN_MEMORIA:
                        del self._mesi[next(iter(self._mesi))]  # via il mese usato meno di recente
            return agg
