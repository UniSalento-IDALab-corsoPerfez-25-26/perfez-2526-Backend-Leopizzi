# AReSS Puglia — PugliaStat, Open Salute Puglia, open data su dati.puglia.it

Scheda di riferimento per il servizio dati, secondo la convenzione del repo. **Stato al 01/10/2026: verificato, non ancora integrato nel codice.** Indice delle fonti salute: `Lista_dataset_salute.md`.

Tutto ciò che segue è stato **verificato il 01/10/2026 con chiamate reali** (pagine, bundle JavaScript delle web app, API CKAN e datastore SQL), salvo dove indicato "non verificato".

**AReSS Puglia** (Agenzia Regionale Strategica per la Salute ed il Sociale), Area "Epidemiologia e Care Intelligence", ha assorbito dal 2024 le funzioni dell'OER Puglia (DGR 1396/2024) ed è quindi l'ente di riferimento per mortalità e ospedalizzazioni regionali. Pubblica i dati per tre canali molto diversi fra loro:

| Canale | Cosa contiene | Grana territoriale | Accesso programmatico |
|---|---|---|---|
| **PugliaStat** | ospedalizzazioni e decessi dei residenti | provincia, **distretto**, comune | ❌ nessuno: strumento interno, report su richiesta |
| **Open Salute Puglia** | malattie croniche (BPCO, diabete, ipertensione, scompenso) e >25 tumori | non dichiarata nelle pagine pubbliche | ❌ dashboard Superset incorporate, serve un *guest token* |
| **Open data su dati.puglia.it** | 75 dataset AReSS, tra cui BPCO e accessi in PS/ricoveri urgenti | **ASL** e regione | ✅ **CKAN + datastore (anche SQL)** |

Conclusione operativa: **l'unico canale utilizzabile dalla pipeline è il terzo**, ma si ferma alla grana **ASL** (sei ASL pugliesi, tre delle quali nel Salento), non al distretto.

---

## 1. PugliaStat

- URL: <https://aress.regione.puglia.it/en/aree-tematiche/mappe-e-dati-per-la-salute/pugliastat>
- La pagina istituzionale lo descrive come *software tool* per analisi su **ospedalizzazioni e decessi della popolazione residente pugliese**, con disaggregazione **provinciale, distrettuale e comunale**, che «produce report da includere nelle relazioni periodiche di AReSS sullo stato di salute della popolazione» e che «nel tempo ha risposto a domande di amministratori locali e associazioni di volontariato».
- Pubblicazione citata: Antonio Chieti, Anna Maria Nannavecchia, Lucia Bisceglia, "Lo stato di salute pugliese on demand: un nuovo strumento informativo", XXXIX Congresso dell'Associazione Italiana di Epidemiologia, Milano, 27-30 ottobre 2015.
- **Verificato il 01/10/2026:** la pagina non contiene **nessun link ai dati, nessun export, nessun endpoint**; non esiste una web app PugliaStat pubblica. È uno strumento interno che produce report **su richiesta**.
- **Licenza**: non dichiarata (non essendoci dati pubblicati).
- È la fonte che darebbe nativamente la grana **distretto** sia per i decessi sia per i ricoveri — cioè esattamente la zonizzazione di OneHealth. Per averla servirebbe una **richiesta formale ad AReSS**: ⏳ Matteo valuta se inoltrarla (v. `Lista_dataset_salute.md`, "Punti aperti").

## 2. Open Salute Puglia

