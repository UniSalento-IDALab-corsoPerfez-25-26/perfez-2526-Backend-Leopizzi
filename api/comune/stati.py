#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
I tre stati di una cella dei dataset (docs/Regole_dei_dati.md), condivisi da aria,
salute e calore: mai una cella vuota, mai un valore inventato.

Stanno qui e non in una delle fonti perché li usano tutti i domini e il modulo
di aggregazione (api/comune/aggregazione.py). `api.aria.arpa_puglia` li
ri-esporta per non rompere gli import già scritti.
"""

STATO_VALORE = "VALORE"
STATO_NULL = "NULL"
STATO_NO_DATA = "NO_DATA"

LEGENDA_STATI = {
    STATO_VALORE: "valore numerico valido restituito dalla fonte",
    STATO_NULL: "la fonte copre la cella ma il valore non è usabile (null, non valido, discordante, "
                "nessuna misura valida nel periodo o errore API)",
    STATO_NO_DATA: "la fonte non copre la cella (nessuna stazione, stazione non coperta o non attiva, "
                   "inquinante/indicatore non misurato, data fuori copertura)",
}
