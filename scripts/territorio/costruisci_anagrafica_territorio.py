#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Costruisce l'anagrafica relazionale del territorio: province → distretti →
comuni, con chiavi primarie ed esterne (v. data/dataset/Anagrafiche_relazionali.md).

Input:
  data/territorio/lista_presidi/Distretti_Salento.json   distretti e comuni afferenti, residenti
  data/territorio/lista_presidi/Presidi_Puglia.json      codici ISTAT dei comuni, codici ASL dei distretti
  data/territorio/confini/comuni_salento.geojson         confini (per il centroide di ogni comune)

Output:
  data/territorio/anagrafica/territorio.json
    tabelle: province, distretti, comuni (v. blocco "schema" del file)

Rilanciare quando cambia la zonizzazione o l'anagrafica comunale:
  uv run scripts/territorio/costruisci_anagrafica_territorio.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # radice del repo, per il package api
from api.comune.anagrafiche import scrivi_anagrafica  # noqa: E402
from api.comune.confini_comuni import carica_confini, centroide  # noqa: E402
from api.comune.distretti_salento import chiave  # noqa: E402

RADICE = Path(__file__).resolve().parents[2]
FILE_DISTRETTI = RADICE / "data" / "territorio" / "lista_presidi" / "Distretti_Salento.json"
FILE_PRESIDI = RADICE / "data" / "territorio" / "lista_presidi" / "Presidi_Puglia.json"
FILE_MITIGAZIONE = RADICE / "data" / "dataset" / "calore" / "clms" / "mitigazione_comuni.json"
FILE_OUTPUT = RADICE / "data" / "territorio" / "anagrafica" / "territorio.json"

PROVINCE = {"LE": ("Lecce", "075"), "BR": ("Brindisi", "074"), "TA": ("Taranto", "073")}  # sigla → (nome, prefisso ISTAT)

# Comuni fusi il 1/1/2019: nell'elenco dei distretti restano due comuni, la mappa ha un solo confine.
FUSIONI_CONFINE = {"PRESICCE": "Presicce-Acquarica", "ACQUARICA DEL CAPO": "Presicce-Acquarica"}

# Comuni fusi: i comuni storici confluiscono in un solo comune attuale (stesso confine), con il
# codice ISTAT del comune fuso e i residenti sommati. Scelta del 14/10/2026: l'anagrafica tiene un
# solo comune, come lo pubblica ISTAT, così sparisce il doppio conteggio in ogni somma su più comuni
# (prima gestito a mano in api/salute/istat.py e scripts/salute/valida_decessi.py).
FUSIONI_COMUNE = {
    "PRESICCE": {"id_comune": "075098", "denominazione": "Presicce-Acquarica"},
    "ACQUARICA DEL CAPO": {"id_comune": "075098", "denominazione": "Presicce-Acquarica"},
}

# Codici ISTAT malformati in Presidi_Puglia.json (campo COD_ISTAT_COMUNI), corretti a mano.
#   BR-03 "07401": cifra mancante; Oria è l'unico comune di Brindisi il cui codice (074011) non compare altrove.
#   TA-08 "73027": zero iniziale perso (073027 = Taranto).
CORREZIONI_ISTAT = {("BR", "ORIA"): "074011"}

