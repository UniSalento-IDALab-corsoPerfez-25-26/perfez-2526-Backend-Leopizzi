#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API locale di OneHealth (FastAPI, solo 127.0.0.1): serve alla dashboard React i valori già
generati nei dataset JSON. Documentazione OpenAPI interattiva su /docs.

Avvio (dalla radice del repo):
    uv run localhost/server/main.py          # http://127.0.0.1:8000

Endpoint:
    POST /api/valori    {"giorno": "2024-06-15", "comune": "075035"}  oppure  {"giorno": ..., "distretto": "LE-51"}
        → tutti i valori di quella zona in quel giorno, per dominio (aria, salute, calore), senza medie.
    GET  /api/territorio            → province → distretti → comuni, per i selettori della dashboard.
    GET  /api/territorio/confini    → GeoJSON di distretti e comuni per la mappa.
    GET  /api/stato                 → servizio, versione dell'API e cosa c'è in locale (il Frontend lo chiama all'avvio).
    GET  /api/disponibilita         → mesi con un dataset aria, periodo dei decessi, anagrafica inquinanti.
    GET  /api/aria/mese             → valore del mese per distretto e comune (una fonte, tutti gli inquinanti) + stazioni.
    GET  /api/aria/calendario       → i giorni che l'archivio copre davvero: estremi e buchi della barra temporale.
    GET  /api/aria/finestra         → come /api/aria/mese ma su una finestra di giorni qualsiasi (barra temporale).
    GET  /api/aria/serie            → serie giornaliera di fino a 3 zone (confronto zona con zona).
    GET  /api/zona/dettaglio        → tutto ciò che si sa di una zona in una finestra di giorni, per dominio (pannello a sinistra della mappa).
    GET  /api/aria/fonti            → serie giornaliera di ogni fonte in una zona + concordanza (confronto fonte con fonte).
    GET  /api/calore/disponibilita  → mesi di temperatura ERA5-Land già in cache locale.
    GET  /api/calore/mappa          → temperatura ERA5-Land di tutte le zone in una finestra (modalità «temperatura» della mappa).
    GET  /api/calore/serie          → temperatura giornaliera (media/massima/minima) di fino a 3 zone, un mese.
    GET  /api/salute/decessi        → decessi ISTAT per distretto × mese (mai per comune × giorno: privacy).
    GET  /api/salute/dimissioni     → dimissioni ospedaliere ISTAT HFA per provincia × anno (solo informativo, non correlato).
    GET  /api/confronto             → aria, temperatura ERA5-Land e decessi per distretto × mese.
    GET  /api/stagionalita          → i 12 mesi dell'anno a confronto (aria, calore, decessi, PS/ADI/ricoveri simulati) e le criticità dell'anno, per Salento o distretto.
    GET  /api/salute/simulati/finestra → ricoveri, PS e ADI **simulati** di una zona (o del Salento) in una finestra.
    GET  /api/salute/simulati/serie → un indicatore simulato mese per mese, entrambi gli scenari, fino a 4 zone.
    GET  /api/assistente/stato      → se l'assistente può rispondere: Ollama attivo e modello scaricato.
    GET  /api/assistente/fatti      → scheda dei fatti di una card, calcolata senza modello di linguaggio.
    GET  /api/assistente/domande    → domande proposte di una card.
    POST /api/assistente            → risposta a una domanda: filtro, instradamento, analisi o documenti, modello, verifica.

Regole (docs/Regole_dei_dati.md): gli stati VALORE/NULL/NO_DATA arrivano fino al
frontend; un valore per fonte, **mai mediato fra fonti**; le medie per comune, distretto e mese seguono le
regole decise il 02/10/2026 (api/comune/aggregazione.py, v. localhost/server/aggregati_aria.py); il
disclaimer esplorativo sta nel payload.

All'avvio il server prepara in background le risposte con cui si apre la dashboard (finestra iniziale, valori
predefiniti del frontend) e le tiene in memoria finché i dati non cambiano: localhost/server/risposte_iniziali.py.
"""

import json
import math
import os
import re
import sys
import threading
import time
from calendar import monthrange
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # radice del repo, per i package api e localhost

import pandas as pd  # noqa: E402
from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.comune.aggregazione import NOTA_DISTRETTO_SENZA_STAZIONI, per_finestra  # noqa: E402
from api.comune.anagrafiche import FILE_ANAGRAFICHE, carica_anagrafiche, leggi_anagrafica  # noqa: E402
from localhost.server.aggregati_aria import (  # noqa: E402
    FONTE_ACCORPATA,
    LICENZE,
    SOGLIA_CONCORDANZA,
    CacheAria,
    FinestraAria,
    aggregati_periodo,
    confronti_fonti,
    statistica,
    testi_uso,
)
from localhost.server.dati_aria import ArchivioAria  # noqa: E402
from localhost.server.dati_calore import FONTE as FONTE_CALORE  # noqa: E402
from localhost.server.dati_calore import FONTE_ARPA as FONTE_CALORE_ARPA  # noqa: E402
from localhost.server.dati_calore import LICENZA_ARPA as LICENZA_CALORE_ARPA  # noqa: E402
from localhost.server.dati_calore import LICENZA as LICENZA_CALORE  # noqa: E402
from localhost.server.dati_calore import UNITA as UNITA_CALORE  # noqa: E402
from localhost.server.dati_calore import ArchivioCalore  # noqa: E402
from localhost.server.dati_salute import FONTE as FONTE_DECESSI  # noqa: E402
from localhost.server.dati_salute import LICENZA as LICENZA_DECESSI  # noqa: E402
from localhost.server.dati_salute import NOTA_PRIVACY, ArchivioDecessi  # noqa: E402
from localhost.server import consuntivi  # noqa: E402
from localhost.server import dati_dimissioni  # noqa: E402
from localhost.server.dati_dimissioni import ArchivioDimissioni  # noqa: E402
from localhost.server import salubrita  # noqa: E402
from localhost.server import dati_stagionalita  # noqa: E402
from localhost.server import risposte_iniziali  # noqa: E402
from localhost.server import dati_simulati  # noqa: E402
from localhost.server import dati_fonti_salute  # noqa: E402
from api.calore.soglie import SOGLIE as SOGLIE_CALDO  # noqa: E402
from localhost.server.dati_simulati import ArchivioSimulato  # noqa: E402
from api.aria.anagrafica_aria import RIFERIMENTI_NORMATIVI  # noqa: E402
from localhost.rag import assistente  # noqa: E402
from localhost.rag import config as config_assistente  # noqa: E402
from localhost.rag import ollama  # noqa: E402
from localhost.rag import prompt as prompt_assistente  # noqa: E402
from localhost.rag import schede  # noqa: E402
from localhost.rag.analisi import AnalisiNonApplicabile, dal_al, elenco, quando  # noqa: E402
from localhost.rag.perimetro import Instradamento, Rifiuto, controlla_parametri  # noqa: E402
from localhost.rag.serie import da_punti  # noqa: E402
from localhost.server.modelli import (  # noqa: E402
    CellaMensile,
    ComuneAria,
    ComuneCalore,
    ComuneTerritorio,
    ConfrontoConteggi,
    ConfrontoFonti,
    ConfrontoTemperatura,
    DettaglioCalore,
    DettaglioDecessi,
    DettaglioDimissioni,
    DettaglioFonteAria,
    DistrettoTerritorio,
    FileDataset,
    InfoFonte,
    InfoInquinante,
    MeseDisponibile,
    PeriodoCompleto,
    PeriodoDecessi,
    PeriodoDimissioni,
    ProvinciaTerritorio,
    PuntoDimissioni,
    PuntoDecessi,
    PuntoGiorno,
    PuntoMese,
    RichiestaValori,
    RispostaAriaFinestra,
    RispostaAriaMese,
    RispostaCalendarioAria,
    RispostaConfronto,
    RispostaDecessi,
    RispostaDimissioni,
    RispostaDettaglioZona,
    RispostaDisponibilita,
    RispostaDisponibilitaCalore,
    RispostaFontiAria,
    RispostaFontiCalore,
    RispostaFontiSalute,
    PuntoPeriodo,
    SerieFontePeriodo,
    SogliaFonti,
    RispostaSerieAria,
    RispostaCaloreMappa,
    RispostaSerieCalore,
    RispostaSalubritaMappa,
    RispostaSaluteMappa,
    ComponentiEventi,
    RispostaStagionalita,
    RispostaValori,
    SalubritaZona,
    SalubritaZonaMappa,
    SerieConfronto,
    SerieDecessi,
    SerieDimissioni,
    SerieFonte,
    SerieZona,
    SezioneAria,
    SezioneCalore,
    SezioneNonIntegrata,
    StazioneAria,
    StazioneMappa,
    Valore,
    Zona,
    ZonaRif,
    UsoFonteAccorpata,
    ValoreDimissioni,
    CellaRiepilogo,
    ColonnaRiepilogo,
    RigaRiepilogo,
    RispostaRiepilogo,
    DettaglioSimulati,
    IndicatoreSimulato,
    InfoSimulati,
    PuntoSimulato,
    RispostaSerieSimulata,
    SerieSimulata,
    CardAssistente,
    DomandaAssistente,
    DomandaProposta,
    FattoAssistente,
    RispostaAssistente,
    RispostaDomandeAssistente,
    RispostaFattiAssistente,
    SerieAssistente,
    StatoAssistente,
    StatoServizio,
    DatiInLocale,
    ValoreSimulato,
)

RADICE = Path(__file__).resolve().parents[2]
DIR_CONFINI = RADICE / "data" / "territorio" / "confini"
MESE = r"^\d{4}-(0[1-9]|1[0-2])$"
GIORNO = r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"
ID_DISTRETTO = re.compile(r"^[A-Z]{2}-\d{2}$")
MAX_ZONE = 4  # confronto zona con zona: quattro colori della palette (v. localhost/dashboard)
MAX_MESI_CONFRONTO = 36
FINESTRA_PREDEFINITA = 7   # «ultimi giorni» della barra: una settimana (06/10/2026); si apre sul periodo completo (28/10/2026)
MAX_GIORNI_FINESTRA = 31   # al più un mese per richiesta (decisione del 09/10/2026; era 92 giorni)
# la barra temporale parte dal 2024: da lì i tre domini (aria, calore, salute) sono tutti completi; l'archivio aria
# più vecchio resta su disco e nei report, ma la dashboard non lo mostra (decisione del 25/10/2026)
INIZIO_BARRA = date(2024, 1, 1)
REGOLE_AGGREGAZIONE = ("Comune: media delle stazioni fisiche con VALORE (le fonti modellate restano una serie a parte). "
                       "Distretto: media pesata sui residenti dei comuni con VALORE. Mese: media dei giorni con VALORE. "
                       "Regole del 02/10/2026.")
MOTIVO_CALORE = "nessun mese di temperatura ERA5-Land ancora scaricato in locale"

archivio = ArchivioAria()
cache_aria = CacheAria(archivio)
archivio_decessi = ArchivioDecessi()
archivio_dimissioni = ArchivioDimissioni()
archivio_calore = ArchivioCalore()
archivio_stagionalita = dati_stagionalita.ArchivioStagionalita()
archivio_simulato = ArchivioSimulato()
archivio_fonti_decessi = dati_fonti_salute.ArchivioFontiDecessi()
_territorio = {}
_blocco_territorio = threading.Lock()
_confini = {}
_blocco_confini = threading.Lock()


memoria_iniziale = risposte_iniziali.RisposteIniziali()
_blocco_preriscaldamento = threading.Lock()
_ancora_da_preriscaldare = threading.Event()
MAX_PASSATE = 3
# valori con cui si apre la dashboard (localhost/dashboard/src/App.tsx e componenti/ConfrontoDomini.tsx): se il frontend
# ne cambia uno, quella richiesta non trova la memoria e si calcola come prima, senza mai un dato sbagliato
ZONA_INIZIALE = "LE-51"
INQUINANTE_INIZIALE = "PM2.5"
SCENARIO_INIZIALE = "letteratura"
MESI_CONFRONTO_INIZIALE = 12


def _richieste_iniziali(periodo: PeriodoCompleto | None) -> list[str]:
    """Le GET che la dashboard manda all'apertura, sulla finestra iniziale (il periodo completo) e sulla finestra
    precedente della stessa ampiezza, che serve alla variazione del riepilogo (03/11/2026)."""
    richieste = [("/api/territorio", {}), ("/api/territorio/confini", {}), ("/api/disponibilita", {}),
                 ("/api/aria/calendario", {})]
    if periodo is not None:
        da, a = periodo.da, periodo.a
        fine_prima = da - timedelta(days=1)
        inizio_prima = fine_prima - timedelta(days=(a - da).days)
        mese, n_mesi = a.strftime("%Y-%m"), (a.year * 12 + a.month) - (da.year * 12 + da.month) + 1
        primo_confronto = _sposta_mese(mese, -(MESI_CONFRONTO_INIZIALE - 1))
        finestra = {"da": da.isoformat(), "a": a.isoformat()}
        richieste += [
            ("/api/zona/dettaglio", {"zona": ZONA_INIZIALE, **finestra, "scenario": SCENARIO_INIZIALE}),
            ("/api/aria/finestra", {**finestra, "fonte": FONTE_ACCORPATA}),
            ("/api/aria/finestra", {"da": inizio_prima.isoformat(), "a": fine_prima.isoformat(), "fonte": FONTE_ACCORPATA}),
            ("/api/aria/serie", {"mese": mese, "inquinante": INQUINANTE_INIZIALE, "fonte": FONTE_ACCORPATA,
                                 "zone": ZONA_INIZIALE}),
            ("/api/confronto", {"da": primo_confronto, "a": mese, "inquinante": INQUINANTE_INIZIALE,
                                "fonte": FONTE_ACCORPATA, "distretti": ZONA_INIZIALE, "statistica_calore": "massima"}),
            ("/api/salute/simulati/serie", {"da": primo_confronto, "a": mese, "indicatore": "ps_accessi",
                                            "zone": ZONA_INIZIALE}),
            ("/api/salute/mappa", {**finestra, "scenario": SCENARIO_INIZIALE}),
            ("/api/salute/simulati/finestra", {"zona": dati_stagionalita.ZONA_SALENTO, **finestra,
                                               "scenario": SCENARIO_INIZIALE}),
            ("/api/salute/decessi", {"da": _sposta_mese(da.strftime("%Y-%m"), -n_mesi), "a": mese}),
            ("/api/salute/dimissioni", {"da": str(max(1999, a.year - 2)), "a": str(a.year), "province": "LE,BR,TA",
                                        "gruppi": "respiratorio"}),
        ]
    return [risposte_iniziali.chiave(p, q) for p, q in richieste]


def _preriscalda():
    """Calcola in background il mese aria con cui si apre la dashboard e i decessi, poi le risposte della finestra
    iniziale, che restano in memoria: la prima apertura non aspetta. Rilanciato quando i dati cambiano: se cambiano
    di nuovo mentre gira (un archivio in aggiornamento), le risposte calcolate prima del cambio non valgono e si
    ripete, al più MAX_PASSATE volte; quelle che restano fuori si calcolano alla richiesta, come prima."""
    _ancora_da_preriscaldare.set()
    if not _blocco_preriscaldamento.acquire(blocking=False):
        return  # già in corso: ripeterà lui
    try:
        for _ in range(MAX_PASSATE):
            if not _ancora_da_preriscaldare.is_set():
                break
            _ancora_da_preriscaldare.clear()
            if _preriscalda_una_volta():
                _ancora_da_preriscaldare.set()
    finally:
        _blocco_preriscaldamento.release()


def _preriscalda_una_volta():
    """Una passata; restituisce quante risposte sono state scartate perché i dati sono cambiati nel frattempo."""
    try:
        inizio = time.monotonic()
        mesi = archivio.mesi_disponibili()
        # il periodo completo legge anche decessi e calore: è la finestra iniziale della barra (28/10/2026)
        periodo = _periodo_completo([g for g in archivio.giorni_disponibili() if g >= INIZIO_BARRA])
        if mesi:
            cache_aria.mese(periodo.da.strftime("%Y-%m") if periodo else max(mesi))
            for m in sorted(mesi):  # consuntivi mensili da disco (data/interim/consuntivi/): pochi ms per mese
                cache_aria.riassunto(m, tieni=False)
        archivio_decessi.distretto_mese()  # già letti dal periodo completo, salvo archivio aria vuoto
        archivio_stagionalita.aria()  # riassunti della tab Stagionalità: la prima lettura dura qualche secondo
        archivio_stagionalita.calore()
        archivio_simulato.parametri()  # il parquet dei dati simulati in forma larga: ~2,6 milioni di righe da girare
        esiti = risposte_iniziali.prepara(app, memoria_iniziale, _richieste_iniziali(periodo))
        falliti = [f"{k} ({c})" for k, c in esiti.items() if c != 200]
        fuori = len(memoria_iniziale.mancanti()) - len(falliti)
        print(f"preriscaldamento: {len(esiti) - len(falliti) - fuori}/{len(esiti)} risposte della finestra iniziale in "
              "memoria" + (f" ({periodo.da} → {periodo.a})" if periodo else "") + f" in {time.monotonic() - inizio:.1f} s"
              + (f"; {fuori} scartate perché i dati sono cambiati nel frattempo" if fuori else "")
              + (f"; non riuscite: {', '.join(falliti)}" if falliti else ""), flush=True)
        return fuori
    except Exception as exc:  # noqa: BLE001 - il preriscaldamento non deve mai fermare il server
        print(f"preriscaldamento non riuscito: {exc}", file=sys.stderr)
        return 0


memoria_iniziale.al_cambio = _preriscalda


@asynccontextmanager
async def ciclo_di_vita(_app):
    threading.Thread(target=_preriscalda, daemon=True).start()
    yield


# host, porta e origini consentite (CORS) dalle variabili d'ambiente, coi valori di sempre come default (piano F0.1)
HOST = os.environ.get("ONEHEALTH_HOST", "127.0.0.1")
PORTA = int(os.environ.get("ONEHEALTH_PORT", "8000"))
ORIGINI_CONSENTITE = [o.strip() for o in os.environ.get(
    "ONEHEALTH_ORIGINI", "http://127.0.0.1:5173,http://localhost:5173").split(",") if o.strip()]

VERSIONE_API = "0.2.0"  # da confrontare con quella attesa dal Frontend (piano F0.3)
NOME_SERVIZIO = "OneHealth — API locale"

app = FastAPI(title=NOME_SERVIZIO, version=VERSIONE_API, lifespan=ciclo_di_vita,
              description="Valori di aria e decessi (e, quando integrato, calore) per comune o distretto.")
# prima del CORS, che così resta all'esterno e aggiunge le sue intestazioni anche alle risposte tenute in memoria
app.add_middleware(risposte_iniziali.MiddlewareRisposteIniziali, memoria=memoria_iniziale)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINI_CONSENTITE, allow_methods=["GET", "POST"], allow_headers=["*"])


def _pulito(v):
    """NaN/NA di pandas → None (Pydantic non accetta NaN per i campi testo)."""
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
        if v != v:  # pd.NA e simili
            return None
    except TypeError:
        return None
    return v


def territorio():
    """Anagrafica del territorio in memoria: province, distretti, comuni (caricata al primo uso). Sotto blocco e scritta
    in un colpo solo: richieste concorrenti all'apertura vedevano la cache con «province» ma senza «comuni»."""
    with _blocco_territorio:
        if not _territorio:
            _, tabelle = carica_anagrafiche({"territorio": FILE_ANAGRAFICHE["territorio"]})
            _territorio.update(
                province=tabelle["province"].to_dict("records"),
                distretti={r["id_distretto"]: r for r in tabelle["distretti"].to_dict("records")},
                comuni={r["id_comune"]: {k: _pulito(v) for k, v in r.items()} for r in tabelle["comuni"].to_dict("records")})
    return _territorio


