"""Il percorso completo di una domanda all'assistente (piano del modulo AI §13.1):

    filtro → instradamento → controllo dei parametri → analisi e/o sezioni dei documenti → risposta → verifica

Le domande proposte della card saltano filtro e instradamento: il loro instradamento è scritto nel codice (prompt.py).
Il modulo non conosce il server: i dati della card glieli passa chi lo chiama (`fornisci_dati`), con le stesse funzioni
degli endpoint della dashboard, così aggregazioni e privacy sono già applicate.

Su una card senza scheda dei fatti (fuori da schede.CARD_CON_FATTI) si risponderebbe solo alle descrizioni: una domanda
di analisi riceve il rifiuto fisso. Dal 01/11/2026 (passo 8) tutte le card con l'assistente hanno la loro scheda; dal
03/11/2026 anche le sette card istantanee (schede_istantanee.py).

Esiti: «risposta» (testo verificato), «rifiuto» (il messaggio fisso di config.RIFIUTO), «non_verificata» (il testo
del modello non passa la verifica: si mostrano solo i fatti), «assistente_spento» (Ollama non risponde: si mostrano i
fatti calcolati, §7).
"""

import re
import time

from localhost.rag import config, corpus, ollama, prompt, schede
from localhost.rag.analisi import AnalisiNonApplicabile
from localhost.rag.perimetro import Instradamento, Rifiuto, controlla_parametri, filtra, instrada
from localhost.rag.verifica import pulisci, verifica

NOTA_SPENTO = "ONE è spento: questi sono i dati calcolati e le descrizioni della scheda, senza commento."
NOTA_NON_VERIFICATA = "La risposta del modello non ha passato la verifica: questi sono i dati calcolati."
ARGOMENTI_CON_INQUINANTE = {"inquinanti", "limiti_legge"}


def domanda_proposta(card, id_domanda):
    for d in prompt.DOMANDE_PROPOSTE.get(card, []):
        if d["id"] == id_domanda:
            return d
    raise KeyError(id_domanda)