SCHEMA = {
    "province": {
        "chiave_primaria": ["id_provincia"],
        "chiavi_esterne": {},
        "colonne": {"id_provincia": "sigla automobilistica (LE, BR, TA)", "denominazione": "nome della provincia"},
    },
    "distretti": {
        "chiave_primaria": ["id_distretto"],
        "chiavi_esterne": {"id_provincia": "province.id_provincia", "id_comune_sede": "comuni.id_comune"},
        "colonne": {
            "id_distretto": "<provincia>-<codice ASL a 2 cifre>, es. BR-01",
            "id_provincia": "provincia del distretto",
            "denominazione": "denominazione ufficiale del distretto socio-sanitario",
            "codice_asl": "codice ASL del distretto (COD_DISTRETTO_ASL)",
            "id_comune_sede": "comune sede del distretto",
        },
    },
    "comuni": {
        "chiave_primaria": ["id_comune"],
        "chiavi_esterne": {"id_distretto": "distretti.id_distretto"},
        "colonne": {
            "id_comune": "codice ISTAT del comune, 6 cifre (testo)",
            "denominazione": "nome del comune",
            "id_distretto": "distretto socio-sanitario di appartenenza",
            "residenti": "popolazione residente (v. Comuni_<provincia>.json)",
            "lat": "latitudine del centroide del confine comunale",
            "lon": "longitudine del centroide del confine comunale",
            "nome_confine": "nome del poligono in comuni_salento.geojson (uguale per i comuni fusi)",
            "copertura_arborea_pct": "% media di copertura arborea sul comune (CLMS Tree Cover Density 2018, 10 m); "
                                     "dato autorevole in data/dataset/calore/clms/mitigazione_comuni.json",
            "suolo_impermeabile_pct": "% media di suolo impermeabile sul comune (CLMS Imperviousness Density 2018, 10 m); "
                                      "stessa origine. Media sull'intero comune, non sulla sola area urbana",
            "nota": "avvertenze sul comune",
        },
    },
}


def codici_istat():
    """{(sigla provincia, chiave nome comune): codice ISTAT a 6 cifre} da Presidi_Puglia.json."""
    with open(FILE_PRESIDI, encoding="utf-8") as f:
        presidi = json.load(f)
    campi = [c["id"] for c in presidi["fields"]]
    codici = {}
    for riga in presidi["records"]:
        r = dict(zip(campi, riga))
        sigla = r["SIGLA_PROVINCIA_SEDE"]
        if sigla not in PROVINCE:
            continue
        nomi, cod = r["COMUNI"].split("|"), r["COD_ISTAT_COMUNI"].split("|")
        if len(nomi) != len(cod):
            raise ValueError(f"{r['DENOMINAZIONE']} ({sigla}): {len(nomi)} comuni ma {len(cod)} codici ISTAT")
        for nome, c in zip(nomi, cod):
            codici[(sigla, chiave(nome))] = CORREZIONI_ISTAT.get((sigla, chiave(nome)), c.zfill(6))
    return codici


def codici_asl():
    """{(sigla provincia, chiave nome comune sede): codice ASL del distretto}."""
    with open(FILE_PRESIDI, encoding="utf-8") as f:
        presidi = json.load(f)
    campi = [c["id"] for c in presidi["fields"]]
    codici = {}
    for riga in presidi["records"]:
        r = dict(zip(campi, riga))
        if r["SIGLA_PROVINCIA_SEDE"] in PROVINCE:
            codici[(r["SIGLA_PROVINCIA_SEDE"], chiave(r["COMUNE_SEDE"]))] = r["COD_DISTRETTO_ASL"]
    return codici


def carica_mitigazione():
    """{id_comune: {prodotto: media %}} dal file autorevole dei fattori di mitigazione (vuoto se non ancora calcolato).
    Solo le celle `VALORE`: un `NULL` resta vuoto nell'anagrafica."""
    if not FILE_MITIGAZIONE.exists():
        print(f"Avviso: {FILE_MITIGAZIONE.relative_to(RADICE)} assente, colonne di mitigazione vuote "
              "(scripts/calore/calcola_mitigazione_comuni.py).", file=sys.stderr)
        return {}
    with open(FILE_MITIGAZIONE, encoding="utf-8") as f:
        comuni = json.load(f)["comuni"]
    return {
        id_comune: {p: riga[p]["valore"] for p in ("copertura_arborea", "suolo_impermeabile") if riga[p]["stato"] == "VALORE"}
        for id_comune, riga in comuni.items()
    }


