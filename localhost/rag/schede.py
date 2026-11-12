"""Schede dei fatti per card (piano del modulo AI §5.2 e §13.3): quali analisi generiche si applicano ai dati di una
card, con quali serie, e quali avvertenze accompagnano sempre la risposta. Le serie arrivano già pronte dal server
(localhost/server/main.py), che le costruisce con le stesse funzioni degli endpoint della dashboard.

Card con la scheda dei fatti: «andamento» (inquinante giorno per giorno, GraficoAndamento.tsx) dal 30/10/2026; dal
01/11/2026 (passo 8 del piano) anche «domini» (aria e decessi per distretto e mese, ConfrontoDomini.tsx; dal
03/11/2026 anche la temperatura ERA5-Land) e le quattro card della Stagionalità («consiglio», «anno_su_anno»,
«dettaglio_mese», «cambiamenti», Stagionalita.tsx). Dal 03/11/2026 anche le sette card «istantanee» (mappa, sintesi,
riepilogo, fonti, ricoveri), con le loro schede in schede_istantanee.py.

Per la Stagionalità i numeri sono già calcolati da /api/stagionalita (localhost/server/dati_stagionalita.py: ranghi,
periodi critici, andamento): qui si mettono in frase, senza rifare medie né ranghi. Dove la card legge una serie (un
anno dell'indicatore, un mese negli anni) si usano le analisi generiche sulle stesse celle.

Punto d'ingresso: `scheda(card, dati, parametri)` (scheda intera, per /api/assistente/fatti e per l'assistente spento)
e `fatti(card, dati, scelte, parametri)` (solo le analisi scelte dall'instradamento). `dati` è ciò che il server
prepara per la card (localhost/server/main.py, _dati_assistente).
"""

from statistics import mean

from localhost.rag import analisi, schede_istantanee
from localhost.rag.analisi import MESI, AnalisiNonApplicabile, Fatto, con_segno, elenco, numero, percento
from localhost.rag.serie import Punto, Serie

# Card su cui c'è l'assistente: id → come si chiama la card nelle istruzioni dell'instradamento. Lo stesso elenco sta in
# localhost/server/modelli.py (DomandaAssistente.card) e in stato/assistente.ts della dashboard.
CARD = {
    "andamento": "grafico «inquinante giorno per giorno»",
    "domini": "grafici «Aria e salute per distretto e mese»",
    "consiglio": "sommario «Quando intervenire» della Stagionalità",
    "anno_su_anno": "grafico «anno su anno» della Stagionalità",
    "dettaglio_mese": "tabella «mese anno per anno» della Stagionalità",
    "cambiamenti": "blocco «Cosa sta cambiando» della Stagionalità",
    **schede_istantanee.CARD,
}
# Card con una scheda dei fatti: solo su queste si eseguono le analisi (§13.3). Dal 01/11/2026 tutte quelle con
# l'assistente; l'insieme resta per una card che arrivasse con la sola descrizione.
CARD_CON_FATTI = set(CARD)
STAGIONE = ("consiglio", "anno_su_anno", "dettaglio_mese", "cambiamenti")

AVVERTENZA_ESPLORATIVA = ("Le relazioni sono esplorative, non causali: età, fumo, malattie già presenti e aria degli "
                          "ambienti chiusi non sono considerati.")
AVVERTENZA_SALUTE_GIORNO = ("I decessi non sono disponibili per giorno né per comune (riservatezza): questo grafico non "
                            "si mette in relazione giorno per giorno con la salute.")


def _avvertenze_serie(serie: list[Serie]):
    avvertenze = []
    for s in serie:
        if s.natura == "modellato":
            fonte = "CAMS" if s.fonte == "Tutte" else s.fonte  # «Tutte» senza stazioni fisiche è il solo CAMS
            avvertenze.append(f"{s.zona}: {s.variabile} è un dato modellato ({fonte}), non misurato.")
        elif s.natura == "misto":
            avvertenze.append(f"{s.zona}: {s.variabile} è in parte misurato e in parte modellato (CAMS).")
        elif s.natura == "simulato":
            avvertenze.append(f"{s.zona}: {s.variabile} è un dato simulato, non reale.")
    return avvertenze


def scheda_andamento(aria: list[Serie], temperatura: dict[str, Serie], soglia=None):
    """aria: una serie giornaliera per zona a confronto (stesso inquinante, mese e fonte); temperatura: T max
    giornaliera ERA5-Land per id di zona, quando è in archivio; soglia: scelta dall'utente, facoltativa."""
    fatti = []
    for s in aria:
        fatti += analisi.copertura(s) + analisi.riepilogo(s) + analisi.estremi(s) + analisi.tendenza(s) + analisi.anomalie(s)
        try:
            fatti += analisi.superamenti(s)
        except AnalisiNonApplicabile:
            pass
        if soglia is not None:
            fatti += analisi.superamenti(s, soglia) + analisi.episodi(s, soglia, "soglia scelta dall'utente")
        if s.zona_id in temperatura:
            fatti += analisi.relazione(s, temperatura[s.zona_id])
    if len(aria) >= 2:
        fatti += analisi.classifica_zone(aria)
    _numera(fatti)
    return {"fatti": fatti, "serie": aria + list(temperatura.values()),
            "avvertenze": _avvertenze_andamento(aria, temperatura, usa_temperatura=True, relazione=True)}


def _numera(fatti):
    for i, f in enumerate(fatti, 1):
        f.id = f"f{i}"


def _avvertenze_andamento(aria: list[Serie], temperatura: dict[str, Serie], usa_temperatura, relazione):
    avvertenze = _avvertenze_serie(aria)
    if any(s.fonte == "Tutte" for s in aria):
        avvertenze.append("Vista «Tutte»: per ogni comune e giorno, media delle sole fonti che concordano; è una lettura "
                          "di sintesi.")
    if usa_temperatura:
        if temperatura:
            avvertenze.append("La temperatura massima è ERA5-Land, un dato modellato (rianalisi a circa 9 km), non "
                              "misurato.")
        else:
            avvertenze.append("Temperatura del mese non disponibile in archivio: nessuna relazione con il caldo.")
    if relazione:
        avvertenze += [AVVERTENZA_ESPLORATIVA, AVVERTENZA_SALUTE_GIORNO]
    return avvertenze


