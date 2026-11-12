"""Schede dei fatti delle card «istantanee» (03/11/2026, richiesta di Matteo): le card che mettono a confronto zone o
fonti in un momento (la finestra, un mese, un anno) invece di seguire una serie nel tempo. Sono la carta con la zona in
primo piano («mappa»), la «Sintesi della finestra» («sintesi»), il «Riepilogo per distretto» («riepilogo»), le tre card
di «Fonti a confronto» («fonti_aria», «fonti_decessi», «fonti_calore») e i «Ricoveri» della Stagionalità («ricoveri»).

Il server (localhost/server/main.py, _dati_istantanea) prepara i dati con le stesse funzioni degli endpoint delle card e
li passa già ridotti a una forma comune: una «voce» è {"id", "nome", "valore", "stato", "nota"}, una «variabile» è
{"nome", "unita", "dominio"}. Qui si mettono in frase, senza rifare aggregazioni: mediane, posizioni e scarti sono fra
le zone o le fonti che la card mostra.

Ogni fatto porta l'analisi che lo produce e i domini che tocca (aria, salubrita, calore, alberi, suolo, decessi,
ricoveri, simulati, territorio): l'instradamento sceglie le analisi, il dominio nominato nella domanda (lo riconosce il
codice, perimetro.py) filtra i fatti, e i domini dei fatti consegnati scelgono le avvertenze.
"""

from collections import Counter
from statistics import median

from localhost.rag.analisi import AnalisiNonApplicabile, Fatto, con_segno, elenco, numero, percento

CARD = {
    "mappa": ("carta della finestra (per ogni zona: aria, salubrità, temperatura, alberi, suolo, eventi sanitari) e "
              "scheda della zona in primo piano (gli stessi domini più decessi, dati simulati e ricoveri)"),
    "sintesi": "scheda «Sintesi della finestra» (numeri di testa e classifica delle zone)",
    "riepilogo": ("tabella «Riepilogo per distretto» (per ogni distretto: territorio, aria, salubrità, decessi, "
                  "ricoveri, dati simulati, temperatura media, massima e minima)"),
    "fonti_aria": "grafico «inquinante secondo ogni fonte» di Fonti a confronto",
    "fonti_decessi": "grafico «decessi secondo ogni fonte» di Fonti a confronto",
    "fonti_calore": "grafico «temperatura secondo ogni fonte» di Fonti a confronto",
    "ricoveri": "grafico «Ricoveri (dimissioni ospedaliere)» della Stagionalità",
}
BANDE = ("cattiva", "scadente", "accettabile", "buona", "non_confrontabile")
NOME_BANDA = {"non_confrontabile": "non confrontabile"}

AVVERTENZA_MEDIANE = ("Mediane, posizioni e classifiche sono fra le zone della card, senza pesi: non sono la media del "
                      "Salento.")
AVVERTENZA_DECESSI = ("Decessi ISTAT per tutte le cause, a distretto e mese: provvisori negli ultimi mesi, senza la causa "
                      "di morte, mai per comune né per giorno (riservatezza).")
AVVERTENZA_RICOVERI = ("Ricoveri: dimissioni ospedaliere ISTAT Health for All della provincia di residenza, annuali; solo "
                       "informative, non entrano nelle correlazioni.")
AVVERTENZA_CALORE = "La temperatura ERA5-Land è un dato modellato (rianalisi a circa 9 km), non misurato."
AVVERTENZA_MITIGAZIONE = ("Copertura arborea (CLMS Tree Cover Density 2024) e suolo impermeabile (CLMS Imperviousness "
                          "Density 2018): valori fissi del territorio, non cambiano con la finestra.")
AVVERTENZA_SALUBRITA = ("Salubrità = il peggiore inquinante rispetto ai limiti del D.Lgs. 155/2010, su tutte le fonti e "
                        "solo a parità di statistica; con l'ozono il confronto è quasi sempre «non confrontabile».")
AVVERTENZA_FONTI = "Le fonti non si mediano fra loro: la concordanza dice quanto si somigliano, non quale sia giusta."
AVVERTENZA_ARPA = ("ARPA tiene il massimo giornaliero per NO2, O3, SO2 e CO: con le altre fonti si confronta in numeri "
                   "solo dove la statistica giornaliera è la stessa.")


