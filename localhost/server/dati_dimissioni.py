"""Dimissioni ospedaliere per la dashboard (18/10/2026): **provincia × anno**, da ISTAT Health for All.

Fonte: data/interim/salute/istat_hfa/dimissioni_province.csv, scritto da scripts/salute/scarica_dimissioni_hfa.py
(client e formato in api/salute/istat_hfa.py; scheda in data/dataset/salute/istat/ISTAT.md, canale C).

**Solo informativo**: il dato è annuale e provinciale, quindi non entra nelle correlazioni, in `/api/confronto` né nel
confronto distretto × mese. Si affianca ai decessi come lettura di contesto; la media giornaliera (`~`, dimissioni /
giorni dell'anno) è solo presentazione (convenzione del 09/10/2026). A differenza dei decessi non c'è un problema di
privacy: sono migliaia di dimissioni per provincia, quindi vale per qualsiasi zona (comune compreso), con la provincia
della zona dichiarata.
"""

import threading
from calendar import isleap
from pathlib import Path

import pandas as pd

from api.salute.istat_hfa import GRUPPI

RADICE = Path(__file__).resolve().parents[2]
FILE_DIMISSIONI = RADICE / "data" / "interim" / "salute" / "istat_hfa" / "dimissioni_province.csv"
FONTE = ("ISTAT, Health for All (Italia), dimissioni ospedaliere per gruppo di patologia, provincia di residenza, "
         "maschi + femmine")
LICENZA = "CC BY 4.0 (note legali ISTAT)"
GRANA = "provincia × anno"
NOTA_GRANA = ("Dato annuale e provinciale: non è riferito alla zona né alla finestra scelta, e non entra nelle correlazioni. "
              "Il ~/giorno è il totale annuo diviso per i giorni dell'anno.")
ETICHETTE = {g: v[0] for g, v in GRUPPI.items()}


def giorni_dell_anno(anno):
    return 366 if isleap(int(anno)) else 365


class ArchivioDimissioni:
    def __init__(self, percorso=FILE_DIMISSIONI):
        self.percorso = Path(percorso)
        self._blocco = threading.Lock()
        self._mtime = None
        self._df = None

    def disponibile(self):
        return self.percorso.exists()

    def tabella(self):
        """DataFrame lungo (provincia, anno, gruppo, dimissioni, tasso, stato, nota) o None se il file non c'è."""
        if not self.disponibile():
            return None
        with self._blocco:
            mtime = self.percorso.stat().st_mtime
            if self._df is None or self._mtime != mtime:
                df = pd.read_csv(self.percorso, dtype={"provincia": str, "gruppo": str, "nota": str})
                df["tasso"] = df["tasso"].round(2)  # il binario è float32: 91,47 arriva come 91,4700002...
                self._df, self._mtime = df, mtime
            return self._df

    def anni_con_valore(self):
        df = self.tabella()
        if df is None:
            return None, None
        anni = df.loc[df["stato"] == "VALORE", "anno"]
        return (int(anni.min()), int(anni.max())) if len(anni) else (None, None)
