#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera i dati sanitari **simulati** (ricoveri per causa, accessi in PS, accessi in PS degli assistiti in ADI)
per comune × giorno (con il distretto accanto), nei due scenari `nullo` e `letteratura`, e il report di verifica.

Sono dati di partenza in attesa dei dati richiesti ad AReSS Puglia e a Parsec 3,26: non descrivono la
situazione sanitaria reale. Modello e parametri: api/salute/simulazione.py; scheda e dicitura:
data/dataset/salute/simulati/Dati_Simulati.md.

Scrive (gitignored) in data/interim/salute/simulati/:
  salute_simulata.parquet    scenario, id_comune, id_distretto, data, indicatore, valore, stato, nota
                             (parquet: a comune × giorno un CSV supererebbe i 200 MB)
  esposizione_comuni.csv     id_comune, id_distretto, data, PM10 e NO2 CAMS, T max ERA5-Land e le esposizioni con lag
  parametri.json             versione, seme, periodo, dicitura, parametri con le fonti
e il report data/dataset/salute/simulati/Report_simulazione.md.

Legge solo file locali: archivio aria (CAMS) e cache ERA5-Land. Il periodo di default va dal 2024-01-01
all'ultimo giorno in cui aria e temperatura coprono tutti i comuni; si allunga a ritroso quando la cache
ERA5-Land 2021-2023 sarà completa.

Uso (dalla radice del repo):
  uv run scripts/salute/simula_dati_salute.py
  uv run scripts/salute/simula_dati_salute.py --da 2024-01-01 --a 2026-09-30 --moltiplicatore 1
"""

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))

import pandas as pd  # noqa: E402

from api.salute import simulazione as sa  # noqa: E402

REPORT = RADICE / "data" / "dataset" / "salute" / "simulati" / "Report_simulazione.md"


def periodo_coperto(esp):
    """Ultimo giorno in cui PM10, NO2 e T max ci sono per tutti i comuni."""
    completi = esp.dropna(subset=["pm10", "no2", "tmax"]).groupby("data")["id_comune"].nunique()
    completi = completi[completi == esp["id_comune"].nunique()]
    return completi.index.max()


def tabella(righe, intestazione):
    out = ["| " + " | ".join(intestazione) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(intestazione))) + "|"]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in righe]
    return "\n".join(out)


def num(x, cifre=0):
    return f"{x:,.{cifre}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x, cifre=1, segno=False):
    """Percentuale all'italiana: 0,604 -> '60,4%'."""
    return f"{x * 100:{'+' if segno else ''}.{cifre}f}%".replace(".", ",")


