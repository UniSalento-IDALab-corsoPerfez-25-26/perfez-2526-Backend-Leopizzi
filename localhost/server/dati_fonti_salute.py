"""Decessi secondo ogni fonte, per la tab «Fonti a confronto» (scelte di Matteo del 27/10/2026).

Legge solo le tabelle che scripts/salute/valida_decessi.py scrive in data/interim/salute/validazione/: il server non
chiama Eurostat dentro una richiesta HTTP. Due confronti, sull'anno in cui finisce la finestra della barra:

- **distretto × mese**: canale A (decessi comunali giornalieri, somma del mese) ↔ bilancio demografico mensile
  (canale D, 2019-2024). Due pubblicazioni ISTAT con flussi diversi: un piccolo scarto è atteso.
- **provincia × mese**: canale A ↔ Eurostat `demo_r_mwk3_t`. Eurostat pubblica solo settimane ISO: lo script le
  porta al mese del loro giovedì, per entrambe le fonti (scelta di Matteo del 27/10/2026, regola §7). Eurostat
  ridistribuisce i dati ISTAT: la coincidenza verifica la nostra somma, non è un riscontro indipendente.

Privacy (docs/Regole_dei_dati.md): nessun dato sotto il distretto né sotto il mese.
"""

import threading
from datetime import datetime
from pathlib import Path

import pandas as pd

from api.comune.stati import STATO_VALORE

RADICE = Path(__file__).resolve().parents[2]
DIR = RADICE / "data" / "interim" / "salute" / "validazione"
FILE_MESE = DIR / "decessi_fonti_distretto_mese.csv"
FILE_PROVINCIA = DIR / "decessi_fonti_provincia_mese.csv"

# chiave nel CSV -> (nome breve, descrizione)
FONTI = {
    "A": ("ISTAT giornaliero", "ISTAT, decessi comunali giornalieri (dati provvisori), sommati sul periodo"),
    "D": ("ISTAT bilancio mensile", "ISTAT, bilancio demografico mensile per comune (fonte anagrafica), 2019-2024"),
    "Eurostat": ("Eurostat", "Eurostat demo_r_mwk3_t, decessi per provincia (NUTS 3) e settimana ISO, portati al mese del giovedì"),
}
LICENZA = "CC BY 4.0 (ISTAT ed Eurostat)"
NOTA_A_D = ("Due pubblicazioni ISTAT con flussi diversi (schede di morte e anagrafe): un piccolo scarto è atteso, "
            "il canale A è provvisorio. Il bilancio mensile è pubblicato fino al 2024.")
NOTA_A_EUROSTAT = ("Eurostat ridistribuisce i decessi che ISTAT gli trasmette: la coincidenza verifica la nostra somma, "
                   "non è un riscontro indipendente. Scarti negli anni recenti = revisioni dei dati provvisori.")


def _leggi(percorso, dtype):
    # keep_default_na=False: per pandas «NULL» è un valore mancante, qui è uno dei tre stati
    return pd.read_csv(percorso, dtype=dtype, keep_default_na=False, na_values={"valore": [""], "nota": [""]})


class ArchivioFontiDecessi:
    def __init__(self):
        self._blocco = threading.Lock()
        self._firma = None
        self._tabelle = (None, None)

    @staticmethod
    def disponibile():
        return FILE_MESE.exists()

    def tabelle(self):
        """(distretto × mese, provincia × mese) o (None, None) se lo script non è ancora stato lanciato.
        La tabella provinciale è None se lo script è stato lanciato con --senza-eurostat."""
        if not self.disponibile():
            return None, None
        firma = tuple(f.stat().st_mtime if f.exists() else None for f in (FILE_MESE, FILE_PROVINCIA))
        with self._blocco:
            if firma != self._firma:
                mese = _leggi(FILE_MESE, {"fonte": str, "distretto": str, "mese": str, "stato": str})
                provincia = (_leggi(FILE_PROVINCIA, {"fonte": str, "id_provincia": str, "mese": str, "stato": str})
                             if FILE_PROVINCIA.exists() else None)
                self._tabelle, self._firma = (mese, provincia), firma
            return self._tabelle

    @staticmethod
    def generato_il():
        return datetime.fromtimestamp(FILE_MESE.stat().st_mtime).strftime("%d/%m/%Y")


def mesi_dell_anno(anno):
    return [f"{anno}-{m:02d}" for m in range(1, 13)]


def punti(df, fonte, colonna_periodo, periodi, nota_assente):
    """[{periodo, valore, stato, nota}] di una fonte sui periodi richiesti; un periodo senza riga è NO_DATA."""
    per = {r[colonna_periodo]: r for r in df[df["fonte"] == fonte].to_dict("records")} if df is not None else {}
    out = []
    for p in periodi:
        r = per.get(p)
        if r is None:
            out.append({"periodo": p, "valore": None, "stato": "NO_DATA", "nota": nota_assente})
        else:
            v, nota = r["valore"], r["nota"]
            out.append({"periodo": p, "valore": None if pd.isna(v) else float(v), "stato": r["stato"],
                        "nota": None if pd.isna(nota) else nota})
    return out


def confronta(a, b):
    """Statistiche di concordanza fra due liste di punti sugli stessi periodi, sui soli periodi con VALORE in entrambe."""
    coppie = [(x["valore"], y["valore"]) for x, y in zip(a, b)
              if x["stato"] == STATO_VALORE and y["stato"] == STATO_VALORE]
    if not coppie:
        return {"celle_comuni": 0}
    diff = pd.Series([vb - va for va, vb in coppie])
    sa, sb = pd.Series([c[0] for c in coppie]), pd.Series([c[1] for c in coppie])
    r = sa.corr(sb) if len(coppie) > 2 and sa.std() > 0 and sb.std() > 0 else None
    return {
        "celle_comuni": len(coppie),
        "identiche": float((diff == 0).mean()),
        "entro_uno": float((diff.abs() <= 1).mean()),
        "differenza_totale": float(diff.sum()),
        "differenza_media": float(diff.mean()),
        "differenza_massima": float(diff.abs().max()),
        "correlazione": None if r is None or pd.isna(r) else float(r),
    }
