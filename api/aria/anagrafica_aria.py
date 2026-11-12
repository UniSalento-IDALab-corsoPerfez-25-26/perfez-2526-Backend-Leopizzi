#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anagrafiche relazionali dell'aria: stazioni di tutte le fonti collegate al
comune, e inquinanti con le stazioni che li misurano (v.
data/dataset/Anagrafiche_relazionali.md e api/comune/anagrafiche.py).

File gestiti (JSON con chiavi primarie/esterne, ricaricabili come tabelle SQL):
  data/dataset/aria/anagrafica/stazioni.json     fonti, stazioni, stazioni_fonti
  data/dataset/aria/anagrafica/inquinanti.json   inquinanti, stazioni_inquinanti

Sono file *cumulativi*: ogni aggiornamento aggiunge o aggiorna righe e non ne
toglie mai (una stazione o un inquinante non visto in un periodo non sparisce).

Due livelli di stazione:
  - `stazioni`         una riga per stazione fisica, con la chiave unificata già usata
                       dal dataset aria (id ARPA, oppure "<fonte>-<id>", es. "OpenAQ-<id>") e il comune;
  - `stazioni_fonti`   una riga per record della stazione in una fonte (es. "ARPA:24",
                       "OpenAQ:8378"); una stazione può averne più d'uno, anche della
                       stessa fonte (OpenAQ ha cambiato id il 01/06/2026).
La media per comune (dashboard) si fa sulle *stazioni* e non sui record, così una
stazione con due id non pesa il doppio.

Comune di una stazione (in ordine):
  0. un comune forzato a mano (COMUNE_FORZATO), per i pochi casi verificati
     sulla carta in cui il comune dichiarato dalla fonte è sbagliato;
  1. il comune dichiarato dalla fonte di riferimento, se è tra i 145 del Salento;
  2. se la fonte ne dichiara uno fuori dal Salento (es. Monopoli): nessun comune;
  3. se la fonte non ne dichiara: il comune il cui confine contiene le coordinate,
     oppure il più vicino entro api.comune.confini_comuni.SOGLIA_COMUNE_VICINO_KM.
