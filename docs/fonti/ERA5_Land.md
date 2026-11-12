# Copernicus ERA5-Land — temperatura dell'aria (fonte primaria del calore)

Scheda della fonte, **documentata il 01/10/2026**. **Client scritto il 09/10/2026** (`api/calore/era5_land.py`, dataset CDS `derived-era5-land-daily-statistics`: media/massima/minima giornaliere già in UTC+1, un mese per richiesta ritagliato sul Salento; cache in `data/raw/calore/era5_land/`; download con `scripts/calore/scarica_era5_land.py`; endpoint `GET /api/calore/disponibilita` e `/api/calore/serie`). Cella → comune: media pesata sull'area sulle sole celle con dato; Corsano e Patù (solo celle marine) usano la cella di terra più vicina, con nota. **Provato su dati reali (luglio 2024)**: griglia 12×19, 57% mare, valori plausibili (massima media 33,6 °C). Condizioni d'uso del CDS e licenza del dataset accettate a mano.

- **Servizio**: Copernicus Climate Change Service (C3S), Climate Data Store (CDS).
- **Dataset**: *ERA5-Land hourly data from 1950 to present* — https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land
- **Licenza**: CC BY (licenza Copernicus; attribuzione obbligatoria — formula esatta da riportare in tesi).
- **Accesso**: API CDS con il pacchetto **`cdsapi`**, **già fra le dipendenze** del progetto (aggiunto per CAMS) e chiave **già presente** in `.env` come `COPERNICUS_API_KEY` (v. `Copernicus_CAMS.md`). Gratuito, senza quote di consumo → compatibile con il vincolo di gratuità (docs/Regole_dei_dati.md).

## 1. Che cosa dà

| Caratteristica | Valore |
|---|---|
| Variabile principale | `2m_temperature` (temperatura dell'aria a 2 m dal suolo), oraria |
| Risoluzione spaziale | **0,1° × 0,1°** (~9 km) su griglia regolare lat/lon |
| Copertura temporale | **gennaio 1950 → oggi − 6 giorni** (aggiornamento giornaliero, latenza misurata il 03/11/2026, v. §3) |
| Formato | NetCDF / GRIB, per riquadro geografico e intervallo di date |
| Variabili utili in più | umidità e vento a 2/10 m, radiazione, temperatura del suolo (non necessarie per l'MVP) |

**Derivati che calcoliamo noi**, per comune e per giorno: temperatura **media**, **massima**, **minima**; da queste, le **giornate di caldo estremo** e le **notti tropicali** (soglie ancora da decidere, v. §4).

## 2. Perché è la fonte primaria

- È l'unica fonte gratuita, senza quote e con **copertura di tutti i 146 comuni** del Salento su tutta la finestra del progetto (5-10 anni e oltre).
- Non richiede nuovi servizi, chiavi o dipendenze: il canale CDS è già predisposto.
- Dà una serie **giornaliera continua**, l'unica grana che permette di incrociare il caldo con i decessi comunali giornalieri ISTAT.

## 3. Limiti da dichiarare

- **È una rianalisi, non una misura**: valore modellato, assimilando osservazioni. Da presentare come tale in tesi e in dashboard, affiancandogli la validazione con le stazioni ARPA (2023-2024, v. `../arpa_meteo/ARPA_Meteo.md`).
- **~9 km di lato**: un comune piccolo sta dentro una sola cella e **più comuni condividono la stessa cella** → la temperatura non distingue il centro urbano dalla campagna. Per l'isola di calore in senso stretto serve la temperatura superficiale satellitare (Landsat, rimandata dopo l'MVP).
- **Latenza: 6 giorni, misurata il 03/11/2026.** Il catalogo CDS (`/api/catalogue/v1/collections/<dataset>`, campo `extent.temporal`), aggiornato lo stesso giorno, dichiara sia `reanalysis-era5-land` sia `derived-era5-land-daily-statistics` fino al **28/10/2026**; una richiesta reale delle massime del 25-31/10 (UTC+1, riquadro del Salento) ha restituito con valore **solo 25-28/10**. Ultimo giorno disponibile = **oggi − 6**, come la costante `LATENZA_GIORNI` del client, che quindi non chiede giorni che non esistono. Attenzione: **il CDS non dà errore** per i giorni non ancora pubblicati, li omette in silenzio; nel dataset restano `NO_DATA` («giorno non ancora in ERA5-Land»), non `NULL`. Una misura sola: se in futuro il catalogo restasse indietro di più giorni, basta alzare la costante.
- **Riquadro e volume**: un riquadro sul Salento (~`16,70 / 39,75 / 18,55 / 40,95`, lo stesso già usato per CAMS) a passo 0,1° sono poche centinaia di celle: volumi modesti, ma 24 ore × 365 giorni per anno vanno scaricate e aggregate (v. §4, variante con statistiche giornaliere già calcolate).

## 4. Punti da chiudere prima di scrivere il client

1. **Da cella a comune**: cella che contiene il centroide comunale, oppure media pesata sull'area di sovrapposizione con `data/territorio/confini/comuni_salento.geojson`. **Stesso problema già aperto per CAMS**: una sola regola per entrambi.
2. **Soglie di caldo**: soglia fissa (es. T max ≥ 35 °C, T min ≥ 20 °C) o percentile locale della serie del comune. V. `Lista_dataset_calore.md` §5.
3. **Variante giornaliera**: verificare `derived-era5-land-daily-statistics` sul CDS (statistiche giornaliere già calcolate): se copre media/massima/minima, evita di scaricare le 24 ore e riduce di molto i tempi.
4. **Fuso orario**: i file sono in UTC; il giorno del progetto è in **UTC+1**, come già deciso per ARPA ed EEA (docs/Regole_dei_dati.md). L'aggregazione giornaliera va fatta dopo la conversione.
5. **Celle sul mare**: la costa salentina è lunga; serve la maschera terra/mare di ERA5-Land (le celle marine sono prive di dato) per non attribuire a un comune costiero una cella senza valore → `NULL` con nota, non silenzio.
