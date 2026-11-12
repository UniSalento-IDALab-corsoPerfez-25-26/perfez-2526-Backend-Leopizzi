"""Stagionalità (tab «Stagionalità» della dashboard, 16/10/2026; spec in repository Frontend, docs/Specifiche_Design.md):
i 12 mesi dell'anno a confronto su aria, calore e decessi, per il Salento intero o un distretto.

Due parti:

1. **Riassunti mensili su disco** (`data/interim/stagionalita/`, gitignored). Per ogni mese dell'archivio, un JSON
   con il valore del mese di ogni zona (Salento + 20 distretti) × fonte × inquinante e l'esito dei limiti del
   D.Lgs. 155/2010; uno per il calore (ERA5-Land, T media e T massima). Li scrive
   `scripts/dashboard/prepara_stagionalita.py`, che **ricalcola solo i mesi non ancora preparati** (o il cui file
   di origine è cambiato, firma come in `CacheAria`): un mese d'aria costa ~14 s, i 34 mesi ~8 minuti una volta
   sola. Il server li legge e basta, non calcola mai un mese dentro una richiesta.
2. **Calcolo della stagionalità** (`calcola()`), leggero, a ogni richiesta: medie per mese dell'anno, ranghi
   1-12, aria complessiva (rango medio dei 5 inquinanti), criticità dell'anno, andamento dell'ultimo mese completo
   sugli anni precedenti.

Regole (scelte di Matteo del 16/10/2026, riviste il 29/10/2026):
- grana = mese; zona = Salento (media pesata sui residenti di tutti i comuni; decessi = somma dei distretti) o un
  distretto; aria = vista «Tutte» di default o una fonte; decessi = media giornaliera del mese (totale ÷ giorni);
- anni dei ranghi = quelli comuni a tutti i domini, **dal 2024** (`PRIMO_ANNO_CONFRONTO`, confermato il 29/10/2026:
  prima si partiva dal primo riassunto d'aria preparato e nel 2020-2023 entravano anche gli anni COVID); lo storico
  precedente si restituisce per il dettaglio anno per anno e per il grafico anno su anno, fuori da medie e ranghi;
- solo i **mesi completi** entrano nei ranghi e nell'andamento; il mese in corso e quelli senza dato si dichiarano;
- **rango 1 = mese peggiore** (valore più alto: concentrazione, T massima, eventi al giorno), 12 = migliore, in
  tutta la tab (29/10/2026: prima la griglia andava da 1 migliore a 12 peggiore e il calendario al contrario); a pari
  merito rango medio;
- aria complessiva = media dei ranghi dei 5 inquinanti di riferimento, poi riordinata da 1 a 12; per ogni mese si dice
  se un limite del D.Lgs. 155/2010 è superato (in almeno un anno); i limiti si confrontano **solo a parità di
  statistica** (localhost/server/salubrita.py). Con «Tutte» si usano tutte le fonti reali, come nel pannello della
  zona; per il Salento un limite è superato se lo è in almeno un distretto (una media sul territorio diluirebbe il
  superamento di una zona);
- andamento = ultimo mese completo vs media dello stesso mese negli anni precedenti: ±10% per aria e decessi,
  ±1 °C per la temperatura (sui gradi Celsius una percentuale non ha senso: lo zero è convenzionale);
- **criticità dell'anno** (27/10/2026, `criticita()`): un mese è critico per un tema se è fra i suoi 3 mesi peggiori;
  un indicatore per tema (aria complessiva, T massima, decessi, PS, PS degli assistiti ADI, ricoveri respiratori; gli
  ultimi tre **simulati**, data/dataset/salute/simulati/Dati_Simulati.md); i mesi vicini con almeno due temi critici
  formano un periodo, col perché e gli indicatori di dettaglio. `simulati_nella_sintesi` toglie i simulati dal
  conteggio. **Il «mese peggiore» della tab è il picco del primo periodo** (29/10/2026, scelta di Matteo): la somma
  dei ranghi (periodo peggiore, 16-25/10/2026) è stata tolta, perché dava un mese diverso dal consiglio.

Esplorativo, non causale.
"""

import json
import math
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from api.comune.aggregazione import media_per_distretto, per_mese
from api.comune.stati import STATO_NO_DATA, STATO_NULL, STATO_VALORE
from localhost.server import salubrita
from localhost.server.aggregati_aria import FONTE_ACCORPATA, statistica

RADICE = Path(__file__).resolve().parents[2]
DIR_STAGIONALITA = RADICE / "data" / "interim" / "stagionalita"
VERSIONE = 1  # cambia se cambia il calcolo dei riassunti: i file di una versione diversa si rifanno
ZONA_SALENTO = "SALENTO"
STATISTICHE_CALORE = ("media", "massima")
SOGLIA_RELATIVA = 0.10  # ±10% per aria e decessi
SOGLIA_GRADI = 1.0      # ±1 °C per la temperatura
PRIMO_ANNO_CONFRONTO = 2024  # primo anno con tutti i domini (simulati compresi), come l'inizio della barra temporale
NOMI_MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
             "ottobre", "novembre", "dicembre")


