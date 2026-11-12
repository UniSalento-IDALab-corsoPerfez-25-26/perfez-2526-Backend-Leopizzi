# EEA — Air Quality Download Service

Scheda di riferimento per il servizio dati, secondo la convenzione del repo: una cartella + un file `.md` per ogni servizio/fonte dati. **Stato al 28/09/2026: integrato** come terza fonte del dataset aria (decisione di Matteo del 28/09/2026), con accesso tramite **lista di URL** (strada A sotto). Client `api/aria/eea.py`, adattatore `api/aria/fonti/eea.py`. Il ruolo è la **validazione incrociata** di ARPA e OpenAQ (v. "Ridondanza come validazione").

Tutto ciò che segue è stato **verificato il 28/09/2026 con chiamate reali** all'API e scaricando i parquet delle stazioni salentine (script di prova nello scratchpad, non nel repo), salvo dove indicato "non verificato".

## Cos'è

L'**EEA** (European Environment Agency) raccoglie le misure di qualità dell'aria che ogni Stato membro è obbligato a trasmettere (flussi *Air Quality e-Reporting*, Direttiva 2008/50/CE). Per la Puglia il dato **nasce dalla rete RRQA di ARPA Puglia** (reti "REGIONE PUGLIA", "PROVINCIA DI LECCE/BRINDISI/TARANTO", "COMUNE DI LECCE", "RETE SIMAGE", ENEL Brindisi...): è quindi la **fonte a monte di OpenAQ** (che la ridistribuisce) e un canale ufficiale europeo verso gli stessi dati di ARPA, con alcune differenze utili (v. "Confronto con ARPA").

Tre dataset rilevanti:

| `dataset` (API) | Nome | Contenuto | Periodo verificato (Salento) |
|---|---|---|---|
| **1** | **E2a / UTD** (*Up-To-Date*) | dati **non verificati**, trasmessi in continuo | **01/01/2026 → oggi** (aggiornato in giornata: ultima ora disponibile il 28/09 alle 15:00) |
| **2** | **E1a** | dati **verificati**, consegnati dagli Stati entro il 30/09 di ogni anno per l'anno precedente | **01/01/2013 → 31/12/2025** (⚠️ **2014 assente** per tutta l'Italia, non solo per il Salento) |
| **3** | **AirBase** | storico pre-Direttiva 2008/50/CE | 2004 → 2012 (unità di misura non valorizzata) |
| 4 | CAMS *downscaled* a livello di stazione | previsione CAMS riportata sulle stazioni | **nessun file per l'Italia** |
| 5 | E2a *gap-filled* | E2a con buchi riempiti (interpolazione lineare / regressore su stazioni simili) | 2026, per il Salento **solo SO2 e CO** scaricabili (gli altri URL restituiscono 404) |

> Nota: la guida ufficiale (v. 1.2, maggio 2026) descrive l'E1a come "2013-2022" e l'E2a "dall'inizio del 2023", ma i file reali oggi contengono E1a fino al 2025 ed E2a solo per il 2026: quando un anno viene verificato passa da E2a a E1a. Il confine tra i due si sposta quindi ogni anno (a fine settembre).

## Link