def main():
    with open(FILE_DISTRETTI, encoding="utf-8") as f:
        distretti_salento = json.load(f)["distretti"]
    codici = codici_istat()
    confini = carica_confini()
    chiavi_confini = {chiave(n): n for n in confini}

    province = [{"id_provincia": s, "denominazione": n} for s, (n, _) in PROVINCE.items()]
    distretti, comuni, errori = [], [], []
    codice_asl = codici_asl()
    fattori_mitigazione = carica_mitigazione()

    for d in distretti_salento:
        sigla = d["provincia"]
        sede = codici.get((sigla, chiave(d["comune_sede"])))
        distretti.append({
            "id_distretto": d["id_distretto"], "id_provincia": sigla, "denominazione": d["denominazione"],
            "codice_asl": codice_asl.get((sigla, chiave(d["comune_sede"]))), "id_comune_sede": sede,
        })
        residenti = {chiave(x["comune"]): x["residenti"] for x in d["n_residenti_comune"]}
        fusi_emessi = set()  # id_comune fuso già aggiunto in questo distretto, per non duplicarlo
        for nome in d["comuni"]:
            k = chiave(nome)
            fusione = FUSIONI_COMUNE.get(k)
            id_comune = fusione["id_comune"] if fusione else codici.get((sigla, k))
            if fusione:
                if id_comune in fusi_emessi:
                    continue  # il componente successivo dello stesso comune fuso: già emesso
                fusi_emessi.add(id_comune)
            nome_confine = FUSIONI_CONFINE.get(k) or chiavi_confini.get(k)
            if id_comune is None:
                errori.append(f"{sigla} {nome}: nessun codice ISTAT in Presidi_Puglia.json")
            if nome_confine is None:
                errori.append(f"{sigla} {nome}: nessun confine in comuni_salento.geojson")
                continue
            if id_comune and not id_comune.startswith(PROVINCE[sigla][1]):
                errori.append(f"{sigla} {nome}: codice ISTAT {id_comune} incoerente con la provincia")
            lat, lon = centroide(confini[nome_confine])
            if fusione:
                componenti = [n for n in d["comuni"] if FUSIONI_COMUNE.get(chiave(n), {}).get("id_comune") == id_comune]
                n_residenti = sum(residenti.get(chiave(n), 0) for n in componenti)
                nota = (f"comune fuso nel 2019 da {' + '.join(componenti)} (ISTAT {id_comune}): "
                        "residenti sommati, confine e centroide condivisi")
                denominazione = fusione["denominazione"]
            else:
                n_residenti = residenti.get(k)
                nota = None
                denominazione = nome
            mitigazione = fattori_mitigazione.get(id_comune, {})
            comuni.append({
                "id_comune": id_comune, "denominazione": denominazione, "id_distretto": d["id_distretto"],
                "residenti": n_residenti, "lat": round(lat, 5), "lon": round(lon, 5),
                "nome_confine": nome_confine,
                "copertura_arborea_pct": mitigazione.get("copertura_arborea"),
                "suolo_impermeabile_pct": mitigazione.get("suolo_impermeabile"),
                "nota": nota,
            })

    codici_comuni = [c["id_comune"] for c in comuni]
    if len(set(codici_comuni)) != len(codici_comuni):
        errori.append("codici ISTAT duplicati fra i comuni")
    usati = {c["nome_confine"] for c in comuni}
    errori += [f"confine senza comune: {n}" for n in confini if n not in usati]
    sedi_ignote = [d["id_distretto"] for d in distretti if d["id_comune_sede"] not in set(codici_comuni)]
    errori += [f"distretto {d}: comune sede fuori dall'elenco dei comuni" for d in sedi_ignote]
    if errori:
        print("ERRORI:\n  " + "\n  ".join(errori), file=sys.stderr)
        return 1

    comuni.sort(key=lambda c: c["id_comune"])
    scrivi_anagrafica(
        FILE_OUTPUT,
        "Anagrafica relazionale del territorio (Salento): province → distretti socio-sanitari → comuni. "
        "Generata da scripts/territorio/costruisci_anagrafica_territorio.py.",
        SCHEMA,
        {"province": province, "distretti": distretti, "comuni": comuni},
    )
    print(f"{len(province)} province, {len(distretti)} distretti, {len(comuni)} comuni → {FILE_OUTPUT.relative_to(RADICE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
