# Lista dataset — Qualità dell'aria

Fonti **realmente usate** per il dataset aria, con fonte, licenza e cosa se ne preleva, divise per organizzazione. Deve rimanere sempre aggiornato. Indice generale e fonti territoriali: `Lista_dataset.md`. Dataset salute: `Lista_dataset_salute.md`.

**Obiettivo:** un **dataset aria unificato** — JSON annidato provincia → distretto → comune → stazione → giorno → fonte → inquinante, un valore per fonte (mai aggregato tra fonti), ogni cella con stato `VALORE` / `NULL` / `NO_DATA` (v. docs/Regole_dei_dati.md), rigenerato in `data/interim/aria/` (gitignored) via chiamate API dirette con `uv run --env-file .env scripts/aria/genera_dataset_aria.py --da … --a …`, che produce anche un report di analisi in `report/`. Ogni fonte è un adattatore in `api/aria/fonti/`. Anagrafiche relazionali (stazioni collegate al comune, inquinanti): `anagrafica/`, v. `Anagrafiche_relazionali.md`. Da mettere a confronto in serie temporale con il dataset salute.

**Inquinanti di riferimento (26/09/2026):** CO, NO2, O3, PM2.5, SO2 — v. `docs/Specifiche_Design.md` del repository Frontend. Si usano tutti quelli disponibili per zona/periodo; dove uno manca per un distretto/stazione va indicato esplicitamente, non omesso. Elenco completo dei 10 inquinanti ARPA con limiti di legge: `arpa_puglia/Parametri_Qualita_Aria.md`.

---

## ARPA Puglia — fonte primaria

**Cosa ci procuriamo**: misurazioni giornaliere di qualità dell'aria (i 10 inquinanti ARPA, tra cui i 5 di riferimento) dalle stazioni della Rete Regionale di Rilevamento della Qualità dell'Aria (RRQA) e delle reti locali/private, nelle province di Lecce, Brindisi e Taranto; anagrafica delle stazioni con coordinate.

- **Accesso usato** (dal 27/09/2026): host `old.arpa.puglia.it/ARPA_ARIA/`, che espone **lo stesso contratto** documentato nella guida ufficiale per `cloud.arpa.puglia.it` (stessi campi e parametri: `measurement_date`, `year`, `month`, `id_station`, `network`, `format`):
  - `dati.jsp` ≈ `QualitaAria` — misurazioni giornaliere
  - `centraline.jsp` ≈ `QualitaAria/Stations` — anagrafica stazioni (GeoJSON)
  - `inquinanti.jsp` ≈ `QualitaAria/Pollutants` — anagrafica inquinanti
- **Copertura verificata** (27/09/2026, controllando valori non-null e non solo la risposta HTTP): **2012 → oggi**, aggiornata ogni giorno (senza `measurement_date` restituisce il giorno precedente). Copre quindi anche gli anni che prima risultavano scoperti (2019-2022, 2024-oggi). Alcune stazioni hanno buchi propri (es. Arnesano senza valori nel 2013-2014).
- ⚠️ **Host non documentato**: `old.arpa.puglia.it` non compare in nessuna guida ARPA in nostro possesso — è stato trovato per tentativi. Può sparire senza preavviso; l'host documentato `cloud.arpa.puglia.it` resta **irraggiungibile** (timeout, dall'ambiente di sviluppo e dalla rete dell'autore). In tesi citare la guida ufficiale per il contratto dei dati e dichiarare l'host effettivamente usato.
  - **Come è stato trovato** (27/09/2026): per tentativi, provando i nomi dei servizi della guida su host storici di ARPA Puglia; `old.arpa.puglia.it/ARPA_ARIA/` risponde con gli stessi campi e gli stessi parametri e con dati reali 2012 → ieri.
  - **Scelta di Matteo (07/11/2026):** si continua a usare `old.arpa.puglia.it`, senza più riverificare `cloud.arpa.puglia.it`. Se l'host sparisse, l'archivio già generato resta valido; per i dati nuovi l'alternativa documentata è la guida ufficiale, con l'host `cloud.arpa.puglia.it`, ed EEA come canale europeo (v. `eea/EEA.md`).
  - **Ultima verifica:** 07/11/2026, `get_qualita_aria_giorno('2026-11-06')` risponde con 199 righe (client `api/aria/arpa_puglia.py`).
  - **Conferma d'uso e licenza da ARPA Puglia:** **non si chiede** (Matteo, 07/11/2026): resta un'assunzione dichiarata (CC BY 4.0 come per i dataset ARPA su dati.puglia.it) e la tesi dice che l'host non è documentato.
