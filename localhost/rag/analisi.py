"""Analisi generiche dell'assistente (piano del modulo AI §13.3): funzioni che ricevono serie nel formato comune
(serie.py) e restituiscono **fatti**, frasi in italiano con i numeri già calcolati e formattati come in dashboard.
Il modello di linguaggio non fa conti: racconta questi fatti.

Le analisi non introducono statistiche nuove dove il progetto ne ha già una: il confronto con i limiti di legge è
quello del motore di salubrità (localhost/server/salubrita.py), le soglie di caldo quelle di api/calore/soglie.py.

Fatte (passo 2): riepilogo, copertura, estremi, tendenza, anomalie, episodi, superamenti, classifica_zone, relazione;
dal passo 8 (01/11/2026) anni_precedenti. «stagionalita» non rifà i ranghi: li legge dalla tab Stagionalità
(localhost/rag/schede.py). Da fare: periodo_precedente, zona_e_riferimento, concordanza_fonti, salubrita, composizione
(servono dati oltre a quelli delle card).
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date
from statistics import mean, median

import numpy as np
import pandas as pd

from api.calore.soglie import SOGLIE as SOGLIE_CALDO
from localhost.rag.serie import Serie, ordinale
from localhost.server import salubrita

MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
        "novembre", "dicembre")
UNITA_TEMPO = {"giorno": ("giorno", "giorni"), "mese": ("mese", "mesi"), "anno": ("anno", "anni")}
QUADRO = {"dlgs_155_2010": "del D.Lgs. 155/2010", "oms_2021": "della linea guida OMS 2021",
          "ue_2024_2881": "della direttiva UE 2024/2881 (in vigore dal 2030)"}
STATISTICA_LIMITE = {"media_24h": "sulla media delle 24 ore", "massimo_orario": "orario",
                     "massimo_8h": "sul massimo della media su 8 ore", "media_annua": "sulla media annua"}

MIN_PUNTI_TENDENZA = 7
MIN_PUNTI_RELAZIONE = 12
SOGLIA_STABILE = 0.10  # ±10% della media, ±1 °C per la temperatura: la stessa regola della tab Stagionalità
SOGLIA_STABILE_GRADI = 1.0
FATTORE_ANOMALIA = 3.0  # deviazioni robuste (MAD × 1,4826) dalla mediana


class AnalisiNonApplicabile(ValueError):
    """Parametri o serie che l'analisi non può trattare: diventa il rifiuto fisso dell'assistente."""


@dataclass
class Fatto:
    analisi: str
    testo: str
    id: str = ""


# --- formattazione, come localhost/dashboard/src/lib/formato.ts ---------------------------------------------------

def numero(v):
    """Due decimali sotto 1, uno sotto 100, nessuno oltre; virgola decimale, nessun separatore delle migliaia (così
    la verifica dei numeri non confonde un punto delle migliaia con un decimale)."""
    a = abs(v)
    s = f"{v:.2f}" if a < 1 else f"{v:.1f}" if a < 100 else f"{v:.0f}"
    s = s.replace(".", ",")
    return s[1:] if s.startswith("-") and not s.strip("-0,") else s  # niente «-0,0»


def con_segno(v):
    return ("+" if v > 0 else "") + numero(v)


def percento(frazione):
    """0,232 → «+23%», come lo scarto della tab Stagionalità (percentuale intera)."""
    p = round(frazione * 100)
    return f"{'+' if p > 0 else ''}{p}%"


def elenco(voci):
    """«a», «a e b», «a, b e c»."""
    voci = [str(v) for v in voci]
    return " e ".join(voci) if len(voci) < 3 else f"{', '.join(voci[:-1])} e {voci[-1]}"


def con_unita(v, s: Serie):
    return f"{numero(v)} {s.unita}" if s.unita else numero(v)


def quando(tempo, grana):
    """«15 luglio 2024», «1° luglio 2024», «luglio 2024», «2024»."""
    if grana == "giorno":
        d = date.fromisoformat(tempo)
        return f"{d.day}{'°' if d.day == 1 else ''} {MESI[d.month - 1]} {d.year}"
    if grana == "mese":
        return f"{MESI[int(tempo[5:7]) - 1]} {tempo[:4]}"
    return tempo[:4]


def _elide(tempo, grana):
    """8 e 11 si leggono «otto» e «undici»: vogliono l'articolo eliso («l'8», «dall'11»)."""
    return grana == "giorno" and date.fromisoformat(tempo).day in (8, 11)