class _Fatti:
    """Fatti con i domini che toccano, per filtrare per dominio e scegliere le avvertenze dei soli fatti consegnati."""

    def __init__(self):
        self.voci = []

    def add(self, nome_analisi, testo, *domini):
        self.voci.append((Fatto(nome_analisi, testo), set(domini)))

    def scegli(self, scelte=None, dominio=""):
        """Un fatto senza domini (una regola, un periodo) resta anche quando si filtra per dominio."""
        voci = [(f, d) for f, d in self.voci if (scelte is None or f.analisi in scelte)
                and (not dominio or not d or dominio in d)]
        return [f for f, _ in voci], set().union(*(d for _, d in voci))


def _u(v, unita):
    testo = str(v) if isinstance(v, int) else numero(v)
    return f"{testo} {unita}" if unita else testo


def _conteggio(v, segno=False):
    """Un conteggio (decessi, dimissioni, comuni) senza decimali: «43», non «43,0»."""
    return f"{'+' if segno and round(v) > 0 else ''}{round(v)}"


def _quota(frazione):
    return f"{round(frazione * 100)}%"


def _il_quota(frazione):
    """La percentuale con l'articolo: «il 43%», «l'8%», «l'11%», «l'80%», «lo 0%»."""
    p = round(frazione * 100)
    articolo = "lo " if p == 0 else "l'" if p in (1, 8, 11) or 80 <= p <= 89 else "il "
    return f"{articolo}{p}%"


def _validi(voci):
    return [v for v in voci if v["stato"] == "VALORE" and v["valore"] is not None]


def _ordine(voci):
    """Le voci con valore dal più alto al più basso: la posizione 1 è il valore più alto."""
    return sorted(_validi(voci), key=lambda v: v["valore"], reverse=True)


def _note_frequenti(voci, stato):
    note = Counter(v["nota"] for v in voci if v["stato"] == stato and v.get("nota"))
    return note.most_common(1)[0][0] if note else None


# --- analisi fra zone (o fra fonti) ----------------------------------------------------------------------------------

def _distribuzione(F, var, voci, plurale, testa, nome_analisi="riepilogo"):
    vv = _validi(voci)
    dominio = var["dominio"]
    if not vv:
        F.add(nome_analisi, f"{testa}, {var['nome']}: nessuno dei {len(voci)} {plurale} ha un valore.", dominio)
        return
    alto, basso = max(vv, key=lambda v: v["valore"]), min(vv, key=lambda v: v["valore"])
    F.add(nome_analisi, f"{testa}, {var['nome']}: {len(vv)} {plurale} con un valore su {len(voci)}; mediana "
                        f"{_u(median(v['valore'] for v in vv), var['unita'])}, più alto {alto['nome']} con "
                        f"{_u(alto['valore'], var['unita'])}, più basso {basso['nome']} con "
                        f"{_u(basso['valore'], var['unita'])}.", dominio)


def _estremi(F, var, voci, plurale, verso, k=3):
    ordine = _ordine(voci)
    if not ordine:
        return
    if verso == "bassi":
        ordine = ordine[::-1]
    scelti = ordine[:k]
    F.add("estremi", f"{var['nome']}: {'i' if len(scelti) > 1 else 'il'} {len(scelti)} {plurale} con il valore più "
                     f"{'alto' if verso == 'alti' else 'basso'}: "
                     f"{'; '.join(v['nome'] + ' ' + _u(v['valore'], var['unita']) for v in scelti)}.", var["dominio"])


def _posizioni(F, var, voci, ids, plurale):
    """Le zone a confronto nella classifica di tutte le zone della card (1 = valore più alto)."""
    ordine = _ordine(voci)
    per_id = {v["id"]: v for v in voci}
    for i in ids:
        v = per_id.get(i)
        if v is None:
            continue
        pos = next((n for n, x in enumerate(ordine, 1) if x["id"] == i), None)
        if pos is None:
            motivo = f" ({v['nota']})" if v.get("nota") else ""
            F.add("classifica_zone", f"{v['nome']}, {var['nome']}: nessun valore{motivo}.", var["dominio"])
        else:
            F.add("classifica_zone", f"{v['nome']}, {var['nome']}: {_u(v['valore'], var['unita'])}, {pos}° su "
                                     f"{len(ordine)} {plurale} con un valore (1 = il più alto).", var["dominio"])


