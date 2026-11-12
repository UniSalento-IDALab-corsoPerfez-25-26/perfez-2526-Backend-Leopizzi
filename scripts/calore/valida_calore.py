#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validazione per ridondanza di ERA5-Land con la temperatura misurata da ARPA meteo (docs/Regole_dei_dati.md).

Per ogni stazione ARPA del Salento confronta, giorno per giorno, il suo valore (media, massima, minima) con
quello ERA5-Land del comune che la contiene, sui soli giorni in cui entrambe le fonti hanno `VALORE` e sui soli
mesi ERA5-Land presenti in cache. Per ogni coppia: bias (ERA5 − ARPA), errore medio assoluto, RMSE, correlazione.
Poi confronta i **giorni sopra soglia** (api/calore/soglie.py): quanti ne vede ARPA e quanti ERA5-Land.

Scrive data/dataset/calore/report/Report_validazione_calore.md. Legge solo la cache.

    uv run scripts/calore/valida_calore.py
"""

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from api.calore import arpa_meteo, era5_land  # noqa: E402
from api.calore.dataset_calore import arpa_meteo_stazioni  # noqa: E402
from api.calore.soglie import SOGLIE  # noqa: E402
from api.aria.copernicus_cams import CopernicusError  # noqa: E402

FILE_REPORT = era5_land.RADICE / "data" / "dataset" / "calore" / "report" / "Report_validazione_calore.md"


def mesi_era5():
    """{statistica: [(anno, mese)]} dei mesi in cache."""
    out = {s: [] for s in era5_land.STATISTICHE}
    for f in sorted(era5_land.DIR_CACHE.glob("*.parquet")):
        stat, resto = f.stem.split("_")
        if stat in out:
            out[stat].append((int(resto[:4]), int(resto[5:])))
    return out


def era5_comuni(statistica, mesi):
    parti = []
    for anno, m in mesi:
        try:
            parti.append(era5_land.temperatura_comuni(statistica, anno, m, scarica=False))
        except CopernicusError:
            pass
    df = pd.concat(parti, ignore_index=True)
    return df[df["stato"] == "VALORE"][["comune", "giorno", "valore"]]


def confronta():
    stazioni = arpa_meteo_stazioni()
    mesi = mesi_era5()
    era = {s: era5_comuni(s, mesi[s]) for s in era5_land.STATISTICHE}
    righe, soglie = [], []
    for r in stazioni.itertuples():
        anni = sorted({a for a, _ in mesi["media"]} & set(arpa_meteo.ANNI))
        arpa = []
        for anno in anni:
            try:
                arpa.append(arpa_meteo.giornaliero(r.rete, r.id_station, anno, scarica=False))
            except arpa_meteo.ArpaMeteoError:
                pass
        if not arpa:
            continue
        arpa = pd.concat(arpa, ignore_index=True)
        arpa = arpa[arpa["stato"] == "VALORE"]
        for s in era5_land.STATISTICHE:
            a = arpa[arpa["statistica"] == s][["giorno", "valore"]]
            e = era[s][era[s]["comune"] == r.id_comune][["giorno", "valore"]]
            j = a.merge(e, on="giorno", suffixes=("_arpa", "_era"))
            if len(j) < 30:
                continue
            d = j["valore_era"] - j["valore_arpa"]
            righe.append({"stazione": f"meteo.{r.id_station}", "rete": r.rete, "comune": r.id_comune, "statistica": s,
                          "n": len(j), "bias": d.mean(), "mae": d.abs().mean(), "rmse": float(np.sqrt((d ** 2).mean())),
                          "r": float(np.corrcoef(j["valore_era"], j["valore_arpa"])[0, 1])})
            for nome, (stat, soglia, _) in SOGLIE.items():
                if stat == s:
                    soglie.append({"stazione": f"meteo.{r.id_station}", "rete": r.rete, "soglia": nome, "n": len(j),
                                   "arpa": int((j["valore_arpa"] >= soglia).sum()), "era5": int((j["valore_era"] >= soglia).sum())})
    return pd.DataFrame(righe), pd.DataFrame(soglie), mesi


def tabella(df, colonne, intestazioni):
    righe = ["| " + " | ".join(intestazioni) + " |", "|" + "---|" * len(intestazioni)]
    for r in df[colonne].itertuples(index=False):
        righe.append("| " + " | ".join(f"{x:.2f}" if isinstance(x, float) else str(x) for x in r) + " |")
    return "\n".join(righe)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cfr, soglie, mesi = confronta()
    if cfr.empty:
        sys.exit("nessun confronto possibile: servono ERA5-Land in cache e le stazioni ARPA scaricate")
    ordine = list(era5_land.STATISTICHE)
    per_stat = cfr.groupby("statistica").agg(stazioni=("stazione", "nunique"), n=("n", "sum"), bias=("bias", "mean"),
                                             mae=("mae", "mean"), rmse=("rmse", "mean"), r=("r", "mean")).reindex(ordine).reset_index()
    per_rete = cfr.groupby(["rete", "statistica"]).agg(n=("n", "sum"), bias=("bias", "mean"), mae=("mae", "mean"),
                                                       r=("r", "mean")).reset_index()
    somma = soglie.groupby("soglia")[["n", "arpa", "era5"]].sum().reindex(list(SOGLIE)).reset_index()
    somma["diff"] = somma["era5"] - somma["arpa"]
    periodo = sorted(set(m for v in mesi.values() for m in v))
    testo = f"""# Validazione di ERA5-Land con ARPA meteo (temperatura a 2 m)