def il_(tempo, grana):
    """Con la preposizione giusta: «il 15 luglio 2024», «l'11 luglio 2024», «a luglio 2024», «ad agosto 2024», «nel 2024»."""
    if grana == "giorno":
        return ("l'" if _elide(tempo, grana) else "il ") + quando(tempo, grana)
    if grana == "mese":
        return ("ad " if quando(tempo, grana).startswith("a") else "a ") + quando(tempo, grana)
    return "nel " + quando(tempo, grana)


def dal_al(inizio, fine, grana):
    """«dal 1° luglio 2024 al 31 luglio 2024», «dall'8 … all'11 …», «da luglio 2024 a ottobre 2024»."""
    if grana == "mese":
        return f"da {quando(inizio, grana)} a {quando(fine, grana)}"
    da = "dall'" if _elide(inizio, grana) else "dal "
    a = "all'" if _elide(fine, grana) else "al "
    return f"{da}{quando(inizio, grana)} {a}{quando(fine, grana)}"


def unita_tempo(n, grana):
    singolare, plurale = UNITA_TEMPO[grana]
    return f"{n} {singolare if n == 1 else plurale}"


def _testa(s: Serie):
    return f"{s.zona}, {s.variabile}"


# --- descrivere una serie ------------------------------------------------------------------------------------------

def riepilogo(s: Serie):
    v = s.validi()
    if not v:
        return [Fatto("riepilogo", f"{_testa(s)}: nessun valore nel periodo ({unita_tempo(len(s.punti), s.grana)}).")]
    valori = [p.valore for p in v]
    pmax = max(v, key=lambda p: p.valore)
    pmin = min(v, key=lambda p: p.valore)
    return [
        Fatto("riepilogo", f"{_testa(s)}: media {con_unita(mean(valori), s)} e mediana {con_unita(median(valori), s)}, "
                           f"su {unita_tempo(len(v), s.grana)} con valore su {len(s.punti)}."),
        Fatto("riepilogo", f"{_testa(s)}: valore più alto {con_unita(pmax.valore, s)} {il_(pmax.tempo, s.grana)}, "
                           f"più basso {con_unita(pmin.valore, s)} {il_(pmin.tempo, s.grana)}."),
    ]


def copertura(s: Serie):
    conta = Counter(p.stato if p.stato != "VALORE" or p.valore is not None else "NULL" for p in s.punti)
    natura = {"misurato": "un dato misurato dalle stazioni", "modellato": "un dato modellato, non misurato",
              "misto": "un dato in parte misurato dalle stazioni e in parte modellato (CAMS)",
              "simulato": "un dato simulato, non reale", "reale": "un dato reale (conteggi ufficiali)"}[s.natura]
    fatti = [Fatto("copertura", f"{_testa(s)}: {unita_tempo(conta['VALORE'], s.grana)} con valore, "
                                f"{conta['NULL']} non utilizzabili (null) e {conta['NO_DATA']} non disponibili (N/D), "
                                f"su {len(s.punti)}."),
             Fatto("copertura", f"{_testa(s)} è {natura}; fonte: "
                                f"{'vista «Tutte» (fonti concordi)' if s.fonte == 'Tutte' else s.fonte}.")]
    for stato, nome in (("NO_DATA", "dei valori non disponibili"), ("NULL", "dei valori non utilizzabili")):
        note = Counter(p.nota for p in s.punti if p.stato == stato and p.nota)
        if note:
            fatti.append(Fatto("copertura", f"{_testa(s)}: motivo più frequente {nome}: {note.most_common(1)[0][0]}."))
    return fatti


def estremi(s: Serie, k=3, verso="alti"):
    v = s.validi()
    if not v:
        return [Fatto("estremi", f"{_testa(s)}: nessun valore nel periodo.")]
    ordinati = sorted(v, key=lambda p: p.valore, reverse=verso == "alti")[:k]
    elenco = "; ".join(f"{quando(p.tempo, s.grana)} con {con_unita(p.valore, s)}" for p in ordinati)
    chi = UNITA_TEMPO[s.grana][1] if len(ordinati) > 1 else UNITA_TEMPO[s.grana][0]
    return [Fatto("estremi", f"{_testa(s)}: {'i' if len(ordinati) > 1 else 'il'} {len(ordinati)} {chi} "
                             f"con il valore più {'alto' if verso == 'alti' else 'basso'}: {elenco}.")]


def _theil_sen(xs, ys):
    pendenze = [(ys[j] - ys[i]) / (xs[j] - xs[i]) for i in range(len(xs)) for j in range(i + 1, len(xs)) if xs[j] != xs[i]]
    return median(pendenze)


