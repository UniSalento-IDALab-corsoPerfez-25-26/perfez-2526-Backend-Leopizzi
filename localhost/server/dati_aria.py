"""Dataset aria in SQLite **in memoria** (nessun database persistente, docs/Architettura.md): i JSON di
data/interim/aria/ sono la fonte, la tabella `misure_aria` si ricostruisce al primo uso di un file
e muore con il processo. Si ricarica da sola se il file cambia (nuova generazione del dataset)."""

import calendar
import json
import re
import sqlite3
import threading
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

RADICE = Path(__file__).resolve().parents[2]
DIR_DATASET = RADICE / "data" / "interim" / "aria"
MODELLO_NOME = re.compile(r"dataset_aria_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.json$")
MAX_FILE_IN_MEMORIA = 4  # un file = un periodo (di solito un mese): si tengono i più usati di recente

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS misure_aria (
    file TEXT NOT NULL, provincia TEXT, distretto TEXT, comune TEXT NOT NULL, stazione TEXT NOT NULL,
    giorno TEXT NOT NULL, fonte TEXT NOT NULL, inquinante TEXT NOT NULL,
    valore REAL, stato TEXT NOT NULL, nota TEXT
);
CREATE INDEX IF NOT EXISTS ix_misure_giorno ON misure_aria (file, giorno, comune);
"""


class ArchivioAria:
    def __init__(self, cartella=DIR_DATASET):
        self.cartella = Path(cartella)
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.executescript(SCHEMA_SQL)
        self.meta = {}  # nome file -> {mtime, generato_il, fonti, inquinanti, stazioni, uso}
        self._blocco = threading.RLock()
        self._contatore_uso = 0

    def periodi(self):
        """[(da, a, mtime, percorso)] dei file di dataset presenti, letti dal nome del file."""
        out = []
        for p in self.cartella.glob("dataset_aria_*.json"):
            m = MODELLO_NOME.search(p.name)
            if m:
                out.append((date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2)), p.stat().st_mtime, p))
        return out

    def file_per_giorno(self, giorno: date):
        """Il file del dataset che copre il giorno (il più recente se ce n'è più d'uno), o None."""
        candidati = [(mtime, p) for da, a, mtime, p in self.periodi() if da <= giorno <= a]
        return max(candidati)[1] if candidati else None

    def giorni_disponibili(self):
        """[date] ordinate dei giorni coperti da almeno un file: è l'asse della barra
        temporale della dashboard, che scorre giorno per giorno."""
        giorni = set()
        for da, a, _, _ in self.periodi():
            g = da
            while g <= a:
                giorni.add(g)
                g += timedelta(days=1)
        return sorted(giorni)

    def buchi(self):
        """['AAAA-MM-GG → AAAA-MM-GG'] degli intervalli non coperti dentro l'archivio: la barra
        temporale li mostra come vuoti invece di far sembrare continua una serie che non lo è."""
        giorni = self.giorni_disponibili()
        if not giorni:
            return []
        fuori, atteso = [], giorni[0]
        for g in giorni:
            if g > atteso:
                fuori.append(f"{atteso.isoformat()} → {(g - timedelta(days=1)).isoformat()}")
            atteso = g + timedelta(days=1)
        return fuori

    def mesi_disponibili(self):
        """{'AAAA-MM': giorni del mese coperti da almeno un file}, dai soli nomi dei file (nessuna lettura)."""
        giorni = set()
        for da, a, _, _ in self.periodi():
            g = da
            while g <= a:
                giorni.add(g)
                g += timedelta(days=1)
        mesi = {}
        for g in giorni:
            chiave = f"{g.year:04d}-{g.month:02d}"
            mesi[chiave] = mesi.get(chiave, 0) + 1
        return dict(sorted(mesi.items()))

    def celle_mese(self, mese: str):
        """(DataFrame, meta) con **tutte** le celle del mese 'AAAA-MM' (anche NULL e NO_DATA: servono a
        distinguere i due stati quando si aggrega), oppure None se nessun file copre il mese.
        Ogni giorno viene dal file più recente che lo copre, come in `file_per_giorno`.
        Colonne: distretto, comune, stazione, giorno, fonte, inquinante, valore, stato, nota.
        `meta`: file usati (con data di generazione), fonti, unità degli inquinanti, schede delle stazioni."""
        anno, num = (int(x) for x in mese.split("-"))
        giorni = [date(anno, num, g) for g in range(1, calendar.monthrange(anno, num)[1] + 1)]
        per_file = {}
        for g in giorni:
            p = self.file_per_giorno(g)
            if p is not None:
                per_file.setdefault(p, []).append(g.isoformat())
        if not per_file:
            return None
        parti, meta = [], {"file": [], "fonti": {}, "inquinanti": {}, "stazioni": {}, "giorni_coperti": 0,
                           "giorni_del_mese": len(giorni)}
        with self._blocco:
            for percorso, gg in per_file.items():
                self._carica(percorso)
                m = self.meta[percorso.name]
                parte = pd.read_sql_query(
                    "SELECT distretto, comune, stazione, giorno, fonte, inquinante, valore, stato, nota "
                    "FROM misure_aria WHERE file = ? AND giorno >= ? AND giorno <= ?",
                    self.conn, params=(percorso.name, min(gg), max(gg)))
                parti.append(parte[parte["giorno"].isin(gg)])  # i giorni di un altro file più recente restano fuori
                meta["file"].append({"nome": percorso.name, "generato_il": m["generato_il"], "giorni": len(gg)})
                meta["fonti"].update(m.get("fonti_dettaglio") or {f: {} for f in m["fonti"]})
                meta["inquinanti"].update(m["inquinanti"])
                meta["stazioni"].update(m["stazioni"])
                meta["giorni_coperti"] += len(gg)
        return pd.concat(parti, ignore_index=True), meta

    def _carica(self, percorso: Path):
        nome, mtime = percorso.name, percorso.stat().st_mtime
        self._contatore_uso += 1
        if nome in self.meta and self.meta[nome]["mtime"] == mtime:
            self.meta[nome]["uso"] = self._contatore_uso
            return
        with open(percorso, encoding="utf-8") as f:
            dati = json.load(f)
        righe = []
        for prov, distretti in dati["dati"].items():
            for distretto, comuni in distretti.items():
                for comune, stazioni in comuni.items():
                    for stazione, giorni in stazioni.items():
                        for giorno, fonti in giorni.items():
                            for fonte, inquinanti in fonti.items():
                                for inq, cella in inquinanti.items():
                                    righe.append((nome, prov, distretto, comune, stazione, giorno, fonte, inq,
                                                  cella["valore"], cella["stato"], cella["nota"]))
        self.conn.execute("DELETE FROM misure_aria WHERE file = ?", (nome,))
        self.conn.executemany("INSERT INTO misure_aria VALUES (?,?,?,?,?,?,?,?,?,?,?)", righe)
        self.meta[nome] = {
            "mtime": mtime, "generato_il": dati.get("generato_il"), "fonti": list(dati.get("fonti", {})),
            "fonti_dettaglio": dati.get("fonti", {}),  # copertura_da e, dai dataset del 02/10, modellata/stazioni_virtuali
            "inquinanti": dati.get("inquinanti", {}), "stazioni": dati.get("stazioni", {}), "uso": self._contatore_uso,
        }
        while len(self.meta) > MAX_FILE_IN_MEMORIA:  # via il meno usato di recente
            vecchio = min(self.meta, key=lambda n: self.meta[n]["uso"])
            self.conn.execute("DELETE FROM misure_aria WHERE file = ?", (vecchio,))
            del self.meta[vecchio]
        self.conn.commit()

    def valori_del_giorno(self, giorno: date, id_comuni):
        """(nome_file, meta, righe) con le celle del giorno per i comuni indicati, oppure None se nessun
        dataset copre il giorno. Ogni riga: (comune, stazione, fonte, inquinante, valore, stato, nota)."""
        percorso = self.file_per_giorno(giorno)
        if percorso is None:
            return None
        with self._blocco:
            self._carica(percorso)
            segnaposto = ",".join("?" * len(id_comuni))
            righe = self.conn.execute(
                f"SELECT comune, stazione, fonte, inquinante, valore, stato, nota FROM misure_aria "
                f"WHERE file = ? AND giorno = ? AND comune IN ({segnaposto})",
                (percorso.name, giorno.isoformat(), *id_comuni),
            ).fetchall()
            return percorso.name, dict(self.meta[percorso.name]), righe
