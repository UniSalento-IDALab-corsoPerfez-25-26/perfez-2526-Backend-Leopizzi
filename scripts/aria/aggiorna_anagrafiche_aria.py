#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aggiorna le anagrafiche relazionali dell'aria (stazioni collegate al comune,
inquinanti e stazioni che li misurano) senza generare il dataset completo.
Le stesse anagrafiche si aggiornano anche a ogni esecuzione di
scripts/aria/genera_dataset_aria.py; questo script serve per farlo da solo.

Uso (dalla radice del repo):
  uv run --env-file .env scripts/aria/aggiorna_anagrafiche_aria.py                  # ultimi 7 giorni, tutte le fonti
  uv run --env-file .env scripts/aria/aggiorna_anagrafiche_aria.py --giorni 30
  uv run --env-file .env scripts/aria/aggiorna_anagrafiche_aria.py --da 2024-06-01 --a 2024-06-30
  uv run scripts/aria/aggiorna_anagrafiche_aria.py --offline                        # senza rete, dai file locali

Più il periodo è lungo, più stazioni e inquinanti si scoprono (una stazione che non ha
restituito righe nel periodo non risulta "misurare" quell'inquinante), ma OpenAQ richiede
molte chiamate: per un primo popolamento conviene un mese intero.

--offline usa solo file già nel repo: l'anagrafica ARPA (stazioni_di_monitoraggio.json),
gli inquinanti osservati nel 2023 (Copertura_Distretti_ARPA.json) e le descrizioni degli
inquinanti (Parametri_Qualita_Aria.md). Non vede OpenAQ né le stazioni assenti dall'anagrafica.

Le anagrafiche dipendono dal territorio: prima lanciare, se manca,
scripts/territorio/costruisci_anagrafica_territorio.py.
"""

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # radice del repo, per il package api
from api.aria.anagrafica_aria import aggiorna_anagrafiche_aria, aggiorna_descrizioni_inquinanti  # noqa: E402
from api.aria.arpa_puglia import ArpaPugliaError, get_inquinanti  # noqa: E402
from api.aria.fonti import fonti_aria  # noqa: E402
from api.aria.fonti.base import COLONNE_STAZIONI  # noqa: E402
from api.comune.distretti_salento import carica_stazioni_salento  # noqa: E402

RADICE = Path(__file__).resolve().parents[2]
FILE_COPERTURA = RADICE / "data" / "dataset" / "aria" / "arpa_puglia" / "Copertura_Distretti_ARPA.json"
FILE_PARAMETRI = RADICE / "data" / "dataset" / "aria" / "arpa_puglia" / "Parametri_Qualita_Aria.md"
ANNO_OFFLINE = 2023  # anno degli inquinanti osservati in Copertura_Distretti_ARPA.json


def leggi_parametri_md():
    """Righe della tabella di Parametri_Qualita_Aria.md, nel formato di get_inquinanti()."""
    righe = []
    for linea in FILE_PARAMETRI.read_text(encoding="utf-8").splitlines():
        celle = [c.strip() for c in linea.strip().strip("|").split("|")]
        if len(celle) == 7 and celle[0] in ("", "✅") and celle[1] not in ("Sigla", "---"):
            righe.append(dict(zip(
                ["sigla", "descrizione", "periodo_di_misurazione", "valore_limite", "soglia_di_allarme", "unita_misura"],
                celle[1:])))
    return righe


def raccogli_offline():
    """(stazioni, capacita, fonti, da, a, unita) dai file locali, nel formato di aggiorna_anagrafiche_aria."""
    stazioni = [
        {"stazione": s["id_station"], "fonte": "ARPA", "id_fonte": s["id_station"], "denominazione": s["denominazione"],
         "comune": s["comune"], "provincia": s["provincia"], "lat": s["lat"], "lon": s["lon"],
         "id_distretto": s["id_distretto"], "attiva_da": None, "attiva_a": None,
         "abbinamento": "anagrafica ARPA locale, distretto dal comune"}
        for s in carica_stazioni_salento() if s["rete"] != "ADI"  # rete privata ex-ILVA esclusa dal dataset
    ]
    with open(FILE_COPERTURA, encoding="utf-8") as f:
        copertura = json.load(f)
    capacita = {(s["id_station"], "ARPA", inq)
                for d in copertura["distretti"] for s in d.get("stazioni", [])
                for inq in s.get("inquinanti_osservati_2023", [])}
    unita = {r["sigla"]: r["unita_misura"] for r in leggi_parametri_md()}
    return (pd.DataFrame(stazioni, columns=COLONNE_STAZIONI),
            pd.DataFrame(sorted(capacita), columns=["stazione", "fonte", "inquinante"]),
            {"ARPA": date(2012, 1, 1), "OpenAQ": date(2020, 5, 6)},
            date(ANNO_OFFLINE, 1, 1), date(ANNO_OFFLINE, 12, 31), unita)


def raccogli_live(da, a):
    """Stessi dati dalle fonti vere. Una fonte che fallisce non ferma le altre."""
    fonti = fonti_aria()
    stazioni, capacita, unita, errori = [], [], {}, []
    for fonte in fonti:
        print(f"  {fonte.nome}...", flush=True)
        try:
            r = fonte.raccogli(da, a)
        except Exception as exc:  # noqa: BLE001
            errori.append(f"{fonte.nome}: {type(exc).__name__}: {exc}")
            continue
        errori += [f"{e['fonte']} {e['chiamata']}: {e['errore']}" for e in r.errori]
        stazioni.append(r.stazioni)
        capacita.append(r.capacita.assign(fonte=fonte.nome))
        unita.update({k: v for k, v in r.unita.items() if k not in unita})
    if not stazioni:
        return None, errori
    return (pd.concat(stazioni, ignore_index=True), pd.concat(capacita, ignore_index=True),
            {f.nome: f.copertura_da for f in fonti}, da, a, unita), errori


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ieri = date.today() - timedelta(days=1)
    parser = argparse.ArgumentParser(description="Aggiorna le anagrafiche dell'aria (stazioni, inquinanti).")
    parser.add_argument("--giorni", type=int, default=7, help="ultimi N giorni fino a ieri (default: 7)")
    parser.add_argument("--da", help="data iniziale YYYY-MM-DD (alternativa a --giorni)")
    parser.add_argument("--a", help="data finale YYYY-MM-DD (default: ieri)")
    parser.add_argument("--offline", action="store_true", help="usa solo i file locali, senza rete")
    args = parser.parse_args()

    errori = []
    if args.offline:
        stazioni, capacita, fonti, da, a, unita = raccogli_offline()
        descrizioni = leggi_parametri_md()
    else:
        a = date.fromisoformat(args.a) if args.a else ieri
        da = date.fromisoformat(args.da) if args.da else a - timedelta(days=args.giorni - 1)
        print(f"Raccolgo stazioni e inquinanti {da} → {a}...")
        raccolta, errori = raccogli_live(da, a)
        if raccolta is None:
            print("ERRORE: nessuna fonte ha risposto.\n  " + "\n  ".join(errori), file=sys.stderr)
            return 1
        stazioni, capacita, fonti, da, a, unita = raccolta
        try:
            descrizioni = get_inquinanti()
        except ArpaPugliaError as exc:
            errori.append(f"ARPA inquinanti.jsp: {exc}")
            descrizioni = []

    riepilogo = aggiorna_anagrafiche_aria(stazioni, capacita, fonti, da, a, unita)
    aggiornati = aggiorna_descrizioni_inquinanti(descrizioni)

    print(f"Periodo {da} → {a}: +{riepilogo['stazioni_nuove']} stazioni, +{riepilogo['stazioni_fonti_nuove']} record di fonte, "
          f"+{riepilogo['coppie_nuove']} coppie stazione/inquinante, inquinanti nuovi: {riepilogo['inquinanti_nuovi'] or '-'}")
    print(f"Descrizioni aggiornate per: {', '.join(aggiornati) or '-'}")
    print(f"Stazioni senza comune ({len(riepilogo['stazioni_senza_comune'])}): {riepilogo['stazioni_senza_comune'] or '-'}")
    for x in riepilogo["discrepanze"]:
        print(f"  discrepanza distretto: {x}")
    for p in riepilogo["problemi"]:
        print(f"  PROBLEMA DI INTEGRITÀ: {p}", file=sys.stderr)
    for e in errori:
        print(f"  errore fonte: {e}", file=sys.stderr)
    return 1 if riepilogo["problemi"] else 0


if __name__ == "__main__":
    sys.exit(main())
