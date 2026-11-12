#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Report di analisi di un DatasetAria (api/aria/dataset_aria.py), in Markdown:
copertura per distretto e per fonte, inquinanti nuovi, zone non elencate,
abbinamenti tra stazioni, motivi dei valori mancanti, confronto tra fonti
(validazione incrociata), copertura misurata o modellata, errori.

Il confronto fra fonti (sezione 9) è diviso in due blocchi, perché le fonti non
si leggono tutte allo stesso modo (decisione del 02/10/2026):

- le fonti che producono il valore giornaliero con la **stessa statistica** (la
  media delle ore del giorno: OpenAQ, EEA, CAMS) si confrontano cella per cella
  e la quota di celle concordanti misura davvero la concordanza del dato;
- **ARPA** pubblica un valore già giornaliero con la *sua* statistica (il massimo
  per NO2, O3, SO2 e CO): per quegli inquinanti il confronto misura la distanza
  fra massimo e media, non un disaccordo fra fonti. Resta quindi in un blocco a
  parte, come lettura qualitativa.

Il confronto con CAMS si fa a **comune × giorno** (CAMS non ha stazioni: ha una
stazione virtuale per comune), contro la media delle stazioni fisiche del comune.
"""

import pandas as pd

from api.aria.anagrafica_aria import SOGLIE_PLAUSIBILITA
from api.aria.arpa_puglia import STATO_NO_DATA, STATO_NULL, STATO_VALORE
from api.aria.dataset_aria import NESSUNA_STAZIONE
from api.comune.aggregazione import media_per_comune, quota_residenti_coperta
from api.comune.distretti_salento import carica_distretti

STATI = [STATO_VALORE, STATO_NULL, STATO_NO_DATA]
SOGLIA_CONCORDANZA = 1.0  # differenza entro cui due fonti si considerano concordanti


def _tabella(df, indice=False):
    """DataFrame -> tabella Markdown (senza dipendenze extra)."""
    if indice:
        df = df.reset_index()
    righe = ["| " + " | ".join(str(c) for c in df.columns) + " |", "|" + "---|" * len(df.columns)]
    for r in df.itertuples(index=False):
        righe.append("| " + " | ".join("" if pd.isna(v) else (f"{v:g}" if isinstance(v, float) else str(v)) for v in r) + " |")
    return "\n".join(righe)


def _tipo_statistica(statistica):
    """"media" per ogni media giornaliera (semplice o pesata sul tempo), altrimenti la statistica così com'è."""
    if not statistica:
        return None
    return "media" if statistica.startswith("media") else statistica


def _pct(parte, totale):
    return f"{100 * parte / totale:.1f}%" if totale else "—"


def _statistiche(ds, fonte):
    """{inquinante: tipo di statistica giornaliera} dichiarato dalla fonte."""
    return {i: _tipo_statistica(s) for i, s in (ds.note.get(fonte, {}).get("statistiche") or {}).items()}


def _statistica_omogenea(ds, fonte):
    """True se la fonte usa la **stessa** statistica (la media del giorno) per tutti gli
    inquinanti: sono queste le fonti direttamente confrontabili fra loro."""
    tipi = set(_statistiche(ds, fonte).values())
    return tipi == {"media"}


def _descrizione_statistica(ds, fonte):
    per_tipo = {}
    for inq, tipo in sorted(_statistiche(ds, fonte).items()):
        per_tipo.setdefault(tipo or "?", []).append(inq)
    if len(per_tipo) == 1:
        return f"{next(iter(per_tipo))} (tutti gli inquinanti)"
    return "; ".join(f"{tipo}: {', '.join(inq)}" for tipo, inq in sorted(per_tipo.items()))