def _una_analisi(nome, s: Serie, temperatura: dict[str, Serie], soglia, verso):
    if nome == "riepilogo":
        return analisi.riepilogo(s)
    if nome == "copertura":
        return analisi.copertura(s)
    if nome == "estremi":
        return analisi.estremi(s, verso=verso)
    if nome == "tendenza":
        return analisi.tendenza(s)
    if nome == "anomalie":
        return analisi.anomalie(s)
    if nome == "superamenti":
        return analisi.superamenti(s, soglia)
    if nome == "episodi":
        if soglia is not None:
            return analisi.episodi(s, soglia, "soglia scelta dall'utente")
        if not s.temperatura:
            raise AnalisiNonApplicabile("gli episodi dell'aria richiedono una soglia")
        stat = s.variabile.removeprefix("temperatura ").strip()
        return [f for statistica, valore, descr in analisi.SOGLIE_CALDO.values() if statistica == stat
                for f in analisi.episodi(s, valore, f"soglia di caldo del progetto: {descr.split(':')[0].split(' (')[0]}",
                                         inclusiva=True)]
    if nome == "relazione":
        if s.zona_id not in temperatura:
            raise AnalisiNonApplicabile("temperatura del mese non in archivio")
        return analisi.relazione(s, temperatura[s.zona_id])
    raise AnalisiNonApplicabile(f"analisi non disponibile per questa card: {nome}")


def fatti_andamento(aria: list[Serie], temperatura: dict[str, Serie], scelte, variabile="inquinante", soglia=None,
                    verso="alti"):
    """Solo le analisi scelte dall'instradamento (§13.1), con i parametri della domanda. `variabile` = «temperatura
    massima» le applica alla T max invece che all'inquinante; la relazione è sempre fra i due. Le analisi che non si
    applicano a una zona si saltano; se non resta nessun fatto, AnalisiNonApplicabile (→ rifiuto fisso)."""
    if variabile == "inquinante":
        serie = aria
    else:
        serie = [temperatura[s.zona_id] for s in aria if s.zona_id in temperatura]
        if not serie:
            raise AnalisiNonApplicabile("temperatura del mese non in archivio")
    fatti = []
    for s in serie:
        aria_zona = next(a for a in aria if a.zona_id == s.zona_id)
        for nome in scelte:
            if nome == "classifica_zone":
                continue
            try:
                fatti += _una_analisi(nome, aria_zona if nome == "relazione" else s, temperatura, soglia, verso)
            except AnalisiNonApplicabile:
                pass
    if "classifica_zone" in scelte and len(serie) >= 2:
        fatti += analisi.classifica_zone(serie)
    if not fatti:
        raise AnalisiNonApplicabile("nessuna delle analisi scelte si applica ai dati della card")
    _numera(fatti)
    usa_temperatura = variabile != "inquinante" or "relazione" in scelte
    avvertenze = _avvertenze_andamento(aria if variabile == "inquinante" or "relazione" in scelte else [], temperatura,
                                       usa_temperatura, relazione="relazione" in scelte)
    return {"fatti": fatti, "avvertenze": avvertenze}


# --- «domini»: aria, temperatura e decessi per distretto × mese -----------------------------------------------------

AVVERTENZA_DECESSI = ("Decessi ISTAT per tutte le cause, somma dei comuni del distretto nel mese: provvisori negli ultimi "
                      "mesi, senza la causa di morte, pubblicati solo per distretto e mese (riservatezza).")
AVVERTENZA_TEMPERATURA_MESE = ("La temperatura è ERA5-Land, un dato modellato (rianalisi a circa 9 km), non misurato: "
                               "media del mese, pesata sui residenti dei comuni del distretto.")
AVVERTENZA_TOTALI = ("I decessi sono totali del mese: un distretto con più residenti ne conta di più, quindi la "
                     "classifica fra distretti non dice dove si muore di più in proporzione.")


def _una_analisi_generica(nome, s: Serie, verso):
    if nome == "riepilogo":
        return analisi.riepilogo(s)
    if nome == "copertura":
        return analisi.copertura(s)
    if nome == "estremi":
        return analisi.estremi(s, verso=verso)
    if nome == "tendenza":
        return analisi.tendenza(s)
    if nome == "anomalie":
        return analisi.anomalie(s)
    raise AnalisiNonApplicabile(f"analisi non disponibile per questa card: {nome}")


def _avvertenze_domini(aria, decessi, relazione, totali, comuni_esclusi, temperatura=None):
    """`temperatura`: None = la risposta non la usa; {} = la usa ma non è in archivio."""
    avvertenze = _avvertenze_serie(aria)
    if any(s.fonte == "Tutte" for s in aria):
        avvertenze.append("Vista «Tutte»: per ogni comune e giorno, media delle sole fonti che concordano; è una lettura "
                          "di sintesi.")
    if temperatura is not None:
        avvertenze.append(AVVERTENZA_TEMPERATURA_MESE if temperatura else
                          "Temperatura del periodo non disponibile in archivio: nessun fatto sul caldo.")
    if decessi:
        avvertenze.append(AVVERTENZA_DECESSI)
    if totali:
        avvertenze.append(AVVERTENZA_TOTALI)
    if relazione:
        avvertenze.append(AVVERTENZA_ESPLORATIVA)
    if comuni_esclusi:
        quali = "comune, fuori" if len(comuni_esclusi) == 1 else "comuni, fuori"
        avvertenze.append(f"{elenco(comuni_esclusi)}: {quali} da questi fatti perché i decessi si pubblicano solo per "
                          f"distretto.")
    return avvertenze


def scheda_domini(aria: list[Serie], decessi: dict[str, Serie], temperatura: dict[str, Serie] | None = None,
                  comuni_esclusi=()):
    """aria: la media mensile dell'inquinante per distretto; decessi: la somma mensile per id di distretto;
    temperatura: la media mensile della statistica scelta nella card (ERA5-Land) per id di distretto, quando è in
    archivio. Le relazioni mettono l'aria e la temperatura fino a un mese prima dei decessi."""
    if not aria:
        raise AnalisiNonApplicabile("nessun distretto a confronto")
    temperatura = temperatura or {}
    fatti = []
    for s in aria:
        fatti += analisi.copertura(s) + analisi.riepilogo(s)
        if s.zona_id in temperatura:
            fatti += analisi.riepilogo(temperatura[s.zona_id])
        if s.zona_id in decessi:
            fatti += analisi.riepilogo(decessi[s.zona_id]) + analisi.relazione(decessi[s.zona_id], s)
            if s.zona_id in temperatura:
                fatti += analisi.relazione(decessi[s.zona_id], temperatura[s.zona_id])
    if len(aria) >= 2:
        fatti += analisi.classifica_zone(aria)
    _numera(fatti)
    return {"fatti": fatti, "serie": aria + list(temperatura.values()) + list(decessi.values()),
            "avvertenze": _avvertenze_domini(aria, decessi, relazione=bool(decessi), totali=False,
                                             comuni_esclusi=comuni_esclusi, temperatura=temperatura)}


