#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corregge **offline** i mesi dell'archivio aria generati prima di una fusione di comuni
nell'anagrafica del territorio (v. docs/Regole_dei_dati.md, 14/10/2026).

Un mese generato prima del 14/10/2026 ha ancora Presicce (075062) e Acquarica del Capo (075001)
come due comuni, che l'anagrafica non conosce più: il server non sa in quale distretto metterli.
Rigenerare il mese richiamerebbe tutte le fonti (minuti per mese), ma nei due comuni non c'è
nessuna stazione fisica: l'unico dato che cambia è la **stazione virtuale CAMS**, la media pesata
sull'area delle celle CAMS, che va ricalcolata sul confine del comune fuso. CAMS si legge dalla
cache locale (data/raw/aria/copernicus_cams/), quindi la correzione non chiama nessuna API.

Per ogni file dell'archivio con comuni fuori dall'anagrafica:
  - i comuni componenti spariscono e al loro posto c'è il comune fuso, nello stesso distretto;
  - le stazioni fisiche dei componenti (oggi nessuna) passano al comune fuso così come sono;
  - le stazioni CAMS dei componenti si sostituiscono con `CAMS-<comune fuso>`, ricalcolata dalla cache;
  - `nessuna_stazione` resta una sola, e solo se il comune fuso non ha nessun'altra stazione;
  - testata `stazioni`, `riepilogo`, impronta del territorio e copertura dell'archivio si aggiornano,
    e in `correzioni` resta scritto cosa è stato fatto e quando.
Un file con comuni sconosciuti che non sono in FUSIONI non si tocca: va rigenerato con
`genera_dataset_aria.py --rigenera` (il generatore lo rifà comunque da sé, motivo "anagrafica").

Uso (dalla radice del repo):
  uv run scripts/aria/correggi_comuni_fusi.py              # corregge tutto l'archivio
  uv run scripts/aria/correggi_comuni_fusi.py --prova      # dice cosa farebbe, senza scrivere

Sicuro anche con un `genera_dataset_aria.py` in corso: un file che cambia mentre lo si corregge
(o che si sta scrivendo) si salta, e un mese che il generatore riscrive dopo è già giusto.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # radice del repo, per il package api
from api.aria.anagrafica_aria import carica_comuni  # noqa: E402
from api.aria.archivio_aria import (  # noqa: E402
    DIR_ARCHIVIO,
    aggiorna_copertura_da_json,
    file_presenti,
    impronta_territorio,
)
from api.aria.dataset_aria import NESSUNA_STAZIONE, _ordina_stazione  # noqa: E402
from api.aria.fonti.cams import FonteCAMS  # noqa: E402

# codice ISTAT soppresso → codice del comune fuso (ISTAT, fusione del 2019; anagrafica unificata il 14/10/2026).
# Una fusione futura si aggiunge qui.
FUSIONI = {
    "075062": "075098",  # Presicce → Presicce-Acquarica
    "075001": "075098",  # Acquarica del Capo → Presicce-Acquarica
}
PREFISSO_CAMS = "CAMS-"
NOTA_SENZA_DATO = "nessun dato dalla fonte per questo giorno"


def _foglia(valore, stato, nota):
    return {"valore": None if valore is None else float(valore), "stato": stato,
            "nota": nota if isinstance(nota, str) else None}


