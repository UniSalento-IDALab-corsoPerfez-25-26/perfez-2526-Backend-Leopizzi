"""Documenti dell'assistente (piano del modulo AI §13.2 e §13.4): l'unica base delle descrizioni. Legge i file `.md` di
localhost/rag/documenti/ (formato nel LEGGIMI.md della cartella) e sceglie le sezioni da passare al modello.

La scelta è per argomento e per parole della domanda, senza modello di embedding: il corpus è piccolo e la scelta
resta prevedibile e verificabile. I documenti con la proprietà `card` (scheda_<card>.md, 01/11/2026) descrivono una
card sola e si vedono solo quando è aperta quella card.
"""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent / "documenti"

# Elenco chiuso degli argomenti (§13.2): lo stesso del LEGGIMI.md. Un id che non è qui rende invisibile il documento.
ARGOMENTI = {
    "progetto": "che cos'è OneHealth, per chi è, che territorio copre",
    "territorio": "province, distretti socio-sanitari, comuni",
    "inquinanti": "cosa sono gli inquinanti tracciati e le loro unità di misura",
    "limiti_legge": "limiti di legge (D.Lgs. 155/2010, OMS 2021, direttiva UE 2024/2881), confronto a parità di statistica",
    "fonti_aria": "fonti dell'aria (ARPA, OpenAQ, EEA, CAMS), dato misurato e modellato, vista «Tutte»",
    "calore": "UHRI, temperatura ERA5-Land e ARPA meteo, soglie di caldo, copertura arborea, suolo impermeabile",
    "salute": "decessi ISTAT, dimissioni ospedaliere, perché i dati sono per distretto e mese",
    "dati_simulati": "dati simulati di pronto soccorso e ADI, scenari, dicitura",
    "lettura_dashboard": "come si legge la dashboard: stati N/D e null, segni, mappa, grafici, Stagionalità, salubrità",
    "limiti_analisi": "perché le relazioni sono esplorative e non causali, fattori confondenti",
    "scheda": "la scheda aperta: cosa mostra, quali dati contiene, come si legge",
    "assistente": "l'assistente stesso, ONE: cosa fa, come controlla le risposte, che domande gli si possono fare",
    "medicina_iniziativa": "lo scopo di ONE: medicina di iniziativa e riduzione dell'ospedalizzazione evitabile; leve per "
                           "organizzare i servizi (medici e infermieri di famiglia, ADI, dimissioni protette, piani per "
                           "il caldo e l'inverno), come si scelgono zone e periodi, il report delle linee d'azione",
}

MAX_SEZIONI = 4
MAX_SEZIONI_REPORT = 6  # il report delle linee d'azione (10/11/2026) attinge a più leve
# Argomenti le cui prime sezioni entrano sempre: per l'assistente, che cosa fa e le domande che gli si possono fare
# (richiesta di Matteo del 01/11/2026: l'introduzione con le domande principali).
SEZIONI_FISSE = {"assistente": 2, "medicina_iniziativa": 1}  # per la medicina di iniziativa lo scopo e i limiti (10/11/2026)
PESO_TITOLO = 3
PESO_SOGGETTO_TITOLO = 5

PAROLA = re.compile(r"[a-z0-9àèéìòù]+(?:[.,]\d+)?")
VUOTE = {"che", "cos", "cosa", "come", "con", "del", "della", "dei", "delle", "dal", "dalla", "nel", "nella", "per",
         "una", "uno", "sono", "questo", "questa", "quello", "quella", "quale", "quali", "quanto", "quanti", "dove",
         "perché", "anche", "più", "non", "gli", "le", "il", "lo", "la", "mi", "si", "vuol", "dire", "significa"}


@dataclass(frozen=True)
class Sezione:
    documento: str  # nome del file, es. «inquinanti.md»
    titolo: str
    testo: str
    argomenti: tuple[str, ...]
    soggetti: tuple[str, ...]
    card: str | None = None  # la card che il documento descrive (scheda_<card>.md); None = vale per tutte


def _lista(valore):
    """«[a, b, c]» della testata → ("a", "b", "c")."""
    return tuple(v.strip() for v in valore.strip().strip("[]").split(",") if v.strip())


