"""Consuntivi mensili su disco (data/interim/consuntivi/, gitignored): un file per dominio e mese, riletto al posto
di ricalcolare gli aggregati dai dataset di partenza a ogni avvio del server.

- **aria** (`aria_AAAA-MM.pkl`): il `RiassuntoMese` di `aggregati_aria` (comune×mese, distretto×mese, copertura,
  uso della vista «Tutte», stazioni per inquinante) di **tutte le fonti** — evita di aprire il JSON da ~20 MB
  e di rifare i ~14 s di calcolo;
- **calore** (`calore_<statistica>_AAAA-MM.pkl`, `calore_arpa_<statistica>_AAAA-MM.pkl`): comune×giorno di
  ERA5-Land e di ARPA meteo, già portato da cella/stazione a comune.

Un consuntivo vale finché non cambiano i file di origine (la «firma») né l'anagrafica del territorio e le celle
CAMS/ERA5-Land: altrimenti si ignora e si rifà. Scrittura atomica (file temporaneo + rename): un server che legge
mentre lo script scrive non vede mai un file a metà. Nessun filtro silenzioso: un file illeggibile si rifà.
Pickle perché il contenuto è nostro, in una cartella locale; si salvano dizionari di tipi semplici e DataFrame,
non le classi, così i file non dipendono da come si importa il modulo.
"""

import logging
import os
import pickle
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
DIR_CONSUNTIVI = RADICE / "data" / "interim" / "consuntivi"
VERSIONE = 1
log = logging.getLogger(__name__)

_FILE_TERRITORIO = (RADICE / "data" / "territorio" / "anagrafica" / "territorio.json",
                    RADICE / "data" / "dataset" / "aria" / "copernicus_cams" / "Celle_Comuni.json")


def firma_territorio():
    """Tempi di modifica dell'anagrafica del territorio e del mapping celle → comuni."""
    return tuple((f.name, f.stat().st_mtime) for f in _FILE_TERRITORIO if f.exists())


def percorso(nome, cartella=DIR_CONSUNTIVI):
    return Path(cartella) / f"{nome}.pkl"


def leggi(nome, firma, cartella=DIR_CONSUNTIVI):
    """Il contenuto salvato, o None se il file manca, è illeggibile, di un'altra versione o fatto con altri dati."""
    f = percorso(nome, cartella)
    if not f.exists():
        return None
    try:
        with open(f, "rb") as fh:
            d = pickle.load(fh)
        if d["versione"] == VERSIONE and d["firma"] == firma and d["territorio"] == firma_territorio():
            return d["contenuto"]
    except Exception as e:  # noqa: BLE001
        log.warning("consuntivo %s illeggibile (%s): si rifà", f.name, e)
    return None


def scrivi(nome, firma, contenuto, cartella=DIR_CONSUNTIVI):
    f = percorso(nome, cartella)
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(f".tmp{os.getpid()}")
        with open(tmp, "wb") as fh:
            pickle.dump({"versione": VERSIONE, "firma": firma, "territorio": firma_territorio(), "contenuto": contenuto},
                        fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, f)
    except Exception as e:  # noqa: BLE001 — il consuntivo è un'ottimizzazione: se non si scrive, il calcolo resta valido
        log.warning("consuntivo %s non scritto: %s", f.name, e)


def riassunto_in_dict(r):
    """RiassuntoMese → dizionario di tipi semplici."""
    return {c: getattr(r, c) for c in ("mese", "firma", "meta", "fonti_virtuali", "fonti", "inquinanti", "giorni",
                                       "comune_mese", "distretto_mese", "copertura_comune",
                                       "inquinanti_per_stazione", "uso_mese")}