def fatti_domini(aria: list[Serie], decessi: dict[str, Serie], scelte, variabile="inquinante", verso="alti",
                 comuni_esclusi=(), temperatura: dict[str, Serie] | None = None, esposizione="inquinante"):
    """Le analisi scelte sull'inquinante, sulla temperatura o sui decessi; «relazione» è sempre fra i decessi e
    l'esposizione: l'inquinante, o la temperatura quando la domanda parla di caldo."""
    if not aria:
        raise AnalisiNonApplicabile("nessun distretto a confronto")
    temperatura = temperatura or {}
    if variabile == "inquinante":
        serie = aria
    else:
        altra = decessi if variabile == "decessi" else temperatura
        serie = [altra[s.zona_id] for s in aria if s.zona_id in altra]
    if not serie:
        raise AnalisiNonApplicabile(f"{'decessi' if variabile == 'decessi' else 'temperatura'} del periodo non disponibili")
    rispetto = temperatura if esposizione == "temperatura" else {s.zona_id: s for s in aria}
    fatti = []
    for s in serie:
        for nome in scelte:
            try:
                if nome == "relazione":
                    if s.zona_id in decessi and s.zona_id in rispetto:
                        fatti += analisi.relazione(decessi[s.zona_id], rispetto[s.zona_id])
                elif nome != "classifica_zone":
                    fatti += _una_analisi_generica(nome, s, verso)
            except AnalisiNonApplicabile:
                pass
    if "classifica_zone" in scelte and len(serie) >= 2:
        fatti += analisi.classifica_zone(serie)
    if not fatti:
        raise AnalisiNonApplicabile("nessuna delle analisi scelte si applica ai dati della card")
    _numera(fatti)
    relazione = "relazione" in scelte
    usa_aria = variabile == "inquinante" or relazione and esposizione == "inquinante"
    usa_temperatura = variabile == "temperatura" or relazione and esposizione == "temperatura"
    usa_decessi = variabile == "decessi" or relazione
    return {"fatti": fatti, "avvertenze": _avvertenze_domini(
        aria if usa_aria else [], decessi if usa_decessi else {}, relazione=relazione,
        totali=variabile == "decessi" and "classifica_zone" in scelte, comuni_esclusi=comuni_esclusi,
        temperatura=temperatura if usa_temperatura else None)}


# --- Stagionalità: consiglio, anno su anno, mese anno per anno, cosa sta cambiando ---------------------------------

LIVELLO = {"alta": "alto", "media": "medio", "bassa": "basso"}
POSIZIONE = {1: "il mese peggiore dell'anno", 2: "il secondo mese peggiore", 3: "il terzo mese peggiore"}
CLASSE = {"in_aumento": "in aumento", "in_calo": "in calo", "stabile": "stabile"}
ANNI_COVID = {"2020", "2021", "2022"}
UNITA_SIMULATI = "per 100.000 residenti al giorno"
REGOLA_CAMBIAMENTI = ("Un indicatore è stabile se lo scarto dalla media degli anni precedenti è entro ±10%, entro ±1 °C "
                      "per la temperatura; fuori è in aumento o in calo.")
# Domini di «Cosa sta cambiando» che possono restare indietro, come nella card (Stagionalita.tsx, Cambiamenti)
NOMI_DOMINIO = {"aria": "aria", "simulati": "PS, ADI e ricoveri simulati", "calore": "temperatura", "decessi": "decessi"}


class _Raccolta:
    """Fatti con le righe della Stagionalità che toccano: servono a filtrare per indicatore e a scegliere le
    avvertenze (simulato, modellato) dei soli fatti consegnati."""

    def __init__(self):
        self.voci = []

    def add(self, nome_analisi, testo, *righe, sempre=False):
        """`sempre`: il fatto resta anche quando la domanda nomina un indicatore (i fatti della medicina di iniziativa
        parlano di più indicatori insieme: «ricoveri ripetuti» nomina i ricoveri ma vuole i ritorni degli ADI)."""
        self.voci.append((Fatto(nome_analisi, testo), set(righe), sempre))

    def extend(self, fatti, *righe):
        self.voci += [(f, set(righe), False) for f in fatti]

    def scegli(self, scelte=None, indicatore=None):
        """Un fatto senza righe (un periodo, una regola) resta anche quando si filtra per indicatore."""
        voci = [(f, r) for f, r, sempre in self.voci if (scelte is None or f.analisi in scelte)
                and (sempre or not indicatore or not r or indicatore in r)]
        return [f for f, _ in voci], set().union(*(r for _, r in voci))


def _mese(m):
    return MESI[m - 1]


def _a_mese(m):
    """«a luglio», «ad agosto»."""
    return ("ad " if _mese(m).startswith("a") else "a ") + _mese(m)


def _rango(x):
    return numero(x).removesuffix(",0")


def _minuscola(t):
    """«Decessi» → «decessi», ma «PM2.5» e «ADI» restano come sono."""
    return t[0].lower() + t[1:] if len(t) > 1 and t[1].islower() else t


def _righe(st):
    return {r["id"]: r for r in st["righe"]}


def _nome(r, st):
    """Come nomeIndicatore della dashboard: il nome del tema se la riga è un tema («Pronto soccorso»)."""
    if r["id"] == "calore":
        return "temperatura massima"
    temi = {t["id"]: t["nome"] for t in (st.get("criticita") or {}).get("temi", [])}
    return _minuscola(temi.get(r["id"], r["etichetta"]))


def _unita(r):
    if r.get("simulata"):
        return UNITA_SIMULATI
    return "decessi al giorno" if r["id"] == "decessi" else r.get("unita")


def _val(v, r):
    u = _unita(r)
    return f"{numero(v)} {u}" if u else numero(v)


def _serie_riga(r, st, natura_aria, variabile, punti, grana, area):
    if r.get("simulata"):
        natura = "simulato"
    elif r.get("modellata") or r["id"] == "calore":
        natura = "modellato"
    else:
        natura = "reale" if r["id"] == "decessi" else natura_aria
    return Serie(zona_id=st["zona"]["id"] if st.get("zona") else "SALENTO", zona=area, variabile=variabile,
                 unita=_unita(r), grana=grana, natura=natura, fonte=st["fonte"], statistica=None, punti=punti)


def _punto(tempo, cella):
    """Solo i mesi completi entrano in medie e confronti, come nella tab: un mese in corso è «non ancora completo»."""
    if cella is None:
        return Punto(tempo, None, "NO_DATA", "nessun valore per questo anno")
    if cella["stato"] == "VALORE" and cella["valore"] is not None and not cella.get("completo"):
        return Punto(tempo, None, "NULL", "mese non ancora completo")
    return Punto(tempo, cella["valore"], cella["stato"], cella.get("nota"))