def _num(v):
    """float pulito o None (NaN, NA)."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _testo(v):
    return v if isinstance(v, str) and v else None


def giorni_del_mese(mese):
    return monthrange(int(mese[:4]), int(mese[5:]))[1]


def nome_mese(m):
    return NOMI_MESI[m - 1]


def etichetta_mese(mese):
    return f"{nome_mese(int(mese[5:]))} {mese[:4]}"


# ======================================================================================== riassunti su disco

def file_aria(mese):
    return DIR_STAGIONALITA / f"aria_{mese}.json"


def file_calore(mese):
    return DIR_STAGIONALITA / f"calore_{mese}.json"


def leggi(percorso):
    try:
        return json.loads(Path(percorso).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def scrivi(percorso, dati):
    percorso = Path(percorso)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    tmp = percorso.with_suffix(".tmp")
    tmp.write_text(json.dumps(dati, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(percorso)


def aggiornato(percorso, firma):
    """True se il riassunto esiste, è della versione corrente ed è stato fatto sugli stessi file di origine."""
    r = leggi(percorso)
    return bool(r) and r.get("versione") == VERSIONE and r.get("firma") == [list(x) for x in firma]


def _pesi_salento(pesi):
    return {c: (ZONA_SALENTO, residenti) for c, (_, residenti) in pesi.items()}


def _celle_mese(mensile, colonna_zona):
    """{zona: {fonte: {inquinante: cella}}} da un frame per_mese."""
    out = {}
    for r in mensile.itertuples():
        out.setdefault(getattr(r, colonna_zona), {}).setdefault(r.fonte, {})[r.inquinante] = {
            "valore": _num(r.valore), "stato": r.stato, "nota": _testo(r.nota),
            "giorni": int(r.giorni), "giorni_con_valore": int(r.giorni_con_valore)}
    return out


def _limiti_dlgs(inquinante, fonte, valori):
    """Esiti del D.Lgs. 155/2010 (legge in vigore) per i valori giornalieri di un mese, a parità di statistica."""
    s = salubrita.valuta_inquinante(inquinante, [{"fonte": fonte, "statistica": statistica(fonte, inquinante), "valori": valori}])
    if s is None:
        return []
    return [{"statistica": e["statistica"], "limite": e["limite"], "unita": e["unita"], "tipo": e["tipo"],
             "superato": bool(e["superato"]), "indicativo": bool(e["indicativo"]),
             "giorni_superamento": e.get("giorni_superamento"), "valore": _num(e.get("valore")),
             "giorni_con_valore": e["giorni_con_valore"], "nota": e["nota"]}
            for e in s["esiti"] if e["quadro"] == "dlgs_155_2010"]


def riassunto_aria(mese, agg, pesi, firma):
    """Riassunto di un mese d'aria da un AggregatiMese: valore del mese per zona × fonte × inquinante e limiti."""
    cg = agg.comune_giorno
    # Salento: media pesata sui residenti di tutti i comuni con VALORE (stessa regola del distretto)
    sal = media_per_distretto(cg[["comune", "giorno", "fonte", "inquinante", "valore", "stato", "nota"]],
                              pesi=_pesi_salento(pesi), colonna_tempo="giorno", chiavi=["fonte", "inquinante"])
    zone = _celle_mese(per_mese(agg.distretto_giorno, chiavi=("fonte", "inquinante"), colonna_zona="distretto"), "distretto")
    zone.update(_celle_mese(per_mese(sal, chiavi=("fonte", "inquinante"), colonna_zona="distretto"), "distretto"))

    # limiti: per distretto dai valori giornalieri di ogni fonte reale (la vista «Tutte» non è una fonte)
    dg = agg.distretto_giorno
    validi = dg[(dg["stato"] == STATO_VALORE) & (dg["fonte"] != FONTE_ACCORPATA)]
    limiti = {}
    for (distretto, fonte, inq), g in validi.groupby(["distretto", "fonte", "inquinante"]):
        valori = [float(v) for v in g["valore"] if v == v]
        esiti = _limiti_dlgs(inq, fonte, valori) if valori else []
        if esiti:
            limiti.setdefault(distretto, {}).setdefault(fonte, {})[inq] = esiti
    # Salento: un limite è superato se lo è in almeno un distretto
    sal_lim = {}
    for distretto, per_fonte in limiti.items():
        for fonte, per_inq in per_fonte.items():
            for inq, esiti in per_inq.items():
                for e in esiti:
                    chiave = (fonte, inq, e["statistica"])
                    s = sal_lim.setdefault(chiave, {**e, "superato": False, "distretti_superati": [], "distretti": 0,
                                                     "giorni_superamento": None, "valore": None, "giorni_con_valore": None})
                    s["distretti"] += 1
                    if e["superato"]:
                        s["superato"] = True
                        s["distretti_superati"].append(distretto)
    for (fonte, inq, _), e in sal_lim.items():
        n = len(e["distretti_superati"])
        e["nota"] = (f"superato in {n} {'distretto' if n == 1 else 'distretti'} su {e['distretti']} con un valore "
                     f"({', '.join(sorted(e['distretti_superati']))})" if n
                     else f"entro il limite in tutti i distretti con un valore ({e['distretti']})")
        limiti.setdefault(ZONA_SALENTO, {}).setdefault(fonte, {}).setdefault(inq, []).append(e)

    giorni = sorted(cg["giorno"].unique())
    return {"versione": VERSIONE, "dominio": "aria", "mese": mese, "firma": [list(x) for x in firma],
            "generato_il": datetime.now().isoformat(timespec="seconds"),
            "giorni_coperti": len(giorni), "giorni_del_mese": giorni_del_mese(mese),
            "completo": len(giorni) == giorni_del_mese(mese), "ultimo_giorno": giorni[-1] if giorni else None,
            "fonti_modellate": sorted(agg.fonti_virtuali), "zone": zone, "limiti": limiti}


def firma_calore(mese):
    from api.calore import era5_land
    anno, num = int(mese[:4]), int(mese[5:])
    out = []
    for s in STATISTICHE_CALORE:
        f = era5_land._file_cache(s, anno, num)
        if f.exists():
            out.append((f.name, f.stat().st_mtime))
    return tuple(out)