def _stazione_cams(js, codice, componenti, cams):
    """Nodo giorno > fonte > inquinante della stazione CAMS del comune fuso.

    Si parte dal nodo CAMS di un componente (stessi giorni, fonti e inquinanti, stesse celle NO_DATA
    delle altre fonti) e si rimpiazzano le foglie CAMS con il valore ricalcolato sul confine fuso."""
    modello = next((stazioni[PREFISSO_CAMS + c] for c, stazioni in componenti if PREFISSO_CAMS + c in stazioni), None)
    if modello is None:
        return None
    misure = cams.misure[cams.misure["stazione"] == PREFISSO_CAMS + codice]
    nuove = {(m.giorno, m.inquinante): _foglia(m.valore, m.stato, m.nota) for m in misure.itertuples(index=False)}
    nodo = {}
    for giorno, fonti in modello.items():
        nodo[giorno] = {}
        for fonte, inquinanti in fonti.items():
            nodo[giorno][fonte] = {}
            for inquinante, foglia in inquinanti.items():
                if fonte == "CAMS" and (giorno, inquinante) in nuove:
                    foglia = nuove[(giorno, inquinante)]
                elif fonte == "CAMS" and foglia["stato"] == "VALORE":  # c'era un valore ma il ricalcolo non lo dà
                    foglia = _foglia(None, "NULL", NOTA_SENZA_DATO)
                nodo[giorno][fonte][inquinante] = dict(foglia)
    return nodo


def _testata_cams(cams, codice):
    righe = cams.stazioni[cams.stazioni["stazione"] == PREFISSO_CAMS + codice]
    if righe.empty:
        return None
    s = righe.iloc[0]
    return {"distretto": s.id_distretto, "comune": codice, "fonti": {"CAMS": [{
        "id_fonte": s.id_fonte, "denominazione": s.denominazione, "comune": s.comune,
        "lat": float(s.lat), "lon": float(s.lon), "attiva_da": None, "attiva_a": None,
        "abbinamento": s.abbinamento}]}}


def _riepilogo(js):
    celle, per_fonte = 0, {}
    for provincia in js["dati"].values():
        for comuni in provincia.values():
            for stazioni in comuni.values():
                for giorni in stazioni.values():
                    for fonti in giorni.values():
                        for fonte, inquinanti in fonti.items():
                            for foglia in inquinanti.values():
                                celle += 1
                                conta = per_fonte.setdefault(fonte, {})
                                conta[foglia["stato"]] = conta.get(foglia["stato"], 0) + 1
    return {**js["riepilogo"], "celle": celle,
            "per_fonte_e_stato": {f: dict(sorted(s.items())) for f, s in sorted(per_fonte.items())}}


def _con_testata_territorio(js, id_comuni):
    """Il dict con "territorio" subito dopo "periodo", dove archivio_aria lo cerca nei primi KB."""
    out = {}
    for k, v in js.items():
        if k == "territorio":
            continue
        out[k] = v
        if k == "periodo":
            out["territorio"] = {"comuni": len(id_comuni), "impronta": impronta_territorio(id_comuni)}
    return out


