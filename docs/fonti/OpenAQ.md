# OpenAQ

Scheda di riferimento per il servizio dati, creata secondo la convenzione del repo: una cartella + un file `.md` per ogni nuovo servizio/fonte dati integrato, con link al servizio, alla documentazione, alle API e alle licenze.

## Cos'è

OpenAQ è un aggregatore no-profit di dati di qualità dell'aria. Per l'Italia/Puglia i dati che aggrega provengono da **EEA** (European Environment Agency), che a sua volta riceve i dati dalla rete regionale ARPA: le stazioni viste da OpenAQ nel Salento hanno **nomi e coordinate sovrapponibili** a quelli della rete RRQA di ARPA Puglia già censita in `data/dataset/aria/arpa_puglia/`. Non è quindi una fonte primaria alternativa ad ARPA, ma un secondo canale di accesso agli stessi dati, con una copertura temporale diversa (v. sotto).

## Link

- Sito: <https://openaq.org/>
- Documentazione API v3: <https://docs.openaq.org/>
- Explorer (interfaccia web, anche per registrarsi): <https://explore.openaq.org/>
- Registrazione API key: <https://explore.openaq.org/register>
- Gestione API key: <https://explore.openaq.org/account>
- Riferimento endpoint (reference, generato da OpenAPI): <https://docs.openaq.org/api/operations/locations_get_v3_locations_get>

## Autenticazione

- API key gratuita, ottenuta via registrazione (link sopra).
- Va passata **solo come header** `X-API-Key: <chiave>` (i query param non sono supportati).
- La chiave del progetto è in `.env` (root, **gitignored**), variabile `OPENAQ_API_KEY`. Nessuna chiave è hardcoded nel codice.
- **Rate limit (free tier)**: 60 richieste/minuto, 2.000/ora (HTTP 429 se superato).

## API usate (v3)

- `GET /v3/locations` — anagrafica stazioni. Query geospaziale con `bbox=minLon,minLat,maxLon,maxLat` **oppure** `coordinates=lat,lon&radius=<metri, max 25000>` (non combinabili tra loro). Bbox usata per il Salento: `16.70,39.75,18.55,40.95` (`BBOX_SALENTO` in `api/aria/openaq.py`).
- `GET /v3/sensors/{sensors_id}/days` — aggregati giornalieri per un sensore (= una stazione + un parametro), con `date_from`/`date_to`.
- `GET /v3/parameters` — anagrafica inquinanti (id, nome, unità di misura).
- `GET /v3/licenses` — anagrafica licenze applicate ai dati (v. sotto).
- Client: `api/aria/openaq.py`.

### Parametri di riferimento (id in µg/m³)

OpenAQ espone più `id` per lo stesso inquinante a seconda dell'unità (mass in µg/m³ vs. concentrazione in ppm/ppb). Per confrontare/unire con ARPA (che pubblica in µg/m³) si usano sempre gli id "mass":

| Inquinante | id OpenAQ (µg/m³) |
|---|---|
| PM2.5 | 2 |
| O₃ | 3 |
| CO | 4 |
| NO₂ | 5 |
| SO₂ | 6 |