_stazioni_fisiche = {}


def stazioni_fisiche_per_comune():
    """{id_comune: numero di stazioni fisiche dell'aria}, di qualunque fonte, dall'anagrafica stazioni.json (le virtuali
    CAMS escluse). Un comune assente non ha stazioni: l'unico dato aria è CAMS, modellato. Dato statico (non dipende
    dal periodo: le stazioni fisiche sono le stesse nel 2024, nel 2025 e nel 2026, docs/Regole_dei_dati.md), caricato al primo uso."""
    if not _stazioni_fisiche:
        _, _, tabelle = leggi_anagrafica(FILE_ANAGRAFICHE["stazioni"])
        conteggio = {}
        for s in tabelle["stazioni"]:
            if s.get("id_comune") and s.get("fonte_riferimento") != "CAMS" and not str(s["id_stazione"]).startswith("CAMS-"):
                conteggio[s["id_comune"]] = conteggio.get(s["id_comune"], 0) + 1
        _stazioni_fisiche["per_comune"] = conteggio
    return _stazioni_fisiche["per_comune"]


def _comuni_del_distretto(id_distretto):
    return sorted(c["id_comune"] for c in territorio()["comuni"].values() if c["id_distretto"] == id_distretto)


def _zona(richiesta: RichiestaValori) -> Zona:
    t = territorio()
    if richiesta.comune is not None:
        comune = t["comuni"].get(richiesta.comune)
        if comune is None:
            raise HTTPException(404, f"comune '{richiesta.comune}' non trovato (atteso id_comune ISTAT a 6 cifre)")
        distretto = t["distretti"][comune["id_distretto"]]
        return Zona(tipo="comune", id=comune["id_comune"], denominazione=comune["denominazione"],
                    id_distretto=distretto["id_distretto"], id_provincia=distretto["id_provincia"], comuni=[comune["id_comune"]])
    distretto = t["distretti"].get(richiesta.distretto)
    if distretto is None:
        raise HTTPException(404, f"distretto '{richiesta.distretto}' non trovato (atteso es. 'LE-51')")
    comuni = _comuni_del_distretto(distretto["id_distretto"])
    return Zona(tipo="distretto", id=distretto["id_distretto"], denominazione=distretto["denominazione"],
                id_distretto=distretto["id_distretto"], id_provincia=distretto["id_provincia"], comuni=comuni)


def _zona_rif(id_zona) -> ZonaRif:
    """Un distretto ('LE-51') o un comune ('075035') come riferimento di zona; 404 se non esiste."""
    t = territorio()
    if ID_DISTRETTO.match(id_zona):
        d = t["distretti"].get(id_zona)
        if d is None:
            raise HTTPException(404, f"distretto '{id_zona}' non trovato")
        return ZonaRif(tipo="distretto", id=id_zona, denominazione=d["denominazione"], id_distretto=id_zona)
    c = t["comuni"].get(id_zona)
    if c is None:
        raise HTTPException(404, f"zona '{id_zona}' non trovata (atteso id_distretto, es. 'LE-51', o id_comune ISTAT)")
    return ZonaRif(tipo="comune", id=id_zona, denominazione=c["denominazione"], id_distretto=c["id_distretto"])


def _sezione_aria(richiesta: RichiestaValori, zona: Zona) -> SezioneAria:
    trovato = archivio.valori_del_giorno(richiesta.giorno, zona.comuni)
    if trovato is None:
        return SezioneAria(stato="NON_DISPONIBILE",
                           motivo=f"l'archivio dell'aria non copre ancora il {richiesta.giorno.isoformat()}")
    nome_file, meta, righe = trovato
    comuni_t = territorio()["comuni"]
    per_comune = {}
    for comune, stazione, fonte, inquinante, valore, stato, nota in righe:
        c = per_comune.setdefault(comune, {"stazioni": {}, "celle": {}})
        c["stazioni"].setdefault(stazione, {}).setdefault(fonte, {})[inquinante] = Valore(valore=valore, stato=stato, nota=nota)
        conteggio = c["celle"].setdefault(fonte, {}).setdefault(inquinante, {"VALORE": 0, "NULL": 0, "NO_DATA": 0})
        conteggio[stato] += 1

    def stazione_aria(id_stazione, valori):
        if id_stazione == "nessuna_stazione":
            return StazioneAria(id_stazione=id_stazione, denominazione=None, tipo="assente", valori=valori)
        schede = [s for fonte in meta["stazioni"].get(id_stazione, {}).get("fonti", {}).values() for s in fonte]
        scheda = schede[0] if schede else {}
        tipo = "virtuale_modello" if id_stazione.startswith("CAMS-") else "fisica"
        return StazioneAria(id_stazione=id_stazione, denominazione=scheda.get("denominazione"), tipo=tipo,
                            lat=scheda.get("lat"), lon=scheda.get("lon"), valori=valori)

    comuni = [
        ComuneAria(
            id_comune=id_comune, denominazione=comuni_t[id_comune]["denominazione"],
            stazioni=[stazione_aria(s, v) for s, v in sorted(per_comune[id_comune]["stazioni"].items(),
                                                             key=lambda kv: (kv[0] == "nessuna_stazione", kv[0]))],
            celle_per_stato=per_comune[id_comune]["celle"])
        for id_comune in zona.comuni if id_comune in per_comune
    ]
    return SezioneAria(stato="DISPONIBILE", dataset=nome_file, generato_il=meta["generato_il"], fonti=meta["fonti"],
                       inquinanti=meta["inquinanti"], comuni=comuni)


def _sezione_calore(richiesta: RichiestaValori, zona: Zona) -> SezioneCalore:
    giorno = richiesta.giorno.isoformat()
    base = dict(fonte=FONTE_CALORE, licenza=LICENZA_CALORE, unita=UNITA_CALORE, mesi=archivio_calore.mesi_in_cache())
    if not any(base["mesi"].values()):
        return SezioneCalore(stato="NON_INTEGRATO", motivo=MOTIVO_CALORE)
    trovati = archivio_calore.valori_del_giorno(giorno, zona.comuni)
    if not trovati:
        return SezioneCalore(stato="NON_DISPONIBILE", motivo=f"temperatura ERA5-Land non in cache per {giorno[:7]}", **base)
    comuni_t = territorio()["comuni"]
    comuni = [ComuneCalore(id_comune=c, denominazione=comuni_t[c]["denominazione"],
                           **{s: Valore(valore=_pulito(r.valore), stato=r.stato, nota=_pulito(r.nota)) for s, r in trovati[c].items()})
              for c in zona.comuni if c in trovati]
    return SezioneCalore(stato="DISPONIBILE", comuni=comuni, **base)


@app.post("/api/valori", response_model=RispostaValori, summary="Tutti i valori di un comune o distretto in un giorno")
def valori(richiesta: RichiestaValori) -> RispostaValori:
    zona = _zona(richiesta)
    return RispostaValori(
        giorno=richiesta.giorno, zona=zona, aria=_sezione_aria(richiesta, zona),
        salute=SezioneNonIntegrata(motivo="dataset salute non ancora generato (primo passo: decessi comunali giornalieri ISTAT). "
                                          "Quando ci sarà, il dato di decesso sarà restituito aggregato almeno a distretto e a mese, "
                                          "non per comune × giorno (regola di privacy)."),
        calore=_sezione_calore(richiesta, zona),
    )


@app.get("/api/territorio", response_model=list[ProvinciaTerritorio], summary="Province, distretti e comuni per i selettori")
def get_territorio():
    """Con, per ogni comune e distretto, il **flag esplicito** `senza_stazioni` (decisione del 14/10/2026): nessuna stazione
    fisica di nessuna fonte, l'unico dato aria è CAMS. La dashboard lo usa per distinguere queste zone da un buco temporale."""
    t = territorio()
    fisiche = stazioni_fisiche_per_comune()
    aree = {f["properties"]["nome"]: f["properties"].get("area_kmq") for f in get_confini()["comuni"]["features"]}

    def media_su_area(comuni, campo):
        """Fattori di mitigazione CLMS (16/10/2026): sono quote di superficie, quindi il distretto è la media dei comuni
        pesata sull'area, non sui residenti. None se nessun comune ha il valore."""
        coppie = [(c[campo], aree.get(c["nome_confine"])) for c in comuni if c.get(campo) is not None and aree.get(c["nome_confine"])]
        totale = sum(a for _, a in coppie)
        return round(sum(v * a for v, a in coppie) / totale, 2) if totale else None

    out = []
    for p in t["province"]:
        distretti = []
        for d in (d for d in t["distretti"].values() if d["id_provincia"] == p["id_provincia"]):
            comuni = sorted((c for c in t["comuni"].values() if c["id_distretto"] == d["id_distretto"]),
                            key=lambda c: c["denominazione"])
            sede = t["comuni"].get(d.get("id_comune_sede"))
            n_distretto = sum(fisiche.get(c["id_comune"], 0) for c in comuni)
            distretti.append(DistrettoTerritorio(
                id_distretto=d["id_distretto"], denominazione=d["denominazione"], id_comune_sede=d.get("id_comune_sede"),
                sede=sede["denominazione"] if sede else None, residenti=sum(c["residenti"] or 0 for c in comuni),
                stazioni_fisiche=n_distretto, senza_stazioni=n_distretto == 0,
                copertura_arborea_pct=media_su_area(comuni, "copertura_arborea_pct"),
                suolo_impermeabile_pct=media_su_area(comuni, "suolo_impermeabile_pct"),
                comuni=[ComuneTerritorio(id_comune=c["id_comune"], denominazione=c["denominazione"],
                                         residenti=c["residenti"], nome_confine=c["nome_confine"], nota=c["nota"],
                                         stazioni_fisiche=fisiche.get(c["id_comune"], 0),
                                         senza_stazioni=fisiche.get(c["id_comune"], 0) == 0,
                                         lat=c.get("lat"), lon=c.get("lon"), area_kmq=aree.get(c["nome_confine"]),
                                         copertura_arborea_pct=c.get("copertura_arborea_pct"),
                                         suolo_impermeabile_pct=c.get("suolo_impermeabile_pct"))
                        for c in comuni]))
        out.append(ProvinciaTerritorio(id_provincia=p["id_provincia"], denominazione=p["denominazione"], distretti=distretti))
    return out


@app.get("/api/territorio/confini", summary="Confini GeoJSON di distretti e comuni")
def get_confini():
    """`distretti` da distretti_salento.geojson; `comuni` da comuni_salento.geojson con, in più, `id_comuni`:
    gli id ISTAT dei comuni che usano quel poligono (un solo id per poligono dal 14/10/2026, dopo
    che Presicce e Acquarica del Capo sono stati unificati in Presicce-Acquarica, 075098)."""
    # all'apertura /api/territorio e /api/territorio/confini arrivano insieme: senza blocco il secondo trovava la cache
    # già con «distretti» ma ancora senza «comuni» (KeyError, 28/10/2026)
    with _blocco_confini:
        if not _confini:
            per_confine = {}
            for c in territorio()["comuni"].values():
                per_confine.setdefault(c["nome_confine"], []).append(c["id_comune"])
            with open(DIR_CONFINI / "distretti_salento.geojson", encoding="utf-8") as f:
                distretti = json.load(f)
            with open(DIR_CONFINI / "comuni_salento.geojson", encoding="utf-8") as f:
                comuni = json.load(f)
            for feat in comuni["features"]:
                feat["properties"]["id_comuni"] = sorted(per_confine.get(feat["properties"]["nome"], []))
            _confini.update(distretti=distretti, comuni=comuni)
    return _confini


def _disponibilita_calore() -> SezioneCalore:
    mesi = archivio_calore.mesi_in_cache()
    if not any(mesi.values()):
        return SezioneCalore(stato="NON_INTEGRATO", motivo=MOTIVO_CALORE)
    return SezioneCalore(stato="DISPONIBILE", fonte=FONTE_CALORE, licenza=LICENZA_CALORE, unita=UNITA_CALORE, mesi=mesi)


@app.get("/api/stato", response_model=StatoServizio, summary="Il servizio è vivo? Che versione? Ci sono dati in locale?")
def get_stato():
    """Leggero: conta file, non legge i dataset. Il Frontend lo chiama all'avvio per scegliere l'avviso giusto."""
    mesi_aria = sorted(archivio.mesi_disponibili())
    mesi_calore = max((len(m) for m in archivio_calore.mesi_in_cache().values()), default=0)
    consuntivi_pronti = len(list(consuntivi.DIR_CONSUNTIVI.glob("aria_*.pkl"))) if consuntivi.DIR_CONSUNTIVI.exists() else 0
    stagionalita = dati_stagionalita.DIR_STAGIONALITA.exists() and any(dati_stagionalita.DIR_STAGIONALITA.glob("aria_*.json"))
    dati = DatiInLocale(
        mesi_aria=len(mesi_aria), ultimo_mese_aria=mesi_aria[-1] if mesi_aria else None, mesi_calore=mesi_calore,
        decessi=archivio_decessi.disponibile(), dimissioni=archivio_dimissioni.disponibile(),
        simulati=archivio_simulato.disponibile(), consuntivi_pronti=consuntivi_pronti, stagionalita_pronta=bool(stagionalita))
    con_dati = bool(mesi_aria or mesi_calore or dati.decessi or dati.dimissioni or dati.simulati)
    return StatoServizio(servizio=NOME_SERVIZIO, versione_api=VERSIONE_API, con_dati=con_dati, dati=dati)


@app.get("/api/disponibilita", response_model=RispostaDisponibilita, summary="Cosa c'è da mostrare: mesi, inquinanti, decessi")
def get_disponibilita():
    _, _, tabelle = leggi_anagrafica(FILE_ANAGRAFICHE["inquinanti"])
    inquinanti = []
    for r in tabelle["inquinanti"]:
        # descrizione/unità dall'anagrafica (ARPA); i limiti dal dato autorevole di progetto (RIFERIMENTI_NORMATIVI),
        # così sono corretti anche se una rigenerazione ha azzerato le colonne del JSON
        n = RIFERIMENTI_NORMATIVI.get(r["id_inquinante"])
        periodo, valore, allarme = n["primario"] if n else (r.get("periodo_misurazione"), r.get("valore_limite"), r.get("soglia_allarme"))
        inquinanti.append(InfoInquinante(
            id=r["id_inquinante"], descrizione=r.get("descrizione"), unita=r.get("unita_misura"),
            riferimento=bool(r.get("riferimento_dashboard")), valore_limite=valore, periodo_limite=periodo,
            soglia_allarme=allarme, riferimenti=n["riferimenti"] if n else None,
            soglie_acute=n["soglie_acute"] if n else None))
    decessi = None
    if archivio_decessi.disponibile():
        dm, fino = archivio_decessi.distretto_mese()
        con_valore = dm[dm["stato"] == "VALORE"]["mese"]
        if len(con_valore):
            decessi = PeriodoDecessi(da=dm["mese"].min(), a=con_valore.max(), copertura_fino_al=fino,
                                     fonte=FONTE_DECESSI, licenza=LICENZA_DECESSI)
    dimissioni = None
    anno_da, anno_a = archivio_dimissioni.anni_con_valore()
    if anno_a is not None:
        dimissioni = PeriodoDimissioni(da=anno_da, a=anno_a, fonte=dati_dimissioni.FONTE, licenza=dati_dimissioni.LICENZA)
    aria = [MeseDisponibile(mese=m, giorni_coperti=g, giorni_del_mese=monthrange(int(m[:4]), int(m[5:]))[1])
            for m, g in archivio.mesi_disponibili().items()]
    return RispostaDisponibilita(aria=aria, inquinanti=inquinanti, decessi=decessi, dimissioni=dimissioni,
                                 simulati=_info_simulati(), calore=_disponibilita_calore())


def _aggregati(mese):
    agg = cache_aria.mese(mese)
    if agg is None:
        raise HTTPException(404, f"l'archivio dell'aria non copre ancora {mese}")
    return agg


def _controlla_fonte(agg, fonte):
    fonti = sorted(agg.comune_giorno["fonte"].unique())
    if fonte not in fonti:
        raise HTTPException(404, f"fonte '{fonte}' assente nel dataset di {agg.mese}: disponibili {', '.join(fonti)}")


def _modellata(agg, fonte):
    return fonte in agg.fonti_virtuali or bool((agg.meta["fonti"].get(fonte) or {}).get("modellata"))


def _note_accorpata(distretti, comuni, uso):
    """Vista «tutte le fonti»: aggiunge alla nota di ogni cella con valore quali fonti sono entrate nella media e quali
    sono state scartate per scarto, così il tooltip della mappa dice da dove viene il numero (decisione del 14/10/2026)."""
    testi = testi_uso(uso, cache_aria.pesi())
    for livello, celle in (("distretto", distretti), ("comune", comuni)):
        for zona, per_inq in celle.items():
            for inq, cella in per_inq.items():
                t = testi.get((livello, zona, inq))
                if t and cella.stato == "VALORE":
                    prefisso = "su comuni × giorni del distretto, " if livello == "distretto" else ""
                    cella.nota = "; ".join(filter(None, [cella.nota, prefisso + t]))


@app.get("/api/aria/mese", response_model=RispostaAriaMese, summary="Valore del mese per distretto e comune, una fonte")
def aria_mese(mese: str = Query(pattern=MESE, description="AAAA-MM"),
              fonte: str = Query("ARPA", description="una fonte del dataset (i valori non si mediano fra fonti), oppure «Tutte»: media delle fonti concordi, solo presentazione")):
    agg = _aggregati(mese)
    _controlla_fonte(agg, fonte)
    inquinanti = sorted(agg.comune_giorno["inquinante"].unique())

    cop_d = {(r.distretto, r.inquinante): r for r in agg.copertura_distretto[agg.copertura_distretto["fonte"] == fonte].itertuples()}
    distretti = {}
    for r in agg.distretto_mese[agg.distretto_mese["fonte"] == fonte].itertuples():
        cop = cop_d.get((r.distretto, r.inquinante))
        distretti.setdefault(r.distretto, {})[r.inquinante] = CellaMensile(
            valore=_pulito(r.valore), stato=r.stato, nota=_pulito(r.nota), giorni=int(r.giorni),
            giorni_con_valore=int(r.giorni_con_valore), con_valore=int(cop.con_valore) if cop else None,
            totale=int(cop.totale) if cop else None, quota_residenti=float(cop.quota_residenti) if cop else None)

    cop_c = {(r.comune, r.inquinante): r for r in agg.copertura_comune[agg.copertura_comune["fonte"] == fonte].itertuples()}
    comuni = {}
    for r in agg.comune_mese[agg.comune_mese["fonte"] == fonte].itertuples():
        cop = cop_c.get((r.comune, r.inquinante))
        comuni.setdefault(r.comune, {})[r.inquinante] = CellaMensile(
            valore=_pulito(r.valore), stato=r.stato, nota=_pulito(r.nota), giorni=int(r.giorni),
            giorni_con_valore=int(r.giorni_con_valore),
            # fonte misurata in un comune senza stazioni fisiche: 0 su 0; fonte modellata: non si contano stazioni
            con_valore=int(cop.con_valore) if cop else (0 if fonte not in agg.fonti_virtuali | {FONTE_ACCORPATA} else None),
            totale=int(cop.totale) if cop else (0 if fonte not in agg.fonti_virtuali | {FONTE_ACCORPATA} else None))
    if fonte == FONTE_ACCORPATA:
        _note_accorpata(distretti, comuni, agg.uso_fonti)

    return RispostaAriaMese(
        mese=mese, fonte=fonte, fonte_modellata=_modellata(agg, fonte), giorni_coperti=agg.meta["giorni_coperti"],
        giorni_del_mese=agg.meta["giorni_del_mese"], dataset=[FileDataset(**f) for f in agg.meta["file"]],
        fonti=_info_fonti(agg, inquinanti), inquinanti=inquinanti, distretti=distretti, comuni=comuni,
        stazioni=_stazioni_mappa(agg), regole=REGOLE_AGGREGAZIONE)