def _copertura(F, var, voci, plurale):
    conta = Counter(v["stato"] if v["stato"] != "VALORE" or v["valore"] is not None else "NULL" for v in voci)
    testo = (f"{var['nome']}: {conta['VALORE']} {plurale} con un valore, {conta['NULL']} non utilizzabili (null) e "
             f"{conta['NO_DATA']} non disponibili (N/D), su {len(voci)}")
    for stato, nome in (("NO_DATA", "N/D"), ("NULL", "null")):
        if nota := _note_frequenti(voci, stato):
            testo += f"; motivo più frequente dei {nome}: {nota}"
    F.add("copertura", testo + ".", var["dominio"])


def _bande(F, bande, plurale):
    """bande: [{"nome", "banda", "peggiore"}] della salubrità, una per zona."""
    if not bande:
        return
    conta = Counter(b["banda"] for b in bande)
    F.add("superamenti", f"Salubrità dell'aria nella finestra, {plurale} per banda: "
                         f"{', '.join(f'{conta[b]} in banda {NOME_BANDA.get(b, b)}' for b in BANDE if conta[b])} "
                         f"su {len(bande)}.", "salubrita", "aria")
    peggiori = [b for b in bande if b["banda"] in ("cattiva", "scadente")]
    if peggiori:
        F.add("superamenti", f"In banda scadente o cattiva: "
                             f"{elenco(b['nome'] + ' (' + b['banda'] + (', ' + b['peggiore'] if b.get('peggiore') else '') + ')' for b in peggiori)}.",
              "salubrita", "aria")
    else:
        F.add("superamenti", f"Nessuno dei {len(bande)} {plurale} è in banda scadente o cattiva.", "salubrita", "aria")


# --- avvertenze -------------------------------------------------------------------------------------------------------

def _avvertenze(domini, dati, mediane=False, fonti=False):
    avvertenze = []
    if "aria" in domini:
        natura = dati.get("natura_aria")
        if natura == "modellato":
            avvertenze.append("L'aria è un dato modellato (CAMS), non misurato.")
        elif natura == "misto":
            avvertenze.append("L'aria è in parte misurata dalle stazioni e in parte modellata (CAMS): dove non ci sono "
                              "stazioni fisiche c'è solo CAMS.")
        if dati.get("fonte") == "Tutte":
            avvertenze.append("Vista «Tutte»: per ogni comune e giorno, media delle sole fonti che concordano; è una "
                              "lettura di sintesi.")
    if "salubrita" in domini:
        avvertenze.append(AVVERTENZA_SALUBRITA)
    if "calore" in domini:
        avvertenze.append(AVVERTENZA_CALORE)
    if domini & {"alberi", "suolo"}:
        avvertenze.append(AVVERTENZA_MITIGAZIONE)
    if "decessi" in domini:
        avvertenze.append(AVVERTENZA_DECESSI)
    if "ricoveri" in domini:
        avvertenze.append(AVVERTENZA_RICOVERI)
    if "simulati" in domini:
        scenario = f" (scenario {dati['scenario']})" if dati.get("scenario") else ""
        avvertenze.append(f"Pronto soccorso, ADI e ricoveri per causa sono dati simulati, non reali{scenario}.")
    if mediane:
        avvertenze.append(AVVERTENZA_MEDIANE)
    if fonti:
        avvertenze.append(AVVERTENZA_FONTI)
        if "aria" in domini:
            avvertenze.append(AVVERTENZA_ARPA)
    return avvertenze


# --- mappa e zona in primo piano --------------------------------------------------------------------------------------

