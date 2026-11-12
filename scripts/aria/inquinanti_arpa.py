#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scarica l'elenco completo degli inquinanti monitorati da ARPA Puglia
(servizio QualitaAria/Pollutants) e genera una tabella Markdown con tutti
i parametri (sigla, descrizione, periodo di misurazione, valore limite,
soglia di allarme, unità di misura), evidenziando quali fanno già parte
dei 5 inquinanti di riferimento della dashboard.

Input:
  ARPA Puglia, old.arpa.puglia.it/ARPA_ARIA/inquinanti.jsp (stesso contratto
  del servizio documentato QualitaAria/Pollutants — v. api/aria/arpa_puglia.py).

Output:
  data/dataset/aria/arpa_puglia/Parametri_Qualita_Aria.md
  data/dataset/aria/anagrafica/inquinanti.json  descrizione, unità, periodo, limiti degli inquinanti
                                                già tracciati (se il file esiste)

Riferimento dashboard (CO, NO2, O3, PM2.5, SO2): repository Frontend, docs/Specifiche_Design.md.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # radice del repo, per il package api
from api.aria.anagrafica_aria import FILE_INQUINANTI, aggiorna_descrizioni_inquinanti  # noqa: E402
from api.aria.arpa_puglia import ArpaPugliaError, get_inquinanti  # noqa: E402

RADICE = Path(__file__).resolve().parents[2]
FILE_OUTPUT = RADICE / "data" / "dataset" / "aria" / "arpa_puglia" / "Parametri_Qualita_Aria.md"

RIFERIMENTO_DASHBOARD = {"CO", "NO2", "O3", "PM2.5", "SO2"}


def main():
    try:
        inquinanti = get_inquinanti()
    except ArpaPugliaError as exc:
        print(f"ERRORE nel contattare ARPA Puglia: {exc}", file=sys.stderr)
        return 1

    if not inquinanti:
        print("ATTENZIONE: risposta vuota dall'API (nessun inquinante trovato).", file=sys.stderr)
        return 1

    inquinanti.sort(key=lambda r: r.get("sigla", ""))

    righe = [
        "# Parametri di qualità dell'aria monitorati da ARPA Puglia",
        "",
        f"Generato automaticamente da `scripts/aria/inquinanti_arpa.py` il {date.today().isoformat()}, "
        "da ARPA Puglia (`old.arpa.puglia.it/ARPA_ARIA/inquinanti.jsp`, stesso contratto del servizio "
        "documentato `QualitaAria/Pollutants` — v. `api/aria/arpa_puglia.py`).",
        "",
        "I 5 inquinanti di riferimento per la dashboard (CO, NO2, O3, PM2.5, SO2, v. "
        "`repository Frontend, docs/Specifiche_Design.md`) sono marcati con ✅; gli altri sono "
        "comunque monitorati da ARPA ma non fanno parte dell'elenco di riferimento, salvo diversa "
        "indicazione.",
        "",
        "| Rif. dashboard | Sigla | Descrizione | Periodo di misurazione | Valore limite | Soglia di allarme | Unità |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in inquinanti:
        sigla = r.get("sigla", "")
        segno = "✅" if sigla in RIFERIMENTO_DASHBOARD else ""
        righe.append(
            "| {} | {} | {} | {} | {} | {} | {} |".format(
                segno,
                sigla,
                r.get("descrizione", ""),
                r.get("periodo_di_misurazione", ""),
                r.get("valore_limite", ""),
                r.get("soglia_di_allarme", ""),
                r.get("unita_misura", ""),
            )
        )

    sigle_trovate = {r.get("sigla", "") for r in inquinanti}
    mancanti = RIFERIMENTO_DASHBOARD - sigle_trovate
    if mancanti:
        righe.append("")
        righe.append(
            f"⚠️ Sigle di riferimento non trovate nell'elenco ARPA: {', '.join(sorted(mancanti))} "
            "(possibile differenza di notazione, es. 'PM2.5' vs 'PM25' — da verificare a mano)."
        )

    FILE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    FILE_OUTPUT.write_text("\n".join(righe) + "\n", encoding="utf-8")

    print(f"Scritto: {FILE_OUTPUT}")
    if FILE_INQUINANTI.exists():
        aggiornati = aggiorna_descrizioni_inquinanti(inquinanti)
        print(f"Anagrafica inquinanti aggiornata: {', '.join(aggiornati) or '-'}")
    print(f"Inquinanti trovati: {len(inquinanti)}")
    for r in inquinanti:
        # [rif] invece di un emoji: su console Windows (cp1252) print() va in
        # crash su caratteri fuori Latin-1 (osservato il 27/09/2026). L'emoji
        # resta nel file Markdown, scritto esplicitamente in UTF-8.
        segno = "[rif]" if r.get("sigla", "") in RIFERIMENTO_DASHBOARD else "     "
        try:
            print(f"  {segno} {r.get('sigla', ''):8} {r.get('descrizione', '')}")
        except UnicodeEncodeError:
            print(f"  {segno} {r.get('sigla', ''):8} <descrizione con caratteri non stampabili in questa console>")

    return 0


if __name__ == "__main__":
    sys.exit(main())