def _celle_per_livello(ds, fonte, per_comune):
    """(celle confrontabili, livello) di una fonte: stazione × giorno per le fonti con
    stazioni fisiche, comune × giorno per quelle a stazioni virtuali (CAMS), dove il
    termine di confronto è la media delle stazioni fisiche del comune."""
    virtuali = ds.proprieta_fonti.get(fonte, {}).get("stazioni_virtuali")
    if virtuali:
        celle = ds.griglia[(ds.griglia["fonte"] == fonte) & (ds.griglia["stato"] == STATO_VALORE)]
        return celle[["comune", "giorno", "inquinante", "valore"]], "comune"
    celle = per_comune[(per_comune["fonte"] == fonte) & (per_comune["stato"] == STATO_VALORE)]
    return celle[["comune", "giorno", "inquinante", "valore"]], "comune_da_stazioni"


def _confronto_stazioni(ds, prima, altra):
    """Celle (stazione × giorno × inquinante) in cui entrambe le fonti hanno un VALORE."""
    valori = ds.griglia[ds.griglia["stato"] == STATO_VALORE]
    chiave = ["stazione", "giorno", "inquinante"]
    return (valori[valori["fonte"] == prima][chiave + ["valore"]]
            .merge(valori[valori["fonte"] == altra][chiave + ["valore"]], on=chiave,
                   suffixes=(f"_{prima}", f"_{altra}")), chiave)


def _confronto_comuni(ds, prima, altra, per_comune):
    """Celle (comune × giorno × inquinante) confrontabili quando una delle due fonti non ha
    stazioni fisiche: la fonte fisica è rappresentata dalla media delle sue stazioni nel comune."""
    a, _ = _celle_per_livello(ds, prima, per_comune)
    b, _ = _celle_per_livello(ds, altra, per_comune)
    chiave = ["comune", "giorno", "inquinante"]
    return a.merge(b, on=chiave, suffixes=(f"_{prima}", f"_{altra}")), chiave


def _tabella_confronto(ds, confronto, prima, altra, chiave, confrontabile):
    """Righe markdown del confronto fra due fonti: una riga per inquinante e, se le
    statistiche coincidono, le celle più discordanti. `confrontabile`: {inquinante: bool}."""
    a, b = f"valore_{prima}", f"valore_{altra}"
    confronto = confronto.copy()
    confronto["diff"] = confronto[b] - confronto[a]
    righe = []
    for inq, c in confronto.groupby("inquinante"):
        ok = confrontabile.get(inq, False)
        righe.append({
            "Inquinante": inq,
            "Stessa statistica": "sì" if ok else "no",
            "Celle": len(c),
            "Concordanti": _pct(int((c["diff"].abs() <= SOGLIA_CONCORDANZA).sum()), len(c)) if ok else "non misurabile",
            f"Media {prima}": round(c[a].mean(), 2), f"Media {altra}": round(c[b].mean(), 2),
            f"Diff. media ({altra}−{prima})": round(c["diff"].mean(), 2),
            "Mediana diff. assoluta": round(c["diff"].abs().median(), 2),
            "Diff. assoluta massima": round(c["diff"].abs().max(), 2),
            "Correlazione (Pearson)": round(c[a].corr(c[b]), 3) if len(c) > 2 else None,
        })
    out = [_tabella(pd.DataFrame(righe)), ""]
    comparabili = confronto[confronto["inquinante"].map(lambda i: confrontabile.get(i, False))]
    discordi = comparabili[comparabili["diff"].abs() > SOGLIA_CONCORDANZA]
    if not discordi.empty:
        peggiori = discordi.reindex(discordi["diff"].abs().sort_values(ascending=False).index).head(10)
        out += [f"Celle più discordanti fra quelle a statistica uguale (prime {len(peggiori)} di {len(discordi)}):", "",
                _tabella(peggiori[chiave + [a, b, "diff"]].round(2)), ""]
    return out