def _avvertenze_stagione(st, area, righe_usate, natura_aria, medie=True, consiglio=False):
    righe = _righe(st)
    avvertenze = []
    if medie:
        avvertenze.append(f"{area}: medie e ranghi sugli anni {elenco(st['anni_confronto'])}, solo mesi completi; gli "
                          f"anni precedenti sono storico, fuori da medie e ranghi.")
    if any(i.startswith("aria") for i in righe_usate):
        if natura_aria == "modellato":
            avvertenze.append(f"{area}: l'aria è un dato modellato (CAMS), non misurato.")
        elif natura_aria == "misto":
            avvertenze.append(f"{area}: l'aria è in parte misurata e in parte modellata (CAMS).")
    if "calore" in righe_usate:
        avvertenze.append("La temperatura massima è ERA5-Land, un dato modellato (rianalisi a circa 9 km), non misurato.")
    if "decessi" in righe_usate:
        avvertenze.append("Decessi ISTAT per tutte le cause, media al giorno del mese, provvisori negli ultimi mesi.")
    simulate = [_nome(righe[i], st) for i in sorted(righe_usate) if i in righe and righe[i].get("simulata")]
    if simulate:
        scenario = f" (scenario {st['scenario']})" if st.get("scenario") else ""
        avvertenze.append(f"{elenco(simulate)}: dati simulati, non reali{scenario}.")
    if consiglio:
        avvertenze.append("Sono spunti da valutare, non prescrizioni; che più temi siano critici negli stessi mesi è una "
                          "lettura esplorativa, non causale.")
    return avvertenze


def _cambiamento(r, st, area, nome=None):
    """Una riga di «Cosa sta cambiando»: l'andamento già calcolato dalla tab (ultimo mese completo contro la media
    dello stesso mese negli anni precedenti). `nome`: come chiamare la riga, se non col nome del tema."""
    a = r.get("andamento") or {}
    if a.get("classe") not in CLASSE or a.get("delta") is None:
        return None
    rif = a["mese_riferimento"]
    mese = _mese(int(rif[5:7]))
    if r["id"] == "calore" or a.get("delta_percentuale") is None:
        sc = f"{con_segno(a['delta'])} {'°C' if r['id'] == 'calore' else _unita(r) or ''}".rstrip()
    else:
        sc = percento(a["delta_percentuale"])
    indicativo = ", indicativo (un solo anno di storico)" if a.get("indicativo") else ""
    return (f"{area}, {nome or _nome(r, st)}: {mese} {rif[:4]} {_val(a['valore'], r)} contro una media di "
            f"{_val(a['media_anni_precedenti'], r)} a {mese} {elenco(a['anni_precedenti'])}: {sc}, "
            f"{CLASSE[a['classe']]}{indicativo}.")


def _fatti_cambiamenti(R: _Raccolta, st, area, solo_cambiati=False):
    voci = [(r, t) for r in st["righe"] if (t := _cambiamento(r, st, area))]
    if solo_cambiati:
        voci = [(r, t) for r, t in voci if r["andamento"]["classe"] != "stabile"]
        if not voci:
            R.add("anni_precedenti", f"{area}: nessun indicatore lontano dal solito nell'ultimo mese completo.")
    for r, t in voci:
        R.add("anni_precedenti", t, r["id"])
    R.add("anni_precedenti", REGOLA_CAMBIAMENTI)


def _scheda_consiglio(R: _Raccolta, st, area):
    """Il sommario «Quando intervenire»: periodi critici, temi, spunti, limiti superati e cosa sta cambiando, dalla
    `criticita` di /api/stagionalita (ConsiglioStagionalita.tsx compone il testo dagli stessi campi)."""
    k = st.get("criticita")
    if not k:
        raise AnalisiNonApplicabile("criticità dell'anno non disponibili")
    n, critici = k["temi_contati"], k.get("mesi_critici_per_tema", 3)
    temi = {t["id"]: t for t in k["temi"]}
    righe = _righe(st)

    def nome(i, etichetta=None):
        return _nome(righe[i], st) if i in righe else _minuscola(temi.get(i, {}).get("nome") or etichetta or i)

    def motivo(m):
        posto = POSIZIONE.get(m.get("posizione"), f"fra i {critici} mesi peggiori")
        if m["formato"] == "rango" or m.get("valore") is None:
            return f"{nome(m['id'])} {_a_mese(m['mese'])}, {posto}"
        r = righe.get(m["id"], {"id": m["id"], "unita": m.get("unita"), "simulata": m.get("simulata")})
        sc = ""
        if m.get("scarto") is not None:
            sc = f"{con_segno(m['scarto'])} °C" if m.get("scarto_assoluto") else percento(m["scarto"])
            sc = f", {sc} sulla media dei 12 mesi"
        return f"{nome(m['id'])} {_a_mese(m['mese'])}, {posto} ({_val(m['valore'], r)}{sc})"

    if not k["periodi"]:
        R.add("stagionalita", f"{area}: nessun periodo critico, nessun gruppo di mesi vicini è fra i {critici} mesi "
                              f"peggiori per almeno due temi.")
    for i, p in enumerate(k["periodi"], 1):
        ids = [m["id"] for m in p["motivi"]]
        testa = (f"{area}: il periodo più critico dell'anno è {p['etichetta']}" if i == 1
                 else f"{area}: periodo critico n. {i}, {p['etichetta']}")
        livello = f", livello {LIVELLO[p['livello']]}" if p.get("livello") else ""
        picco = f"; {_mese(p['mese_picco'])} è il mese peggiore dell'anno" if i == 1 else ""
        R.add("stagionalita", f"{testa}{livello}: {_a_mese(p['mese_picco'])} {p['massimo']} temi su {n} sono fra i "
                              f"{critici} mesi peggiori{picco}.", *ids)
        R.add("stagionalita", f"Periodo {p['etichetta']}, temi critici: {'; '.join(motivo(m) for m in p['motivi'])}.",
              *ids)
        if p.get("anche"):
            anche = elenco(f"{nome(m['id'], m['etichetta'])} ({elenco(_mese(x) for x in m['mesi'])})" for m in p["anche"])
            R.add("stagionalita", f"Periodo {p['etichetta']}, fra i {critici} mesi peggiori anche: {anche}.",
                  *[m["id"] for m in p["anche"]])
        if p.get("spunti"):
            spunti = "; ".join(s["esteso"] for s in p["spunti"])
            R.add("stagionalita", f"Spunti da valutare per {p['etichetta']}: {spunti}.")
        if p.get("limiti_superati"):
            R.add("superamenti", f"Periodo {p['etichetta']}: un limite del D.Lgs. 155/2010 è stato superato, a parità di "
                                 f"statistica, in almeno un mese e un anno per {elenco(p['limiti_superati'])} (per i "
                                 f"limiti annui il confronto con la media del mese è solo indicativo).",
                  *[f"aria:{x}" for x in p["limiti_superati"]])
        else:
            R.add("superamenti", f"Periodo {p['etichetta']}: nessun limite del D.Lgs. 155/2010 superato.")
    if k.get("attenzione"):
        mesi = elenco(f"{_mese(a['mese'])} ({elenco(nome(t) for t in a['temi'])})" for a in k["attenzione"])
        R.add("stagionalita", f"{area}, da tenere d'occhio (critici per un solo tema, fuori dai periodi): {mesi}.",
              *[t for a in k["attenzione"] for t in a["temi"]])
    contati = [t for t in k["temi"] if t["entra"]]
    fuori = [t for t in k["temi"] if not t["entra"]]
    testo = f"{area}: temi contati {n}, cioè {elenco(nome(t['id']) for t in contati)}."
    if fuori:
        testo += " Fuori dal conteggio: " + elenco(nome(t["id"]) + (f" ({t['motivo']})" if t.get("motivo") else "")
                                                  for t in fuori) + "."
    R.add("stagionalita", testo, *[t["id"] for t in contati])
    _fatti_cambiamenti(R, st, area, solo_cambiati=True)