def tendenza(s: Serie):
    v = s.validi()
    if len(v) < MIN_PUNTI_TENDENZA:
        return [Fatto("tendenza", f"{_testa(s)}: troppo pochi valori per una tendenza "
                                  f"({unita_tempo(len(v), s.grana)}, ne servono almeno {MIN_PUNTI_TENDENZA}).")]
    xs = [ordinale(p.tempo, s.grana) for p in v]
    ys = [p.valore for p in v]
    variazione = _theil_sen(xs, ys) * (xs[-1] - xs[0])
    soglia = SOGLIA_STABILE_GRADI if s.temperatura else SOGLIA_STABILE * abs(mean(ys))
    criterio = "±1 °C" if s.temperatura else "±10% della media"
    if abs(variazione) <= soglia:
        verso = "stabile"
    else:
        verso = "in crescita" if variazione > 0 else "in calo"
    return [Fatto("tendenza", f"{_testa(s)}: andamento {verso} nel periodo, con una variazione stimata di "
                              f"{con_segno(variazione)}{' ' + s.unita if s.unita else ''} "
                              f"{dal_al(v[0].tempo, v[-1].tempo, s.grana)} "
                              f"(pendenza di Theil-Sen; stabile se entro {criterio}).")]


def anomalie(s: Serie, fattore=FATTORE_ANOMALIA):
    v = s.validi()
    if len(v) < MIN_PUNTI_TENDENZA:
        return [Fatto("anomalie", f"{_testa(s)}: troppo pochi valori per cercare valori insoliti.")]
    valori = [p.valore for p in v]
    med = median(valori)
    scala = 1.4826 * median(abs(x - med) for x in valori)
    insoliti = [p for p in v if scala and abs(p.valore - med) / scala > fattore]
    if not insoliti:
        return [Fatto("anomalie", f"{_testa(s)}: nessun valore insolito rispetto alla mediana di "
                                  f"{con_unita(med, s)}.")]
    elenco = "; ".join(f"{quando(p.tempo, s.grana)} con {con_unita(p.valore, s)}" for p in insoliti)
    return [Fatto("anomalie", f"{_testa(s)}: valori insoliti rispetto alla mediana di {con_unita(med, s)}: {elenco}.")]


def episodi(s: Serie, soglia, origine, inclusiva=False):
    """Sequenze di punti consecutivi oltre una soglia; un punto senza valore interrompe la sequenza."""
    sequenze, corrente = [], []
    for p in s.punti:
        if p.valido and (p.valore >= soglia if inclusiva else p.valore > soglia):
            corrente.append(p)
        elif corrente:
            sequenze.append(corrente)
            corrente = []
    if corrente:
        sequenze.append(corrente)
    segno = "almeno" if inclusiva else "oltre"
    if not sequenze:
        return [Fatto("episodi", f"{_testa(s)}: nessun {UNITA_TEMPO[s.grana][0]} {segno} {con_unita(soglia, s)} "
                                 f"({origine}).")]
    lunga = max(sequenze, key=len)
    totale = sum(len(q) for q in sequenze)
    return [Fatto("episodi", f"{_testa(s)}: {len(sequenze)} {'episodio' if len(sequenze) == 1 else 'episodi'} "
                             f"{segno} {con_unita(soglia, s)} ({origine}), {unita_tempo(totale, s.grana)} in tutto; "
                             f"il più lungo {dal_al(lunga[0].tempo, lunga[-1].tempo, s.grana)}, "
                             f"{unita_tempo(len(lunga), s.grana)} di fila.")]


def classe_scarto(delta, frazione, temperatura):
    """Stabile, in aumento o in calo: ±1 °C per la temperatura, ±10% della media per il resto (tab Stagionalità)."""
    if temperatura:
        return "in aumento" if delta > SOGLIA_STABILE_GRADI else "in calo" if delta < -SOGLIA_STABILE_GRADI else "stabile"
    if frazione is None:
        return "stabile" if delta == 0 else "in aumento" if delta > 0 else "in calo"
    return "in aumento" if frazione > SOGLIA_STABILE else "in calo" if frazione < -SOGLIA_STABILE else "stabile"


def scarto(delta, frazione, s: Serie):
    """«+1,3 °C» per la temperatura, «+23%» per il resto (o la differenza assoluta se la media è zero)."""
    if s.temperatura or frazione is None:
        return f"{con_segno(delta)}{' ' + s.unita if s.unita else ''}"
    return percento(frazione)