def _sezione_confronti(ds, coppie, per_comune, livello_comune):
    """Un blocco di confronti: per ogni coppia, le celle comuni e la tabella per inquinante."""
    out = []
    for prima, altra in coppie:
        if livello_comune or any(ds.proprieta_fonti.get(f, {}).get("stazioni_virtuali") for f in (prima, altra)):
            confronto, chiave = _confronto_comuni(ds, prima, altra, per_comune)
            dove = ("comune × giorno (per le fonti con stazioni: media delle stazioni fisiche del comune)")
        else:
            confronto, chiave = _confronto_stazioni(ds, prima, altra)
            dove = "stazione × giorno"
        stat_1, stat_2 = _statistiche(ds, prima), _statistiche(ds, altra)
        confrontabile = {i: bool(stat_1.get(i)) and stat_1.get(i) == stat_2.get(i)
                         for i in set(stat_1) | set(stat_2)}
        out += [f"#### {prima} ↔ {altra}", "",
                f"Livello: {dove}. Celle in cui entrambe hanno un `VALORE`: **{len(confronto)}**.", ""]
        if confronto.empty:
            out += ["Nessuna cella in comune nel periodo.", ""]
            continue
        out += _tabella_confronto(ds, confronto, prima, altra, chiave, confrontabile)
    return out


