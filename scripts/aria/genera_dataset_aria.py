#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Costruisce ed estende l'archivio del dataset aria multi-fonte, **un mese alla
volta e giorno per giorno** (v. api/aria/archivio_aria.py, api/aria/dataset_aria.py,
api/aria/report_aria.py e docs/Regole_dei_dati.md).

Il periodo richiesto viene spezzato sui mesi di calendario: ogni mese è un file in
data/interim/aria/. I mesi già completi **si saltano**, quindi un anno chiuso si
scarica una volta sola e resta in locale, mentre il mese aperto si rigenera e
sostituisce il file precedente dello stesso mese. L'esecuzione è riprendibile:
se si interrompe, basta rilanciarla con lo stesso periodo.

Uso (dalla radice del repo; --env-file serve per la chiave OpenAQ):
  uv run --env-file .env scripts/aria/genera_dataset_aria.py                       # solo ieri
  uv run --env-file .env scripts/aria/genera_dataset_aria.py --da 2025-01-01 --a 2025-12-31
  uv run --env-file .env scripts/aria/genera_dataset_aria.py --continua            # dal primo giorno
                                                                                   # scoperto a ieri
  uv run --env-file .env scripts/aria/genera_dataset_aria.py --da 2026-01-01 --rigenera

Aggiornamento quotidiano: `--continua` rigenera il solo mese aperto e aggiunge i
giorni nuovi fino a ieri, senza toccare i mesi già archiviati.

Un mese già archiviato si rifà comunque se è stato generato con un elenco di comuni
diverso da quello dell'anagrafica attuale (motivo "anagrafica", v. api/aria/archivio_aria.py):
dopo una fusione di comuni conviene prima correggerlo offline con
scripts/aria/correggi_comuni_fusi.py, che non richiama le fonti.

Output:
  data/interim/aria/dataset_aria_<da>_<a>.json             un file per mese (gitignored)
  data/interim/aria/errori_api.csv                         errori, in accodamento (gitignored)
  data/dataset/aria/report/Report_dataset_aria_<da>_<a>.md report per mese (--senza-report lo salta)
  data/dataset/aria/report/Copertura_archivio_aria.md      copertura di tutto l'archivio, mese per mese
  data/dataset/aria/anagrafica/stazioni.json               + stazioni nuove, collegate al comune
  data/dataset/aria/anagrafica/inquinanti.json             + inquinanti nuovi e stazioni che li misurano
  data/interim/aria/riepilogo_errori.md                    + una riga di riepilogo per esecuzione, solo se
                                                             ci sono errori, zone non elencate
                                                             o inquinanti nuovi (gitignored)