- URL: <https://opensalute.aress.regione.puglia.it/>
- Contenuto dichiarato: prevalenza e incidenza di malattie croniche — **BPCO** (l'indicatore respiratorio diretto), diabete tipo 2, ipertensione arteriosa, scompenso cardiaco — e di oltre 25 tipologie tumorali (polmone, colon-retto, mammella, prostata, leucemie, linfomi, mesotelioma...). Una dashboard per indicatore, es. `/dashboard/bpco-sintesi`, `/dashboard/bpco-incidenza-sintesi`, `/dashboard/tumori-polmone`, più `/dashboard/metodi` e `/dashboard/guida-all-uso`.
- **Verificato il 01/10/2026:** il portale è un front-end **Next.js** che incorpora dashboard **Apache Superset** ospitate su `https://superset.aress.regione.puglia.it`. Il bundle JavaScript usa gli endpoint Superset `/api/v1/security/guest_token/`, `/api/v1/security/csrf_token/`, `/api/v1/chart/data`, `/api/v1/dashboard/`.
- Una chiamata **anonima** a `https://superset.aress.regione.puglia.it/api/v1/dashboard/` risponde `200` ma con `count: 0`: le dashboard non sono elencabili né interrogabili senza un **guest token**, che viene emesso dal backend del portale con credenziali proprie. **Nessuna API pubblica**, quindi.
- Resta possibile l'**export manuale** dalla UI (le dashboard Superset normalmente permettono "Download as CSV" per singolo grafico): **non verificato**, va provato nel browser.
- **Licenza**: non dichiarata nelle pagine consultate.

## 3. Open data AReSS su dati.puglia.it (CKAN) — il canale usabile

- Portale: <https://dati.puglia.it/> — API CKAN: `https://dati.puglia.it/ckan/api/3/action/...`
- Organizzazione: **"Agenzia Regionale Strategica per la Salute ed il Sociale"** — **75 dataset** al 01/10/2026, tutti con licenza **CC BY 4.0**.
- Client già presente nel repo: `api/comune/dati_puglia_ckan.py` (lo stesso usato per le fonti territoriali e il mirror CKAN di ARPA).
- Molti dataset hanno **`datastore_active: true`**, quindi si interrogano senza scaricare il file:
  - `GET /api/3/action/datastore_search?resource_id=<id>&limit=...`
  - `GET /api/3/action/datastore_search_sql?sql=SELECT ... FROM "<resource_id>"` (SQL vero, usato per verificare i livelli territoriali)
  - elenco dataset dell'ente: `GET /api/3/action/package_search?q=organization:agenzia-regionale-strategica-per-la-salute-ed-il-sociale&rows=100`

### Dataset rilevanti per OneHealth (verificati)

| Dataset | Campi | Grana | Periodo |
|---|---|---|---|
| Pazienti cronici affetti da **broncopneumopatia cronica ostruttiva** (2023; e 2020-2022; e 2006-2019) | `ASL, ANNO, SESSO, ETA, NUMERO` | **ASL** | 2006 → 2023 su tre dataset |
| Pazienti cronici: diabete / ipertensione / scompenso cardiaco (stesse tre finestre) | idem | **ASL** | 2006 → 2023 |
| Pazienti cronici affetti dalle **quattro patologie** insieme | idem | **ASL** | 2020-2022; 2023 |
| **Accessi in PS e ricoveri urgenti** di pazienti cronici: **malattie cerebrovascolari** | `PATOLOGIA, ANNO, LIVELLO, TERRITORIO, NUMERO` | `LIVELLO` ∈ {`REGIONE`, `ASL`} | 2018-2023 |
| **Accessi in PS e ricoveri urgenti** di pazienti cronici: **malattie renali** | idem | `LIVELLO` ∈ {`REGIONE`, `ASL`} | 2018-2023 |

Dettagli verificati:

- BPCO 2023 (`resource_id` `07da535a-f423-4846-aff3-58494fc9747b`): 210 righe, popolazione **ultraquarantenne**, `SESSO` ∈ {Maschi, Femmine, Tutti}, `ETA` in classi quinquennali da `40-44`, `ASL` ∈ {BAT, Bari, Brindisi, Foggia, Lecce, Taranto}.
- Accessi in PS/ricoveri urgenti, cerebrovascolari (`resource_id` `1224145a-7ec2-4f88-a3aa-b385a5cc3f9a`): 696 righe; interrogando `SELECT "LIVELLO", count(*) GROUP BY "LIVELLO"` si ottengono **solo** `REGIONE` (624) e `ASL` (72) → **nessun livello distretto o comune**.
- **Tra i dataset di accessi in PS e ricoveri urgenti non c'è nessuna patologia respiratoria**: solo malattie cerebrovascolari e malattie renali. La BPCO c'è come **prevalenza di pazienti cronici**, non come ricoveri.

### Cosa questo canale può e non può dare al progetto

- ✅ Può dare un **indicatore respiratorio cronico (BPCO) per ASL e anno**, utile come contesto e come riscontro della mortalità respiratoria ISTAT.
- ❌ Non può dare **ricoveri per causa respiratoria**, né alcun dato a grana **distretto** o comune.
- Le tre ASL salentine (Lecce, Brindisi, Taranto) coincidono con le tre province, quindi la grana ASL equivale alla grana provinciale già coperta da ISTAT per le cause di morte.

---

## Altre fonti di ricoveri provate il 01/10/2026 (per non riprovarle)

- **Ministero della Salute — open data** (<https://www.dati.salute.gov.it/>, IODL 2.0): i dataset SDO pubblicati sono *Dimissioni ospedaliere per azienda sanitaria e tipologia di ricovero per traumatismo o intossicazione* (verificato: **solo anno 2022**, per azienda, con i valori piccoli oscurati da `***`), *per fasce d'età e sesso* e *per istituto e tipologia di dimissione*. **Nessuna diagnosi, nessun comune di residenza** → inutilizzabili per correlare con l'aria.
- **Regione Puglia — "Assistenza ospedaliera"** su dati.puglia.it (IODL 2.0): dati aggregati di ricovero del **solo 2014**.
- **PNE / AGENAS** (<https://pne.agenas.it/open-data>): è una single-page app Angular; contiene indicatori di ospedalizzazione (tra cui respiratori) ma **non ho verificato** se esista un download o un'API, né la granularità territoriale. Da valutare se si decide di insistere sui ricoveri.
- **IPRES — "Decessi in Puglia"** su dati.puglia.it (CC BY 4.0, risorse ospitate su `opendataipres.it`): decessi per comune e sesso per singoli anni (2019, 2023, ...) → ridondante rispetto al file giornaliero ISTAT, che copre tutta la serie 2011-2026.