def _info_fonti(agg, inquinanti, fonti=None):
    fonti = fonti if fonti is not None else sorted(agg.comune_giorno["fonte"].unique())
    return [InfoFonte(nome=f, modellata=_modellata(agg, f),
                      copertura_da=(agg.meta["fonti"].get(f) or {}).get("copertura_da"),
                      statistiche={i: statistica(f, i) for i in inquinanti}, licenza=LICENZE.get(f, "non dichiarata"))
            for f in fonti]


def _stazioni_mappa(agg):
    stazioni = []
    for id_stazione, scheda in agg.meta["stazioni"].items():
        if id_stazione.startswith("CAMS-") or id_stazione == "nessuna_stazione":
            continue
        fonti_st = scheda.get("fonti", {})
        principale = (fonti_st.get("ARPA") or next(iter(fonti_st.values()), [{}]))[0]
        stazioni.append(StazioneMappa(
            id_stazione=id_stazione, denominazione=principale.get("denominazione"), lat=principale.get("lat"),
            lon=principale.get("lon"), id_comune=scheda.get("comune"), id_distretto=scheda.get("distretto"),
            fonti=sorted(fonti_st), inquinanti_con_valore=agg.inquinanti_per_stazione.get(id_stazione, {})))
    return stazioni


@app.get("/api/aria/calendario", response_model=RispostaCalendarioAria,
         summary="I giorni coperti dall'archivio, per la barra temporale")
def aria_calendario():
    """L'asse della barra di progressione della dashboard: estremi dell'archivio, giorni
    effettivamente coperti e buchi in mezzo. I file del dataset sono mensili (un mese per
    file, v. api/aria/archivio_aria.py), quindi l'asse cresce di un mese alla volta mentre
    il mese in corso si allunga giorno per giorno. L'asse parte da INIZIO_BARRA (2024-01-01):
    prima di allora mancano calore e salute simulata. La finestra iniziale è `periodo_completo`."""
    giorni = [g for g in archivio.giorni_disponibili() if g >= INIZIO_BARRA]
    buchi = [b for b in archivio.buchi() if b.split(" → ")[1] >= INIZIO_BARRA.isoformat()]
    return RispostaCalendarioAria(
        da=giorni[0] if giorni else None, a=giorni[-1] if giorni else None, giorni=giorni,
        buchi=buchi, finestra_predefinita=FINESTRA_PREDEFINITA, finestra_massima=MAX_GIORNI_FINESTRA,
        periodo_completo=_periodo_completo(giorni))


def _periodo_completo(giorni_aria: list[date]) -> PeriodoCompleto | None:
    """L'ultimo mese di calendario coperto per intero da aria, calore, decessi e dati simulati: la finestra con cui
    la dashboard si apre (decisione del 28/10/2026). Un dominio assente (mai scaricato) non conta; i ricoveri HFA
    neanche, perché sono annuali e il pannello mostra comunque l'ultimo anno pubblicato."""
    if not giorni_aria:
        return None
    _, fino_decessi = archivio_decessi.distretto_mese()
    sim_da, sim_a = archivio_simulato.periodo() if archivio_simulato.disponibile() else (None, None)
    fino_al = {"aria": giorni_aria[-1].isoformat(), "calore": archivio_calore.ultimo_giorno(),
               "decessi": fino_decessi, "simulati": sim_a}
    coperti = set(giorni_aria)
    mese = giorni_aria[-1].replace(day=1)
    while mese >= INIZIO_BARRA:
        ultimo = mese.replace(day=monthrange(mese.year, mese.month)[1])
        if (all(f is None or f >= ultimo.isoformat() for f in fino_al.values())
                and all(mese + timedelta(days=i) in coperti for i in range(ultimo.day))
                and (sim_da is None or sim_da <= mese.isoformat())
                and (fino_al["calore"] is None or archivio_calore.mese_completo(mese.strftime("%Y-%m")))):
            return PeriodoCompleto(da=mese, a=ultimo, fino_al=fino_al,
                                   limitato_da=[d for d, f in fino_al.items() if f is not None and f < fino_al["aria"]])
        mese = (mese - timedelta(days=1)).replace(day=1)
    return None


def _giorni_finestra(da: str, a: str) -> list[str]:
    """I giorni ISO di una finestra, al più MAX_GIORNI_FINESTRA (un mese)."""
    try:
        d0, d1 = date.fromisoformat(da), date.fromisoformat(a)
    except ValueError as exc:
        raise HTTPException(422, f"date non valide: {exc}") from exc
    if d1 < d0:
        raise HTTPException(422, f"la finestra finisce ({d1}) prima di iniziare ({d0})")
    numero = (d1 - d0).days + 1
    if numero > MAX_GIORNI_FINESTRA:
        raise HTTPException(422, f"finestra di {numero} giorni: il massimo è {MAX_GIORNI_FINESTRA} (un mese): "
                                 "per periodi più lunghi usare /api/aria/mese")
    return [(d0 + timedelta(days=n)).isoformat() for n in range(numero)]


def _celle(df, cop, colonna, distretto: bool, virtuale: bool, zona_id=None):
    """{zona: {inquinante: CellaMensile}} da un aggregato di finestra (di una sola fonte) e dalla sua copertura."""
    if zona_id is not None:
        df, cop = df[df[colonna] == zona_id], cop[cop[colonna] == zona_id]
    mappa_cop = {(getattr(r, colonna), r.inquinante): r for r in cop.itertuples()}
    out = {}
    for r in df.itertuples():
        zona = getattr(r, colonna)
        c = mappa_cop.get((zona, r.inquinante))
        if distretto:
            extra = dict(con_valore=int(c.con_valore) if c else 0, totale=int(c.totale) if c else None,
                         quota_residenti=float(c.quota_residenti) if c else 0.0)
        else:
            # fonte modellata: non si contano stazioni fisiche, il valore è della cella del modello
            noto = c is not None and c.totale == c.totale  # NaN: il comune non ha stazioni fisiche
            con, tot = (None, None) if virtuale else ((int(c.con_valore), int(c.totale)) if noto else (0, 0))
            extra = dict(con_valore=con, totale=tot)
        out.setdefault(zona, {})[r.inquinante] = CellaMensile(
            valore=_pulito(r.valore), stato=r.stato, nota=_pulito(r.nota), giorni=int(r.giorni),
            giorni_con_valore=int(r.giorni_con_valore), **extra)
    return out


def _di_fonte(f: FinestraAria, fonte):
    def sel(df):
        return df[df["fonte"] == fonte]
    return sel(f.comune), sel(f.distretto), sel(f.copertura_comune), sel(f.copertura_distretto)


@app.get("/api/aria/finestra", response_model=RispostaAriaFinestra,
         summary="Valore di una finestra di giorni (fino a un mese) per distretto e comune, una fonte")
def aria_finestra(da: str = Query(pattern=GIORNO, description="primo giorno della finestra, AAAA-MM-GG"),
                  a: str = Query(pattern=GIORNO, description="ultimo giorno della finestra, AAAA-MM-GG"),
                  fonte: str = Query("ARPA", description="una fonte del dataset (i valori non si mediano fra fonti), oppure «Tutte»: media delle fonti concordi, solo presentazione")):
    """Come /api/aria/mese, ma su una finestra di giorni qualsiasi, fino a un mese: è quello che la mappa ridisegna
    a ogni passo della barra temporale. I mesi interi della finestra si leggono dai riassunti mensili, i mesi di
    bordo dai giorni (localhost/server/aggregati_aria.py, `aggregati_periodo`): il risultato è la media dei giorni
    con VALORE, come prima. Il confronto fra domini resta a distretto × mese (docs/Regole_dei_dati.md)."""
    giorni = _giorni_finestra(da, a)
    f = aggregati_periodo(cache_aria, giorni, fonte)
    if f is None:
        raise HTTPException(404, f"l'archivio dell'aria non copre ancora {da} → {a}")
    if fonte not in f.fonti:
        raise HTTPException(404, f"fonte '{fonte}' assente nei dataset della finestra: disponibili {', '.join(f.fonti)}")
    recente = f.mesi[-1]
    virtuale = _modellata(recente, fonte)
    comune, distretto, cop_c, cop_d = _di_fonte(f, fonte)
    accorpata = fonte == FONTE_ACCORPATA
    celle_d = _celle(distretto, cop_d, "distretto", True, virtuale)
    celle_c = _celle(comune, cop_c, "comune", False, virtuale or accorpata)  # la vista accorpata non conta stazioni
    if accorpata:
        _note_accorpata(celle_d, celle_c, f.uso)
    dataset = {d["nome"]: d for r in f.mesi for d in r.meta["file"]}
    return RispostaAriaFinestra(
        da=date.fromisoformat(da), a=date.fromisoformat(a), giorni=len(giorni), giorni_coperti=f.giorni_coperti,
        fonte=fonte, fonte_modellata=virtuale, dataset=[FileDataset(**d) for d in dataset.values()],
        fonti=_info_fonti(recente, f.inquinanti, f.fonti), inquinanti=f.inquinanti,
        distretti=celle_d, comuni=celle_c, stazioni=_stazioni_mappa(recente), regole=REGOLE_AGGREGAZIONE)


def _celle_calore(zona: ZonaRif, giorni, mesi, per_distretto, per_comune):
    """{statistica: CellaMensile} della finestra per una fonte: `per_distretto` e `per_comune` sono i metodi
    dell'archivio che danno il DataFrame giornaliero di (statistica, mese), o None."""
    colonna = "distretto" if zona.tipo == "distretto" else "comune"
    celle = {}
    for stat in ("media", "massima", "minima"):
        metodo = per_distretto if zona.tipo == "distretto" else per_comune
        parti = [df for m in mesi if (df := metodo(stat, m)) is not None]
        if not parti:
            continue
        df = pd.concat(parti, ignore_index=True)
        f = per_finestra(df[df[colonna] == zona.id], giorni, funzione="media", chiavi=(), colonna_zona=colonna)
        if len(f):
            r = f.iloc[0]
            celle[stat] = CellaMensile(valore=_pulito(r.valore), stato=r.stato, nota=_pulito(r.nota), giorni=int(r.giorni),
                                       giorni_con_valore=int(r.giorni_con_valore))
    return celle


def _dettaglio_calore(zona: ZonaRif, giorni) -> DettaglioCalore:
    if not any(archivio_calore.mesi_in_cache().values()):
        return DettaglioCalore(stato="NON_INTEGRATO", motivo=MOTIVO_CALORE)
    mesi = sorted({g[:7] for g in giorni})
    celle = _celle_calore(zona, giorni, mesi, archivio_calore.distretto_giorno, archivio_calore.comune_giorno)
    if not celle:
        return DettaglioCalore(stato="NON_DISPONIBILE", fonte=FONTE_CALORE, unita=UNITA_CALORE,
                               motivo=f"temperatura ERA5-Land non in cache per {', '.join(mesi)}")
    arpa = {}
    if archivio_calore.arpa_disponibile():  # misurato, accanto al modellato: mai mediati fra loro
        arpa = {f"arpa_{k}": v for k, v in _celle_calore(zona, giorni, mesi, archivio_calore.arpa_distretto_giorno,
                                                          archivio_calore.arpa_comune_giorno).items()}
    return DettaglioCalore(stato="DISPONIBILE", fonte=FONTE_CALORE, unita=UNITA_CALORE,
                           arpa_fonte=FONTE_CALORE_ARPA if arpa else None, **celle, **arpa)


def _dettaglio_decessi(zona: ZonaRif, mesi) -> DettaglioDecessi:
    """Decessi dei mesi che la finestra tocca (la grana minima è distretto × mese): somma dei mesi con VALORE e media
    giornaliera su quei mesi, marcata come valore derivato. Per un comune sempre N/D (privacy, docs/Regole_dei_dati.md)."""
    base = dict(mesi=mesi, fonte=FONTE_DECESSI)
    if zona.tipo == "comune":
        return DettaglioDecessi(stato="NO_DATA", nota="N/D per comune: i numeri sono troppo piccoli e si pubblicano solo per "
                                                      "distretto e per mese, per la privacy", **base)
    dm, _ = archivio_decessi.distretto_mese()
    sel = None if dm is None else dm[(dm["distretto"] == zona.id) & (dm["mese"].isin(mesi))]
    if sel is None or sel.empty:
        return DettaglioDecessi(stato="NO_DATA", nota="mesi fuori dal periodo coperto dal file ISTAT", **base)
    validi = sel[sel["stato"] == "VALORE"]
    if validi.empty:
        stato = "NULL" if (sel["stato"] == "NULL").any() else "NO_DATA"
        return DettaglioDecessi(stato=stato, nota="nessun mese della finestra con un valore", **base)
    giorni = sum(monthrange(int(m[:4]), int(m[5:]))[1] for m in validi["mese"])
    totale = float(validi["valore"].sum())
    nota = (f"somma di {len(validi)} {'mese' if len(validi) == 1 else 'mesi'} su {len(mesi)} toccati dalla finestra"
            + ("" if len(validi) == len(mesi) else ": gli altri sono fuori dal periodo ISTAT o senza valore"))
    return DettaglioDecessi(stato="VALORE", valore=totale, media_giornaliera=totale / giorni, giorni=giorni,
                            mesi_con_valore=len(validi), nota=nota, **base)


def _provincia_di(zona: ZonaRif):
    """(id_provincia, denominazione) della provincia che contiene il distretto o il comune."""
    t = territorio()
    id_prov = t["distretti"][zona.id_distretto]["id_provincia"]
    return id_prov, next(p["denominazione"] for p in t["province"] if p["id_provincia"] == id_prov)


def _media_dimissioni(r, anno):
    """Dimissioni / giorni dell'anno (valore derivato, convenzione ~), None se la cella non ha un conteggio."""
    if r.stato != "VALORE" or r.dimissioni != r.dimissioni:
        return None
    return float(r.dimissioni) / dati_dimissioni.giorni_dell_anno(anno)


def _valore_dimissioni(r, anno) -> ValoreDimissioni:
    return ValoreDimissioni(
        gruppo=r.gruppo, etichetta=dati_dimissioni.ETICHETTE[r.gruppo], anno=anno, dimissioni=_pulito(r.dimissioni),
        tasso=_pulito(r.tasso), stato=r.stato, nota=_pulito(r.nota), media_giornaliera=_media_dimissioni(r, anno))


def _dettaglio_dimissioni(zona: ZonaRif, giorni) -> DettaglioDimissioni:
    """Dimissioni della provincia della zona: l'anno della finestra se coperto, altrimenti l'ultimo con un valore
    (dato annuale: la finestra non si applica). Valido anche per i comuni (sono migliaia di casi, nessuna privacy)."""
    id_prov, nome_prov = _provincia_di(zona)
    base = dict(provincia=id_prov, denominazione_provincia=nome_prov, fonte=dati_dimissioni.FONTE)
    df = archivio_dimissioni.tabella()
    if df is None:
        return DettaglioDimissioni(stato="NO_DATA", nota="dimissioni ISTAT non ancora scaricate", **base)
    _, ultimo = archivio_dimissioni.anni_con_valore()
    richiesto = int(giorni[-1][:4])
    anno = richiesto if richiesto <= ultimo else ultimo
    sel = df[(df["provincia"] == id_prov) & (df["anno"] == anno)]
    if sel.empty or (sel["stato"] != "VALORE").all():
        return DettaglioDimissioni(stato="NO_DATA", anno=anno, nota=f"provincia senza dati HFA per il {anno}", **base)
    nota = (f"dato annuale della provincia di {nome_prov}, anno {anno}" +
            ("" if anno == richiesto else f": la finestra è nel {richiesto}, ma l'ultimo anno pubblicato da HFA è il {anno}") +
            "; non riferito alla zona né alla finestra, non entra nelle correlazioni")
    return DettaglioDimissioni(stato="VALORE", anno=anno, nota=nota,
                               valori=[_valore_dimissioni(r, anno) for r in sel.itertuples()], **base)


def _salubrita_zona(z: ZonaRif, giorni) -> SalubritaZona | None:
    """Indice di salubrità della zona nella finestra: raccoglie i **valori giornalieri** (solo VALORE) per fonte e
    inquinante dai mesi toccati (al più due, finestra ≤ 31 giorni) e li confronta con i limiti di legge a parità di
    statistica (localhost/server/salubrita.py). None se non c'è nessun valore d'aria nella zona/finestra."""
    colonna = "distretto" if z.tipo == "distretto" else "comune"
    giorni_set = set(giorni)
    righe = []
    for m in sorted({g[:7] for g in giorni}):
        agg = cache_aria.mese(m)
        if agg is None:
            continue
        df = agg.distretto_giorno if z.tipo == "distretto" else agg.comune_giorno
        sel = df[(df[colonna] == z.id) & df["giorno"].isin(giorni_set) & (df["stato"] == "VALORE")
                 & (df["fonte"] != FONTE_ACCORPATA)]  # la vista accorpata non è una fonte: non si conta due volte
        if len(sel):
            righe.append(sel[["fonte", "inquinante", "valore"]])
    if not righe:
        return None
    tutte = pd.concat(righe, ignore_index=True)
    misure = {}
    for (fonte, inq), g in tutte.groupby(["fonte", "inquinante"]):
        valori = [float(v) for v in g["valore"].tolist() if v == v]
        if valori:
            misure.setdefault(inq, []).append({"fonte": fonte, "statistica": statistica(fonte, inq), "valori": valori})
    if not misure:
        return None
    return SalubritaZona(**salubrita.valuta_zona(misure))


def _uso_accorpata_zona(f: FinestraAria, z: ZonaRif) -> dict[str, list[UsoFonteAccorpata]]:
    """Per inquinante, quali fonti sono entrate nella vista «Tutte» della zona nella finestra (e quante volte scartate).
    Comune: giorni; distretto: comuni × giorni dei suoi comuni. La riga "*" del registro è la base (celle con valore)."""
    uso = f.uso
    if uso is None or uso.empty:
        return {}
    comuni = [z.id] if z.tipo == "comune" else _comuni_del_distretto(z.id)
    sel = uso[uso["comune"].isin(comuni)]
    out = {}
    for inq, g in sel.groupby("inquinante"):
        tot = g.groupby("fonte_usata")[["usata", "esclusa"]].sum()
        base = int(tot.loc["*", "usata"]) if "*" in tot.index else 0
        out[inq] = [UsoFonteAccorpata(fonte=fonte, usata=int(r.usata), scartata=int(r.esclusa), base=base)
                    for fonte, r in tot.iterrows() if fonte != "*"]
    return out


