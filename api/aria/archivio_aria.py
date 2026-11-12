#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Archivio del dataset aria: i file mensili di data/interim/aria/ visti come una
serie continua giorno per giorno (v. docs/Regole_dei_dati.md).

Il dataset non si rigenera mai tutto da capo: si costruisce **un mese alla
volta** e i mesi già completi si saltano. Così un anno chiuso (es. il 2025) si
scarica una volta sola e resta in locale, mentre l'anno in corso si estende
ogni giorno rigenerando soltanto il mese aperto — che è l'unico file che può
cambiare, perché le fonti pubblicano in ritardo e rivedono i giorni recenti.

Un file copre sempre un solo mese di calendario:
    dataset_aria_2025-03-01_2025-03-31.json   mese completo, non si rigenera più
    dataset_aria_2026-10-01_2026-10-05.json   mese aperto, si rigenera e sostituisce

Un mese completo è "già buono" solo se è stato generato con lo **stesso elenco di
comuni** dell'anagrafica attuale (impronta del territorio nella testata del file):
dopo una fusione di comuni, come Presicce-Acquarica il 14/10/2026, i mesi vecchi
hanno codici che l'anagrafica non conosce più e vanno rifatti (o corretti offline
con scripts/aria/correggi_comuni_fusi.py, se basta ricalcolare la stazione CAMS).

Qui stanno solo le regole dell'archivio (quali blocchi servono, quali file sono
già buoni, quali sono scaduti) e l'indice di copertura; la generazione del
singolo mese resta in api/aria/dataset_aria.py e scripts/aria/genera_dataset_aria.py.
"""

import calendar
import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
DIR_ARCHIVIO = RADICE / "data" / "interim" / "aria"
FILE_COPERTURA = RADICE / "data" / "dataset" / "aria" / "report" / "Copertura_archivio_aria.md"
MODELLO_NOME = re.compile(r"^dataset_aria_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.json$")
# testata scritta da dataset_aria.a_json subito dopo "periodo": si legge dai primi KB senza aprire tutto il file
MODELLO_TESTATA = re.compile(r'"territorio": \{"comuni": \d+, "impronta": "([0-9a-f]+)"')


def impronta_territorio(id_comuni) -> str:
    """Impronta dell'elenco dei comuni: cambia se un comune si aggiunge, si toglie o si fonde con un altro."""
    return hashlib.sha1(",".join(sorted(id_comuni)).encode("utf-8")).hexdigest()[:12]


def impronta_file(percorso):
    """Impronta del territorio con cui è stato generato un file dell'archivio, o None se illeggibile.

    Dalla testata se c'è; i file generati prima del 14/10/2026 non la hanno e l'impronta si ricava
    dai comuni di `dati` (che sono sempre tutti quelli dell'anagrafica del momento)."""
    percorso = Path(percorso)
    try:
        with open(percorso, encoding="utf-8") as f:
            trovata = MODELLO_TESTATA.search(f.read(4096))
        if trovata:
            return trovata.group(1)
        dati = json.loads(percorso.read_text(encoding="utf-8"))["dati"]
    except (OSError, ValueError, KeyError):
        return None
    return impronta_territorio(c for provincia in dati.values() for distretto in provincia.values() for c in distretto)


def nome_file(da: date, a: date) -> str:
    return f"dataset_aria_{da.isoformat()}_{a.isoformat()}.json"


def ultimo_giorno(anno: int, mese: int) -> date:
    return date(anno, mese, calendar.monthrange(anno, mese)[1])


def blocchi_mensili(da: date, a: date):
    """[(inizio, fine)] del periodo spezzato sui mesi di calendario: ogni blocco
    è un file. Il primo e l'ultimo possono essere parziali."""
    blocchi, inizio = [], da
    while inizio <= a:
        fine_mese = ultimo_giorno(inizio.year, inizio.month)
        fine = min(fine_mese, a)
        blocchi.append((inizio, fine))
        inizio = fine_mese + timedelta(days=1)
    return blocchi


def file_presenti(cartella=DIR_ARCHIVIO):
    """[(da, a, percorso)] dei file di dataset nella cartella, ordinati per data."""
    cartella = Path(cartella)
    if not cartella.is_dir():
        return []
    trovati = []
    for p in cartella.glob("dataset_aria_*.json"):
        m = MODELLO_NOME.match(p.name)
        if m:
            trovati.append((date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2)), p))
    return sorted(trovati)


def giorni_coperti(cartella=DIR_ARCHIVIO):
    """Insieme dei giorni (date) per cui esiste almeno un file."""
    giorni = set()
    for da, a, _ in file_presenti(cartella):
        g = da
        while g <= a:
            giorni.add(g)
            g += timedelta(days=1)
    return giorni