def _primo_piano(F, pp):
    """La scheda della zona appoggiata alla carta: ogni strato (aria, temperatura, alberi, suolo, eventi sanitari) con
    la mediana e la posizione fra le zone dello stesso livello, poi salubrità, decessi, simulati e ricoveri."""
    nome, plurale = pp["nome"], pp["plurale"]
    for st in pp["strati"].values():
        var, voci = st["var"], st["voci"]
        v = next((x for x in voci if x["id"] == pp["id"]), None)
        if v is None:
            continue
        if v["stato"] != "VALORE" or v["valore"] is None:
            motivo = f" ({v['nota']})" if v.get("nota") else ""
            F.add("dettaglio_zona", f"{nome}, {var['nome']}: nessun valore{motivo}.", var["dominio"])
            continue
        ordine = _ordine(voci)
        pos = next(n for n, x in enumerate(ordine, 1) if x["id"] == pp["id"])
        F.add("dettaglio_zona", f"{nome}, {var['nome']}: {_u(v['valore'], var['unita'])}; mediana dei {plurale} "
                                f"{_u(median(x['valore'] for x in ordine), var['unita'])}, {pos}° su {len(ordine)} "
                                f"(1 = il più alto).", var["dominio"])
    if s := pp.get("salubrita"):
        peggiore = f", inquinante peggiore {s['peggiore']}" if s.get("peggiore") else ""
        F.add("dettaglio_zona", f"{nome}: salubrità dell'aria {NOME_BANDA.get(s['banda'], s['banda'])}{peggiore}.",
              "salubrita", "aria")
    if d := pp.get("decessi"):
        if d.get("valore") is not None:
            giorno = f", ~{numero(d['media_giornaliera'])} al giorno" if d.get("media_giornaliera") is not None else ""
            F.add("dettaglio_zona", f"{nome}: {_conteggio(d['valore'])} decessi per tutte le cause nei mesi "
                                    f"{elenco(d['mesi'])}{giorno}.", "decessi")
        else:
            F.add("dettaglio_zona", f"{nome}, decessi: {d.get('nota') or 'nessun valore'}.", "decessi")
    # simulati e ricoveri in un fatto ciascuno: uno per indicatore gonfiava la scheda e la risposta del modello restava
    # troncata (prova del 03/11/2026)
    if sim := pp.get("simulati"):
        F.add("dettaglio_zona", f"{nome}, dati simulati: "
                                f"{'; '.join(x['etichetta'] + ' ' + _u(x['valore'], x['unita']) for x in sim)}.", "simulati")
    if (r := pp.get("ricoveri")) and r["valori"]:
        voci = [f"{x['etichetta'].lower()} {_conteggio(x['dimissioni'])}"
                + (f" ({numero(x['tasso'])} per 10.000 abitanti)" if x.get("tasso") is not None else "") for x in r["valori"]]
        F.add("dettaglio_zona", f"Provincia di {r['provincia']}, che contiene {nome}, dimissioni ospedaliere {r['anno']}: "
                                f"{'; '.join(voci)}.", "ricoveri")


def _scheda_mappa(F, d, verso):
    plurale = d["plurale"]
    st = d["strati"].get(d["vista"])
    if st:
        _distribuzione(F, st["var"], st["voci"], plurale, d["periodo"])
        _estremi(F, st["var"], st["voci"], plurale, verso)
        _posizioni(F, st["var"], st["voci"], d["a_confronto"], plurale)
        _copertura(F, st["var"], st["voci"], plurale)
        if st["var"]["dominio"] == "aria" and d.get("senza_stazioni") is not None:
            n = len(d["senza_stazioni"])
            F.add("copertura", f"{n} {plurale} su {len(st['voci'])} senza stazioni fisiche: lì l'aria è solo il dato "
                               f"modellato di CAMS.", "aria")
    _bande(F, d.get("bande"), plurale)
    if d.get("primo_piano"):
        _primo_piano(F, d["primo_piano"])


# --- sintesi della finestra -------------------------------------------------------------------------------------------

