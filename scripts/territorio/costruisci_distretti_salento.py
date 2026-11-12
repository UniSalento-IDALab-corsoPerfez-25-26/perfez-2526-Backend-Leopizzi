#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Costruisce la tabella distretto socio-sanitario -> comuni per il Salento
(province di Lecce, Brindisi e Taranto).

Input:
  data/territorio/lista_presidi/Presidi_Puglia.json   (distretti ASL + comuni afferenti)
  data/territorio/lista_presidi/Comuni_{Lecce,Brindisi,Taranto}.json  (anagrafica comuni)

Output:
  data/territorio/lista_presidi/Distretti_Salento.json
    una riga per distretto: id_distretto, provincia (sigla), comuni (lista nomi),
    n_residenti_comune (popolazione per comune) e n_residenti_distretto (totale)

A video: il report dei comuni di ciascuna provincia rimasti fuori dalla
suddivisione in distretti, e degli eventuali comuni citati nei distretti ma
assenti dall'anagrafica provinciale.

Fonte: dataset regionale "Presidi/Distretti ASL Puglia" (vedi data/dataset/Lista_dataset.md, sezione Territorio).
"""

import json
import sys
import unicodedata
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
DIR_DATI = RADICE / "data" / "territorio" / "lista_presidi"

FILE_PRESIDI = DIR_DATI / "Presidi_Puglia.json"
FILE_OUTPUT = DIR_DATI / "Distretti_Salento.json"

# province del Salento: sigla -> file anagrafica comuni
PROVINCE_SALENTO = {
    "LE": DIR_DATI / "Comuni_Lecce.json",
    "BR": DIR_DATI / "Comuni_Brindisi.json",
    "TA": DIR_DATI / "Comuni_Taranto.json",
}


def chiave(nome):
    """Chiave di confronto fra nomi di comune scritti in modo diverso
    ("Nardò" / "NARDO'", "Patù" / "PATU'"): maiuscolo, senza accenti,
    senza apostrofi/punteggiatura, spazi normalizzati."""
    n = unicodedata.normalize("NFD", nome)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")  # via i segni diacritici
    n = n.upper()
    n = "".join(c if c.isalnum() or c.isspace() else " " for c in n)
    return " ".join(n.split())


def carica_anagrafiche():
    """Restituisce {sigla: {chiave: {"nome": ..., "residenti": ...}}} dalle liste
    comunali, piu' {sigla: residenti_provincia} per il controllo dei totali."""
    anagrafiche = {}
    totali_provincia = {}
    for sigla, percorso in PROVINCE_SALENTO.items():
        with open(percorso, encoding="utf-8") as f:
            dati = json.load(f)
        anagrafiche[sigla] = {
            chiave(c["comune"]): {"nome": c["comune"], "residenti": c["residenti"]}
            for c in dati["comuni"]
        }
        totali_provincia[sigla] = dati["totale"]["residenti"]
    return anagrafiche, totali_provincia


def carica_distretti():
    """Legge Presidi_Puglia.json (formato CKAN: fields + records) e tiene
    solo i distretti delle tre province del Salento."""
    with open(FILE_PRESIDI, encoding="utf-8") as f:
        dati = json.load(f)

    colonne = [campo["id"] for campo in dati["fields"]]
    distretti = []
    for record in dati["records"]:
        riga = dict(zip(colonne, record))
        sigla = riga["SIGLA_PROVINCIA_SEDE"]
        if sigla not in PROVINCE_SALENTO:
            continue
        distretti.append(
            {
                "id_distretto": "{}-{}".format(sigla, riga["COD_DISTRETTO_ASL"].zfill(2)),
                "provincia": sigla,
                "cod_distretto_asl": riga["COD_DISTRETTO_ASL"],
                "cod_nazionale_asl": riga["COD_NAZIONALE_ASL"],
                "denominazione": riga["DENOMINAZIONE"],
                "comune_sede": riga["COMUNE_SEDE"],
                "comuni_grezzi": [c.strip() for c in riga["COMUNI"].split("|") if c.strip()],
            }
        )
    distretti.sort(key=lambda d: (d["provincia"], int(d["cod_distretto_asl"])))
    return distretti


