"""Dati sanitari **simulati** per la dashboard (25/10/2026): ricoveri, accessi in pronto soccorso e accessi degli
assistiti in ADI per **comune × giorno**, in due scenari (`nullo`, `letteratura`).

Fonte: data/interim/salute/simulati/salute_simulata.parquet e parametri.json accanto, scritti da
scripts/salute/simula_dati_salute.py (modello in api/salute/simulazione.py; scheda, dicitura e limiti in
data/dataset/salute/simulati/Dati_Simulati.md).

Regole di presentazione (piano in repository Frontend, docs/Specifiche_Design.md, scelte di Matteo del 25/10/2026):
- **il simulato non si confonde mai col reale**: la dicitura viene da parametri.json, non si ricopia;
- sono **conteggi**: distretto e Salento = **somma** dei comuni (regola di api/comune/aggregazione.py); il dato è
  sintetico, quindi la regola di privacy dei decessi (docs/Regole_dei_dati.md) non si applica e i comuni sono ammessi;
- nei grafici e nelle tabelle i valori sono **per 100.000 residenti al giorno**, così zone diverse si confrontano;
- `adi_assistiti` è uno **stock** (assistiti in carico ogni giorno): nella finestra si media, non si somma.
"""

import json
import threading
from pathlib import Path

import pandas as pd

RADICE = Path(__file__).resolve().parents[2]
DIR_SIMULATI = RADICE / "data" / "interim" / "salute" / "simulati"
FILE_SIMULATI = DIR_SIMULATI / "salute_simulata.parquet"
FILE_PARAMETRI = DIR_SIMULATI / "parametri.json"
SCENARI = ("nullo", "letteratura")
SCENARIO_PREDEFINITO = "letteratura"  # lo scenario usato in tesi
DICITURA_BREVE = "Dato simulato, non reale"
PER = 100_000  # residenti
STOCK = {"adi_assistiti"}
UNITA = {i: "per 100.000 residenti al giorno" for i in (
    "ricoveri_respiratori", "ricoveri_circolatori", "ps_accessi", "ps_respiratori", "ps_cardiovascolari",
    "adi_accessi_ps", "adi_accessi_bassa_urgenza", "adi_ritorni_30g")}
UNITA["adi_assistiti"] = "assistiti in carico"
# etichette brevi per tabelle, filtri e grafici (quelle lunghe stanno in parametri.json)
BREVI = {
    "ricoveri_respiratori": "Ricoveri respiratori",
    "ricoveri_circolatori": "Ricoveri circolatori",
    "ps_accessi": "Accessi in PS",
    "ps_respiratori": "PS respiratori",
    "ps_cardiovascolari": "PS cardiovascolari",
    "adi_assistiti": "Assistiti in ADI",
    "adi_accessi_ps": "PS degli assistiti ADI",
    "adi_accessi_bassa_urgenza": "ADI a bassa urgenza",
    "adi_ritorni_30g": "ADI ritorni entro 30 giorni",
}


class ArchivioSimulato:
    """Il parquet in memoria, in forma larga: una riga per (scenario, comune, giorno), una colonna per indicatore.
    Si ricarica da solo se il file cambia (mtime), come ArchivioDimissioni."""

    def __init__(self, percorso=FILE_SIMULATI, parametri=FILE_PARAMETRI):
        self.percorso = Path(percorso)
        self.file_parametri = Path(parametri)
        self._blocco = threading.Lock()
        self._mtime = None
        self._larga = None
        self._parametri = None

    def disponibile(self):
        return self.percorso.exists() and self.file_parametri.exists()

    def _carica(self):
        if not self.disponibile():
            return None
        with self._blocco:
            mtime = (self.percorso.stat().st_mtime, self.file_parametri.stat().st_mtime)
            if self._larga is None or self._mtime != mtime:
                df = pd.read_parquet(self.percorso, columns=["scenario", "id_comune", "data", "indicatore", "valore"])
                larga = df.pivot_table(index=["scenario", "id_comune", "data"], columns="indicatore", values="valore",
                                       aggfunc="sum").reset_index()
                larga.columns.name = None
                larga["mese"] = larga["data"].str.slice(0, 7)
                self._larga = larga
                self._parametri = json.loads(self.file_parametri.read_text(encoding="utf-8"))
                self._mtime = mtime
            return self._larga

    def parametri(self):
        return self._parametri if self._carica() is not None else None

    def indicatori(self):
        p = self.parametri()
        return list(p["indicatori"]) if p else []

    def periodo(self):
        p = self.parametri()
        return (p["periodo"]["da"], p["periodo"]["a"]) if p else (None, None)

    def righe(self, comuni, scenario, giorni=None, mesi=None):
        """Righe larghe (comune × giorno) dei comuni e dello scenario, ristrette ai giorni o ai mesi chiesti."""
        larga = self._carica()
        if larga is None:
            return None
        sel = larga[(larga["scenario"] == scenario) & larga["id_comune"].isin(set(comuni))]
        if giorni is not None:
            sel = sel[sel["data"].isin(set(giorni))]
        if mesi is not None:
            sel = sel[sel["mese"].isin(set(mesi))]
        return sel


def per_100k_giorno(totale, residenti, giorni):
    """Conteggio della finestra → per 100.000 residenti al giorno (None se manca un denominatore)."""
    if totale is None or not residenti or not giorni:
        return None
    return float(totale) / residenti * PER / giorni


def riassunto_finestra(righe, indicatori, residenti):
    """{indicatore: {totale, giorni, al_giorno, per_100k}} sulle righe (comune × giorno) di una zona. I conteggi si
    sommano sui comuni e si dividono per i giorni distinti; lo stock ADI si somma sui comuni e si media sui giorni."""
    giorni = righe["data"].nunique() if righe is not None else 0
    out = {}
    for ind in indicatori:
        if righe is None or giorni == 0 or ind not in righe:
            out[ind] = {"totale": None, "giorni": 0, "al_giorno": None, "per_100k": None}
            continue
        per_giorno = righe.groupby("data")[ind].sum()
        if ind in STOCK:
            media = float(per_giorno.mean())
            out[ind] = {"totale": media, "giorni": giorni, "al_giorno": media, "per_100k": media / residenti * PER if residenti else None}
        else:
            totale = float(per_giorno.sum())
            out[ind] = {"totale": totale, "giorni": giorni, "al_giorno": totale / giorni,
                        "per_100k": per_100k_giorno(totale, residenti, giorni)}
    return out


def mensile(righe, indicatore):
    """{mese: (totale del mese, giorni con dato)} di un indicatore, somma dei comuni. Per lo stock, la media."""
    if righe is None or righe.empty:
        return {}
    per_giorno = righe.groupby(["mese", "data"])[indicatore].sum().reset_index()
    g = per_giorno.groupby("mese")[indicatore]
    funz = g.mean() if indicatore in STOCK else g.sum()
    giorni = per_giorno.groupby("mese")["data"].nunique()
    return {m: (float(funz[m]), int(giorni[m])) for m in funz.index}