def _scheda_sintesi(F, d, verso):
    var, distretti, livello = d["var"], d["distretti"], d["livello"]
    vv = _validi(distretti)
    if vv:
        alto = max(vv, key=lambda v: v["valore"])
        quota = f"; il {_quota(d['quota_residenti'])} dei residenti vive in un comune con un valore" \
            if d.get("quota_residenti") is not None else ""
        F.add("riepilogo", f"{d['periodo']}, {var['nome']}: valore più alto fra i distretti {alto['nome']} con "
                           f"{_u(alto['valore'], var['unita'])}; {len(vv)} distretti su {len(distretti)} con un "
                           f"valore{quota}.", "aria")
    else:
        F.add("riepilogo", f"{d['periodo']}, {var['nome']}: nessun distretto con un valore.", "aria")
    _estremi(F, var, livello["voci"], livello["plurale"], verso)
    _posizioni(F, var, livello["voci"], d["a_confronto"], livello["plurale"])
    if dec := d.get("decessi"):
        if dec["con"]:
            completi = "" if dec["con"] == dec["totale"] else \
                f" (solo {dec['con']} celle distretto × mese su {dec['totale']}: gli altri mesi non sono ancora pubblicati)"
            F.add("riepilogo", f"Salento, decessi per tutte le cause, {dec['mesi']}: {_conteggio(dec['somma'])}{completi}.",
                  "decessi")
            if dec.get("variazione") is not None:
                prima = "al mese prima" if dec["n_mesi"] == 1 else f"ai {dec['n_mesi']} mesi prima"
                F.add("variazione", f"Salento, decessi {dec['mesi']}: {_conteggio(dec['variazione'], True)} rispetto "
                                    f"{prima} ({dec['mesi_prima']}).", "decessi")
        else:
            F.add("riepilogo", f"Salento, decessi {dec['mesi']}: non ancora pubblicati da ISTAT.", "decessi")
    if r := d.get("ricoveri"):
        F.add("riepilogo", f"Salento, dimissioni ospedaliere per malattie respiratorie nel {r['anno']}: "
                           f"{_conteggio(r['totale'])}, somma delle tre province.", "ricoveri")
        if r.get("variazione") is not None:
            F.add("variazione", f"Salento, dimissioni respiratorie {r['anno']}: {_conteggio(r['variazione'], True)} rispetto "
                                f"al {r['anno'] - 1}.", "ricoveri")
    if ps := d.get("ps"):
        F.add("riepilogo", f"Salento, accessi in pronto soccorso nella finestra: {numero(ps['per_100k'])} per 100.000 "
                           f"residenti al giorno.", "simulati")


# --- riepilogo per distretto ------------------------------------------------------------------------------------------

