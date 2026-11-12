#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Soglie di caldo (dato autorevole nel codice, come RIFERIMENTI_NORMATIVI per l'aria): scelte il 14/10/2026
fra le definizioni più usate in climatologia e nella sanità pubblica, **soglie fisse** e uguali per tutti i
comuni. Motivazioni, limiti e citazioni: data/dataset/calore/Soglie_Caldo.md.

Ogni soglia produce un indicatore giornaliero 0/1 (1 = soglia raggiunta) che eredita lo stato della
temperatura da cui deriva: così si somma per distretto e per mese come ogni conteggio (api/comune/aggregazione.py).
"""

# nome indicatore -> (statistica di base, soglia in °C, descrizione)
SOGLIE = {
    "giorno_caldo": ("massima", 30.0, "giornata calda (summer/hot day): T max ≥ 30 °C"),
    "giorno_molto_caldo": ("massima", 35.0, "giornata di caldo estremo (very hot day): T max ≥ 35 °C"),
    "notte_tropicale": ("minima", 20.0, "notte tropicale: T min ≥ 20 °C"),
    "notte_equatoriale": ("minima", 25.0, "notte equatoriale: T min ≥ 25 °C"),
}

UNITA_TEMPERATURA = "°C"
UNITA_SOGLIA = "giorno (0/1)"