- **Guida ufficiale**: `arpa_puglia/API_ARPA.pdf` (ARPA Puglia, *Servizio di interoperabilità Open Data — Linea guida per la interoperabilità ai servizi API*, Rev_01, 09/10/2023).
- **Licenza**: la guida non dichiara una licenza per l'API; i dataset ARPA pubblicati su dati.puglia.it sono in **CC BY 4.0** (assunzione: vale anche per i dati esposti via API — **da confermare con ARPA Puglia** prima di citarla formalmente in tesi).
- **Qualità del dato**: la sorgente contiene righe duplicate identiche (es. stazione 31 di Arnesano, PM10 dello stesso giorno ripetuto 5 volte) e tipi incoerenti tra mesi (id_station intero/stringa, date con/senza orario) — il client normalizza e deduplica.
- **Stazioni**: 74 in Puglia, 49 nelle tre province del Salento (incluse le 6 private della rete ADI ex-ILVA a Taranto e, dal 01/10/2026, le 6 private della rete VERSALIS, petrolchimico di Brindisi, id_station 114-119, aggiunte all'anagrafica e trattate come tutte le altre stazioni — decisione di Matteo). Copia locale: `arpa_puglia/stazioni_di_monitoraggio.json` (rigenerabile con `scripts/aria/aggiorna_stazioni_arpa.py`, che però riscarica solo quanto espone `centraline.jsp`: le VERSALIS non ci sono e vanno riaggiunte a mano se il file viene rigenerato). Tabella stazioni × distretto: `arpa_puglia/Stazioni_Salento.md`.
- **Copertura per distretto**: **12 distretti su 20** hanno almeno una stazione pubblica; **8 non coperti** (LE-53 Nardò, LE-54 Martano, LE-56 Gallipoli, LE-58 Poggiardo, LE-59 Casarano, LE-60 Gagliano del Capo, TA-01 Ginosa, TA-07 Manduria) — `arpa_puglia/Copertura_Distretti_ARPA.json`.
- **Codice**: `api/aria/arpa_puglia.py` — endpoint `get_qualita_aria_periodo(distretti, data_inizio, data_fine)` (qualunque periodo 2012→ieri), `get_qualita_aria_mensile(anno, mese)`, `get_qualita_aria_giorno(data)`, `get_stazioni()`, `get_inquinanti()`.
- **Ente**: ARPA Puglia — Centro Regionale Aria (UOC CRA)

### Riscontro indipendente: mirror CKAN su dati.puglia.it (solo 2023)

Prima fonte usata, ora secondaria: stessi dati ARPA pubblicati sul portale regionale, per il solo 2023 (12 dataset mensili `dati-qualita-aria-2023`). Tenuto come **riscontro indipendente** per quell'anno (per verificare in tesi che le due vie di accesso concordino).

- Scaricato il 27/09/2026 per Lecce/Brindisi/Taranto: 72.635 righe deduplicate → `data/raw/aria/arpa_puglia/qualita_aria_2023_salento.json` (gitignored), script `scripts/aria/scarica_qualita_aria_2023.py`.
- Codice: `get_qualita_aria_mensile_2023_ckan(mese)` in `api/aria/arpa_puglia.py`, client CKAN generico in `api/comune/dati_puglia_ckan.py`.
- **Licenza**: **CC BY 4.0** (decisione di Matteo del 01/10/2026: usare sempre la stessa licenza dichiarata per gli altri dataset ARPA su dati.puglia.it, senza verificarla dataset per dataset).
- Anni 2014-2017 e 1° semestre 2018 esistono su dati.puglia.it solo come ZIP ospitati su `dati.comune.lecce.it`: non esplorati e, con `old.arpa.puglia.it` che copre dal 2012, probabilmente non più necessari.

---

## OpenAQ — seconda fonte

**Cosa ci procuriamo**: misurazioni di qualità dell'aria (CO, NO2, O3, PM2.5, SO2, PM10) per le stazioni della rete EEA/ARPA nel Salento, come **seconda fonte indipendente** della pipeline multi-fonte (v. docs/Regole_dei_dati.md). Da quando ARPA copre da sola 2012→oggi, OpenAQ non serve più a coprire anni mancanti: resta un riscontro sullo stesso periodo, tenuto come valore separato per fonte.

- **Scheda completa**: `openaq/OpenAQ.md` (link, documentazione API v3, endpoint usati, licenze, copertura verificata)
- **Valore giornaliero** *(dal 29/09/2026)*: media pesata sul tempo delle misure orarie del giorno in UTC+1, senza soglia di ore, completezza nella nota. ⚠️ Gli orari OpenAQ sono sfasati di 0-2 ore rispetto a EEA/ARPA in modo variabile nel tempo (scoperto con la validazione, v. scheda).
- **Copertura reale**: 2020-05-06 → oggi (2019 non coperto); dal 01/06/2026 le stazioni storiche cambiano id — va riconciliato vecchio/nuovo id per nome+coordinate.
- **Licenza**: **ODC-BY** per le 60 stazioni EEA/EEA Italy (diversa da CC BY 4.0 di ARPA); **nessuna licenza dichiarata** per le 2 stazioni HabitatMap, **incluse comunque** nel dataset dal 01/10/2026 (decisione di Matteo) e segnalate a parte, v. `openaq/OpenAQ.md`.
- **Formato**: API REST (JSON), API key gratuita (header `X-API-Key`, chiave in `.env`, gitignored).
- **Codice**: `api/aria/openaq.py`
- **Ente**: OpenAQ (non-profit), dati di origine EEA/EEA Italy

---

## EEA — terza fonte, validazione (integrata il 28/09/2026)

**Cosa ci procuriamo**: serie **orarie** di CO, NO2, O3, PM2.5, SO2 e PM10 delle stazioni della rete ARPA trasmesse all'Agenzia Europea dell'Ambiente, da cui si calcola un valore al giorno: la media pesata sul tempo delle ore disponibili (decisione del 29/09/2026). Sono gli stessi dati di ARPA (e la fonte da cui li prende OpenAQ): la **ridondanza è voluta** e serve a **validare** ARPA e OpenAQ cella per cella (decisione di Matteo del 28/09/2026; confronto tra ogni coppia di fonti nella sezione 9 di ogni report).

- **Scheda completa**: `eea/EEA.md` (API, formato dei parquet, codici di validità, copertura, confronto con ARPA, completezza dell'E2a)
- **Servizio**: EEA Air Quality Download Service — API <https://eeadmz1-downloads-api-appservice.azurewebsites.net/swagger/index.html>, record di catalogo <https://sdi.eea.europa.eu/catalogue/srv/eng/catalog.search#/metadata/778ef9f5-6293-4846-badd-56a29c70880d>
- **Come si preleva**: **lista di URL** (`POST /ParquetFile/urls`) filtrata sulle stazioni del Salento, poi download dei soli parquet necessari (uno per stazione × inquinante), con cache in `data/raw/aria/eea/` (gitignored). Nessuna API key.
- **Copertura reale**: 33 stazioni (tutte già in ARPA); **E1a verificato 01/01/2013 → 31/12/2025, 2014 assente** (`NO_DATA`); **E2a non verificato 2026 → oggi**, con ore incomplete (medie su poche ore, completezza nella nota).
- **Licenza**: **CC BY 4.0** (politica di riuso EEA: citare sempre EEA come fonte).
- **Formato**: Apache Parquet (letto con `pyarrow`), una riga per ora, con codice di validità e di verifica.
- **Codice**: `api/aria/eea.py` (client), `api/aria/fonti/eea.py` (adattatore)
- **Ente**: European Environment Agency (EEA), dati della rete ARPA Puglia trasmessi dall'Italia con l'Air Quality e-Reporting

---

## Copernicus / CAMS — quarta fonte (integrata il 02/10/2026, licenze ADS da accettare)

**Cosa ci procuriamo**: concentrazioni **modellate** (non misurate) di CO, NO2, O3, PM2.5, SO2 e PM10 su griglia 0,1° (~10 km), orarie, da cui si calcola un valore al giorno per comune: **media oraria in UTC+1** (stessa regola di OpenAQ/EEA, completezza nella nota). Il valore di un comune è la **media pesata sull'area** delle celle che ne intersecano il confine (decisione del 02/10/2026, `api/comune/celle_comuni.py`; mapping in `copernicus_cams/Celle_Comuni.json`), registrato sotto una **stazione virtuale `CAMS-<id_comune>`**: così dà un valore anche agli **8 distretti senza stazioni ARPA**. Resta marcata come "modellata" e tenuta separata dalle fonti misurate; non entra nella media delle stazioni fisiche.

- **Scheda completa**: `copernicus_cams/Copernicus_CAMS.md` (dataset ADS, parametri di richiesta, copertura per anno, autenticazione, punti aperti)
- **Servizio**: Atmosphere Data Store (ADS) di Copernicus/ECMWF — <https://ads.atmosphere.copernicus.eu/>, client Python `cdsapi` (già in `pyproject.toml`)
- **Dataset usati**: `cams-europe-air-quality-reanalyses` (anni consegnati: validata o interim; copertura adottata dal 2016-01-01 perché CO e SO2 mancano nel 2013-2015) e `cams-europe-air-quality-forecasts` con `type=analysis` (anno in corso e ripiego dal 23/09/2023)
- **Licenza**: **CC-BY-4.0** (da citare con DOI, v. scheda)
- **Formato**: NetCDF/GRIB, richiesta via API con token personale (chiave in `.env` come `COPERNICUS_API_KEY`, gitignored, inserita il 28/09/2026). **Prima di scaricare**: accettare a mano le licenze dei due dataset dalla tab *Download* (finora l'ADS risponde 403 *required licences not accepted*).
- **Codice**: `api/aria/copernicus_cams.py` (client), `api/aria/fonti/cams.py` (adattatore), `api/comune/celle_comuni.py` (pesi cella → comune). **Collaudato solo con NetCDF sintetici**: nessun file reale scaricato
- **Ente**: Copernicus Atmosphere Monitoring Service (CAMS), implementato da ECMWF

---

## Altre fonti aria valutate ma non ancora integrate

Dettagli in `ricerca/`ricerca/03_Datasets_List.md` del repository Presentation del repository Presentation.

- **EEA AirBase (2004-2012)** — storico pre-Direttiva disponibile dallo stesso servizio EEA (`dataset: 3`), non usato: unità di misura non valorizzata e ARPA copre già dal 2012 (v. `eea/EEA.md`).
