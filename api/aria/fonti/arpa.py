#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fonte ARPA Puglia per il dataset aria (client: api/aria/arpa_puglia.py, che
fa già il controllo a monte di payload e valori).

- Stazioni: anagrafica ARPA delle tre province, esclusa la rete privata ADI
  (ex-ILVA, decisione del 27/09/2026). Le 6 private VERSALIS del petrolchimico
  di Brindisi (id_station 114-119), non restituite da centraline.jsp, sono
  state aggiunte a mano all'anagrafica locale il 01/10/2026 (decisione di
  Matteo: trattarle come tutte le altre stazioni, non escluderle come ADI).
  Una stazione ancora assente dall'anagrafica (non vista nei dati finora)
  verrebbe comunque ricondotta al distretto tramite il comune.
- Inquinanti misurati da una stazione: quelli per cui ARPA restituisce righe
  (anche null) nei mesi scaricati — ARPA elenca ogni inquinante configurato
  sulla stazione anche quando il valore manca.
- Statistica giornaliera e unità: quelle di ARPA, che pubblica un solo valore
  al giorno già aggregato (non ci sono dati orari): si tiene così com'è
  (decisione del 29/09/2026). Per NO2, O3, SO2 e CO è un massimo, non una media
  come per OpenAQ ed EEA (v. STATISTICHE).
"""

import calendar
from datetime import date

from api.aria.arpa_puglia import (
    ArpaPugliaError,
    _mesi_nel_periodo,
    get_inquinanti,
    get_qualita_aria_mensile,
)
from api.aria.fonti.base import FonteAria, RisultatoFonte, consolida_misure, df_capacita, df_stazioni
from api.comune.distretti_salento import carica_stazioni_salento, distretto_del_comune


# statistica del valore giornaliero ARPA (v. data/dataset/aria/arpa_puglia/Parametri_Qualita_Aria.md;
# per il PM2.5 la tabella riporta il limite annuo, il valore giornaliero è la media del giorno)
STATISTICHE = {
    "PM10": "media giornaliera",
    "PM2.5": "media giornaliera",
    "NO2": "massimo orario del giorno",
    "O3": "massimo orario del giorno",
    "SO2": "massimo orario del giorno",
    "CO": "massimo giornaliero della media mobile su 8 ore",
}


class FonteARPA(FonteAria):
    nome = "ARPA"
    copertura_da = date(2012, 1, 1)  # primi valori reali verificati il 27/09/2026

    def raccogli(self, data_inizio, data_fine):
        errori, falliti = [], []
        note = {"stazioni_non_in_anagrafica": {}, "stazioni_escluse": {}, "statistiche": dict(STATISTICHE)}

        try:
            unita = {r["sigla"]: r["unita_misura"] for r in get_inquinanti()}
        except ArpaPugliaError as exc:
            errori.append({"fonte": self.nome, "chiamata": "inquinanti.jsp", "tipo": "errore_api", "errore": str(exc)})
            unita = {}

        stazioni = {}
        for s in carica_stazioni_salento():
            if s["rete"] == "ADI":
                note["stazioni_escluse"][s["id_station"]] = f"{s['denominazione']} (rete privata ADI ex-ILVA)"
                continue
            stazioni[s["id_station"]] = self._riga_stazione(s, "anagrafica ARPA, distretto dal comune")

        misure, capacita = [], set()
        inizio = max(data_inizio, self.copertura_da)
        mesi = _mesi_nel_periodo(inizio, data_fine) if inizio <= data_fine else []
        for anno, mese in mesi:
            chiamata = f"dati.jsp {anno}-{mese:02d}"
            try:
                righe = get_qualita_aria_mensile(anno, mese)
            except ArpaPugliaError as exc:
                ultimo = date(anno, mese, calendar.monthrange(anno, mese)[1])
                falliti.append({
                    "da": max(date(anno, mese, 1), data_inizio), "a": min(ultimo, data_fine),
                    "stazione": None, "inquinante": None, "messaggio": f"{chiamata}: {exc}",
                })
                errori.append({"fonte": self.nome, "chiamata": chiamata, "tipo": "errore_api", "errore": str(exc)})
                continue
            for anomalia in righe.anomalie:
                errori.append({"fonte": self.nome, "chiamata": chiamata, "tipo": "anomalia_payload", "errore": anomalia})

            for r in righe:
                if r.get("rete") == "ADI":
                    continue
                id_station = r["id_station"]
                if id_station not in stazioni:
                    stazioni[id_station] = self._riga_stazione(
                        {
                            "id_station": id_station, "denominazione": r.get("denominazione"),
                            "comune": r.get("comune"), "provincia": r.get("provincia"),
                            "lat": r.get("Latitude"), "lon": r.get("Longitude"),
                            "id_distretto": distretto_del_comune(r.get("comune")),
                        },
                        "non in anagrafica ARPA, distretto dal comune",
                    )
                    note["stazioni_non_in_anagrafica"][id_station] = r.get("denominazione")
                inquinante = r["inquinante_misurato"]
                unita.setdefault(inquinante, r.get("unita_misura"))
                capacita.add((id_station, inquinante))
                giorno = r["data_di_misurazione"]
                if data_inizio.isoformat() <= giorno <= data_fine.isoformat():
                    misure.append({
                        "stazione": id_station, "giorno": giorno, "inquinante": inquinante,
                        "valore": r["valore"], "stato": r["stato"], "nota": r["nota"],
                    })

        return RisultatoFonte(
            stazioni=df_stazioni(list(stazioni.values())),
            capacita=df_capacita(capacita),
            misure=consolida_misure(misure),
            unita=unita,
            periodi_falliti=falliti,
            errori=errori,
            note=note,
        )

    def _riga_stazione(self, s, abbinamento):
        return {
            "stazione": s["id_station"], "fonte": self.nome, "id_fonte": s["id_station"],
            "denominazione": s["denominazione"], "comune": s["comune"], "provincia": s["provincia"],
            "lat": _float(s.get("lat")), "lon": _float(s.get("lon")),
            "id_distretto": s.get("id_distretto"), "attiva_da": None, "attiva_a": None,
            "abbinamento": abbinamento,
        }


def _float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
