"""Perimetro dell'assistente, prima della risposta (piano del modulo AI §13.1, passi 1-3):

1. filtro nel codice: domanda vuota, troppo lunga o che cerca di cambiare le regole → rifiuto senza chiamare il modello;
2. instradamento con Qwen (temperatura 0, risposta vincolata dallo schema): analisi, descrizione o nessuno;
3. controllo dei parametri nel codice: quelli mancanti vengono dal contesto della card.

Ogni uscita negativa è il rifiuto fisso (config.RIFIUTO), scritto dal codice: qui si decide solo il motivo, che finisce
nel report della prova (§12.5) e non nell'interfaccia.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from localhost.rag import config, ollama, prompt

# Frasi che cercano di cambiare le regole, di farsi ripetere le istruzioni o di cambiare ruolo. Si confrontano sul
# testo in minuscolo e senza accenti. Un rifiuto sbagliato su una domanda lecita si corregge qui (§12.5).
AGGIRAMENTI = [
    r"\bignora\w*\b", r"\bdimentica\w*\b", r"\bistruzion\w*", r"\bprompt\b", r"\bsystem\b", r"\bjailbreak\b",
    r"\bfai finta\b", r"\bfingi\w*\b", r"\bimmagina di essere\b", r"\b(?:da )?ora sei\b", r"\bsei ora\b",
    r"\b(?:agisci|comportati|rispondi) come\b", r"\bmodalita (?:sviluppatore|developer|dan)\b",
    r"\b(?:ripeti|mostra\w*|scrivi\w*|rivela\w*|dimmi) (?:le |il |i )?(?:tue |tuo |tuoi )?(?:regole|messaggi)\b",
    r"\bnuove regole\b", r"\bsenza (?:regole|limiti|filtri)\b", r"\bcambia\w* (?:le )?regole\b",
    r"</?\s*domanda\s*>", r"```",
]
_AGGIRAMENTI = [re.compile(p) for p in AGGIRAMENTI]
MESE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
# Una descrizione che chiede anche come va il dato della card («che inquinante è e come si comporta?»): il modello la
# manda fra le sole descrizioni anche con le istruzioni e gli esempi (prova del 31/10/2026), il codice aggiunge le
# analisi della domanda proposta «come_va».
ANDAMENTO = re.compile(r"come si comport|com'e andat|come (?:va|sta andando)|andamento|come si muove")
# Domande sulla card aperta o sull'assistente stesso, ONE (01/11/2026, richiesta di Matteo): vanno all'argomento senza
# chiedere al modello, così non dipendono da come il modello legge l'elenco. Si confrontano sul testo normalizzato
# (minuscolo, senza accenti); le domande su un argomento preciso («come si legge il limite OMS?») non ci cadono.
OGGETTO = r"(?:questo|questa|questi|queste|qui|il grafico|la scheda|la tabella|il blocco|la card|la sezione)"
SCHEDA = re.compile(r"cosa sto (?:guardando|vedendo)|^\W*descrizione\W*$|^\W*descrivi\w*(?: " + OGGETTO + r"(?: \w+)?)?\W*$"
                    r"|(?:cosa|che cosa) (?:mostra|rappresenta|contiene) " + OGGETTO
                    + r"|come si legg\w* " + OGGETTO + r"|^\W*come si legge\W*$|(?:che|quali) dati (?:ci sono|contiene|mostra|usa)"
                    r"|di cosa si tratta|cos'e (?:questo|questa) (?:grafico|scheda|tabella|blocco|card|sezione)?\W*$"
                    r"|a cosa serve " + OGGETTO)
ASSISTENTE = re.compile(r"^\W*chi sei\b|come funzion\w*\b.*\b(?:assistente|chat|one)\b|^\W*come funzioni\b"
                        r"|cosa (?:sai|puoi) fare|che (?:cosa|domande) (?:ti )?posso (?:chied|fa)\w*"
                        r"|cosa (?:ti )?posso chied\w*|come (?:si usa|uso) (?:l'assistente|la chat|questa chat)"
                        r"|(?:cos'e|cosa fa|chi e) (?:l'assistente|questa chat|la chat|one)\b|come ti chiami|come controlli le risposte")
CALDO = re.compile(r"temperatur|cald|gradi|°|\bfredd|\bfresc|\bafa\b|canicol|\bt ?max\b")
CONFRONTO_DISTRETTI = re.compile(r"\b(?:quale|quali|che|chi)\b.{0,40}\bdistrett|\bfra i distretti\b|\bdistretto peggiore\b")
DECESSI = re.compile(r"decess|mortalit|\bmort[ie]\b|\bmuor")
ARIA = re.compile(r"\baria\b|inquinant|\bco\b|monossido|\bno2\b|azoto|\bo3\b|ozono|pm ?2[.,]?5|polver|particolat|\bso2\b|zolfo")
# Indicatori della Stagionalità nominati nella domanda (testo normalizzato): li riconosce il codice, non il modello, così
# una domanda che non ne nomina nessuno resta sull'indicatore della card (01/11/2026, passo 8).
NOMI_INDICATORI = {
    "aria:CO": r"\bco\b|monossido", "aria:NO2": r"\bno2\b|biossido di azoto|ossidi di azoto",
    "aria:O3": r"\bo3\b|ozono", "aria:PM2.5": r"pm ?2[.,]?5|polveri sottili|particolato",
    "aria:SO2": r"\bso2\b|biossido di zolfo|anidride solforosa", "aria": r"aria complessiva|qualita dell'aria",
    "calore": CALDO.pattern, "decessi": DECESSI.pattern, "pronto_soccorso": r"pronto soccorso|\bps\b",
    "adi_accessi_ps": r"\badi\b|domicil", "ricoveri_respiratori": r"ricover",
}
_NOMI_INDICATORI = {k: re.compile(v) for k, v in NOMI_INDICATORI.items()}
# Domini nominati nella domanda sulle card istantanee (schede_istantanee.py, 03/11/2026): filtrano i fatti come gli
# indicatori della Stagionalità. Li riconosce il codice; con più domini nominati non si filtra.
NOMI_DOMINI = {
    "aria": ARIA.pattern, "salubrita": r"salubr|\bband[ae]\b", "calore": CALDO.pattern,
    "alberi": r"\balber|chioma|arbore|\bverde\b", "suolo": r"\bsuol|impermeab|cemento|asfalt",
    "decessi": DECESSI.pattern, "ricoveri": r"ricover|dimission",
    "simulati": r"pronto soccorso|\bps\b|\badi\b|simulat", "territorio": r"resident|abitant|popolazion|\bstazion",
}
_NOMI_DOMINI = {k: re.compile(v) for k, v in NOMI_DOMINI.items()}
# Il report delle linee d'azione sul sommario «Quando intervenire» (10/11/2026): quando, quanto e dove.
ANALISI_REPORT = ("stagionalita", "ospedalizzazione", "priorita_zone")
ANALISI_INIZIATIVA = {"ospedalizzazione", "priorita_zone"}
# Correzione della batteria del 10/11/2026 (gruppo medicina_iniziativa), sul testo normalizzato: «dove…», «quali
# zone/distretti/comuni…» vogliono la classifica (il modello sceglieva solo «ospedalizzazione»). Il quartiere no: lo
# instradava bene, lo fermava la risposta (regola 2b di prompt.ISTRUZIONI_RISPOSTA); forzarlo dal codice farebbe
# passare anche «i nomi degli assistiti del quartiere X».
DOVE = re.compile(r"^\W*dove\b|\bin quali? (?:zon|distrett|comun)|\bquali? (?:zon|distrett|comun)")
NOMI_MESI = re.compile(r"\b(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\b")


@dataclass
class Instradamento:
    tipo: str  # analisi | descrizione | nessuno
    analisi: list[str] = field(default_factory=list)
    argomenti: list[str] = field(default_factory=list)
    parametri: dict = field(default_factory=dict)


class Rifiuto(Exception):
    """Domanda fuori perimetro. `barriera`: filtro, instradamento o parametri; `motivo`: per il report, non per
    l'utente, che vede sempre config.RIFIUTO."""

    def __init__(self, barriera, motivo):
        super().__init__(motivo)
        self.barriera, self.motivo = barriera, motivo


