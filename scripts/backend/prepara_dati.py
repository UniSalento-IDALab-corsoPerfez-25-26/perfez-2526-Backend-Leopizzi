#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Popola un clone del Backend: lancia nell'ordine giusto gli script che scaricano i dati dalle fonti pubbliche e
preparano le viste della dashboard. Il repository non contiene nessun dato: questa è la strada unica per riempirlo.

Uso (dalla radice del repo; --env-file serve per le chiavi, v. .env.example):
    uv run --env-file .env scripts/backend/prepara_dati.py                        # l'ultimo mese completo
    uv run --env-file .env scripts/backend/prepara_dati.py --da 2025-01-01 --a 2025-12-31
    uv run --env-file .env scripts/backend/prepara_dati.py --solo decessi dimissioni
    uv run scripts/backend/prepara_dati.py --dry-run                              # mostra cosa farebbe

Passi (numerati come nella sezione «Dati» del README):
    1  cams           aria CAMS (modellato, 0,1°) nella cache locale      chiave COPERNICUS_API_KEY + licenze ADS
    2  aria           ARPA Puglia, OpenAQ, EEA (e CAMS dalla cache)       chiave OPENAQ_API_KEY (senza, OpenAQ resta NULL)
    3  era5            temperatura ERA5-Land nella cache locale            chiave COPERNICUS_API_KEY + licenza CDS
    4  arpa-meteo      temperatura misurata da ARPA Puglia                 nessuna
    5  decessi         decessi comunali giornalieri ISTAT                  nessuna
    6  dimissioni      dimissioni ISTAT Health for All                     nessuna
    7  simulati        dati sanitari simulati (periodo: quello dello script, dal 2024-01-01)  serve il passo 1-3
    8  viste           consuntivi dell'aria e riassunti della Stagionalità  nessuna, sempre in locale