def rispondi(card, contesto, domanda=None, id_domanda_proposta=None, *, fornisci_dati, nomi_zone, inquinanti):
    """card: una di schede.CARD; contesto: lo stato della card aperta (ContestoAssistente del server: mese, inquinante,
    fonte, zone e, secondo la card, da, indicatore, mese_dell_anno, scenario, simulati_nella_sintesi);
    fornisci_dati(card, parametri) → i dati della card nel formato di schede.py, AnalisiNonApplicabile se il periodo
    non è in archivio; nomi_zone: id → nome leggibile delle zone della card; inquinanti: id degli inquinanti tracciati."""
    inizio = time.perf_counter()
    esito = {"esito": None, "domanda": domanda, "testo": None, "citati": [], "fatti": [], "sezioni": [],
             "avvertenze": [], "instradamento": None, "fermata_da": None, "motivo": None, "modello": config.MODELLO,
             "tempi": {}}

    def chiudi(nome, **campi):
        esito.update(esito=nome, **campi)
        esito["tempi"]["totale_s"] = round(time.perf_counter() - inizio, 2)
        return esito

    def rifiuto(r: Rifiuto):
        return chiudi("rifiuto", testo=config.RIFIUTO, fatti=[], sezioni=[], avvertenze=[], citati=[],
                      fermata_da=r.barriera, motivo=r.motivo)

    def spento(motivo, ins=None):
        """Senza modello si mostra la scheda: quella dell'instradamento, se c'è, altrimenti la scheda intera (per le
        card senza fatti, la loro descrizione)."""
        if not esito["fatti"] and not esito["sezioni"] and card not in schede.CARD_CON_FATTI:
            esito["sezioni"] = _sezioni(corpus.scegli(["scheda"], "", card=card))
        elif not esito["fatti"] and not esito["sezioni"]:
            try:
                p = controlla_parametri(card, Instradamento("analisi"), contesto, inquinanti).parametri
                s = schede.scheda(card, fornisci_dati(card, p), p)
                esito.update(fatti=s["fatti"], avvertenze=s["avvertenze"])
            except (AnalisiNonApplicabile, Rifiuto):
                pass
        return chiudi("assistente_spento", testo=NOTA_SPENTO, fermata_da="modello", motivo=motivo)

    # 1-3: filtro, instradamento, parametri
    if id_domanda_proposta is not None:
        proposta = domanda_proposta(card, id_domanda_proposta)
        domanda = esito["domanda"] = proposta["testo"]
        ins = Instradamento(**proposta["instradamento"])
    else:
        try:
            domanda = esito["domanda"] = filtra(domanda)
            ins, t = instrada(domanda, card, contesto, nomi_zone, inquinanti)
            esito["tempi"]["instradamento_s"] = round(t, 2)
        except Rifiuto as r:
            return rifiuto(r)
        except ollama.OllamaNonDisponibile as e:
            return spento(str(e))
    esito["instradamento"] = {"tipo": ins.tipo, "analisi": ins.analisi, "argomenti": ins.argomenti,
                              "parametri": ins.parametri}

    # 4: esecuzione
    if ins.analisi and card not in schede.CARD_CON_FATTI:
        return rifiuto(Rifiuto("parametri", f"analisi non ancora disponibili sulla card «{card}»"))
    if ins.analisi:
        try:
            ins = controlla_parametri(card, ins, contesto, inquinanti, domanda)
            esito["instradamento"]["parametri"] = ins.parametri
            scheda = schede.fatti(card, fornisci_dati(card, ins.parametri), ins.analisi, ins.parametri)
        except Rifiuto as r:
            return rifiuto(r)
        except AnalisiNonApplicabile as e:
            return rifiuto(Rifiuto("parametri", f"analisi non eseguibile: {e}"))
        esito.update(fatti=scheda["fatti"], avvertenze=scheda["avvertenze"])
    report = prompt.e_report(card, domanda)
    if ins.argomenti:
        esito["sezioni"] = _sezioni(corpus.scegli(ins.argomenti, domanda, _soggetti_dal_contesto(ins, domanda, contesto),
                                                  card=card, massimo=corpus.MAX_SEZIONI_REPORT if report
                                                  else corpus.MAX_SEZIONI))
    if not esito["fatti"] and not esito["sezioni"]:
        return rifiuto(Rifiuto("parametri", "nessun fatto e nessuna sezione per la domanda"))

    # 5: risposta
    fatti = [(f.id, f.testo) for f in esito["fatti"]]
    sezioni = [(s["id"], s["titolo"], s["testo"]) for s in esito["sezioni"]]
    try:
        r = ollama.chat(prompt.messaggi_risposta(domanda, fatti, sezioni, esito["avvertenze"], report=report),
                        schema=prompt.schema_risposta([i for i, _ in fatti] + [i for i, _, _ in sezioni]),
                        opzioni={"num_predict": config.NUM_PREDICT_REPORT} if report else None)
    except ollama.OllamaNonDisponibile as e:
        return spento(str(e))
    esito["tempi"]["risposta_s"] = round(r["totale_s"], 2)
    d = prompt.leggi_json(r["testo"])
    if d is None:
        return chiudi("non_verificata", testo=NOTA_NON_VERIFICATA, fermata_da="verifica",
                      motivo=f"risposta non leggibile: {r['testo'][:200]!r}")
    if d.get("pertinente") is False:
        return rifiuto(Rifiuto("modello", "il modello ha dichiarato la domanda fuori perimetro"))

    # 6: verifica
    ammessi = {i for i, _ in fatti} | {i for i, _, _ in sezioni}
    testo = pulisci(d.get("risposta"), ammessi)
    basi = [t for _, t in fatti] + [f"{titolo} {t}" for _, titolo, t in sezioni] + esito["avvertenze"]
    ok, citati, motivo = verifica(testo, d.get("citati"), ammessi, basi)
    if not ok:
        return chiudi("non_verificata", testo=NOTA_NON_VERIFICATA, fermata_da="verifica",
                      motivo=f"{motivo} — testo del modello: {testo[:300]!r}")
    return chiudi("risposta", testo=testo, citati=citati)


def _sezioni(scelte):
    return [{"id": f"d{i}", "documento": s.documento, "titolo": s.titolo, "testo": s.testo} for i, s in enumerate(scelte, 1)]


def _soggetti_dal_contesto(ins: Instradamento, domanda, contesto):
    """L'inquinante della card conta come soggetto nominato quando la domanda dice «l'inquinante» senza nominarlo, o
    quando l'instradamento ne ha indicato uno."""
    if not set(ins.argomenti) & ARGOMENTI_CON_INQUINANTE:
        return ()
    scelto = (ins.parametri.get("inquinante") or "").strip()
    if scelto:
        return (scelto,)
    return (contesto["inquinante"],) if contesto.get("inquinante") and re.search(r"inquinant", domanda, re.IGNORECASE) else ()
