#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Incrocia l'anagrafica ufficiale delle stazioni ARPA Puglia con i distretti
socio-sanitari del Salento, per capire quali distretti sono coperti dal
monitoraggio della qualità dell'aria e con quali inquinanti.

Usa api/comune/distretti_salento.py per l'associazione stazione -> distretto (stessa
logica usata dall'endpoint api.aria.arpa_puglia.get_qualita_aria_periodo).

Input:
  data/dataset/aria/arpa_puglia/stazioni_di_monitoraggio.json
    Anagrafica completa (74 stazioni, tutta la Puglia, incluse le 6 private
    VERSALIS di Brindisi aggiunte a mano il 01/10/2026; GeoJSON nel formato
    del servizio QualitaAria/Stations di ARPA Puglia). Rigenerabile da
    old.arpa.puglia.it con scripts/aria/aggiorna_stazioni_arpa.py (che
    mantiene le stazioni private non restituite da centraline.jsp).
  data/territorio/lista_presidi/Distretti_Salento.json
    Comuni per distretto socio-sanitario (v. scripts/territorio/costruisci_distretti_salento.py).
  data/raw/aria/arpa_puglia/qualita_aria_2023_salento.json  (opzionale)
    Se presente (v. scripts/aria/scarica_qualita_aria_2023.py), viene usato per
    riportare gli inquinanti REALMENTE misurati in ciascuna stazione nel
    2023, invece di una lista dichiarata/statica.

Output:
  data/dataset/aria/arpa_puglia/Copertura_Distretti_ARPA.json  (dati strutturati)
  data/dataset/aria/arpa_puglia/Stazioni_Salento.md            (tabella leggibile)
  report a video
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # radice del repo, per il package api
from api.comune.distretti_salento import carica_distretti, carica_stazioni_salento  # noqa: E402

RADICE = Path(__file__).resolve().parents[2]
FILE_DATI_2023 = RADICE / "data" / "raw" / "aria" / "arpa_puglia" / "qualita_aria_2023_salento.json"

FILE_OUTPUT_JSON = RADICE / "data" / "dataset" / "aria" / "arpa_puglia" / "Copertura_Distretti_ARPA.json"
FILE_OUTPUT_MD = RADICE / "data" / "dataset" / "aria" / "arpa_puglia" / "Stazioni_Salento.md"


def carica_inquinanti_osservati_2023():
    """id_station -> set di sigle inquinante realmente misurate nel 2023,
    se il file di dati scaricati esiste; altrimenti {} (nessun dato ancora)."""
    if not FILE_DATI_2023.exists():
        return {}
    with open(FILE_DATI_2023, encoding="utf-8") as f:
        dati = json.load(f)
    osservati = defaultdict(set)
    for riga in dati["righe"]:
        osservati[riga["id_station"]].add(riga["inquinante_misurato"])
    return osservati


