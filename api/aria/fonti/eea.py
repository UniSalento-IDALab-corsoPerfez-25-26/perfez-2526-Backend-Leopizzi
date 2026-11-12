#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fonte EEA per il dataset aria (client: api/aria/eea.py, nessuna API key;
scheda: data/dataset/aria/eea/EEA.md).

L'EEA riceve i dati della rete ARPA Puglia: stesse stazioni e, sui dati
verificati, stessi valori (con i decimali). Nel dataset è una fonte ridondante
voluta: serve a validare ARPA e OpenAQ cella per cella (v. report, sezione
"Confronto tra fonti").

Dati. Serie orarie per punto di campionamento, scaricate tramite la lista di URL:
  - E1a (verificati) per gli anni già consegnati — oggi 2013-2025, 2014 assente;
  - E2a (non verificati) per l'anno in corso; se la stessa ora c'è in entrambi
    prevale l'E1a. I giorni calcolati con ore E2a hanno nota "non verificato (E2a)".
Ore valide: `Validity` > 0 e valore numerico, finito, non negativo (le ore non
valide arrivano come righe con -9999/-999 e Validity -1). Orari in UTC+1 fisso
(campo Timezone dei metadati), come ARPA: il giorno è la data di `Start`.

Stazioni. Codici EoI nel riquadro del Salento (metadati EEA), ricondotti alle
stazioni ARPA con api/aria/fonti/abbinamento.py. Una stazione entra nel dataset
solo se ha almeno un'ora (valida o no) nel periodo.

Il riquadro (bbox largo, con margine) include anche IT1817A "Monopoli - Aldo
Moro" (provincia di Bari, fuori Salento): esclusa esplicitamente (decisione di
Matteo, 01/10/2026), invece di lasciarla ricomparire ogni volta tra le
"stazioni fuori dai distretti noti" del report.