def _normalizza(testo):
    senza_accenti = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", senza_accenti.lower())


def filtra(domanda):
    """Barriera del codice, prima del modello. Restituisce la domanda ripulita o solleva Rifiuto."""
    testo = (domanda or "").strip()
    if not testo:
        raise Rifiuto("filtro", "domanda vuota")
    if len(testo) > config.LUNGHEZZA_MAX_DOMANDA:
        raise Rifiuto("filtro", f"domanda oltre {config.LUNGHEZZA_MAX_DOMANDA} caratteri")
    norm = _normalizza(testo)
    for p in _AGGIRAMENTI:
        if p.search(norm):
            raise Rifiuto("filtro", f"tentativo di cambiare le regole ({p.pattern})")
    return testo


def instrada(domanda, card, contesto, nomi_zone, inquinanti):
    """Chiede al modello a quale voce dell'elenco chiuso appartiene la domanda. Restituisce l'Instradamento e i tempi
    della chiamata; solleva Rifiuto se la voce è «nessuno» o la risposta non è leggibile, OllamaNonDisponibile se il
    modello non risponde. Le domande sulla card aperta o sull'assistente non passano dal modello (SCHEDA, ASSISTENTE)."""
    norm = _normalizza(domanda.replace("’", "'"))  # prima della normalizzazione, che toglierebbe l'apostrofo curvo
    if ASSISTENTE.search(norm):
        return Instradamento("descrizione", [], ["assistente"], {}), 0.0
    if SCHEDA.search(norm):
        return Instradamento("descrizione", [], ["scheda"], {}), 0.0
    if prompt.e_report(card, domanda):
        # il report delle linee d'azione (10/11/2026) vuole sempre quando, dove e cosa: lo instrada il codice
        return Instradamento("analisi", list(ANALISI_REPORT), ["medicina_iniziativa"], {}), 0.0
    schema = prompt.schema_instradamento(list(nomi_zone), inquinanti, card)
    if card == "dettaglio_mese" and mese_nominato(domanda):
        # la tabella è su luglio e la domanda su gennaio: con «mese luglio» nella scheda il modello la dava fuori
        # elenco (prova del 01/11/2026); il mese lo sceglie comunque il codice (_parametri_stagione)
        contesto = {**contesto, "mese_dell_anno": mese_nominato(domanda)}
    r = ollama.chat(prompt.messaggi_instradamento(domanda, card, contesto, nomi_zone), schema=schema,
                    opzioni={"temperature": 0, "num_predict": config.NUM_PREDICT_INSTRADAMENTO})
    d = prompt.leggi_json(r["testo"])
    if d is None:
        raise Rifiuto("instradamento", f"risposta non leggibile: {r['testo'][:200]!r}")
    tipo = d.get("tipo")
    analisi = [a for a in d.get("analisi") or [] if a in prompt.ANALISI_CARD[card]]
    argomenti = [a for a in d.get("argomenti") or [] if a in prompt.argomenti_card(card)]
    parametri = {k: d.get(k) for k in schema["properties"] if k not in ("tipo", "analisi", "argomenti")}
    if tipo == "analisi" and not analisi:
        raise Rifiuto("instradamento", "analisi senza un'analisi del catalogo")
    if tipo == "descrizione" and not argomenti:
        raise Rifiuto("instradamento", "descrizione senza un argomento dell'elenco")
    if tipo not in ("analisi", "descrizione"):
        raise Rifiuto("instradamento", "fuori dall'elenco chiuso")
    if (tipo == "analisi" and card == "domini" and len(nomi_zone) >= 2 and "classifica_zone" not in analisi
            and CONFRONTO_DISTRETTI.search(norm)):
        analisi = [*analisi, "classifica_zone"][-3:]  # «quale distretto ha il PM2.5 più alto?» andava su «estremi»
    if card == "consiglio" and tipo == "analisi":
        if "ospedalizzazione" in analisi and "priorita_zone" not in analisi and DOVE.search(norm):
            analisi = [*analisi, "priorita_zone"][-3:]
        if set(analisi) & ANALISI_INIZIATIVA and "medicina_iniziativa" not in argomenti:
            argomenti = [*argomenti, "medicina_iniziativa"][-2:]  # i numeri senza le leve non rispondono allo scopo
    if tipo == "descrizione":
        analisi = []
        if card == "andamento" and ANDAMENTO.search(norm):
            tipo, analisi = "analisi", list(next(d for d in prompt.DOMANDE_PROPOSTE["andamento"]
                                                 if d["id"] == "come_va")["instradamento"]["analisi"])
    return Instradamento(tipo, analisi, argomenti, parametri), r["totale_s"]