# ------------------------------------------------------------------------- salute simulata (25/10/2026)

MOTIVO_SIMULATI = "dati simulati non ancora generati"
SCENARIO = Query(dati_simulati.SCENARIO_PREDEFINITO, description="scenario dei dati simulati: nullo | letteratura")


def _residenti(comuni):
    t = territorio()
    return int(sum(t["comuni"][c]["residenti"] or 0 for c in comuni))


def _comuni_zona(z: ZonaRif):
    return [z.id] if z.tipo == "comune" else _comuni_del_distretto(z.id)


def _scenario_valido(scenario):
    if scenario not in dati_simulati.SCENARI:
        raise HTTPException(422, f"scenario '{scenario}' sconosciuto: {', '.join(dati_simulati.SCENARI)}")
    return scenario


def _info_simulati() -> InfoSimulati:
    p = archivio_simulato.parametri()
    if p is None:
        return InfoSimulati(disponibile=False, motivo=MOTIVO_SIMULATI, dicitura_breve=dati_simulati.DICITURA_BREVE)
    return InfoSimulati(
        disponibile=True, versione=p.get("versione"), generato_il=p.get("generato_il"), da=p["periodo"]["da"],
        a=p["periodo"]["a"], scenari=list(p["scenari"]), scenario_predefinito=dati_simulati.SCENARIO_PREDEFINITO,
        dicitura=p["dicitura"], dicitura_breve=dati_simulati.DICITURA_BREVE,
        indicatori=[IndicatoreSimulato(id=i, etichetta=e, breve=dati_simulati.BREVI.get(i, e),
                                       unita=dati_simulati.UNITA.get(i, "per 100.000 residenti al giorno"))
                    for i, e in p["indicatori"].items()])


def _dettaglio_simulati(comuni, giorni, scenario) -> DettaglioSimulati:
    """Ricoveri, PS e ADI simulati dei comuni (somma) nella finestra: totale, al giorno, per 100.000 al giorno."""
    base = dict(scenario=scenario, giorni_finestra=len(giorni), dicitura_breve=dati_simulati.DICITURA_BREVE)
    if not archivio_simulato.disponibile():
        return DettaglioSimulati(stato="NO_DATA", nota=MOTIVO_SIMULATI, **base)
    da_s, a_s = archivio_simulato.periodo()
    righe = archivio_simulato.righe(comuni, scenario, giorni=giorni)
    residenti = _residenti(comuni)
    if righe is None or righe.empty:
        return DettaglioSimulati(stato="NO_DATA", residenti=residenti,
                                 nota=f"finestra fuori dal periodo simulato ({da_s} → {a_s})", **base)
    indicatori = archivio_simulato.indicatori()
    r = dati_simulati.riassunto_finestra(righe, indicatori, residenti)
    valori = [ValoreSimulato(indicatore=i, etichetta=dati_simulati.BREVI.get(i, i), **r[i]) for i in indicatori]
    accessi = r.get("adi_accessi_ps", {}).get("totale")

    def quota(k):
        tot = r.get(k, {}).get("totale")
        return tot / accessi if accessi and tot is not None else None

    giorni_dato = int(righe["data"].nunique())
    nota = f"simulato, scenario {scenario}" + (f"; somma di {len(comuni)} comuni" if len(comuni) > 1 else "")
    if giorni_dato < len(giorni):
        nota += f"; {giorni_dato} giorni su {len(giorni)}: gli altri sono fuori dal periodo simulato ({da_s} → {a_s})"
    return DettaglioSimulati(stato="VALORE", residenti=residenti, giorni=giorni_dato, valori=valori,
                             quota_bassa_urgenza=quota("adi_accessi_bassa_urgenza"), quota_ritorni=quota("adi_ritorni_30g"),
                             nota=nota, **base)


@app.get("/api/salute/simulati/finestra", response_model=DettaglioSimulati,
         summary="Ricoveri, PS e ADI simulati di una zona (o del Salento) in una finestra di giorni")
def salute_simulati_finestra(zona: str = Query(dati_stagionalita.ZONA_SALENTO, description="SALENTO, un id_distretto o un id_comune"),
                             da: str = Query(pattern=GIORNO), a: str = Query(pattern=GIORNO), scenario: str = SCENARIO):
    """Per i numeri di testa della dashboard (Salento) e per qualunque zona. **Dato simulato, non reale.**"""
    _scenario_valido(scenario)
    giorni = _giorni_finestra(da, a)
    comuni = sorted(territorio()["comuni"]) if zona == dati_stagionalita.ZONA_SALENTO else _comuni_zona(_zona_rif(zona))
    return _dettaglio_simulati(comuni, giorni, scenario)


#: parti degli eventi sanitari della vista «Salute» (29/10/2026): i PS respiratori e cardiovascolari e quelli degli
#: assistiti ADI sono già dentro gli accessi in PS totali, quindi non si sommano
EVENTI_SIMULATI = {"ricoveri": ("ricoveri_respiratori", "ricoveri_circolatori"), "ps": ("ps_accessi",)}


def _virgola(v):
    return f"{v:.1f}".replace(".", ",")


@app.get("/api/salute/mappa", response_model=RispostaSaluteMappa,
         summary="Eventi sanitari (decessi + ricoveri + accessi in PS) di tutte le zone nella finestra (vista «Salute» della mappa)")
def salute_mappa(da: str = Query(pattern=GIORNO, description="primo giorno della finestra"),
                 a: str = Query(pattern=GIORNO, description="ultimo giorno della finestra"), scenario: str = SCENARIO):
    """Per ogni distretto: decessi + ricoveri (respiratori e circolatori) + accessi in PS, per 100.000 residenti al
    giorno; ogni evento conta 1, nessun peso (scelta di Matteo del 29/10/2026). I decessi sono quelli ISTAT dei mesi
    toccati dalla finestra (grana minima distretto × mese), ricoveri e PS i simulati dei giorni della finestra: il
    valore è **simulato, non reale**. Se manca una delle tre parti il distretto è N/D col motivo, perché una somma
    parziale cambierebbe significato. Ogni comune prende il valore del suo distretto (decessi per comune: privacy, §7).
    Scala relativa min-max fra le zone, come le altre viste della mappa."""
    _scenario_valido(scenario)
    giorni = _giorni_finestra(da, a)
    mesi = sorted({g[:7] for g in giorni})
    t = territorio()
    righe = archivio_simulato.righe(list(t["comuni"]), scenario, giorni=giorni) if archivio_simulato.disponibile() else None
    da_s, a_s = archivio_simulato.periodo()
    indicatori = [i for gruppo in EVENTI_SIMULATI.values() for i in gruppo]
    distretti, componenti = {}, {}
    for id_d in sorted(t["distretti"]):
        comuni = _comuni_del_distretto(id_d)
        residenti = _residenti(comuni)
        dec = _dettaglio_decessi(_zona_rif(id_d), mesi)
        parti = ComponentiEventi(decessi=dec.media_giornaliera / residenti * dati_simulati.PER
                                 if dec.stato == "VALORE" and dec.media_giornaliera is not None and residenti else None)
        sel = None if righe is None else righe[righe["id_comune"].isin(comuni)]
        giorni_dato = 0 if sel is None else int(sel["data"].nunique())
        if giorni_dato:
            r = dati_simulati.riassunto_finestra(sel, indicatori, residenti)
            for parte, gruppo in EVENTI_SIMULATI.items():
                valori = [r[i]["per_100k"] for i in gruppo]
                setattr(parti, parte, sum(valori) if all(v is not None for v in valori) else None)
        motivi = []
        if parti.decessi is None:
            motivi.append(f"decessi: {dec.nota or 'non disponibili'}")
        if parti.ricoveri is None or parti.ps is None:
            motivi.append(MOTIVO_SIMULATI if righe is None else f"ricoveri e PS: finestra fuori dal periodo simulato ({da_s} → {a_s})")
        if motivi:
            cella = CellaMensile(valore=None, stato="NO_DATA", nota="; ".join(motivi), giorni=len(giorni), giorni_con_valore=0)
        else:
            nota = (f"decessi {_virgola(parti.decessi)} + ricoveri {_virgola(parti.ricoveri)} + PS {_virgola(parti.ps)}; "
                    f"ricoveri e PS simulati, scenario {scenario}")
            cella = CellaMensile(valore=parti.decessi + parti.ricoveri + parti.ps, stato="VALORE", nota=nota,
                                 giorni=len(giorni), giorni_con_valore=giorni_dato)
        distretti[id_d], componenti[id_d] = cella, parti
    comuni = {
        id_c: distretti[c["id_distretto"]].model_copy(update={"nota": (
            f"valore del distretto (i decessi per comune non si mostrano, privacy); {distretti[c['id_distretto']].nota}")})
        for id_c, c in t["comuni"].items() if c["id_distretto"] in distretti
    }
    return RispostaSaluteMappa(da=date.fromisoformat(da), a=date.fromisoformat(a), giorni=len(giorni), scenario=scenario,
                               dicitura_breve=dati_simulati.DICITURA_BREVE, distretti=distretti, comuni=comuni,
                               componenti=componenti)


def _punti_simulati(comuni, mesi, indicatore, residenti):
    """[PuntoSimulato] mese per mese, i due scenari insieme, per 100.000 residenti al giorno."""
    per_scenario = {sc: dati_simulati.mensile(archivio_simulato.righe(comuni, sc, mesi=mesi), indicatore)
                    for sc in dati_simulati.SCENARI}
    stock = indicatore in dati_simulati.STOCK
    punti = []
    for m in mesi:
        valori, giorni = {}, 0
        for sc, mensili in per_scenario.items():
            if m in mensili:
                tot, giorni = mensili[m]
                valori[sc] = (tot / residenti * dati_simulati.PER if stock and residenti
                              else dati_simulati.per_100k_giorno(tot, residenti, giorni))
        n, l = valori.get("nullo"), valori.get("letteratura")
        punti.append(PuntoSimulato(mese=m, giorni=giorni, nullo=n, letteratura=l,
                                   differenza_percentuale=(l - n) / n if n and l is not None else None))
    return punti


@app.get("/api/salute/simulati/serie", response_model=RispostaSerieSimulata,
         summary="Un indicatore simulato mese per mese, entrambi gli scenari, fino a 4 zone (comuni ammessi)")
def salute_simulati_serie(zone: str = Query(..., description="id di distretti o comuni, separati da virgola, al più 4"),
                          da: str = Query(pattern=MESE), a: str = Query(pattern=MESE),
                          indicatore: str = Query("ps_accessi")):
    """Il grafico del confronto sovrappone i due scenari: linea piena per quello scelto, tratteggiata per l'altro.
    La distanza fra le linee è l'effetto di aria e caldo **imposto** nello scenario «letteratura». Dato simulato."""
    p = archivio_simulato.parametri()
    if p is None:
        raise HTTPException(404, MOTIVO_SIMULATI)
    if indicatore not in p["indicatori"]:
        raise HTTPException(404, f"indicatore '{indicatore}' sconosciuto: {', '.join(p['indicatori'])}")
    mesi = _periodo(da, a)
    ids = [x.strip() for x in zone.split(",") if x.strip()]
    if not ids or len(ids) > MAX_ZONE:
        raise HTTPException(422, f"da 1 a {MAX_ZONE} zone")
    serie = []
    for id_zona in ids:
        z = _zona_rif(id_zona)
        comuni = _comuni_zona(z)
        res = _residenti(comuni)
        serie.append(SerieSimulata(zona=z, residenti=res, punti=_punti_simulati(comuni, mesi, indicatore, res)))
    unita = "per 100.000 residenti" if indicatore in dati_simulati.STOCK else dati_simulati.UNITA[indicatore]
    return RispostaSerieSimulata(da=da, a=a, indicatore=indicatore, etichetta=dati_simulati.BREVI.get(indicatore, indicatore),
                                 unita=unita, serie=serie, dicitura=p["dicitura"], dicitura_breve=dati_simulati.DICITURA_BREVE)


@app.get("/api/zona/dettaglio", response_model=RispostaDettaglioZona,
         summary="Aria (ogni fonte), decessi, ricoveri, simulati e calore di una zona in una finestra di giorni")
def zona_dettaglio(zona: str = Query(..., description="id_distretto (es. LE-51) o id_comune ISTAT"),
                   da: str = Query(pattern=GIORNO, description="primo giorno della finestra"),
                   a: str = Query(pattern=GIORNO, description="ultimo giorno della finestra"),
                   scenario: str = SCENARIO):
    """Il pannello di dettaglio mostra, per la zona cliccata, tutti i domini nella **stessa finestra** della mappa.
    Aria: un valore per inquinante e per fonte (mai mediato fra fonti). Decessi: distretto × mese, sui mesi che la
    finestra tocca, con la media giornaliera come valore derivato; per un comune sempre N/D (privacy).
    Calore: media/massima/minima ERA5-Land della finestra, se in cache. Le malattie non ci sono più (03/11/2026, scelta di
    Matteo): nessuna fonte pubblica a grana fine e nessun dato atteso da altri."""
    _scenario_valido(scenario)
    z = _zona_rif(zona)
    giorni = _giorni_finestra(da, a)
    mesi = sorted({g[:7] for g in giorni})
    f = aggregati_periodo(cache_aria, giorni)
    aria, inquinanti, coperti, motivo = [], [], 0, None
    if f is not None:
        coperti, inquinanti = f.giorni_coperti, f.inquinanti
        recente = f.mesi[-1]
        colonna = "distretto" if z.tipo == "distretto" else "comune"
        for fonte in f.fonti:
            comune, distretto, cop_c, cop_d = _di_fonte(f, fonte)
            virtuale = _modellata(recente, fonte)
            celle = (_celle(distretto, cop_d, colonna, True, virtuale, z.id) if z.tipo == "distretto"
                     else _celle(comune, cop_c, colonna, False, virtuale, z.id)).get(z.id, {})
            aria.append(DettaglioFonteAria(fonte=fonte, modellata=virtuale, licenza=LICENZE.get(fonte, "non dichiarata"),
                                           celle=celle, statistiche={i: statistica(fonte, i) for i in inquinanti}))
    else:
        motivo = f"l'archivio dell'aria non copre ancora {da} → {a}"
    sal = _salubrita_zona(z, giorni) if f is not None else None
    return RispostaDettaglioZona(
        fonti_accorpata=_uso_accorpata_zona(f, z) if f is not None else {},
        zona=z, da=date.fromisoformat(da), a=date.fromisoformat(a), giorni=len(giorni), giorni_coperti=coperti,
        inquinanti=inquinanti, aria=aria, aria_motivo=motivo, salubrita=sal, salute=_dettaglio_decessi(z, mesi),
        dimissioni=_dettaglio_dimissioni(z, giorni),
        simulati=_dettaglio_simulati(_comuni_zona(z), giorni, scenario),
        calore=_dettaglio_calore(z, giorni))


@app.get("/api/riepilogo", response_model=RispostaRiepilogo,
         summary="Tutti i dati per distretto nella finestra: territorio, aria, salubrità, salute, calore")
