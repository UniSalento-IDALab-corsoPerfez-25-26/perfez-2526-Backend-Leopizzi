"""Decessi ISTAT per la dashboard, **solo a distretto × mese** (regola di privacy, docs/Regole_dei_dati.md): il file
comune × giorno resta sul disco e in memoria, ma nessuna funzione di questo modulo lo restituisce.

Fonte: data/interim/salute/istat/decessi_giornalieri_salento.csv, scritto da
scripts/salute/scarica_decessi_istat.py (somma di sesso e classi di età, stati VALORE/NULL/NO_DATA).
Aggregazione con le regole del 02/10/2026 (api/comune/aggregazione.py), nello stesso ordine di
scripts/salute/valida_decessi.py: comune × giorno → comune × mese (somma) → distretto × mese (somma).

Comuni fusi: dal 14/10/2026 l'anagrafica del territorio rappresenta Presicce-Acquarica come un solo
comune (075098, residenti sommati) e ISTAT pubblica da sempre un solo valore per quel codice, quindi
niente ripetizione da togliere qui (prima dell'unificazione il file la aveva, v. valida_decessi.py).
"""

import threading
from pathlib import Path

import pandas as pd

from api.comune.aggregazione import carica_pesi_comuni, per_mese, somma_per_distretto
from api.comune.stati import STATO_VALORE

RADICE = Path(__file__).resolve().parents[2]
FILE_DECESSI = RADICE / "data" / "interim" / "salute" / "istat" / "decessi_giornalieri_salento.csv"
FONTE = ("ISTAT, decessi comunali giornalieri (rilascio con dati provvisori), somma di sesso e classi di età; "
         "Presicce-Acquarica contato una volta sola")
LICENZA = "CC BY 4.0 (note legali ISTAT)"
NOTA_PRIVACY = ("Decessi esposti solo come somma per distretto e mese: il dato per comune e giorno è fatto di "
                "numeri piccolissimi e non si mostra, per la privacy.")


class ArchivioDecessi:
    def __init__(self, percorso=FILE_DECESSI):
        self.percorso = Path(percorso)
        self._blocco = threading.Lock()
        self._mtime = None
        self._distretto_mese = None
        self._copertura_fino_al = None

    def disponibile(self):
        return self.percorso.exists()

    def _carica(self):
        mtime = self.percorso.stat().st_mtime
        if self._distretto_mese is not None and self._mtime == mtime:
            return
        df = pd.read_csv(self.percorso, dtype={"id_comune": str, "nota": str})
        df = df.rename(columns={"id_comune": "comune", "data": "giorno", "decessi": "valore"})
        valori = df.loc[df["stato"] == STATO_VALORE, "giorno"]
        self._copertura_fino_al = valori.max() if len(valori) else None
        pesi = dict(carica_pesi_comuni())
        mensile = per_mese(df, funzione="somma", colonna_tempo="giorno", chiavi=(), colonna_zona="comune")
        self._distretto_mese = somma_per_distretto(mensile, pesi=pesi, colonna_tempo="mese")
        self._mtime = mtime

    def distretto_mese(self):
        """DataFrame distretto × mese (colonne distretto, mese, valore, stato, nota, comuni,
        comuni_con_valore, quota_residenti) e ultimo giorno con un VALORE, oppure (None, None)."""
        if not self.disponibile():
            return None, None
        with self._blocco:  # il primo calcolo dura qualche secondo: le richieste concorrenti aspettano
            self._carica()
            return self._distretto_mese, self._copertura_fino_al
