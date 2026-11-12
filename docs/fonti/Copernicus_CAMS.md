# Copernicus / CAMS — Atmosphere Data Store (ADS)

Scheda di riferimento per il servizio dati, secondo la convenzione del repo: una cartella + un file `.md` per ogni servizio/fonte dati. **Stato al 02/10/2026: integrato come quarta fonte aria, ma non ancora scaricato nulla di reale.** Client `api/aria/copernicus_cams.py`, adattatore `api/aria/fonti/cams.py`, pesi cella → comune `api/comune/celle_comuni.py`; collaudati con NetCDF sintetici (ritaglio, pesi, fuso UTC+1, conversione del CO, generatore e report). La chiave in `.env` (`COPERNICUS_API_KEY`) è valida, ma l'ADS risponde **403 "required licences not accepted"** per entrambi i dataset usati: Matteo deve accettare le licenze dalla tab *Download* di `cams-europe-air-quality-reanalyses` e `cams-europe-air-quality-forecasts`. **Da fare al primo download reale:** controllare nomi di variabile/coordinate del NetCDF, dimensione e tempi di coda, passo e posizione delle celle (il mapping `Celle_Comuni.json` usa la griglia nominale con centri a xx,x5°).

**Scelte del 02/10/2026** (Matteo): CAMS entra tra le fonti; le celle si riportano ai comuni con la **media pesata sull'area** (peso = quota della superficie comunale dentro la cella; 10 comuni su 146 in una sola cella, mediana 3, massimo 11); nel dataset ogni comune ha una **stazione virtuale `CAMS-<id_comune>`**; prodotto = rianalisi europea per gli anni consegnati (validata, o interim), analisi europea per l'anno in corso e come ripiego dal 23/09/2023; copertura da 2016-01-01; valore giornaliero = media oraria in UTC+1 con la completezza nella nota. Il ritaglio sul Salento della rianalisi (che scarica tutta l'Europa, un mese per variabile) si fa in locale e in `data/raw/aria/copernicus_cams/` resta solo la fetta del Salento in parquet.

Tutto ciò che segue è stato verificato il 28/09/2026 sul catalogo pubblico dell'ADS (`https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections/<dataset>`, incluso il `form` e i `constraints` di ogni dataset, cioè i valori ammessi per i parametri di richiesta), salvo dove indicato "non verificato".

## Cos'è

**CAMS** (Copernicus Atmosphere Monitoring Service) è il servizio europeo sulla composizione dell'atmosfera, gestito da **ECMWF** per conto della Commissione Europea. I suoi dati si scaricano dall'**Atmosphere Data Store (ADS)**. Sono dati **modellati** (modelli di chimica-trasporto con assimilazione di osservazioni EEA e satellitari), non misure di stazione: coprono l'intero territorio su una griglia regolare, quindi danno un valore anche ai **8 distretti senza stazioni ARPA** (LE-53, LE-54, LE-56, LE-58, LE-59, LE-60, TA-01, TA-07 — v. `../arpa_puglia/Copertura_Distretti_ARPA.json`). Nel dataset aria vanno marcati come "modellati", distinti dai valori misurati di ARPA/OpenAQ.

## Link

- ADS (portale): <https://ads.atmosphere.copernicus.eu/>
- Guida all'API: <https://ads.atmosphere.copernicus.eu/how-to-api>
- Catalogo dataset: <https://ads.atmosphere.copernicus.eu/datasets>
- Catalogo in JSON (pubblico, senza chiave): `https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections`
- Client Python: `cdsapi` (PyPI) — v. sotto. Alternativa "incubating" indicata dalla guida: `ecmwf-datastores-client` (già installato come dipendenza di `cdsapi` 0.7.7).

## Autenticazione

- Account gratuito sull'ADS (creato da Matteo il 28/09/2026). Serve un **Personal Access Token**, visibile nel profilo dopo il login.
- Endpoint: `https://ads.atmosphere.copernicus.eu/api`.
- **Termini d'uso da accettare a mano, una volta per dataset**, dalla pagina del dataset (tab *Download*, in fondo al form): finché non sono accettati la richiesta API viene rifiutata. Va fatto per ogni dataset che si userà (licenza CC-BY, ma l'accettazione è comunque richiesta).
- **Come fornire la chiave.** `cdsapi` la legge, in quest'ordine, dalle variabili d'ambiente `CDSAPI_URL` e `CDSAPI_KEY` oppure dal file `~/.cdsapirc` (percorso cambiabile con `CDSAPI_RC`) — verificato leggendo `cdsapi/api.py` v0.7.7. Per coerenza con OpenAQ si userà `.env` (root, **gitignored**):
  ```
  CDSAPI_URL=https://ads.atmosphere.copernicus.eu/api
  CDSAPI_KEY=<personal-access-token>
  ```
  lanciando gli script con `uv run --env-file .env ...`. Nessuna chiave va scritta nel codice o nei `.md`.