def main():
    anagrafiche, totali_provincia = carica_anagrafiche()
    distretti = carica_distretti()

    assegnati = {sigla: {} for sigla in PROVINCE_SALENTO}  # chiave -> id_distretto
    non_in_anagrafica = []  # comuni citati nei distretti ma assenti dalla lista provinciale
    duplicati = []          # comuni assegnati a piu' di un distretto

    righe = []
    for distretto in distretti:
        sigla = distretto["provincia"]
        voci = []  # (nome ufficiale, residenti)
        for grezzo in distretto["comuni_grezzi"]:
            k = chiave(grezzo)
            scheda = anagrafiche[sigla].get(k)
            if scheda is None:
                non_in_anagrafica.append((distretto["id_distretto"], grezzo))
                # si tiene comunque, con il nome del dataset ASL e popolazione ignota
                voci.append((grezzo.title(), None))
                continue
            if k in assegnati[sigla]:
                duplicati.append((grezzo, assegnati[sigla][k], distretto["id_distretto"]))
            assegnati[sigla][k] = distretto["id_distretto"]
            voci.append((scheda["nome"], scheda["residenti"]))

        voci.sort(key=lambda v: v[0])
        noti = [r for _, r in voci if r is not None]

        righe.append(
            {
                "id_distretto": distretto["id_distretto"],
                "provincia": sigla,
                "denominazione": distretto["denominazione"],
                "comune_sede": distretto["comune_sede"].title(),
                "n_comuni": len(voci),
                "comuni": [nome for nome, _ in voci],
                "n_residenti_comune": [
                    {"comune": nome, "residenti": res} for nome, res in voci
                ],
                "n_residenti_distretto": sum(noti),
                # popolazione incompleta se qualche comune non e' in anagrafica
                "residenti_completi": len(noti) == len(voci),
            }
        )

    # comuni dell'anagrafica non coperti da alcun distretto
    scoperti = {
        sigla: sorted(nome for k, nome in anagrafiche[sigla].items() if k not in assegnati[sigla])
        for sigla in PROVINCE_SALENTO
    }

    residenti_per_provincia = {
        sigla: sum(r["n_residenti_distretto"] for r in righe if r["provincia"] == sigla)
        for sigla in PROVINCE_SALENTO
    }

    uscita = {
        "descrizione": "Distretti socio-sanitari delle province di Lecce, Brindisi e Taranto (Salento) con i comuni afferenti",
        "fonte": "Presidi_Puglia.json (distretti ASL Puglia) incrociato con le anagrafiche comunali provinciali",
        "province": list(PROVINCE_SALENTO),
        "n_distretti": len(righe),
        "n_residenti_totale": sum(residenti_per_provincia.values()),
        "n_residenti_provincia": residenti_per_provincia,
        "distretti": righe,
        "comuni_non_assegnati": {
            sigla: {"n": len(scoperti[sigla]), "comuni": scoperti[sigla]} for sigla in PROVINCE_SALENTO
        },
    }

    with open(FILE_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(uscita, f, ensure_ascii=False, indent=2)

    # ---- report a video ----
    print("Scritto: {}".format(FILE_OUTPUT))
    print("Distretti: {}".format(len(righe)))
    for sigla in PROVINCE_SALENTO:
        n_d = sum(1 for r in righe if r["provincia"] == sigla)
        tot = len(anagrafiche[sigla])
        print("  {}: {} distretti, {}/{} comuni assegnati, {} residenti (anagrafica: {})".format(
            sigla, n_d, tot - len(scoperti[sigla]), tot,
            residenti_per_provincia[sigla], totali_provincia[sigla]))
        if residenti_per_provincia[sigla] != totali_provincia[sigla]:
            print("    ATTENZIONE: somma dei distretti diversa dal totale provinciale")

    print("\n--- Comuni rimasti fuori dalla suddivisione in distretti ---")
    for sigla in PROVINCE_SALENTO:
        elenco = scoperti[sigla]
        print("\n[{}] {} comuni fuori".format(sigla, len(elenco)))
        for nome in elenco:
            print("   - {}".format(nome))

    if non_in_anagrafica:
        print("\n--- Comuni citati nei distretti ma assenti dall'anagrafica provinciale ---")
        for id_distretto, nome in non_in_anagrafica:
            print("   - {} (distretto {})".format(nome, id_distretto))

    if duplicati:
        print("\n--- Comuni assegnati a piu' distretti ---")
        for nome, primo, secondo in duplicati:
            print("   - {}: {} e {}".format(nome, primo, secondo))

    return 0


if __name__ == "__main__":
    sys.exit(main())