def scrivi_report(celle, esp, args, da, a, durata):
    residenti = int(sim.comuni()["residenti"].sum())
    giorni = (pd.Timestamp(a) - pd.Timestamp(da)).days + 1
    anni_eq = giorni / 365.25
    nullo = celle[celle["scenario"] == "nullo"]
    lett = celle[celle["scenario"] == "letteratura"]
    s = [f"# Report della simulazione dei dati sanitari",
         "",
         f"*Generato da `scripts/salute/simula_dati_salute.py` il {datetime.now():%d/%m/%Y %H:%M} "
         f"(versione del modello {sim.VERSIONE}, seme {args.seme}, moltiplicatore degli effetti {args.moltiplicatore}). "
         f"Periodo: **{da} → {a}** ({giorni} giorni), 145 comuni × giorno (20 distretti), due scenari. Durata: {durata:.0f} s.*",
         "",
         f"> ⚠️ **{sim.DICITURA}**",
         "",
         "Modello, parametri e fonti: `api/salute/simulazione.py` e `Dati_Simulati.md` in questa cartella.",
         "",
         "## 1. Calibrazione: i livelli tornano con le fonti pubbliche?",
         "",
         "Scenario `nullo` (senza effetto dell'ambiente). Ricoveri: media annua simulata per provincia contro le "
         "dimissioni ISTAT Health for All dell'ultimo anno pubblicato (2024).",
         ""]
    hfa = pd.read_csv(sim.FILE_HFA)
    righe = []
    for ind, gruppo in sim.PARAMETRI["ricoveri"]["gruppi"].items():
        for prov in ("LE", "BR", "TA"):
            simulato = nullo[(nullo["indicatore"] == ind) & nullo["id_distretto"].str.startswith(prov)]["valore"].sum() / anni_eq
            reale = hfa[(hfa["provincia"] == prov) & (hfa["gruppo"] == gruppo) & (hfa["anno"] == 2024)]["dimissioni"].iloc[0]
            righe.append((ind, prov, num(simulato), num(reale), pct(simulato / reale - 1, segno=True)))
    s += [tabella(righe, ["Indicatore", "Provincia", "Simulato (media annua)", "HFA 2024", "Scarto"]), ""]
    ps = nullo[nullo["indicatore"] == "ps_accessi"]["valore"].sum() / anni_eq / residenti * 1000
    assistiti = nullo[nullo["indicatore"] == "adi_assistiti"].groupby("id_comune")["valore"].first().sum()
    acc_adi = nullo[nullo["indicatore"] == "adi_accessi_ps"]["valore"].sum()
    rit = nullo[nullo["indicatore"] == "adi_ritorni_30g"]["valore"].sum()
    bassa = nullo[nullo["indicatore"] == "adi_accessi_bassa_urgenza"]["valore"].sum()
    p = sim.PARAMETRI
    s += [tabella([
        ("Accessi in PS per 1.000 residenti l'anno", num(ps, 1), num(p["ps"]["tasso_annuo_per_1000"], 1)),
        ("Assistiti in ADI (Salento)", num(assistiti), f"{pct(p['adi']['quota_over65'])} degli over 65 × {pct(p['adi']['quota_assistiti_over65'], 0)}"),
        ("Accessi in PS per assistito ADI l'anno", num(acc_adi / anni_eq / assistiti, 2), num(p["adi"]["accessi_ps_per_assistito_anno"], 2)),
        ("Quota di accessi ADI a bassa urgenza", pct(bassa / acc_adi), pct(p['adi']['quota_bassa_urgenza'], 0)),
        ("Quota di accessi ADI che sono ritorni entro 30 giorni", pct(rit / acc_adi), "emerge dalla fragilità (non imposta)"),
    ], ["Grandezza", "Simulato", "Parametro"]), ""]

    s += ["## 2. Verifica: il modello ritrova l'effetto solo quando c'è?",
          "",
          "Ogni scenario è ristimato con un modello di Poisson di serie temporali standard (effetti fissi di comune "
          "e anno, stagione con due armoniche, giorno della settimana). Nello scenario `nullo` le stime devono "
          "comprendere lo zero; nello scenario `letteratura` devono essere vicine all'effetto imposto. Un intervallo "
          "largo che comprende lo zero anche in `letteratura` dice che, alla dimensione reale dell'effetto, "
          "**quasi tre anni di dati dei 145 comuni non bastano a vederlo** (succede con PM10 e NO2, la cui variazione giornaliera in CAMS è piccola): è un limite di potenza statistica, "
          "non del generatore.",
          ""]
    righe = []
    for ind in ("ricoveri_respiratori", "ps_respiratori", "adi_accessi_ps", "ricoveri_circolatori", "ps_cardiovascolari"):
        esposizioni = p["esiti"].get(ind) or p["esiti"].get(ind.replace("ricoveri_", "ricoveri_"))
        for scenario, dati in (("nullo", nullo), ("letteratura", lett)):
            stime = sim.stima_effetti(dati, esp, ind, esposizioni)
            for e, (st, lo, hi, unita) in stime.items():
                imposto = 0.0 if scenario == "nullo" else (p["effetti"][e].get("per_10") or p["effetti"][e]["per_grado"]) * args.moltiplicatore
                righe.append((ind, scenario, e, unita, pct(imposto / 100, 2, True),
                              f"{pct(st / 100, 2, True)} ({pct(lo / 100, 2, True)}; {pct(hi / 100, 2, True)})"))
    s += [tabella(righe, ["Indicatore", "Scenario", "Esposizione", "Unità", "Imposto", "Stimato (IC95%)"]), ""]

    s += ["## 3. Il tranello della correlazione grezza",
          "",
          "Correlazione fra PM10 medio e tasso di ricoveri respiratori a **distretto × mese**, senza togliere la "
          "stagione: è la lettura che darebbe una dashboard che mette le due serie una accanto all'altra.",
          ""]
    righe = [(sc, num(sim.correlazione_grezza(d, esp, "ricoveri_respiratori", "pm10"), 3),
              num(sim.correlazione_grezza(d, esp, "ricoveri_respiratori", "tmax"), 3))
             for sc, d in (("nullo", nullo), ("letteratura", lett))]
    s += [tabella(righe, ["Scenario", "r(PM10, ricoveri resp.)", "r(T max, ricoveri resp.)"]), "",
          "Come leggerla: nello scenario `nullo` aria e caldo **non hanno alcun effetto per costruzione**, eppure le "
          "correlazioni non sono zero; nello scenario `letteratura` il caldo **aumenta** i ricoveri, eppure la "
          "correlazione grezza con la T max può restare negativa. Il motivo è la stagione: l'inverno porta più "
          "ricoveri (stagionalità calibrata sui decessi reali), più PM10 e meno caldo, e domina il confronto. Solo il "
          "modello che toglie la stagione (sezione 2) ritrova l'effetto imposto. È la dimostrazione, su dati di cui "
          "conosciamo la verità, del perché in dashboard e in tesi la correlazione resta **esplorativa e non "
          "causale** (docs/Regole_dei_dati.md).",
          ""]

    s += ["## 4. ADI: i periodi critici",
          "",
          "Accessi in PS degli assistiti in ADI per 1.000 assistiti al giorno, nei mesi da giugno a settembre, nei "
          "giorni con T max (media lag 0-3) oltre i 30 °C contro gli altri giorni estivi. Nello scenario `nullo` la "
          "differenza viene solo dal profilo stagionale e dal caso. È la criticità che la "
          "dashboard deve far emergere: i giorni in cui conviene anticipare telefonate e visite domiciliari "
          "(medici di famiglia, volontariato, protezione civile) per evitare l'accesso al PS.",
          ""]
    righe = []
    for sc, d in (("nullo", nullo), ("letteratura", lett)):
        x = d[d["indicatore"].isin(["adi_accessi_ps", "adi_assistiti", "adi_accessi_bassa_urgenza"])].pivot_table(
            index=["id_comune", "data"], columns="indicatore", values="valore").reset_index()
        x = x.merge(esp.assign(data=esp["data"].dt.strftime("%Y-%m-%d"))[["id_comune", "data", "caldo_lag03"]],
                    on=["id_comune", "data"])
        x = x[pd.to_datetime(x["data"]).dt.month.between(6, 9)]
        caldo = x["caldo_lag03"] > 0
        tasso = lambda m, col="adi_accessi_ps": x.loc[m, col].sum() / x.loc[m, "adi_assistiti"].sum() * 1000
        righe.append((sc, int(caldo.sum()), num(tasso(caldo), 2), num(tasso(~caldo), 2),
                      pct(tasso(caldo) / tasso(~caldo) - 1, segno=True), num(tasso(caldo, "adi_accessi_bassa_urgenza"), 2)))
    s += [tabella(righe, ["Scenario", "Comune-giorni caldi", "Accessi/1.000 assistiti, caldo", "… altri giorni estivi",
                          "Differenza", "di cui a bassa urgenza, caldo"]), ""]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(s) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--da", default="2024-01-01", help="primo giorno (AAAA-MM-GG)")
    ap.add_argument("--a", help="ultimo giorno (default: ultimo giorno con aria e temperatura per tutti i comuni)")
    ap.add_argument("--seme", type=int, default=sim.SEME)
    ap.add_argument("--moltiplicatore", type=float, default=1.0,
                    help="moltiplica gli effetti dello scenario `letteratura` (1 = valori di letteratura)")
    args = ap.parse_args()
    inizio = time.time()
    a_richiesto = args.a or date.today().isoformat()
    print(f"Esposizione {args.da} → {a_richiesto} (CAMS + ERA5-Land, solo file locali)…")
    esp = sim.esposizione_comuni(args.da, a_richiesto)
    a = args.a or periodo_coperto(esp).strftime("%Y-%m-%d")
    esp = sim.esposizioni_con_lag(esp[esp["data"] <= a])
    buchi = esp[["pm10", "no2", "tmax"]].isna().sum()
    print(f"Periodo: {args.da} → {a}; comune-giorni senza PM10/NO2/T max: {dict(buchi)}")

    celle = pd.concat([sim.simula(esp, sc, args.seme, args.moltiplicatore) for sc in sim.SCENARI], ignore_index=True)
    sim.DIR_USCITA.mkdir(parents=True, exist_ok=True)
    celle.to_parquet(sim.DIR_USCITA / "salute_simulata.parquet", index=False)
    esp.assign(data=esp["data"].dt.strftime("%Y-%m-%d")).round(3).to_csv(sim.DIR_USCITA / "esposizione_comuni.csv", index=False)
    for superato in ("salute_simulata.csv", "esposizione_distretti.csv"):  # uscite della versione per distretto
        (sim.DIR_USCITA / superato).unlink(missing_ok=True)
    (sim.DIR_USCITA / "parametri.json").write_text(json.dumps({
        "versione": sim.VERSIONE, "generato_il": datetime.now().isoformat(timespec="seconds"),
        "periodo": {"da": args.da, "a": a}, "seme": args.seme, "moltiplicatore": args.moltiplicatore,
        "scenari": list(sim.SCENARI), "indicatori": sim.INDICATORI, "dicitura": sim.DICITURA,
        "parametri": sim.PARAMETRI}, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    print(f"Scritte {len(celle):,} celle in {sim.DIR_USCITA}")
    scrivi_report(celle, esp, args, args.da, a, time.time() - inizio)
    print(f"Report: {REPORT.relative_to(RADICE)}")


if __name__ == "__main__":
    main()