*Generato da `scripts/calore/valida_calore.py` il {datetime.now():%d/%m/%Y %H:%M}. Validazione per ridondanza (docs/Regole_dei_dati.md): ERA5-Land è **modellato**, ARPA **misurato**.*

- **Periodo confrontato:** {len(periodo)} mesi ERA5-Land in cache, da {periodo[0][0]}-{periodo[0][1]:02d} a {periodo[-1][0]}-{periodo[-1][1]:02d} (i mesi non scaricati non entrano).
- **Coppie:** una per stazione ARPA e giorno, con il valore ERA5-Land del **comune che contiene la stazione** (media pesata sull'area, ~9 km). Solo giorni in cui entrambe hanno `VALORE`.
- **Segno del bias:** ERA5-Land − ARPA (negativo = ERA5-Land più freddo della misura).

## 1. Accordo per statistica

{tabella(per_stat, ['statistica', 'stazioni', 'n', 'bias', 'mae', 'rmse', 'r'], ['Statistica', 'Stazioni', 'Coppie', 'Bias °C', 'Errore medio abs. °C', 'RMSE °C', 'Correlazione'])}

## 2. Per rete

La rete RRQA vede 24 letture orarie al giorno, la rete dedicata una ogni 30 minuti con il massimo/minimo di ciascuna: **massima e minima non sono la stessa statistica** nelle due reti (la dedicata coglie picchi più estremi).

{tabella(per_rete, ['rete', 'statistica', 'n', 'bias', 'mae', 'r'], ['Rete', 'Statistica', 'Coppie', 'Bias °C', 'Errore medio abs. °C', 'Correlazione'])}

## 3. Per stazione

{tabella(cfr.sort_values(['statistica', 'stazione']), ['stazione', 'rete', 'comune', 'statistica', 'n', 'bias', 'mae', 'rmse', 'r'], ['Stazione', 'Rete', 'Comune', 'Statistica', 'Coppie', 'Bias', 'MAE', 'RMSE', 'r'])}

## 4. Giorni sopra soglia

Somma sulle stazioni e sui giorni confrontati. Le soglie sono in `api/calore/soglie.py` (v. `Soglie_Caldo.md`).

{tabella(somma, ['soglia', 'n', 'arpa', 'era5', 'diff'], ['Indicatore', 'Giorni confrontati', 'ARPA (misurato)', 'ERA5-Land (modellato)', 'ERA5 − ARPA'])}

## 5. Lettura e limiti

- **Esplorativa, non causale.** Il confronto dice quanto ERA5-Land segue la misura, non quanto sia «giusto» il dato in un punto.
- La **media** è ben riprodotta; la **massima** è sottostimata e la **minima** sovrastimata: ERA5-Land è una media su ~9 km, smussa i picchi, e una stazione è un punto. Quindi i giorni sopra 35 °C e le notti tropicali da ERA5-Land sono **soglie sbagliate in modo sistematico** rispetto alla misura: usarle come **ordine di grandezza**, e dove c'è una stazione preferire il dato misurato.
- Il confronto vale **dove ci sono stazioni** (11 comuni su 145): altrove ERA5-Land resta l'unica fonte e il suo errore non è osservabile, ma è plausibilmente dello stesso ordine.
- Pochi mesi in cache → poche stagioni: i bias estivi e invernali non sono separati. Rilanciare lo script dopo aver scaricato altri mesi.
"""
    FILE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    FILE_REPORT.write_text(testo, encoding="utf-8")
    print(per_stat.round(2).to_string(index=False))
    print(somma.to_string(index=False))
    print(f"\nReport → {FILE_REPORT}")


if __name__ == "__main__":
    main()