Se le coordinate cadono fuori dal confine del comune dichiarato, resta il comune
dichiarato e la discrepanza va in `nota`.
"""

from datetime import date

from api.comune.anagrafiche import FILE_ANAGRAFICHE, carica_anagrafiche, leggi_anagrafica, scrivi_anagrafica, verifica_integrita
from api.comune.confini_comuni import confine_da_coordinate
from api.comune.distretti_salento import chiave

FILE_STAZIONI = FILE_ANAGRAFICHE["stazioni"]
FILE_INQUINANTI = FILE_ANAGRAFICHE["inquinanti"]
RIFERIMENTO_DASHBOARD = ("CO", "NO2", "O3", "PM2.5", "SO2")  # docs/Regole_dei_dati.md

# Valori limite normativi: dato **autorevole di progetto**, non derivato da ARPA (v. report del 11/10/2026
# data/dataset/aria/Valori_Riferimento_Normativi.md §3). Si riapplicano a ogni salvataggio dell'anagrafica
# (_applica_riferimenti), così non vengono sovrascritti né dai valori ARPA né da una rigenerazione dello schema.
# `primario` = terna legacy (periodo_misurazione, valore_limite, soglia_allarme) = riferimento D.Lgs. 155/2010 in vigore.
# Statistiche di `riferimenti`: media_annua | media_24h | massimo_orario | massimo_8h | peak_season | media_10min.
def _rif(statistica, valore, unita, superamenti_ammessi=None, nota=None):
    return {"statistica": statistica, "valore": valore, "unita": unita,
            "superamenti_ammessi": superamenti_ammessi, "nota": nota}


RIFERIMENTI_NORMATIVI = {
    "CO": {
        "primario": ("Max media mobile 8h giornaliera", 10.0, None),
        "riferimenti": {
            "dlgs_155_2010": [_rif("massimo_8h", 10.0, "mg/m³")],
            "oms_2021": [_rif("massimo_8h", 10.0, "mg/m³", nota="non rivalutata dal 2005"),
                         _rif("media_24h", 4.0, "mg/m³")],
            "ue_2024_2881": [_rif("massimo_8h", 10.0, "mg/m³"),
                             _rif("media_24h", 4.0, "mg/m³", 18, "dal 2030")],
        },
        "soglie_acute": None,
    },
    "NO2": {
        "primario": ("Media annua", 40.0, 400.0),
        "riferimenti": {
            "dlgs_155_2010": [_rif("media_annua", 40.0, "µg/m³"),
                              _rif("massimo_orario", 200.0, "µg/m³", 18)],
            "oms_2021": [_rif("media_annua", 10.0, "µg/m³"), _rif("media_24h", 25.0, "µg/m³"),
                         _rif("massimo_orario", 200.0, "µg/m³", nota="non rivalutata dal 2005")],
            "ue_2024_2881": [_rif("media_annua", 20.0, "µg/m³", nota="dal 2030"),
                             _rif("media_24h", 50.0, "µg/m³", 18, "dal 2030"),
                             _rif("massimo_orario", 200.0, "µg/m³", 3, "dal 2030")],
        },
        "soglie_acute": {"informazione": None,
                         "allarme": {"valore": 400.0, "unita": "µg/m³", "statistica": "massimo_orario",
                                     "nota": "superata per 3 ore consecutive"}},
    },
    "O3": {
        "primario": ("Max media mobile 8h giornaliera (valore obiettivo)", 120.0, 240.0),
        "riferimenti": {
            "dlgs_155_2010": [_rif("massimo_8h", 120.0, "µg/m³", 25, "valore obiettivo, media su 3 anni")],
            "oms_2021": [_rif("massimo_8h", 100.0, "µg/m³"),
                         _rif("peak_season", 60.0, "µg/m³", nota="media del max 8h sui 6 mesi più caldi")],
            "ue_2024_2881": [_rif("massimo_8h", 120.0, "µg/m³", 18, "valore obiettivo, media su 3 anni, dal 2030")],
        },
        "soglie_acute": {"informazione": {"valore": 180.0, "unita": "µg/m³", "statistica": "massimo_orario", "nota": "media oraria"},
                         "allarme": {"valore": 240.0, "unita": "µg/m³", "statistica": "massimo_orario", "nota": "media oraria"}},
    },
    "PM2.5": {
        "primario": ("Media annua", 25.0, None),
        "riferimenti": {
            "dlgs_155_2010": [_rif("media_annua", 25.0, "µg/m³")],
            "oms_2021": [_rif("media_annua", 5.0, "µg/m³"), _rif("media_24h", 15.0, "µg/m³")],
            "ue_2024_2881": [_rif("media_annua", 10.0, "µg/m³", nota="dal 2030"),
                             _rif("media_24h", 25.0, "µg/m³", 18, "dal 2030")],
        },
        "soglie_acute": None,
    },
    "SO2": {
        "primario": ("Media giornaliera", 125.0, 500.0),
        "riferimenti": {
            "dlgs_155_2010": [_rif("media_24h", 125.0, "µg/m³", 3),
                              _rif("massimo_orario", 350.0, "µg/m³", 24)],
            "oms_2021": [_rif("media_24h", 40.0, "µg/m³"),
                         _rif("media_10min", 500.0, "µg/m³", nota="non rivalutata dal 2005, non confrontabile col dato giornaliero")],
            "ue_2024_2881": [_rif("media_annua", 20.0, "µg/m³", nota="dal 2030"),
                             _rif("media_24h", 50.0, "µg/m³", 18, "dal 2030"),
                             _rif("massimo_orario", 350.0, "µg/m³", 3, "dal 2030")],
        },
        "soglie_acute": {"informazione": None,
                         "allarme": {"valore": 500.0, "unita": "µg/m³", "statistica": "massimo_orario",
                                     "nota": "superata per 3 ore consecutive"}},
    },
    "PM10": {
        "primario": ("Media giornaliera", 50.0, None),
        "riferimenti": {
            "dlgs_155_2010": [_rif("media_annua", 40.0, "µg/m³"),
                              _rif("media_24h", 50.0, "µg/m³", 35)],
            "oms_2021": [_rif("media_annua", 15.0, "µg/m³"), _rif("media_24h", 45.0, "µg/m³")],
            "ue_2024_2881": [_rif("media_annua", 20.0, "µg/m³", nota="dal 2030"),
                             _rif("media_24h", 45.0, "µg/m³", 18, "dal 2030")],
        },
        "soglie_acute": None,
    },
    "C6H6": {
        "primario": ("Media annua", 5.0, None),
        "riferimenti": {
            "dlgs_155_2010": [_rif("media_annua", 5.0, "µg/m³")],
            "oms_2021": [_rif("media_annua", None, "µg/m³", nota="cancerogeno senza soglia: solo stima del rischio unitario, nessun valore limite")],
            "ue_2024_2881": [_rif("media_annua", 3.4, "µg/m³", nota="dal 2030")],
        },
        "soglie_acute": None,
    },
}

# Soglie di plausibilità per inquinante: non limiti di legge, ma un tetto oltre il quale un
# valore giornaliero è fisicamente implausibile per una stazione del Salento ed è più
# probabile un errore del sensore che un episodio reale. Usate SOLO per escludere una cella
# dalla **media per comune** (api/comune/aggregazione.py, media_per_comune): il valore
# originale resta intatto nel dataset per-fonte ("niente filtri silenziosi", docs/Regole_dei_dati.md).
# Caso che ha motivato la soglia (chiuso il 14/10/2026): OpenAQ a Torchiarolo
# (stazione 93, giugno 2024) dà PM2.5 = 443,84 µg/m³ il 28/06 contro 8,70 di CAMS e 8,45 di
# EEA, e SO2 = 65,6 contro 2,07 il 04/06 — EEA e CAMS concordano fra loro, l'anomalia è solo
# di OpenAQ. Dove esiste, si usa la **soglia di allarme** del D.Lgs. 155/2010 (RIFERIMENTI_NORMATIVI,
# `soglie_acute.allarme`): è il livello a cui scattano le procedure di allerta pubblica, quindi
# un valore giornaliero sopra è già un'anomalia; dove non è prevista (CO, PM2.5, PM10, C6H6) si
# usa 10 volte il valore limite primario, una soglia larga che lascia passare qualunque episodio
# di inquinamento reale. **Nota onesta**: una soglia assoluta per inquinante non cattura tutto —
# il caso SO2 sopra (65,6 µg/m³) resta sotto qualunque soglia ragionevole, perché è plausibile in
# assoluto e anomalo solo per confronto con le altre fonti (ridondanza, non soglia): resta un
# limite dichiarato, non un errore di questa soglia.
SOGLIE_PLAUSIBILITA = {
    sigla: (r["soglie_acute"]["allarme"]["valore"] if r["soglie_acute"] and r["soglie_acute"].get("allarme")
            else r["primario"][1] * 10)
    for sigla, r in RIFERIMENTI_NORMATIVI.items()
}

METODO_DICHIARATO = "comune_dichiarato_dalla_fonte"
METODO_DENTRO = "dentro_il_confine"
METODO_VICINO = "confine_piu_vicino"
METODO_FORZATO = "forzato_a_mano"

# Comune forzato a mano per id_stazione (chiave unificata del dataset, es. id
# ARPA): casi verificati sulla carta in cui il comune dichiarato dalla fonte
# non è quello giusto. {id_stazione: denominazione del comune corretto}
COMUNE_FORZATO = {
    "95": "Lecce",  # Surbo - Croce (ARPA): coordinate dentro il confine di Lecce, non di Surbo
                     # (dichiarato dalla fonte) — verificato sulla carta, decisione di Matteo del 01/10/2026
}

SCHEMA_STAZIONI = {
    "fonti": {
        "chiave_primaria": ["fonte"],
        "chiavi_esterne": {},
        "colonne": {
            "fonte": "nome della fonte dati (ARPA, OpenAQ, ...)",
            "priorita": "1 = più prioritaria: la sua anagrafica prevale per denominazione, coordinate e comune",
            "copertura_da": "prima data con dati reali (YYYY-MM-DD), null se non nota",
        },
    },
    "stazioni": {
        "chiave_primaria": ["id_stazione"],
        "chiavi_esterne": {"id_comune": "comuni.id_comune", "fonte_riferimento": "fonti.fonte"},
        "colonne": {
            "id_stazione": "chiave unificata del dataset aria: id ARPA, oppure <fonte>-<id> (es. OpenAQ-<id>, EEA-<codice EoI>) se senza stazione ARPA",
            "denominazione": "nome della stazione secondo la fonte di riferimento",
            "id_comune": "comune della stazione; null se fuori dal Salento o non assegnabile (v. nota)",
            "lat": "latitudine",
            "lon": "longitudine",
            "fonte_riferimento": "fonte da cui vengono denominazione, coordinate e comune",
            "metodo_comune": "comune_dichiarato_dalla_fonte | dentro_il_confine | confine_piu_vicino | forzato_a_mano | null",
            "distanza_comune_km": "distanza dal confine del comune (0 se dentro), solo se assegnato per coordinate",
            "nota": "avvertenze sull'assegnazione al comune",
        },
    },
    "stazioni_fonti": {
        "chiave_primaria": ["id_stazione_fonte"],
        "chiavi_esterne": {"id_stazione": "stazioni.id_stazione", "fonte": "fonti.fonte"},
        "colonne": {
            "id_stazione_fonte": "<fonte>:<id nella fonte>, es. ARPA:24",
            "id_stazione": "stazione fisica a cui il record è ricondotto",
            "fonte": "fonte del record",
            "id_nella_fonte": "identificativo della stazione nella fonte",
            "denominazione": "nome nella fonte",
            "lat": "latitudine nella fonte",
            "lon": "longitudine nella fonte",
            "attiva_da": "prima data di attività nella fonte (null = non nota)",
            "attiva_a": "ultima data di attività nella fonte (null = non nota / ancora attiva)",
            "abbinamento": "come il record è stato ricondotto alla stazione e al distretto",
        },
    },
}

SCHEMA_INQUINANTI = {
    "inquinanti": {
        "chiave_primaria": ["id_inquinante"],
        "chiavi_esterne": {},
        "colonne": {
            "id_inquinante": "sigla dell'inquinante (CO, NO2, O3, PM2.5, SO2, ...)",
            "descrizione": "significato: cos'è e da dove deriva (ARPA Puglia); null se non fornito da nessuna fonte",
            "unita_misura": "unità di misura del dataset (quella di ARPA)",
            "periodo_misurazione": "riferimento primario (D.Lgs. 155/2010) per retrocompatibilità: statistica del limite. Per il confronto per statistica usare 'riferimenti'. Da RIFERIMENTI_NORMATIVI, non da ARPA",
            "valore_limite": "riferimento primario (D.Lgs. 155/2010) per retrocompatibilità: valore limite, nell'unità indicata. Da RIFERIMENTI_NORMATIVI",
            "soglia_allarme": "soglia di allarme (media oraria/3h consecutive), nell'unità indicata. Da RIFERIMENTI_NORMATIVI",
            "riferimenti": "tre quadri normativi (dlgs_155_2010, oms_2021, ue_2024_2881) per il confronto per statistica in dashboard (Tappa B, v. data/dataset/aria/Valori_Riferimento_Normativi.md); ogni quadro è una lista di {statistica, valore, unita, superamenti_ammessi, nota}. Dato autorevole di progetto (RIFERIMENTI_NORMATIVI), non derivato da ARPA; null se l'inquinante non ha limiti",
            "soglie_acute": "soglie di informazione/allarme del D.Lgs. 155/2010 (media oraria/3h), {informazione, allarme} ciascuna {valore, unita, statistica, nota}; null se non previste",
            "riferimento_dashboard": "true per i 5 inquinanti di riferimento (docs/Regole_dei_dati.md)",
            "aggiunto_il": "data in cui l'inquinante è stato tracciato",
            "origine": "perché è tracciato",
        },
    },
    "stazioni_inquinanti": {
        "chiave_primaria": ["id_stazione_fonte", "id_inquinante"],
        "chiavi_esterne": {"id_stazione_fonte": "stazioni_fonti.id_stazione_fonte",
                           "id_inquinante": "inquinanti.id_inquinante"},
        "colonne": {
            "id_stazione_fonte": "record della stazione nella fonte",
            "id_inquinante": "inquinante misurato",
            "visto_da": "inizio del primo periodo in cui la fonte ha restituito righe per la coppia",
            "visto_a": "fine dell'ultimo periodo in cui l'ha fatto",
        },
    },
}

DESCRIZIONE_STAZIONI = ("Stazioni di misura dell'aria di tutte le fonti, collegate al comune. File cumulativo aggiornato da "
                        "api/aria/anagrafica_aria.py a ogni generazione del dataset aria.")
DESCRIZIONE_INQUINANTI = ("Inquinanti tracciati (lista di docs/Regole_dei_dati.md) e stazioni che li misurano. File cumulativo aggiornato "
                          "da api/aria/anagrafica_aria.py; le descrizioni vengono da scripts/aria/inquinanti_arpa.py.")


def inquinanti_tracciati():
    """{sigla: riga} degli inquinanti tracciati (tabella `inquinanti`); vuoto se il file non esiste ancora."""
    if not FILE_INQUINANTI.exists():
        return {}
    _, _, tabelle = leggi_anagrafica(FILE_INQUINANTI)
    return {r["id_inquinante"]: r for r in tabelle["inquinanti"]}


def carica_comuni():
    """Righe della tabella `comuni` (territorio.json), per assegnare le stazioni ai comuni."""
    if not FILE_ANAGRAFICHE["territorio"].exists():
        raise FileNotFoundError("manca l'anagrafica del territorio: lanciare scripts/territorio/costruisci_anagrafica_territorio.py")
    _, _, tabelle = leggi_anagrafica(FILE_ANAGRAFICHE["territorio"])
    return tabelle["comuni"]


def _righe(tabelle, nome):
    return tabelle[nome].to_dict("records") if nome in tabelle else []


def _carica():
    """(righe stazioni.json, righe inquinanti.json, comuni) — le righe sono {tabella: [dict]}."""
    schema, tabelle = carica_anagrafiche()
    stazioni = {t: _righe(tabelle, t) for t in SCHEMA_STAZIONI}
    inquinanti = {t: _righe(tabelle, t) for t in SCHEMA_INQUINANTI}
    if "comuni" not in tabelle:
        raise FileNotFoundError("manca l'anagrafica del territorio: lanciare scripts/territorio/costruisci_anagrafica_territorio.py")
    return stazioni, inquinanti, tabelle["comuni"].to_dict("records")


def _salva(stazioni, inquinanti, comuni):
    """Scrive i due file dopo aver verificato chiavi primarie ed esterne; restituisce i problemi trovati
    (i file vengono scritti comunque: non si perde il lavoro della corsa)."""
    import pandas as pd

    tabelle = {t: pd.DataFrame(r, columns=list({**SCHEMA_STAZIONI, **SCHEMA_INQUINANTI}[t]["colonne"]), dtype=object)
               for t, r in {**stazioni, **inquinanti}.items()}
    tabelle["comuni"] = pd.DataFrame(comuni, dtype=object)
    schema = {**SCHEMA_STAZIONI, **SCHEMA_INQUINANTI,
              "comuni": {"chiave_primaria": ["id_comune"], "chiavi_esterne": {}, "colonne": {}}}
    problemi = verifica_integrita(schema, tabelle)
    scrivi_anagrafica(FILE_STAZIONI, DESCRIZIONE_STAZIONI, SCHEMA_STAZIONI, stazioni)
    scrivi_anagrafica(FILE_INQUINANTI, DESCRIZIONE_INQUINANTI, SCHEMA_INQUINANTI, inquinanti)
    return problemi


def _valore(x):
    """None per NaN/None (le righe arrivano da DataFrame), altrimenti il valore."""
    return None if x is None or x != x else x


def _iso(x):
    x = _valore(x)
    return x.isoformat() if hasattr(x, "isoformat") else x


def comune_della_stazione(riga, comuni):
    """(id_comune, metodo, distanza_km, nota) per una riga di stazione (colonne di
    api.aria.fonti.base.COLONNE_STAZIONI). `comuni`: righe della tabella comuni."""
    per_nome = {chiave(c["denominazione"]): c for c in comuni}
    per_confine = {}
    for c in comuni:
        per_confine.setdefault(c["nome_confine"], []).append(c)
    dichiarato = _valore(riga.get("comune"))
    lat, lon = _valore(riga.get("lat")), _valore(riga.get("lon"))
    confine, distanza, dentro = confine_da_coordinate(lat, lon) if lat is not None and lon is not None else (None, None, False)

    forzato = COMUNE_FORZATO.get(str(_valore(riga.get("stazione"))))
    if forzato:
        c = per_nome[chiave(forzato)]
        nota = f"comune forzato a mano ({forzato})" + (f", dichiarato dalla fonte: {dichiarato}" if dichiarato else "")
        return c["id_comune"], METODO_FORZATO, None, nota

    if dichiarato:
        c = per_nome.get(chiave(dichiarato))
        if c is None:
            return None, None, None, f"comune dichiarato dalla fonte ({dichiarato}) fuori dai distretti noti"
        nota = None
        if confine is not None and confine != c["nome_confine"]:
            nota = (f"coordinate {'dentro' if dentro else 'vicino'} al confine di {confine}, "
                    f"diverso dal comune dichiarato ({c['denominazione']})")
        return c["id_comune"], METODO_DICHIARATO, None, nota

    if confine is None:
        motivo = ("senza coordinate" if lat is None or lon is None
                  else f"coordinate a {distanza} km dal confine comunale più vicino: fuori dal Salento o non assegnabile")
        return None, None, None, f"nessun comune dichiarato; {motivo}"
    candidati = per_confine[confine]
    if len(candidati) > 1:
        return None, None, None, (f"il confine {confine} è condiviso da {', '.join(c['denominazione'] for c in candidati)}: "
                                  "assegnare a mano")
    return (candidati[0]["id_comune"], METODO_DENTRO if dentro else METODO_VICINO, distanza,
            None if dentro else f"stazione fuori da ogni confine: comune con il confine più vicino ({distanza} km)")


def aggiorna_anagrafiche_aria(stazioni, capacita, fonti, data_inizio, data_fine, unita=None):
    """Unisce alle anagrafiche stazioni e coppie stazione/inquinante viste in una corsa.

    stazioni:  DataFrame con le colonne di api.aria.fonti.base.COLONNE_STAZIONI, di tutte le
               fonti, comprese le stazioni fuori dai distretti;
    capacita:  DataFrame (stazione, fonte, inquinante): coppie che la fonte ha misurato;
    fonti:     {nome: copertura_da} nell'ordine di priorità (la prima è la più prioritaria);
    data_inizio, data_fine: periodo della corsa (per visto_da/visto_a);
    unita:     {inquinante: unità} per gli inquinanti nuovi.

    Restituisce un riepilogo: righe aggiunte, stazioni senza comune, problemi di integrità."""
    unita = unita or {}
    st, inq, comuni = _carica()
    oggi = date.today().isoformat()
    priorita = {f: i + 1 for i, f in enumerate(fonti)}
    riepilogo = {"stazioni_nuove": 0, "stazioni_fonti_nuove": 0, "inquinanti_nuovi": [], "coppie_nuove": 0,
                 "stazioni_senza_comune": [], "discrepanze": []}

    # --- fonti ------------------------------------------------------------------
    per_fonte = {r["fonte"]: r for r in st["fonti"]}
    for nome, copertura in fonti.items():
        per_fonte[nome] = {"fonte": nome, "priorita": priorita[nome], "copertura_da": _iso(copertura)}
    st["fonti"] = sorted(per_fonte.values(), key=lambda r: (r["priorita"], r["fonte"]))
    priorita_nota = {r["fonte"]: r["priorita"] for r in st["fonti"]}

    # --- stazioni fisiche e record per fonte ------------------------------------
    per_stazione = {r["id_stazione"]: r for r in st["stazioni"]}
    per_record = {r["id_stazione_fonte"]: r for r in st["stazioni_fonti"]}
    righe = sorted(stazioni.to_dict("records"), key=lambda r: (priorita_nota.get(r["fonte"], 99), str(r["id_fonte"])))
    for r in righe:
        id_stazione, fonte = str(r["stazione"]), r["fonte"]
        id_record = f"{fonte}:{r['id_fonte']}"
        if id_record not in per_record:
            riepilogo["stazioni_fonti_nuove"] += 1
        per_record[id_record] = {
            "id_stazione_fonte": id_record, "id_stazione": id_stazione, "fonte": fonte,
            "id_nella_fonte": str(r["id_fonte"]), "denominazione": _valore(r["denominazione"]),
            "lat": _valore(r["lat"]), "lon": _valore(r["lon"]),
            "attiva_da": _iso(r["attiva_da"]), "attiva_a": _iso(r["attiva_a"]),
            "abbinamento": _valore(r["abbinamento"]),
        }
        esistente = per_stazione.get(id_stazione)
        if esistente is not None and priorita_nota.get(esistente["fonte_riferimento"], 99) < priorita_nota.get(fonte, 99):
            continue  # la stazione è già descritta da una fonte più prioritaria
        id_comune, metodo, distanza, nota = comune_della_stazione(r, comuni)
        if esistente is None:
            riepilogo["stazioni_nuove"] += 1
        per_stazione[id_stazione] = {
            "id_stazione": id_stazione, "denominazione": _valore(r["denominazione"]), "id_comune": id_comune,
            "lat": _valore(r["lat"]), "lon": _valore(r["lon"]), "fonte_riferimento": fonte,
            "metodo_comune": metodo, "distanza_comune_km": distanza, "nota": nota,
        }
        distretto_comune = next((c["id_distretto"] for c in comuni if c["id_comune"] == id_comune), None)
        if id_comune and _valore(r.get("id_distretto")) and distretto_comune != r["id_distretto"]:
            riepilogo["discrepanze"].append(f"{id_stazione}: distretto {r['id_distretto']} dalla fonte, "
                                            f"{distretto_comune} dal comune")
    st["stazioni"] = sorted(per_stazione.values(), key=lambda r: (not str(r["id_stazione"]).isdigit(),
                                                                  len(str(r["id_stazione"])), str(r["id_stazione"])))
    st["stazioni_fonti"] = sorted(per_record.values(), key=lambda r: (priorita_nota.get(r["fonte"], 99),
                                                                       not r["id_nella_fonte"].isdigit(),
                                                                       len(r["id_nella_fonte"]), r["id_nella_fonte"]))
    riepilogo["stazioni_senza_comune"] = [r["id_stazione"] for r in st["stazioni"] if r["id_comune"] is None]

    # --- inquinanti -------------------------------------------------------------
    tracciati = {r["id_inquinante"]: r for r in inq["inquinanti"]}
    osservati = sorted(set(capacita["inquinante"]))
    for sigla in osservati:
        if sigla not in tracciati:
            fonti_inq = sorted(set(capacita.loc[capacita["inquinante"] == sigla, "fonte"]))
            tracciati[sigla] = {
                "id_inquinante": sigla, "descrizione": None, "unita_misura": unita.get(sigla),
                "periodo_misurazione": None, "valore_limite": None, "soglia_allarme": None,
                "riferimento_dashboard": sigla in RIFERIMENTO_DASHBOARD, "aggiunto_il": oggi,
                "origine": f"scoperto nei dati di {', '.join(fonti_inq)}",
            }
            riepilogo["inquinanti_nuovi"].append(sigla)
        elif tracciati[sigla]["unita_misura"] is None and unita.get(sigla):
            tracciati[sigla]["unita_misura"] = unita[sigla]
    inq["inquinanti"] = sorted(tracciati.values(), key=lambda r: (not r["riferimento_dashboard"], r["id_inquinante"]))

    # --- stazioni che misurano l'inquinante -------------------------------------
    coppie = {(r["id_stazione_fonte"], r["id_inquinante"]): r for r in inq["stazioni_inquinanti"]}
    record_per_stazione_fonte = {}
    for r in per_record.values():
        record_per_stazione_fonte.setdefault((r["id_stazione"], r["fonte"]), []).append(r["id_stazione_fonte"])
    da, a = data_inizio.isoformat(), data_fine.isoformat()
    for c in capacita.itertuples(index=False):
        for id_record in record_per_stazione_fonte.get((str(c.stazione), c.fonte), []):
            k = (id_record, c.inquinante)
            if k in coppie:
                coppie[k]["visto_da"] = min(coppie[k]["visto_da"], da)
                coppie[k]["visto_a"] = max(coppie[k]["visto_a"], a)
            else:
                coppie[k] = {"id_stazione_fonte": id_record, "id_inquinante": c.inquinante, "visto_da": da, "visto_a": a}
                riepilogo["coppie_nuove"] += 1
    inq["stazioni_inquinanti"] = [coppie[k] for k in sorted(coppie)]

    _applica_riferimenti(inq["inquinanti"])
    riepilogo["problemi"] = _salva(st, inq, comuni)
    return riepilogo


def _applica_riferimenti(inquinanti_rows):
    """Riapplica i valori limite normativi autorevoli (RIFERIMENTI_NORMATIVI) a ogni riga inquinante, così non
    vengono mai sovrascritti dai valori ARPA né persi in una rigenerazione. Gli inquinanti senza riferimenti noti
    (H2S, IPA) ottengono comunque le due colonne a None, mantenendo periodo/valore/soglia come sono."""
    for r in inquinanti_rows:
        n = RIFERIMENTI_NORMATIVI.get(r["id_inquinante"])
        if n:
            r["periodo_misurazione"], r["valore_limite"], r["soglia_allarme"] = n["primario"]
            r["riferimenti"] = n["riferimenti"]
            r["soglie_acute"] = n["soglie_acute"]
        else:
            r.setdefault("riferimenti", None)
            r.setdefault("soglie_acute", None)


def _numero(x):
    """Valore numerico o None: ARPA scrive 'null' o numeri come testo."""
    if x is None or str(x).strip().lower() in ("", "null", "none", "nan", "n/a", "-"):
        return None
    try:
        return float(str(x).replace(",", "."))
    except ValueError:
        return None


def _testo(x):
    return None if x is None or str(x).strip().lower() in ("", "null", "none") else str(x).strip()


def aggiorna_descrizioni_inquinanti(elenco_arpa):
    """Aggiorna descrizione e unità degli inquinanti già tracciati con l'elenco di ARPA
    (api.aria.arpa_puglia.get_inquinanti(): sigla, descrizione, unita_misura). I **valori limite** NON si
    prendono da ARPA (le sue statistiche sono ARPA-specifiche): sono dato autorevole di progetto e si
    riapplicano da RIFERIMENTI_NORMATIVI. Non aggiunge inquinanti. Restituisce le sigle aggiornate."""
    st, inq, comuni = _carica()
    per_sigla = {r["sigla"]: r for r in elenco_arpa}
    aggiornati = []
    for riga in inq["inquinanti"]:
        arpa = per_sigla.get(riga["id_inquinante"])
        if arpa is None:
            continue
        riga.update(descrizione=_testo(arpa.get("descrizione")), unita_misura=_testo(arpa.get("unita_misura")))
        aggiornati.append(riga["id_inquinante"])
    _applica_riferimenti(inq["inquinanti"])
    _salva(st, inq, comuni)
    return aggiornati
