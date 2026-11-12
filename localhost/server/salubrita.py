"""Indice di salubrità dell'aria rispetto ai limiti di legge (docs/Regole_dei_dati.md, 11/10/2026; report
data/dataset/aria/Valori_Riferimento_Normativi.md). Motore puro, senza dipendenze da FastAPI:
riceve, per la zona e la finestra, i **valori giornalieri** per fonte e inquinante e li confronta
con i tre quadri normativi (D.Lgs. 155/2010 in vigore, OMS 2021, direttiva UE 2024/2881).

Regole (report §2 e §5bis), confronto **solo a parità di statistica**:

- dato misurato *media giornaliera* (OpenAQ, EEA, CAMS; ARPA per PM) → limite su *media 24 h*
  (conteggio dei giorni di superamento) e, indicativo, *media annua* (media della finestra vs limite);
- dato misurato *massimo orario del giorno* (ARPA per NO2/O3/SO2) → limite *orario* (giorni col massimo
  oltre soglia); **non** si confronta col valore obiettivo O3 su 8 h (statistica diversa);
- dato misurato *massimo della media mobile 8 h* (ARPA per CO) → limite su *max 8 h*;
- ogni altra combinazione → «non confrontabile» (nessuna percentuale).

Dato che la finestra della dashboard è al più un mese, il confronto con la *media annua* è sempre
**indicativo** (la media di un periodo più corto dell'anno, stessa statistica ma non la metrica di legge).

Indice complessivo = **peggiore inquinante** (stile EAQI europeo / IQA italiano, nessun peso arbitrario).
La banda dell'intestazione/mappa segue il **D.Lgs. 155/2010 in vigore**; gli esiti riportano tutti e tre i quadri.
"""

from api.aria.anagrafica_aria import RIFERIMENTI_NORMATIVI

QUADRI = ("dlgs_155_2010", "oms_2021", "ue_2024_2881")

# dato misurato (token) → {statistica del limite: tipo di confronto}
COMPATIBILITA = {
    "media_giornaliera": {"media_24h": "giorni_superamento", "media_annua": "media_indicativa"},
    "massimo_orario_giorno": {"massimo_orario": "giorni_superamento"},
    "massimo_8h": {"massimo_8h": "giorni_superamento"},
}

ORDINE_BANDE = {"buona": 0, "accettabile": 1, "scadente": 2, "cattiva": 3}


def token_misura(statistica_dichiarata):
    """Stringa di statistica dell'adattatore → token confrontabile, o None se non classificabile.
    ARPA: 'media giornaliera' | 'massimo orario del giorno' | 'massimo giornaliero della media mobile su 8 ore';
    OpenAQ/EEA/CAMS: una media ('media pesata sul tempo...', 'media oraria del giorno...')."""
    if not statistica_dichiarata:
        return None
    s = statistica_dichiarata.lower()
    if s.startswith("media"):
        return "media_giornaliera"
    if "8 ore" in s or "8h" in s or "media mobile" in s:
        return "massimo_8h"
    if s.startswith("massimo") or s.startswith("max"):
        return "massimo_orario_giorno"
    return None


def riferimenti():
    """{id_inquinante: {quadro: [ {statistica, valore, unita, superamenti_ammessi, nota} ]}}.

    Fonte autorevole: la costante RIFERIMENTI_NORMATIVI nel codice (api/aria/anagrafica_aria.py), **non** il JSON
    dell'anagrafica: il JSON è un mirror che una rigenerazione può azzerare, il dato di legge no."""
    return {inq: n["riferimenti"] for inq, n in RIFERIMENTI_NORMATIVI.items()}


def _banda_rapporto(r):
    if r <= 0.5:
        return "buona"
    if r <= 1.0:
        return "accettabile"
    if r <= 1.5:
        return "scadente"
    return "cattiva"


def _banda_frazione(fr):
    if fr <= 0.0:
        return "buona"
    if fr <= 0.10:
        return "accettabile"
    if fr <= 0.25:
        return "scadente"
    return "cattiva"