def correggi(js, anagrafica):
    """Corregge il dict di un mese. Restituisce (js corretto, descrizione) oppure (None, motivo per non farlo)."""
    distretto_di = {c["id_comune"]: c["id_distretto"] for c in anagrafica}
    presenti = {c: (p, d) for p, dd in js["dati"].items() for d, cc in dd.items() for c in cc}
    ignoti = sorted(set(presenti) - set(distretto_di))
    if not ignoti:
        return js, None
    non_fusi = [c for c in ignoti if c not in FUSIONI or FUSIONI[c] not in distretto_di]
    if non_fusi:
        return None, f"comuni sconosciuti non dovuti a una fusione nota ({', '.join(non_fusi)}): rigenerare il mese"

    da, a = (datetime.fromisoformat(js["periodo"][k]).date() for k in ("da", "a"))
    cams = FonteCAMS(solo_cache=True).raccogli(da, a) if "CAMS" in js["fonti"] else None
    fatti = []
    for codice in sorted({FUSIONI[c] for c in ignoti}):
        vecchi = [c for c in ignoti if FUSIONI[c] == codice]
        componenti = [(c, js["dati"][presenti[c][0]][presenti[c][1]].pop(c)) for c in vecchi]
        nodo = {}
        for _, stazioni in componenti:  # stazioni fisiche: passano al comune fuso così come sono
            nodo.update({s: v for s, v in stazioni.items() if s != NESSUNA_STAZIONE and not s.startswith(PREFISSO_CAMS)})
        if cams is not None:
            nodo_cams = _stazione_cams(js, codice, componenti, cams)
            if nodo_cams is not None:
                nodo[PREFISSO_CAMS + codice] = nodo_cams
        if not nodo:  # come il generatore: la stazione fittizia solo per un comune senza alcuna stazione
            vuota = next((st[NESSUNA_STAZIONE] for _, st in componenti if NESSUNA_STAZIONE in st), None)
            if vuota is not None:
                nodo[NESSUNA_STAZIONE] = vuota
        provincia, distretto = distretto_di[codice][:2], distretto_di[codice]
        comuni = js["dati"].setdefault(provincia, {}).setdefault(distretto, {})
        comuni[codice] = dict(sorted(nodo.items(), key=lambda kv: _ordina_stazione(kv[0])))
        js["dati"][provincia][distretto] = dict(sorted(comuni.items()))

        testata = js["stazioni"]
        for c in vecchi:
            testata.pop(PREFISSO_CAMS + c, None)
        for s, voce in testata.items():
            if voce.get("comune") in vecchi:
                voce["comune"], voce["distretto"] = codice, distretto
        if cams is not None and (voce := _testata_cams(cams, codice)) is not None:
            testata[PREFISSO_CAMS + codice] = voce
        js["stazioni"] = dict(sorted(testata.items(), key=lambda kv: _ordina_stazione(kv[0])))
        fatti.append(f"comuni {', '.join(vecchi)} fusi in {codice} (stazione CAMS ricalcolata sul confine fuso "
                     "dalla cache locale)")

    js["riepilogo"] = _riepilogo(js)
    descrizione = "; ".join(fatti)
    js.setdefault("correzioni", []).append({"il": datetime.now().isoformat(timespec="seconds"),
                                            "script": "scripts/aria/correggi_comuni_fusi.py",
                                            "descrizione": descrizione})
    id_comuni = [c for dd in js["dati"].values() for cc in dd.values() for c in cc]
    return _con_testata_territorio(js, id_comuni), descrizione


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Corregge offline i mesi dell'archivio aria precedenti a una fusione di comuni.")
    parser.add_argument("--prova", action="store_true", help="dice cosa farebbe, senza scrivere")
    args = parser.parse_args()

    anagrafica = carica_comuni()
    attesa = impronta_territorio(c["id_comune"] for c in anagrafica)
    corretti, saltati = 0, []
    for _, _, percorso in file_presenti(DIR_ARCHIVIO):
        mtime = percorso.stat().st_mtime
        try:
            js = json.loads(percorso.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            saltati.append(f"{percorso.name}: illeggibile, forse in scrittura ({type(exc).__name__})")
            continue
        nuovo, descrizione = correggi(js, anagrafica)
        if nuovo is None:
            saltati.append(f"{percorso.name}: {descrizione}")
            continue
        if descrizione is None:
            continue  # già allineato all'anagrafica
        id_comuni = [c for dd in nuovo["dati"].values() for cc in dd.values() for c in cc]
        if impronta_territorio(id_comuni) != attesa:
            saltati.append(f"{percorso.name}: dopo la correzione i comuni non coincidono con l'anagrafica")
            continue
        print(f"{percorso.name}: {descrizione}")
        if args.prova:
            continue
        if percorso.stat().st_mtime != mtime:
            saltati.append(f"{percorso.name}: riscritto nel frattempo da un'altra esecuzione, lasciato com'è")
            continue
        temporaneo = percorso.with_suffix(".json.tmp")
        with open(temporaneo, "w", encoding="utf-8") as f:
            json.dump(nuovo, f, ensure_ascii=False)
        os.replace(temporaneo, percorso)
        aggiorna_copertura_da_json(nuovo)
        corretti += 1

    print(f"\n{'Da correggere' if args.prova else 'Corretti'}: {corretti if not args.prova else '(v. sopra)'}; "
          f"saltati: {len(saltati)}")
    for s in saltati:
        print(f"  - {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