def riassunto_calore(mese, archivio_calore, pesi, firma):
    """Riassunto di un mese di temperatura ERA5-Land: T media e T massima del mese per zona. None se non in cache."""
    zone = {}
    for s in STATISTICHE_CALORE:
        cg = archivio_calore.comune_giorno(s, mese)
        if cg is None:
            continue
        dg = media_per_distretto(cg, pesi=pesi, colonna_tempo="giorno", chiavi=[])
        sg = media_per_distretto(cg, pesi=_pesi_salento(pesi), colonna_tempo="giorno", chiavi=[])
        for df in (dg, sg):
            for r in per_mese(df, chiavi=(), colonna_zona="distretto").itertuples():
                zone.setdefault(r.distretto, {})[s] = {"valore": _num(r.valore), "stato": r.stato, "nota": _testo(r.nota),
                                                       "giorni": int(r.giorni), "giorni_con_valore": int(r.giorni_con_valore)}
    if not zone:
        return None
    sal = zone.get(ZONA_SALENTO, {}).get("massima") or {}
    return {"versione": VERSIONE, "dominio": "calore", "mese": mese, "firma": [list(x) for x in firma],
            "generato_il": datetime.now().isoformat(timespec="seconds"),
            "completo": sal.get("giorni_con_valore") == giorni_del_mese(mese), "zone": zone}


# ======================================================================================== lettura (server)

class ArchivioStagionalita:
    """I riassunti su disco, tenuti in memoria finché il file non cambia (mtime)."""

    def __init__(self, cartella=DIR_STAGIONALITA):
        self.cartella = Path(cartella)
        self._cache = {}

    def _carica(self, dominio):
        out = {}
        if not self.cartella.exists():
            return out
        for f in sorted(self.cartella.glob(f"{dominio}_*.json")):
            mtime = f.stat().st_mtime
            trovato = self._cache.get(f.name)
            if trovato is None or trovato[0] != mtime:
                dati = leggi(f)
                if not dati or dati.get("versione") != VERSIONE:
                    continue
                trovato = (mtime, dati)
                self._cache[f.name] = trovato
            out[trovato[1]["mese"]] = trovato[1]
        return out

    def aria(self):
        return self._carica("aria")

    def calore(self):
        return self._carica("calore")


# ======================================================================================== calcolo

def _rango(valori, alto_peggiore=True):
    """{mese 1-12: valore} → {mese: rango} con **1 = peggiore**; pari merito rango medio. `alto_peggiore`: il valore
    più alto è il peggiore (concentrazioni, temperature, eventi); False per una media di ranghi (più bassa = peggiore)."""
    s = pd.Series({m: v for m, v in valori.items() if v is not None}, dtype=float)
    return {} if s.empty else {int(m): float(r) for m, r in s.rank(method="average", ascending=not alto_peggiore).items()}


def _mese_peggiore(ranghi):
    return min(ranghi, key=lambda m: (ranghi[m], m)) if ranghi else None


def _cella_vuota(stato, nota, completo=False):
    return {"valore": None, "stato": stato, "nota": nota, "completo": completo, "extra": {}, "limite_superato": None,
            "limiti": []}


def _clima(per_anno, anni, completi_solo=True):
    """Media per mese dell'anno sugli `anni`, solo celle VALORE (e complete). → {m: (media, [anni usati])}"""
    out = {}
    for m in range(1, 13):
        usati = [(a, c["valore"]) for a in anni if (c := per_anno.get(a, [None] * 12)[m - 1]) is not None
                 and c["stato"] == STATO_VALORE and c["valore"] is not None and (c["completo"] or not completi_solo)]
        out[m] = (sum(v for _, v in usati) / len(usati), [a for a, _ in usati]) if usati else (None, [])
    return out


def _andamento(per_anno, assoluta, mese_corrente, motivo_vuoti):
    """Ultimo mese completo con VALORE vs media dello stesso mese negli anni precedenti."""
    candidati = sorted(((a, m) for a, celle in per_anno.items() for m in range(1, 13)
                        if (c := celle[m - 1]) and c["stato"] == STATO_VALORE and c["completo"]), reverse=True)
    if not candidati:
        return {"classe": "nessun_dato", "mese_riferimento": None, "valore": None, "media_anni_precedenti": None,
                "anni_precedenti": [], "delta": None, "delta_percentuale": None, "indicativo": False,
                "soglia": _testo_soglia(assoluta), "mesi_senza_dati": [], "motivo_senza_dati": motivo_vuoti,
                "nota": "nessun mese completo con un valore"}
    anno, m = candidati[0]
    rif = per_anno[anno][m - 1]["valore"]
    prec = [(a, per_anno[a][m - 1]["valore"]) for a in sorted(per_anno) if a < anno
            and (c := per_anno[a][m - 1]) and c["stato"] == STATO_VALORE and c["completo"]]
    rif_mese = f"{anno:04d}-{m:02d}"
    vuoti = []
    y, mm = anno, m
    while True:
        mm += 1
        if mm > 12:
            y, mm = y + 1, 1
        if f"{y:04d}-{mm:02d}" > mese_corrente:
            break
        vuoti.append(f"{y:04d}-{mm:02d}")
    base = {"mese_riferimento": rif_mese, "valore": rif, "anni_precedenti": [a for a, _ in prec],
            "soglia": _testo_soglia(assoluta), "mesi_senza_dati": vuoti,
            "motivo_senza_dati": motivo_vuoti if vuoti else None}
    if not prec:
        return {**base, "classe": "storico_insufficiente", "media_anni_precedenti": None, "delta": None,
                "delta_percentuale": None, "indicativo": False,
                "nota": f"nessun {nome_mese(m)} completo negli anni precedenti al {anno}"}
    media = sum(v for _, v in prec) / len(prec)
    delta = rif - media
    pct = delta / media if media else None
    if assoluta:
        classe = "in_aumento" if delta > SOGLIA_GRADI else "in_calo" if delta < -SOGLIA_GRADI else "stabile"
    elif pct is None:
        classe = "stabile" if delta == 0 else ("in_aumento" if delta > 0 else "in_calo")
    else:
        classe = "in_aumento" if pct > SOGLIA_RELATIVA else "in_calo" if pct < -SOGLIA_RELATIVA else "stabile"
    anni_txt = ", ".join(str(a) for a, _ in prec)
    return {**base, "classe": classe, "media_anni_precedenti": media, "delta": delta, "delta_percentuale": pct,
            "indicativo": len(prec) < 2,
            "nota": f"{etichetta_mese(rif_mese)} rispetto alla media di {nome_mese(m)} {anni_txt}"
                    + (" (un solo anno di storico: indicativo)" if len(prec) < 2 else "")}