Un passo che richiede una chiave mancante si salta dicendo come ottenerla; un passo che fallisce non ferma gli altri.
Tutti gli script sono riprendibili: rilanciare con lo stesso periodo completa quello che manca.
Il passo facoltativo che rifà `mitigazione_comuni.json` (calcola_mitigazione_comuni.py, 1,1 GB di raster CLMS scaricati
a mano con un account EU Login) non fa parte di questo comando: il file è già nel repository.
"""

import argparse
import os
import subprocess
import sys
import time
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]

COME_AVERE = {
    "OPENAQ_API_KEY": "registrarsi gratis su https://explore.openaq.org/register e copiare la chiave in .env",
    "COPERNICUS_API_KEY": "creare l'account gratuito su https://cds.climate.copernicus.eu (e su https://ads.atmosphere.copernicus.eu), "
                          "copiare la chiave in .env e accettare a mano, sul sito, le licenze dei dataset",
}


@dataclass
class Passo:
    id: str
    titolo: str
    comando: list[str]
    chiavi: list[str] = field(default_factory=list)  # tutte obbligatorie per eseguire il passo
    chiavi_consigliate: list[str] = field(default_factory=list)  # il passo gira anche senza, con un risultato ridotto


def _ultimo_mese_completo(oggi=None):
    oggi = oggi or date.today()
    fine = oggi.replace(day=1) - timedelta(days=1)
    return fine.replace(day=1), fine


def _mesi(da, a):
    m = da.replace(day=1)
    out = []
    while m <= a:
        out.append(m.strftime("%Y-%m"))
        m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


def costruisci_passi(da, a):
    """I passi con i loro comandi, per il periodo scelto."""
    py = sys.executable
    s = lambda *p: str(RADICE.joinpath("scripts", *p))  # noqa: E731
    mesi = _mesi(da, a)
    return [
        Passo("cams", "Aria CAMS (cache locale)", [py, s("aria", "scarica_cams.py"), "--da", mesi[0], "--a", mesi[-1]],
              chiavi=["COPERNICUS_API_KEY"]),
        Passo("aria", "Aria: ARPA, OpenAQ, EEA", [py, s("aria", "genera_dataset_aria.py"), "--da", da.isoformat(), "--a", a.isoformat()],
              chiavi_consigliate=["OPENAQ_API_KEY"]),
        Passo("era5", "Temperatura ERA5-Land (cache locale)", [py, s("calore", "scarica_era5_land.py"), "--da", mesi[0], "--a", mesi[-1]],
              chiavi=["COPERNICUS_API_KEY"]),
        Passo("arpa-meteo", "Temperatura misurata ARPA", [py, s("calore", "scarica_arpa_meteo.py"), "--da", str(da.year), "--a", str(a.year)]),
        Passo("decessi", "Decessi comunali ISTAT", [py, s("salute", "scarica_decessi_istat.py")]),
        Passo("dimissioni", "Dimissioni ISTAT Health for All", [py, s("salute", "scarica_dimissioni_hfa.py")]),
        Passo("simulati", "Dati sanitari simulati", [py, s("salute", "simula_dati_salute.py")]),
        Passo("viste", "Viste della dashboard (consuntivi)", [py, s("dashboard", "prepara_consuntivi.py")]),
        Passo("viste-stagionalita", "Viste della dashboard (Stagionalità)", [py, s("dashboard", "prepara_stagionalita.py")]),
    ]


def _periodo(testo):
    try:
        return date.fromisoformat(testo)
    except ValueError:
        raise argparse.ArgumentTypeError(f"data non valida: {testo!r} (atteso AAAA-MM-GG)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--da", type=_periodo, help="primo giorno AAAA-MM-GG (default: il primo giorno dell'ultimo mese completo)")
    ap.add_argument("--a", type=_periodo, help="ultimo giorno AAAA-MM-GG (default: l'ultimo giorno dell'ultimo mese completo)")
    ap.add_argument("--solo", nargs="+", metavar="PASSO", help="esegue solo questi passi (id nell'elenco sopra; «viste» include la Stagionalità)")
    ap.add_argument("--salta", nargs="+", default=[], metavar="PASSO", help="salta questi passi")
    ap.add_argument("--dry-run", action="store_true", help="mostra i passi e i comandi senza eseguirli")
    args = ap.parse_args()

    da_def, a_def = _ultimo_mese_completo()
    da, a = args.da or da_def, args.a or a_def
    if a < da:
        ap.error("--a precede --da")
    passi = costruisci_passi(da, a)

    ids = {p.id for p in passi} | {"viste"}
    for nome in (args.solo or []) + args.salta:
        if nome not in ids:
            ap.error(f"passo sconosciuto: {nome} (validi: {', '.join(sorted(ids))})")

    def scelto(p):
        chiave = "viste" if p.id.startswith("viste") else p.id
        return (not args.solo or chiave in args.solo) and chiave not in args.salta

    print(f"OneHealth: preparazione dei dati dal {da.isoformat()} al {a.isoformat()}"
          + (" (prova, non eseguo nulla)" if args.dry_run else ""))
    esiti = []
    for p in passi:
        if not scelto(p):
            continue
        print(f"\n== {p.titolo} [{p.id}]")
        mancanti = [k for k in p.chiavi if not os.environ.get(k)]
        if mancanti:
            come = "; ".join(COME_AVERE[k] for k in mancanti)
            print(f"   saltato: manca {', '.join(mancanti)}. Come averla: {come}")
            esiti.append((p, "saltato (manca la chiave)"))
            continue
        for k in [k for k in p.chiavi_consigliate if not os.environ.get(k)]:
            print(f"   attenzione: manca {k}: il passo gira, ma le celle di quella fonte restano NULL. Come averla: {COME_AVERE[k]}")
        print("   $ " + " ".join(Path(x).name if x == sys.executable else x for x in p.comando))
        if args.dry_run:
            esiti.append((p, "da eseguire"))
            continue
        inizio = time.monotonic()
        r = subprocess.run(p.comando, cwd=RADICE)
        durata = time.monotonic() - inizio
        esiti.append((p, f"ok in {durata:.0f} s" if r.returncode == 0 else f"FALLITO (codice {r.returncode}) dopo {durata:.0f} s"))

    print("\n== Riepilogo")
    for p, esito in esiti:
        print(f"   {p.id:<20} {esito}")
    if not args.dry_run:
        print("\nOra si può avviare il server:  uv run localhost/server/main.py")
    return 1 if any(e.startswith("FALLITO") for _, e in esiti) else 0


if __name__ == "__main__":
    sys.exit(main())