def _leggi(percorso: Path):
    righe = percorso.read_text(encoding="utf-8").splitlines()
    if not righe or righe[0].strip() != "---":
        return []
    fine = righe.index("---", 1)
    testata = dict(r.split(":", 1) for r in righe[1:fine] if ":" in r)
    argomenti = tuple(a for a in _lista(testata.get("argomenti", "")) if a in ARGOMENTI)
    if not argomenti:
        return []
    soggetti = _lista(testata.get("soggetti", ""))
    card = testata.get("card", "").strip() or None
    sezioni, titolo, corpo = [], None, []
    for riga in righe[fine + 1:] + ["## "]:  # la sentinella chiude l'ultima sezione
        if riga.startswith("## "):
            if titolo and " ".join(corpo).strip():
                sezioni.append(Sezione(percorso.name, titolo, " ".join(corpo).strip(), argomenti, soggetti, card))
            titolo, corpo = riga[3:].strip(), []
        elif titolo and not riga.startswith("# "):
            corpo.append(riga.strip())
    return sezioni


@cache
def sezioni():
    """Tutte le sezioni dei documenti visibili all'assistente (il LEGGIMI.md è escluso). Lette una volta: dopo aver
    modificato un documento si riavvia il server."""
    return tuple(s for p in sorted(CARTELLA.glob("*.md")) if p.name != "LEGGIMI.md" for s in _leggi(p))


def _radici(testo):
    """Parole significative ridotte alle prime 6 lettere, una radice grezza che unisce singolare e plurale
    («modellato», «modellati»). Le sigle con cifre restano intere («pm2.5», «no2»)."""
    parole = PAROLA.findall(testo.lower())
    return {p if any(c.isdigit() for c in p) else p[:6] for p in parole
            if p not in VUOTE and (len(p) > 2 or any(c.isdigit() for c in p))}


def _nomina(soggetto, testo):
    """Il soggetto compare come parola intera; le sigle brevi («CO», «O3») solo in maiuscolo, per non confondere
    «CO» con «cos'è»."""
    return re.search(rf"(?<!\w){re.escape(soggetto)}(?!\w)", testo, 0 if len(soggetto) <= 3 else re.IGNORECASE)


def scegli(argomenti, domanda, extra_soggetti=(), massimo=MAX_SEZIONI, card=None):
    """Le sezioni dei documenti di quegli argomenti più vicine alla domanda: parole in comune (il titolo pesa di più)
    e soggetti nominati. `extra_soggetti` aggiunge soggetti dal contesto della card (l'inquinante aperto). Se nessuna
    sezione ha parole in comune, la prima sezione di ogni documento, che lo presenta.

    `card`: la card aperta. Le sezioni di un'altra card non si vedono; con l'argomento «scheda» la descrizione della
    card aperta entra tutta (cosa mostra, quali dati, come si legge), prima delle altre sezioni; con gli altri argomenti
    concorre con le loro sezioni."""
    visibili = [s for s in sezioni() if s.card in (None, card)]
    fisse = [s for s in visibili if "scheda" in argomenti and "scheda" in s.argomenti and s.card == card]
    for a, n in SEZIONI_FISSE.items():
        if a in argomenti:
            fisse += [s for s in visibili if a in s.argomenti and s not in fisse][:n]
    fisse = fisse[:massimo]
    altri = [a for a in argomenti if a != "scheda"]
    if not altri or len(fisse) >= massimo:
        return fisse
    # la descrizione della card aperta concorre sempre, anche se l'instradamento ha scelto un altro argomento: una
    # domanda come «perché i comuni non compaiono nei grafici?» ha la risposta lì (prova del 01/11/2026)
    candidate = [s for s in visibili if (set(s.argomenti) & set(altri) or (card and s.card == card)) and s not in fisse]
    return fisse + _per_punteggio(candidate, domanda, extra_soggetti, massimo - len(fisse))


def _per_punteggio(candidate, domanda, extra_soggetti, massimo):
    q = _radici(domanda)
    nominati = {sog for s in candidate for sog in s.soggetti if _nomina(sog, domanda)} | set(extra_soggetti)

    def punteggio(s: Sezione):
        p = PESO_TITOLO * len(q & _radici(s.titolo)) + len(q & _radici(s.testo))
        for sog in nominati:
            if _nomina(sog, s.titolo):
                p += PESO_SOGGETTO_TITOLO
            elif _nomina(sog, s.testo):
                p += 1
        return p

    punteggi = [(punteggio(s), i, s) for i, s in enumerate(candidate)]
    scelte = [s for p, _, s in sorted(punteggi, key=lambda t: (-t[0], t[1])) if p > 0][:massimo]
    if not scelte:
        visti = set()
        scelte = [s for s in candidate if not (s.documento in visti or visti.add(s.documento))][:massimo]
    return scelte
