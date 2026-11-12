#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client ISTAT **Health for All** (HFA, canale C di data/dataset/salute/istat/ISTAT.md): dimissioni
ospedaliere per gruppo di patologia, **provincia × anno**, 1999 -> ultimo anno del rilascio.

Riaperto il 18/10/2026 su richiesta di Matteo, **solo per le dimissioni** e **solo a titolo
informativo**: il dato è annuale e provinciale, quindi non entra nelle correlazioni né nel confronto
distretto × mese; in dashboard si affianca ai decessi con la convenzione `~` (v. docs/Regole_dei_dati.md).

Formato (binario non documentato, decodificato e verificato il 01/10/2026 su valori noti):
  HFA/Data/11600.<anno>  float32 little-endian, ordinato per indicatore:
                         offset = (indice_indicatore * n_territori + indice_territorio) * 4
  HFA/Data/11600.ind     uint16 con il numero di indicatori, poi i loro codici (uint16)
  HFA/Data/11600.rid     codici dei territori, record a 16 byte terminati da NUL
  `11600` è il dataset della Puglia: 1601 Foggia, 1602 Bari, 1603 Taranto, 1604 Brindisi,
  1605 Lecce, 1606 BAT, 1607 Puglia. Il valore mancante è -1e8.

Stati (docs/Regole_dei_dati.md): anno fuori dalla copertura della provincia -> NO_DATA; anno coperto ma
tasso o conteggio mancante, non finito o negativo -> la cella resta vuota con la nota del motivo
(stato NULL se mancano entrambi). Il conteggio totale è la somma di maschi e femmine (HFA non
pubblica il totale M+F dei conteggi); se manca uno dei due sessi il conteggio è vuoto.
"""

import re
import struct
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

RADICE = Path(__file__).resolve().parents[2]
URL_PAGINA = "https://www.istat.it/sistema-informativo-6/health-for-all-italia/"
URL_NOTO = "https://www.istat.it/wp-content/uploads/2026/04/HFA_giugno.zip"  # ripiego se la pagina cambia
DIR_CACHE = RADICE / "data" / "raw" / "salute" / "istat_hfa"
TIMEOUT = 300
INTESTAZIONI = {"User-Agent": "Mozilla/5.0 (OneHealth; ricerca universitaria)"}
DATASET_PUGLIA = "11600"
MANCANTE = -1e8
ANNO_INIZIO, ANNO_FINE = 1999, 2024  # copertura dichiarata nella lista indicatori (giugno 2026)

# territori del Salento nel dataset della Puglia -> sigla di provincia
PROVINCE = {"1605": "LE", "1604": "BR", "1603": "TA"}

# gruppo -> (etichetta, codice tasso M+F per 10.000 ab., codice conteggio M, codice conteggio F)
GRUPPI = {
    "respiratorio": ("Malattie dell'apparato respiratorio", 8550, 8556, 8557),
    "bpco": ("Malattie polmonari croniche ostruttive (BPCO)", 8610, 8616, 8617),
    "circolatorio": ("Malattie del sistema circolatorio", 8430, 8436, 8437),
    "ischemiche": ("Malattie ischemiche del cuore", 8460, 8466, 8467),
    "cerebrovascolari": ("Malattie cerebrovascolari", 8520, 8526, 8527),
}

_RE_LINK = re.compile(r'href="(https://www\.istat\.it/wp-content/uploads/[^"]*/HFA_[^"/]*\.zip)"', re.IGNORECASE)


class HfaError(RuntimeError):
    """Errore nel prelievo o nella lettura di Health for All."""


def trova_url():
    """URL dello ZIP HFA più recente letto dalla pagina ISTAT (il nome contiene il mese di rilascio)."""
    try:
        r = requests.get(URL_PAGINA, timeout=TIMEOUT, headers=INTESTAZIONI)
        if r.status_code == 200:
            link = _RE_LINK.findall(r.text)
            if link:
                return link[0]
    except requests.RequestException:
        pass
    return URL_NOTO


def scarica_zip(url=None, forza=False):
    """Scarica lo ZIP HFA (~26 MB) in data/raw/salute/istat_hfa/ (gitignored) e ne restituisce il percorso."""
    url = url or trova_url()
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    destinazione = DIR_CACHE / url.rsplit("/", 1)[-1]
    if destinazione.exists() and not forza:
        return destinazione
    try:
        r = requests.get(url, timeout=TIMEOUT, headers=INTESTAZIONI)
    except requests.RequestException as exc:
        raise HfaError(f"HFA non raggiungibile: {url} ({exc})") from exc
    if r.status_code != 200 or not r.content.startswith(b"PK"):
        raise HfaError(f"HFA: risposta inattesa da {url} (HTTP {r.status_code})")
    destinazione.write_bytes(r.content)
    return destinazione


def _indicatori(z):
    ind = z.read(f"HFA/Data/{DATASET_PUGLIA}.ind")
    n = struct.unpack("<H", ind[:2])[0]
    if len(ind) != 2 + 2 * n:
        raise HfaError("HFA: file .ind di dimensione inattesa (formato cambiato?)")
    return n, {int(c): i for i, c in enumerate(np.frombuffer(ind[2:], dtype="<u2"))}


def _territori(z):
    rid = z.read(f"HFA/Data/{DATASET_PUGLIA}.rid")
    codici = [rid[i:i + 16].split(b"\0")[0].decode("ascii") for i in range(0, len(rid), 16)]
    mancanti = [c for c in PROVINCE if c not in codici]
    if mancanti:
        raise HfaError(f"HFA: territori {mancanti} assenti dal dataset {DATASET_PUGLIA} (formato cambiato?)")
    return codici


def _valido(x):
    return bool(np.isfinite(x)) and x > MANCANTE / 2 and x >= 0


def leggi_dimissioni(percorso_zip):
    """Tabella lunga provincia × anno × gruppo: colonne provincia, anno, gruppo, dimissioni, tasso,
    stato, nota. `tasso` è per 10.000 abitanti (già calcolato da ISTAT); `dimissioni` è la somma M+F."""
    try:
        z = zipfile.ZipFile(percorso_zip)
        n, codici_ind = _indicatori(z)
        territori = _territori(z)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise HfaError(f"HFA: ZIP non valido o senza il dataset {DATASET_PUGLIA}: {exc}") from exc
    for gruppo, (_, *cod) in GRUPPI.items():
        assenti = [c for c in cod if c not in codici_ind]
        if assenti:
            raise HfaError(f"HFA: indicatori {assenti} ({gruppo}) assenti (codici cambiati?)")

    righe = []
    for anno in range(ANNO_INIZIO, ANNO_FINE + 1):
        try:
            dati = z.read(f"HFA/Data/{DATASET_PUGLIA}.{anno}")
        except KeyError:
            dati = None
        if dati is not None:
            if len(dati) != n * len(territori) * 4:
                raise HfaError(f"HFA: file {anno} di dimensione inattesa ({len(dati)} byte)")
            m = np.frombuffer(dati, dtype="<f4").reshape(n, len(territori))
        for codice, sigla in PROVINCE.items():
            t = territori.index(codice)
            for gruppo, (_, c_tasso, c_m, c_f) in GRUPPI.items():
                if dati is None:
                    righe.append((sigla, anno, gruppo, None, None, "NO_DATA", f"file {anno} assente dal rilascio HFA"))
                    continue
                tasso, m_, f_ = (float(m[codici_ind[c], t]) for c in (c_tasso, c_m, c_f))
                note = []
                if not _valido(tasso):
                    tasso = None
                    note.append("tasso mancante nella fonte")
                if _valido(m_) and _valido(f_):
                    dimissioni = m_ + f_
                else:
                    dimissioni = None
                    note.append("conteggio mancante nella fonte (maschi o femmine)")
                stato = "NULL" if tasso is None and dimissioni is None else "VALORE"
                righe.append((sigla, anno, gruppo, dimissioni, tasso, stato, "; ".join(note) or None))
    df = pd.DataFrame(righe, columns=["provincia", "anno", "gruppo", "dimissioni", "tasso", "stato", "nota"])
    # un anno in cui la provincia non ha alcun valore in nessun gruppo è fuori copertura, non "mancante"
    tutto_vuoto = df.groupby(["provincia", "anno"])["stato"].transform(lambda s: (s != "VALORE").all())
    df.loc[tutto_vuoto, ["stato", "nota"]] = ["NO_DATA", "anno non coperto dalla fonte per questa provincia"]
    return df