def genera_report(ds, info_inquinanti=None):
    """`info_inquinanti`: righe della tabella `inquinanti` di data/dataset/aria/anagrafica/inquinanti.json, per
    distinguere i 5 di riferimento della dashboard da quelli scoperti nei dati."""
    info_inquinanti = info_inquinanti or {}
    riferimento = [i for i, v in info_inquinanti.items() if v.get("riferimento_dashboard")]
    scoperti = {i: v for i, v in info_inquinanti.items() if not v.get("riferimento_dashboard")}
    g = ds.griglia
    fonti = list(ds.fonti)
    nomi_distretti = {d["id_distretto"]: d["comune_sede"].title() for d in carica_distretti()}
    n_distretti = len(nomi_distretti)
    reali = g[g["stazione"] != NESSUNA_STAZIONE]
    valori = g[g["stato"] == STATO_VALORE]
    fonti_misurate = [f for f in fonti if not ds.proprieta_fonti.get(f, {}).get("modellata")]
    comuni_con_misura = set(valori.loc[valori["fonte"].isin(fonti_misurate), "comune"])

    out = [
        f"# Report dataset aria — {ds.data_inizio.isoformat()} → {ds.data_fine.isoformat()}",
        "",
        f"Generato il {ds.generato_il} da `scripts/aria/genera_dataset_aria.py`. Fonti: {', '.join(fonti)}. "
        f"Struttura: provincia → distretto → comune → stazione → giorno → fonte → inquinante (v. docs/Regole_dei_dati.md). "
        "L'analisi è descrittiva della copertura dei dati, non un'analisi dell'esposizione.",
        "",
        "## 1. Sintesi",
        "",
    ]

    # --- sintesi ---------------------------------------------------------------
    distretti_con_valore = {f: set(valori.loc[valori["fonte"] == f, "distretto"]) for f in fonti}
    tutti_con_valore = set(valori["distretto"])
    senza_valore = sorted(set(nomi_distretti) - tutti_con_valore)
    out += [
        f"- **Celle totali:** {len(g):,}".replace(",", "."),
        f"- **Distretti con almeno un valore** (qualunque fonte): **{len(tutti_con_valore)} su {n_distretti}**"
        + "".join(f"; {f}: {len(distretti_con_valore[f])}" for f in fonti),
        f"- **Comuni con almeno un valore:** {valori['comune'].nunique()} su {g['comune'].nunique()}, "
        f"di cui **{len(comuni_con_misura)} con dato misurato** e "
        f"**{valori['comune'].nunique() - len(comuni_con_misura)} solo modellato** (v. sezione 10)",
        f"- **Distretti senza alcun valore:** {len(senza_valore)} — "
        + (", ".join(f"{d} ({nomi_distretti[d]})" for d in senza_valore) or "nessuno"),
        f"- **Inquinanti scoperti nei dati** oltre ai {len(riferimento)} di riferimento della dashboard: "
        + (", ".join(sorted(set(scoperti) | set(ds.inquinanti_nuovi))) or "nessuno")
        + (f" (nuovi in questa esecuzione: {', '.join(ds.inquinanti_nuovi)})" if ds.inquinanti_nuovi else ""),
        f"- **Stazioni/zone fuori dai distretti noti:** {len(ds.fuori_area)}",
        f"- **Errori delle API:** {len(ds.errori)}",
        "",
    ]

    # --- stati per fonte ---------------------------------------------------------
    stati = g.groupby(["fonte", "stato"]).size().unstack(fill_value=0).reindex(columns=STATI, fill_value=0)
    stati_reali = reali.groupby(["fonte", "stato"]).size().unstack(fill_value=0).reindex(columns=STATI, fill_value=0)
    tab = pd.DataFrame({
        "Fonte": stati.index,
        "VALORE": stati[STATO_VALORE].values,
        "NULL": stati[STATO_NULL].values,
        "NO_DATA": stati[STATO_NO_DATA].values,
        "% VALORE sulle celle di stazioni reali": [
            _pct(stati_reali.loc[f, STATO_VALORE], stati_reali.loc[f].sum()) if f in stati_reali.index else "—"
            for f in stati.index
        ],
    })
    out += ["## 2. Celle per fonte e stato", "", _tabella(tab), ""]

    # --- copertura per distretto ------------------------------------------------
    out += ["## 3. Copertura per distretto", "",
            "Celle con `VALORE` per distretto e fonte (stazione × giorno × inquinante), e stazioni coperte da ciascuna fonte.", ""]
    stazioni_per_fonte = ds.stazioni.groupby(["id_distretto", "fonte"])["stazione"].nunique().unstack(fill_value=0)
    righe = []
    for d in sorted(nomi_distretti):
        riga = {"Distretto": d, "Comune sede": nomi_distretti[d]}
        for f in fonti:
            riga[f"{f} stazioni"] = int(stazioni_per_fonte.loc[d, f]) if d in stazioni_per_fonte.index and f in stazioni_per_fonte.columns else 0
            riga[f"{f} valori"] = int(((valori["distretto"] == d) & (valori["fonte"] == f)).sum())
        righe.append(riga)
    out += [_tabella(pd.DataFrame(righe)), ""]

    # --- distretti con valore per inquinante --------------------------------------
    out += ["## 4. Distretti con almeno un valore, per inquinante", ""]
    per_inq = valori.groupby(["inquinante", "fonte"])["distretto"].nunique().unstack(fill_value=0).reindex(columns=fonti, fill_value=0)
    per_inq_tot = valori.groupby("inquinante")["distretto"].nunique()
    tab = pd.DataFrame({"Inquinante": ds.unita.keys(), "Unità": ds.unita.values()})
    for f in fonti:
        tab[f] = [int(per_inq.loc[i, f]) if i in per_inq.index else 0 for i in tab["Inquinante"]]
    tab["Qualunque fonte"] = [int(per_inq_tot.get(i, 0)) for i in tab["Inquinante"]]
    tab["Stato nella lista"] = [
        "riferimento dashboard" if i in riferimento
        else "**nuovo (questa esecuzione)**" if i in ds.inquinanti_nuovi
        else f"scoperto il {scoperti[i].get('aggiunto_il', '?')}" if i in scoperti
        else "tracciato"
        for i in tab["Inquinante"]
    ]
    out += [f"Su {n_distretti} distretti.", "", _tabella(tab), ""]

    # --- inquinanti scoperti ---------------------------------------------------------
    out += ["## 5. Inquinanti scoperti nei dati", "",
            f"Inquinanti di riferimento per la dashboard (docs/Regole_dei_dati.md): {', '.join(riferimento) or '—'}. "
            "Per la regola di docs/Regole_dei_dati.md ogni altro inquinante restituito da una fonte viene aggiunto "
            "alla lista tracciata (`data/dataset/aria/anagrafica/inquinanti.json`); resta da decidere se "
            "includerlo fra gli inquinanti di riferimento della dashboard (`RIFERIMENTO_DASHBOARD` in `api/aria/anagrafica_aria.py`).", ""]
    elenco = sorted(set(scoperti) | set(ds.inquinanti_nuovi))
    if elenco:
        for i in elenco:
            fonti_i = ds.inquinanti_nuovi.get(i)
            origine = (f"restituito da {', '.join(fonti_i)} — **nuovo in questa esecuzione**" if fonti_i
                       else f"{scoperti[i].get('origine', '')}, aggiunto il {scoperti[i].get('aggiunto_il', '?')}")
            out += [f"- **{i}** ({ds.unita.get(i) or 'unità ?'}) — {origine}"]
    else:
        out += ["Nessuno."]
    out += [""]

    # --- zone non elencate --------------------------------------------------------
    out += ["## 6. Stazioni fuori dai distretti noti (zone non elencate)", "",
            "Stazioni restituite da una fonte ma non riconducibili a nessuno dei 20 distretti del Salento: "
            "escluse dalla griglia e segnalate in `data/interim/aria/riepilogo_errori.md` (regola di docs/Regole_dei_dati.md).", ""]
    if ds.fuori_area.empty:
        out += ["Nessuna.", ""]
    else:
        fa = ds.fuori_area[["fonte", "id_fonte", "denominazione", "comune", "provincia", "abbinamento"]].fillna("—")
        out += [_tabella(fa), ""]

    # --- stazioni ------------------------------------------------------------------
    out += ["## 7. Stazioni", ""]
    for f in fonti:
        n_staz = ds.stazioni.loc[ds.stazioni["fonte"] == f, "stazione"].nunique()
        out += [f"- **{f}:** {n_staz} stazioni nel dataset"]
        note = ds.note.get(f, {})
        if note.get("stazioni_non_in_anagrafica"):
            out += [f"  - non in anagrafica ARPA, incluse tramite il comune: "
                    + ", ".join(f"{k} ({v})" for k, v in note["stazioni_non_in_anagrafica"].items())]
        if note.get("stazioni_escluse"):
            out += [f"  - escluse: " + "; ".join(f"{k} {v}" for k, v in note["stazioni_escluse"].items())]
        if note.get("stazioni_senza_licenza"):
            out += [f"  - senza licenza dichiarata (incluse comunque): "
                    + "; ".join(f"{k} {v}" for k, v in note["stazioni_senza_licenza"].items())]
        if note.get("sensori_scartati"):
            out += [f"  - sensori scartati: " + "; ".join(note["sensori_scartati"])]
        if note.get("dataset_usati"):
            out += [f"  - dataset usati: " + ", ".join(f"{k} {v}" for k, v in note["dataset_usati"].items())]
        if note.get("statistiche"):
            out += [f"  - statistica giornaliera usata: " + ", ".join(f"{k}={v}" for k, v in sorted(note["statistiche"].items()))]
    condivise = ds.stazioni.groupby("stazione")["fonte"].nunique()
    out += [f"- **Stazioni comuni a più fonti:** {int((condivise > 1).sum())} su {len(condivise)}", ""]

    for f in fonti:
        abbinamenti = ds.note.get(f, {}).get("abbinamenti", [])
        if abbinamenti:
            out += [f"### Abbinamento stazioni {f} → stazioni ARPA", "",
                    "Solo le stazioni con dati nel periodo.", "",
                    _tabella(pd.DataFrame(abbinamenti).fillna("—").rename(columns={
                        "id_fonte": f"id {f}", "nome_fonte": f"nome {f}", "stazione": "chiave nel dataset",
                        "id_distretto": "distretto"})), ""]

    # --- motivi ------------------------------------------------------------------
    out += ["## 8. Perché mancano i valori", "", "Solo celle di stazioni reali (escluse le stazioni fittizie `nessuna_stazione`).", ""]
    mancanti = reali[reali["stato"] != STATO_VALORE].copy()
    mancanti["motivo"] = mancanti["nota"].fillna("").str.split(":").str[0].str.split(" \\(").str[0]
    motivi = mancanti.groupby(["fonte", "stato", "motivo"]).size().reset_index(name="celle")
    out += [_tabella(motivi.rename(columns={"fonte": "Fonte", "stato": "Stato", "motivo": "Motivo", "celle": "Celle"})), ""]

    # --- confronto tra fonti (validazione incrociata) ---------------------------------
    virtuali = [f for f in fonti if ds.proprieta_fonti.get(f, {}).get("stazioni_virtuali")]
    per_comune = media_per_comune(g, escludi_stazioni=[NESSUNA_STAZIONE] + list(
        ds.stazioni.loc[ds.stazioni["fonte"].isin(virtuali), "stazione"].unique()),
        soglie_plausibilita=SOGLIE_PLAUSIBILITA)
    dirette = [f for f in fonti if _statistica_omogenea(ds, f)]
    a_parte = [f for f in fonti if f not in dirette]

    out += ["## 9. Confronto tra fonti sulle stesse celle (validazione)", "",
            "ARPA, OpenAQ ed EEA misurano con le stesse stazioni (ARPA trasmette i dati all'EEA, OpenAQ li "
            "riprende dall'EEA): la ridondanza è voluta e serve a validare i dati. Sulle celle in cui due fonti "
            f"hanno entrambe un `VALORE` si confrontano i valori; *concordanti* = differenza entro "
            f"{SOGLIA_CONCORDANZA:g} unità (ARPA pubblica valori interi).", "",
            "**Le fonti non si leggono tutte allo stesso modo** (decisione del 02/10/2026), quindi il confronto è "
            "diviso in due blocchi.", "",
            "### 9.1 Che cosa è confrontabile con che cosa", ""]
    tab = pd.DataFrame([{
        "Fonte": f,
        "Dato": "modellato" if ds.proprieta_fonti.get(f, {}).get("modellata") else "misurato",
        "Livello del valore": "comune (stazione virtuale)" if f in virtuali else "stazione fisica",
        "Statistica giornaliera": _descrizione_statistica(ds, f) or "—",
        "Blocco": "validazione diretta" if f in dirette else "a parte",
    } for f in fonti])
    out += [_tabella(tab), "",
            f"- **Validazione diretta — {', '.join(dirette) or 'nessuna fonte'}:** producono tutte il valore "
            "giornaliero con la stessa regola (media delle ore del giorno, UTC+1, senza soglia di completezza), "
            "quindi si confrontano cella per cella e la quota di celle concordanti **misura la concordanza del "
            "dato**. Si accorpano in un unico blocco.",
            f"- **A parte — {', '.join(a_parte) or 'nessuna fonte'}:** ARPA pubblica un valore già giornaliero con "
            "la *sua* statistica (il massimo per NO2, O3, SO2 e CO). Per quegli inquinanti la differenza con le "
            "altre fonti è la distanza fra un massimo e una media: **non misura un disaccordo fra fonti** e la "
            "colonna *Concordanti* resta vuota. Il confronto si tiene come lettura qualitativa (ordine di "
            "grandezza, andamento), non come validazione.",
            "- **CAMS è l'unica fonte modellata** e non ha stazioni: il confronto si fa a **comune × giorno** "
            "contro la media delle stazioni fisiche del comune, e misura **quanto il modello somiglia alla misura "
            "nel punto** (la cella è ~10 km, la stazione un punto), non la bontà della misura.", ""]

    coppie_dirette = [(a, b) for i, a in enumerate(dirette) for b in dirette[i + 1:]]
    coppie_a_parte = [(a, b) for a in a_parte for b in fonti if b not in a_parte] + \
                     [(a, b) for i, a in enumerate(a_parte) for b in a_parte[i + 1:]]
    out += [f"### 9.2 Validazione diretta — {', '.join(dirette) or 'nessuna fonte'}", ""]
    if coppie_dirette:
        out += ["Stessa statistica su tutti gli inquinanti: le percentuali di concordanza sono quelle da leggere.", ""]
        out += _sezione_confronti(ds, coppie_dirette, per_comune, livello_comune=False)
    else:
        out += ["Meno di due fonti con statistica omogenea: nessun confronto diretto in questo periodo.", ""]
    out += [f"### 9.3 Confronti con {', '.join(a_parte) or '—'} (statistica diversa: lettura qualitativa)", ""]
    if coppie_a_parte:
        out += ["Da leggere per ordine di grandezza e andamento. Dove *Stessa statistica* è \"no\" le differenze "
                "sono attese e la concordanza non è misurabile; la correlazione resta indicativa.", ""]
        out += _sezione_confronti(ds, coppie_a_parte, per_comune, livello_comune=False)
    else:
        out += ["Nessuna fonte con statistica diversa in questo periodo.", ""]

    # --- copertura misurata o modellata ----------------------------------------------
    misurate, comuni_misurati = fonti_misurate, comuni_con_misura
    modellate = [f for f in fonti if ds.proprieta_fonti.get(f, {}).get("modellata")]
    solo_modellati = set(valori.loc[valori["fonte"].isin(modellate), "comune"]) - comuni_misurati
    distretti_misurati = set(valori.loc[valori["fonte"].isin(misurate), "distretto"])
    quote = quota_residenti_coperta(per_comune)
    out += ["## 10. Copertura: dato misurato o dato modellato", "",
            "Dichiarazione necessaria per ogni analisi e per ogni correlazione che usa questo dataset: dove non "
            "ci sono stazioni, l'unico valore disponibile è **modellato** (CAMS, cella ~10 km).", "",
            f"- **Comuni con almeno un valore misurato** ({', '.join(misurate) or '—'}): "
            f"**{len(comuni_misurati)} su {g['comune'].nunique()}**",
            f"- **Comuni coperti solo da dato modellato** ({', '.join(modellate) or '—'}): **{len(solo_modellati)}**",
            f"- **Distretti con almeno un valore misurato:** **{len(distretti_misurati)} su {n_distretti}**",
            "- **Quota di residenti del distretto che vive in un comune con almeno una misura** "
            "(media pesata sui residenti, regola del 02/10/2026): v. tabella", "",
            "**Come va letta una correlazione su questi dati:** i comuni e i distretti senza stazioni entrano "
            "nelle analisi con il valore CAMS, quindi la correlazione che li riguarda è calcolata **su dato "
            "modellato, non misurato**. La correlazione si calcola comunque — serve a leggere l'andamento dove "
            "non esistono stazioni — ma va sempre presentata con questa etichetta, nel report e in dashboard.", ""]
    righe = []
    for d in sorted(nomi_distretti):
        comuni_d = set(g.loc[g["distretto"] == d, "comune"])
        righe.append({
            "Distretto": d, "Comune sede": nomi_distretti[d], "Comuni": len(comuni_d),
            "Comuni con misura": len(comuni_d & comuni_misurati),
            "Comuni solo modellati": len(comuni_d & solo_modellati),
            "Residenti coperti da misura": f"{quote.get(d, 0):.0%}",
            "Lettura": "misurato" if d in distretti_misurati else "solo modellato",
        })
    out += [_tabella(pd.DataFrame(righe)), ""]

    # --- errori --------------------------------------------------------------------
    out += ["## 11. Errori delle API", ""]
    if ds.errori:
        err = pd.DataFrame(ds.errori)
        out += [_tabella(err.groupby(["fonte", "tipo"]).size().reset_index(name="numero")), "",
                "Dettaglio in `data/interim/aria/errori_api.csv`.", ""]
    else:
        out += ["Nessun errore.", ""]
    if ds.avvisi:
        out += ["### Avvisi", ""] + [f"- {a}" for a in ds.avvisi] + [""]
    return "\n".join(out)