# --- medicina di iniziativa (10/11/2026): lo scopo di ONE, sulla card «Quando intervenire» --------------------------
#
# Due analisi in più sul sommario della Stagionalità, dai dati che il server prepara in `iniziativa`
# (localhost/server/main.py, _dati_iniziativa): ricoveri, PS e ADI simulati degli ultimi 12 mesi per l'area della card
# («ospedalizzazione») e per le zone dell'area («priorita_zone»: i 20 distretti dal Salento, i comuni da un distretto).
# Le zone si ordinano tema per tema, senza punteggio unico (come l'indice di salubrità e lo UHRI): una zona è
# prioritaria se è fra le prime 3 per almeno 2 dei 3 temi, la stessa regola dei periodi critici.

RIGHE_INIZIATIVA = ("ricoveri_respiratori", "adi_accessi_ps", "pronto_soccorso")  # righe simulate: avvertenza «simulato»
# il nome del tema («Assistiti ADI») si leggerebbe come numero di assistiti: qui si dice cosa si conta
NOMI_INIZIATIVA = {"ricoveri_respiratori": "ricoveri respiratori",
                   "adi_accessi_ps": "accessi in pronto soccorso degli assistiti in ADI",
                   "pronto_soccorso": "accessi in pronto soccorso"}
TEMI_PRIORITA = (  # id, nome, come si calcola dai valori della zona
    ("ricoveri", "ricoveri respiratori e circolatori",
     lambda v: v["ricoveri_respiratori"] + v["ricoveri_circolatori"]),
    ("bassa_urgenza", "accessi in pronto soccorso a bassa urgenza degli assistiti in ADI",
     lambda v: v["adi_accessi_bassa_urgenza"]),
    ("ritorni", "ritorni in pronto soccorso entro 30 giorni degli assistiti in ADI", lambda v: v["adi_ritorni_30g"]),
)
PRIME = 3
TEMI_PER_PRIORITA = 2
PER_100K = "per 100.000 residenti al giorno"


def _tasso(v):
    """I tassi simulati sono piccoli e vicini fra le zone: due decimali sotto 10."""
    return f"{v:.2f}".replace(".", ",") if v is not None and abs(v) < 10 else numero(v)


def _quota(q):
    return f"{round(q * 100)}%"


def _periodo_iniziativa(k):
    da, a = k["mesi"][0], k["mesi"][-1]
    return f"da {_mese(int(da[5:]))} {da[:4]} a {_mese(int(a[5:]))} {a[:4]}"


def _mesi_peggiori(riga):
    ranghi = [(x["rango"], x["mese"]) for x in riga.get("clima", []) if x.get("rango") is not None]
    return [m for r, m in sorted(ranghi) if r < PRIME + 1] if len(ranghi) >= 6 else []


def _fatti_ospedalizzazione(R: _Raccolta, st, area, k):
    """I numeri dell'ospedalizzazione dell'area della card: livello, quote evitabili e ripetute, confronto col
    Salento, mesi peggiori e cosa sta cambiando."""
    if not k:
        R.add("ospedalizzazione", f"{area}: i dati simulati di ricoveri, pronto soccorso e ADI non sono disponibili.")
        return
    v, quando_ = k["area"]["valori"], _periodo_iniziativa(k)
    righe_sim = RIGHE_INIZIATIVA
    R.add("ospedalizzazione", f"{area}, ultimi 12 mesi simulati ({quando_}): ricoveri respiratori "
                              f"{_tasso(v['ricoveri_respiratori'])} e circolatori {_tasso(v['ricoveri_circolatori'])} "
                              f"{PER_100K}; accessi in pronto soccorso {_tasso(v['ps_accessi'])} {PER_100K}.",
          *righe_sim, sempre=True)
    if v.get("quota_bassa_urgenza") is not None:
        R.add("ospedalizzazione", f"{area}: assistiti in ADI in carico in media {numero(v['adi_assistiti'])} ogni 100.000 "
                                  f"residenti; i loro accessi in pronto soccorso sono {_tasso(v['adi_accessi_ps'])} "
                                  f"{PER_100K}, di cui il {_quota(v['quota_bassa_urgenza'])} a bassa urgenza "
                                  f"(potenzialmente gestibili a domicilio) e il {_quota(v['quota_ritorni'])} è un ritorno "
                                  f"entro 30 giorni da un accesso precedente (accessi ripetuti).", *righe_sim, sempre=True)
    if k["livello"] == "comuni":
        s = k["salento"]["valori"]
        voci = [(n, f(v), f(s)) for _, n, f in TEMI_PRIORITA]
        R.add("ospedalizzazione", f"{area} rispetto al Salento: " + "; ".join(
            f"{n} {_tasso(a)} contro {_tasso(b)} ({percento((a - b) / b) if b else 'n.d.'})" for n, a, b in voci)
              + f", {PER_100K}.", *righe_sim, sempre=True)
    righe = _righe(st)
    mesi = [(r, _mesi_peggiori(righe[r])) for r in RIGHE_INIZIATIVA if r in righe]
    mesi = [(r, m) for r, m in mesi if m]
    if mesi:
        R.add("ospedalizzazione", f"{area}, i mesi peggiori dell'anno (rango da 1 a {PRIME}, 1 = peggiore): " + "; ".join(
            f"{NOMI_INIZIATIVA[r]} {elenco(_mese(x) for x in m)}" for r, m in mesi) + ".", *[r for r, _ in mesi],
              sempre=True)
    for r in RIGHE_INIZIATIVA:
        if r in righe and (t := _cambiamento(righe[r], st, area, NOMI_INIZIATIVA[r])):
            R.add("ospedalizzazione", t, r, sempre=True)


