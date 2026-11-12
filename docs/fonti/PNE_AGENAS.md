# PNE — Programma Nazionale Esiti (AGENAS)

Scheda di riferimento per il servizio dati, secondo la convenzione del repo. **Stato al 01/10/2026: verificato, non ancora integrato — in perimetro.** Indice delle fonti salute: `Lista_dataset_salute.md` (punto 4).

> È l'**unica fonte di ricoveri rimasta nel progetto** dopo l'uscita di ISTAT Health for All (v. `documentazione/Scelte_Progettuali.md` del repository Presentation). ⏳ La licenza non è dichiarata: va chiarita con AGENAS prima di citare i dati in tesi.

Tutto ciò che segue è stato **verificato il 01/10/2026 con chiamate reali** all'API, salvo dove indicato "non verificato".

## Cos'è

Il **Programma Nazionale Esiti**, gestito da **AGENAS** per il Ministero della Salute, calcola ogni anno oltre 200 indicatori di esito e di volume a partire dal **flusso SDO** nazionale, integrato con l'**Anagrafe Tributaria** per il follow-up della mortalità (documentato in `assets/documentation/fonti_metodi/fonti_informative.pdf`). Il sito è <https://pne.agenas.it/>: una single-page app Angular che — a differenza di PugliaStat e Open Salute Puglia — **espone un'API JSON pubblica senza autenticazione**.

Per OneHealth è la fonte che dà i **ricoveri per patologia respiratoria calcolati sui residenti**, cosa che gli open data del Ministero della Salute non danno.

## API (verificata)

- Base: `https://pne.agenas.it/pne` — il front-end la legge da `https://pne.agenas.it/assets/config.json` (`apiUrl`)
- Nessuna chiave, nessun token. Risposte paginate in stile Spring Data (`content`, `totalElements`, `size`, `page`); `unpaged=true` restituisce tutto.
- Endpoint utili:

| Endpoint | Cosa dà |
|---|---|
| `GET /edizioni` | edizioni del programma: 2022, 2023, 2024 (`OFFLINE`) e **2025 (`IN_CORSO`)** con i rispettivi `id` |
| `GET /indicatori?unpaged=true` | **838** indicatori su tutte le edizioni (**218** nell'edizione 2025), con `codice`, `descr`, `areaValutazione` (`OSPEDALIERA`, `TERRITORIALE`, `ALTRO`), `edizione` |
| `GET /asl?unpaged=true` | anagrafica ASL per edizione (568 record): per la Puglia `160106` ASL Br, `160112` ASL Ta, `160116` ASL Le |
| `GET /regioni`, `/province`, `/comuni`, `/strutture` | altre anagrafiche territoriali e delle strutture |
| `GET /valori/by?edizione=<id>&unpaged=true&indicatore=<id>[&asl=<id>&regione=<id>&provincia=<id>&comune=<id>&struttura=<id>]` | **i valori**: con `indicatore` e `asl` restituisce i record di quell'indicatore per quella ASL |
| `GET /valori-types` | definizione dei "tipi di valore" (quali campi contiene ogni record: conteggi, tassi, trend...) |

> ⚠️ Il front-end usa anche `POST /valori/by-asl` (lista di ASL nel body): dall'esterno risponde **403**. Il `GET /valori/by` serve lo stesso scopo e funziona.

## Indicatori rilevanti per la qualità dell'aria (edizione 2025)

| Codice | Indicatore | Area |
|---|---|---|
| **56** | **Ospedalizzazione per broncopneumopatia cronica ostruttiva (BPCO)** | TERRITORIALE |
| **47** | Ospedalizzazione per **asma negli adulti** | TERRITORIALE |
| **46** | Ospedalizzazione per **asma pediatrico** | TERRITORIALE |
| **44** | Ospedalizzazione per **influenza** | TERRITORIALE |
| 58, 59 | Ospedalizzazione per ipertensione arteriosa / scompenso cardiaco (confronto cardiovascolare) | TERRITORIALE |
| 21, 22 | BPCO riacutizzata: mortalità e riammissioni a 30 giorni | OSPEDALIERA |
| 126 | BPCO: volume di ricoveri ordinari | OSPEDALIERA |
| 408-410 | Embolia polmonare: ospedalizzazione, mortalità e riammissioni a 30 giorni | OSPEDALIERA |
| 63, 101, 721 | Tumore del polmone: mortalità a 30/90 giorni dall'intervento, volume di ricoveri | OSPEDALIERA / ALTRO |

Gli indicatori **TERRITORIALE** sono quelli che ci interessano: sono tassi di ospedalizzazione calcolati sulla **popolazione residente** della ASL, non sull'attività della singola struttura.

## Esempio verificato

`GET /valori/by?edizione=59c174f9-…&unpaged=true&indicatore=98a25229-…&asl=47f7cd72-…` (indicatore 56, ASL Lecce, edizione 2025) → 11 record, tra cui:

- ricoveri di residenti: **1.425**, di cui 1.402 in regione (98,4%) e 23 in mobilità (1,6%)
- **tasso grezzo 2,16** per 1.000 (IC 2,06-2,28), **tasso aggiustato 2,08** (IC 1,96-2,21)
- una **serie storica** per anno nello stesso payload (es. 2022: n = 1.082, tasso grezzo 1,64, tasso aggiustato 1,52, con intervalli di confidenza)
- il dettaglio per **struttura di ricovero** (8 strutture per la ASL di Lecce, con numero e percentuale di ricoveri)

## Limiti

- Grana **ASL di residenza** (+ struttura di ricovero): **non c'è il distretto**, e nel Salento ASL = provincia, quindi non aggiunge granularità rispetto a ISTAT.
- Indicatori **annuali**, in gran parte come **tassi** (il conteggio dei ricoveri c'è, le classi d'età no).
- L'API **non è documentata** (nessuno Swagger pubblico: `/swagger-ui.html`, `/v3/api-docs` → 404): quanto sopra viene dalla lettura del bundle JavaScript del sito. Va quindi considerata **non stabile** e ricontrollata nel tempo.
- **Licenza: non dichiarata.** Non ho trovato né nel sito né nel bundle una nota di licenza o di riuso; il PNE è pubblicato da AGENAS (ente pubblico) per il Ministero della Salute, ma prima di usarlo in tesi va chiarito — ⏳ da verificare (eventualmente scrivendo a AGENAS).
- Le edizioni precedenti sono marcate `OFFLINE` ma i loro dati restano interrogabili via API; il significato di quello stato **non è verificato**.