def _zone(p, contesto):
    zone = [z for z in p.get("zone") or [] if z and not (z == prompt.ZONA_SALENTO and not contesto["zone"])]
    if prompt.ALTRA_ZONA in zone:
        raise Rifiuto("parametri", "zona non fra quelle della card")
    if any(z not in contesto["zone"] for z in zone):
        raise Rifiuto("parametri", f"zone sconosciute: {zone}")
    return zone


def _inquinante(p, contesto, inquinanti):
    inquinante = (p.get("inquinante") or "").strip() or contesto["inquinante"]
    if inquinante not in inquinanti:
        raise Rifiuto("parametri", f"inquinante non tracciato: {inquinante!r}")
    return inquinante


def _verso(p):
    return p.get("verso") if p.get("verso") in ("alti", "bassi") else "alti"


def indicatore_nominato(domanda):
    """L'id dell'indicatore della Stagionalità che la domanda nomina, o "" se non ne nomina uno solo. «Accessi in PS
    degli assistiti ADI» nomina l'ADI, non il pronto soccorso."""
    norm = _normalizza(domanda or "").replace("’", "'")
    trovati = {k for k, r in _NOMI_INDICATORI.items() if r.search(norm)}
    if "adi_accessi_ps" in trovati:
        trovati.discard("pronto_soccorso")
    return trovati.pop() if len(trovati) == 1 else ""