def ultimo_giorno_coperto(cartella=DIR_ARCHIVIO):
    """L'ultimo giorno presente nell'archivio, o None se è vuoto."""
    presenti = file_presenti(cartella)
    return max(a for _, a, _ in presenti) if presenti else None


def file_che_copre(da: date, a: date, cartella=DIR_ARCHIVIO):
    """Il file già esistente che copre interamente [da, a] (il più recente se
    ce n'è più d'uno), o None: è quello che permette di saltare il blocco."""
    candidati = [p for d, f, p in file_presenti(cartella) if d <= da and f >= a]
    return max(candidati, key=lambda p: p.stat().st_mtime) if candidati else None


def file_superati(da: date, a: date, cartella=DIR_ARCHIVIO):
    """I file dello stesso mese di calendario che il nuovo blocco [da, a]
    rimpiazza: stesso mese e periodo contenuto nel nuovo, nome diverso.

    Serve a non accumulare un file per ogni giorno nel mese aperto: la
    generazione del 5 ottobre sostituisce quella del 4, invece di affiancarla
    (il server terrebbe comunque il più recente, ma la cartella crescerebbe)."""
    nuovo = nome_file(da, a)
    return [p for d, f, p in file_presenti(cartella)
            if p.name != nuovo and (d.year, d.month) == (da.year, da.month)
            and (f.year, f.month) == (da.year, da.month) and d >= da and f <= a]


def stato_blocchi(da: date, a: date, cartella=DIR_ARCHIVIO, rigenera=False, impronta=None):
    """[(inizio, fine, motivo)] per ogni blocco mensile del periodo.

    `motivo`: "nuovo" (nessun file), "esteso" (c'è un file dello stesso mese ma
    più corto: il mese era aperto), "rigenerato" (c'è già ma --rigenera),
    "anagrafica" (c'è già ma è stato generato con un elenco di comuni diverso da
    `impronta`, quella dell'anagrafica attuale: si rifà) o "presente" (già
    completo: si salta)."""
    fuori = []
    for inizio, fine in blocchi_mensili(da, a):
        esistente = file_che_copre(inizio, fine, cartella)
        if esistente is None:
            motivo = "esteso" if file_superati(inizio, fine, cartella) else "nuovo"
        elif rigenera:
            motivo = "rigenerato"
        else:
            motivo = "anagrafica" if impronta and impronta_file(esistente) != impronta else "presente"
        fuori.append((inizio, fine, motivo))
    return fuori


# --- indice di copertura ------------------------------------------------------
# Una riga per mese e fonte: quante celle hanno un valore e quanta parte del
# territorio tocca. Risponde alla domanda "quali distretti restano senza dato
# in questo mese" senza riaprire i JSON, e dichiara dove il dato è solo
# modellato (CAMS), come richiesto da docs/Regole_dei_dati.md.

INTESTAZIONE_COPERTURA = """# Copertura dell'archivio aria

Rigenerato da `scripts/aria/genera_dataset_aria.py` a ogni esecuzione: tiene le righe
dei mesi già presenti e aggiorna solo quelli rigenerati. I file del dataset stanno in
`data/interim/aria/` (gitignored), uno per mese.

Nella tabella compaiono solo i mesi **generati da questo script**: un mese archiviato prima che la
tabella esistesse resta nel dataset ma non qui, finché non lo si rigenera con `--rigenera`.

Per ogni mese e fonte: celle con un valore, distretti e comuni con almeno un valore, e
inquinanti osservati. **CAMS è una fonte modellata** (griglia 0,1°, stazioni virtuali per
comune): copre tutti i 145 comuni e tutti i 20 distretti, ma non è una misura. Le fonti
misurate (ARPA, OpenAQ, EEA) hanno stazioni in 21 comuni su 145 e 12 distretti su 20:
i distretti che restano vuoti non dipendono dal periodo scelto, non hanno centraline.
"""


def _riga_copertura(ds):
    """{fonte: riga} della copertura di un mese, dal DatasetAria appena generato."""
    g = ds.griglia
    valori = g[g["stato"] == "VALORE"]
    righe = {}
    for fonte in ds.fonti:
        v = valori[valori["fonte"] == fonte]
        righe[fonte] = {
            "celle_valore": int(len(v)),
            "distretti": int(v["distretto"].nunique()),
            "comuni": int(v["comune"].nunique()),
            "stazioni": int(v["stazione"].nunique()),
            "inquinanti": sorted(v["inquinante"].unique().tolist()),
            "modellata": bool(ds.proprieta_fonti.get(fonte, {}).get("modellata")),
        }
    return righe