def riepilogo(da: str = Query(pattern=GIORNO, description="primo giorno della finestra"),
              a: str = Query(pattern=GIORNO, description="ultimo giorno della finestra"),
              fonte: str = Query("ARPA", description="fonte delle colonne dell'aria (o «Tutte»)"),
              scenario: str = SCENARIO):
    """La tabella del tab Riepilogo (14/10/2026): una riga per distretto, una colonna per dato, raggruppate per dominio.
    È **generica**: un dato nuovo (isole di calore...) si aggiunge come colonna qui.
    Stesse regole di sempre: aria = media della finestra (distretto pesato sui residenti), decessi = somma dei mesi
    toccati (privacy: distretto × mese), temperatura = media della finestra ERA5-Land (modellata)."""
    _scenario_valido(scenario)
    giorni = _giorni_finestra(da, a)
    mesi = sorted({g[:7] for g in giorni})
    t = territorio()
    fisiche = stazioni_fisiche_per_comune()
    colonne, celle = [], {d: {} for d in t["distretti"]}

    def colonna(**k):
        colonne.append(ColonnaRiepilogo(**k))

    # --- territorio
    colonna(id="residenti", gruppo="Territorio", etichetta="Residenti", formato="intero")
    colonna(id="comuni", gruppo="Territorio", etichetta="Comuni", formato="intero")
    colonna(id="stazioni", gruppo="Territorio", etichetta="Stazioni", formato="intero",
            nota="stazioni fisiche dell'aria di qualunque fonte; 0 = l'unico dato aria è CAMS, modellato")
    staz_distretto = {}
    for d in t["distretti"]:
        comuni = [c for c in t["comuni"].values() if c["id_distretto"] == d]
        n_staz = staz_distretto[d] = sum(fisiche.get(c["id_comune"], 0) for c in comuni)
        celle[d]["residenti"] = CellaRiepilogo(valore=sum(c["residenti"] or 0 for c in comuni), stato="VALORE")
        celle[d]["comuni"] = CellaRiepilogo(valore=len(comuni), stato="VALORE")
        celle[d]["stazioni"] = CellaRiepilogo(valore=n_staz, stato="VALORE",
                                              nota=NOTA_DISTRETTO_SENZA_STAZIONI if n_staz == 0 else None)

    # --- aria: i cinque inquinanti di riferimento, per la fonte scelta
    _, _, tab_inq = leggi_anagrafica(FILE_ANAGRAFICHE["inquinanti"])
    riferimento = [r for r in tab_inq["inquinanti"] if r.get("riferimento_dashboard")]
    f = aggregati_periodo(cache_aria, giorni, fonte)
    modellata = bool(f) and _modellata(f.mesi[-1], fonte)
    gruppo_aria = "Aria, tutte le fonti" if fonte == FONTE_ACCORPATA else f"Aria da {fonte}"
    for r in riferimento:
        colonna(id=f"aria:{r['id_inquinante']}", gruppo=gruppo_aria, etichetta=r["id_inquinante"], unita=r.get("unita_misura"),
                modellata=modellata, nota=f"media della finestra, {fonte}; distretto = media pesata sui residenti dei comuni con valore")
    if f is not None and fonte in f.fonti:
        dist = f.distretto[f.distretto["fonte"] == fonte]
        for x in dist.itertuples():
            if x.distretto in celle:
                celle[x.distretto][f"aria:{x.inquinante}"] = CellaRiepilogo(valore=_pulito(x.valore), stato=x.stato, nota=_pulito(x.nota))

    # --- salubrità (rispetto ai limiti di legge, tutte le fonti, peggiore inquinante): non segue la fonte scelta,
    # quindi il gruppo lo dice (fase 6, 29/10/2026); nei distretti senza stazioni fisiche la banda viene dal solo CAMS
    colonna(id="salubrita", gruppo="Salubrità, tutte le fonti", etichetta="Banda", formato="banda",
            nota="rispetto al D.Lgs. 155/2010, solo a parità di statistica; indice di zona = peggiore inquinante")
    colonna(id="salubrita_peggiore", gruppo="Salubrità, tutte le fonti", etichetta="Peggiore", formato="testo")
    try:
        bande = aria_salubrita(da=da, a=a).distretti
    except HTTPException:
        bande = {}
    for d, b in bande.items():
        if d in celle:
            solo_cams = staz_distretto.get(d) == 0
            nota = "nel distretto non ci sono stazioni fisiche: banda dal solo CAMS, modellato" if solo_cams else None
            celle[d]["salubrita"] = CellaRiepilogo(testo=b.banda, stato="VALORE", nota=nota, modellata=solo_cams)
            # il cubo una volta sola per riga, sulla banda; il peggiore ripete solo la nota
            celle[d]["salubrita_peggiore"] = CellaRiepilogo(testo=b.inquinante_peggiore, stato="VALORE" if b.inquinante_peggiore else "NO_DATA",
                                                            nota=nota)

    # --- salute
    colonna(id="decessi", gruppo="Salute", etichetta="Decessi", formato="intero",
            nota="somma dei mesi toccati dalla finestra, tutte le cause (ISTAT, provvisori): la grana minima è distretto × mese")
    colonna(id="decessi_giorno", gruppo="Salute", etichetta="~/giorno", formato="decimale",
            nota="decessi / giorni dei mesi con valore: valore derivato, solo per leggerlo (convenzione ~)")
    # dimissioni in un gruppo a sé che dice la grana: è il dato della provincia, uguale per i distretti della stessa
    # provincia (fase 6, 29/10/2026)
    gruppi_riepilogo = {"respiratorio": "Respiratori", "circolatorio": "Circolatori"}
    for g, etichetta in gruppi_riepilogo.items():
        colonna(id=f"dimissioni:{g}", gruppo="Ricoveri della provincia", etichetta=etichetta, unita="all'anno", formato="intero",
                nota=f"dimissioni ospedaliere per {dati_dimissioni.ETICHETTE[g].lower()}: dato annuale della provincia del distretto "
                     "(ISTAT HFA), l'anno della finestra o l'ultimo pubblicato; solo informativo, non correlato")
    for d in t["distretti"]:
        dd = _dettaglio_decessi(_zona_rif(d), mesi)
        celle[d]["decessi"] = CellaRiepilogo(valore=dd.valore, stato=dd.stato, nota=dd.nota)
        celle[d]["decessi_giorno"] = CellaRiepilogo(valore=dd.media_giornaliera, stato=dd.stato, nota=dd.nota)
        di = _dettaglio_dimissioni(_zona_rif(d), giorni)
        for g in gruppi_riepilogo:
            v = next((x for x in di.valori if x.gruppo == g), None)
            celle[d][f"dimissioni:{g}"] = (CellaRiepilogo(valore=v.dimissioni, stato=v.stato, nota=di.nota) if v
                                           else CellaRiepilogo(stato=di.stato, nota=di.nota))

    # --- salute simulata: ricoveri, PS e ADI per 100.000 residenti al giorno (dato simulato, non reale)
    gruppo_sim = f"Salute simulata, scenario {scenario}"
    nota_sim = f"{dati_simulati.DICITURA_BREVE}: per 100.000 residenti al giorno nella finestra, distretto = somma dei comuni"
    colonne_sim = {"ricoveri_respiratori": "Ric. resp.", "ricoveri_circolatori": "Ric. circ.", "ps_accessi": "PS",
                   "ps_respiratori": "PS resp.", "adi_accessi_ps": "PS ADI"}
    for ind, etichetta in colonne_sim.items():
        colonna(id=f"sim:{ind}", gruppo=gruppo_sim, etichetta=etichetta, unita="/100.000/g", simulata=True,
                nota=f"{dati_simulati.BREVI[ind]}. {nota_sim}")
    colonna(id="sim:adi_bassa_urgenza", gruppo=gruppo_sim, etichetta="ADI bassa urg.", formato="percentuale", simulata=True,
            nota=f"quota degli accessi in PS degli assistiti ADI a bassa urgenza (gestibili a domicilio). {dati_simulati.DICITURA_BREVE}")
    colonna(id="sim:adi_ritorni", gruppo=gruppo_sim, etichetta="ADI ritorni", formato="percentuale", simulata=True,
            nota=f"quota degli accessi ADI di chi era già passato dal PS nei 30 giorni prima. {dati_simulati.DICITURA_BREVE}")
    for d in t["distretti"]:
        ds = _dettaglio_simulati(_comuni_del_distretto(d), giorni, scenario)
        per_ind = {v.indicatore: v for v in ds.valori}
        for ind in colonne_sim:
            v = per_ind.get(ind)
            nota = f"{v.totale:.0f} nella finestra; {ds.nota}" if v and v.totale is not None else ds.nota
            celle[d][f"sim:{ind}"] = CellaRiepilogo(valore=v.per_100k if v else None, stato=ds.stato if v else "NO_DATA", nota=nota)
        for col, q in (("sim:adi_bassa_urgenza", ds.quota_bassa_urgenza), ("sim:adi_ritorni", ds.quota_ritorni)):
            celle[d][col] = CellaRiepilogo(valore=q, stato="VALORE" if q is not None else "NO_DATA", nota=ds.nota)

    # --- calore: temperatura ERA5-Land della finestra (modellata)
    for stat, etichetta in (("media", "T media"), ("massima", "T max"), ("minima", "T min")):
        colonna(id=f"calore:{stat}", gruppo="Calore", etichetta=etichetta, unita=UNITA_CALORE, modellata=True,
                nota=f"temperatura {stat} giornaliera a 2 m, media della finestra ({FONTE_CALORE}, rianalisi: modellata)")
        parti = [df for m in mesi if (df := archivio_calore.distretto_giorno(stat, m)) is not None]
        if not parti:
            for d in celle:
                celle[d][f"calore:{stat}"] = CellaRiepilogo(stato="NO_DATA", nota=f"ERA5-Land non in cache per {', '.join(mesi)}")
            continue
        fin = per_finestra(pd.concat(parti, ignore_index=True), giorni, funzione="media", chiavi=(), colonna_zona="distretto")
        for x in fin.itertuples():
            if x.distretto in celle:
                celle[x.distretto][f"calore:{stat}"] = CellaRiepilogo(valore=_pulito(x.valore), stato=x.stato, nota=_pulito(x.nota))

    righe = [RigaRiepilogo(id_distretto=d, denominazione=v["denominazione"], celle=celle[d])
             for d, v in sorted(t["distretti"].items())]
    return RispostaRiepilogo(da=date.fromisoformat(da), a=date.fromisoformat(a), giorni=len(giorni), fonte=fonte,
                             colonne=colonne, righe=righe)


def _bande_zone(parti, colonna):
    """{id_zona: SalubritaZonaMappa} da uno o più frame (comune|distretto, fonte, inquinante, valore) di soli VALORE,
    uniti su tutti i mesi della finestra (così una zona di un window a cavallo di due mesi usa tutti i suoi giorni)."""
    if not parti:
        return {}
    tutte = pd.concat(parti, ignore_index=True)
    out = {}
    for zona, gz in tutte.groupby(colonna):
        misure = {}
        for (fonte, inq), g in gz.groupby(["fonte", "inquinante"]):
            valori = [float(v) for v in g["valore"].tolist() if v == v]
            if valori:
                misure.setdefault(inq, []).append({"fonte": fonte, "statistica": statistica(fonte, inq), "valori": valori})
        if misure:
            r = salubrita.valuta_zona(misure)
            out[zona] = SalubritaZonaMappa(banda=r["banda"], inquinante_peggiore=r["inquinante_peggiore"])
    return out


@app.get("/api/aria/salubrita", response_model=RispostaSalubritaMappa,
         summary="Banda di salubrità di tutte le zone della finestra (modalità «salubrità» della mappa)")
def aria_salubrita(da: str = Query(pattern=GIORNO, description="primo giorno della finestra"),
                   a: str = Query(pattern=GIORNO, description="ultimo giorno della finestra")):
    """Per ogni distretto e comune, la banda di salubrità (rispetto al D.Lgs. 155/2010 in vigore, peggiore inquinante)
    nella stessa finestra della mappa. Alimenta l'interruttore «valore»/«salubrità»: a differenza della scala di
    colore «valore» (relativa min-max), qui il colore dice il rapporto coi limiti di legge."""
    giorni = _giorni_finestra(da, a)
    giorni_set = set(giorni)
    parti = {"comune": [], "distretto": []}
    coperti = set()
    trovato = False
    for m in sorted({g[:7] for g in giorni}):
        agg = cache_aria.mese(m)
        if agg is None:
            continue
        trovato = True
        coperti |= set(agg.comune_giorno["giorno"].unique()) & giorni_set
        for colonna, df in (("comune", agg.comune_giorno), ("distretto", agg.distretto_giorno)):
            sel = df[df["giorno"].isin(giorni_set) & (df["stato"] == "VALORE") & (df["fonte"] != FONTE_ACCORPATA)]
            if len(sel):
                parti[colonna].append(sel[[colonna, "fonte", "inquinante", "valore"]])
    if not trovato:
        raise HTTPException(404, f"l'archivio dell'aria non copre ancora {da} → {a}")
    return RispostaSalubritaMappa(da=date.fromisoformat(da), a=date.fromisoformat(a), giorni=len(giorni),
                                  giorni_coperti=len(coperti), distretti=_bande_zone(parti["distretto"], "distretto"),
                                  comuni=_bande_zone(parti["comune"], "comune"))


def _punti_giorno(df, giorni):
    per_giorno = {r.giorno: r for r in df.itertuples()}
    punti = []
    for g in giorni:
        r = per_giorno.get(g)
        if r is None:
            punti.append(PuntoGiorno(giorno=g, valore=None, stato="NO_DATA", nota="giorno non coperto dal dataset"))
        else:
            punti.append(PuntoGiorno(giorno=g, valore=_pulito(r.valore), stato=r.stato, nota=_pulito(r.nota)))
    return punti


def _giorni_del_mese(mese):
    anno, num = int(mese[:4]), int(mese[5:])
    return [f"{anno:04d}-{num:02d}-{g:02d}" for g in range(1, monthrange(anno, num)[1] + 1)]


def _giorni(agg):
    return _giorni_del_mese(agg.mese)


def _serie_zona(agg, zona: ZonaRif, fonte, inquinante):
    if zona.tipo == "distretto":
        df = agg.distretto_giorno
        df = df[(df["distretto"] == zona.id) & (df["fonte"] == fonte) & (df["inquinante"] == inquinante)]
    else:
        df = agg.comune_giorno
        df = df[(df["comune"] == zona.id) & (df["fonte"] == fonte) & (df["inquinante"] == inquinante)]
    return _punti_giorno(df, _giorni(agg))


@app.get("/api/aria/serie", response_model=RispostaSerieAria, summary="Serie giornaliera di fino a 3 zone, una fonte")
def aria_serie(mese: str = Query(pattern=MESE), inquinante: str = Query(...), fonte: str = Query("ARPA"),
               zone: str = Query(..., description="id di distretti o comuni separati da virgola, al più 3")):
    ids = [z.strip() for z in zone.split(",") if z.strip()]
    if not ids or len(ids) > MAX_ZONE:
        raise HTTPException(422, f"indicare da 1 a {MAX_ZONE} zone")
    agg = _aggregati(mese)
    _controlla_fonte(agg, fonte)
    serie = [SerieZona(zona=(z := _zona_rif(i)), punti=_serie_zona(agg, z, fonte, inquinante)) for i in ids]
    return RispostaSerieAria(mese=mese, inquinante=inquinante, unita=agg.meta["inquinanti"].get(inquinante), fonte=fonte,
                             fonte_modellata=_modellata(agg, fonte), statistica=statistica(fonte, inquinante), serie=serie)


@app.get("/api/calore/disponibilita", response_model=RispostaDisponibilitaCalore,
         summary="Mesi di temperatura ERA5-Land già scaricati")
def calore_disponibilita():
    return RispostaDisponibilitaCalore(
        fonte=FONTE_CALORE, licenza=LICENZA_CALORE, mesi=archivio_calore.mesi_in_cache(),
        come_scaricare="uv run --env-file .env scripts/calore/scarica_era5_land.py --da AAAA-MM --a AAAA-MM")


def _serie_calore(zona: ZonaRif, statistica, mese, fonte="era5"):
    arpa = fonte == "arpa"
    dist, com = ((archivio_calore.arpa_distretto_giorno, archivio_calore.arpa_comune_giorno) if arpa
                 else (archivio_calore.distretto_giorno, archivio_calore.comune_giorno))
    df = dist(statistica, mese) if zona.tipo == "distretto" else com(statistica, mese)
    if df is None:
        raise HTTPException(404, (f"temperatura ARPA meteo del {mese[:4]} non ancora scaricata in locale"
                                  if arpa else f"temperatura {statistica} ERA5-Land di {mese} non ancora scaricata in locale"))
    df = df[df["distretto" if zona.tipo == "distretto" else "comune"] == zona.id]
    return _punti_giorno(df, _giorni_del_mese(mese))


@app.get("/api/calore/serie", response_model=RispostaSerieCalore,
         summary="Temperatura giornaliera di fino a 3 zone, un mese (ERA5-Land o ARPA meteo)")
def calore_serie(mese: str = Query(pattern=MESE), zone: str = Query(..., description="id di distretti o comuni, al più 3"),
                 statistica: Literal["media", "massima", "minima"] = Query("media"),
                 fonte: Literal["era5", "arpa"] = Query("era5", description="era5 = ERA5-Land (modellato, tutti i comuni); "
                                                         "arpa = stazioni misurate (solo i comuni con una stazione)")):
    """ERA5-Land — comune: media pesata sull'area delle celle 0,1°; distretto: media pesata sui residenti. Dato
    modellato (rianalisi). ARPA meteo — comune: media delle stazioni fisiche; distretto: media pesata sui residenti
    **dei soli comuni con una stazione** (la nota di ogni punto dice su quanti e su quale quota di residenti).
    Le due fonti non si mediano mai fra loro."""
    ids = [z.strip() for z in zone.split(",") if z.strip()]
    if not ids or len(ids) > MAX_ZONE:
        raise HTTPException(422, f"indicare da 1 a {MAX_ZONE} zone")
    serie = [SerieZona(zona=(z := _zona_rif(i)), punti=_serie_calore(z, statistica, mese, fonte)) for i in ids]
    arpa = fonte == "arpa"
    return RispostaSerieCalore(mese=mese, statistica=statistica, unita=UNITA_CALORE,
                               fonte=FONTE_CALORE_ARPA if arpa else FONTE_CALORE,
                               licenza=LICENZA_CALORE_ARPA if arpa else LICENZA_CALORE, fonte_modellata=not arpa, serie=serie)


def _celle_calore_tutte(giorni, mesi, statistica, per_zona, colonna):
    """{id_zona: CellaMensile} della finestra per tutte le zone di un livello (per_zona = metodo dell'archivio)."""
    parti = [df for m in mesi if (df := per_zona(statistica, m)) is not None]
    if not parti:
        return {}
    f = per_finestra(pd.concat(parti, ignore_index=True), giorni, funzione="media", chiavi=(), colonna_zona=colonna)
    return {getattr(r, colonna): CellaMensile(valore=_pulito(r.valore), stato=r.stato, nota=_pulito(r.nota), giorni=int(r.giorni),
                                              giorni_con_valore=int(r.giorni_con_valore))
            for r in f.itertuples()}


@app.get("/api/calore/mappa", response_model=RispostaCaloreMappa,
         summary="Temperatura di tutte le zone nella finestra (modalità «temperatura» della mappa)")
def calore_mappa(da: str = Query(pattern=GIORNO, description="primo giorno della finestra"),
                 a: str = Query(pattern=GIORNO, description="ultimo giorno della finestra"),
                 statistica: Literal["media", "massima", "minima"] = Query("media")):
    """Per ogni distretto e comune, la media nella finestra della temperatura giornaliera ERA5-Land (dato modellato:
    media pesata sull'area per il comune, sui residenti per il distretto). Nessuna scala di legge: il colore sulla
    mappa è relativo al minimo e al massimo della finestra, come per l'aria."""
    giorni = _giorni_finestra(da, a)
    mesi = sorted({g[:7] for g in giorni})
    comuni = _celle_calore_tutte(giorni, mesi, statistica, archivio_calore.comune_giorno, "comune")
    if not comuni:
        raise HTTPException(404, f"temperatura ERA5-Land non ancora scaricata in locale per {', '.join(mesi)}")
    distretti = _celle_calore_tutte(giorni, mesi, statistica, archivio_calore.distretto_giorno, "distretto")
    return RispostaCaloreMappa(da=date.fromisoformat(da), a=date.fromisoformat(a), giorni=len(giorni), statistica=statistica,
                               unita=UNITA_CALORE, fonte=FONTE_CALORE, distretti=distretti, comuni=comuni)


@app.get("/api/aria/fonti", response_model=RispostaFontiAria, summary="Ogni fonte nella stessa zona, con la concordanza")
def aria_fonti(mese: str = Query(pattern=MESE), inquinante: str = Query(...), zona: str = Query(...)):
    agg = _aggregati(mese)
    z = _zona_rif(zona)
    comuni_zona = [z.id] if z.tipo == "comune" else _comuni_del_distretto(z.id)
    serie = [SerieFonte(fonte=f, modellata=_modellata(agg, f), statistica=statistica(f, inquinante),
                        punti=_serie_zona(agg, z, f, inquinante))
             for f in sorted(set(agg.comune_giorno["fonte"].unique()) - {FONTE_ACCORPATA})]  # solo fonti vere
    confronti = [ConfrontoFonti(**c) for c in confronti_fonti(agg, inquinante, comuni_zona)]
    return RispostaFontiAria(mese=mese, inquinante=inquinante, unita=agg.meta["inquinanti"].get(inquinante), zona=z,
                             serie=serie, confronti=confronti, soglia_concordanza=SOGLIA_CONCORDANZA)


FONTI_CALORE = (("era5", "ERA5-Land", True), ("arpa", "ARPA meteo", False))


@app.get("/api/calore/fonti", response_model=RispostaFontiCalore,
         summary="Temperatura secondo ERA5-Land e ARPA meteo nella stessa zona, con la concordanza")