def dominio_nominato(domanda):
    """Il dominio (aria, calore, decessi…) che la domanda nomina, o "" se non ne nomina uno solo. «Ricoveri simulati»
    sono i simulati, non le dimissioni ISTAT."""
    norm = _normalizza(domanda or "").replace("’", "'")
    trovati = {k for k, r in _NOMI_DOMINI.items() if r.search(norm)} | ({"calore"} if "°" in (domanda or "") else set())
    if "simulati" in trovati:
        trovati.discard("ricoveri")
    return trovati.pop() if len(trovati) == 1 else ""


def mese_nominato(domanda):
    """Il mese dell'anno (1-12) che la domanda nomina, se ne nomina uno solo."""
    trovati = set(NOMI_MESI.findall(_normalizza(domanda or "")))
    return prompt.MESI.index(trovati.pop()) + 1 if len(trovati) == 1 else None


def controlla_parametri(card, ins: Instradamento, contesto, inquinanti, domanda=""):
    """Parametri dell'analisi: quelli che la domanda non dà vengono dalla card; uno non valido è un rifiuto.
    Che il periodo sia davvero in archivio lo controlla chi fornisce i dati (assistente.py)."""
    famiglia = prompt.famiglia(card)
    if famiglia == "domini":
        return _parametri_domini(ins, contesto, inquinanti, domanda)
    if famiglia == "stagione":
        return _parametri_stagione(card, ins, contesto, domanda)
    if famiglia == "istantanea":
        return _parametri_istantanea(ins, contesto, domanda)
    p = ins.parametri
    zone = _zone(p, contesto)
    mese = (p.get("mese") or "").strip() or contesto["mese"]
    if not MESE.match(mese):
        raise Rifiuto("parametri", f"mese non valido: {mese!r}")
    inquinante = _inquinante(p, contesto, inquinanti)
    soglia = p.get("soglia")
    if soglia is not None and (not isinstance(soglia, (int, float)) or isinstance(soglia, bool) or soglia < 0):
        raise Rifiuto("parametri", f"soglia non valida: {soglia!r}")
    variabile = p.get("variabile") if p.get("variabile") in prompt.VARIABILI else "inquinante"
    if variabile != "inquinante" and not CALDO.search(domanda.lower()):  # «°» non sopravvive a _normalizza
        variabile = "inquinante"  # la card è il grafico dell'inquinante: «sopra 18» senza unità non è la temperatura
    ins.parametri = {"variabile": variabile, "zone": zone or list(contesto["zone"]), "mese": mese,
                     "inquinante": inquinante, "fonte": contesto["fonte"], "soglia": soglia, "verso": _verso(p)}
    return ins