"""

import argparse
import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # radice del repo, per il package api
from api.aria.anagrafica_aria import aggiorna_anagrafiche_aria, carica_comuni, inquinanti_tracciati  # noqa: E402
from api.aria.archivio_aria import (  # noqa: E402
    aggiorna_copertura,
    file_superati,
    impronta_territorio,
    nome_file,
    stato_blocchi,
    ultimo_giorno_coperto,
)
from api.aria.dataset_aria import a_json, costruisci_dataset_aria  # noqa: E402
from api.aria.report_aria import genera_report  # noqa: E402

RADICE = Path(__file__).resolve().parents[2]
DIR_OUTPUT = RADICE / "data" / "interim" / "aria"
DIR_REPORT = RADICE / "data" / "dataset" / "aria" / "report"
FILE_ERRORI = DIR_OUTPUT / "errori_api.csv"
FILE_RIEPILOGO = DIR_OUTPUT / "riepilogo_errori.md"


def _registra_errori(errori, istante):
    FILE_ERRORI.parent.mkdir(parents=True, exist_ok=True)
    nuovo = not FILE_ERRORI.exists()
    with open(FILE_ERRORI, "a", encoding="utf-8", newline="") as f:
        scrittore = csv.DictWriter(f, fieldnames=["istante", "fonte", "chiamata", "tipo", "errore"])
        if nuovo:
            scrittore.writeheader()
        for e in errori:
            scrittore.writerow({"istante": istante, **e})


def _riga_riepilogo(corse, da, a):
    """Una riga di riepilogo per *esecuzione* (non per mese), con quanto va guardato a mano:
    errori delle API, zone e distretti che le fonti dichiarano fuori dalla lista nota,
    stazioni senza comune e inquinanti nuovi aggiunti alla lista tracciata.
    Va in data/interim/aria/riepilogo_errori.md, accanto a errori_api.csv (pipeline multi-fonte).
    `corse`: [(ds, riepilogo_anagrafiche)] dei mesi generati in questa esecuzione."""
    if not corse:
        return None
    todo_attuale = FILE_RIEPILOGO.read_text(encoding="utf-8") if FILE_RIEPILOGO.exists() else ""
    parti = []

    tipi = {}
    for ds, _ in corse:
        for e in ds.errori:
            tipi[e["tipo"]] = tipi.get(e["tipo"], 0) + 1
    if tipi:
        parti.append(f"{sum(tipi.values())} errori ({', '.join(f'{n} {t}' for t, n in sorted(tipi.items()))}), "
                     "dettaglio in `data/interim/aria/errori_api.csv`")

    # (a) zone restituite dalle fonti che non stanno nella lista nota dei distretti:
    #     stazioni non riconducibili a nessun comune del Salento. Si segnalano solo
    #     quelle non ancora citate nel riepilogo, una volta sola per esecuzione.
    fuori = {f"{s.fonte} {s.id_fonte} \"{s.denominazione}\""
             for ds, _ in corse for s in ds.fuori_area.itertuples(index=False)
             if f"{s.fonte} {s.id_fonte} " not in todo_attuale}
    if fuori:
        parti.append("stazioni fuori dai distretti noti, da analizzare: " + "; ".join(sorted(fuori)))

    # (a bis) distretto dichiarato dalla fonte diverso da quello del comune nell'anagrafica
    discrepanze = {d for _, r in corse for d in (r or {}).get("discrepanze", [])
                   if d.split(":")[0] not in todo_attuale}
    if discrepanze:
        parti.append("distretti dichiarati dalle fonti diversi da quelli dell'anagrafica, da verificare: "
                     + "; ".join(sorted(discrepanze)))

    # stazioni senza comune (fuori dal Salento, confine condiviso, ...): quelle non già segnalate sopra
    gia_fuori = {str(s) for ds, _ in corse for s in ds.fuori_area["stazione"]}
    senza_comune = {s for _, r in corse for s in (r or {}).get("stazioni_senza_comune", [])
                    if s not in gia_fuori and f"stazione {s} senza comune" not in todo_attuale}
    if senza_comune:
        parti.append("stazioni senza comune in `anagrafica/stazioni.json` (motivo nella colonna `nota`), "
                     "da assegnare a mano: " + ", ".join(f"stazione {s} senza comune" for s in sorted(senza_comune)))

    # (b) inquinanti osservati e non ancora tracciati: aggiunti da aggiorna_anagrafiche_aria
    nuovi = sorted({i for ds, _ in corse for i in ds.inquinanti_nuovi})
    if nuovi:
        parti.append(f"inquinanti nuovi aggiunti a `anagrafica/inquinanti.json` ({', '.join(nuovi)}): "
                     "valutare se va fra gli inquinanti di riferimento della dashboard")

    if not parti:
        return None
    mesi = ", ".join(f"{ds.data_inizio.isoformat()} → {ds.data_fine.isoformat()}" for ds, _ in corse[:3])
    if len(corse) > 3:
        mesi += f", … ({len(corse)} mesi)"
    return (f"\n- [ ] **[{date.today().strftime('%d/%m/%Y')}]** **Archivio aria {da.isoformat()} → {a.isoformat()}"
            f"** (mesi generati: {mesi})**:** " + "; ".join(parti)
            + ". Copertura: `data/dataset/aria/report/Copertura_archivio_aria.md`.\n")


def _genera_blocco(inizio, fine, tracciati, senza_report):
    """Genera il file (e il report) di un mese. Restituisce (ds, riepilogo_anagrafiche)."""
    ds = costruisci_dataset_aria(inizio, fine, inquinanti_tracciati=list(tracciati))

    DIR_OUTPUT.mkdir(parents=True, exist_ok=True)
    file_dataset = DIR_OUTPUT / nome_file(ds.data_inizio, ds.data_fine)
    with open(file_dataset, "w", encoding="utf-8") as f:
        json.dump(a_json(ds), f, ensure_ascii=False)
    # i file più corti dello stesso mese (le generazioni dei giorni precedenti) non servono più,
    # e con loro il report che li descriveva: altrimenti ogni giorno del mese aperto ne lascia uno
    for vecchio in file_superati(ds.data_inizio, ds.data_fine, DIR_OUTPUT):
        suffisso = vecchio.stem.removeprefix("dataset_aria_")
        (DIR_REPORT / f"Report_dataset_aria_{suffisso}.md").unlink(missing_ok=True)
        vecchio.unlink()

    # anagrafiche di stazioni e inquinanti: un errore qui non deve perdere il dataset già generato
    riepilogo = None
    try:
        riepilogo = aggiorna_anagrafiche_aria(
            pd.concat([ds.stazioni, ds.fuori_area], ignore_index=True), ds.capacita, ds.fonti,
            ds.data_inizio, ds.data_fine, ds.unita)
    except Exception as exc:  # noqa: BLE001
        ds.errori.append({"fonte": "anagrafiche", "chiamata": "aggiorna_anagrafiche_aria",
                          "tipo": "errore_imprevisto", "errore": f"{type(exc).__name__}: {exc}"})

    if not senza_report:
        DIR_REPORT.mkdir(parents=True, exist_ok=True)
        # il report dopo l'aggiornamento della lista, così vede anche gli inquinanti appena aggiunti
        file_report = DIR_REPORT / f"Report_dataset_aria_{ds.data_inizio.isoformat()}_{ds.data_fine.isoformat()}.md"
        file_report.write_text(genera_report(ds, inquinanti_tracciati()), encoding="utf-8")
    aggiorna_copertura(ds)
    return ds, riepilogo, file_dataset


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # la console Windows (cp1252) non stampa µ, ₂...
    ieri = date.today() - timedelta(days=1)
    parser = argparse.ArgumentParser(description="Costruisce ed estende l'archivio del dataset aria, un mese alla volta.")
    parser.add_argument("--da", help="data iniziale YYYY-MM-DD (default: ieri, o il primo giorno scoperto con --continua)")
    parser.add_argument("--a", default=ieri.isoformat(), help="data finale YYYY-MM-DD (default: ieri)")
    parser.add_argument("--continua", action="store_true",
                        help="riparte dal mese dell'ultimo giorno già in archivio (aggiornamento quotidiano)")
    parser.add_argument("--rigenera", action="store_true", help="rigenera anche i mesi già presenti")
    parser.add_argument("--senza-report", action="store_true",
                        help="non scrive il report per mese (utile quando si costruisce un archivio di molti mesi)")
    args = parser.parse_args()

    try:
        a = date.fromisoformat(args.a)
        if args.da:
            da = date.fromisoformat(args.da)
        elif args.continua:
            ultimo = ultimo_giorno_coperto(DIR_OUTPUT)
            # si riparte dall'inizio del mese dell'ultimo giorno coperto: quel mese era aperto
            # e le fonti possono aver pubblicato i giorni mancanti nel frattempo
            da = date(ultimo.year, ultimo.month, 1) if ultimo else a
        else:
            da = ieri
    except ValueError as exc:
        print(f"ERRORE nei parametri: {exc}", file=sys.stderr)
        return 2
    if da > a:
        print(f"ERRORE nei parametri: --da ({da}) è dopo --a ({a})", file=sys.stderr)
        return 2
    if a > ieri:
        print(f"ERRORE nei parametri: --a ({a}) è nel futuro: il dato più recente è di ieri ({ieri})", file=sys.stderr)
        return 2

    comuni = carica_comuni()
    impronta = impronta_territorio(c["id_comune"] for c in comuni)
    blocchi = stato_blocchi(da, a, DIR_OUTPUT, rigenera=args.rigenera, impronta=impronta)
    da_fare = [(i, f, m) for i, f, m in blocchi if m != "presente"]
    saltati = len(blocchi) - len(da_fare)
    print(f"Periodo {da} → {a}: {len(blocchi)} mesi, {saltati} già in archivio, {len(da_fare)} da generare.")
    vecchi = [i.strftime("%Y-%m") for i, _, m in da_fare if m == "anagrafica"]
    if vecchi:
        print(f"{len(vecchi)} mesi generati con un elenco di comuni diverso dall'anagrafica attuale, da rifare: "
              f"{', '.join(vecchi)}. Se è una fusione di comuni senza stazioni fisiche si fa prima offline: "
              "`uv run scripts/aria/correggi_comuni_fusi.py`.")
    if not da_fare:
        print("Niente da fare (usa --rigenera per rifare i mesi già presenti).")
        return 0
    print("OpenAQ richiede alcuni minuti per mese; EEA scarica i parquet al primo uso, poi usa la cache in "
          "data/raw/aria/eea/; CAMS legge solo la cache in data/raw/aria/copernicus_cams/ "
          "(si riempie con scripts/aria/scarica_cams.py).")

    corse, errori_totali = [], 0
    for n, (inizio, fine, motivo) in enumerate(da_fare, 1):
        print(f"\n[{n}/{len(da_fare)}] {inizio} → {fine} ({motivo})...", flush=True)
        try:
            ds, riepilogo, file_dataset = _genera_blocco(inizio, fine, inquinanti_tracciati(), args.senza_report)
        except ValueError as exc:
            print(f"  ERRORE nei parametri: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:  # noqa: BLE001 — un mese che fallisce non ferma l'archivio
            print(f"  ERRORE, mese saltato: {type(exc).__name__}: {exc}", file=sys.stderr)
            _registra_errori([{"fonte": "archivio", "chiamata": f"{inizio}_{fine}", "tipo": "mese_fallito",
                               "errore": f"{type(exc).__name__}: {exc}"}],
                             datetime.now().isoformat(timespec="seconds"))
            errori_totali += 1
            continue

        if ds.errori:
            _registra_errori(ds.errori, datetime.now().isoformat(timespec="seconds"))
        errori_totali += len(ds.errori)
        corse.append((ds, riepilogo))

        conteggi = ds.griglia.groupby(["fonte", "stato"]).size()
        valori = ds.griglia[ds.griglia["stato"] == "VALORE"]
        print(f"  {file_dataset.name} ({len(ds.griglia)} celle, {len(valori)} con valore)")
        for fonte in ds.fonti:
            v = valori[valori["fonte"] == fonte]
            print(f"    {fonte:7s} " + "  ".join(f"{s}={n}" for s, n in conteggi[fonte].items())
                  + f"  | distretti con valore: {v['distretto'].nunique()}/20, comuni: {v['comune'].nunique()}/{len(comuni)}")
        if ds.errori:
            print(f"    errori: {len(ds.errori)}")

    riga = _riga_riepilogo(corse, da, a)
    if riga:
        FILE_RIEPILOGO.parent.mkdir(parents=True, exist_ok=True)
        nuovo = not FILE_RIEPILOGO.exists()
        with open(FILE_RIEPILOGO, "a", encoding="utf-8") as f:
            if nuovo:
                f.write("# Riepilogo degli errori dell'archivio aria\n\nUna riga per esecuzione di `genera_dataset_aria.py`, "
                        "con quanto va guardato a mano.\n")
            f.write(riga)

    nuovi = sorted({i for ds, _ in corse for i in ds.inquinanti_nuovi})
    fuori = sum(len(ds.fuori_area) for ds, _ in corse)
    print(f"\nFinito: {len(corse)}/{len(da_fare)} mesi generati, {errori_totali} errori, "
          f"inquinanti nuovi: {nuovi or '-'}, stazioni fuori area: {fuori}"
          + (f" | riepilogo accodato a {FILE_RIEPILOGO.relative_to(RADICE).as_posix()}" if riga else ""))
    print(f"Copertura dell'archivio: {(DIR_REPORT / 'Copertura_archivio_aria.md').relative_to(RADICE).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