def calore_fonti(mese: str = Query(pattern=MESE), zona: str = Query(...),
                 statistica: Literal["media", "massima", "minima"] = Query("media")):
    """Le due serie della zona come in /api/calore/serie (mai mediate fra loro) e il confronto sulle sole coppie
    comune × giorno con un VALORE in entrambe: nei distretti ARPA copre solo i comuni con una stazione, quindi la
    concordanza si misura sugli stessi comuni (scelta del 27/10/2026). Segno: ERA5-Land − ARPA."""
    z = _zona_rif(zona)
    comuni = [z.id] if z.tipo == "comune" else _comuni_del_distretto(z.id)
    giorni = _giorni_del_mese(mese)
    serie = []
    for fonte, nome, modellata in FONTI_CALORE:
        try:
            p = _serie_calore(z, statistica, mese, fonte)
        except HTTPException as exc:  # mese non in cache: la serie resta, tutta NO_DATA col motivo
            p = [PuntoGiorno(giorno=g, valore=None, stato="NO_DATA", nota=exc.detail) for g in giorni]
        serie.append(SerieFonte(fonte=nome, modellata=modellata, statistica=f"{statistica} giornaliera", punti=p))

    era, arpa = archivio_calore.comune_giorno(statistica, mese), archivio_calore.arpa_comune_giorno(statistica, mese)
    nomi = {c: territorio()["comuni"][c]["denominazione"] for c in comuni}
    base = dict(fonte_a="ERA5-Land", fonte_b="ARPA meteo")
    soglie = []
    if era is None or arpa is None:
        confronto = ConfrontoTemperatura(**base, coppie=0, nota=(
            f"ERA5-Land {statistica} {mese} non in cache" if era is None else f"ARPA meteo {mese[:4]} non in cache"))
    else:
        a = arpa[arpa["comune"].isin(comuni)]
        con_stazione = sorted(set(a.loc[a["stato"] != "NO_DATA", "comune"]))
        j = (era[(era["stato"] == "VALORE") & era["comune"].isin(comuni)][["comune", "giorno", "valore"]]
             .merge(a[a["stato"] == "VALORE"][["comune", "giorno", "valore"]], on=["comune", "giorno"],
                    suffixes=("_era", "_arpa")))
        if j.empty:
            nota = ("nessuna stazione ARPA meteo nei comuni della zona: ERA5-Land è l'unica fonte" if not con_stazione
                    else "le stazioni ARPA meteo della zona non hanno valori nel mese")
            confronto = ConfrontoTemperatura(**base, coppie=0, comuni=[nomi[c] for c in con_stazione], nota=nota)
        else:
            d = j["valore_era"] - j["valore_arpa"]
            r = j["valore_era"].corr(j["valore_arpa"]) if len(j) > 2 else None
            confronto = ConfrontoTemperatura(
                **base, coppie=len(j), comuni=[nomi[c] for c in sorted(j["comune"].unique())],
                bias=float(d.mean()), errore_medio=float(d.abs().mean()), rmse=float((d ** 2).mean() ** 0.5),
                correlazione=None if r is None or pd.isna(r) else float(r),
                nota=("Modello su celle di ~9 km contro misura in un punto: ERA5-Land smussa i picchi, quindi tende a "
                      "sottostimare la massima e a sovrastimare la minima."))
            for nome, (stat, soglia, descrizione) in SOGLIE_CALDO.items():
                if stat == statistica:
                    soglie.append(SogliaFonti(indicatore=nome, descrizione=descrizione, soglia=soglia,
                                              giorni_a=int((j["valore_era"] >= soglia).sum()),
                                              giorni_b=int((j["valore_arpa"] >= soglia).sum())))
    return RispostaFontiCalore(mese=mese, statistica=statistica, unita=UNITA_CALORE, zona=z, serie=serie,
                               confronto=confronto, soglie=soglie)


@app.get("/api/salute/fonti", response_model=RispostaFontiSalute,
         summary="Decessi secondo ISTAT giornaliero, bilancio mensile ed Eurostat, in un anno")
def salute_fonti(anno: int = Query(ge=2011, le=2100),
                 zona: str = Query(..., description="distretto o comune (un comune si legge col suo distretto)")):
    """Legge le tabelle di scripts/salute/valida_decessi.py (nessuna chiamata a Eurostat). Distretto × mese: canale A
    ↔ bilancio mensile; provincia × mese: canale A ↔ Eurostat (settimane ISO portate al mese del giovedì). Un comune
    non ha decessi propri in dashboard (privacy, docs/Regole_dei_dati.md): si mostra il suo distretto e lo si dichiara."""
    mese_df, prov_df = archivio_fonti_decessi.tabelle()
    if mese_df is None:
        raise HTTPException(404, "il confronto fra le fonti dei decessi non è ancora stato preparato")
    richiesta = _zona_rif(zona)
    distretto = _zona_rif(richiesta.id_distretto)
    t = territorio()
    id_prov = t["distretti"][distretto.id]["id_provincia"]
    prov = next((p["denominazione"] for p in t["province"] if p["id_provincia"] == id_prov), id_prov)

    def serie(df, chiave, colonna, periodi, nota_assente):
        nome, descrizione = dati_fonti_salute.FONTI[chiave]
        p = dati_fonti_salute.punti(df, chiave, colonna, periodi, nota_assente)
        return SerieFontePeriodo(chiave=chiave, fonte=nome, descrizione=descrizione, punti=[PuntoPeriodo(**x) for x in p])

    del_distretto = mese_df[mese_df["distretto"] == distretto.id]
    mesi = dati_fonti_salute.mesi_dell_anno(anno)
    mensile = [serie(del_distretto, "A", "mese", mesi, "mese fuori dalla copertura del rilascio ISTAT"),
               serie(del_distretto, "D", "mese", mesi,
                     "bilancio mensile non pubblicato per l'anno (file scaricabili 2019-2024)")]
    della_prov = prov_df[prov_df["id_provincia"] == id_prov] if prov_df is not None else None
    assente_eu = ("Eurostat non scaricato (script lanciato con --senza-eurostat)" if prov_df is None
                  else "mese non pubblicato da Eurostat")
    provinciale = [serie(della_prov, "A", "mese", mesi, "mese fuori dalla copertura del rilascio ISTAT"),
                   serie(della_prov, "Eurostat", "mese", mesi, assente_eu)]

    def confronto(sa, sb, livello, nota):
        c = dati_fonti_salute.confronta([p.model_dump() for p in sa.punti], [p.model_dump() for p in sb.punti])
        return ConfrontoConteggi(fonte_a=sa.fonte, fonte_b=sb.fonte, livello=livello, nota=nota, **c)

    confronti = [confronto(*mensile, "distretto × mese", dati_fonti_salute.NOTA_A_D),
                 confronto(*provinciale, f"provincia × mese ({prov})", dati_fonti_salute.NOTA_A_EUROSTAT)]
    return RispostaFontiSalute(anno=anno, zona=distretto, zona_richiesta=richiesta, id_provincia=id_prov,
                               denominazione_provincia=prov, mensile=mensile, provinciale=provinciale,
                               confronti=confronti, licenza=dati_fonti_salute.LICENZA,
                               generato_il=archivio_fonti_decessi.generato_il(), nota_privacy=NOTA_PRIVACY)


def _mesi(da, a):
    anno, num = int(da[:4]), int(da[5:])
    out = []
    while f"{anno:04d}-{num:02d}" <= a:
        out.append(f"{anno:04d}-{num:02d}")
        num += 1
        if num == 13:
            anno, num = anno + 1, 1
    return out


def _decessi_distretti(distretti, mesi):
    """{id_distretto: [PuntoDecessi per mese]} o None se il file dei decessi non c'è."""
    dm, _ = archivio_decessi.distretto_mese()
    if dm is None:
        return None
    sel = dm[dm["distretto"].isin(distretti) & dm["mese"].isin(mesi)]
    per_chiave = {(r.distretto, r.mese): r for r in sel.itertuples()}
    out = {}
    for d in distretti:
        punti = []
        for m in mesi:
            r = per_chiave.get((d, m))
            if r is None:
                punti.append(PuntoDecessi(mese=m, valore=None, stato="NO_DATA", nota="mese fuori dal periodo del file ISTAT"))
            else:
                punti.append(PuntoDecessi(mese=m, valore=_pulito(r.valore), stato=r.stato, nota=_pulito(r.nota),
                                          comuni=int(r.comuni), comuni_con_valore=int(r.comuni_con_valore),
                                          quota_residenti=float(r.quota_residenti)))
        out[d] = punti
    return out


def _periodo(da, a):
    if da > a:
        raise HTTPException(422, "'da' deve precedere 'a'")
    mesi = _mesi(da, a)
    if len(mesi) > MAX_MESI_CONFRONTO:
        raise HTTPException(422, f"al più {MAX_MESI_CONFRONTO} mesi per richiesta")
    return mesi


def _distretti_validi(distretti):
    ids = [d.strip() for d in (distretti or "").split(",") if d.strip()]
    sconosciuti = [d for d in ids if d not in territorio()["distretti"]]
    if sconosciuti:
        raise HTTPException(404, f"distretti non trovati: {', '.join(sconosciuti)} (i decessi si espongono solo per distretto)")
    return ids or sorted(territorio()["distretti"])


def _calore_distretti(distretti, mesi, statistica):
    """{id_distretto: [PuntoMese per mese]} della temperatura; vuoto se nessun mese è in cache."""
    out = {d: [] for d in distretti}
    if not any(archivio_calore.mesi_in_cache().values()):
        return {}
    for m in mesi:
        dm = archivio_calore.distretto_mese(statistica, m)
        per_d = {r.distretto: r for r in dm.itertuples()} if dm is not None else {}
        for d in distretti:
            r = per_d.get(d)
            if r is None:
                out[d].append(PuntoMese(mese=m, valore=None, stato="NO_DATA", nota=f"temperatura {statistica} non in cache per il mese"))
            else:
                out[d].append(PuntoMese(mese=m, valore=_pulito(r.valore), stato=r.stato, nota=_pulito(r.nota)))
    return out


@app.get("/api/salute/decessi", response_model=RispostaDecessi, summary="Decessi ISTAT per distretto × mese")
def salute_decessi(da: str = Query(pattern=MESE), a: str = Query(pattern=MESE),
                   distretti: str | None = Query(None, description="id separati da virgola; tutti se assente")):
    mesi = _periodo(da, a)
    ids = _distretti_validi(distretti)
    per_distretto = _decessi_distretti(ids, mesi)
    if per_distretto is None:
        raise HTTPException(404, "decessi ISTAT non ancora scaricati")
    _, fino = archivio_decessi.distretto_mese()
    return RispostaDecessi(da=da, a=a, fonte=FONTE_DECESSI, licenza=LICENZA_DECESSI, copertura_fino_al=fino,
                           distretti=[SerieDecessi(id_distretto=d, punti=p) for d, p in per_distretto.items()],
                           nota_privacy=NOTA_PRIVACY)


@app.get("/api/salute/dimissioni", response_model=RispostaDimissioni,
         summary="Dimissioni ospedaliere ISTAT HFA per provincia × anno (solo informativo)")
def salute_dimissioni(da: int = Query(ge=1999, le=2100), a: int = Query(ge=1999, le=2100),
                      province: str | None = Query(None, description="LE, BR, TA separate da virgola; tutte se assente"),
                      gruppi: str | None = Query(None, description="gruppi separati da virgola; tutti se assente")):
    """Serie annuale per provincia e gruppo di patologia. Dato di contesto da affiancare ai decessi: la grana è
    provincia × anno, quindi non si correla con l'aria e non si riporta a distretto o a mese."""
    if da > a:
        raise HTTPException(422, "da deve essere <= a")
    df = archivio_dimissioni.tabella()
    if df is None:
        raise HTTPException(404, "dimissioni ISTAT non ancora scaricate")
    nomi = {p["id_provincia"]: p["denominazione"] for p in territorio()["province"]}
    ids = [x.strip().upper() for x in province.split(",")] if province else list(nomi)
    ignoti = [x for x in ids if x not in nomi]
    if ignoti:
        raise HTTPException(404, f"province non trovate: {', '.join(ignoti)}")
    scelti = [x.strip() for x in gruppi.split(",")] if gruppi else list(dati_dimissioni.ETICHETTE)
    ignoti = [x for x in scelti if x not in dati_dimissioni.ETICHETTE]
    if ignoti:
        raise HTTPException(404, f"gruppi non trovati: {', '.join(ignoti)} (ammessi: {', '.join(dati_dimissioni.ETICHETTE)})")
    serie = []
    for p in ids:
        for g in scelti:
            sel = df[(df["provincia"] == p) & (df["gruppo"] == g) & (df["anno"] >= da) & (df["anno"] <= a)].sort_values("anno")
            punti = [PuntoDimissioni(anno=int(r.anno), dimissioni=_pulito(r.dimissioni), tasso=_pulito(r.tasso), stato=r.stato,
                                     nota=_pulito(r.nota), media_giornaliera=_media_dimissioni(r, int(r.anno)))
                     for r in sel.itertuples()]
            serie.append(SerieDimissioni(provincia=p, denominazione_provincia=nomi[p], gruppo=g,
                                         etichetta=dati_dimissioni.ETICHETTE[g], punti=punti))
    return RispostaDimissioni(da=da, a=a, fonte=dati_dimissioni.FONTE, licenza=dati_dimissioni.LICENZA, serie=serie,
                              nota=dati_dimissioni.NOTA_GRANA)


@app.get("/api/confronto", response_model=RispostaConfronto, summary="Aria, temperatura e decessi per distretto × mese (esplorativo)")
def get_confronto(da: str = Query(pattern=MESE), a: str = Query(pattern=MESE), inquinante: str = Query(...),
                  fonte: str = Query("ARPA"), distretti: str = Query(..., description="al più 3, separati da virgola"),
                  statistica_calore: Literal["media", "massima", "minima"] = Query("media")):
    mesi = _periodo(da, a)
    ids = _distretti_validi(distretti)
    if len(ids) > MAX_ZONE:
        raise HTTPException(422, f"al più {MAX_ZONE} distretti")
    aria = {d: [] for d in ids}
    unita = None
    for m in mesi:
        agg = cache_aria.riassunto(m)  # basta il riassunto del mese (consuntivo su disco): niente ricalcolo dei giorni
        if agg is not None:
            unita = unita or agg.meta["inquinanti"].get(inquinante)
            sel = agg.distretto_mese[(agg.distretto_mese["fonte"] == fonte) & (agg.distretto_mese["inquinante"] == inquinante)]
            per_d = {r.distretto: r for r in sel.itertuples()}
        for d in ids:
            r = per_d.get(d) if agg is not None else None
            if agg is None:
                aria[d].append(PuntoMese(mese=m, valore=None, stato="NO_DATA", nota="nessun dataset aria generato per il mese"))
            elif r is None:
                aria[d].append(PuntoMese(mese=m, valore=None, stato="NO_DATA",
                                         nota=f"fonte {fonte} o inquinante {inquinante} assente nel dataset del mese"))
            else:
                aria[d].append(PuntoMese(mese=m, valore=_pulito(r.valore), stato=r.stato, nota=_pulito(r.nota)))
    decessi = _decessi_distretti(ids, mesi) or {}
    calore = _calore_distretti(ids, mesi, statistica_calore)
    serie = [SerieConfronto(zona=_zona_rif(d), aria=aria[d], decessi=decessi.get(d, []), calore=calore.get(d, [])) for d in ids]
    return RispostaConfronto(da=da, a=a, inquinante=inquinante, unita=unita, fonte_aria=fonte, serie=serie,
                             fonte_decessi=FONTE_DECESSI if decessi else None,
                             statistica_calore=statistica_calore, calore=_disponibilita_calore())


REGOLE_STAGIONALITA = (
    "Mese dell'anno = media dei mesi completi degli anni del confronto, comuni a tutti i domini (dal 2024); lo storico "
    "precedente resta nel dettaglio anno per anno e nel grafico anno su anno, fuori da medie e ranghi. Rango 1-12: "
    "1 = mese peggiore (valore più alto), pari merito = rango medio. Aria complessiva = media dei ranghi dei 5 "
    "inquinanti di riferimento, riordinata; limite del D.Lgs. 155/2010 superato nel mese in almeno un anno (a parità di "
    "statistica; con «Tutte» su tutte le fonti reali; per il Salento in almeno un distretto). Criticità dell'anno "
    "(27/10/2026): un mese è critico per un tema se è fra i suoi 3 mesi peggiori; temi = aria complessiva, temperatura "
    "massima, decessi, PS, PS degli assistiti ADI, ricoveri respiratori (gli ultimi tre simulati, escludibili); i mesi "
    "vicini con almeno due temi critici formano un periodo; il mese peggiore è il picco del primo periodo (29/10/2026). "
    "Andamento = ultimo mese completo vs media dello stesso mese negli anni precedenti: ±10% (aria, decessi), "
    "±1 °C (temperatura). Scelte del 16/10 e del 29/10/2026.")


@app.get("/api/stagionalita", response_model=RispostaStagionalita,
         summary="I 12 mesi dell'anno a confronto: aria, calore, decessi, PS/ADI/ricoveri simulati e criticità (tab Stagionalità)")
def stagionalita(zona: str = Query(dati_stagionalita.ZONA_SALENTO, description="SALENTO o un id_distretto (es. LE-51)"),
                 fonte: str = Query(FONTE_ACCORPATA, description="fonte dell'aria, o «Tutte» (default)"),
                 scenario: str = SCENARIO,
                 simulati_nella_sintesi: bool = Query(True, description="se PS, ADI e ricoveri simulati contano fra i temi "
                                                                        "critici (periodi e mese peggiore)")):
    """Legge solo i riassunti mensili preparati da scripts/dashboard/prepara_stagionalita.py: nessun mese si calcola
    dentro la richiesta. I mesi dell'archivio senza riassunto aggiornato sono in `mesi_da_preparare`. Niente comuni:
    i decessi si pubblicano solo per distretto e mese (privacy, docs/Regole_dei_dati.md)."""
    t = territorio()
    if zona == dati_stagionalita.ZONA_SALENTO:
        rif, denominazione = None, "Salento"
    else:
        if not ID_DISTRETTO.match(zona):
            raise HTTPException(422, "zona: SALENTO o un id_distretto (i comuni non sono ammessi: privacy dei decessi)")
        rif = _zona_rif(zona)
        denominazione = rif.denominazione
    aria = archivio_stagionalita.aria()
    calore = archivio_stagionalita.calore()
    fonti = {f for r in aria.values() for z in r["zone"].values() for f in z}
    if aria and fonte not in fonti:
        raise HTTPException(404, f"fonte '{fonte}' assente nei riassunti: disponibili {', '.join(sorted(fonti))}")
    da_preparare = [m for m in archivio.mesi_disponibili()
                    if m not in aria or aria[m].get("firma") != [list(x) for x in cache_aria._firma(m)]]
    _, _, tab_inq = leggi_anagrafica(FILE_ANAGRAFICHE["inquinanti"])
    riferimento = [r for r in tab_inq["inquinanti"] if r.get("riferimento_dashboard")]
    _scenario_valido(scenario)
    comuni = sorted(t["comuni"]) if rif is None else _comuni_del_distretto(rif.id)
    ps = None
    if archivio_simulato.disponibile():
        righe_sim = archivio_simulato.righe(comuni, scenario)
        ps = {"mensile": {i: dati_simulati.mensile(righe_sim, i) for i in dati_stagionalita.INDICATORI_SIMULATI},
              "residenti": _residenti(comuni), "scenario": scenario, "periodo": archivio_simulato.periodo()}
    dati = dati_stagionalita.calcola(
        zona, fonte, aria, calore, archivio_decessi.distretto_mese(), sorted(t["distretti"]),
        [r["id_inquinante"] for r in riferimento], {r["id_inquinante"]: r.get("unita_misura") for r in riferimento},
        ps=ps, simulati_nella_sintesi=simulati_nella_sintesi)
    return RispostaStagionalita(zona=rif, denominazione=denominazione, mesi_da_preparare=da_preparare,
                                regole=REGOLE_STAGIONALITA, scenario=scenario if ps else None,
                                simulati_nella_sintesi=simulati_nella_sintesi,
                                **{k: v for k, v in dati.items() if k != "zona"})