def _parametri_domini(ins: Instradamento, contesto, inquinanti, domanda):
    """«domini»: il periodo è quello della card (da → mese). Il caldo (03/11/2026) lo riconosce il codice: una domanda
    sulla temperatura che non parla dell'aria ha la temperatura come variabile e come esposizione della relazione coi
    decessi. La variabile è «decessi» solo se la domanda li nomina e non parla né dell'aria né del caldo (o il modello
    li ha scelti e la domanda li nomina)."""
    p = ins.parametri
    zone = _zone(p, contesto)
    if not (MESE.match(contesto.get("da") or "") and MESE.match(contesto.get("mese") or "")):
        raise Rifiuto("parametri", "periodo della card mancante")
    norm = _normalizza(domanda)
    aria = ARIA.search(norm)
    caldo = not aria and bool(CALDO.search(norm) or "°" in domanda)  # «°» non sopravvive a _normalizza
    decessi = DECESSI.search(norm) and not caldo and (p.get("variabile") == "decessi" or not aria)
    ins.parametri = {"variabile": "decessi" if decessi else "temperatura" if caldo else "inquinante",
                     "esposizione": "temperatura" if caldo else "inquinante", "zone": zone or list(contesto["zone"]),
                     "da": contesto["da"], "mese": contesto["mese"], "inquinante": _inquinante(p, contesto, inquinanti),
                     "fonte": contesto["fonte"], "statistica_calore": contesto.get("statistica_calore") or "massima",
                     "verso": _verso(p)}
    return ins


def _parametri_istantanea(ins: Instradamento, contesto, domanda):
    """Card istantanee (mappa, sintesi, riepilogo, fonti, ricoveri, 03/11/2026): finestra, zone, fonte e vista sono
    quelli della card (un'altra zona è un rifiuto, la zona in primo piano della carta no); il dominio nominato nella
    domanda filtra i fatti."""
    p = ins.parametri
    _zone(p, {**contesto, "zone": [*contesto["zone"], *([contesto["primo_piano"]] if contesto.get("primo_piano") else [])]})
    ins.parametri = {**contesto, "zone": list(contesto["zone"]), "verso": _verso(p),
                     "dominio": dominio_nominato(domanda)}
    return ins


def _parametri_stagione(card, ins: Instradamento, contesto, domanda):
    """Stagionalità: zona e fonte della card (un'altra zona è un rifiuto). L'indicatore nominato nella domanda
    sostituisce quello del grafico «anno su anno» e sulle altre card filtra i fatti; il mese nominato sostituisce quello
    della tabella «mese anno per anno»."""
    p = ins.parametri
    if card == "consiglio" and set(ins.analisi) & ANALISI_INIZIATIVA and re.search(r"\bsalento\b", _normalizza(domanda)):
        # «il mio distretto ha più ricoveri del Salento?»: il Salento è il termine di confronto dei fatti, non una zona
        # fuori dalla card (il modello lo dava come altra_zona, batteria del 10/11/2026)
        p = {**p, "zone": [z for z in p.get("zone") or [] if z != prompt.ALTRA_ZONA]}
    if not (card == "consiglio" and "priorita_zone" in ins.analisi):
        # la classifica delle zone (10/11/2026) contiene già tutti i distretti o i comuni dell'area: una zona o un
        # quartiere nominati non sono un rifiuto, la risposta dice fin dove arrivano i dati
        _zone(p, contesto)
    indicatore = indicatore_nominato(domanda)
    if card == "anno_su_anno":
        indicatore = indicatore or contesto.get("indicatore") or "decessi"
    mese = contesto.get("mese_dell_anno")
    if card == "dettaglio_mese":
        mese = mese_nominato(domanda) or mese
        if not mese:
            raise Rifiuto("parametri", "mese dell'anno mancante")
    ins.parametri = {"zone": list(contesto["zone"]), "fonte": contesto["fonte"], "indicatore": indicatore,
                     "mese_dell_anno": mese, "scenario": contesto.get("scenario"),
                     "simulati_nella_sintesi": contesto.get("simulati_nella_sintesi") is not False, "verso": _verso(p)}
    return ins