def main():
    stazioni = carica_stazioni_salento()
    distretti = carica_distretti()
    inquinanti_2023 = carica_inquinanti_osservati_2023()

    stazioni_per_distretto = {d["id_distretto"]: [] for d in distretti}
    stazioni_senza_distretto = []

    for s in stazioni:
        s["inquinanti_osservati_2023"] = sorted(inquinanti_2023.get(s["id_station"], []))
        if s["id_distretto"] is None:
            stazioni_senza_distretto.append(s)
            continue
        stazioni_per_distretto[s["id_distretto"]].append(s)

    distretti_non_coperti = [d for d in distretti if not stazioni_per_distretto[d["id_distretto"]]]

    righe_distretti = []
    for d in distretti:
        staz = stazioni_per_distretto[d["id_distretto"]]
        inquinanti_distretto = sorted({sig for s in staz for sig in s["inquinanti_osservati_2023"]})
        righe_distretti.append(
            {
                "id_distretto": d["id_distretto"],
                "denominazione": d["denominazione"],
                "provincia": d["provincia"],
                "n_stazioni": len(staz),
                "stazioni": staz,
                "inquinanti_osservati_2023": inquinanti_distretto,
            }
        )

    uscita = {
        "descrizione": "Stazioni ARPA Puglia (anagrafica fornita il 27/09/2026) associate ai distretti "
        "socio-sanitari del Salento, con gli inquinanti realmente misurati nel 2023 (se disponibili)",
        "fonte_stazioni": "data/dataset/aria/arpa_puglia/stazioni_di_monitoraggio.json",
        "fonte_inquinanti_osservati": "data/raw/aria/arpa_puglia/qualita_aria_2023_salento.json"
        if inquinanti_2023
        else None,
        "n_distretti_totali": len(distretti),
        "n_distretti_coperti": len(distretti) - len(distretti_non_coperti),
        "n_distretti_non_coperti": len(distretti_non_coperti),
        "distretti_non_coperti": [
            {"id_distretto": d["id_distretto"], "denominazione": d["denominazione"], "provincia": d["provincia"]}
            for d in distretti_non_coperti
        ],
        "distretti": righe_distretti,
        "stazioni_senza_distretto": stazioni_senza_distretto,
    }

    FILE_OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(FILE_OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(uscita, f, ensure_ascii=False, indent=2)

    # ---- tabella Markdown di documentazione ----
    righe_md = [
        "# Stazioni ARPA Puglia nel Salento (Lecce, Brindisi, Taranto)",
        "",
        "Anagrafica ufficiale ARPA Puglia "
        "(`data/dataset/aria/arpa_puglia/stazioni_di_monitoraggio.json`, rigenerabile con "
        "`scripts/aria/aggiorna_stazioni_arpa.py`), incrociata con i distretti "
        "socio-sanitari (`data/territorio/lista_presidi/Distretti_Salento.json`).",
        "",
        f"**{len(stazioni)} stazioni** nelle tre province (incluse le {sum(1 for s in stazioni if s['provincia'] == 'ILVA')} "
        "private della rete ADI ex-ILVA a Taranto). Colonna \"Inquinanti osservati 2023\" = "
        + ("sigle realmente misurate secondo i dati scaricati (v. `scripts/aria/scarica_qualita_aria_2023.py`)."
           if inquinanti_2023 else "non disponibile: eseguire prima `scripts/aria/scarica_qualita_aria_2023.py`."),
        "",
        "| Distretto | Provincia | Comune | Stazione | id | Rete | Interesse | Inquinanti osservati 2023 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in righe_distretti:
        if not d["stazioni"]:
            righe_md.append(
                f"| **{d['id_distretto']} — {d['denominazione']}** | {d['provincia']} | "
                "*(nessuna stazione)* | | | | | |"
            )
            continue
        for s in sorted(d["stazioni"], key=lambda x: (x["comune"], x["denominazione"])):
            righe_md.append(
                "| {} — {} | {} | {} | {} | {} | {} | {} | {} |".format(
                    d["id_distretto"], d["denominazione"], s["provincia"], s["comune"],
                    s["denominazione"], s["id_station"], s["rete"], s["interesse_rete"],
                    ", ".join(s["inquinanti_osservati_2023"]) or "—",
                )
            )
    if stazioni_senza_distretto:
        righe_md.append("")
        righe_md.append("## Stazioni non assegnate a nessun distretto")
        righe_md.append(
            "Comune della stazione non trovato nell'elenco comuni di nessun distretto "
            "(possibile refuso di nome, da verificare):"
        )
        for s in stazioni_senza_distretto:
            righe_md.append(f"- {s['denominazione']} (comune: {s['comune']}, provincia: {s['provincia']})")

    FILE_OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    FILE_OUTPUT_MD.write_text("\n".join(righe_md) + "\n", encoding="utf-8")

    # ---- report a video ----
    print(f"Scritto: {FILE_OUTPUT_JSON}")
    print(f"Scritto: {FILE_OUTPUT_MD}")
    print(f"\nDistretti Salento: {len(distretti)}  |  coperti: {uscita['n_distretti_coperti']}  |  NON coperti: {uscita['n_distretti_non_coperti']}")
    if not inquinanti_2023:
        print("(nessun dato 2023 trovato: esegui scripts/aria/scarica_qualita_aria_2023.py per popolare gli inquinanti osservati)")
    print()
    for d in righe_distretti:
        stato = "OK" if d["n_stazioni"] else "NON COPERTO"
        print(f"  [{stato:>12}] {d['id_distretto']:8} {d['denominazione']:35} stazioni: {d['n_stazioni']:2}  inquinanti 2023: {', '.join(d['inquinanti_osservati_2023']) or '-'}")

    if distretti_non_coperti:
        print("\n--- Distretti NON coperti da alcuna stazione ARPA ---")
        for d in distretti_non_coperti:
            print(f"   - {d['id_distretto']}: {d['denominazione']} ({d['provincia']})")

    if stazioni_senza_distretto:
        print(f"\n{len(stazioni_senza_distretto)} stazioni con comune non trovato in nessun distretto (v. tabella Markdown).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