def _scheda_riepilogo(F, d, verso):
    righe, plurale = d["righe"], "distretti"
    for c in d["colonne"]:
        voci = [{"id": r["id"], "nome": r["nome"], **r["celle"].get(c["id"], {"valore": None, "stato": "NO_DATA",
                                                                              "nota": None})} for r in righe]
        if c["formato"] == "banda":
            _bande(F, [{"nome": r["nome"], "banda": r["celle"][c["id"]]["testo"],
                        "peggiore": (r["celle"].get("salubrita_peggiore") or {}).get("testo")}
                       for r in righe if (r["celle"].get(c["id"]) or {}).get("testo")], plurale)
            continue
        if c["formato"] not in ("decimale", "intero", "percentuale"):
            if c["dominio"] != "territorio" and all(v["stato"] != "VALORE" for v in voci):
                F.add("copertura", f"{c['nome']}: {_note_frequenti(voci, 'NO_DATA') or 'non disponibile'}.",
                      c["dominio"])
            continue
        perc = c["formato"] == "percentuale"
        var = {"nome": c["nome"], "unita": None if perc else c["unita"], "dominio": c["dominio"]}
        if perc:
            voci = [{**v, "valore": v["valore"] * 100 if v["valore"] is not None else None} for v in voci]
            var["unita"] = "%"
        elif c["formato"] == "intero":
            voci = [{**v, "valore": round(v["valore"]) if v["valore"] is not None else None} for v in voci]
        ordine = _ordine(voci)
        if ordine:
            mediana = median(v["valore"] for v in ordine)
            mediana = round(mediana) if c["formato"] == "intero" and float(mediana).is_integer() else mediana
            F.add("estremi", f"{c['nome']}: mediana {_u(mediana, var['unita'])} fra i "
                             f"{len(ordine)} distretti con un valore; più alto {ordine[0]['nome']} "
                             f"({_u(ordine[0]['valore'], var['unita'])}), più basso {ordine[-1]['nome']} "
                             f"({_u(ordine[-1]['valore'], var['unita'])}).", c["dominio"])
        if c["dominio"] != "territorio":
            _posizioni(F, var, voci, d["a_confronto"], plurale)
            mancano = len(voci) - len(ordine)
            if mancano:
                nota = _note_frequenti(voci, "NO_DATA") or _note_frequenti(voci, "NULL")
                F.add("copertura", f"{c['nome']}: {mancano} distretti su {len(voci)} senza valore"
                                   f"{f' ({nota})' if nota else ''}.", c["dominio"])
    if delta := d.get("delta"):
        var, voci = delta["var"], delta["voci"]
        ordine = _ordine(voci)
        if ordine:
            su, giu = [v for v in ordine if v["valore"] > 0][:3], [v for v in ordine if v["valore"] < 0][-3:][::-1]
            for gruppo, nome in ((su, "aumenti"), (giu, "cali")):
                if gruppo:
                    F.add("variazione", f"Δ di {var['nome']} rispetto alla finestra precedente ({delta['periodo_prima']}), "
                                        f"{nome} più forti: {'; '.join(v['nome'] + ' ' + con_segno(v['valore']) + ' ' + var['unita'] for v in gruppo)}.",
                          "aria")
            for i in d["a_confronto"]:
                v = next((x for x in voci if x["id"] == i), None)
                if v and v["stato"] == "VALORE" and v["valore"] is not None:
                    F.add("variazione", f"{v['nome']}, Δ di {var['nome']}: {con_segno(v['valore'])} {var['unita']} "
                                        f"rispetto alla finestra precedente.", "aria")
        else:
            F.add("variazione", f"Δ di {var['nome']}: nessun distretto con un valore in entrambe le finestre.", "aria")


# --- fonti a confronto ------------------------------------------------------------------------------------------------

def _serie_fonti(F, d, dominio, verso, plurale_tempo="giorni"):
    """Media, giorni più alti e copertura di ogni fonte: le fonti non si mediano fra loro."""
    for s in d["serie"]:
        vv = _validi(s["punti"])
        etichetta = f"{d['zona']}, {d['variabile']} {d['periodo']}, {s['fonte']}{' (modello)' if s.get('modellata') else ''}"
        statistica = f"; statistica giornaliera: {s['statistica']}" if s.get("statistica") else ""
        if vv:
            media = sum(v["valore"] for v in vv) / len(vv)
            F.add("riepilogo", f"{etichetta}: media {_u(media, d['unita'])} su {len(vv)} {plurale_tempo} con un valore "
                               f"su {len(s['punti'])}{statistica}.", dominio)
            ordine = sorted(vv, key=lambda v: v["valore"], reverse=verso == "alti")[:3]
            F.add("estremi", f"{etichetta}: {plurale_tempo} con il valore più {'alto' if verso == 'alti' else 'basso'}: "
                             f"{'; '.join(v['nome'] + ' ' + _u(v['valore'], d['unita']) for v in ordine)}.", dominio)
        conta = Counter(p["stato"] for p in s["punti"])
        F.add("copertura", f"{etichetta}: {conta['VALORE']} {plurale_tempo} con un valore, {conta['NULL']} non "
                           f"utilizzabili (null), {conta['NO_DATA']} non disponibili (N/D)"
                           f"{f' ({n})' if (n := _note_frequenti(s['punti'], 'NO_DATA')) else ''}.", dominio)


