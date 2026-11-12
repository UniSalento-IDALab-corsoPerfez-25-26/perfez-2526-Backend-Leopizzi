#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Costruzione del dataset aria multi-fonte con pandas (v. docs/Regole_dei_dati.md).

Il dataset è una griglia completa

    provincia (LE, BR, TA) > distretto > comune > stazione > giorno > fonte > inquinante

in cui ogni cella ha valore, stato e nota:

- VALORE  — numero valido dalla fonte;
- NULL    — la fonte copre la cella ma il valore non è usabile (null dalla
            fonte, non valido, discordante, nessuna misura valida nel giorno,
            errore dell'API sulla chiamata che la conteneva);
- NO_DATA — la fonte non copre la cella (comune senza stazioni, stazione
            che la fonte non ha o che non era attiva, inquinante non misurato,
            data fuori dalla copertura della fonte).

Le fonti sono in api/aria/fonti/ e si aggiungono lì: ognuna restituisce un
RisultatoFonte già controllato a monte (VALORE/NULL); qui si decide NO_DATA,
si unificano le stazioni tra fonti, si collegano ai comuni (v. api/aria/anagrafica_aria.py) e si
costruisce la griglia. I valori restano separati per stazione, fonte e giorno: la media delle
stazioni di un comune non è nel dataset, si calcola solo per la mappa e per le analisi su un comune. Nessun errore
di una fonte interrompe la costruzione: finisce in `errori`.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import pandas as pd

from api.aria.anagrafica_aria import carica_comuni, comune_della_stazione
from api.aria.archivio_aria import impronta_territorio
from api.aria.arpa_puglia import STATO_NO_DATA, STATO_NULL, STATO_VALORE, _a_data
from api.aria.fonti import fonti_aria
from api.aria.fonti.base import RisultatoFonte, consolida_misure, df_capacita, df_stazioni
from api.comune.stati import LEGENDA_STATI

NESSUNA_STAZIONE = "nessuna_stazione"  # chiave dei comuni senza stazioni
STRUTTURA = ["provincia", "distretto", "comune", "stazione", "giorno", "fonte", "inquinante"]
COLONNE_GRIGLIA = STRUTTURA + ["valore", "stato", "nota"]


@dataclass
class DatasetAria:
    data_inizio: date
    data_fine: date
    griglia: pd.DataFrame  # COLONNE_GRIGLIA, una riga per cella
    stazioni: pd.DataFrame  # stazioni nel dataset, una riga per (stazione, fonte, id_fonte)
    fuori_area: pd.DataFrame  # stazioni restituite dalle fonti ma non riconducibili a un comune del Salento
    capacita: pd.DataFrame  # (stazione, inquinante, fonte): coppie misurate, di tutte le stazioni (anche fuori area)
    fonti: dict  # nome -> copertura_da
    # nome -> {"modellata", "stazioni_virtuali"}: il report tiene separate le fonti modellate
    proprieta_fonti: dict
    unita: dict  # inquinante -> unità
    inquinanti_tracciati: list
    inquinanti_nuovi: dict  # inquinante -> fonti che lo hanno restituito
    errori: list
    note: dict  # nome fonte -> note della fonte
    avvisi: list = field(default_factory=list)
    generato_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def _ordina_stazione(chiave):
    return (chiave == NESSUNA_STAZIONE, not str(chiave).isdigit(), len(str(chiave)), str(chiave))


def costruisci_dataset_aria(data_inizio, data_fine, fonti=None, inquinanti_tracciati=()):
    """Costruisce il DatasetAria per il periodo [data_inizio, data_fine].

    `fonti`: istanze di FonteAria (default: tutte, v. api/aria/fonti).
    `inquinanti_tracciati`: lista tracciata (tabella `inquinanti` di data/dataset/aria/anagrafica/inquinanti.json);
    gli inquinanti osservati che non ne fanno parte finiscono in `inquinanti_nuovi`.
    Solleva ValueError solo per un periodo non valido."""
    data_inizio, data_fine = _a_data(data_inizio), _a_data(data_fine)
    ieri = date.today() - timedelta(days=1)
    if data_inizio > data_fine:
        raise ValueError("data_inizio deve precedere (o coincidere con) data_fine")
    if data_fine > ieri:
        raise ValueError(f"data_fine ({data_fine}) è nel futuro: il dato più recente è di ieri ({ieri})")
    fonti = fonti if fonti is not None else fonti_aria()

    # --- raccolta: una fonte che va in crash non ferma le altre ---------------
    risultati, errori, avvisi = {}, [], []
    for fonte in fonti:
        try:
            risultato = fonte.raccogli(data_inizio, data_fine)
        except Exception as exc:  # noqa: BLE001 — qualunque errore imprevisto diventa NULL + log
            messaggio = f"{type(exc).__name__}: {exc}"
            errori.append({"fonte": fonte.nome, "chiamata": "raccogli", "tipo": "errore_imprevisto", "errore": messaggio})
            risultato = RisultatoFonte(
                df_stazioni([]), df_capacita([]), consolida_misure([]),
                periodi_falliti=[{"da": data_inizio, "a": data_fine, "stazione": None, "inquinante": None,
                                  "messaggio": f"errore imprevisto: {messaggio}"}],
            )
        risultati[fonte.nome] = risultato
        errori.extend(risultato.errori)

    # --- stazioni unificate ---------------------------------------------------
    tutte = pd.concat([r.stazioni for r in risultati.values()], ignore_index=True)
    comuni = pd.DataFrame(carica_comuni())
    distretto_del_comune = dict(zip(comuni["id_comune"], comuni["id_distretto"]))
    # comune e distretto di ogni riga: dal comune dichiarato dalla fonte o, in mancanza, dalle coordinate
    # (stessa logica delle anagrafiche); il distretto assegnato dalla fonte viene sostituito da quello del comune
    assegnazioni = [comune_della_stazione(r, comuni.to_dict("records")) for r in tutte.to_dict("records")]
    tutte["id_comune"] = [a[0] for a in assegnazioni]
    tutte["id_distretto"] = tutte["id_comune"].map(distretto_del_comune)
    fuori_area = tutte[tutte["id_comune"].isna()].reset_index(drop=True)
    stazioni = tutte[tutte["id_comune"].notna()].reset_index(drop=True)
    comune_per_stazione = stazioni.drop_duplicates(["stazione", "id_comune"])
    doppie = comune_per_stazione[comune_per_stazione.duplicated("stazione", keep=False)]
    if not doppie.empty:
        avvisi.append(f"stazioni assegnate a più comuni da fonti diverse (tenuto il primo): "
                      f"{sorted(doppie['stazione'].unique())}")
    comune_per_stazione = comune_per_stazione.drop_duplicates("stazione")[["stazione", "id_comune"]]

    # --- inquinanti e unità ---------------------------------------------------
    unita, osservati = {}, {}
    for nome, r in risultati.items():
        for inq, u in r.unita.items():
            if inq in unita and u and unita[inq] and u != unita[inq]:
                avvisi.append(f"unità diversa per {inq}: {unita[inq]} vs {u} ({nome})")
            unita.setdefault(inq, u)
        for inq in set(r.capacita["inquinante"]) | set(r.misure["inquinante"]):
            osservati.setdefault(inq, []).append(nome)
    tracciati = list(inquinanti_tracciati)
    nuovi = {inq: fonti_inq for inq, fonti_inq in sorted(osservati.items()) if inq not in tracciati}
    inquinanti = sorted(set(tracciati) | set(osservati))

    # --- griglia: distretto x stazione x giorno x fonte x inquinante ------------
    base = comuni.rename(columns={"id_distretto": "distretto", "id_comune": "comune"}).assign(
        provincia=comuni["id_distretto"].str[:2])[["provincia", "distretto", "comune"]]
    base = base.merge(comune_per_stazione.rename(columns={"id_comune": "comune"}), on="comune", how="left")
    base["stazione"] = base["stazione"].fillna(NESSUNA_STAZIONE)
    giorni = pd.DataFrame({"giorno": [(data_inizio + timedelta(days=n)).isoformat()
                                      for n in range((data_fine - data_inizio).days + 1)]})
    g = (base.merge(giorni, how="cross")
             .merge(pd.DataFrame({"fonte": [f.nome for f in fonti]}), how="cross")
             .merge(pd.DataFrame({"inquinante": inquinanti}), how="cross"))

    g["valore"] = float("nan")
    g["stato"] = pd.Series(STATO_NULL, index=g.index, dtype=object)
    g["nota"] = pd.Series("nessun dato dalla fonte per questo giorno", index=g.index, dtype=object)

    def imposta(maschera, stato, nota):
        g.loc[maschera, "valore"] = float("nan")
        g.loc[maschera, "stato"] = stato
        g.loc[maschera, "nota"] = nota

    # valori restituiti dalle fonti
    misure = pd.concat([r.misure.assign(fonte=n) for n, r in risultati.items()], ignore_index=True)
    g = g.merge(misure.rename(columns={"valore": "_v", "stato": "_s", "nota": "_n"}),
                on=["stazione", "giorno", "fonte", "inquinante"], how="left")
    presenti = g["_s"].notna()
    g.loc[presenti, "valore"] = g.loc[presenti, "_v"].astype(float)
    g.loc[presenti, "stato"] = g.loc[presenti, "_s"]
    g.loc[presenti, "nota"] = g.loc[presenti, "_n"].where(g.loc[presenti, "_n"].notna(), None)
    g = g.drop(columns=["_v", "_s", "_n"])

    # dalla regola meno prioritaria alla più prioritaria: ognuna sovrascrive le precedenti
    capacita = pd.concat([r.capacita.assign(fonte=n) for n, r in risultati.items()], ignore_index=True)
    g = g.merge(capacita.assign(_capace=True), on=["stazione", "fonte", "inquinante"], how="left")
    imposta(g["_capace"].isna(), STATO_NO_DATA, "inquinante non misurato dalla stazione")

    finestre = (stazioni.groupby(["stazione", "fonte"])
                        .agg(_da=("attiva_da", lambda s: None if s.isna().any() else min(s)),
                             _a=("attiva_a", lambda s: None if s.isna().any() else max(s)))
                        .reset_index())
    g = g.merge(finestre.assign(_coperta=True), on=["stazione", "fonte"], how="left")
    inattiva = g["_coperta"].notna() & (
        (g["_da"].notna() & (g["giorno"] < g["_da"].fillna(""))) |
        (g["_a"].notna() & (g["giorno"] > g["_a"].fillna("9999")))
    )
    imposta(inattiva, STATO_NO_DATA, "stazione non attiva nella fonte in questa data")
    imposta(g["_coperta"].isna(), STATO_NO_DATA, "stazione non coperta dalla fonte")

    for nome, r in risultati.items():
        for p in r.periodi_falliti:
            m = (g["fonte"] == nome) & (g["giorno"] >= p["da"].isoformat()) & (g["giorno"] <= p["a"].isoformat())
            if p.get("stazione"):
                m &= g["stazione"] == p["stazione"]
            if p.get("inquinante"):
                m &= g["inquinante"] == p["inquinante"]
            imposta(m, STATO_NULL, "errore API, v. errori_api.csv")

    for fonte in fonti:
        if fonte.copertura_da:
            imposta((g["fonte"] == fonte.nome) & (g["giorno"] < fonte.copertura_da.isoformat()),
                    STATO_NO_DATA, "data fuori dal periodo coperto dalla fonte")
        for da, a, nota in fonte.periodi_non_coperti:
            imposta((g["fonte"] == fonte.nome) & (g["giorno"] >= da.isoformat()) & (g["giorno"] <= a.isoformat()),
                    STATO_NO_DATA, nota)
    imposta(g["stazione"] == NESSUNA_STAZIONE, STATO_NO_DATA, "nessuna stazione nel comune")

    g = g[COLONNE_GRIGLIA]
    ordine_fonti = {f.nome: i for i, f in enumerate(fonti)}
    g = g.sort_values(
        ["provincia", "distretto", "comune", "stazione", "giorno", "fonte", "inquinante"],
        key=lambda col: col.map(_ordina_stazione) if col.name == "stazione"
        else col.map(ordine_fonti) if col.name == "fonte" else col,
    ).reset_index(drop=True)

    return DatasetAria(
        data_inizio=data_inizio, data_fine=data_fine, griglia=g, stazioni=stazioni, fuori_area=fuori_area,
        capacita=capacita[["stazione", "inquinante", "fonte"]],
        fonti={f.nome: f.copertura_da for f in fonti},
        proprieta_fonti={f.nome: {"modellata": f.modellata, "stazioni_virtuali": f.stazioni_virtuali}
                         for f in fonti},
        unita={i: unita.get(i) for i in inquinanti},
        inquinanti_tracciati=tracciati, inquinanti_nuovi=nuovi, errori=errori,
        note={n: r.note for n, r in risultati.items()}, avvisi=avvisi,
    )


def a_json(ds):
    """Il dataset nel formato deciso (docs/Regole_dei_dati.md): metadati + `dati`
    annidati provincia > distretto > comune > stazione > giorno > fonte > inquinante,
    ogni foglia {"valore", "stato", "nota"}."""
    dati = {}
    for r in ds.griglia.itertuples(index=False):
        foglia = {
            "valore": None if pd.isna(r.valore) else float(r.valore),
            "stato": r.stato,
            "nota": r.nota if isinstance(r.nota, str) else None,
        }
        (dati.setdefault(r.provincia, {}).setdefault(r.distretto, {}).setdefault(r.comune, {})
             .setdefault(r.stazione, {}).setdefault(r.giorno, {}).setdefault(r.fonte, {}))[r.inquinante] = foglia

    stazioni = {}
    for s in ds.stazioni.itertuples(index=False):
        voce = stazioni.setdefault(s.stazione, {"distretto": s.id_distretto, "comune": s.id_comune, "fonti": {}})
        voce["fonti"].setdefault(s.fonte, []).append({
            "id_fonte": s.id_fonte, "denominazione": s.denominazione, "comune": s.comune,
            "lat": None if pd.isna(s.lat) else s.lat, "lon": None if pd.isna(s.lon) else s.lon,
            "attiva_da": s.attiva_da, "attiva_a": s.attiva_a, "abbinamento": s.abbinamento,
        })

    conteggi = ds.griglia.groupby(["fonte", "stato"]).size()
    return {
        "descrizione": "Dataset qualità dell'aria — Salento (LE, BR, TA), multi-fonte, non aggregato né tra fonti né tra stazioni",
        "generato_il": ds.generato_il,
        "periodo": {"da": ds.data_inizio.isoformat(), "a": ds.data_fine.isoformat()},
        # elenco dei comuni con cui è stato generato il file: l'archivio rifà il mese se l'anagrafica cambia
        "territorio": {"comuni": int(ds.griglia["comune"].nunique()),
                       "impronta": impronta_territorio(ds.griglia["comune"].unique())},
        "struttura": STRUTTURA,
        "stati": LEGENDA_STATI,
        "fonti": {n: {"copertura_da": c.isoformat() if c else None, **ds.proprieta_fonti.get(n, {})}
                  for n, c in ds.fonti.items()},
        "inquinanti": ds.unita,
        "stazioni": dict(sorted(stazioni.items(), key=lambda kv: _ordina_stazione(kv[0]))),
        "riepilogo": {
            "celle": int(len(ds.griglia)),
            "per_fonte_e_stato": {f: {s: int(n) for s, n in conteggi[f].items()} for f in conteggi.index.levels[0]},
            "errori": len(ds.errori),
        },
        "dati": dati,
    }