@app.get("/api/assistente/stato", response_model=StatoAssistente,
         summary="Se l'assistente può rispondere: Ollama attivo e modello scaricato")
def assistente_stato():
    """Modello e indirizzo di Ollama vengono da localhost/rag/config.py, non dal client. Un nome senza tag vale
    come ':latest', come in Ollama."""
    modello = config_assistente.MODELLO
    versione = ollama.versione()
    installato = versione is not None and (modello if ":" in modello else f"{modello}:latest") in ollama.modelli_installati()
    motivo = None
    if versione is None:
        motivo = f"Ollama non risponde su {config_assistente.URL_OLLAMA}: avviarlo (ollama serve) o installarlo."
    elif not installato:
        motivo = f"Modello {modello} non scaricato: ollama pull {modello}"
    return StatoAssistente(pronto=motivo is None, modello=modello, ollama_attivo=versione is not None,
                           versione_ollama=versione, modello_installato=installato, motivo=motivo)


def _nome_zona_assistente(z: ZonaRif):
    """Come nella dashboard (nomeZona in stato/dati.ts): «Lecce (LE 51)» per un distretto, il nome per un comune."""
    if z.tipo == "comune":
        return z.denominazione
    t = territorio()
    d = t["distretti"][z.id]
    sede = (t["comuni"].get(d.get("id_comune_sede")) or {}).get("denominazione")
    cifre = re.sub(r"\D", "", d["denominazione"]) or z.id
    numero = f"{d['id_provincia']} {cifre}"
    return f"{sede} ({numero})" if sede else f"Distretto {numero}"


def _natura_aria(z: ZonaRif, fonte, modellata):
    """Fonte misurata → misurato, CAMS → modellato. «Tutte» = media delle fonti concordi, CAMS compresa: modellato
    dove la zona non ha stazioni fisiche, altrimenti misto."""
    if fonte != FONTE_ACCORPATA:
        return "modellato" if modellata else "misurato"
    stazioni = stazioni_fisiche_per_comune()
    comuni = [z.id] if z.tipo == "comune" else _comuni_del_distretto(z.id)
    return "misto" if any(stazioni.get(c) for c in comuni) else "modellato"


def _serie_assistente(mese, inquinante, fonte, zone):
    """Serie della card «andamento» nel formato dell'assistente: l'inquinante giorno per giorno e la T max ERA5-Land
    delle stesse zone (dict vuoto se il mese di temperatura non è in archivio)."""
    aria = aria_serie(mese=mese, inquinante=inquinante, fonte=fonte, zone=zone)
    try:
        calore = calore_serie(mese=mese, zone=zone, statistica="massima", fonte="era5")
    except HTTPException:
        calore = None  # temperatura del mese non in archivio: la scheda lo dichiara
    serie_aria = [da_punti(s.punti, zona_id=s.zona.id, zona=_nome_zona_assistente(s.zona), variabile=inquinante,
                           unita=aria.unita, grana="giorno", natura=_natura_aria(s.zona, fonte, aria.fonte_modellata),
                           fonte=fonte, statistica=aria.statistica) for s in aria.serie]
    serie_calore = {} if calore is None else {
        s.zona.id: da_punti(s.punti, zona_id=s.zona.id, zona=_nome_zona_assistente(s.zona), variabile="temperatura massima",
                            unita=calore.unita, grana="giorno", natura="modellato", fonte=calore.fonte, statistica="massima")
        for s in calore.serie}
    return serie_aria, serie_calore


def _dati_domini(da, mese, inquinante, fonte, zone, statistica_calore="massima"):
    """Card «domini»: l'aria, la temperatura (dal 03/11/2026, la statistica scelta nella card) e i decessi di
    /api/confronto per i soli distretti (i decessi non esistono per comune). La temperatura entra solo per i distretti
    con almeno un mese a valore."""
    distretti = [z for z in zone if ID_DISTRETTO.match(z)]
    esclusi = [_nome_zona_assistente(_zona_rif(z)) for z in zone if not ID_DISTRETTO.match(z)]
    if not distretti:
        return {"aria": [], "decessi": {}, "temperatura": {}, "comuni_esclusi": esclusi}
    c = get_confronto(da=da, a=mese, inquinante=inquinante, fonte=fonte, distretti=",".join(distretti),
                      statistica_calore=statistica_calore)
    aria, decessi, temperatura = [], {}, {}
    for s in c.serie:
        nome = _nome_zona_assistente(s.zona)
        aria.append(da_punti(s.aria, zona_id=s.zona.id, zona=nome, variabile=inquinante, unita=c.unita, grana="mese",
                             natura=_natura_aria(s.zona, fonte, fonte == "CAMS"), fonte=fonte, statistica="media del mese"))
        if any(p.stato == "VALORE" for p in s.calore):
            temperatura[s.zona.id] = da_punti(s.calore, zona_id=s.zona.id, zona=nome,
                                              variabile=f"temperatura {statistica_calore}", unita=c.calore.unita or "°C",
                                              grana="mese", natura="modellato", fonte="ERA5-Land",
                                              statistica="media del mese")
        if s.decessi:
            decessi[s.zona.id] = da_punti(s.decessi, zona_id=s.zona.id, zona=nome, variabile="decessi del mese",
                                          unita="decessi", grana="mese", natura="reale", fonte="ISTAT",
                                          statistica="somma del mese")
    return {"aria": aria, "decessi": decessi, "temperatura": temperatura, "comuni_esclusi": esclusi}


def _dati_stagione(zone, fonte, scenario, simulati_nella_sintesi):
    """Card della Stagionalità: la risposta di /api/stagionalita per il Salento o il distretto della card."""
    st = stagionalita(zona=zone[0] if zone else dati_stagionalita.ZONA_SALENTO, fonte=fonte,
                      scenario=scenario or dati_simulati.SCENARIO_PREDEFINITO,
                      simulati_nella_sintesi=simulati_nella_sintesi)
    if fonte == "CAMS":
        natura = "modellato"
    elif fonte != FONTE_ACCORPATA:
        natura = "misurato"
    else:
        natura = "misto" if st.zona is None else _natura_aria(st.zona, fonte, False)
    out = {"st": st.model_dump(mode="json"), "area": "Salento" if st.zona is None else _nome_zona_assistente(st.zona),
           "natura_aria": natura}
    out["iniziativa"] = _dati_iniziativa(st.zona.id if st.zona else None, scenario or dati_simulati.SCENARIO_PREDEFINITO)
    return out


# Medicina di iniziativa (10/11/2026, scopo di ONE): gli indicatori dell'ospedalizzazione per zona, sugli ultimi 12
# mesi completi del periodo simulato. Sotto questa soglia un comune ha troppi pochi eventi l'anno per un tasso stabile
# e resta fuori dalla classifica (localhost/rag/schede.py, _fatti_priorita_zone).
INDICATORI_INIZIATIVA = ("ricoveri_respiratori", "ricoveri_circolatori", "ps_accessi", "adi_assistiti",
                         "adi_accessi_ps", "adi_accessi_bassa_urgenza", "adi_ritorni_30g")
MESI_ESTATE = (7, 8)
SOGLIA_RESIDENTI_INIZIATIVA = 5000


def _ultimi_12_mesi_simulati():
    """I 12 mesi completi che finiscono con l'ultimo mese intero del periodo simulato; None se non ci sono 12 mesi."""
    da_s, a_s = archivio_simulato.periodo()
    if not a_s:
        return None
    fine = date.fromisoformat(a_s)
    if (fine + timedelta(days=1)).month == fine.month:  # l'ultimo giorno non chiude il mese
        fine = fine.replace(day=1) - timedelta(days=1)
    mesi = []
    a, m = fine.year, fine.month
    for _ in range(12):
        mesi.append(f"{a:04d}-{m:02d}")
        a, m = (a, m - 1) if m > 1 else (a - 1, 12)
    mesi.reverse()
    return mesi if mesi[0] >= da_s[:7] else None


def _estate_distretti():
    """{id_distretto | SALENTO: media della T max di luglio e agosto (ERA5-Land, modellata) nei mesi completi dal 2024}."""
    somme = {}
    for mese, r in archivio_stagionalita.calore().items():
        if int(mese[5:7]) not in MESI_ESTATE or int(mese[:4]) < dati_stagionalita.PRIMO_ANNO_CONFRONTO or not r.get("completo"):
            continue
        for zona, v in r["zone"].items():
            x = (v.get("massima") or {}).get("valore")
            if x is not None:
                somme.setdefault(zona, []).append(x)
    return {z: sum(v) / len(v) for z, v in somme.items()}


def _dati_iniziativa(id_distretto, scenario):
    """Ricoveri, PS e ADI simulati degli ultimi 12 mesi per zona: i 20 distretti se la card è sul Salento, i comuni del
    distretto se è su un distretto. Con alberi e suolo (CLMS) e, per i distretti, il caldo estivo. **Dato simulato.**"""
    mesi = _ultimi_12_mesi_simulati()
    if not archivio_simulato.disponibile() or not mesi:
        return None
    t = territorio()
    tutti = sorted(t["comuni"])
    righe = archivio_simulato.righe(tutti, scenario, mesi=mesi)
    if righe is None or righe.empty:
        return None
    giorni = int(righe["data"].nunique())
    indicatori = [i for i in INDICATORI_INIZIATIVA if i in righe]
    somme = righe.groupby("id_comune")[indicatori].sum()

    def valori(comuni):
        res = _residenti(comuni)
        tot = somme.reindex(comuni).fillna(0).sum()
        out = {i: (float(tot[i]) / giorni / res * dati_simulati.PER if i in dati_simulati.STOCK
                   else dati_simulati.per_100k_giorno(float(tot[i]), res, giorni)) for i in indicatori}
        adi = float(tot.get("adi_accessi_ps", 0))
        out["quota_bassa_urgenza"] = float(tot["adi_accessi_bassa_urgenza"]) / adi if adi else None
        out["quota_ritorni"] = float(tot["adi_ritorni_30g"]) / adi if adi else None
        return res, out

    distretti = {p.id_distretto: p for pr in get_territorio() for p in pr.distretti}
    estate = _estate_distretti()

    def voce_distretto(d):
        res, v = valori(_comuni_del_distretto(d))
        x = distretti[d]
        return {"id": d, "nome": _nome_zona_assistente(_zona_rif(d)), "residenti": res, "valori": v,
                "alberi": x.copertura_arborea_pct, "suolo": x.suolo_impermeabile_pct, "estate": estate.get(d)}

    res_sal, val_sal = valori(tutti)
    salento = {"id": dati_stagionalita.ZONA_SALENTO, "nome": "Salento", "residenti": res_sal, "valori": val_sal,
               "estate": estate.get(dati_stagionalita.ZONA_SALENTO)}
    base = {"mesi": mesi, "giorni": giorni, "scenario": scenario, "salento": salento,
            "soglia_residenti": SOGLIA_RESIDENTI_INIZIATIVA}
    if id_distretto is None:
        return {**base, "livello": "distretti", "area": salento, "zone": [voce_distretto(d) for d in sorted(distretti)]}
    zone = []
    for c in _comuni_del_distretto(id_distretto):
        res, v = valori([c])
        x = t["comuni"][c]
        zone.append({"id": c, "nome": x["denominazione"], "residenti": res, "valori": v,
                     "alberi": x.get("copertura_arborea_pct"), "suolo": x.get("suolo_impermeabile_pct"), "estate": None})
    return {**base, "livello": "comuni", "area": voce_distretto(id_distretto),
            "distretti": [voce_distretto(d) for d in sorted(distretti)], "zone": zone}


# --- card istantanee (03/11/2026): i dati di localhost/rag/schede_istantanee.py --------------------------------------

def _nomi_zone():
    """id → nome leggibile di tutti i distretti e i comuni, come nella chat."""
    t = territorio()
    nomi = {c: x["denominazione"] for c, x in t["comuni"].items()}
    nomi.update({d: _nome_zona_assistente(_zona_rif(d)) for d in t["distretti"]})
    return nomi


def _territorio_zone():
    """{"distretti": id → DistrettoTerritorio, "comuni": id → ComuneTerritorio}, con stazioni, chioma e suolo."""
    out = {"distretti": {}, "comuni": {}}
    for p in get_territorio():
        for d in p.distretti:
            out["distretti"][d.id_distretto] = d
            out["comuni"].update({c.id_comune: c for c in d.comuni})
    return out


def _voce(i, nome, c):
    """Una cella (CellaMensile, CellaRiepilogo o dict) come «voce» delle schede istantanee; None = la zona non c'è."""
    if c is None:
        return {"id": i, "nome": nome, "valore": None, "stato": "NO_DATA", "nota": "nessun dato per la zona"}
    c = c if isinstance(c, dict) else c.model_dump()
    return {"id": i, "nome": nome, "valore": _pulito(c.get("valore")), "stato": c["stato"], "nota": c.get("nota")}


def _facoltativo(chiamata):
    """Un dato di contorno (temperatura, salute, salubrità…) che può mancare senza togliere il resto della scheda."""
    try:
        return chiamata()
    except HTTPException:
        return None


def _periodo_assistente(da, a):
    testo = dal_al(da, a, "giorno")
    return testo[0].upper() + testo[1:]


def _natura_fonte(fonte):
    """Natura dell'aria di una card con molte zone: «Tutte» mescola misura e CAMS, CAMS è modellato."""
    return "modellato" if fonte == "CAMS" else "misto" if fonte == FONTE_ACCORPATA else "misurato"


def _unita_inquinante(inquinante):
    _, _, tab_inq = leggi_anagrafica(FILE_ANAGRAFICHE["inquinanti"])
    return next((r.get("unita_misura") for r in tab_inq["inquinanti"] if r["id_inquinante"] == inquinante), None)


def _strati(livello, ter, nomi, aria, inquinante, calore, salute):
    """I dati delle viste della carta per le zone di un livello: aria, temperatura, alberi, suolo, eventi sanitari."""
    ids = sorted(ter[livello])
    celle_aria = getattr(aria, livello)
    s = {"aria": {"var": {"nome": inquinante, "unita": _unita_inquinante(inquinante), "dominio": "aria"},
                  "voci": [_voce(i, nomi[i], celle_aria.get(i, {}).get(inquinante)) for i in ids]}}
    if calore is not None:
        s["temperatura"] = {"var": {"nome": f"temperatura {calore.statistica}", "unita": calore.unita, "dominio": "calore"},
                            "voci": [_voce(i, nomi[i], getattr(calore, livello).get(i)) for i in ids]}
    for chiave, campo, nome in (("alberi", "copertura_arborea_pct", "copertura arborea"),
                                ("suolo", "suolo_impermeabile_pct", "suolo impermeabile")):
        s[chiave] = {"var": {"nome": nome, "unita": "%", "dominio": chiave}, "voci": [
            {"id": i, "nome": nomi[i], "valore": v, "stato": "VALORE" if v is not None else "NO_DATA",
             "nota": None if v is not None else "valore CLMS non disponibile"}
            for i in ids for v in [getattr(ter[livello][i], campo)]]}
    if salute is not None:
        s["salute"] = {"var": {"nome": "eventi sanitari (decessi, ricoveri e accessi in PS)", "unita": "per 100.000 "
                               "residenti al giorno", "dominio": "simulati"},
                       "voci": [_voce(i, nomi[i], getattr(salute, livello).get(i)) for i in ids]}
    return s


def _simulati_zona(sim):
    """I simulati della scheda della zona come li mostra DettaglioZona.tsx: tassi per 100.000 residenti al giorno, gli
    assistiti ADI in carico (media della finestra) e le due quote ADI in percentuale."""
    if not sim or sim.stato != "VALORE":
        return []
    per = {v.indicatore: v for v in sim.valori}
    out = [{"etichetta": per[k].etichetta, "valore": per[k].per_100k, "unita": "per 100.000 residenti al giorno"}
           for k in ("ricoveri_respiratori", "ricoveri_circolatori", "ps_accessi", "ps_respiratori",
                     "ps_cardiovascolari", "adi_accessi_ps") if k in per and per[k].per_100k is not None]
    if (a := per.get("adi_assistiti")) and a.totale is not None:
        out.append({"etichetta": "assistiti in ADI in carico, media della finestra", "valore": round(a.totale), "unita": None})
    for campo, etichetta in (("quota_bassa_urgenza", "accessi in PS degli assistiti ADI a bassa urgenza"),
                             ("quota_ritorni", "accessi ADI di chi era già passato dal PS nei 30 giorni prima")):
        if (q := getattr(sim, campo)) is not None:
            out.append({"etichetta": etichetta, "valore": q * 100, "unita": "%"})
    return out


VISTA_STRATO = {"valore": "aria", "salubrita": "aria", "temperatura": "temperatura", "alberi": "alberi",
                "suolo": "suolo", "salute": "salute"}


def _dati_mappa(p):
    """Card «mappa»: le viste della carta nella finestra e la scheda della zona in primo piano (scelta di Matteo del
    03/11/2026: la chat della carta risponde anche sulla zona)."""
    da, a, fonte, inq = p["giorno_da"], p["giorno_a"], p["fonte"], p["inquinante"]
    livello = p.get("livello") or "distretti"
    scenario = p.get("scenario") or dati_simulati.SCENARIO_PREDEFINITO
    nomi, ter = _nomi_zone(), _territorio_zone()
    aria = aria_finestra(da=da, a=a, fonte=fonte)
    calore = _facoltativo(lambda: calore_mappa(da=da, a=a, statistica="media"))
    salute = _facoltativo(lambda: salute_mappa(da=da, a=a, scenario=scenario))
    sal = _facoltativo(lambda: aria_salubrita(da=da, a=a))
    strati = _strati(livello, ter, nomi, aria, inq, calore, salute)
    out = {"periodo": _periodo_assistente(da, a), "plurale": livello, "vista": VISTA_STRATO[p.get("vista") or "valore"],
           "strati": strati, "senza_stazioni": [i for i, z in ter[livello].items() if z.senza_stazioni],
           "bande": [{"nome": nomi[i], "banda": z.banda, "peggiore": z.inquinante_peggiore}
                     for i, z in sorted(getattr(sal, livello).items())] if sal else None,
           "a_confronto": [z for z in p["zone"] if z in ter[livello]], "natura_aria": _natura_fonte(fonte),
           "fonte": fonte, "scenario": scenario}
    if pp := p.get("primo_piano"):
        z = _zona_rif(pp)
        liv = "distretti" if z.tipo == "distretto" else "comuni"
        det = zona_dettaglio(zona=pp, da=da, a=a, scenario=scenario)
        dec = det.salute
        out["primo_piano"] = {
            "id": pp, "nome": nomi[pp], "plurale": liv,
            "strati": strati if liv == livello else _strati(liv, ter, nomi, aria, inq, calore, salute),
            "salubrita": {"banda": det.salubrita.banda, "peggiore": det.salubrita.inquinante_peggiore} if det.salubrita else None,
            "decessi": ({"valore": dec.valore, "media_giornaliera": dec.media_giornaliera,
                         "mesi": [quando(m, "mese") for m in dec.mesi], "nota": dec.nota} if z.tipo == "distretto"
                        else {"valore": None, "nota": "non si mostrano per comune, per riservatezza"}),
            "simulati": _simulati_zona(det.simulati),
            "ricoveri": {"provincia": det.dimissioni.denominazione_provincia, "anno": det.dimissioni.anno,
                         "valori": [{"etichetta": v.etichetta, "dimissioni": v.dimissioni, "tasso": v.tasso}
                                    for v in det.dimissioni.valori if v.stato == "VALORE" and v.dimissioni is not None]}
            if det.dimissioni.stato == "VALORE" else None,
        }
    return out


