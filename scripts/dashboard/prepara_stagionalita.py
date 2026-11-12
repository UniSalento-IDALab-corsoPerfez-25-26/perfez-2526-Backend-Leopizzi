#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prepara i riassunti mensili della tab «Stagionalità» in data/interim/stagionalita/ (gitignored): per ogni mese
dell'archivio aria e della cache ERA5-Land, il valore del mese di Salento e distretti per fonte e inquinante, con
l'esito dei limiti del D.Lgs. 155/2010 (aria), e la T media/massima del mese (calore).

**Ricalcola solo i mesi non ancora preparati**, o quelli il cui file di origine è cambiato (es. il mese aperto
dell'archivio aria, che si allunga ogni giorno): un mese d'aria costa ~14 s, quindi la prima esecuzione sui
34 mesi dura ~8 minuti, le successive pochi secondi. Il server (GET /api/stagionalita) legge solo questi file.
I decessi non servono qui: sono già leggeri, il server li somma al volo.

    uv run scripts/dashboard/prepara_stagionalita.py               # tutti i mesi mancanti
    uv run scripts/dashboard/prepara_stagionalita.py --rigenera    # rifà tutto
    uv run scripts/dashboard/prepara_stagionalita.py --da 2025-01 --a 2025-12 --solo aria

Logica in localhost/server/dati_stagionalita.py.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from localhost.server import dati_stagionalita as st  # noqa: E402
from localhost.server.aggregati_aria import CacheAria  # noqa: E402
from localhost.server.dati_aria import ArchivioAria  # noqa: E402
from localhost.server.dati_calore import ArchivioCalore  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--da", help="primo mese AAAA-MM (default: il primo disponibile)")
    p.add_argument("--a", help="ultimo mese AAAA-MM (default: l'ultimo disponibile)")
    p.add_argument("--solo", choices=("aria", "calore"), help="un solo dominio")
    p.add_argument("--rigenera", action="store_true", help="rifà anche i mesi già preparati")
    args = p.parse_args()

    def nel_periodo(m):
        return (not args.da or m >= args.da) and (not args.a or m <= args.a)

    fatti, saltati, vuoti = 0, 0, 0
    if args.solo in (None, "aria"):
        archivio = ArchivioAria()
        cache = CacheAria(archivio)
        mesi = [m for m in sorted(archivio.mesi_disponibili()) if nel_periodo(m)]
        print(f"aria: {len(mesi)} mesi nell'archivio", flush=True)
        for m in mesi:
            firma = cache._firma(m)
            if not args.rigenera and st.aggiornato(st.file_aria(m), firma):
                saltati += 1
                continue
            t = time.time()
            agg = cache.mese(m, tieni=False)
            if agg is None:
                vuoti += 1
                continue
            st.scrivi(st.file_aria(m), st.riassunto_aria(m, agg, cache.pesi(), firma))
            fatti += 1
            print(f"  aria {m}: preparato in {time.time() - t:.0f} s", flush=True)

    if args.solo in (None, "calore"):
        calore = ArchivioCalore()
        pesi = CacheAria(None).pesi()
        mesi = sorted({m for v in calore.mesi_in_cache().values() for m in v if nel_periodo(m)})
        print(f"calore: {len(mesi)} mesi in cache ERA5-Land", flush=True)
        for m in mesi:
            firma = st.firma_calore(m)
            if not args.rigenera and st.aggiornato(st.file_calore(m), firma):
                saltati += 1
                continue
            r = st.riassunto_calore(m, calore, pesi, firma)
            if r is None:
                vuoti += 1
                continue
            st.scrivi(st.file_calore(m), r)
            fatti += 1
            print(f"  calore {m}: preparato", flush=True)

    print(f"fatto: {fatti} mesi preparati, {saltati} già pronti (saltati), {vuoti} senza dati. "
          f"Cartella: {st.DIR_STAGIONALITA}")


if __name__ == "__main__":
    main()