def _peggiore(bande):
    scelte = [b for b in bande if b in ORDINE_BANDE]
    if not scelte:
        return "non_confrontabile"
    return max(scelte, key=ORDINE_BANDE.get)


def _esito(fonte, quadro, ref, tipo, token, valori, finestra_intera):
    """Un esito {dict} pronto per EsitoRiferimento, o None se non calcolabile."""
    limite = ref["valore"]
    unita = ref.get("unita")
    gc = len(valori)
    base = dict(fonte=fonte, quadro=quadro, statistica=ref["statistica"], statistica_misura=token,
                limite=float(limite), unita=unita, tipo=tipo, giorni_con_valore=gc,
                superamenti_ammessi_anno=ref.get("superamenti_ammessi"))
    if tipo == "giorni_superamento":
        if gc == 0:
            return None
        oltre = sum(1 for v in valori if v > limite)
        fr = oltre / gc
        return {**base, "giorni_superamento": oltre, "rapporto": fr, "superato": oltre > 0,
                "indicativo": False, "banda": _banda_frazione(fr),
                "nota": f"{oltre} giorno/i oltre {limite} {unita} su {gc} con valore"
                        + (f"; {ref['superamenti_ammessi']} superamenti ammessi/anno" if ref.get("superamenti_ammessi") else "")}
    # media_indicativa
    if gc == 0:
        return None
    media = sum(valori) / gc
    r = media / limite if limite else None
    return {**base, "valore": media, "rapporto": r, "superato": media > limite,
            "indicativo": not finestra_intera, "banda": _banda_rapporto(r) if r is not None else "non_confrontabile",
            "nota": ("media della finestra vs media annua di legge: indicativo, non è la metrica annuale"
                     if not finestra_intera else "finestra di un anno: confronto con la media annua di legge")}


def valuta_inquinante(inquinante, misure, finestra_intera=False):
    """misure: lista di {fonte, statistica (stringa dichiarata), valori (list[float] dei giorni con VALORE)}.
    Ritorna un dict pronto per SalubritaInquinante, o None se non ci sono riferimenti per l'inquinante."""
    rif_inq = riferimenti().get(inquinante)
    if not rif_inq:
        return None
    esiti, stat_misura = [], {}
    for m in misure:
        stat_misura[m["fonte"]] = m["statistica"]
        token = token_misura(m["statistica"])
        if token is None or not m["valori"]:
            continue
        compat = COMPATIBILITA.get(token, {})
        for quadro in QUADRI:
            for ref in rif_inq.get(quadro, []):
                if ref.get("valore") is None:
                    continue
                tipo = compat.get(ref["statistica"])
                if not tipo:
                    continue
                e = _esito(m["fonte"], quadro, ref, tipo, token, m["valori"], finestra_intera)
                if e is not None:
                    esiti.append(e)
    banda_dlgs = _peggiore([e["banda"] for e in esiti if e["quadro"] == "dlgs_155_2010"])
    nota = None
    if not esiti:
        nota = "nessun limite confrontabile con la statistica del dato disponibile a questa grana"
    return {"inquinante": inquinante, "confrontabile": bool(esiti), "banda": banda_dlgs,
            "statistiche_misura": stat_misura, "esiti": esiti, "nota": nota}


def valuta_zona(misure_per_inquinante, finestra_intera=False):
    """misure_per_inquinante: {inquinante: [ {fonte, statistica, valori} ]}. Ritorna un dict pronto per SalubritaZona."""
    per_inq = []
    for inq in sorted(misure_per_inquinante):
        s = valuta_inquinante(inq, misure_per_inquinante[inq], finestra_intera)
        if s is not None:
            per_inq.append(s)
    confrontabili = [s for s in per_inq if s["banda"] in ORDINE_BANDE]
    if confrontabili:
        peggiore = max(confrontabili, key=lambda s: ORDINE_BANDE[s["banda"]])
        banda, inq_peggiore = peggiore["banda"], peggiore["inquinante"]
    else:
        banda, inq_peggiore = "non_confrontabile", None
    return {"banda": banda, "inquinante_peggiore": inq_peggiore, "per_inquinante": per_inq}