def _sposta_mese(mese, n):
    anno, num = divmod(int(mese[:4]) * 12 + int(mese[5:]) - 1 + n, 12)
    return f"{anno:04d}-{num + 1:02d}"


def _dati_sintesi(p):
    """Card «sintesi»: gli stessi numeri di Kpi.tsx (valore più alto, copertura, decessi, ricoveri e PS del Salento) e
    la classifica delle zone di BarreConfronto.tsx."""
    da, a, fonte, inq = p["giorno_da"], p["giorno_a"], p["fonte"], p["inquinante"]
    livello = p.get("livello") or "distretti"
    scenario = p.get("scenario") or dati_simulati.SCENARIO_PREDEFINITO
    nomi, ter = _nomi_zone(), _territorio_zone()
    aria = aria_finestra(da=da, a=a, fonte=fonte)
    var = {"nome": inq, "unita": _unita_inquinante(inq), "dominio": "aria"}
    voci = {liv: [_voce(i, nomi[i], getattr(aria, liv).get(i, {}).get(inq)) for i in sorted(ter[liv])]
            for liv in ("distretti", "comuni")}
    residenti = sum(c.residenti or 0 for c in ter["comuni"].values())
    coperti = sum(ter["comuni"][v["id"]].residenti or 0 for v in voci["comuni"] if v["stato"] == "VALORE")
    out = {"periodo": _periodo_assistente(da, a), "var": var, "distretti": voci["distretti"],
           "livello": {"voci": voci[livello], "plurale": livello}, "a_confronto": p["zone"],
           "quota_residenti": coperti / residenti if residenti else None, "natura_aria": _natura_fonte(fonte),
           "fonte": fonte, "scenario": scenario}
    mesi = _mesi(da[:7], a[:7])
    prima = [_sposta_mese(m, -len(mesi)) for m in mesi]
    if dec := _facoltativo(lambda: salute_decessi(da=prima[0], a=mesi[-1], distretti=None)):
        def somma(ms):
            punti = [x for s in dec.distretti for x in s.punti if x.mese in ms]
            validi = [x.valore for x in punti if x.stato == "VALORE" and x.valore is not None]
            return sum(validi), len(validi), len(dec.distretti) * len(ms)
        (s, con, tot), (s0, con0, tot0) = somma(mesi), somma(prima)
        out["decessi"] = {"mesi": elenco(quando(m, "mese") for m in mesi), "somma": s, "con": con, "totale": tot,
                          "n_mesi": len(mesi), "mesi_prima": elenco(quando(m, "mese") for m in prima),
                          "variazione": s - s0 if con == tot and con0 == tot0 and tot else None}
    anno = int(a[:4])
    if dim := _facoltativo(lambda: salute_dimissioni(da=max(1999, anno - 2), a=anno, province="LE,BR,TA",
                                                     gruppi="respiratorio")):
        def totale(y):
            valori = [next((x for x in s.punti if x.anno == y), None) for s in dim.serie]
            return sum(x.dimissioni for x in valori) if dim.serie and all(
                x and x.stato == "VALORE" and x.dimissioni is not None for x in valori) else None
        anni = sorted({x.anno for s in dim.serie for x in s.punti}, reverse=True)
        if (y := next((y for y in anni if totale(y) is not None), None)) is not None:
            t0 = totale(y - 1)
            out["ricoveri"] = {"anno": y, "totale": totale(y), "variazione": totale(y) - t0 if t0 is not None else None}
    sim = _facoltativo(lambda: salute_simulati_finestra(zona=dati_stagionalita.ZONA_SALENTO, da=da, a=a, scenario=scenario))
    ps = next((v for v in sim.valori if v.indicatore == "ps_accessi"), None) if sim and sim.stato == "VALORE" else None
    if ps and ps.per_100k is not None:
        out["ps"] = {"per_100k": ps.per_100k}
    return out


def _dominio_colonna(id_colonna):
    radice = id_colonna.split(":")[0]
    return {"residenti": "territorio", "comuni": "territorio", "stazioni": "territorio", "aria": "aria",
            "salubrita": "salubrita", "salubrita_peggiore": "salubrita", "decessi": "decessi",
            "decessi_giorno": "decessi", "dimissioni": "ricoveri", "sim": "simulati",
            "calore": "calore"}.get(radice, "territorio")


def _dati_riepilogo(p):
    """Card «riepilogo»: le colonne di /api/riepilogo e la Δ dell'inquinante rispetto alla finestra precedente della
    stessa ampiezza (come TabellaRiepilogo.tsx)."""
    da, a, fonte, inq = p["giorno_da"], p["giorno_a"], p["fonte"], p["inquinante"]
    scenario = p.get("scenario") or dati_simulati.SCENARIO_PREDEFINITO
    nomi = _nomi_zone()
    r = riepilogo(da=da, a=a, fonte=fonte, scenario=scenario)
    out = {"periodo": _periodo_assistente(da, a), "a_confronto": [z for z in p["zone"] if ID_DISTRETTO.match(z)],
           "colonne": [{"id": c.id, "nome": f"{c.etichetta} ({c.gruppo})", "unita": c.unita, "formato": c.formato,
                        "dominio": _dominio_colonna(c.id)} for c in r.colonne],
           "righe": [{"id": x.id_distretto, "nome": nomi[x.id_distretto],
                      "celle": {k: v.model_dump() for k, v in x.celle.items()}} for x in r.righe],
           "natura_aria": _natura_fonte(fonte), "fonte": fonte, "scenario": scenario}
    d0, d1 = date.fromisoformat(da), date.fromisoformat(a)
    fine_prima = d0 - timedelta(days=1)
    inizio_prima = fine_prima - timedelta(days=(d1 - d0).days)
    if prima := _facoltativo(lambda: aria_finestra(da=inizio_prima.isoformat(), a=fine_prima.isoformat(), fonte=fonte)):
        ora = {x.id_distretto: x.celle.get(f"aria:{inq}") for x in r.righe}
        voci = []
        for i, c in ora.items():
            c0 = prima.distretti.get(i, {}).get(inq)
            ok = c and c0 and c.stato == "VALORE" and c0.stato == "VALORE" and c.valore is not None and c0.valore is not None
            voci.append({"id": i, "nome": nomi[i], "valore": c.valore - c0.valore if ok else None,
                         "stato": "VALORE" if ok else "NO_DATA", "nota": None if ok else "manca una delle due finestre"})
        out["delta"] = {"var": {"nome": inq, "unita": _unita_inquinante(inq) or "", "dominio": "aria"}, "voci": voci,
                        "periodo_prima": dal_al(inizio_prima.isoformat(), fine_prima.isoformat(), "giorno")}
    return out


def _punti_voci(punti, grana):
    return [{"id": t, "nome": quando(t, grana), "valore": _pulito(x.valore), "stato": x.stato, "nota": x.nota}
            for x in punti for t in [str(getattr(x, "giorno", None) or getattr(x, "periodo", None))]]


def _zona_card(p):
    if not p["zone"]:
        raise HTTPException(422, "la card vuole una zona")
    return p["zone"][0]


def _dati_fonti_aria(p):
    r = aria_fonti(mese=p["mese"], inquinante=p["inquinante"], zona=_zona_card(p))
    return {"zona": _nome_zona_assistente(r.zona), "variabile": r.inquinante, "periodo": quando(r.mese, "mese"),
            "unita": r.unita, "soglia": r.soglia_concordanza,
            "serie": [{"fonte": s.fonte, "modellata": s.modellata, "statistica": s.statistica,
                       "punti": _punti_voci(s.punti, "giorno")} for s in r.serie],
            "confronti": [c.model_dump() for c in r.confronti]}


def _dati_fonti_calore(p):
    r = calore_fonti(mese=p["mese"], zona=_zona_card(p), statistica=p.get("statistica_calore") or "media")
    return {"zona": _nome_zona_assistente(r.zona), "variabile": f"temperatura {r.statistica}",
            "periodo": quando(r.mese, "mese"), "unita": r.unita,
            "serie": [{"fonte": s.fonte, "modellata": s.modellata, "statistica": s.statistica,
                       "punti": _punti_voci(s.punti, "giorno")} for s in r.serie],
            "confronto": r.confronto.model_dump(), "soglie": [s.model_dump() for s in r.soglie]}


def _dati_fonti_decessi(p):
    r = salute_fonti(anno=int(p["mese"][:4]), zona=_zona_card(p))
    serie = lambda gruppo: [{"fonte": s.fonte, "descrizione": s.descrizione, "punti": _punti_voci(s.punti, "mese")}
                            for s in gruppo]
    return {"zona": _nome_zona_assistente(r.zona), "anno": r.anno, "provincia": r.denominazione_provincia,
            "mensile": serie(r.mensile), "provinciale": serie(r.provinciale),
            "confronti": [c.model_dump() for c in r.confronti]}


def _dati_ricoveri(p):
    """Card «ricoveri» della Stagionalità: le province della zona della tab (Salento = tutte e tre), gli ultimi cinque
    anni pubblicati, il gruppo di patologia scelto (`indicatore`), come Ricoveri.tsx."""
    t = territorio()
    zona = p["zone"][0] if p["zone"] else dati_stagionalita.ZONA_SALENTO
    province = ([x["id_provincia"] for x in t["province"]] if zona == dati_stagionalita.ZONA_SALENTO
                else [t["distretti"][zona]["id_provincia"]])
    anno_da, anno_a = archivio_dimissioni.anni_con_valore()
    if anno_a is None:
        raise HTTPException(404, "dimissioni ospedaliere non disponibili")
    da = max(anno_da, anno_a - 4)
    gruppo = p.get("indicatore") or "respiratorio"
    r = salute_dimissioni(da=da, a=anno_a, province=",".join(province), gruppi=gruppo)
    return {"gruppo": dati_dimissioni.ETICHETTE.get(gruppo, gruppo).lower(), "da": da, "a": anno_a,
            "serie": [{"provincia": s.denominazione_provincia,
                       "punti": [x.model_dump() for x in s.punti]} for s in r.serie]}


DATI_ISTANTANEE = {"mappa": _dati_mappa, "sintesi": _dati_sintesi, "riepilogo": _dati_riepilogo,
                   "fonti_aria": _dati_fonti_aria, "fonti_calore": _dati_fonti_calore,
                   "fonti_decessi": _dati_fonti_decessi, "ricoveri": _dati_ricoveri}


def _dati_assistente(card, p):
    """I dati di una card nel formato di localhost/rag/schede.py, con le stesse funzioni degli endpoint che la card
    chiama: aggregazioni, stati e privacy sono già applicati. `p`: parametri controllati (perimetro.controlla_parametri)."""
    if card == "andamento":
        return _serie_assistente(p["mese"], p["inquinante"], p["fonte"], ",".join(p["zone"]))
    if card == "domini":
        return _dati_domini(p["da"], p["mese"], p["inquinante"], p["fonte"], p["zone"], p["statistica_calore"])
    if card in DATI_ISTANTANEE:
        return DATI_ISTANTANEE[card](p)
    return _dati_stagione(p["zone"], p["fonte"], p["scenario"], p["simulati_nella_sintesi"])


def _inquinanti_tracciati():
    _, _, tab_inq = leggi_anagrafica(FILE_ANAGRAFICHE["inquinanti"])
    return [r["id_inquinante"] for r in tab_inq["inquinanti"]]


@app.get("/api/assistente/fatti", response_model=RispostaFattiAssistente,
         summary="Scheda dei fatti di una card, senza modello di linguaggio")
def assistente_fatti(card: CardAssistente = Query("andamento", description="card della dashboard (schede.CARD)"),
                     mese: str | None = Query(None, pattern=MESE, description="mese della card; per «domini» l'ultimo del periodo"),
                     da: str | None = Query(None, pattern=MESE, description="primo mese del periodo («domini»)"),
                     inquinante: str | None = Query(None, description="«andamento» e «domini»"),
                     fonte: str = Query(FONTE_ACCORPATA),
                     zone: str = Query("", description="id di distretti o comuni separati da virgola, al più 4; vuota = Salento"),
                     soglia: float | None = Query(None, ge=0, description="soglia scelta dall'utente («andamento»)"),
                     indicatore: str | None = Query(None, description="riga della Stagionalità («anno_su_anno»: quella del grafico)"),
                     mese_dell_anno: int | None = Query(None, ge=1, le=12, description="«dettaglio_mese»"),
                     scenario: Literal["nullo", "letteratura"] | None = Query(None, description="scenario dei simulati (Stagionalità)"),
                     simulati_nella_sintesi: bool = Query(True, description="interruttore «nella sintesi» (Stagionalità)"),
                     statistica_calore: Literal["media", "massima", "minima"] | None = Query(
                         None, description="statistica giornaliera della temperatura («domini»: massima; "
                                           "«fonti_calore»: media)"),
                     giorno_da: str | None = Query(None, pattern=GIORNO, description="primo giorno della finestra "
                                                                                     "(mappa, sintesi, riepilogo)"),
                     giorno_a: str | None = Query(None, pattern=GIORNO, description="ultimo giorno della finestra"),
                     vista: Literal["valore", "salubrita", "temperatura", "alberi", "suolo", "salute"] | None = Query(
                         None, description="vista della carta («mappa»)"),
                     livello: Literal["distretti", "comuni"] | None = Query(None, description="«mappa» e «sintesi»"),
                     primo_piano: str | None = Query(None, description="zona in primo piano («mappa»)")):
    """I dati si costruiscono con le stesse funzioni degli endpoint della card (/api/aria/serie e /api/calore/serie,
    /api/confronto, /api/stagionalita); le analisi di localhost/rag/analisi.py e schede.py ne ricavano i fatti. Un
    periodo fuori archivio risponde 404, che l'assistente traduce nel rifiuto fisso."""
    ids = [z for z in zone.split(",") if z]
    if len(ids) > MAX_ZONE:
        raise HTTPException(422, f"al più {MAX_ZONE} zone")
    contesto = {"mese": mese, "da": da, "inquinante": inquinante, "fonte": fonte, "zone": ids, "indicatore": indicatore,
                "mese_dell_anno": mese_dell_anno, "scenario": scenario, "simulati_nella_sintesi": simulati_nella_sintesi,
                "statistica_calore": statistica_calore, "giorno_da": giorno_da, "giorno_a": giorno_a, "vista": vista,
                "livello": livello, "primo_piano": primo_piano}
    finestra = ("giorno_da", "giorno_a", "inquinante")
    richiesti = {"andamento": ("mese", "inquinante", "zone"), "domini": ("da", "mese", "inquinante", "zone"),
                 "dettaglio_mese": ("mese_dell_anno",), "mappa": finestra, "sintesi": finestra, "riepilogo": finestra,
                 "fonti_aria": ("mese", "inquinante", "zone"), "fonti_calore": ("mese", "zone"),
                 "fonti_decessi": ("mese", "zone")}.get(card, ())
    if mancanti := [k for k in richiesti if not contesto[k]]:
        raise HTTPException(422, f"la card «{card}» vuole anche: {', '.join(mancanti)}")
    for z in ids + ([primo_piano] if primo_piano else []):
        _zona_rif(z)  # 404 se la zona non esiste
    inquinanti = _inquinanti_tracciati()
    if inquinante is not None and inquinante not in inquinanti:
        raise HTTPException(404, f"inquinante '{inquinante}' non tracciato")
    try:
        p = controlla_parametri(card, Instradamento("analisi", parametri={"soglia": soglia}), contesto, inquinanti).parametri
        risultato = schede.scheda(card, _dati_assistente(card, p), p)
    except Rifiuto as e:
        raise HTTPException(422, e.motivo) from e
    except AnalisiNonApplicabile as e:
        raise HTTPException(404, str(e)) from e
    return RispostaFattiAssistente(
        card=card, contesto={**contesto, "soglia": soglia},
        serie=[SerieAssistente(zona_id=s.zona_id, zona=s.zona, variabile=s.variabile, unita=s.unita, grana=s.grana,
                               natura=s.natura, fonte=s.fonte, statistica=s.statistica, punti=len(s.punti),
                               punti_con_valore=len(s.validi()))
               for s in risultato.get("serie", [])],
        fatti=[FattoAssistente(id=f.id, analisi=f.analisi, testo=f.testo) for f in risultato["fatti"]],
        avvertenze=risultato["avvertenze"])


@app.get("/api/assistente/domande", response_model=RispostaDomandeAssistente,
         summary="Domande proposte di una card")
def assistente_domande(card: CardAssistente = Query("andamento")):
    return RispostaDomandeAssistente(card=card, con_fatti=card in schede.CARD_CON_FATTI,
                                     domande=[DomandaProposta(id=d["id"], testo=d["testo"])
                                              for d in prompt_assistente.DOMANDE_PROPOSTE[card]])


def _fornisci_dati_assistente(card, p):
    """Per l'assistente un periodo fuori archivio non è un errore HTTP: è il rifiuto fisso."""
    try:
        return _dati_assistente(card, p)
    except HTTPException as e:
        raise AnalisiNonApplicabile(e.detail) from e


@app.post("/api/assistente", response_model=RispostaAssistente,
          summary="Risposta dell'assistente a una domanda sulla card aperta")
def assistente_domanda(richiesta: DomandaAssistente):
    """Percorso del piano del modulo AI §13.1 (localhost/rag/assistente.py). Il client manda solo card, contesto e
    domanda: modello e istruzioni stanno nel server. Una zona sconosciuta nel contesto è un errore del client (404);
    tutto ciò che dipende dalla domanda (periodo fuori archivio, argomento fuori elenco) è il rifiuto fisso."""
    c = richiesta.contesto
    if richiesta.card == "andamento" and not (c.mese and c.inquinante and c.zone):
        raise HTTPException(422, "la card «andamento» vuole mese, inquinante e almeno una zona nel contesto")
    # la zona in primo piano sulla carta è fra quelle di cui si può chiedere (card «mappa», 03/11/2026)
    nomi_zone = {z: _nome_zona_assistente(_zona_rif(z)) for z in [*c.zone, *([c.primo_piano] if c.primo_piano else [])]}
    inquinanti = _inquinanti_tracciati()
    if c.inquinante is not None and c.inquinante not in inquinanti:
        raise HTTPException(404, f"inquinante '{c.inquinante}' non tracciato")
    if richiesta.id_domanda_proposta is not None and richiesta.id_domanda_proposta not in {
            d["id"] for d in prompt_assistente.DOMANDE_PROPOSTE[richiesta.card]}:
        raise HTTPException(404, f"domanda proposta '{richiesta.id_domanda_proposta}' inesistente")
    r = assistente.rispondi(richiesta.card, c.model_dump(), richiesta.domanda, richiesta.id_domanda_proposta,
                            fornisci_dati=_fornisci_dati_assistente, nomi_zone=nomi_zone, inquinanti=inquinanti)
    r["fatti"] = [FattoAssistente(id=f.id, analisi=f.analisi, testo=f.testo) for f in r["fatti"]]
    return RispostaAssistente(**r)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("localhost.server.main:app", host=HOST, port=PORTA)
