#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scarica i monitoraggi giornalieri di qualità dell'aria 2023 per il Salento
(Lecce, Brindisi, Taranto) dal mirror CKAN di dati.puglia.it (dataset
"dati-qualita-aria-2023"), un mese alla volta, e li unisce in un unico file.

Non dipende da cloud.arpa.puglia.it (al 27/09/2026 irraggiungibile).

Output:
  data/raw/aria/arpa_puglia/qualita_aria_2023_salento.json  (gitignored)

Fonte: dati.puglia.it, dataset "dati-qualita-aria-2023".
Licenza: da confermare per questo dataset specifico (altri dataset ARPA su
dati.puglia.it sono in CC BY 4.0, v. data/dataset/aria/Lista_dataset_aria.md).
"""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # radice del repo, per il package api
from api.aria.arpa_puglia import get_qualita_aria_mensile_2023_ckan  # noqa: E402
from api.comune.dati_puglia_ckan import CkanError  # noqa: E402

RADICE = Path(__file__).resolve().parents[2]
DIR_OUTPUT = RADICE / "data" / "raw" / "aria" / "arpa_puglia"
FILE_OUTPUT = DIR_OUTPUT / "qualita_aria_2023_salento.json"

NOMI_MESI = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]


def main():
    tutte_le_righe = []
    print("Scarico i 12 mesi del 2023 (Lecce, Brindisi, Taranto) da dati.puglia.it...")
    for mese in range(1, 13):
        try:
            righe = get_qualita_aria_mensile_2023_ckan(mese)
        except CkanError as exc:
            print(f"  ERRORE su {NOMI_MESI[mese - 1]}: {exc}", file=sys.stderr)
            continue
        stazioni = {r["id_station"] for r in righe}
        comuni = {r["comune"] for r in righe}
        print(
            "  {:10} {:6} righe  |  {} stazioni  |  {} comuni".format(
                NOMI_MESI[mese - 1], len(righe), len(stazioni), len(comuni)
            )
        )
        tutte_le_righe.extend(righe)

    DIR_OUTPUT.mkdir(parents=True, exist_ok=True)
    with open(FILE_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(
            {
                "descrizione": "Monitoraggi giornalieri qualità aria 2023, Lecce/Brindisi/Taranto",
                "fonte": "dati.puglia.it, dataset dati-qualita-aria-2023 (mirror CKAN)",
                "data_download": date.today().isoformat(),
                "n_righe": len(tutte_le_righe),
                "righe": tutte_le_righe,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\nScritto: {FILE_OUTPUT}")
    print(f"Totale righe (Salento, 2023, deduplicate): {len(tutte_le_righe)}")

    stazioni_totali = {
        (r["id_station"], r["denominazione"], r["comune"], r["provincia"]) for r in tutte_le_righe
    }
    print(f"Stazioni distinte viste nell'anno: {len(stazioni_totali)}")
    for s in sorted(stazioni_totali, key=lambda x: (x[3], x[2])):
        print(f"   [{s[3]:10}] {s[2]:20} {s[1]} (id {s[0]})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
