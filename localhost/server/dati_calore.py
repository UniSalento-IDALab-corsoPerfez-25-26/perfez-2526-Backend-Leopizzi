"""Temperatura ERA5-Land per la dashboard: **legge solo la cache locale** (data/raw/calore/era5_land/), come
CAMS per l'aria — una richiesta al CDS dura minuti, quindi non si fa dentro una richiesta HTTP. La cache si
riempie con scripts/calore/scarica_era5_land.py.

Per comune il valore è la media pesata sull'area delle celle 0,1° (api/calore/era5_land.py); per distretto è la
media pesata sui residenti dei comuni con VALORE (api/comune/aggregazione.py, regola del 02/10/2026).
"""

import re
import threading
from calendar import monthrange

from api.aria.copernicus_cams import CopernicusError
from api.calore import arpa_meteo, dataset_calore, era5_land
from api.comune.aggregazione import media_per_comune, media_per_distretto, per_mese
from localhost.server import consuntivi

FONTE = "Copernicus ERA5-Land, temperatura dell'aria a 2 m, statistiche giornaliere in UTC+1 (rianalisi, dato modellato)"
LICENZA = "CC BY 4.0 (licenza Copernicus; attribuzione obbligatoria)"
UNITA = "°C"
FONTE_ARPA = "ARPA Puglia, rete meteo: temperatura dell'aria misurata (RRQA oraria, rete dedicata ogni 30 minuti), UTC+1"
LICENZA_ARPA = "CC BY 4.0 (ARPA Puglia, dati.puglia.it)"
_FILE = re.compile(r"^(media|massima|minima)_(\d{4})-(\d{2})\.parquet$")


class ArchivioCalore:
    def __init__(self):
        self._blocco = threading.Lock()
        self._cache = {}  # (statistica, mese) -> (mtime, comune_giorno)
        self._cache_arpa = {}  # (statistica, mese) -> (impronta dei file, comune_giorno)

    @staticmethod
    def mesi_in_cache():
        """{statistica: [AAAA-MM, ...]} dei mesi già scaricati."""
        out = {s: [] for s in era5_land.STATISTICHE}
        if era5_land.DIR_CACHE.exists():
            for f in sorted(era5_land.DIR_CACHE.glob("*.parquet")):
                m = _FILE.match(f.name)
                if m:
                    out[m.group(1)].append(f"{m.group(2)}-{m.group(3)}")
        return out

    def comune_giorno(self, statistica, mese):
        """DataFrame comune × giorno (comune, giorno, valore, stato, nota) o None se il mese non è in cache."""
        anno, num = int(mese[:4]), int(mese[5:])
        file = era5_land._file_cache(statistica, anno, num)
        if not file.exists():
            return None
        mtime = file.stat().st_mtime
        with self._blocco:
            trovato = self._cache.get((statistica, mese))
            if trovato and trovato[0] == mtime:
                return trovato[1]
            firma = ((file.name, mtime),)
            df = consuntivi.leggi(f"calore_{statistica}_{mese}", firma)  # consuntivo mensile su disco
            if df is None:
                try:
                    df = era5_land.temperatura_comuni(statistica, anno, num, scarica=False)
                except CopernicusError:
                    return None
                consuntivi.scrivi(f"calore_{statistica}_{mese}", firma, df)
            self._cache[(statistica, mese)] = (mtime, df)
            return df

    def ultimo_giorno(self):
        """Ultimo giorno con un VALORE in tutte le statistiche (la più corta decide), o None se la cache è vuota."""
        fine = None
        for statistica, mesi in self.mesi_in_cache().items():
            ultimo = None
            for mese in reversed(mesi):
                df = self.comune_giorno(statistica, mese)
                giorni = df.loc[df["stato"] == "VALORE", "giorno"] if df is not None else ()
                if len(giorni):
                    ultimo = giorni.max()
                    break
            if ultimo is None:
                return None
            fine = ultimo if fine is None else min(fine, ultimo)
        return fine

    def mese_completo(self, mese):
        """Vero se ogni statistica del mese è in cache con un VALORE per ogni giorno."""
        for statistica in era5_land.STATISTICHE:
            df = self.comune_giorno(statistica, mese)
            if df is None or df.loc[df["stato"] == "VALORE", "giorno"].nunique() < monthrange(int(mese[:4]), int(mese[5:]))[1]:
                return False
        return True

    def distretto_giorno(self, statistica, mese):
        df = self.comune_giorno(statistica, mese)
        if df is None:
            return None
        return media_per_distretto(df, colonna_tempo="giorno", chiavi=[])

    def distretto_mese(self, statistica, mese):
        """Media del mese per distretto (distretto, mese, valore, stato, nota, ...) o None se il mese non è in cache."""
        df = self.distretto_giorno(statistica, mese)
        if df is None:
            return None
        return per_mese(df, chiavi=(), colonna_zona="distretto")

    def valori_del_giorno(self, giorno, comuni):
        """{id_comune: {statistica: riga}} del giorno per i comuni indicati, solo per le statistiche in cache."""
        mese = giorno[:7]
        out = {}
        for statistica in era5_land.STATISTICHE:
            df = self.comune_giorno(statistica, mese)
            if df is None:
                continue
            sel = df[(df["giorno"] == giorno) & (df["comune"].isin(comuni))]
            for r in sel.itertuples():
                out.setdefault(r.comune, {})[statistica] = r
        return out

    # ---------------------------------------------------------------- ARPA meteo (misurato)
    @staticmethod
    def _impronta_arpa(anno):
        """Tempi di modifica dei CSV ARPA dell'anno: se cambiano (scarica_arpa_meteo.py) la cache dei calcoli scade."""
        if not arpa_meteo.DIR_CACHE.exists():
            return ()
        return tuple(sorted((f.name, f.stat().st_mtime) for f in arpa_meteo.DIR_CACHE.glob(f"*_{anno}.csv")))

    @staticmethod
    def arpa_disponibile():
        return arpa_meteo.DIR_CACHE.exists() and any(arpa_meteo.DIR_CACHE.glob("*_*_*.csv"))

    def arpa_comune_giorno(self, statistica, mese):
        """Comune × giorno da ARPA meteo: media delle stazioni fisiche del comune con VALORE (stessa regola
        dell'aria); i comuni senza stazioni sono NO_DATA. None se non c'è nessun CSV dell'anno in cache."""
        anno = int(mese[:4])
        impronta = self._impronta_arpa(anno)
        if not impronta:
            return None
        with self._blocco:
            trovato = self._cache_arpa.get((statistica, mese))
            if trovato and trovato[0] == impronta:
                return trovato[1]
            df = consuntivi.leggi(f"calore_arpa_{statistica}_{mese}", impronta)  # consuntivo mensile su disco
            if df is None:
                dataset_calore._arpa_anno.cache_clear()  # i CSV sono cambiati: rileggi
                per_stat, _ = dataset_calore._arpa(dataset_calore._territorio(), dataset_calore.arpa_meteo_stazioni(), anno, int(mese[5:]))
                df = media_per_comune(per_stat[statistica], chiavi=())
                consuntivi.scrivi(f"calore_arpa_{statistica}_{mese}", impronta, df)
            self._cache_arpa[(statistica, mese)] = (impronta, df)
            return df

    def arpa_distretto_giorno(self, statistica, mese):
        df = self.arpa_comune_giorno(statistica, mese)
        return None if df is None else media_per_distretto(df, colonna_tempo="giorno", chiavi=[])