def anni_precedenti(s: Serie):
    """L'ultimo punto con valore contro la media dei punti con valore che lo precedono. La serie è lo stesso periodo in
    anni diversi (luglio 2024, luglio 2025, luglio 2026, grana «anno»): è la Δ della tabella «mese anno per anno», con
    la stessa regola della tab Stagionalità; con un solo anno precedente il confronto è indicativo."""
    v = s.validi()
    if len(v) < 2:
        return [Fatto("anni_precedenti", f"{_testa(s)}: servono almeno due anni con un valore per il confronto con "
                                         f"gli anni precedenti ({unita_tempo(len(v), 'anno')}).")]
    ultimo, prima = v[-1], v[:-1]
    media = mean(p.valore for p in prima)
    delta = ultimo.valore - media
    frazione = delta / media if media else None
    criterio = "±1 °C" if s.temperatura else "±10%"
    indicativo = "; indicativo, con un solo anno precedente" if len(prima) == 1 else ""
    anni = (il_(prima[0].tempo, s.grana) if len(prima) == 1
            else f"negli anni {elenco(quando(p.tempo, s.grana) for p in prima)}")
    return [Fatto("anni_precedenti", f"{_testa(s)}: {il_(ultimo.tempo, s.grana)} {con_unita(ultimo.valore, s)} contro "
                                     f"una media di {con_unita(media, s)} {anni}: {scarto(delta, frazione, s)}, "
                                     f"{classe_scarto(delta, frazione, s.temperatura)} (fascia di stabilità "
                                     f"{criterio}){indicativo}.")]


# --- soglie e limiti ----------------------------------------------------------------------------------------------

def _superamenti_soglia(s: Serie, soglia, origine, inclusiva):
    v = s.validi()
    oltre = [p for p in v if (p.valore >= soglia if inclusiva else p.valore > soglia)]
    return Fatto("superamenti", f"{_testa(s)}: {unita_tempo(len(oltre), s.grana)} su {len(v)} con valore "
                                f"{'almeno' if inclusiva else 'oltre'} {con_unita(soglia, s)} ({origine}).")


def superamenti(s: Serie, soglia=None):
    """Senza soglia: limiti di legge a parità di statistica (motore di salubrità) per l'aria, soglie di caldo del
    progetto per la temperatura. Con una soglia: quella scelta dall'utente, dichiarata come tale."""
    if not s.validi():
        return [Fatto("superamenti", f"{_testa(s)}: nessun valore da confrontare con una soglia.")]
    if soglia is not None:
        return [_superamenti_soglia(s, soglia, "soglia scelta dall'utente", inclusiva=False)]
    if s.temperatura:
        stat = s.variabile.removeprefix("temperatura ").strip()
        # descrizione di api/calore/soglie.py senza la parte inglese: «giornata calda (summer/hot day): …» → «giornata calda»
        return [_superamenti_soglia(s, valore, f"soglia di caldo del progetto: {descr.split(':')[0].split(' (')[0]}",
                                    inclusiva=True)
                for statistica_soglia, valore, descr in SOGLIE_CALDO.values() if statistica_soglia == stat] or \
               [Fatto("superamenti", f"{_testa(s)}: nessuna soglia di caldo del progetto per questa statistica.")]
    if s.grana != "giorno":
        raise AnalisiNonApplicabile("i limiti di legge si confrontano con valori giornalieri")
    esito = salubrita.valuta_inquinante(s.variabile, [{"fonte": s.fonte, "statistica": s.statistica,
                                                      "valori": [p.valore for p in s.validi()]}])
    if esito is None:
        return [Fatto("superamenti", f"{_testa(s)}: il progetto non ha limiti di legge per questo inquinante.")]
    if not esito["esiti"]:
        return [Fatto("superamenti", f"{_testa(s)}: non confrontabile con i limiti di legge, perché la statistica "
                                     f"del dato ({s.statistica}) non è quella su cui sono definiti i limiti.")]
    fatti = []
    for e in esito["esiti"]:
        limite = f"{numero(e['limite'])} {e['unita']}"
        quadro = f"{STATISTICA_LIMITE.get(e['statistica'], e['statistica'])} {QUADRO[e['quadro']]}"
        if e["tipo"] == "giorni_superamento":
            ammessi = (f"; la legge ne ammette {e['superamenti_ammessi_anno']} all'anno"
                       if e.get("superamenti_ammessi_anno") else "")
            fatti.append(Fatto("superamenti", f"{_testa(s)}: {unita_tempo(e['giorni_superamento'], 'giorno')} su "
                                              f"{e['giorni_con_valore']} oltre il limite di {limite} {quadro}{ammessi}."))
        else:
            fatti.append(Fatto("superamenti", f"{_testa(s)}: media del periodo {con_unita(e['valore'], s)} contro il "
                                              f"limite di {limite} {quadro}; confronto solo indicativo, perché il "
                                              f"periodo è più breve di un anno."))
    return fatti