def _testo_soglia(assoluta):
    return f"±{SOGLIA_GRADI:g} °C" if assoluta else f"±{SOGLIA_RELATIVA:.0%}"


def _riga(id, dominio, etichetta, unita, per_anno, anni_rank, mese_corrente, *, assoluta=False, modellata=False,
          nota=None, motivo_vuoti=None, formato="decimale", andamento=True):
    clima = _clima(per_anno, anni_rank)
    ranghi = _rango({m: v for m, (v, _) in clima.items()})
    peggiore = _mese_peggiore(ranghi)
    mesi = []
    for m in range(1, 13):
        v, anni = clima[m]
        sup = [(a, c) for a in anni_rank if (c := per_anno.get(a, [None] * 12)[m - 1]) and c.get("limite_superato")]
        mesi.append({"mese": m, "valore": v, "anni": anni, "rango": ranghi.get(m),
                     "limite_superato": bool(sup) if any(per_anno.get(a, [None] * 12)[m - 1] and
                                                         per_anno[a][m - 1].get("limite_superato") is not None
                                                         for a in anni_rank) else None,
                     "limiti_nota": "; ".join(f"{a}: {t}" for a, c in sup for t in c.get("limiti_superati", [])) or None})
    return {"id": id, "dominio": dominio, "etichetta": etichetta, "unita": unita, "formato": formato,
            "modellata": modellata, "nota": nota, "disponibile": any(x["valore"] is not None for x in mesi),
            "motivo": None,
            "anni": {str(a): per_anno[a] for a in sorted(per_anno)}, "clima": mesi, "mese_peggiore": peggiore,
            "andamento": _andamento({a: per_anno[a] for a in anni_rank if a in per_anno}, assoluta, mese_corrente,
                                    motivo_vuoti) if andamento else None}


def _testo_limite(e, fonte):
    stat = {"media_annua": "media annua", "media_24h": "media 24 h", "massimo_orario": "limite orario",
            "massimo_8h": "max media 8 h"}.get(e["statistica"], e["statistica"])
    esito = "superato" if e["superato"] else "entro"
    extra = " (indicativo: media del mese vs limite annuo)" if e.get("indicativo") else ""
    return f"{fonte}, {stat} {e['limite']:g} {e['unita']}: {esito} — {e['nota']}{extra}"


def _serie_aria(riassunti, zona, fonte, inquinante, anni):
    per_anno = {a: [None] * 12 for a in anni}
    for mese, r in riassunti.items():
        a, m = int(mese[:4]), int(mese[5:])
        if a not in per_anno:
            continue
        c = r["zone"].get(zona, {}).get(fonte, {}).get(inquinante)
        if c is None:
            cella = _cella_vuota(STATO_NO_DATA, f"fonte {fonte} o inquinante {inquinante} assente nel mese", r["completo"])
        else:
            cella = {**c, "completo": r["completo"], "extra": {}, "limite_superato": None, "limiti": []}
            if not r["completo"]:
                cella["nota"] = (f"mese incompleto ({r['giorni_coperti']} giorni su {r['giorni_del_mese']}, fino al "
                                 f"{r['ultimo_giorno']}): fuori dai ranghi; " + (c["nota"] or ""))
        fonti_lim = ([f for f in r["limiti"].get(zona, {}) if f != FONTE_ACCORPATA] if fonte == FONTE_ACCORPATA else [fonte])
        esiti = [(f, e) for f in fonti_lim for e in r["limiti"].get(zona, {}).get(f, {}).get(inquinante, [])]
        if esiti:
            cella["limite_superato"] = any(e["superato"] for _, e in esiti)
            cella["limiti"] = [_testo_limite(e, f) for f, e in esiti]
            cella["limiti_superati"] = [_testo_limite(e, f) for f, e in esiti if e["superato"]]
        else:
            cella["limiti"] = ["nessun limite del D.Lgs. 155/2010 confrontabile con la statistica del dato"]
        per_anno[a][m - 1] = cella
    for a in anni:
        for m in range(12):
            if per_anno[a][m] is None:
                per_anno[a][m] = _cella_vuota(STATO_NO_DATA, f"nessun dataset aria per {etichetta_mese(f'{a:04d}-{m + 1:02d}')}")
    return per_anno


def _serie_calore(riassunti, zona, anni):
    per_anno = {a: [None] * 12 for a in anni}
    for mese, r in riassunti.items():
        a, m = int(mese[:4]), int(mese[5:])
        if a not in per_anno:
            continue
        z = r["zone"].get(zona, {})
        c = z.get("massima")
        if c is None:
            continue
        cella = {**c, "completo": r["completo"], "extra": {"t_media": (z.get("media") or {}).get("valore")},
                 "limite_superato": None, "limiti": []}
        if not r["completo"]:
            cella["nota"] = f"mese incompleto ({c['giorni_con_valore']} giorni su {giorni_del_mese(mese)}): fuori dai ranghi"
        per_anno[a][m - 1] = cella
    for a in anni:
        for m in range(12):
            if per_anno[a][m] is None:
                per_anno[a][m] = _cella_vuota(STATO_NO_DATA, "temperatura ERA5-Land non ancora scaricata o preparata "
                                              "per il mese")
    return per_anno


