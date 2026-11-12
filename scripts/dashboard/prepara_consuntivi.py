#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prepara i consuntivi mensili di aria e calore in data/interim/consuntivi/ (gitignored), per avviare e usare la
dashboard senza ricalcolare gli aggregati dai dataset di partenza (un mese d'aria costa ~14 s).

- aria: per ogni mese dell'archivio, il riassunto di **tutte le fonti** (ARPA, OpenAQ, EEA, CAMS e vista «Tutte»);
- calore: per ogni mese e statistica, comune × giorno di **ERA5-Land** (cache locale) e di **ARPA meteo**.

Incrementale: si ricalcolano solo i mesi mancanti o con i file di origine cambiati (il mese aperto dell'archivio
aria si rifà ogni giorno). Il server usa gli stessi file da solo, anche senza lanciare questo script: lo script
serve a scaldarli tutti in anticipo. Dopo ogni aggiornamento dell'archivio aria va rilanciato, come
prepara_stagionalita.py (i riassunti della tab Stagionalità restano un prodotto a parte).

    uv run scripts/dashboard/prepara_consuntivi.py                      # tutti i mesi mancanti
    uv run scripts/dashboard/prepara_consuntivi.py --da 2024-01 --a 2026-12
    uv run scripts/dashboard/prepara_consuntivi.py --solo calore --rigenera
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from api.calore import era5_land  # noqa: E402
from localhost.server import consuntivi  # noqa: E402
from localhost.server.aggregati_aria import CacheAria  # noqa: E402
from localhost.server.dati_aria import ArchivioAria  # noqa: E402
from localhost.server.dati_calore import ArchivioCalore  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--da", default="2024-01", help="primo mese AAAA-MM (default: 2024-01)")
    p.add_argument("--a", help="ultimo mese AAAA-MM (default: l'ultimo disponibile)")
    p.add_argument("--solo", choices=("aria", "calore"), help="un solo dominio")
    p.add_argument("--rigenera", action="store_true", help="rifà anche i consuntivi già pronti")
    args = p.parse_args()

    def nel_periodo(m):
        return m >= args.da and (not args.a or m <= args.a)

    def cancella(nome):
        f = consuntivi.percorso(nome)
        if args.rigenera and f.exists():
            f.unlink()

    fatti = pronti = vuoti = 0
    if args.solo in (None, "aria"):
        archivio = ArchivioAria()
        cache = CacheAria(archivio)
        mesi = [m for m in sorted(archivio.mesi_disponibili()) if nel_periodo(m)]
        print(f"aria: {len(mesi)} mesi nell'archivio", flush=True)
        for m in mesi:
            cancella(f"aria_{m}")
            if consuntivi.leggi(f"aria_{m}", cache._firma(m)) is not None:
                pronti += 1
                continue
            t = time.time()
            if cache.riassunto(m, tieni=False) is None:
                vuoti += 1
                continue
            fatti += 1
            print(f"  aria {m}: calcolato in {time.time() - t:.0f} s", flush=True)

    if args.solo in (None, "calore"):
        calore = ArchivioCalore()
        in_cache = calore.mesi_in_cache()
        mesi = sorted({m for v in in_cache.values() for m in v if nel_periodo(m)})
        print(f"calore: {len(mesi)} mesi in cache ERA5-Land", flush=True)
        for m in mesi:
            for s in era5_land.STATISTICHE:
                if m not in in_cache.get(s, []):
                    continue
                cancella(f"calore_{s}_{m}")
                t = time.time()
                prima = consuntivi.percorso(f"calore_{s}_{m}").exists()
                if calore.comune_giorno(s, m) is None:
                    vuoti += 1
                elif prima:
                    pronti += 1
                else:
                    fatti += 1
                    print(f"  calore ERA5-Land {s} {m}: calcolato in {time.time() - t:.1f} s", flush=True)
            if calore.arpa_disponibile():
                for s in era5_land.STATISTICHE:
                    cancella(f"calore_arpa_{s}_{m}")
                    prima = consuntivi.percorso(f"calore_arpa_{s}_{m}").exists()
                    try:
                        df = calore.arpa_comune_giorno(s, m)
                    except Exception as e:  # noqa: BLE001 — un mese senza CSV ARPA non ferma gli altri
                        print(f"  calore ARPA {s} {m}: saltato ({e})", flush=True)
                        vuoti += 1
                        continue
                    if df is None:
                        vuoti += 1
                    elif prima:
                        pronti += 1
                    else:
                        fatti += 1

    print(f"fatto: {fatti} consuntivi calcolati, {pronti} già pronti, {vuoti} senza dati. Cartella: {consuntivi.DIR_CONSUNTIVI}")


if __name__ == "__main__":
    main()