- Pagina del catalogo (record trovato da Matteo): <https://sdi.eea.europa.eu/catalogue/srv/eng/catalog.search#/metadata/778ef9f5-6293-4846-badd-56a29c70880d> — "Air Quality download service", metadati ISO in XML: `https://sdi.eea.europa.eu/catalogue/srv/api/records/778ef9f5-6293-4846-badd-56a29c70880d/formatters/xml`
- Web app di download: <https://eeadmz1-downloads-webapp.azurewebsites.net/>
- API (Swagger): <https://eeadmz1-downloads-api-appservice.azurewebsites.net/swagger/index.html> — spec JSON: `.../swagger/v1/swagger.json` ("Parquet downloads API" v1, **senza descrizioni** degli endpoint: il significato è nella guida PDF)
- Guida ufficiale "How to use Air Quality Downloads" (PDF, v. 1.2 del 05/05/2026): <https://eeadmz1-downloads-webapp.azurewebsites.net/content/documentation/How_To_Downloads.pdf>
- Anagrafica stazioni/punti di campionamento (metadati, non misure): <https://discomap.eea.europa.eu/App/AQViewer/index.html?fqn=Airquality_Dissem.b2g.measurements> — download CSV diretto: `https://discomap.eea.europa.eu/App/AQViewer/download?fqn=Airquality_Dissem.b2g.measurements&f=csv` (ZIP con `DataExtract.csv`, ~4 MB, 187.899 righe × 70 colonne, tutta Europa)
- Vocabolari Eionet (codici usati nei parquet): inquinanti <https://dd.eionet.europa.eu/vocabulary/aq/pollutant>, validità <https://dd.eionet.europa.eu/vocabulary/aq/observationvalidity>, verifica <https://dd.eionet.europa.eu/vocabulary/aq/observationverification>, tipo di osservazione <https://dd.eionet.europa.eu/vocabulary/aq/primaryObservation>, unità <https://dd.eionet.europa.eu/vocabulary/uom/concentration> (tutti scaricabili aggiungendo `/csv` all'URL)
- Politica di riuso EEA: <https://www.eea.europa.eu/en/legal-notice>

## Licenza

