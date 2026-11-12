#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fonte OpenAQ per il dataset aria (client: api/aria/openaq.py, richiede
OPENAQ_API_KEY — es. `uv run --env-file .env ...`).

Stazioni. OpenAQ non dà il comune (`locality` è spesso una via), quindi ogni
location viene ricondotta a una stazione ARPA (anagrafica di tutta la Puglia)
per coordinate, con le regole di api/aria/fonti/abbinamento.py (entro 250 m,
o 1 km se il comune compare nel nome/locality; altrimenti "OpenAQ-<id>").
Le location HabitatMap (sensori citizen-science, nessuna licenza dichiarata)
sono incluse come le altre (decisione di Matteo del 01/10/2026), ma segnalate
in `note["stazioni_senza_licenza"]` e nel report (v. `openaq/OpenAQ.md`).

Valori (decisione del 29/09/2026, uguale per EEA): un solo valore al giorno per
inquinante, la media pesata sul tempo di tutte le misure valide del giorno
(/measurements), senza soglia minima di ore; la nota riporta la completezza
("media pesata sul tempo su n/24 ore"). CO convertito da µg/m³ a mg/m³ come ARPA.

Giorni in UTC+1 fisso, come ARPA ed EEA. L'aggregato /days di OpenAQ usa l'ora
locale (UTC+2 d'estate) e spostava l'ultima ora di ogni giorno al giorno dopo:
lo ha mostrato il confronto con EEA del 28/09/2026 (v. data/dataset/aria/openaq/OpenAQ.md).
Per questo i giorni si ricavano dalle misure orarie e /days serve solo a
controllare in fretta se il sensore ha dati nel periodo.
"""

import time
from datetime import date, timedelta

import pandas as pd

from api.aria.arpa_puglia import STATO_VALORE, classifica_valore
from api.aria.fonti.abbinamento import abbina_ad_arpa, anagrafica_arpa, comuni_salento
from api.aria.fonti.base import FonteAria, RisultatoFonte, consolida_misure, df_capacita, df_stazioni, medie_giornaliere
from api.aria.openaq import OpenAQError, get_giornaliero_sensore, get_orario_sensore, get_stazioni_salento

# nome parametro OpenAQ -> (sigla ARPA, unità OpenAQ attesa, unità ARPA, fattore)
PARAMETRI = {
    "pm10": ("PM10", "µg/m³", "µg/m³", 1.0),
    "pm25": ("PM2.5", "µg/m³", "µg/m³", 1.0),
    "no2": ("NO2", "µg/m³", "µg/m³", 1.0),
    "o3": ("O3", "µg/m³", "µg/m³", 1.0),
    "so2": ("SO2", "µg/m³", "µg/m³", 1.0),
    "co": ("CO", "µg/m³", "mg/m³", 0.001),
}
STATISTICA = "media pesata sul tempo delle misure del giorno"
UTC_PIU_1 = pd.Timedelta(hours=1)  # ora solare, come ARPA ed EEA
PAUSA = 1.1  # s tra chiamate: free tier 60 richieste/minuto
GIORNI_PER_BLOCCO = 31  # dati orari chiesti a blocchi di un mese al massimo
PROVIDER_SENZA_LICENZA = {"HabitatMap"}  # incluse comunque, solo segnalate (v. docs/fonti/OpenAQ.md)
# Stazioni dentro il riquadro di ricerca ma fuori dal Salento: stessa decisione presa per
# l'EEA il 01/10/2026 (api/aria/fonti/eea.py, CODICI_ESCLUSI), applicata anche qui perché
# OpenAQ ridistribuisce le stesse stazioni EEA. Si esclude per nome e non per id, perché
# OpenAQ cambia gli id (split del 01/06/2026: 8378 → 6387781 e simili).
NOMI_ESCLUSI = {"monopoli - aldo moro": "Monopoli - Aldo Moro (provincia di Bari, fuori Salento)"}


class FonteOpenAQ(FonteAria):
    nome = "OpenAQ"
    copertura_da = date(2020, 5, 6)  # prime misure verificate il 27/09/2026

    def raccogli(self, data_inizio, data_fine):
        errori, falliti = [], []
        note = {"abbinamenti": [], "stazioni_senza_licenza": {}, "sensori_scartati": [], "statistiche": {},
                "stazioni_escluse": {}}

        try:
            locations = self._chiama(get_stazioni_salento)
        except OpenAQError as exc:
            errori.append({"fonte": self.nome, "chiamata": "/locations", "tipo": "errore_api", "errore": str(exc)})
            falliti.append({"da": data_inizio, "a": data_fine, "stazione": None, "inquinante": None,
                            "messaggio": f"/locations: {exc}"})
            return RisultatoFonte(df_stazioni([]), df_capacita([]), consolida_misure([]),
                                  periodi_falliti=falliti, errori=errori, note=note)

        anagrafica, comuni = anagrafica_arpa(), comuni_salento()

        stazioni, capacita, misure, unita = [], set(), [], {}
        for loc in locations:
            motivo = NOMI_ESCLUSI.get((loc.get("name") or "").strip().lower())
            if motivo:
                note["stazioni_escluse"][str(loc["id"])] = motivo
                continue
            provider = (loc.get("provider") or {}).get("name")
            if provider in PROVIDER_SENZA_LICENZA:
                note["stazioni_senza_licenza"][str(loc["id"])] = f"{loc.get('name')} (provider {provider}, citizen-science, nessuna licenza dichiarata)"
            attiva_da = ((loc.get("datetimeFirst") or {}).get("local") or "")[:10] or None
            attiva_a = ((loc.get("datetimeLast") or {}).get("local") or "")[:10] or None
            if (attiva_a and attiva_a < data_inizio.isoformat()) or (attiva_da and attiva_da > data_fine.isoformat()):
                continue  # non attiva nel periodo: non copre, NO_DATA lo decide il generatore

            riga = abbina_ad_arpa(self.nome, loc["id"], loc.get("name"),
                                  f"{loc.get('name') or ''} {loc.get('locality') or ''}",
                                  loc["coordinates"]["latitude"], loc["coordinates"]["longitude"], anagrafica, comuni)
            riga.update(attiva_da=attiva_da, attiva_a=attiva_a)
            stazioni.append(riga)
            note["abbinamenti"].append({
                "id_fonte": str(loc["id"]), "nome_fonte": loc.get("name"),
                "stazione": riga["stazione"], "id_distretto": riga["id_distretto"], "abbinamento": riga["abbinamento"],
            })

            for sensore in loc.get("sensors", []):
                param = sensore["parameter"]
                nome_param, unita_param = param["name"], param.get("units")
                if nome_param in PARAMETRI:
                    sigla, unita_attesa, unita_arpa, fattore = PARAMETRI[nome_param]
                    if unita_param != unita_attesa:
                        note["sensori_scartati"].append(f"{loc.get('name')} {nome_param}: unità {unita_param} non convertibile")
                        continue
                else:  # inquinante che ARPA non misura: tenuto con la sua unità
                    sigla, unita_arpa, fattore = nome_param.upper(), unita_param, 1.0
                note["statistiche"][sigla] = STATISTICA
                try:
                    nuove = self._giornalieri(sensore["id"], data_inizio, data_fine, fattore)
                except OpenAQError as exc:
                    chiamata = f"/sensors/{sensore['id']} ({loc.get('name')}, {nome_param})"
                    errori.append({"fonte": self.nome, "chiamata": chiamata, "tipo": "errore_api", "errore": str(exc)})
                    falliti.append({"da": data_inizio, "a": data_fine, "stazione": riga["stazione"],
                                    "inquinante": sigla, "messaggio": f"{chiamata}: {exc}"})
                    capacita.add((riga["stazione"], sigla))  # non sappiamo se misurava: le celle saranno NULL
                    unita.setdefault(sigla, unita_arpa)
                    continue
                # L'elenco delle location non dà le date dei singoli sensori (es. il PM10 di
                # Arnesano esiste solo dal 02/2026): un sensore conta come "misurato" solo se ha
                # restituito almeno un dato nel periodo, come per ARPA. Altrimenti NO_DATA.
                if nuove:
                    capacita.add((riga["stazione"], sigla))
                    unita.setdefault(sigla, unita_arpa)
                    misure.extend(dict(m, stazione=riga["stazione"], inquinante=sigla) for m in nuove)

        return RisultatoFonte(
            stazioni=df_stazioni(stazioni),
            capacita=df_capacita(capacita),
            misure=consolida_misure(misure),
            unita=unita,
            periodi_falliti=falliti,
            errori=errori,
            note=note,
        )

    # --- chiamate ------------------------------------------------------------

    def _chiama(self, funzione, *args):
        """Una chiamata al client con pausa per il rate limit e un solo nuovo
        tentativo: dopo un minuto se il limite è stato superato, dopo pochi
        secondi se OpenAQ risponde con un errore temporaneo (408, 5xx)."""
        time.sleep(PAUSA)
        try:
            return funzione(*args)
        except OpenAQError as exc:
            messaggio = str(exc)
            if "Rate limit" in messaggio:
                time.sleep(61)
            elif any(f"risposto {codice}" in messaggio for codice in ("408", "500", "502", "503", "504")):
                time.sleep(5)
            else:
                raise
            return funzione(*args)

    def _giornalieri(self, sensore_id, data_inizio, data_fine, fattore):
        # Verifica veloce con l'aggregato giornaliero: su un periodo senza dati l'endpoint
        # orario /hours andava in timeout invece di rispondere vuoto (osservato il 27/09/2026 sul CO di giugno 2024,
        # assente in OpenAQ per tutte le stazioni). Nessun giorno → sensore non attivo → NO_DATA.
        # Il giorno prima e dopo perché /days ragiona in ora locale, noi in UTC+1.
        if not self._chiama(get_giornaliero_sensore, sensore_id, (data_inizio - timedelta(days=1)).isoformat(),
                            (data_fine + timedelta(days=1)).isoformat()):
            return []
        # dal giorno prima (UTC): il giorno in UTC+1 inizia alle 23:00 UTC del giorno precedente.
        # A blocchi di GIORNI_PER_BLOCCO giorni (paginazione più prevedibile).
        orari, inizio = [], data_inizio - timedelta(days=1)
        while inizio <= data_fine:
            fine = min(inizio + timedelta(days=GIORNI_PER_BLOCCO - 1), data_fine)
            orari.extend(self._chiama(get_orario_sensore, sensore_id, inizio.isoformat(), fine.isoformat()))
            inizio = fine + timedelta(days=1)
        righe = []
        for rec in orari:
            periodo = rec.get("period") or {}
            try:
                da = pd.Timestamp(periodo["datetimeFrom"]["utc"]).tz_convert(None) + UTC_PIU_1
                a = pd.Timestamp(periodo["datetimeTo"]["utc"]).tz_convert(None) + UTC_PIU_1
            except (KeyError, TypeError, ValueError):
                continue  # misura senza periodo leggibile: non assegnabile a un giorno
            valore, stato, _ = classifica_valore(rec.get("value"))
            righe.append({"inizio": da, "fine": a, "valore": valore * fattore if stato == STATO_VALORE else None,
                          "valida": stato == STATO_VALORE})
        if not righe:
            return []
        misure = pd.DataFrame(righe).sort_values("valida", ascending=False).drop_duplicates(["inizio", "fine"])
        return medie_giornaliere(misure, data_inizio, data_fine)