def _fatti_priorita_zone(R: _Raccolta, area, k):
    """Le zone dell'area tema per tema, le prioritarie e il loro contesto (alberi, suolo, caldo estivo)."""
    if not k:
        R.add("priorita_zone", f"{area}: i dati simulati per zona non sono disponibili.")
        return
    comuni = k["livello"] == "comuni"
    plurale, singolare = ("comuni", "comune") if comuni else ("distretti", "distretto")
    soglia = k["soglia_residenti"]
    zone = [z for z in k["zone"] if not comuni or z["residenti"] >= soglia]
    piccoli = [z["nome"] for z in k["zone"] if comuni and z["residenti"] < soglia]
    quando_ = _periodo_iniziativa(k)
    righe_sim = RIGHE_INIZIATIVA
    R.add("priorita_zone", f"Come si scelgono le zone: per ognuno dei 3 temi (ricoveri respiratori e circolatori, accessi "
                           f"in pronto soccorso a bassa urgenza degli assistiti in ADI, ritorni in pronto soccorso entro "
                           f"30 giorni degli assistiti in ADI) si ordinano i {plurale} sul tasso {PER_100K} degli ultimi "
                           f"12 mesi ({quando_}); un {singolare} è prioritario se è fra i primi {PRIME} per almeno "
                           f"{TEMI_PER_PRIORITA} temi. Nessun punteggio unico.", *righe_sim, sempre=True)
    if piccoli:
        R.add("priorita_zone", f"Fuori dalla classifica, con meno di {soglia} residenti (troppi pochi eventi per un tasso "
                               f"stabile): {elenco(piccoli)}.", sempre=True)
    if len(zone) <= PRIME:
        R.add("priorita_zone", f"{area}: solo {len(zone)} {plurale} con almeno {soglia} residenti, troppo pochi per una "
                               f"classifica.", sempre=True)
        return
    primi = {}
    for i, nome, f in TEMI_PRIORITA:
        ordinate = sorted(zone, key=lambda z: -f(z["valori"]))
        primi[i] = [z["id"] for z in ordinate[:PRIME]]
        mediana = sorted(f(z["valori"]) for z in zone)[len(zone) // 2]
        R.add("priorita_zone", f"{area}, {nome}: i {PRIME} {plurale} più alti sono " + elenco(
            f"{z['nome']} con {_tasso(f(z['valori']))}" for z in ordinate[:PRIME])
              + f" {PER_100K}; la mediana dei {plurale} è {_tasso(mediana)}.", *righe_sim, sempre=True)
    conta = {z["id"]: sum(z["id"] in p for p in primi.values()) for z in zone}
    per_id = {z["id"]: z for z in zone}
    prioritarie = sorted((i for i, n in conta.items() if n >= TEMI_PER_PRIORITA), key=lambda i: (-conta[i], per_id[i]["nome"]))
    if prioritarie:
        R.add("priorita_zone", f"{area}, {plurale} prioritari (fra i primi {PRIME} per almeno {TEMI_PER_PRIORITA} temi): "
              + elenco(f"{per_id[i]['nome']}, {conta[i]} temi su 3" for i in prioritarie) + ".", *righe_sim, sempre=True)
    else:
        una = sorted((i for i, n in conta.items() if n == 1), key=lambda i: per_id[i]["nome"])
        R.add("priorita_zone", f"{area}: nessun {singolare} è fra i primi {PRIME} per almeno {TEMI_PER_PRIORITA} temi; fra "
                               f"i primi {PRIME} di un solo tema: {elenco(per_id[i]['nome'] for i in una)}.",
              *righe_sim, sempre=True)
    # contesto delle prioritarie (o, senza, delle prime del tema ADI): alberi, suolo e caldo d'estate contro la mediana
    contesto = prioritarie or primi["bassa_urgenza"]

    def mediana(campo):
        x = sorted(z[campo] for z in zone if z.get(campo) is not None)
        return x[len(x) // 2] if x else None

    med = {c: mediana(c) for c in ("alberi", "suolo", "estate")}

    def rispetto(v, campo):
        """Il confronto con la mediana detto a parole: il modello leggeva «suolo impermeabile 3,7%» contro «5,4%» come
        suolo poco permeabile (prova del 10/11/2026)."""
        m = med[campo]
        return "" if m is None else " (pari alla mediana)" if v == m else " (sopra la mediana)" if v > m else " (sotto la mediana)"

    parti = []
    for i in contesto:
        z = per_id[i]
        p = [f"copertura arborea {numero(z['alberi'])}%{rispetto(z['alberi'], 'alberi')}" if z.get("alberi") is not None else None,
             f"suolo impermeabile {numero(z['suolo'])}%{rispetto(z['suolo'], 'suolo')}" if z.get("suolo") is not None else None,
             f"temperatura massima media di luglio e agosto {numero(z['estate'])} °C{rispetto(z['estate'], 'estate')}"
             if z.get("estate") is not None else None]
        if any(p):
            parti.append(f"{z['nome']}: " + ", ".join(x for x in p if x))
    if parti:
        meds = [f"copertura arborea {numero(med['alberi'])}%" if med["alberi"] is not None else None,
                f"suolo impermeabile {numero(med['suolo'])}%" if med["suolo"] is not None else None,
                f"temperatura {numero(med['estate'])} °C" if med["estate"] is not None else None]
        R.add("priorita_zone", f"Contesto delle zone indicate (caldo ERA5-Land, modellato; alberi e suolo CLMS): "
              + "; ".join(parti) + f". Mediana dei {plurale}: " + ", ".join(x for x in meds if x) + ".", sempre=True)
    if comuni and k.get("distretti"):
        tutti = k["distretti"]
        posti = []
        for _, nome, f in TEMI_PRIORITA:
            ordinati = sorted(tutti, key=lambda z: -f(z["valori"]))
            posto = next(n for n, z in enumerate(ordinati, 1) if z["id"] == k["area"]["id"])
            posti.append(f"{nome} {posto}° su {len(tutti)}")
        R.add("priorita_zone", f"{area} fra i distretti del Salento (1° = tasso più alto): " + "; ".join(posti) + ".",
              *righe_sim, sempre=True)


def _scheda_anno_su_anno(R: _Raccolta, st, area, natura_aria, indicatore, verso):
    """Il grafico «anno su anno» di un indicatore: ogni anno come serie di 12 mesi (analisi generiche), il mese
    peggiore di ogni anno e quante volte cade in un periodo critico (la lettura sopra il grafico), ranghi e periodi."""
    r = _righe(st).get(indicatore)
    if r is None or not r.get("anni"):
        raise AnalisiNonApplicabile(f"indicatore senza valori anno per anno: {indicatore}")
    nome, confronto = _nome(r, st), [str(a) for a in st["anni_confronto"]]
    anni = sorted(r["anni"])
    storico = [a for a in anni if a not in confronto]
    k = st.get("criticita") or {}
    for a in confronto:
        punti = [_punto(f"{a}-{m:02d}", c) for m, c in enumerate(r["anni"].get(a) or [None] * 12, 1)]
        R.extend(analisi.riepilogo(_serie_riga(r, st, natura_aria, f"{nome} nel {a}", punti, "mese", area)), r["id"])
    # lo storico in un fatto solo: tredici anni di decessi farebbero ventisei frasi
    medie = [(a, mean(v)) for a in storico if (v := [c["valore"] for c in r["anni"][a]
                                                     if c["stato"] == "VALORE" and c.get("completo") and c["valore"] is not None])]
    if medie:
        R.add("riepilogo", f"{area}, {nome} negli anni dello storico, fuori da medie e ranghi, media dei mesi completi"
                           f"{', in ' + _unita(r) if _unita(r) else ''}: {'; '.join(f'{a} {numero(v)}' for a, v in medie)}.",
              r["id"])

    def picco(a):
        celle = [(m, c) for m, c in enumerate(r["anni"].get(a, []), 1)
                 if c["stato"] == "VALORE" and c.get("completo") and c["valore"] is not None]
        if not celle:
            return None
        m, c = (max if verso == "alti" else min)(celle, key=lambda x: x[1]["valore"])
        fino = f", dati fino a {_mese(celle[-1][0])}" if len(celle) < 12 else ""
        return m, f"{a} {_mese(m)} con {_val(c['valore'], r)}{fino}"

    parola = "peggiore" if verso == "alti" else "migliore"
    picchi = [p for a in confronto if (p := picco(a))]
    if picchi:
        R.add("estremi", f"{area}, {nome}, mese {parola} di ogni anno del confronto: {'; '.join(t for _, t in picchi)}.",
              r["id"])
        nel_periodo = {m for p in k.get("periodi", []) for m in p["mesi"]}
        if verso == "alti" and nel_periodo:
            dentro = sum(m in nel_periodo for m, _ in picchi)
            R.add("estremi", f"{area}, {nome}: il mese peggiore cade in un periodo critico {dentro} "
                             f"{'volta' if dentro == 1 else 'volte'} su {len(picchi)}.", r["id"])
    vecchi = [p for a in storico if (p := picco(a))]
    if vecchi:
        R.add("estremi", f"{area}, {nome}, mese {parola} negli anni dello storico: {'; '.join(t for _, t in vecchi)}.",
              r["id"])
    ranghi = sorted(((m["mese"], m["rango"]) for m in r["clima"] if m.get("rango") is not None), key=lambda t: t[1])
    if ranghi:
        R.add("stagionalita", f"{area}, {nome}, rango dei 12 mesi sulla media {elenco(confronto)} (1 = peggiore): "
                              f"{', '.join(f'{_mese(m)} {_rango(x)}' for m, x in ranghi)}.", r["id"])
    if k.get("periodi"):
        periodi = "; ".join(f"{i}. {p['etichetta']}" for i, p in enumerate(k["periodi"], 1))
        R.add("stagionalita", f"{area}: periodi critici, le fasce grigie numerate del grafico: {periodi}.")
    if t := _cambiamento(r, st, area):
        R.add("anni_precedenti", t, r["id"])
        R.add("anni_precedenti", REGOLA_CAMBIAMENTI)
    covid = [a for a in storico if a in ANNI_COVID]
    R.add("copertura", f"{area}, {nome}: anni del confronto, in medie e ranghi, {elenco(confronto)}"
                       + (f"; storico, fuori da medie e ranghi, {elenco(storico)}" if storico else "")
                       + (f", di cui {elenco(covid)} anni del COVID" if covid else "") + ".", r["id"])


def _scheda_dettaglio_mese(R: _Raccolta, st, area, natura_aria, mese, verso):
    """La tabella di un mese anno per anno: per indicatore i valori di ogni anno e la media (riepilogo), il rango del
    mese, la Δ (anni_precedenti, la stessa regola della card), gli anni estremi e i limiti superati."""
    nome_mese = _mese(mese)
    confronto = [str(a) for a in st["anni_confronto"]]
    anni = [str(a) for a in (st.get("anni_storico") or st["anni_confronto"])]
    storico = [a for a in anni if a not in confronto]
    k = st.get("criticita") or {}
    if k.get("mesi"):
        c = k["mesi"][mese - 1]
        righe = _righe(st)
        temi = {t["id"]: t["nome"] for t in k["temi"]}
        if c["conteggio"]:
            R.add("stagionalita", f"{area}: {nome_mese} è fra i {k.get('mesi_critici_per_tema', 3)} mesi peggiori per "
                                  f"{c['conteggio']} {'tema' if c['conteggio'] == 1 else 'temi'} su {k['temi_contati']}: "
                                  f"{elenco(_nome(righe[t], st) if t in righe else _minuscola(temi.get(t, t)) for t in c['temi'])}.",
                  *c["temi"])
        else:
            R.add("stagionalita", f"{area}: {nome_mese} non è fra i mesi peggiori di nessun tema.")
    for r in st["righe"]:
        if not r.get("anni"):
            continue
        nome = _nome(r, st)
        celle = {a: (r["anni"].get(a) or [None] * 12)[mese - 1] for a in anni}

        def cella(a):
            c = celle[a]
            if c is None or c["stato"] != "VALORE" or c["valore"] is None:
                return f"{a} N/D"
            return (f"{a} {numero(c['valore'])}" + ("" if c.get("completo") else " parziale")
                    + (" (limite superato)" if c.get("limite_superato") else ""))

        m = r["clima"][mese - 1]
        u = _unita(r)
        unita = "" if not u else f", {u}" if u.startswith("per ") else f", in {u}"
        testo = f"{area}, {nome} {_a_mese(mese)}{unita}: {'; '.join(cella(a) for a in confronto)}"
        testo += (f"; media {numero(m['valore'])} (anni {elenco(m['anni'])})" if m.get("valore") is not None
                  else "; nessuna media, nessun mese completo")
        if storico:
            testo += f"; storico, fuori dalla media: {'; '.join(cella(a) for a in storico)}"
        R.add("riepilogo", testo + ".", r["id"])
        if m.get("rango") is not None:
            R.add("stagionalita", f"{area}, {nome}: {nome_mese} ha rango {_rango(m['rango'])} su 12 fra i mesi "
                                  f"dell'anno (1 = peggiore).", r["id"])
        variabile = f"{nome} di {nome_mese}"
        s = _serie_riga(r, st, natura_aria, variabile, [_punto(a, celle[a]) for a in confronto], "anno", area)
        R.extend(analisi.anni_precedenti(s), r["id"])
        s = _serie_riga(r, st, natura_aria, variabile, [_punto(a, celle[a]) for a in anni], "anno", area)
        R.extend(analisi.estremi(s, verso=verso), r["id"])
        if any(c and c.get("limite_superato") is not None for c in celle.values()):
            sup = [(a, c) for a, c in celle.items() if c and c.get("limite_superato")]
            if sup:
                dettaglio = "; ".join(f"{a}, {t}" for a, c in sup for t in c.get("limiti_superati") or [])
                R.add("superamenti", f"{area}, {nome} {_a_mese(mese)}: limite del D.Lgs. 155/2010 superato nel "
                                     f"{elenco(a for a, _ in sup)}" + (f": {dettaglio}" if dettaglio else "") + ".",
                      r["id"])
            else:
                R.add("superamenti", f"{area}, {nome} {_a_mese(mese)}: nessun limite del D.Lgs. 155/2010 superato in "
                                     f"nessun anno.", r["id"])


def _scheda_cambiamenti(R: _Raccolta, st, area, verso):
    """«Cosa sta cambiando»: l'andamento di ogni indicatore, gli scarti più grandi e i domini rimasti indietro."""
    _fatti_cambiamenti(R, st, area)
    voci = [r for r in st["righe"] if _cambiamento(r, st, area)]
    pct = sorted((r for r in voci if r["id"] != "calore" and r["andamento"].get("delta_percentuale") is not None),
                 key=lambda r: r["andamento"]["delta_percentuale"], reverse=verso == "alti")[:3]
    if pct:
        R.add("estremi", f"{area}: scarti {'più alti' if verso == 'alti' else 'più bassi'} dagli anni precedenti, in "
                         f"percentuale: {elenco(_nome(r, st) + ' ' + percento(r['andamento']['delta_percentuale']) for r in pct)}.",
              *[r["id"] for r in pct])
    if calore := next((r for r in voci if r["id"] == "calore"), None):
        R.add("estremi", f"{area}: la temperatura massima, che ha una scala sua in gradi, ha uno scarto di "
                         f"{con_segno(calore['andamento']['delta'])} °C.", "calore")
    corrente = st["oggi"][:7]
    indietro = {}
    for r in st["righe"]:
        a = r.get("andamento") or {}
        chiave = "aria" if r["id"].startswith("aria:") else "simulati" if r.get("simulata") else r["id"]
        if any(m != corrente for m in a.get("mesi_senza_dati") or []):
            indietro.setdefault(chiave, []).append(r)
    for chiave, rr in indietro.items():
        a = rr[0]["andamento"]
        rif = a["mese_riferimento"]
        motivo = f"; {a['motivo_senza_dati']}" if a.get("motivo_senza_dati") else ""
        R.add("copertura", f"{area}, {NOMI_DOMINIO.get(chiave, _nome(rr[0], st))}: ultimo mese completo "
                           f"{_mese(int(rif[5:7]))} {rif[:4]}{motivo}.", *[r["id"] for r in rr])
    if not indietro:
        R.add("copertura", f"{area}: nessun dominio indietro oltre il mese in corso.")
    senza = [r for r in st["righe"] if (r.get("andamento") or {}).get("classe") in ("storico_insufficiente", "nessun_dato")]
    if senza:
        R.add("copertura", f"{area}: senza confronto con gli anni precedenti, {elenco(_nome(r, st) for r in senza)}.",
              *[r["id"] for r in senza])


def _stagione(card, dati, p, scelte=None):
    """dati: {"st": risposta di /api/stagionalita, "area": nome leggibile, "natura_aria": misto | modellato | misurato}.
    Su «anno_su_anno» `indicatore` è la riga del grafico; sulle altre card filtra i fatti («" = tutti)."""
    st, area, natura = dati["st"], dati["area"], dati["natura_aria"]
    R = _Raccolta()
    verso = p.get("verso") or "alti"
    if card == "consiglio":
        _scheda_consiglio(R, st, area)
        # medicina di iniziativa (10/11/2026): solo quando la domanda le chiede, non nella scheda intera della card
        if scelte and "ospedalizzazione" in scelte:
            _fatti_ospedalizzazione(R, st, area, dati.get("iniziativa"))
        if scelte and "priorita_zone" in scelte:
            _fatti_priorita_zone(R, area, dati.get("iniziativa"))
    elif card == "anno_su_anno":
        _scheda_anno_su_anno(R, st, area, natura, p["indicatore"], verso)
    elif card == "dettaglio_mese":
        _scheda_dettaglio_mese(R, st, area, natura, p["mese_dell_anno"], verso)
    else:
        _scheda_cambiamenti(R, st, area, verso)
    fatti, usate = R.scegli(scelte, None if card == "anno_su_anno" else p.get("indicatore"))
    if not fatti:
        raise AnalisiNonApplicabile("nessuna delle analisi scelte si applica ai dati della card")
    _numera(fatti)
    return {"fatti": fatti, "avvertenze": _avvertenze_stagione(st, area, usate, natura, medie=card != "cambiamenti",
                                                               consiglio=card == "consiglio")}


# --- punto d'ingresso -----------------------------------------------------------------------------------------------

def scheda(card, dati, p):
    """Scheda intera di una card. `p`: i parametri controllati (perimetro.controlla_parametri)."""
    if card == "andamento":
        return scheda_andamento(*dati, soglia=p.get("soglia"))
    if card == "domini":
        return scheda_domini(dati["aria"], dati["decessi"], dati.get("temperatura"), dati["comuni_esclusi"])
    if card in schede_istantanee.CARD:
        return schede_istantanee.scheda(card, dati, p)
    return _stagione(card, dati, p)


def fatti(card, dati, scelte, p):
    """Solo le analisi scelte dall'instradamento (§13.1), con i parametri della domanda."""
    if card == "andamento":
        return fatti_andamento(*dati, scelte, p["variabile"], p["soglia"], p["verso"])
    if card == "domini":
        return fatti_domini(dati["aria"], dati["decessi"], scelte, p["variabile"], p["verso"], dati["comuni_esclusi"],
                            dati.get("temperatura"), p.get("esposizione", "inquinante"))
    if card in schede_istantanee.CARD:
        return schede_istantanee.scheda(card, dati, p, scelte)
    return _stagione(card, dati, p, scelte)