def _scheda_fonti_aria(F, d, verso):
    _serie_fonti(F, d, "aria", verso)
    for c in d["confronti"]:
        testa = f"{c['fonte_a']} e {c['fonte_b']} ({c['livello']})"
        if not c["celle_comuni"]:
            F.add("concordanza", f"{testa}: nessuna cella con un valore in entrambe.", "aria")
            continue
        testo = f"{testa}: {c['celle_comuni']} celle con un valore in entrambe"
        if c.get("quota_concordanti") is not None:
            testo += f"; concordanti (scarto entro {_u(d['soglia'], d['unita'])}) {_il_quota(c['quota_concordanti'])}"
        if c.get("differenza_media") is not None:
            testo += (f"; differenza media ({c['fonte_b']} − {c['fonte_a']}) {con_segno(c['differenza_media'])} "
                      f"{d['unita']}, massima {_u(c['differenza_massima'], d['unita'])}")
        if c.get("stessa_statistica") is False:
            testo += (f"; statistiche giornaliere diverse ({c['statistica_a']} contro {c['statistica_b']}): "
                      f"il confronto è solo qualitativo")
        F.add("concordanza", testo + ".", "aria")


def _scheda_fonti_calore(F, d, verso):
    _serie_fonti(F, d, "calore", verso)
    c = d["confronto"]
    testa = f"{c['fonte_a']} e {c['fonte_b']} ({c['livello']})"
    if not c["coppie"]:
        F.add("concordanza", f"{testa}: nessuna coppia comune × giorno con un valore in entrambe "
                             f"(ARPA meteo misura solo nei comuni con una stazione).", "calore")
    else:
        parti = [f"{c['coppie']} coppie comune × giorno con un valore in entrambe"]
        if c.get("comuni"):
            parti.append(f"comuni confrontati: {elenco(c['comuni'])}")
        if c.get("bias") is not None:
            parti.append(f"scarto medio ({c['fonte_b']} − {c['fonte_a']}) {con_segno(c['bias'])} °C")
        if c.get("errore_medio") is not None:
            parti.append(f"errore medio assoluto {numero(c['errore_medio'])} °C")
        if c.get("rmse") is not None:
            parti.append(f"RMSE {numero(c['rmse'])} °C")
        if c.get("correlazione") is not None:
            parti.append(f"correlazione {numero(c['correlazione'])}")
        F.add("concordanza", f"{testa}: {'; '.join(parti)}.", "calore")
    for s in d.get("soglie") or []:
        F.add("superamenti", f"{d['zona']}, {s['descrizione']} (sopra {numero(s['soglia'])} °C): {s['giorni_a']} coppie "
                             f"comune × giorno secondo {c['fonte_a']}, {s['giorni_b']} secondo {c['fonte_b']}.", "calore")


def _scheda_fonti_decessi(F, d, verso):
    for gruppo in ("mensile", "provinciale"):
        zona = d["zona"] if gruppo == "mensile" else f"provincia di {d['provincia']}"
        for s in d[gruppo]:
            vv = _validi(s["punti"])
            etichetta = f"{zona}, decessi {d['anno']}, {s['fonte']}"
            if vv:
                F.add("riepilogo", f"{etichetta}: {_conteggio(sum(v['valore'] for v in vv))} in {len(vv)} mesi con un "
                                   f"valore su {len(s['punti'])}.", "decessi")
                if gruppo == "mensile":
                    ordine = sorted(vv, key=lambda v: v["valore"], reverse=verso == "alti")[:3]
                    F.add("estremi", f"{etichetta}: mesi con {'più' if verso == 'alti' else 'meno'} decessi: "
                                     f"{'; '.join(v['nome'] + ' ' + _conteggio(v['valore']) for v in ordine)}.", "decessi")
            mancano = len(s["punti"]) - len(vv)
            if mancano:
                F.add("copertura", f"{etichetta}: {mancano} mesi senza valore"
                                   f"{f' ({n})' if (n := _note_frequenti(s['punti'], 'NO_DATA')) else ''}.", "decessi")
    for c in d["confronti"]:
        testa = f"{c['fonte_a']} e {c['fonte_b']} ({c['livello']})"
        if not c["celle_comuni"]:
            F.add("concordanza", f"{testa}: nessun periodo con un valore in entrambe.", "decessi")
            continue
        parti = [f"{c['celle_comuni']} periodi con un valore in entrambe"]
        if c.get("identiche") is not None:
            parti.append(f"identici {_il_quota(c['identiche'])}")
        if c.get("entro_uno") is not None:
            parti.append(f"entro un decesso {_il_quota(c['entro_uno'])}")
        if c.get("differenza_totale") is not None:
            parti.append(f"differenza totale ({c['fonte_b']} − {c['fonte_a']}) "
                         f"{_conteggio(c['differenza_totale'], True)} decessi")
        if c.get("differenza_massima") is not None:
            parti.append(f"differenza massima in un periodo {_conteggio(c['differenza_massima'])} decessi")
        if c.get("correlazione") is not None:
            parti.append(f"correlazione {numero(c['correlazione'])}")
        F.add("concordanza", f"{testa}: {'; '.join(parti)}.", "decessi")