- **CC BY 4.0** secondo la politica di riuso EEA ("may be re-used without prior permission, free of charge, for commercial or non-commercial purposes, provided that the EEA is always acknowledged as the original source"). Citare sempre **EEA come fonte**.
- Il record del catalogo non riporta una licenza propria (nessun campo licenza/vincoli nell'XML ISO del 28/09/2026): vale la politica generale EEA.
- Nessuna registrazione né API key: l'API è pubblica. Campo `email` facoltativo nelle richieste (l'EEA lo chiede per contattare l'utente in caso di problemi; **non va messo nel codice**, eventualmente in `.env`).

## Come accedere senza scaricare l'intero dataset

Il parquet "intero" che si scarica dalla pagina del catalogo **non è l'unica via**. L'API permette di scegliere paese, città, inquinante, dataset e periodo, e comunque i dati sono salvati **un file parquet per punto di campionamento** (= una stazione × un inquinante × un metodo di misura), che si può scaricare singolarmente. Tre strade, dalla più alla meno consigliata per noi:

### A. Lista di URL + download dei soli file salentini (scelta, usata dal client)

1. `POST /ParquetFile/urls` → CSV con una colonna `ParquetFileUrl`, un URL per punto di campionamento:
   ```json
   {"countries": ["IT"], "cities": [],
    "pollutants": ["CO", "NO2", "O3", "PM2.5", "SO2", "PM10"],
    "dataset": 2, "source": "API"}
   ```
   Risposta istantanea: ~2.100 URL per l'Italia con `dataset: 1`, ~3.000 con `dataset: 2`, ~3.560 con `dataset: 3`.
2. Si filtrano gli URL per **codice stazione EoI** contenuto nel nome del file (`SPO.IT1665A_8_chemi_2004-05-01_00_00_00.parquet` → stazione `IT1665A`, inquinante `8` = NO2) tenendo solo le stazioni del Salento (v. "Anagrafica").
3. Si scarica ogni file con un semplice `GET` (Azure Blob pubblico, nessuna autenticazione): `https://eeadmz1batchservice02.blob.core.windows.net/airquality-p-e1a/IT/SPO....parquet` (container `airquality-p` per E2a, `airquality-p-e1a` per E1a, `airquality-p-airbase` per AirBase, `airquality-p-extended` per il gap-filled).

Dimensioni reali per il Salento (6 inquinanti tracciati, 33 stazioni): **E1a 2013-2025 = 121 file, 128 MB**; **E2a 2026 = 114 file, 19 MB**; AirBase 2004-2012 = 73 file, 31 MB. Ogni file contiene **l'intera serie** del punto di campionamento (i filtri di data sono ignorati da questo endpoint, lo dice la guida): i file E1a pesano ~1 MB, quelli E2a ~150 KB. È la strada indicata dalla guida come **la più stabile**.

I file sono organizzati in *row group* (es. 22 per una serie oraria 2013-2025), quindi in teoria si potrebbe leggere solo una parte del file via HTTP range (pyarrow + fsspec); con file da ~1 MB non conviene.

### B. `POST /ParquetFile` con filtro di periodo (per richieste piccole)

Restituisce subito uno ZIP con i parquet **già ritagliati sul periodo** (cartelle `E1a/` o `E2a/` nello ZIP). Esempio verificato: Lecce, NO2 + PM10, giugno 2024 → **26 KB** in meno di 1 s.

```json
{"countries": ["IT"], "cities": ["Lecce"], "pollutants": ["NO2", "PM10"],
 "dataset": 2, "dateTimeStart": "2024-06-01T00:00:00Z",
 "dateTimeEnd": "2024-07-01T00:00:00Z", "aggregationType": "hour", "source": "API"}
```

Limiti trovati:
- **Il filtro `cities` copre solo i capoluoghi**: le città sono quelle di *Urban Audit* (per la Puglia: Bari, Taranto, Lecce, Brindisi, Foggia, Andria...). Con `["Lecce", "Brindisi", "Taranto"]` si ottengono **15 stazioni su 33**: restano fuori Statte, Mesagne, Guagnano, Campi Salentina, Arnesano, Galatina, Grottaglie, Martina Franca, Massafra, Francavilla, Ceglie, Cisternino, San Pancrazio, San Pietro Vernotico, Torchiarolo... L'API **non ha un filtro per stazione o per coordinate**: per tutto il Salento o si scarica tutta l'Italia per il periodo o si usa la strada A.
- **`dateTimeEnd` esclude l'ultimo giorno** se si passa `...T23:59:59Z` (il filtro guarda la fine dell'intervallo orario): per includere il giorno *D* si passa la **mezzanotte di D+1** (come per OpenAQ).
- **`aggregationType` non calcola aggregati**: filtra le serie per *tipo di osservazione primaria* (`hour`, `day`, `var`). Con `"day"` per l'NO2 lo ZIP è vuoto, perché ARPA trasmette l'NO2 solo orario. La statistica giornaliera va calcolata da noi.
- Limite di **600 MB** per risposta (oltre → HTTP 206 e file troncato); `compress: false` restituisce comunque uno ZIP.
- **Va sempre passato `"cities": []`** esplicito: senza il campo l'API risponde `Processing error`.

### C. `POST /ParquetFile/async` (per richieste grandi)

Stessi parametri di B; restituisce subito un URL (`https://eeadmz1batchservice02.blob.core.windows.net/downloads/<uuid>/ParquetFile.zip`) che dà 404 finché lo ZIP non è pronto, poi il file. Da interrogare a intervalli (la guida usa 20 s). Utile solo per richieste nazionali/europee: per il Salento basta A.

### Endpoint di servizio