- **Chiave salvata il 28/09/2026** da Matteo in `.env` come **`COPERNICUS_API_KEY`** (non `CDSAPI_KEY`): quando si scriverà il client, passarla esplicitamente a `cdsapi.Client(url=..., key=os.environ["COPERNICUS_API_KEY"])` oppure rinominarla in `CDSAPI_KEY`. Nessun download di prova ancora fatto.
- ~~28/09/2026: Copernicus/CAMS non entra per ora tra le fonti~~ — **superato il 02/10/2026**: entra (v. sopra). I punti ⏳ "cella → comune" e "stazione fittizia per cella" sono chiusi con la media pesata sull'area e la stazione virtuale per comune.
- Limiti di richiesta/coda: l'ADS mette le richieste in coda (i tempi dipendono dal carico) e applica limiti di dimensione per richiesta (costo calcolato lato server, endpoint `costing` nei link del catalogo). Valori precisi **non verificati** senza chiave — da rilevare al primo test.

## Client

Installato il 28/09/2026 con uv (non `pip`): `uv add "cdsapi>=0.7.7"` → `pyproject.toml` / `uv.lock` (cdsapi 0.7.7).

Uso base (stesso schema di tutti i dataset, `retrieve(dataset, richiesta, file_di_uscita)`):

```python
import cdsapi
client = cdsapi.Client()          # legge CDSAPI_URL / CDSAPI_KEY
client.retrieve("cams-europe-air-quality-forecasts", richiesta, "out.zip")
```

## Dataset ADS rilevanti per la qualità dell'aria

Sono 16 in tutto nell'ADS; questi sono quelli che contengono inquinanti di superficie. Gli altri (gas serra, emissioni, radiazione solare, incendi GFAS, forzanti radiativi) non riguardano gli inquinanti tracciati (CO, NO2, O3, PM2.5, SO2) e non sono stati approfonditi.

| Dataset (id) | Cosa contiene | Copertura temporale | Risoluzione | Adatto al progetto? |
|---|---|---|---|---|
| `cams-europe-air-quality-reanalyses` | Rianalisi annuali dell'aria in Europa, mediana di 11 modelli + osservazioni EEA | 2013 → 2024 validato, 2025 interim | 0,1° (~10 km), oraria | **Sì, candidato principale (storico)** |
| `cams-europe-air-quality-forecasts` | Analisi + previsioni giornaliere (4 giorni), stesso modello | 2023-09-23 → oggi (archivio mobile di ~3 anni) | 0,1° (~10 km), oraria | **Sì, candidato per l'aggiornamento quotidiano** |
| `cams-europe-air-quality-forecasts-optimised-at-observation-sites` | Previsioni ottimizzate (MOS) su **stazioni EEA/EIONET**, serie giornaliere | 2024-01-17 → oggi | per stazione | Forse: solo NO2, O3, PM10, PM2.5; per stazioni EEA (le stesse già viste da ARPA/OpenAQ) |
| `cams-global-reanalysis-eac4` | Rianalisi globale della composizione atmosferica | 2003 → 2025 | 3-oraria; risoluzione orizzontale non verificata | Copertura più lunga ma griglia più grossolana della europea |
| `cams-global-reanalysis-eac4-monthly` | Medie mensili di EAC4 | 2003 → 2025 | mensile | Solo per trend mensili di lungo periodo |
| `cams-global-atmospheric-composition-forecasts` | Previsioni globali (5 giorni, 2 volte al giorno) | 2015 → oggi | risoluzione orizzontale non verificata | Poco utile: c'è la versione europea a risoluzione maggiore |