# --- zone e relazioni ---------------------------------------------------------------------------------------------

def classifica_zone(serie: list[Serie]):
    if len(serie) < 2:
        raise AnalisiNonApplicabile("la classifica richiede almeno due zone")
    if len({(s.variabile, s.unita) for s in serie}) > 1:
        raise AnalisiNonApplicabile("le zone vanno confrontate sulla stessa variabile")
    medie = sorted(((mean(p.valore for p in s.validi()), s) for s in serie if s.validi()), key=lambda m: -m[0])
    senza = [s.zona for s in serie if not s.validi()]
    if len(medie) < 2:
        return [Fatto("classifica_zone", "Meno di due zone hanno valori nel periodo: nessuna classifica.")]
    s0 = medie[0][1]
    elenco = "; ".join(f"{i}. {s.zona} {con_unita(m, s)}" for i, (m, s) in enumerate(medie, 1))
    fatti = [Fatto("classifica_zone", f"Classifica delle zone per {s0.variabile} medio nel periodo: {elenco}."),
             Fatto("classifica_zone", f"Fra {medie[0][1].zona} e {medie[-1][1].zona} la differenza è di "
                                      f"{con_unita(medie[0][0] - medie[-1][0], s0)}.")]
    if senza:
        fatti.append(Fatto("classifica_zone", f"Senza valori nel periodo, fuori classifica: {', '.join(senza)}."))
    return fatti


def _spearman(x, y):
    return float(np.corrcoef(pd.Series(x).rank(), pd.Series(y).rank())[0, 1])


def forza(rho):
    a = abs(rho)
    return "trascurabile" if a < 0.1 else "debole" if a < 0.3 else "moderata" if a < 0.5 else "forte"


def relazione(a: Serie, b: Serie, ritardo_max=None):
    """Correlazione di rango (Spearman) fra due serie della stessa zona e grana, anche con b in anticipo su a di
    0..ritardo_max unità di tempo. Esplorativa: l'avvertenza la aggiunge chi compone la scheda."""
    if a.zona_id != b.zona_id or a.grana != b.grana:
        raise AnalisiNonApplicabile("la relazione si calcola fra due serie della stessa zona e della stessa grana")
    if ritardo_max is None:
        ritardo_max = 5 if a.grana == "giorno" else 1
    va = {ordinale(p.tempo, a.grana): p.valore for p in a.validi()}
    vb = {ordinale(p.tempo, b.grana): p.valore for p in b.validi()}
    risultati = []
    for r in range(ritardo_max + 1):
        coppie = [(x, vb[o - r]) for o, x in va.items() if o - r in vb]
        if len(coppie) >= MIN_PUNTI_RELAZIONE:
            risultati.append((r, _spearman(*zip(*coppie)), len(coppie)))
    unita = UNITA_TEMPO[a.grana]
    if not risultati or risultati[0][0] != 0:
        return [Fatto("relazione", f"{a.zona}: troppo pochi {unita[1]} con entrambi i valori per mettere in "
                                   f"relazione {a.variabile} e {b.variabile} (ne servono almeno {MIN_PUNTI_RELAZIONE}).")]
    _, rho0, n0 = risultati[0]
    verso = "si muovono nello stesso verso" if rho0 > 0 else "si muovono in verso opposto"
    fatti = [Fatto("relazione", f"{a.zona}: relazione {forza(rho0)} fra {a.variabile} e {b.variabile} "
                                f"{'giorno per giorno' if a.grana == 'giorno' else 'nello stesso ' + unita[0]} "
                                f"(ρ di Spearman {numero(rho0)}, su {unita_tempo(n0, a.grana)}): "
                                f"{verso if forza(rho0) != 'trascurabile' else 'nessun legame apprezzabile'}.")]
    migliore = max(risultati, key=lambda t: abs(t[1]))
    if migliore[0] > 0 and abs(migliore[1]) - abs(rho0) >= 0.1:
        r, rho, n = migliore
        fatti.append(Fatto("relazione", f"{a.zona}: la relazione è più marcata con {b.variabile} di "
                                        f"{unita_tempo(r, a.grana)} prima (ρ {numero(rho)}, {forza(rho)}, su "
                                        f"{unita_tempo(n, a.grana)})."))
    return fatti