# --- ricoveri ---------------------------------------------------------------------------------------------------------

def _scheda_ricoveri(F, d, verso):
    ultimi = []
    for s in d["serie"]:
        vv = [p for p in s["punti"] if p["stato"] == "VALORE" and p.get("dimissioni") is not None]
        testa = f"Provincia di {s['provincia']}, ricoveri {d['gruppo']}"
        if not vv:
            F.add("copertura", f"{testa}: nessun anno con un valore fra il {d['da']} e il {d['a']}.", "ricoveri")
            continue
        u = vv[-1]
        tasso = f", {numero(u['tasso'])} per 10.000 abitanti" if u.get("tasso") is not None else ""
        F.add("riepilogo", f"{testa}, {u['anno']}: {_conteggio(u['dimissioni'])} dimissioni{tasso}.", "ricoveri")
        ultimi.append((s["provincia"], u))
        if len(vv) >= 2:
            p = vv[0]
            F.add("tendenza", f"{testa}: da {_conteggio(p['dimissioni'])} dimissioni nel {p['anno']} a "
                              f"{_conteggio(u['dimissioni'])} nel {u['anno']} ({percento((u['dimissioni'] - p['dimissioni']) / p['dimissioni'])}).",
                  "ricoveri")
        m = (max if verso == "alti" else min)(vv, key=lambda p: p["dimissioni"])
        F.add("estremi", f"{testa}: anno con {'più' if verso == 'alti' else 'meno'} dimissioni il {m['anno']} "
                         f"({_conteggio(m['dimissioni'])}).", "ricoveri")
        assenti = [str(p["anno"]) for p in s["punti"] if p["stato"] != "VALORE"]
        if assenti:
            F.add("copertura", f"{testa}: senza valore {elenco(assenti)} (non ancora pubblicati da ISTAT).", "ricoveri")
    con_tasso = [(prov, u) for prov, u in ultimi if u.get("tasso") is not None]
    if len(con_tasso) >= 2:
        ordine = sorted(con_tasso, key=lambda x: x[1]["tasso"], reverse=True)
        F.add("classifica_zone", f"Ricoveri {d['gruppo']}, tasso per 10.000 abitanti nell'ultimo anno pubblicato: "
                                 f"{'; '.join(f'{n}. {prov} {numero(u['tasso'])} ({u['anno']})' for n, (prov, u) in enumerate(ordine, 1))}.",
              "ricoveri")


SCHEDE = {"mappa": _scheda_mappa, "sintesi": _scheda_sintesi, "riepilogo": _scheda_riepilogo,
          "fonti_aria": _scheda_fonti_aria, "fonti_decessi": _scheda_fonti_decessi,
          "fonti_calore": _scheda_fonti_calore, "ricoveri": _scheda_ricoveri}


def scheda(card, dati, p, scelte=None):
    """Scheda intera (`scelte` None) o solo le analisi scelte dall'instradamento; `p["dominio"]` filtra i fatti."""
    F = _Fatti()
    SCHEDE[card](F, dati, p.get("verso") or "alti")
    fatti, domini = F.scegli(scelte, p.get("dominio") or "")
    if not fatti:
        raise AnalisiNonApplicabile("nessuna delle analisi scelte si applica ai dati della card")
    for i, f in enumerate(fatti, 1):
        f.id = f"f{i}"
    mediane = card in ("mappa", "sintesi", "riepilogo") and any(
        f.analisi in ("riepilogo", "estremi", "classifica_zone", "dettaglio_zona") for f in fatti)
    return {"fatti": fatti, "avvertenze": _avvertenze(domini, dati, mediane=mediane, fonti=card.startswith("fonti_"))}