def _serie_decessi(distretto_mese, fino_al, zona, distretti):
    """{anno: [12 celle]} dei decessi/giorno. Salento = somma dei distretti."""
    if distretto_mese is None:
        return {}
    dm = distretto_mese if zona == ZONA_SALENTO else distretto_mese[distretto_mese["distretto"] == zona]
    per_anno = {}
    for mese, g in dm.groupby("mese"):
        a, m = int(mese[:4]), int(mese[5:])
        validi = g[g["stato"] == STATO_VALORE]
        n_attesi = len(distretti) if zona == ZONA_SALENTO else 1
        gm = giorni_del_mese(mese)
        ultimo = f"{mese}-{gm:02d}"
        completo = bool(fino_al) and fino_al >= ultimo
        if validi.empty or not (fino_al and fino_al >= f"{mese}-01"):
            nota = (f"ISTAT non ha ancora pubblicato i decessi di {etichetta_mese(mese)} (dati fino al {fino_al})"
                    if fino_al and fino_al < f"{mese}-01" else "nessun distretto con un valore")
            cella = _cella_vuota(STATO_NULL if (g["stato"] == STATO_NULL).any() else STATO_NO_DATA, nota)
        else:
            totale = float(validi["valore"].sum())
            nota = (f"~{totale / gm:.1f}/giorno: {totale:.0f} decessi in {gm} giorni"
                    + (f", somma di {len(validi)} distretti su {n_attesi}" if zona == ZONA_SALENTO else ""))
            if not completo:
                nota += f"; mese incompleto (dati ISTAT fino al {fino_al}): fuori dai ranghi"
            if len(validi) < n_attesi:
                completo = False
                nota += "; somma parziale: fuori dai ranghi"
            cella = {"valore": totale / gm, "stato": STATO_VALORE, "nota": nota, "completo": completo,
                     "extra": {"totale": totale, "giorni": gm}, "limite_superato": None, "limiti": []}
        per_anno.setdefault(a, [None] * 12)[m - 1] = cella
    for a in per_anno:
        for m in range(12):
            if per_anno[a][m] is None:
                per_anno[a][m] = _cella_vuota(STATO_NO_DATA, "mese fuori dal periodo del file ISTAT")
    return per_anno


def _serie_simulata(ps, indicatore, anni):
    """{anno: [12 celle]} di un indicatore simulato per 100.000 residenti al giorno. `ps`: {"mensile": {indicatore:
    {mese: (totale, giorni con dato)}}, "residenti", "scenario", "periodo": (da, a)}."""
    per_anno = {a: [None] * 12 for a in anni}
    res, scenario = ps["residenti"], ps["scenario"]
    da_s, a_s = ps["periodo"]
    for mese, (totale, giorni) in ps["mensile"].get(indicatore, {}).items():
        a, m = int(mese[:4]), int(mese[5:])
        if a not in per_anno or not giorni or not res:
            continue
        completo = giorni == giorni_del_mese(mese)
        valore = totale / res * 100_000 / giorni
        nota = (f"{valore:.1f} per 100.000 residenti al giorno: ~{totale / giorni:.0f} al giorno, {totale:.0f} in "
                f"{giorni} giorni; dato simulato, non reale (scenario {scenario})")
        if not completo:
            nota += f"; mese incompleto ({giorni} giorni su {giorni_del_mese(mese)}): fuori dai ranghi"
        per_anno[a][m - 1] = {"valore": valore, "stato": STATO_VALORE, "nota": nota, "completo": completo,
                              "extra": {"totale": totale, "giorni": giorni, "al_giorno": totale / giorni},
                              "limite_superato": None, "limiti": []}
    for a in anni:
        for m in range(12):
            if per_anno[a][m] is None:
                per_anno[a][m] = _cella_vuota(STATO_NO_DATA, f"fuori dal periodo simulato ({da_s} → {a_s})")
    return per_anno


# indicatori simulati della tab oltre al PS (27/10/2026): (id, etichetta, nota). I primi due sono righe della griglia
# e temi del riepilogo delle criticità; gli altri solo dettaglio dei periodi critici, senza pesare sul conteggio.
SIMULATI_GRIGLIA = (
    ("adi_accessi_ps", "Accessi in PS degli assistiti ADI", "accessi in pronto soccorso degli assistiti in assistenza domiciliare"),
    ("ricoveri_respiratori", "Ricoveri respiratori", "ricoveri per malattie respiratorie"),
)
SIMULATI_DETTAGLIO = (
    ("ps_respiratori", "PS respiratori"),
    ("ps_cardiovascolari", "PS cardiovascolari"),
    ("ricoveri_circolatori", "Ricoveri circolatori"),
    ("adi_accessi_bassa_urgenza", "ADI a bassa urgenza"),
    ("adi_ritorni_30g", "ADI ritorni entro 30 giorni"),
)
INDICATORI_SIMULATI = ("ps_accessi",) + tuple(i for i, *_ in SIMULATI_GRIGLIA + SIMULATI_DETTAGLIO)