Valori (decisione del 29/09/2026, uguale per OpenAQ): un solo valore al giorno
per inquinante, la media pesata sul tempo di tutte le misure valide del giorno
(orarie e, se ci sono, giornaliere come il PM10 gravimetrico), senza soglia
minima di ore; la nota riporta la completezza ("media pesata sul tempo su n/24
ore"). Giorno NULL solo se nessuna misura del giorno è valida. Le misure su
intervalli più lunghi di un giorno (`AggType` var settimanali/mensili) sono
ignorate. CO già in mg/m³ come ARPA.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pandas as pd

from api.aria.arpa_puglia import STATO_NULL, STATO_VALORE
from api.aria.eea import (
    DATASET_E1A,
    DATASET_E2A,
    INQUINANTI,
    EEAError,
    get_metadati,
    get_urls,
    info_da_url,
    leggi_parquet,
    stazioni_nel_riquadro,
)
from api.aria.fonti.abbinamento import abbina_ad_arpa, anagrafica_arpa, comuni_salento
from api.aria.fonti.base import FonteAria, RisultatoFonte, consolida_misure, df_capacita, df_stazioni, medie_giornaliere

SIGLA = {codice: sigla for sigla, codice in INQUINANTI.items()}
UNITA_EEA = {"CO": "mg.m-3"}  # unità attesa nei parquet; per gli altri ug.m-3
UNITA_ARPA = {"CO": "mg/m³"}  # per gli altri µg/m³
STATISTICA = "media pesata sul tempo delle misure del giorno"
DOWNLOAD_PARALLELI = 8
NOME_DATASET = {DATASET_E1A: "E1a", DATASET_E2A: "E2a"}
NOTA_E2A = "non verificato (E2a)"
# Stazioni nel riquadro ma fuori dal Salento, escluse a mano (decisione di Matteo, 01/10/2026)
CODICI_ESCLUSI = {"IT1817A": "Monopoli - Aldo Moro (provincia di Bari, fuori Salento)"}


class FonteEEA(FonteAria):
    nome = "EEA"
    copertura_da = date(2013, 1, 1)  # inizio dell'E1a (verificato il 28/09/2026)
    periodi_non_coperti = [(date(2014, 1, 1), date(2014, 12, 31), "anno 2014 assente nell'E1a EEA per l'Italia")]

    def raccogli(self, data_inizio, data_fine):
        errori, falliti = [], []
        note = {"abbinamenti": [], "statistiche": {sigla: STATISTICA for sigla in INQUINANTI},
                "sensori_scartati": [], "dataset_usati": {}, "stazioni_escluse": {}}
        vuoto = lambda: RisultatoFonte(df_stazioni([]), df_capacita([]), consolida_misure([]),  # noqa: E731
                                       periodi_falliti=falliti, errori=errori, note=note)

        inizio = max(data_inizio, self.copertura_da)
        if inizio > data_fine:
            return vuoto()

        try:
            riquadro = stazioni_nel_riquadro(get_metadati())
        except EEAError as exc:
            errori.append({"fonte": self.nome, "chiamata": "metadati", "tipo": "errore_api", "errore": str(exc)})
            falliti.append({"da": inizio, "a": data_fine, "stazione": None, "inquinante": None,
                            "messaggio": f"metadati: {exc}"})
            return vuoto()
        for codice, motivo in CODICI_ESCLUSI.items():
            if codice in set(riquadro["codice_eoi"]):
                note["stazioni_escluse"][codice] = motivo
        riquadro = riquadro[~riquadro["codice_eoi"].isin(CODICI_ESCLUSI)]

        anagrafica, comuni = anagrafica_arpa(), comuni_salento()
        righe_stazioni = {
            s.codice_eoi: abbina_ad_arpa(self.nome, s.codice_eoi, s.nome, s.nome, s.lat, s.lon, anagrafica, comuni)
            for s in riquadro.itertuples(index=False)
        }

        # --- file da scaricare: E1a per gli anni verificati, E2a per quelli recenti --
        anno = date.today().year
        periodi = {
            DATASET_E1A: (inizio, min(data_fine, date(anno - 1, 12, 31))),
            DATASET_E2A: (max(inizio, date(anno - 1, 1, 1)), data_fine),
        }
        compiti = []  # (dataset, url, codice_eoi, sigla)
        for dataset, (da, a) in periodi.items():
            if da > a:
                continue
            note["dataset_usati"][NOME_DATASET[dataset]] = f"{da.isoformat()} → {a.isoformat()}"
            try:
                urls = get_urls(dataset)
            except EEAError as exc:
                errori.append({"fonte": self.nome, "chiamata": f"ParquetFile/urls {NOME_DATASET[dataset]}",
                               "tipo": "errore_api", "errore": str(exc)})
                falliti.append({"da": da, "a": a, "stazione": None, "inquinante": None,
                                "messaggio": f"lista URL {NOME_DATASET[dataset]}: {exc}"})
                continue
            for url in urls:
                codice, codice_inq = info_da_url(url)
                if codice in righe_stazioni and codice_inq in SIGLA:
                    compiti.append((dataset, url, codice, SIGLA[codice_inq]))

        # --- download (in parallelo) e lettura delle sole righe del periodo -------------
        # dal giorno prima per non perdere misure giornaliere/variabili che iniziano prima del periodo
        da_ora, a_ora = pd.Timestamp(inizio - timedelta(days=1)), pd.Timestamp(data_fine + timedelta(days=1))

        def leggi(compito):
            dataset, url, codice, sigla = compito
            try:
                df = leggi_parquet(url, dataset)
            except EEAError as exc:
                return compito, None, exc
            return compito, df[(df["Start"] >= da_ora) & (df["Start"] < a_ora)], None

        with ThreadPoolExecutor(DOWNLOAD_PARALLELI) as pool:
            letti = list(pool.map(leggi, compiti))

        per_serie, stazioni_in_errore = {}, set()
        for (dataset, url, codice, sigla), df, exc in letti:
            stazione = righe_stazioni[codice]["stazione"]
            if exc is not None:
                da, a = periodi[dataset]
                errori.append({"fonte": self.nome, "chiamata": url.rsplit("/", 1)[-1], "tipo": "errore_api",
                               "errore": str(exc)})
                falliti.append({"da": da, "a": a, "stazione": stazione, "inquinante": sigla,
                                "messaggio": f"{url.rsplit('/', 1)[-1]}: {exc}"})
                stazioni_in_errore.add(codice)
                continue
            if df.empty:
                continue
            attesa = UNITA_EEA.get(sigla, "ug.m-3")
            diverse = df["Unit"] != attesa
            if diverse.any():
                note["sensori_scartati"].append(f"{codice} {sigla}: {int(diverse.sum())} righe in "
                                                f"{sorted(df.loc[diverse, 'Unit'].astype(str).unique())} invece di {attesa}")
                df = df[~diverse]
            per_serie.setdefault((codice, sigla), []).append(df)

        # --- statistica giornaliera ---------------------------------------------------------
        stazioni, capacita, misure, unita = [], set(), [], {}
        codici_attivi = set()
        for (codice, sigla), frammenti in per_serie.items():
            stazione = righe_stazioni[codice]["stazione"]
            nuove = self._giornalieri(pd.concat(frammenti, ignore_index=True), sigla, inizio, data_fine)
            if nuove is None:
                continue  # nessuna riga nel periodo: inquinante non misurato → NO_DATA
            codici_attivi.add(codice)
            capacita.add((stazione, sigla))
            unita.setdefault(sigla, UNITA_ARPA.get(sigla, "µg/m³"))
            misure.extend(dict(m, stazione=stazione, inquinante=sigla) for m in nuove)

        for codice in sorted(codici_attivi | stazioni_in_errore):
            riga = dict(righe_stazioni[codice], attiva_da=None, attiva_a=None)
            stazioni.append(riga)
            note["abbinamenti"].append({"id_fonte": codice, "nome_fonte": riga["denominazione"],
                                        "stazione": riga["stazione"], "id_distretto": riga["id_distretto"],
                                        "abbinamento": riga["abbinamento"]})
        for (dataset, url, codice, sigla), _, exc in letti:
            if exc is not None:  # non sappiamo se misurava: le celle saranno NULL (errore API)
                capacita.add((righe_stazioni[codice]["stazione"], sigla))
                unita.setdefault(sigla, UNITA_ARPA.get(sigla, "µg/m³"))

        return RisultatoFonte(
            stazioni=df_stazioni(stazioni),
            capacita=df_capacita(capacita),
            misure=consolida_misure(misure),
            unita=unita,
            periodi_falliti=falliti,
            errori=errori,
            note=note,
        )

    @staticmethod
    def _giornalieri(df, sigla, data_inizio, data_fine):
        """Valori giornalieri (dict giorno/valore/stato/nota) di una stazione × inquinante,
        oppure None se nel periodo non c'è nessuna misura."""
        df = df.copy()
        df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
        df["valida"] = (df["Validity"] > 0) & df["Value"].notna() & (df["Value"] >= 0)
        # la stessa misura da più file (E1a ed E2a, o due punti di campionamento):
        # prevale la verifica migliore (1 = verificato), poi la misura valida
        df = (df.sort_values(["Start", "End", "Verification", "valida"], ascending=[True, True, True, False])
                .drop_duplicates(["Start", "End"]))
        giorni = df["Start"].dt.date
        if not ((giorni >= data_inizio) & (giorni <= data_fine)).any():
            return None
        misure = pd.DataFrame({
            "inizio": df["Start"], "fine": df["End"], "valore": df["Value"].astype(float), "valida": df["valida"],
            "marca": df["Verification"].map(lambda v: None if v == 1 else NOTA_E2A),
        })
        return medie_giornaliere(misure, data_inizio, data_fine)