Tutti i dataset elencati hanno licenza **CC-BY-4.0** (campo `license` del catalogo).

### 1. `cams-europe-air-quality-reanalyses` — rianalisi europee (storico)

- **DOI**: 10.24381/7cc0465a — pagina: <https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-reanalyses>
- **Tipi** (`type`): `validated_reanalysis` (osservazioni validate, rilasciata con circa 1 anno di ritardo) e `interim_reanalysis` (osservazioni non validate, prodotta per l'anno precedente). Aggiornamenti circa due volte l'anno. Ultimo aggiornamento del catalogo: 23/06/2026.
- **Parametri di richiesta** (dal `form`): `variable`, `model`, `level`, `type`, `year`, `month`. **Non c'è `area`, né `data_format`, né giorno/ora**: si scarica **un file NetCDF mensile con tutta l'Europa** (area 30°N–72°N, 25°O–45°E) e il ritaglio sul Salento va fatto **in locale** (es. con xarray/netCDF4, non ancora nelle dipendenze). Dimensione del file mensile: **non verificata**.
- **Variabili** (22): `ammonia`, `carbon_monoxide`, `formaldehyde`, `glyoxal`, `nitrogen_dioxide`, `nitrogen_monoxide`, `non_methane_vocs`, `ozone`, `particulate_matter_2.5um`, `particulate_matter_10um`, `dust`, `peroxyacyl_nitrates`, `sulphur_dioxide` e componenti del particolato (`pm2.5_ammonium`, `pm2.5_nitrate`, `pm2.5_sulphate`, `pm2.5_total_organic_matter`, `residential_elementary_carbon`, `total_elementary_carbon`, `secondary_inorganic_aerosol`, `pm10_sea_salt_dry`, `pm10_wildfires`). Concentrazioni in µg/m³.
- **Modelli** (`model`): `ensemble` (mediana dei modelli, il prodotto di riferimento) e i singoli modelli `chimere`, `dehm`, `emep`, `euradim`, `gemaq`, `lotos`, `match`, `minni`, `mocage`, `monarch`, `silam`.
- **Livelli** (`level`, metri sopra il suolo): `0` (superficie), 50, 100, 250, 500, 750, 1000, 2000, 3000, 5000. Per l'aria che respirano le persone serve `0`.
- **Disponibilità per anno** (dai `constraints`) — **importante per la finestra 2016-2026**:

  | Anni | Tipo | Variabili disponibili | Modelli | Livelli |
  |---|---|---|---|---|
  | 2013-2015 | validated | **solo** NO2, O3, PM10, PM2.5 (**mancano CO e SO2**) | solo `ensemble` | solo `0` |
  | 2016-2017 | validated | NO2, O3, PM10, PM2.5, **CO, SO2** | solo `ensemble` | solo `0` |
  | 2018 | validated | 12 variabili | 8 | 8 |
  | 2019 | validated | 13 | 9 | 8 |
  | 2020 | validated | 15 | 11 | 10 |
  | 2021 | validated | 17 | 12 | 10 |
  | 2022 | validated | 19 | 12 | 10 |
  | 2023-2024 | validated | 22 | 12 | 10 |
  | 2021-2025 | interim | 13-22 (2025: tutte e 22) | 9-12 | 8-10 |

  Nota: l'`interim` del 2024 per il solo modello `gemaq` non ha `carbon_monoxide`; per il 2024 esiste comunque la versione `validated`.
- **Conseguenze**: per i 5 inquinanti tracciati (CO, NO2, O3, PM2.5, SO2) la serie completa parte dal **2016**; nel 2013-2015 CO e SO2 non esistono (→ `NO_DATA` nel dataset). L'anno 2025 è solo `interim` (non validato), da marcare come tale.
- **Statistica giornaliera**: i file sono orari; per confrontarli con ARPA/OpenAQ vanno ricalcolati con la stessa statistica giornaliera ARPA (v. `../arpa_puglia/Parametri_Qualita_Aria.md` e `../openaq/OpenAQ.md`: media giornaliera per PM; massimo orario per NO2/O3/SO2; massimo della media mobile su 8 h per CO).

### 2. `cams-europe-air-quality-forecasts` — analisi e previsioni europee (aggiornamento quotidiano)

- **DOI**: 10.24381/a4005cee — pagina: <https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts>
- **Contenuto**: per ogni giorno, un'*analisi* (modello + osservazioni EEA) e una *previsione* a 4 giorni (una volta al giorno; disponibile alle 06:45 UTC per 0-48 h e alle 08:30 UTC per 49-96 h).
- **Parametri di richiesta**: `variable`, `model`, `level`, `date` (intervallo `AAAA-MM-GG/AAAA-MM-GG`), `type` (`analysis` | `forecast`), `time` (`00:00`…`23:00`), `leadtime_hour` (0…96), `data_format` (`grib` | `netcdf_zip`), `area` (**sotto-regione**: `[Nord, Ovest, Sud, Est]`, passo 0,01°). Qui il ritaglio si può fare **direttamente nella richiesta**.
- **Variabili** (28): le stesse della rianalisi più i pollini (`alder`, `birch`, `grass`, `mugwort`, `olive`, `ragweed`). Formato NetCDF: µg/m³; GRIB: kg/m³ (conversione necessaria).
- **Validazione**: solo NO, NO2, SO2, O3, PM2.5, PM10 e polveri (dust) sono validati regolarmente contro le osservazioni in situ; **tutte le altre variabili sono sperimentali** (dichiarato da CAMS).
- **Copertura**: dalla forma `date` del catalogo, dal 2023-09-23 a oggi (archivio mobile di ~3 anni: i giorni più vecchi escono dal catalogo). **Non è quindi uno storico**: per il 2016-2023 serve la rianalisi. Per i giorni recenti (oltre l'ultimo anno validato) è l'unica fonte europea a 0,1°.
- Ai fini della pipeline usare `type=analysis` (stima del valore *attuale*, con assimilazione) e non `forecast`, che è una previsione.

### 3. `cams-europe-air-quality-forecasts-optimised-at-observation-sites`

- **DOI**: 10.24381/2cce4067. Serie giornaliere previste su centinaia di stazioni EEA, per NO2, O3, PM10, PM2.5, filtrabili per `country` (`italy`), con `type` `raw` | `mos_optimised`, `leadtime_hour` in blocchi da 24 h, `year`/`month`/`day`, e opzione `include_station_metadata=yes` (lat/lon/altitudine/tipo di ambiente, con gli identificativi EIONET).
- È una **previsione**, non una misura né un'analisi: potrebbe servire solo come confronto, non come fonte del dataset. Non copre CO e SO2. Non approfondito ulteriormente.

### 4-6. Dataset globali (EAC4, EAC4 mensile, previsioni globali)

- `cams-global-reanalysis-eac4` (DOI 10.24381/d58bbf47): 3-orario (00:00, 03:00, …), livelli a pressione (25) e a modello (60), variabili come array (elenco non estratto), `area` selezionabile. 2003 → 2025. Risoluzione **non verificata** (non compare nella descrizione).
- `cams-global-reanalysis-eac4-monthly` (DOI 10.24381/fd75fff2): come sopra ma medie mensili (`monthly_mean`, `monthly_mean_by_hour_of_day`).
- `cams-global-atmospheric-composition-forecasts` (DOI 10.24381/04a0b097): previsioni a 5 giorni, `time` 00:00/12:00, 2015 → oggi.
- Tenuti solo come **riserva**: la griglia globale è più grossolana di quella europea e per il progetto la rianalisi europea (storico) + le analisi europee (giorni recenti) coprono già l'intero periodo.

## Area di interesse: Salento

- Bounding box già usata per OpenAQ (`BBOX_SALENTO` in `api/aria/openaq.py`): lon 16,70–18,55, lat 39,75–40,95. Nel formato `area` dell'ADS (Nord, Ovest, Sud, Est): `[40.95, 16.70, 39.75, 18.55]`.
- Su una griglia da 0,1° sono circa **19 × 12 ≈ 230 celle** (stima, da verificare sul primo file reale). Ogni comune/distretto andrà associato alla cella (o alle celle) che lo contengono usando i confini in `data/territorio/confini/comuni_salento.geojson`; come si passa da celle a comune: **deciso il 02/10/2026**, media pesata sull'area (`api/comune/celle_comuni.py`, mapping in `Celle_Comuni.json`).
- Il modello non "vede" i singoli comuni: a 10 km molti comuni cadono nella stessa cella. Va dichiarato in tesi: valore modellato ≈ fondo regionale, non l'esposizione locale (es. vicino a una strada o a un impianto).

## Licenza

**CC-BY-4.0** ("CC-BY licence", <https://spdx.org/licenses/CC-BY-4.0>) per tutti i dataset elencati; richiede l'attribuzione. Citazione richiesta da CAMS: usare i DOI sopra (per le rianalisi europee: 10.24381/7cc0465a; per analisi/previsioni europee: 10.24381/a4005cee) e la dicitura standard Copernicus indicata nella pagina del dataset (tab *Overview → Citation*, da copiare al momento della citazione). Da aggiungere a `Bibliografia.md` del repository Presentation quando si userà il dato.

## Limiti e punti aperti

- **Dato modellato, non misurato**: incertezza e bias rispetto alle stazioni; i valori CAMS non vanno mai mescolati con quelli ARPA/OpenAQ (v. docs/Regole_dei_dati.md: un valore per fonte, la fonte va segnalata come "modellata").
- **CO e SO2 assenti nel 2013-2015** della rianalisi europea; **2025 non validato** (`interim`).
- **Nessun dato a livello di stazione** nella rianalisi/analisi: il dato è per cella. Nel dataset aria la gerarchia è provincia → distretto → comune → **stazione** → giorno → fonte → inquinante: **deciso il 02/10/2026**: una stazione virtuale `CAMS-<id_comune>` per comune, con il valore della media pesata sull'area; non entra nella media delle stazioni fisiche.
- **Rianalisi senza `area`**: ogni richiesta mensile scarica tutta l'Europa; dimensione e tempi in coda **non verificati** (servirà la chiave). Da valutare la cache locale in `data/raw/aria/copernicus_cams/` (gitignored) per non riscaricare gli stessi mesi.
- **Statistica giornaliera e fuso orario**: i file sono in UTC; il giorno locale (Europa/Roma) va ricostruito prima di calcolare la statistica giornaliera.
- **Dipendenze** per leggere i file e fare l'intersezione con i confini: `xarray`, `netcdf4`, `shapely` — **aggiunte il 02/10/2026** (`uv add`). Il formato GRIB non è gestito: si richiede sempre NetCDF.
- Da verificare al primo test con la chiave: dimensione/tempo di risposta, limiti di richiesta, formato esatto delle variabili nel NetCDF (nomi delle variabili, dimensioni, unità).