def calcola(zona, fonte, aria, calore, decessi, distretti, inquinanti, unita_inquinanti, oggi=None, ps=None,
            simulati_nella_sintesi=True):
    """La risposta di /api/stagionalita come dict. `aria`/`calore`: {mese: riassunto}; `decessi`: (distretto_mese,
    copertura_fino_al) di ArchivioDecessi; `inquinanti`: i 5 di riferimento; `ps`: accessi al PS simulati della zona
    (v. `_serie_simulata`), None se i dati simulati non ci sono."""
    oggi = oggi or date.today()
    mese_corrente = oggi.strftime("%Y-%m")
    mesi_aria = sorted(aria)
    primo_storico = int(mesi_aria[0][:4]) if mesi_aria else oggi.year
    # storico = tutti gli anni preparati (dettaglio anno per anno, grafico anno su anno); anni = quelli del confronto
    anni_storico = list(range(primo_storico, oggi.year + 1))
    anni = [a for a in anni_storico if a >= PRIMO_ANNO_CONFRONTO] or [oggi.year]
    ultimo_aria = max((r["ultimo_giorno"] for r in aria.values() if r.get("ultimo_giorno")), default=None)
    righe = []

    # --- aria: un inquinante per riga
    modellata_fonte = fonte == "CAMS"
    motivo_aria = (f"archivio aria fino al {ultimo_aria}: il mese in corso è incompleto e resta fuori dal confronto"
                   if ultimo_aria else "nessun riassunto aria preparato")
    for inq in inquinanti:
        per_anno = _serie_aria(aria, zona, fonte, inq, anni_storico)
        righe.append(_riga(f"aria:{inq}", "aria", inq, unita_inquinanti.get(inq), per_anno, anni, mese_corrente,
                           modellata=modellata_fonte, motivo_vuoti=motivo_aria,
                           nota=f"media del mese, fonte {fonte}" + (" (dove non ci sono stazioni: CAMS, modellato)"
                                                                    if fonte == FONTE_ACCORPATA else "")))

    # --- aria complessiva: rango medio dei 5 inquinanti (1 = peggiore), poi riordinato: la media più bassa è il rango 1
    rig_inq = [r for r in righe if r["dominio"] == "aria"]
    medie_rango = {}
    for m in range(1, 13):
        rr = [r["clima"][m - 1]["rango"] for r in rig_inq if r["clima"][m - 1]["rango"] is not None]
        medie_rango[m] = sum(rr) / len(rr) if rr else None
    ranghi = _rango(medie_rango, alto_peggiore=False)
    clima = []
    for m in range(1, 13):
        sup = [(r["etichetta"], r["clima"][m - 1]["limiti_nota"]) for r in rig_inq if r["clima"][m - 1]["limite_superato"]]
        clima.append({"mese": m, "valore": medie_rango[m],
                      "anni": sorted({a for r in rig_inq for a in r["clima"][m - 1]["anni"]}), "rango": ranghi.get(m),
                      "limite_superato": bool(sup) if any(r["clima"][m - 1]["limite_superato"] is not None
                                                          for r in rig_inq) else None,
                      "limiti_nota": " | ".join(f"{i}: {n}" for i, n in sup) or None})
    righe.append({"id": "aria", "dominio": "aria", "etichetta": "Aria complessiva", "unita": "rango medio",
                  "formato": "rango", "modellata": modellata_fonte,
                  "nota": "media dei ranghi dei 5 inquinanti di riferimento (1 = peggiore), riordinata da 1 a 12",
                  "disponibile": bool(ranghi), "motivo": None, "anni": {}, "clima": clima,
                  "mese_peggiore": _mese_peggiore(ranghi), "andamento": None})

    # --- calore: T massima giornaliera, media del mese
    righe.append(_riga("calore", "calore", "Temperatura massima", "°C", _serie_calore(calore, zona, anni_storico), anni,
                       mese_corrente, assoluta=True, modellata=True,
                       nota="media mensile della temperatura massima giornaliera a 2 m (ERA5-Land, rianalisi: modellata); "
                            "T media nel dettaglio",
                       motivo_vuoti="ERA5-Land arriva con circa una settimana di ritardo: il mese in corso è incompleto"))

    # --- decessi: media giornaliera del mese (lo storico ISTAT dal 2011 resta per il grafico anno su anno)
    dm, fino = decessi
    per_anno_d = _serie_decessi(dm, fino, zona, distretti)
    if per_anno_d:
        righe.append(_riga("decessi", "salute", "Decessi", "decessi/giorno", per_anno_d, anni, mese_corrente,
                           nota="decessi di tutte le cause ÷ giorni del mese (ISTAT, dati provvisori); grana minima distretto × mese",
                           motivo_vuoti=f"ISTAT pubblica i decessi giornalieri con alcuni mesi di ritardo: dati fino al {fino}"))
    else:
        righe.append(_riga_nd("decessi", "salute", "Decessi", "decessi/giorno", "decessi ISTAT non ancora scaricati"))

    # --- pronto soccorso, ADI e ricoveri: dati simulati (nessuna fonte pubblica mensile), solo negli anni del confronto
    unita_sim = "per 100.000 residenti al giorno"
    for ind, etichetta, descr in (("pronto_soccorso", "Accessi al pronto soccorso", "accessi in PS di tutte le cause"),
                                  *SIMULATI_GRIGLIA):
        if ps:
            serie = _serie_simulata(ps, "ps_accessi" if ind == "pronto_soccorso" else ind, anni)
            r = _riga(ind, "salute", etichetta, unita_sim, serie, anni, mese_corrente,
                      nota=f"dato simulato, non reale (scenario {ps['scenario']}): {descr} per 100.000 residenti al "
                           "giorno, media del mese",
                      motivo_vuoti=f"il periodo simulato finisce il {ps['periodo'][1]}")
        else:
            r = _riga_nd(ind, "salute", etichetta, unita_sim,
                         "dati simulati non generati: nessuna fonte pubblica degli accessi al pronto soccorso per mese")
        r["simulata"] = True
        righe.append(r)
    dettaglio_sim = [{**_riga(ind, "salute", etichetta, unita_sim, _serie_simulata(ps, ind, anni), anni, mese_corrente,
                              andamento=False), "simulata": True}
                     for ind, etichetta in SIMULATI_DETTAGLIO] if ps else []

    k = criticita(righe, dettaglio_sim, simulati_nella_sintesi)
    return {"zona": zona, "fonte": fonte, "anni_confronto": anni, "anni_storico": anni_storico, "oggi": oggi.isoformat(),
            "peggiori": _peggiori(k), "sintesi": k["sintesi"], "righe": righe, "criticita": k,
            "mesi_aria": mesi_aria, "mesi_calore": sorted(calore)}


