# Attribuzioni e licenze

Il codice di questo repository ha la propria licenza (v. `LICENSE`). I **dati** che il codice scarica e i **file di riferimento** versionati qui appartengono ai loro enti, con le licenze sotto elencate: l'attribuzione è richiesta anche se il repository ha un'altra licenza. Il repository **non contiene dati scaricati**; chi lo usa li scarica da sé dalle fonti (v. il README, sezione «Dati»). Le schede tecniche di ogni fonte stanno in [`docs/fonti/`](docs/fonti/).

Il confronto con i valori limite usa D.Lgs. 155/2010, le linee guida OMS 2021 e la direttiva (UE) 2024/2881.

## Fonti interrogate dal codice

| Fonte | Ente | Cosa si preleva | Licenza | Note |
|---|---|---|---|---|
| Rete regionale di rilevamento della qualità dell'aria (RRQA), API open data | ARPA Puglia | misure giornaliere di qualità dell'aria, anagrafica delle stazioni | CC BY 4.0 (assunzione, v. nota 1) | host `old.arpa.puglia.it`, non documentato |
| Air quality data | OpenAQ (dati di origine EEA / EEA Italy) | misure orarie di qualità dell'aria | ODC-BY per le stazioni EEA; nessuna licenza dichiarata per le stazioni HabitatMap (incluse e segnalate) | richiede una chiave gratuita |
| Air Quality Download Service (Air Quality e-Reporting) | European Environment Agency (EEA) | serie orarie delle stazioni del Salento (parquet) | CC BY 4.0, politica di riuso EEA | citare sempre EEA |
| CAMS European air quality reanalyses (DOI 10.24381/7cc0465a) e forecasts (DOI 10.24381/a4005cee) | Copernicus Atmosphere Monitoring Service, ECMWF | concentrazioni **modellate** su griglia 0,1° | CC BY 4.0 | licenze da accettare a mano sull'ADS |
| ERA5-Land, statistiche giornaliere (`derived-era5-land-daily-statistics`) | Copernicus Climate Change Service, ECMWF | temperatura dell'aria a 2 m | licenza Copernicus (CC BY), attribuzione obbligatoria | licenza da accettare a mano sul CDS |
| Rete meteo, dati aperti | ARPA Puglia | temperatura misurata (CSV su `dati.arpa.puglia.it`) | CC BY 4.0 (v. nota 1) | |
| Decessi comunali giornalieri; bilancio demografico mensile; cause di morte (SDMX); Health for All | ISTAT | decessi per comune × giorno (tutte le cause), morti per comune × mese, dimissioni per provincia × anno | CC BY 4.0 | |
| `demo_r_mwk3_t` (decessi per NUTS 3 e settimana) | Eurostat | validazione dei decessi ISTAT | CC BY 4.0 | |
| Dati aperti | Regione Puglia, `dati.puglia.it` (CKAN) | riscontro indipendente del 2023 per l'aria | CC BY 4.0 | |

## File di riferimento versionati nel repository

Non sono misure: descrivono il territorio e le reti che la pipeline usa come chiavi.

| File | Origine | Licenza |
|---|---|---|
| `data/territorio/confini/*.geojson` | confini comunali ISTAT, semplificati, dal repository openpolis/geojson-italy | licenza di ISTAT / openpolis: **da verificare** prima della pubblicazione (v. nota 2) |
| `data/territorio/lista_presidi/*.json`, `data/territorio/anagrafica/territorio.json` | Regione Puglia, «Anagrafe distretti socio-sanitari» (distretti e comuni); residenti di origine ISTAT, da comuni-italiani.it | IODL 2.0 per l'anagrafe dei distretti; per i residenti v. nota 2 |
| `data/dataset/aria/anagrafica/*.json`, `data/dataset/aria/arpa_puglia/*.json` | anagrafica di stazioni e inquinanti di ARPA Puglia; copertura dei distretti calcolata dal progetto | CC BY 4.0 (v. nota 1) |
| `data/dataset/aria/copernicus_cams/Celle_Comuni.json` | pesi cella CAMS → comune calcolati dal progetto (sola geometria) | — |
| `data/dataset/calore/clms/mitigazione_comuni.json` e le colonne derivate in `territorio.json` | copertura arborea (Tree Cover Density 2024, `CLMS_HRLVLCC_TCD_ITF4_0`) e suolo impermeabile (Imperviousness Density 2018 v020), Copernicus Land Monitoring Service, media dei pixel per comune | accesso libero e gratuito (Reg. delegato UE 1159/2013), con obbligo di citare la fonte e dichiarare le modifiche |

## Mappa

I tile della dashboard sono di OpenStreetMap: © OpenStreetMap contributors, dati ODbL ([copyright](https://www.openstreetmap.org/copyright)).

## Note

1. La guida ufficiale di ARPA Puglia non dichiara una licenza per l'API; si assume la stessa **CC BY 4.0** dei dataset ARPA pubblicati su `dati.puglia.it`. È un'assunzione dichiarata, non una conferma dell'ente.
2. Per i confini ISTAT/openpolis e per i residenti di comuni-italiani.it (© Prometheo, dati di origine ISTAT) la licenza di riuso non è stata verificata: i residenti sono sostituibili con quelli diretti ISTAT (CC BY 4.0).