(PM10 = id 1, non nell'elenco di riferimento dashboard ma disponibile.)

## Licenza

Verificato il 27/09/2026 interrogando `licenses[]` sulle 62 stazioni trovate nel bbox del Salento:

- **60 stazioni** (provider `EEA` / `EEA Italy`, id 70/186): licenza **ODC-BY** (Open Data Commons Attribution License), attribuzione dichiarata a "Unknown Governmental Organization" (il dato di attribuzione puntuale al singolo ente non è popolato lato OpenAQ — da tenere a mente se serve citare la fonte originale in tesi).
- **2 stazioni** ("egdp-6", "egdp-7", provider `HabitatMap`, id 200): **nessuna licenza dichiarata** in risposta API. Non fanno parte della rete regolatoria EEA/ARPA, ma **incluse comunque** (decisione di Matteo del 01/10/2026) — v. nota sotto.

**Nota bene**: ODC-BY è una licenza diversa da CC BY 4.0 (quella assunta per i dataset ARPA su dati.puglia.it, v. `data/dataset/aria/arpa_puglia/`). Compatibili entrambe con riuso e citazione in tesi con attribuzione, ma **da citare correttamente ciascuna con il proprio nome** in `Bibliografia.md` del repository Presentation quando si userà OpenAQ nella pipeline. Le 2 stazioni HabitatMap **non hanno nessuna licenza da citare** (nessuna dichiarata): vanno segnalate in tesi come dato citizen-science senza licenza, non equiparate alle altre 60.

## Copertura verificata per il Salento (27/09/2026)

- **62 stazioni** nel bbox delle tre province (Lecce, Brindisi, Taranto), quasi tutte con nome/coordinate riconducibili alla rete RRQA ARPA già nota (`stazioni_di_monitoraggio.json`).
- **Copertura temporale reale confermata con dati veri** (non solo metadata): es. NO₂ orario/giornaliero per Lecce–S.M. Cerrate disponibile per **gennaio 2021**. La maggior parte delle 60 stazioni EEA/EEA Italy copre **2020-05-06 → oggi**.
- **Ruolo nel progetto (aggiornato 27/09/2026)**: quando è stata verificata, OpenAQ era l'unica via per gli anni che il mirror CKAN di ARPA non copriva (2019-2022, 2024-oggi). Da quando ARPA è raggiungibile anche su `old.arpa.puglia.it` con copertura 2012 → oggi (v. `Lista_dataset_aria.md`), OpenAQ non serve più a coprire buchi temporali: resta la **seconda fonte indipendente** del dataset aria, con valori tenuti separati da quelli ARPA.
- **2019 non coperto** neanche da OpenAQ (la copertura parte dal 2020-05-06 per la quasi totalità delle stazioni).
- **Split di id dal 01/06/2026**: le stazioni storiche (es. id `8378` "LECCE - S. M. Cerrate") terminano intorno al 03/06/2026 e vengono sostituite da nuovi id (es. `6387781` "Lecce - S.M. Cerrate", stessa posizione, nomi ripuliti) attivi da allora. Per una serie continua serve riconciliare vecchio/nuovo id per nome+coordinate, non basta l'id.
- **Le 2 stazioni HabitatMap** ("egdp-6"/"egdp-7", solo PM2.5) non hanno `datetimeFirst`/`datetimeLast` popolati e nessuna licenza dichiarata: sensori di tipo citizen-science, non regolatori. **Incluse comunque nel dataset dal 01/10/2026** (decisione di Matteo), segnalate in `note["stazioni_senza_licenza"]` dell'adattatore e nella sezione 7 del report — senza affidabilità/licenza equivalenti alle altre 60, da trattare con cautela in tesi.

## Uso nel dataset aria (27/09/2026)

Adattatore: `api/aria/fonti/openaq.py`. Scelte di metodo, da citare in tesi:

- **Stazioni HabitatMap incluse** *(decisione di Matteo, 01/10/2026)*: le 2 stazioni "egdp-6"/"egdp-7" (provider `HabitatMap`, nessuna licenza dichiarata) non sono più escluse ma trattate come le altre 60: stesso abbinamento, stessa logica di valore giornaliero. Restano segnalate in `note["stazioni_senza_licenza"]` per non equipararle in tesi alle stazioni EEA/EEA Italy con licenza ODC-BY.
- **Abbinamento alle stazioni ARPA** (nel dataset la stazione sta sopra la fonte; regole in `api/aria/fonti/abbinamento.py`, condivise con EEA dal 28/09/2026): una location OpenAQ prende la chiave della stazione ARPA più vicina se questa è entro **250 m**, o entro **1 km** se il comune ARPA compare nel nome/locality OpenAQ (es. "brindisi SISRI" a 557 m). Altrimenti resta una stazione a sé (`OpenAQ-<id>`), ricondotta al distretto solo se il nome contiene un comune (es. "Surbo ENEL"); se no è segnalata come non assegnabile. Così anche vecchi e nuovi id della stessa stazione (split di giugno 2026) finiscono sotto la stessa chiave.
- **Un solo valore al giorno per inquinante** *(decisione di Matteo del 29/09/2026, uguale per EEA)*: **media pesata sul tempo** di tutte le misure valide del giorno (`/measurements`), **senza soglia minima di ore**; la nota della cella riporta la completezza (`media pesata sul tempo su n/24 ore`). Giorno `NULL` solo se nessuna misura è valida. CO convertito da µg/m³ a mg/m³ come ARPA. Fino al 28/09/2026 si usava invece la statistica di ARPA (massimo orario per NO2/O3/SO2, media mobile 8 h per il CO) con soglia del 75%.
- **Giorni in UTC+1** (ora solare fissa, come ARPA ed EEA), ricavati dall'orario `utc` delle misure; l'aggregato `/days` (che ragiona in ora locale, UTC+2 d'estate) serve solo a controllare in fretta se il sensore ha dati nel periodo. Attenzione: gli orari OpenAQ stessi sono sfasati (v. sotto).
- **Sensori senza dati nel periodo**: l'elenco delle location non riporta le date dei singoli sensori (es. il PM10 di Arnesano esiste solo da febbraio 2026). Un inquinante conta come misurato dalla stazione solo se il sensore restituisce almeno un dato nel periodo; altrimenti è `NO_DATA`.
- **Endpoint per i dati orari**: `/sensors/{id}/measurements`, non `/sensors/{id}/hours`. Il 27/09/2026 `/hours` andava in timeout (408) anche su 7 giorni e proprio sui periodi vuoti, mentre `/measurements` risponde in pochi secondi su un mese. `datetime_to` è un istante: per includere l'ultimo giorno si passa la mezzanotte successiva.

## Anomalia rilevata dalla validazione con EEA (28-29/09/2026)

Nel primo report a tre fonti (giugno 2024, statistica ARPA) ARPA ed EEA concordavano al 99,9-100%, mentre OpenAQ solo al 56,7% sull'NO2 (80-91% sugli altri inquinanti), con picchi spostati di un giorno (es. Brindisi – Perrino, NO2: ARPA/EEA 86 l'8/06, OpenAQ 86,48 il 9/06).

**Causa, verificata il 29/09/2026 confrontando ora per ora le misure OpenAQ (`/measurements`) con i parquet EEA della stessa stazione** (NO2, Brindisi – Perrino e Lecce – S.M. Cerrate): i **valori** orari OpenAQ sono identici a quelli EEA, ma l'**orario** è sfasato di un numero di ore che **cambia nel tempo**. Sfasamento con cui il 100% delle ore coincide (ora UTC+1 di EEA = orario `utc` di OpenAQ + sfasamento):

| Serie OpenAQ | Periodo | Sfasamento | Ore identiche |
|---|---|---|---|
| id vecchi (fino a maggio 2026) | gennaio 2024 | +0 h | 100% |
| id vecchi | giugno 2024 | −2 h | 100% |
| id vecchi | agosto 2025 | −2 h | 100% |
| id vecchi | dicembre 2025, febbraio 2026 | −1 h | 100% |
| id vecchi | maggio 2026 | +0 h | 100% |
| id vecchi | fine marzo 2023 (cambio d'ora) | metà 0 h, metà −1 h | ~50% |
| id vecchi | dicembre 2020, luglio 2021 | nessuno sfasamento fa coincidere i valori | ~1% |
| id nuovi (da giugno 2026) | settembre 2026 | +0 h | 100% |

Quindi: (1) la sola conversione in UTC+1 non basta, perché è l'orario `utc` dichiarato da OpenAQ a essere sbagliato; (2) lo sfasamento **non segue una regola fissa** (non è solo ora legale/solare); (3) nel 2020-2021 i valori OpenAQ non sono quelli verificati EEA (probabilmente dati provvisori mai aggiornati). Con la media giornaliera l'effetto è più piccolo che con il massimo orario (1-2 ore su 24 finiscono nel giorno sbagliato), ma resta.

Oggi l'adattatore converte fedelmente l'orario dichiarato (UTC → UTC+1) senza correzioni empiriche. ⏳ Come trattare lo sfasamento è da decidere con Matteo.

## Limiti

- È un aggregatore, non fonte primaria: in caso di discordanza con ARPA sullo stesso periodo, la fonte diretta resta il riferimento (entrambi i valori vanno comunque conservati, v. docs/Regole_dei_dati.md).
- Non copre il 2019.
- Completezza per riga (`coverage.percentComplete` in `/sensors/{id}/days`) è variabile (osservato 4%-88% nello stesso mese per la stessa stazione): nel dataset la completezza di ogni giorno è nella nota (`su n/24 ore`).
- **Orari sfasati** di 0-2 ore rispetto a EEA/ARPA, in modo variabile nel tempo (v. sopra). **Decisione di Matteo del 06/11/2026**: non si correggono, si converte fedelmente l'orario dichiarato; limite noto da dichiarare in tesi.
- **Buchi per inquinante**: a giugno 2024 OpenAQ non ha **nessun dato CO** per le stazioni del Salento (ne ha da gennaio 2025) e quasi nessun PM10.
- **Cambio di unità dentro la stessa serie**: il CO di Terminal Passeggeri (sensore 24710) a maggio 2026 passa da valori come 175 a 0,0156 — probabilmente da µg/m³ a mg/m³ a ridosso dello split di id di giugno 2026, senza che l'unità dichiarata cambi. **Decisione di Matteo del 01/10/2026**: lasciare così com'è, senza aggiungere un controllo di coerenza di scala a monte.