def _riga_nd(id, dominio, etichetta, unita, motivo):
    return {"id": id, "dominio": dominio, "etichetta": etichetta, "unita": unita, "formato": "decimale",
            "modellata": False, "nota": motivo, "disponibile": False, "motivo": motivo,
            "anni": {}, "clima": [{"mese": m, "valore": None, "anni": [], "rango": None, "limite_superato": None,
                                   "limiti_nota": None} for m in range(1, 13)],
            "mese_peggiore": None, "andamento": None}


def _peggiori(k):
    """I mesi peggiori dell'anno, dal primo: i picchi dei periodi critici, poi i mesi critici per più temi (al più 3)."""
    ordine = [p["mese_picco"] for p in k["periodi"]]
    ordine += [x["mese"] for x in sorted(k["mesi"], key=lambda x: (-x["conteggio"], x["mese"])) if x["conteggio"]]
    return list(dict.fromkeys(ordine))[:3]


# ======================================================================================== criticità dell'anno

# Riepilogo delle criticità (27/10/2026, scelte di Matteo): un mese è **critico** per un indicatore se è fra i suoi
# 3 mesi peggiori (rango ≤ 3, a pari merito entrano tutti); si conta per quanti temi lo è, un indicatore per tema
# così nessun tema pesa due volte; i mesi vicini con almeno due temi critici formano un **periodo** (dicembre e
# gennaio sono vicini). Gli altri indicatori (inquinanti, PS per causa, ADI a bassa urgenza e ritorni, ricoveri
# circolatori) sono il dettaglio dei periodi e non pesano sul conteggio. Esplorativo, non causale.
TEMI_CRITICITA = (
    ("aria", "aria", "Aria"),
    ("calore", "caldo", "Temperatura"),
    ("decessi", "decessi", "Decessi"),
    ("pronto_soccorso", "ps", "Pronto soccorso"),
    ("adi_accessi_ps", "adi", "Assistiti ADI"),
    ("ricoveri_respiratori", "ricoveri", "Ricoveri respiratori"),
)
MESI_CRITICI = 3
MIN_MESI_RANGO = 6  # sotto i 6 mesi con un rango «i 3 peggiori» non distinguono nulla
# tema → (titolo, breve, esteso): il breve nel consiglio (29/10/2026, Matteo: testo più schematico), l'esteso nel tooltip
SPUNTI = {
    "adi": ("ADI", "telefonate e visite a domicilio",
            "assistiti in ADI: telefonate mirate e visite domiciliari prima e durante il periodo (medici di famiglia, volontariato)"),
    "caldo": ("Caldo", "avvisi ai fragili con la protezione civile",
              "ondate di calore: avvisi e contatti con le persone fragili, insieme alla protezione civile"),
    "ps": ("Pronto soccorso", "turni per il picco di accessi", "pronto soccorso: turni e percorsi per il picco di accessi"),
    "ricoveri": ("Reparti", "posti letto per i ricoveri respiratori", "reparti: posti letto per il picco di ricoveri respiratori"),
    "aria": ("Aria", "avvisi a chi ha malattie respiratorie o cardiache",
             "aria: avvisi alle persone con malattie respiratorie e cardiache nei giorni di picco degli inquinanti"),
}


def _mesi_critici(riga):
    """Mesi (1-12) fra i 3 peggiori della riga; [] se troppo pochi mesi hanno un rango."""
    ranghi = {x["mese"]: x["rango"] for x in riga["clima"] if x["rango"] is not None}
    if len(ranghi) < MIN_MESI_RANGO:
        return []
    # rango 1 = peggiore; un pari merito a cavallo del terzo posto (es. 3,5) entra tutto
    return sorted(m for m, r in ranghi.items() if r < MESI_CRITICI + 1)


def _scarto(riga, mese):
    """Valore del mese rispetto alla media dei 12 mesi: (scarto, assoluto?). °C per la temperatura, frazione per gli
    altri; None per l'aria complessiva (è un rango)."""
    if riga["formato"] == "rango":
        return None, False
    valori = [x["valore"] for x in riga["clima"] if x["valore"] is not None]
    v = riga["clima"][mese - 1]["valore"]
    if v is None or not valori:
        return None, False
    media = sum(valori) / len(valori)
    if riga["id"] == "calore":
        return v - media, True
    return ((v - media) / media if media else None), False


def _motivo(riga, mesi):
    """La riga nel periodo: il mese peggiore fra `mesi`, valore, rango, posizione (1° = peggiore dell'anno), scarto."""
    m = min(mesi, key=lambda x: (riga["clima"][x - 1]["rango"] or math.inf, x))
    c = riga["clima"][m - 1]
    scarto, assoluto = _scarto(riga, m)
    return {"id": riga["id"], "etichetta": riga["etichetta"], "unita": riga["unita"], "formato": riga["formato"],
            "mese": m, "mesi": mesi, "valore": c["valore"], "rango": c["rango"],
            "posizione": math.floor(c["rango"]) if c["rango"] is not None else None,
            "scarto": scarto, "scarto_assoluto": assoluto,
            "simulata": bool(riga.get("simulata")), "modellata": bool(riga.get("modellata"))}


def _etichetta_periodo(mesi):
    return nome_mese(mesi[0]) if len(mesi) == 1 else f"{nome_mese(mesi[0])} – {nome_mese(mesi[-1])}"


def _gruppi_circolari(selezionati):
    """Mesi selezionati (insieme di 1-12) in gruppi di mesi consecutivi, dicembre vicino a gennaio."""
    if not selezionati:
        return []
    if len(selezionati) == 12:
        return [list(range(1, 13))]
    inizio = next(m for m in range(1, 13) if m in selezionati and ((m - 2) % 12 + 1) not in selezionati)
    gruppi, corrente = [], []
    for k in range(12):
        m = (inizio - 1 + k) % 12 + 1
        if m in selezionati:
            corrente.append(m)
        elif corrente:
            gruppi.append(corrente)
            corrente = []
    if corrente:
        gruppi.append(corrente)
    return gruppi


