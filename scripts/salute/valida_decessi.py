#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validazione per ridondanza del dato di mortalità, come già si fa per l'aria con
ARPA ↔ OpenAQ ↔ EEA (v. report dell'aria, sez. 9). Confronta i **decessi comunali
giornalieri ISTAT** (canale A, la fonte del dataset salute) con due pubblicazioni
indipendenti che coprono gli stessi decessi a grana più grossa:

  1. **ISTAT bilancio demografico mensile** (canale D, `demo.istat.it`, 2019-2024):
     comune × mese. Altra pubblicazione, altro flusso (anagrafe invece delle schede
     di morte): il confronto è un controllo vero, non una tautologia.
  2. **Eurostat `demo_r_mwk3_t`**: provincia (NUTS 3) × settimana ISO. Sono gli stessi
     dati che ISTAT trasmette a Eurostat, quindi dovrebbero coincidere quasi
     esattamente: verifica la nostra sommatoria più che la fonte.

Il confronto si fa **solo sui periodi completi** (tutti i giorni del mese o della
settimana con stato `VALORE` per tutti i comuni coinvolti): un mese a metà
sembrerebbe un disaccordo e non lo è. Le celle escluse sono dichiarate nel report.
L'ultima sezione ripete il confronto alla **grana di presentazione decisa il
02/10/2026, distretto × mese** (docs/Regole_dei_dati.md), che è anche la grana del
confronto con aria e calore.

Uso (dalla radice del repo; serve prima scripts/salute/scarica_decessi_istat.py):
  uv run scripts/salute/valida_decessi.py
  uv run scripts/salute/valida_decessi.py --anni 2023 2024
  uv run scripts/salute/valida_decessi.py --senza-eurostat

Output:
  data/dataset/salute/report/Report_validazione_decessi.md   report di validazione
  data/interim/salute/validazione/decessi_fonti_*.csv        le tabelle del confronto per la tab «Fonti a
                                                             confronto» della dashboard (gitignored), così il
                                                             server non chiama Eurostat (legge solo la cache):
                                                             distretto × mese e provincia × mese, mai sotto il
                                                             mese (privacy, docs/Regole_dei_dati.md)
  data/interim/salute/errori_api.csv                         errori, in accodamento (gitignored)
"""

import argparse
import csv
import json
import sys
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path

import pandas as pd

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))

from api.comune.aggregazione import per_mese, somma_per_distretto  # noqa: E402
from api.comune.stati import STATO_VALORE  # noqa: E402
from api.salute import eurostat, istat  # noqa: E402

TERRITORIO = RADICE / "data" / "territorio" / "anagrafica" / "territorio.json"
DECESSI = RADICE / "data" / "interim" / "salute" / "istat" / "decessi_giornalieri_salento.csv"
DIR_REPORT = RADICE / "data" / "dataset" / "salute" / "report"
FILE_ERRORI = RADICE / "data" / "interim" / "salute" / "errori_api.csv"
DIR_DASHBOARD = RADICE / "data" / "interim" / "salute" / "validazione"
FILE_DISTRETTO_MESE = DIR_DASHBOARD / "decessi_fonti_distretto_mese.csv"
FILE_PROVINCIA_MESE = DIR_DASHBOARD / "decessi_fonti_provincia_mese.csv"
FILE_PROVINCIA_SETTIMANA = DIR_DASHBOARD / "decessi_fonti_provincia_settimana.csv"  # versione del 27/10, da cancellare


def _tabella(df):
    """DataFrame -> tabella Markdown (come nel report dell'aria)."""
    if df.empty:
        return "_nessuna riga_"
    righe = ["| " + " | ".join(str(c) for c in df.columns) + " |", "|" + "---|" * len(df.columns)]
    for r in df.itertuples(index=False):
        righe.append("| " + " | ".join("" if pd.isna(v) else (f"{v:g}" if isinstance(v, float) else str(v))
                                       for v in r) + " |")
    return "\n".join(righe)


def _pct(parte, totale):
    return f"{100 * parte / totale:.1f}%" if totale else "—"


def carica_territorio():
    """(comuni, {id_comune: (id_distretto, residenti)}, {id_distretto: comune sede})."""
    tabelle = json.loads(TERRITORIO.read_text(encoding="utf-8"))["tabelle"]
    comuni = tabelle["comuni"]
    pesi = {c["id_comune"]: (c["id_distretto"], c["residenti"] or 0) for c in comuni}
    nomi = {c["id_comune"]: c["denominazione"] for c in comuni}
    return comuni, pesi, nomi


def carica_giornalieri():
    """Decessi giornalieri per comune (canale A), come li ha scritti scarica_decessi_istat.py."""
    if not DECESSI.exists():
        sys.exit(f"Manca {DECESSI.relative_to(RADICE)}: lanciare prima "
                 "`uv run scripts/salute/scarica_decessi_istat.py`.")
    d = pd.read_csv(DECESSI, dtype={"id_comune": str}, parse_dates=["data"])
    return d.rename(columns={"decessi": "valore", "data": "giorno", "id_comune": "comune"})


#  Rete di sicurezza storica: fino al 14/10/2026 l'anagrafica del territorio teneva
#  Presicce (075062) e Acquarica del Capo (075001) come due comuni, mentre ISTAT pubblica
#  da sempre il solo comune fuso Presicce-Acquarica (075098), ripetuto dal client sui due
#  componenti — ogni somma su più comuni lo contava due volte. Dal 14/10/2026 l'anagrafica
#  tiene un solo comune (075098, v. scripts/territorio/costruisci_anagrafica_territorio.py,
#  FUSIONI_COMUNE): la funzione sotto resta solo per i CSV intermedi generati prima di
#  quella data (gitignored: se rigenerati da zero non hanno più righe doppie).
_VECCHI_COMPONENTI_FUSI = ["075001"]  # scartato; 075062 (il primo) è tenuto


def senza_duplicati_fusi(celle, colonna="comune"):
    """Toglie la ripetizione dei **comuni fusi** prima di qualunque somma su più comuni
    (v. nota sopra). Normalmente un no-op: non-op se i CSV sono stati rigenerati dopo
    la fusione in anagrafica."""
    doppi = [c for c in _VECCHI_COMPONENTI_FUSI if c in set(celle[colonna])]
    return celle[~celle[colonna].isin(doppi)], doppi


def mensile_da_giornaliero(giornalieri):
    """Decessi per comune × mese sommando i giorni, con i soli mesi **completi**
    (tutti i giorni con `VALORE`): gli altri restano, marcati come incompleti."""
    mensile = per_mese(giornalieri, funzione="somma", colonna_tempo="giorno", chiavi=(), colonna_zona="comune")
    mensile["completo"] = mensile["giorni_con_valore"] == mensile["giorni"]
    return mensile


def confronta(a, b, chiave, nome_a, nome_b):
    """Tabella di confronto fra due serie di conteggi sulle stesse celle."""
    insieme = a.merge(b, on=chiave, suffixes=(f"_{nome_a}", f"_{nome_b}"))
    if insieme.empty:
        return insieme, None
    va, vb = f"valore_{nome_a}", f"valore_{nome_b}"
    insieme["diff"] = insieme[vb] - insieme[va]
    riepilogo = {
        "Celle confrontate": len(insieme),
        "Identiche": _pct(int((insieme["diff"] == 0).sum()), len(insieme)),
        "Entro ±1": _pct(int((insieme["diff"].abs() <= 1).sum()), len(insieme)),
        f"Totale {nome_a}": int(insieme[va].sum()),
        f"Totale {nome_b}": int(insieme[vb].sum()),
        "Diff. totale": int(insieme["diff"].sum()),
        "Diff. media": round(float(insieme["diff"].mean()), 3),
        "Diff. assoluta massima": int(insieme["diff"].abs().max()),
        "Correlazione (Pearson)": round(float(insieme[va].corr(insieme[vb])), 4) if len(insieme) > 2 else None,
    }
    return insieme, riepilogo


def _distretto_mese_dashboard(mensile, pesi, fonte):
    """Distretto × mese per la dashboard, alla grana consentita dalla privacy (docs/Regole_dei_dati.md). Un mese incompleto
    nel canale A o una somma che non copre tutti i comuni del distretto diventa `NULL` col motivo: sembrerebbe un
    disaccordo con l'altra fonte e non lo è."""
    m = mensile.copy()
    if "completo" in m.columns:
        incompleti = (m["stato"] == STATO_VALORE) & ~m["completo"]
        m.loc[incompleti, "nota"] = [f"mese incompleto nel canale A ({r.giorni_con_valore} giorni su {r.giorni})"
                                     for r in m[incompleti].itertuples()]
        m.loc[incompleti, ["stato", "valore"]] = "NULL", float("nan")
    d = somma_per_distretto(m, pesi=pesi, colonna_tempo="mese")
    totali = pd.Series([dist for dist, _ in pesi.values()]).value_counts()
    parziali = (d["stato"] == STATO_VALORE) & (d["comuni_con_valore"] < d["distretto"].map(totali))
    d.loc[parziali, "nota"] = [f"somma parziale ({r.comuni_con_valore} comuni su {totali[r.distretto]}): non confrontabile"
                               for r in d[parziali].itertuples()]
    d.loc[parziali, ["stato", "valore"]] = "NULL", float("nan")
    d["fonte"] = fonte
    return d[["fonte", "distretto", "mese", "valore", "stato", "nota", "comuni_con_valore"]]


def _giovedi_nel_mese(mese):
    """Quante settimane ISO hanno il giovedì nel mese 'AAAA-MM' (4 o 5): quelle che il mese deve sommare."""
    anno, m = int(mese[:4]), int(mese[5:])
    return sum(1 for g in range(1, monthrange(anno, m)[1] + 1) if date(anno, m, g).weekday() == 3)


def _provincia_mese(settimane):
    """Dalla settimana ISO al mese per la dashboard (scelta di Matteo del 27/10/2026: la regola §7 dice mese).
    Eurostat pubblica solo settimane, che possono cadere a cavallo di due mesi e non si spezzano senza il dato
    giornaliero: ogni settimana va al mese del suo **giovedì** (convenzione ISO), e lo stesso vale per la somma
    ISTAT, così i due lati restano confrontabili. Un mese è VALORE solo se tutte le sue settimane lo sono."""
    s = settimane.copy()
    s["mese"] = [date.fromisocalendar(int(w[:4]), int(w[6:]), 4).strftime("%Y-%m") for w in s["settimana"]]
    out = []
    for (fonte, prov, mese), g in s.groupby(["fonte", "id_provincia", "mese"]):
        attese, con_valore = _giovedi_nel_mese(mese), int((g["stato"] == STATO_VALORE).sum())
        if con_valore == attese:
            stato, valore = STATO_VALORE, float(g["valore"].sum())
            nota = f"somma di {attese} settimane ISO (quelle con il giovedì nel mese)"
        elif con_valore == 0 and (g["stato"] == "NO_DATA").all():
            stato, valore, nota = "NO_DATA", None, "mese fuori dalla copertura della fonte"
        else:
            stato, valore = "NULL", None
            nota = f"{con_valore} settimane ISO su {attese} con un valore: somma del mese incompleta"
        out.append({"fonte": fonte, "id_provincia": prov, "mese": mese, "valore": valore, "stato": stato, "nota": nota})
    return pd.DataFrame(out)


def scrivi_tabelle_dashboard(mensile, mensile_bilancio, pesi, settimane_a, eurostat_settimane):
    """Le tabelle che la tab «Fonti a confronto» legge: distretto × mese (A, D) e provincia × mese (A, Eurostat).
    Il server legge solo questi file: nessuna chiamata a Eurostat dentro una richiesta HTTP."""
    DIR_DASHBOARD.mkdir(parents=True, exist_ok=True)
    mese = [_distretto_mese_dashboard(mensile, pesi, "A")]
    if mensile_bilancio:
        mese.append(_distretto_mese_dashboard(pd.concat(mensile_bilancio, ignore_index=True), pesi, "D"))
    pd.concat(mese, ignore_index=True).to_csv(FILE_DISTRETTO_MESE, index=False)
    FILE_PROVINCIA_SETTIMANA.unlink(missing_ok=True)  # grana settimanale non più usata dalla dashboard (27/10/2026)
    settimana = []
    if settimane_a is not None:
        a = settimane_a.copy()
        completa = (a["celle"] == a["con_valore"]) & (a["giorni"] == 7)
        a["stato"] = [STATO_VALORE if c else "NO_DATA" if r.con_valore == 0 else "NULL"
                      for c, r in zip(completa, a.itertuples())]
        a["nota"] = [None if c else "settimana fuori dalla copertura del rilascio ISTAT" if r.con_valore == 0
                     else f"settimana incompleta nel canale A ({r.giorni} giorni su 7, {r.con_valore} celle "
                     f"comune × giorno con valore su {r.celle})" for c, r in zip(completa, a.itertuples())]
        a.loc[~completa, "valore"] = float("nan")
        settimana.append(a.assign(fonte="A")[["fonte", "id_provincia", "settimana", "valore", "stato", "nota"]])
    if eurostat_settimane is not None:
        e = eurostat_settimane.rename(columns={"decessi": "valore"})
        settimana.append(e.assign(fonte="Eurostat")[["fonte", "id_provincia", "settimana", "valore", "stato", "nota"]])
    if settimana:
        _provincia_mese(pd.concat(settimana, ignore_index=True)).to_csv(FILE_PROVINCIA_MESE, index=False)
    return [FILE_DISTRETTO_MESE] + ([FILE_PROVINCIA_MESE] if settimana else [])


def peggiori(insieme, chiave, nome_a, nome_b, quante=10):
    discordi = insieme[insieme["diff"] != 0]
    if discordi.empty:
        return None, 0
    ordinate = discordi.reindex(discordi["diff"].abs().sort_values(ascending=False).index).head(quante)
    return ordinate[chiave + [f"valore_{nome_a}", f"valore_{nome_b}", "diff"]], len(discordi)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Valida i decessi giornalieri ISTAT contro bilancio mensile ed Eurostat.")
    ap.add_argument("--anni", nargs=2, type=int, metavar=("DA", "A"),
                    default=[istat.ANNI_BILANCIO.start, istat.ANNI_BILANCIO.stop - 1],
                    help="anni del bilancio demografico mensile da confrontare (default: tutti quelli pubblicati)")
    ap.add_argument("--senza-eurostat", action="store_true", help="salta il confronto settimanale con Eurostat")
    args = ap.parse_args()

    comuni, pesi, nomi_comuni = carica_territorio()
    ids = [c["id_comune"] for c in comuni]
    provincia_del_comune = {c["id_comune"]: c["id_distretto"][:2] for c in comuni}
    giornalieri = carica_giornalieri()
    mensile = mensile_da_giornaliero(giornalieri)
    errori = []

    out = [
        "# Report validazione decessi — ISTAT giornaliero ↔ bilancio mensile ↔ Eurostat",
        "",
        f"Generato il {datetime.now().isoformat(timespec='seconds')} da `scripts/salute/valida_decessi.py`. "
        "Validazione per ridondanza del dato di mortalità (stessa logica della sez. 9 del report dell'aria): "
        "tre pubblicazioni che coprono gli **stessi** decessi a grane diverse devono tornare fra loro. "
        "Nessuna delle tre ha la causa di morte.",
        "",
        "Il confronto usa **solo i periodi completi** nel canale A (tutti i giorni con stato `VALORE`): "
        "un mese o una settimana a metà sembrerebbero un disaccordo e non lo sono.",
        "",
        "## 1. Dati di partenza",
        "",
        f"- **Canale A — decessi comunali giornalieri:** `{DECESSI.relative_to(RADICE).as_posix()}`, "
        f"{len(giornalieri):,} righe".replace(",", ".") + f", {giornalieri['comune'].nunique()} comuni, "
        f"{giornalieri['giorno'].min().date()} → {giornalieri['giorno'].max().date()}",
        "- **Stati nel canale A:** " + ", ".join(f"{s}={n}" for s, n in giornalieri["stato"].value_counts().items()),
        f"- **Mesi completi** (tutti i giorni con `VALORE`): {int(mensile['completo'].sum())} su {len(mensile)} "
        f"celle comune × mese",
        "",
    ]

    # --- 2. canale A ↔ bilancio mensile (comune × mese) --------------------------------
    out += ["## 2. Comune × mese — canale A (somma dei giorni) ↔ bilancio demografico mensile (canale D)", "",
            "Due pubblicazioni ISTAT distinte e due flussi diversi (schede di morte / anagrafe): è il "
            "confronto più informativo dei tre. Scarto residuo atteso, perché il canale A è **provvisorio** "
            "e il bilancio è di fonte anagrafica.", ""]
    confronti_annuali, mensile_bilancio = [], []
    for anno in range(args.anni[0], args.anni[1] + 1):
        try:
            percorso = istat.scarica_bilancio_mensile(anno)
            bilancio = istat.leggi_bilancio_mensile(percorso, ids)
        except istat.IstatError as exc:
            errori.append({"fonte": "ISTAT bilancio mensile", "chiamata": f"anno {anno}",
                           "tipo": "errore_api", "errore": str(exc)})
            out += [f"- **{anno}:** non confrontato — {exc}", ""]
            continue
        bilancio = bilancio.rename(columns={"id_comune": "comune", "morti": "valore"})
        bilancio["mese"] = bilancio["anno"].astype(str) + "-" + bilancio["mese"].map(lambda m: f"{m:02d}")
        mensile_bilancio.append(bilancio)
        a = mensile[mensile["completo"] & mensile["mese"].str.startswith(str(anno))][["comune", "mese", "valore", "stato"]]
        a = a[a["stato"] == STATO_VALORE]
        b = bilancio[bilancio["stato"] == STATO_VALORE][["comune", "mese", "valore"]]
        insieme, riepilogo = confronta(a[["comune", "mese", "valore"]], b, ["comune", "mese"], "A", "D")
        if riepilogo is None:
            out += [f"- **{anno}:** nessuna cella confrontabile (mesi completi mancanti).", ""]
            continue
        confronti_annuali.append({"Anno": anno, **riepilogo})
        confronti_annuali[-1]["_insieme"] = insieme
    if confronti_annuali:
        tabella = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in confronti_annuali])
        out += [_tabella(tabella), ""]
        tutte = pd.concat([r["_insieme"] for r in confronti_annuali], ignore_index=True)
        righe, n_discordi = peggiori(tutte, ["comune", "mese"], "A", "D")
        if righe is not None:
            righe = righe.assign(comune=righe["comune"].map(lambda c: f"{c} ({nomi_comuni.get(c, '?')})"))
            out += [f"Celle più discordanti (prime {len(righe)} di {n_discordi} celle non identiche):", "",
                    _tabella(righe), ""]
        else:
            out += ["Nessuna cella discordante: le due pubblicazioni coincidono su tutte le celle confrontate.", ""]
    else:
        out += ["Nessun anno confrontabile.", ""]

    # --- 3. canale A ↔ Eurostat (provincia × settimana) --------------------------------
    out += ["## 3. Provincia × settimana ISO — canale A (somma) ↔ Eurostat `demo_r_mwk3_t`", "",
            "Eurostat ridistribuisce i decessi che ISTAT gli trasmette: il confronto verifica **la nostra "
            "sommatoria** più che la fonte, quindi uno scarto qui va indagato come un errore nostro. "
            "Si confrontano solo le settimane ISO con tutti i 7 giorni `VALORE` per tutti i comuni "
            "della provincia.", ""]
    settimane_a = eurostat_settimane = None
    if args.senza_eurostat:
        out += ["Confronto saltato (`--senza-eurostat`).", ""]
    else:
        g, doppi = senza_duplicati_fusi(giornalieri.copy())
        g["id_provincia"] = g["comune"].map(provincia_del_comune)
        iso = g["giorno"].dt.isocalendar()
        g["settimana"] = iso["year"].astype(str) + "-W" + iso["week"].map(lambda s: f"{s:02d}")
        per_settimana = g.groupby(["id_provincia", "settimana"]).agg(
            valore=("valore", "sum"),
            celle=("stato", "size"),
            con_valore=("stato", lambda s: (s == STATO_VALORE).sum()),
            giorni=("giorno", "nunique"),
        ).reset_index()
        complete = per_settimana[(per_settimana["celle"] == per_settimana["con_valore"]) & (per_settimana["giorni"] == 7)]
        settimane_a = per_settimana
        try:
            eu = eurostat.decessi_settimanali(da_settimana=complete["settimana"].min(),
                                              a_settimana=complete["settimana"].max())
            eurostat_settimane = eu
            eu_valori = eu[eu["stato"] == STATO_VALORE].rename(columns={"decessi": "valore"})
            insieme, riepilogo = confronta(complete[["id_provincia", "settimana", "valore"]],
                                           eu_valori[["id_provincia", "settimana", "valore"]],
                                           ["id_provincia", "settimana"], "A", "Eurostat")
            out += [f"- Settimane ISO complete nel canale A: **{len(complete)}** su {len(per_settimana)} "
                    f"(le altre sono a cavallo di due anni o della fine della copertura)",
                    f"- Comuni esclusi dalla somma perché ripetizione di un comune fuso: "
                    f"{', '.join(doppi) or 'nessuno'} (v. sezione 5)",
                    f"- Serie Eurostat: {len(eu)} settimane, aggiornata al {eu.attrs.get('aggiornato_il')}", ""]
            if riepilogo is None:
                out += ["Nessuna settimana in comune fra le due serie.", ""]
            else:
                out += [_tabella(pd.DataFrame([riepilogo])), ""]
                per_provincia = []
                for provincia, c in insieme.groupby("id_provincia"):
                    per_provincia.append({
                        "Provincia": provincia, "Settimane": len(c),
                        "Identiche": _pct(int((c["diff"] == 0).sum()), len(c)),
                        "Totale A": int(c["valore_A"].sum()), "Totale Eurostat": int(c["valore_Eurostat"].sum()),
                        "Diff. totale": int(c["diff"].sum()),
                        "Diff. assoluta massima": int(c["diff"].abs().max()),
                    })
                per_anno = []
                for anno, c in insieme.groupby(insieme["settimana"].str[:4]):
                    per_anno.append({"Anno": anno, "Settimane": len(c),
                                     "Identiche": _pct(int((c["diff"] == 0).sum()), len(c)),
                                     "Diff. totale": int(c["diff"].sum()),
                                     "Diff. assoluta massima": int(c["diff"].abs().max())})
                out += [_tabella(pd.DataFrame(per_provincia)), "",
                        "Le stesse settimane per anno: serve a vedere se lo scarto è sparso o concentrato negli "
                        "anni più recenti, dove Eurostat riceve i dati con qualche mese di ritardo rispetto al "
                        "rilascio ISTAT (scarto di revisione, non di merito).", "",
                        _tabella(pd.DataFrame(per_anno)), ""]
                righe, n_discordi = peggiori(insieme, ["id_provincia", "settimana"], "A", "Eurostat")
                if righe is not None:
                    out += [f"Settimane più discordanti (prime {len(righe)} di {n_discordi}):", "",
                            _tabella(righe), ""]
        except eurostat.EurostatError as exc:
            errori.append({"fonte": "Eurostat", "chiamata": eurostat.DATASET_DECESSI,
                           "tipo": "errore_api", "errore": str(exc)})
            out += [f"Confronto non eseguito: {exc}", ""]

    # --- 4. grana di presentazione: distretto × mese -----------------------------------
    out += ["## 4. Distretto × mese — la grana del confronto e della dashboard", "",
            "Grana decisa il 02/10/2026 (docs/Regole_dei_dati.md): i decessi si **sommano** sui comuni del distretto "
            "(per i conteggi la media pesata sui residenti non ha senso; la media pesata si usa per aria e "
            "calore, che sono concentrazioni e temperature). È anche la grana minima comune ad aria, salute "
            "e calore, e il minimo consentito in dashboard per la privacy (docs/Regole_dei_dati.md).", ""]
    mensile_valido, _ = senza_duplicati_fusi(mensile[mensile["completo"] & (mensile["stato"] == STATO_VALORE)])
    distretto_a = somma_per_distretto(mensile_valido, pesi=pesi, colonna_tempo="mese")
    out += [f"- Celle distretto × mese dal canale A: **{len(distretto_a)}**, di cui "
            f"{int((distretto_a['stato'] == STATO_VALORE).sum())} con valore",
            f"- Distretti coperti: {distretto_a.loc[distretto_a['stato'] == STATO_VALORE, 'distretto'].nunique()} su 20", ""]
    if mensile_bilancio:
        bilancio_tutto = pd.concat(mensile_bilancio, ignore_index=True)
        bilancio_tutto, _ = senza_duplicati_fusi(bilancio_tutto[bilancio_tutto["stato"] == STATO_VALORE])
        distretto_d = somma_per_distretto(bilancio_tutto, pesi=pesi, colonna_tempo="mese")
        insieme, riepilogo = confronta(
            distretto_a[distretto_a["stato"] == STATO_VALORE][["distretto", "mese", "valore"]],
            distretto_d[distretto_d["stato"] == STATO_VALORE][["distretto", "mese", "valore"]],
            ["distretto", "mese"], "A", "D")
        if riepilogo is not None:
            out += ["Lo stesso confronto della sezione 2, aggregato alla grana di presentazione:", "",
                    _tabella(pd.DataFrame([riepilogo])), ""]
            righe, n_discordi = peggiori(insieme, ["distretto", "mese"], "A", "D")
            if righe is not None:
                out += [f"Celle più discordanti (prime {len(righe)} di {n_discordi}):", "", _tabella(righe), ""]

    # --- 5. limiti --------------------------------------------------------------------
    out += ["## 5. Limiti dichiarati", "",
            "- **Nessuna delle tre fonti ha la causa di morte**: questa validazione riguarda i decessi "
            "**per tutte le cause**. Per causa la grana pubblica massima resta provincia × anno "
            "(ISTAT SDMX), v. `data/dataset/salute/Lista_dataset_salute.md`.",
            "- Il canale A è **provvisorio** e si aggiorna a ogni rilascio: un rilascio nuovo può cambiare "
            "i valori degli anni recenti. Il bilancio mensile si ferma al **2024** come file scaricabile.",
            "- Eurostat **non è indipendente** da ISTAT: coincidenza attesa, non è una conferma esterna.",
            "- **Comuni fusi.** ISTAT pubblica un solo valore per Presicce-Acquarica (075098): fino al "
            "14/10/2026 l'anagrafica del territorio teneva Presicce e Acquarica del Capo come due comuni "
            "separati e il client ripeteva quel valore su entrambi, quindi ogni somma su più comuni "
            "(provincia, distretto) lo contava due volte — è l'errore che questo confronto ha fatto emergere "
            "alla prima esecuzione (provincia di Lecce fuori scala rispetto a Brindisi e Taranto). **Chiuso "
            "il 14/10/2026**: l'anagrafica rappresenta ora Presicce-Acquarica come un solo comune (075098, "
            "residenti sommati), coerente con ISTAT.",
            "- Licenza di entrambi i canali ISTAT e di Eurostat: **CC BY 4.0**.", ""]
    if errori:
        out += ["## 6. Errori", "", _tabella(pd.DataFrame(errori)), "",
                f"Dettaglio in `{FILE_ERRORI.relative_to(RADICE).as_posix()}`.", ""]
        FILE_ERRORI.parent.mkdir(parents=True, exist_ok=True)
        nuovo = not FILE_ERRORI.exists()
        with open(FILE_ERRORI, "a", encoding="utf-8", newline="") as f:
            scrittore = csv.DictWriter(f, fieldnames=["istante", "fonte", "chiamata", "tipo", "errore"])
            if nuovo:
                scrittore.writeheader()
            for e in errori:
                scrittore.writerow({"istante": datetime.now().isoformat(timespec="seconds"), **e})

    DIR_REPORT.mkdir(parents=True, exist_ok=True)
    file_report = DIR_REPORT / "Report_validazione_decessi.md"
    file_report.write_text("\n".join(out), encoding="utf-8")
    print(f"Report: {file_report.relative_to(RADICE)}")
    for f in scrivi_tabelle_dashboard(mensile, mensile_bilancio, pesi, settimane_a, eurostat_settimane):
        print(f"Tabella per la dashboard: {f.relative_to(RADICE)}")
    print(f"Errori: {len(errori)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