def aggiorna_copertura(ds, file_copertura=FILE_COPERTURA):
    """Aggiunge (o sostituisce) le righe del mese di `ds` nella tabella di copertura.

    La tabella si tiene in un blocco JSON in coda al markdown, così la rigenerazione
    incrementale non deve rileggere i dataset dei mesi vecchi."""
    return _scrivi_copertura(ds.data_inizio, ds.data_fine, ds.generato_il, _riga_copertura(ds), file_copertura)


def aggiorna_copertura_da_json(js, file_copertura=FILE_COPERTURA):
    """Come aggiorna_copertura, ma da un file dell'archivio già scritto (il dict di dataset_aria.a_json):
    serve quando un mese si corregge senza rigenerarlo (scripts/aria/correggi_comuni_fusi.py)."""
    righe = {f: {"celle_valore": 0, "distretti": set(), "comuni": set(), "stazioni": set(), "inquinanti": set(),
                 "modellata": bool(p.get("modellata"))} for f, p in js["fonti"].items()}
    for provincia in js["dati"].values():
        for distretto, comuni in provincia.items():
            for comune, stazioni in comuni.items():
                for stazione, giorni in stazioni.items():
                    for fonti in giorni.values():
                        for fonte, inquinanti in fonti.items():
                            for inquinante, foglia in inquinanti.items():
                                if foglia["stato"] == "VALORE":
                                    r = righe[fonte]
                                    r["celle_valore"] += 1
                                    r["distretti"].add(distretto)
                                    r["comuni"].add(comune)
                                    r["stazioni"].add(stazione)
                                    r["inquinanti"].add(inquinante)
    righe = {f: {**r, **{k: len(r[k]) for k in ("distretti", "comuni", "stazioni")},
                 "inquinanti": sorted(r["inquinanti"])} for f, r in righe.items()}
    return _scrivi_copertura(date.fromisoformat(js["periodo"]["da"]), date.fromisoformat(js["periodo"]["a"]),
                             js["generato_il"], righe, file_copertura)


def _scrivi_copertura(data_inizio, data_fine, generato_il, righe_fonti, file_copertura):
    file_copertura = Path(file_copertura)
    indice = {}
    if file_copertura.exists():
        testo = file_copertura.read_text(encoding="utf-8")
        if "<!-- indice" in testo:
            grezzo = testo.split("<!-- indice", 1)[1].split("-->", 1)[0]
            try:
                indice = json.loads(grezzo.split("\n", 1)[1])
            except (ValueError, IndexError):
                indice = {}
    chiave = f"{data_inizio.year:04d}-{data_inizio.month:02d}"
    indice[chiave] = {
        "periodo": {"da": data_inizio.isoformat(), "a": data_fine.isoformat()},
        "giorni": (data_fine - data_inizio).days + 1,
        "generato_il": generato_il,
        "fonti": righe_fonti,
    }
    file_copertura.parent.mkdir(parents=True, exist_ok=True)
    file_copertura.write_text(_markdown_copertura(indice), encoding="utf-8")
    return indice


def _markdown_copertura(indice):
    fonti = sorted({f for m in indice.values() for f in m["fonti"]})
    righe = ["| Mese | Giorni | " + " | ".join(f"{f} — celle / distretti / comuni" for f in fonti) + " |",
             "|---|---:|" + "---:|" * len(fonti)]
    for mese in sorted(indice):
        m = indice[mese]
        celle = []
        for f in fonti:
            d = m["fonti"].get(f)
            celle.append("—" if d is None else
                         f"{d['celle_valore']} / {d['distretti']} / {d['comuni']}"
                         + (" *(mod.)*" if d.get("modellata") else ""))
        parziale = " *(parziale)*" if m["giorni"] < 28 else ""
        righe.append(f"| {mese}{parziale} | {m['giorni']} | " + " | ".join(celle) + " |")

    inquinanti = sorted({i for m in indice.values() for d in m["fonti"].values() for i in d["inquinanti"]})
    coda = ["", f"Inquinanti osservati nell'archivio: {', '.join(inquinanti) or '—'}.",
            f"Mesi presenti: {len(indice)}.", "",
            "<!-- indice (non modificare a mano: lo riscrive genera_dataset_aria.py)",
            json.dumps(indice, ensure_ascii=False, indent=1), "-->", ""]
    return INTESTAZIONE_COPERTURA + "\n" + "\n".join(righe) + "\n" + "\n".join(coda)