def _motivo_tema(r, critici, simulati_nella_sintesi):
    if not r["disponibile"]:
        return r["motivo"]
    if r.get("simulata") and not simulati_nella_sintesi:
        return "dato simulato escluso dalla sintesi"
    return None if critici else "troppo pochi mesi con un valore"


def criticita(righe, dettaglio_sim, simulati_nella_sintesi=True):
    """Riepilogo delle criticità dell'anno: calendario temi × mesi, periodi critici con il perché, mesi da tenere
    d'occhio. `righe` = righe della griglia, `dettaglio_sim` = righe simulate solo di dettaglio."""
    per_id = {r["id"]: r for r in righe}
    temi = []
    for rid, tema, nome in TEMI_CRITICITA:
        r = per_id.get(rid)
        if r is None:
            continue
        simulata = bool(r.get("simulata"))
        critici = _mesi_critici(r) if r["disponibile"] else []
        peggiore = r["mese_peggiore"]
        temi.append({"id": rid, "tema": tema, "nome": nome, "etichetta": r["etichetta"], "unita": r["unita"],
                     "formato": r["formato"], "simulata": simulata, "modellata": bool(r.get("modellata")),
                     "disponibile": r["disponibile"],
                     "entra": bool(critici) and (simulati_nella_sintesi or not simulata),
                     "motivo": _motivo_tema(r, critici, simulati_nella_sintesi),
                     "mesi_critici": critici, "ranghi": [x["rango"] for x in r["clima"]],
                     "mese_peggiore": peggiore,
                     "valore_peggiore": r["clima"][peggiore - 1]["valore"] if peggiore else None})
    contano = [t for t in temi if t["entra"]]
    n = len(contano)

    mesi = []
    for m in range(1, 13):
        su = [t["id"] for t in contano if m in t["mesi_critici"]]
        c = len(su)
        livello = None if c == 0 else "alta" if c >= max(2, math.ceil(n / 2)) else "media" if c >= 2 else "bassa"
        mesi.append({"mese": m, "conteggio": c, "temi": su, "livello": livello})

    soglia = 2 if any(x["conteggio"] >= 2 for x in mesi) else 1
    gruppi = _gruppi_circolari({x["mese"] for x in mesi if x["conteggio"] >= soglia})
    secondarie = [r for r in righe if r["dominio"] == "aria" and r["id"] != "aria"] + list(dettaglio_sim)
    periodi = []
    for g in gruppi:
        cont = [mesi[m - 1]["conteggio"] for m in g]
        picco = g[cont.index(max(cont))]
        motivi = [_motivo(per_id[t["id"]], [m for m in g if m in t["mesi_critici"]])
                  for t in contano if any(m in t["mesi_critici"] for m in g)]
        anche = []
        for r in secondarie:
            if not r["disponibile"] or (r.get("simulata") and not simulati_nella_sintesi):
                continue
            dentro = [m for m in g if m in _mesi_critici(r)]
            if dentro:
                anche.append(_motivo(r, dentro))
        limiti = sorted({r["etichetta"] for r in righe if r["dominio"] == "aria" and r["id"] != "aria"
                         for m in g if r["clima"][m - 1]["limite_superato"]})
        temi_p = {t["tema"] for t in contano if any(m in t["mesi_critici"] for m in g)}
        periodi.append({"mesi": g, "etichetta": _etichetta_periodo(g), "massimo": max(cont), "somma": sum(cont),
                        "mese_picco": picco, "livello": mesi[picco - 1]["livello"],
                        "motivi": motivi, "anche": anche, "limiti_superati": limiti,
                        "spunti": [{"tema": t, "titolo": SPUNTI[t][0], "breve": SPUNTI[t][1], "esteso": SPUNTI[t][2]}
                                   for t in ("adi", "caldo", "ps", "ricoveri", "aria") if t in temi_p],
                        "simulati": sorted({x["etichetta"] for x in motivi + anche if x["simulata"]})})
    periodi.sort(key=lambda p: (-p["massimo"], -p["somma"], p["mesi"][0]))
    nei_periodi = {m for p in periodi for m in p["mesi"]}
    attenzione = [{"mese": x["mese"], "temi": x["temi"]} for x in mesi if x["conteggio"] and x["mese"] not in nei_periodi]
    return {"temi": temi, "mesi": mesi, "periodi": periodi, "attenzione": attenzione, "temi_contati": n,
            "mesi_critici_per_tema": MESI_CRITICI, "simulati_nella_sintesi": simulati_nella_sintesi,
            "sintesi": _sintesi_criticita(periodi, attenzione, temi, n)}


def _elenco(voci):
    voci = list(voci)
    if len(voci) < 2:
        return "".join(voci)
    return f"{', '.join(voci[:-1])} e {voci[-1]}"


def _minuscola(testo):
    return testo[:1].lower() + testo[1:]


def _sintesi_criticita(periodi, attenzione, temi, n):
    if not periodi:
        return "Nessun mese ha abbastanza dati per individuare un periodo critico."
    nomi = {t["id"]: _minuscola(t["nome"]) for t in temi}
    parti = [f"{p['etichetta']} ({_elenco(nomi[x['id']] for x in p['motivi'])})" for p in periodi[:3]]
    testo = ("Il periodo che richiede più attenzione è " if len(parti) == 1
             else f"{len(parti)} periodi richiedono più attenzione: ") + _elenco(parti) + "."
    if attenzione:
        testo += " Da tenere d'occhio anche " + _elenco(
            f"{nome_mese(a['mese'])} ({_elenco(nomi[t] for t in a['temi'])})" for a in attenzione) + "."
    sim = [_minuscola(t["nome"]) for t in temi if t["simulata"] and t["entra"]]
    if sim:
        testo += f" {_elenco(sim)[:1].upper()}{_elenco(sim)[1:]}: dati simulati, non reali."
    return testo + " Lettura esplorativa, non causale."