| Endpoint | Cosa restituisce |
|---|---|
| `GET /Country` | codici e nomi dei paesi |
| `POST /City` (body: `["IT"]`) | città Urban Audit del paese (81 per l'Italia) |
| `GET /Pollutant` | 648 inquinanti: `notation`, URI Eionet, codice numerico (v. tabella sotto) |
| `POST /DownloadSummary` | numero di file e dimensione (MB) di una richiesta, **ignorando** date e tipo |
| `POST /List` | elenco dei punti di campionamento e degli URL (⚠️ ignora il filtro inquinanti) |
| `GET /Version` | versione del servizio |
| `POST /Raster`, `/Raster/async` | mappe di previsione (non usate) |

`/ParquetFile/dynamic` e `/classic` differiscono solo per come il server legge i dati; il risultato è identico (dalla guida).

## Com'è fatto il dato

### Anagrafica (DataExtract.csv)

Una riga per **punto di campionamento × anno di riferimento**. Colonne utili: `Air Quality Station EoI Code` (codice europeo della stazione, es. `IT1665A`), `Air Quality Station Name`, `Sampling Point Id`, `Air Pollutant`, `Latitude`, `Longitude`, `Altitude`, `Air Quality Station Type` (traffic / background / industrial), `Air Quality Station Area` (urban / suburban / rural), `Air Quality Network Name`, `Operational Activity Begin/End`, `Measurement Method`, `Measurement Equipment`.

- `Municipality` **non è il comune**: per la Puglia contiene spesso l'indirizzo (`via machiavelli`, `ABBAZIA DI SM CERRATE`...). Il comune va ricavato dalle coordinate (come già si fa con `api/comune/confini_comuni.py`).
- Nel riquadro del Salento (`16.70,39.75,18.55,40.95`, lo stesso di OpenAQ) ci sono **53 codici EoI**: 34 con metadati 2025 (attive), il resto stazioni storiche senza anno (reti ENEL/SIMAGE dismesse, es. "Maglie 1607583", "LENDINUSO 1607407"). Nel riquadro cade anche **Monopoli (IT1817A, provincia di Bari)**, da escludere.

### Parquet delle misure

| Colonna | Tipo | Significato |
|---|---|---|
| `Samplingpoint` | stringa | id del punto di campionamento, es. `IT/SPO.IT1665A_8_chemi_2004-05-01_00:00:00` (contiene stazione, codice inquinante, metodo, data di inizio) |
| `Pollutant` | intero | codice Eionet dell'inquinante |
| `Start`, `End` | datetime | intervallo della misura (orario: `End = Start + 1h`) |
| `Value` | **decimale come oggetto** | valore misurato; va convertito con `pd.to_numeric` |
| `Unit` | stringa | `ug.m-3` (µg/m³), `mg.m-3` per il CO |
| `AggType` | stringa | `hour`, `day` o `var` (intervallo variabile) |
| `Validity` | intero | validità (v. sotto) |
| `Verification` | intero | 1 = verificato (tutto l'E1a), 2 = verificato in via preliminare, 3 = non verificato (tutto l'E2a) |
| `ResultTime` | datetime | quando è stato generato il file di consegna |
| `DataCapture` | — | percentuale di copertura: **sempre vuota** nei file salentini |
| `FkObservationLog` | stringa | uso interno EEA |

Codici `Validity` (vocabolario Eionet): **1** valido, **2** valido sotto il limite di rilevabilità (valore misurato), **3** valido sotto il limite (sostituito da 0,5 × limite), **4** valido (solo O3, nuova sezione d'urto CCQM.O3.2019), **-1** non valido, **-99** non valido per manutenzione/calibrazione.

Ricavato dai file salentini (E1a + E2a, 9,4 milioni di righe):

- **Le ore non valide sono righe presenti con valore sentinella** `-9999` o `-999` e `Validity = -1`: dall'8% al 10,6% delle ore a seconda dell'inquinante (PM10 il più lacunoso). Non ci sono buchi "silenziosi" da ricostruire: la cella è `NULL` quando non ci sono abbastanza ore valide.
- 1.227 valori negativi hanno comunque `Validity > 0` (es. `-2.1`): per il controllo a monte del repo (valore non negativo) vanno classificati `NULL`.
- **Il dato è orario** per tutti gli inquinanti tracciati (il PM10 di alcune stazioni ha anche serie `var`, cioè gravimetriche su intervalli diversi); la statistica giornaliera va calcolata come già si fa per OpenAQ.
- In 7 casi su 114 la stessa stazione ha **più punti di campionamento per lo stesso inquinante** (cambio di strumento nel tempo): vanno uniti per stazione × inquinante, controllando che non si sovrappongano.

Codici inquinante usati:

| Inquinante | Codice Eionet | Unità |
|---|---|---|
| SO2 | 1 | µg/m³ |
| PM10 | 5 | µg/m³ |
| O3 | 7 | µg/m³ |
| NO2 | 8 | µg/m³ |
| CO | 10 | mg/m³ |
| PM2.5 | 6001 | µg/m³ |

### Copertura nel Salento

**33 stazioni con dati validi, tutte già presenti nell'anagrafica ARPA** (`../anagrafica/stazioni.json`, stessa stazione entro 250 m e stesso nome). Stazioni con dati validi per anno (E1a 2013-2025 + E2a 2026):

| Anno | CO | NO2 | O3 | PM10 | PM2.5 | SO2 |
|---|---|---|---|---|---|---|
| 2013 | 5 | 25 | 4 | 26 | 7 | 9 |
| 2014 | — | — | — | — | — | — |
| 2015-2016 | 10 | 32 | 6 | 24-25 | 15 | 15 |
| 2017-2026 | 10 | 32 | 9 | 31-33 | 14-15 | 15 |

- Il **2014 manca del tutto** (verificato anche su stazioni fuori dalla Puglia): per quell'anno EEA non aiuta, resta ARPA.
- Delle 37 stazioni ARPA dell'anagrafica, **4 non hanno un corrispondente EEA** con dati: Maglie (id 49), Brindisi – Cappuccini (78), Torchiarolo – Lendinuso (94), Galatina – Colacem (113).
- EEA non aggiunge copertura territoriale: i **distretti senza stazioni ARPA restano scoperti** anche con EEA (per quelli resta candidato solo il dato modellato Copernicus/CAMS).

## Confronto con ARPA (giugno 2024)

Verifica del 28/09/2026, fatta ricalcolando dalle ore EEA **la stessa statistica di ARPA** (PM10/PM2.5 media giornaliera; NO2, O3, SO2 massimo orario; CO massimo della media mobile su 8 ore; giorno valido con almeno 18 ore) — non la media che il dataset usa dal 29/09 (v. "Implementazione") — e confrontata con i valori ARPA di `data/interim/aria/dataset_aria_2024-06-01_2024-06-30.json`:

| Inquinante | Coppie | Uguali (entro 0,5) | Differenza media | Correlazione |
|---|---|---|---|---|
| CO | 275 | 100% | -0,01 | 0,991 |
| NO2 | 874 | 99,7% | -0,01 | 1,000 |
| O3 | 255 | 100% | 0,00 | 1,000 |
| PM10 | 740 | 100% | -0,02 | 1,000 |
| PM2.5 | 399 | 100% | -0,05 | 0,998 |
| SO2 | 370 | 52% | -0,46 | 0,994 |

**EEA E1a e ARPA sono lo stesso dato**: ARPA pubblica valori interi, EEA le ore con i decimali. L'unica differenza sistematica è sullo SO2 (valori bassi, 3-4 µg/m³), compatibile con un arrotondamento per eccesso da parte di ARPA (es. EEA 3,37 → ARPA 4), con scarti sotto 1 µg/m³ nei casi osservati. Per l'NO2 c'è un solo giorno discordante (Brindisi – Casale, 18/06/2024: ARPA 20, EEA 17,2). Quindi EEA **non è una fonte indipendente** da ARPA (come non lo è OpenAQ), ma offre:

- il **livello di verifica** esplicito (E1a verificato vs E2a no) e la validità ora per ora;
- **dati orari con decimali**, da cui ricalcolare le statistiche giornaliere con regole uniformi;
- dati **del giorno corrente** (E2a aggiornato in giornata, ARPA arriva a ieri);
- un canale **ufficiale europeo e documentato**, utile se `old.arpa.puglia.it` (host non documentato) smettesse di rispondere.

## Ridondanza come validazione

*Decisione di Matteo, 28/09/2026.* Che EEA riporti gli stessi dati di ARPA (e che OpenAQ li riprenda dall'EEA) **non è un problema, è il motivo per cui la fonte entra nel dataset**: tre canali indipendenti per arrivare alla stessa misura permettono di controllarla. Nel dataset i tre valori restano separati per stazione, giorno e inquinante (regola multi-fonte di docs/Regole_dei_dati.md); il report di ogni generazione (`data/dataset/aria/report/`, sezione 9 "Confronto tra fonti sulle stesse celle (validazione)") confronta **ogni coppia di fonti** (ARPA ↔ OpenAQ, ARPA ↔ EEA, OpenAQ ↔ EEA) e riporta per inquinante: celle confrontate, quota di celle *concordanti* (differenza entro 1 unità, perché ARPA pubblica interi), differenza media e massima, correlazione, e le celle più discordanti.

Come leggere il confronto:
- **ARPA ↔ EEA E1a** dovrebbe concordare quasi al 100% (v. "Confronto con ARPA"): una discordanza indica un errore di trasmissione, una rettifica successiva di ARPA, oppure un giorno in cui ARPA ha applicato un criterio diverso; va guardata a mano.
- **EEA E2a** (non verificato) può differire dall'E1a dell'anno dopo: le celle E2a hanno nota "non verificato (E2a)".
- La concordanza tra fonti è un indicatore di **coerenza del dato**, non di accuratezza della misura: le tre fonti partono dallo stesso strumento.

### Primo esito della validazione (giugno 2024, tre fonti)

Dal report `data/dataset/aria/report/Report_dataset_aria_2024-06-01_2024-06-30.md` (generato il 28/09/2026):

| Coppia | Celle confrontate | Concordanti (entro 1 unità) |
|---|---|---|
| ARPA ↔ EEA | 2.915 | 99,9-100% per tutti e 6 gli inquinanti (1 sola cella discordante: NO2 Brindisi – Casale 18/06, 20 vs 17,2) |
| ARPA ↔ OpenAQ | 995 | NO2 56,7%, PM2.5 80,6%, SO2 90,4%, O3 90,8% |
| OpenAQ ↔ EEA | 990 | come ARPA ↔ OpenAQ |

Visto che ARPA ed EEA concordano, la discordanza sta in **OpenAQ**: i suoi **orari sono sfasati** rispetto a EEA/ARPA di 0-2 ore, con uno sfasamento che cambia nel tempo (dettagli e tabella in `../openaq/OpenAQ.md`, "Anomalia rilevata dalla validazione"). Con il massimo orario lo sfasamento spostava i picchi da un giorno all'altro (es. Brindisi – Perrino, NO2: il massimo dell'8/06, ARPA 86 ed EEA 86,48, in OpenAQ compariva il 9/06). È esattamente il tipo di errore che la ridondanza doveva far emergere. Questo esito si riferisce alla statistica di ARPA (28/09); dal 29/09 OpenAQ ed EEA danno la media giornaliera, e il confronto con ARPA ha senso solo per il PM (v. colonna *Stessa statistica* del report).

## Implementazione (28/09/2026)

- **Client** `api/aria/eea.py`: `get_urls(dataset)` (lista di URL per l'Italia, 6 inquinanti tracciati), `get_metadati()` (anagrafica EEA, `DataExtract.csv`), `stazioni_nel_riquadro()` (stesso riquadro di OpenAQ), `leggi_parquet(url, dataset)` (download con cache e controllo delle colonne).
- **Cache** in `data/raw/aria/eea/` (gitignored), una sottocartella per contenitore (`airquality-p-e1a/`, `airquality-p/`, `metadati/`): i parquet E1a si riscaricano dopo 7 giorni, gli E2a dopo 3 ore, i metadati dopo 7 giorni. Il primo uso di un periodo storico scarica ~130 MB (tutte le serie E1a del Salento); dopo, un mese si genera in pochi secondi.
- **Adattatore** `api/aria/fonti/eea.py` (`FonteEEA`, nome `EEA` nel dataset, `copertura_da` = 01/01/2013):
  - E1a per le date fino al 31/12 dell'anno scorso, E2a dal 01/01 dell'anno scorso in poi (l'anno a cavallo si chiede a entrambi; la stessa ora presente in tutti e due prende l'E1a);
  - stazioni ricondotte a quelle ARPA con le regole condivise con OpenAQ (`api/aria/fonti/abbinamento.py`: 250 m, o 1 km con il comune nel nome); le 33 stazioni salentine sono tutte entro 250 m da una stazione ARPA; **Monopoli** (IT1817A, provincia di Bari) cade nel riquadro e finisce tra le stazioni fuori area, come per OpenAQ;
  - ora valida = `Validity > 0` e valore numerico, finito, non negativo; la stessa ora da più punti di campionamento → prevale quella verificata, poi quella valida;
  - **un solo valore al giorno per inquinante** (decisione di Matteo del 29/09/2026, uguale per OpenAQ): **media pesata sul tempo** di tutte le misure valide del giorno — orarie ed eventualmente giornaliere (PM10 gravimetrico), ognuna pesata sulla durata del suo intervallo — **senza soglia minima di ore**; la nota riporta la completezza (`media pesata sul tempo su n/24 ore`, più `non verificato (E2a)` se serve). Giorno `NULL` solo se nessuna misura del giorno è valida. Funzione comune `medie_giornaliere()` in `api/aria/fonti/base.py`;
  - misure su intervalli più lunghi di un giorno (`AggType` var settimanali/mensili) ignorate;
  - **anno 2014**: celle `NO_DATA` con nota "anno 2014 assente nell'E1a EEA per l'Italia" (attributo `periodi_non_coperti` della fonte, gestito dal generatore);
  - errori (lista URL, download, parquet illeggibile o senza colonne attese) → `NULL` sulle celle coinvolte + `errori_api.csv`, senza fermare la generazione.
- Dipendenza **`pyarrow`** aggiunta con `uv add pyarrow` (28/09/2026) per leggere i parquet.

### Completezza dell'E2a (verificata il 28/09/2026)

Nei parquet E2a le ore **mancano proprio** (non sono righe marcate non valide): a settembre 2026 in media ~18 ore al giorno per CO, NO2, O3 e SO2 e solo **~7-8 ore al giorno per PM10 e PM2.5**, contro 22-24 ore nell'E1a. Con la vecchia regola del 75% circa il 60-65% delle celle EEA dell'anno in corso risultava `NULL`, in modo costante su tutti i giorni (non è ritardo di trasmissione). **Dal 29/09/2026 non c'è più soglia**: si usa la media delle ore disponibili e la nota dice quante sono (su 20-27/09/2026: 918 celle `VALORE` e 2 `NULL`, da 1 a 24 ore, mediana 16). Quando l'anno diventa E1a (autunno dell'anno dopo) le medie si ricalcolano sulle ore verificate. Nell'E1a, inoltre, il PM "orario" è spesso il valore giornaliero ripetuto per ogni ora (79% dei giorni per il PM10, 88% per il PM2.5): la media giornaliera resta corretta.


## Limiti

- Non è fonte primaria: in caso di discordanza con ARPA, la fonte diretta resta il riferimento (entrambi i valori si conservano, v. docs/Regole_dei_dati.md).
- Dati E2a dell'anno in corso incompleti (v. sopra): medie calcolate su poche ore, da leggere insieme alla nota.
- AirBase (2004-2012) non è usato: unità di misura non valorizzata e ARPA copre già dal 2012.
- Anno 2014 assente; 4 stazioni ARPA senza corrispondente.
- Il servizio gira su Azure App Service senza SLA dichiarato; la guida stessa indica la lista di URL come l'endpoint più affidabile.
