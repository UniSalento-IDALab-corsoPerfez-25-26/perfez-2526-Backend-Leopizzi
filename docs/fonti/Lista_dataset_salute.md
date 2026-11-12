# Lista dataset — Salute della popolazione

Fonti per il dataset salute (mortalità, ricoveri, patologie), con fonte, licenza e cosa se ne preleva. Deve rimanere sempre aggiornato. Indice generale e fonti territoriali: `Lista_dataset.md`. Dataset aria: `Lista_dataset_aria.md`. Ricognizione completa con dettagli e citazioni: `ricerca/`ricerca/03_Datasets_List.md` del repository Presentation del repository Presentation (categorie 2 e 3).

**Stato (01/10/2026): nessuna fonte salute è ancora integrata nel codice** (`api/salute/` è vuoto), ma la ricognizione è stata fatta **con chiamate reali** su tutte le fonti qui elencate — schede tecniche in `istat/ISTAT.md`, `eurostat/Eurostat.md`, `aress_puglia/AReSS_Puglia.md` e `iss/ISS.md`.

**Perimetro ridotto il 01/10/2026 su decisione di Matteo:** **eliminate** ISTAT Health for All, IPRES, i dataset SDO del Ministero della Salute, tutto il filone dei **registri tumori**, **tutti i canali ISS** e il **ReNCaM** delle ASL (procedimento troppo lungo); **PNE/AGENAS reinserito**. Dettaglio e conseguenze in "Scartate su decisione di Matteo" qui sotto; il registro completo delle scelte di progetto è `documentazione/Scelte_Progettuali.md` del repository Presentation. Passo operativo in corso: **Open Salute**, che Matteo recupera in autonomia (`aress_puglia/Accesso_Open_Salute.md`).

**Obiettivo:** un **dataset salute unificato** con le stesse regole del dataset aria — JSON annidato per provincia → distretto → … → fonte → indicatore, un valore per fonte (mai aggregato tra fonti), ogni cella con stato `VALORE` / `NULL` / `NO_DATA` — rigenerato in `data/interim/salute/` (gitignored) via chiamate dirette alle fonti. Tutte le cause di morte, non solo respiratorie, per avere un confronto (decisione docs/Regole_dei_dati.md). Il confronto con l'aria è sempre **esplorativo, non causale** (fumo, età, comorbidità, aria indoor sono confondenti).

**Il vincolo di fondo, verificato due volte — prima sulle fonti statistiche e sanitarie, poi (01/10/2026) su ISS, SiSMG, SENTIERI, profilidisalute, RespiVirNet, registri tumori e Centro Salute Ambiente:** le **sole** fonti salute con grana più fine della provincia sono due file ISTAT — i decessi comunali giornalieri e il bilancio demografico mensile — e **nessuna delle due ha la causa di morte**. Appena si vuole una causa o una patologia (respiratoria o altra), la grana massima è la **provincia / ASL** e il passo temporale è **l'anno**. Nessuna fonte pubblica dà mortalità o ricoveri per causa a livello di **distretto socio-sanitario**: l'unico strumento che lo farebbe, PugliaStat di AReSS, non è accessibile.

**Differenza di grana da risolvere:** il dataset aria è giornaliero per distretto; i decessi totali ISTAT sono giornalieri e comunali; tutto il resto è annuale e provinciale/ASL. Scegliere la grana comune è ⏳. I dati comunali si riconducono al distretto con `api/comune/distretti_salento.py`; quelli solo provinciali **non** si possono ripartire tra distretti senza ipotesi aggiuntive.

**Aggiornamento 25/10/2026 — dati simulati.** In attesa dei dati richiesti ad AReSS Puglia e a Parsec 3,26, **ricoveri per causa, accessi in PS e accessi in PS degli assistiti in ADI** sono **simulati** per comune × giorno, calibrati sulle fonti di questa lista (HFA, decessi ISTAT) e su dati nazionali (Annuario SSN). Non sono una fonte: sono dati di partenza, sempre con la dicitura «dato simulato, non reale». Scheda: `simulati/Dati_Simulati.md`. Stato aggiornato di tutte le fonti: `../Inventario_Dati.md`.

## Quadro di sintesi (al 01/10/2026)

Tutte le fonti analizzate, con la grana massima che offrono e il tipo di accesso. Il numero rimanda alla scheda corrispondente nella sezione "Candidate" qui sotto.

| # | Fonte | Cosa dà | Grana | Periodo | Accesso | Licenza |
|---|---|---|---|---|---|---|
| 1 | ISTAT — decessi comunali giornalieri | decessi, **nessuna causa** | **comune × giorno** | 2011 → 30/06/2026 | ZIP/CSV, URL che cambia a ogni rilascio | CC BY 4.0 |
| 1bis | ISTAT — bilancio demografico mensile | morti, **nessuna causa** | **comune × mese** | 2019-2024 | CSV zippato, **URL stabile** | CC BY 4.0 |
| 2 | ISTAT — cause di morte (SDMX) | decessi e tassi per causa (European Short List) | provincia × anno | 2003-2023 | **API SDMX** | CC BY 4.0 |
| 3 | Eurostat | decessi | provincia × **settimana** | 2011-W01 → 2026-W27 | **API JSON** | CC BY 4.0 |
| 4 | PNE / AGENAS | ospedalizzazione per BPCO, asma, influenza | **ASL** × anno | edizioni 2022-2025 | **API JSON** (non documentata) | ⏳ non dichiarata |
| 5 | AReSS Puglia — open data CKAN | prevalenza BPCO; accessi in PS e ricoveri urgenti (cerebrovascolari, renali) | ASL × anno | 2006-2023 | **API CKAN + datastore SQL** | CC BY 4.0 |
| 6 | AReSS Puglia — PugliaStat | mortalità **e** ricoveri | **distretto / comune** | — | ❌ nessuno (report su richiesta) | non dichiarata |
| 7 | AReSS Puglia — Open Salute | malattie croniche e tumori | non dichiarata | — | dashboard Superset: serve un *guest token* (flusso noto, v. `aress_puglia/Accesso_Open_Salute.md`) | non dichiarata |

**Come si legge la tabella:** la grana piena (comune/giorno) esiste **solo** alle righe 1 e 1bis, e lì manca la causa; la riga 6 è l'unica che darebbe causa **e** distretto, ed è l'unica non pubblica. Quindi l'MVP ha **aria giornaliera per distretto ↔ decessi totali giornalieri per distretto** come confronto a grana piena, un livello **provinciale annuale** per le cause di morte (riga 2) e un livello **ASL annuale** per i ricoveri (riga 4), con la riga 3 come controllo di coerenza della riga 1 e la riga 1bis come controllo mensile.

## Decisioni chiuse su questo dataset

| Tema | Decisione | Data |
|---|---|---|
| Classi di età ISTAT | **Non si usano**: i decessi giornalieri per comune si sommano su **tutte le 22 classi di età**; nessuna dimensione età nel dataset salute | 01/10/2026 |
| Privacy (docs/Regole_dei_dati.md) | **Confermata**: il dato comune × giorno è fatto di numeri piccolissimi → va mostrato **aggregato almeno a distretto e a grana non giornaliera** (mese); la somma sulle classi di età è il primo passo di mitigazione | 01/10/2026 |
| Perimetro delle fonti | **Eliminate**: ISTAT Health for All, IPRES, SDO del Ministero della Salute, **registri tumori** (tutti), **tutti i canali ISS** e il **ReNCaM** delle ASL (procedimento troppo lungo per la consegna). **PNE/AGENAS reinserito** dopo un'eliminazione per errore | 01/10/2026 |
| Ricoveri | **Restano nell'MVP con il solo PNE** (grana ASL, annuale): è l'unica fonte di ricoveri in perimetro dopo l'uscita di HFA. **Aggiornamento 18/10/2026:** HFA rientra per le sole **dimissioni**, provincia × anno, **solo informativo** (v. `istat/ISTAT.md` canale C) | 01/10/2026, 18/10/2026 |
| Prossimo passo | **Open Salute**: Matteo procede in autonomia con i passaggi in `aress_puglia/Accesso_Open_Salute.md` | 01/10/2026 |
| Registro delle scelte | Tutte le scelte e i motivi di inclusione/esclusione delle risorse stanno in **`documentazione/Scelte_Progettuali.md` del repository Presentation** | 01/10/2026 |

---

## Candidate, in ordine di priorità proposta

Ordinate per quanto si adattano a una serie temporale per distretto. Tutto quello che segue è stato verificato il 01/10/2026 salvo dove scritto diversamente.

### 1. ISTAT — Decessi comunali giornalieri (tutte le cause)

Scheda completa: `istat/ISTAT.md` (canale A).

- **Cosa ci procureremmo**: decessi giornalieri per **comune di residenza**, sesso e classe d'età — serie **01/01/2011 → 30/06/2026** (dati provvisori). Nessun dettaglio di causa. Per decisione del 01/10/2026 le classi d'età si **sommano**.
- **Perché prima**: è l'**unica** fonte salute giornaliera e comunale → sommabile per distretto, stessa grana temporale del dataset aria.
- **Fonte**: pagina ISTAT "Dati di mortalità: cosa produce l'Istat" (<https://www.istat.it/notizia/dati-di-mortalita-cosa-produce-listat/>) → file `decessi-comunali-giornalieri-provvisori-4.zip` del rilascio corrente (ZIP 51,6 MB → CSV di 827 MB, 5.332.983 righe + PDF col tracciato).
- **Licenza**: CC BY 4.0 (note legali ISTAT: <https://www.istat.it/note-legali/>)
- **Limiti**: dati provvisori; nessuna causa di morte; **non è un'API** — l'URL cambia a ogni rilascio (una cartella per mese), quindi il link corrente va letto dalla pagina. ⚠️ Non confondere questo file con `decessi-comunali-mese-provvisori-3.zip` (stessa cosa, ma **per mese**), che la pagina inglese pubblica come `mortality-data-...-provisional-data.zip`.

### 1bis. ISTAT — Bilancio demografico mensile per comune (CSV, URL stabile)

Scheda completa: `istat/ISTAT.md` (canale D). **Trovata il 01/10/2026; client scritto e usata come validazione il 02/10/2026** (`api/salute/istat.py`, `scripts/salute/valida_decessi.py` → `report/Report_validazione_decessi.md`): sui 2019-2024 le celle comune × mese coincidono con il canale A nel **73,6-96,6 %** (entro ±1: 94-100 %), con correlazione ≥ 0,9995; lo scarto è maggiore sul 2019-2021. **Non entra nel dataset**: è un controllo di ridondanza.

- **Cosa ci procureremmo**: `Morti` (e nati, popolazione a inizio/fine mese) per **comune di residenza, mese e sesso** — anni **2019-2024**.
- **Perché conta**: è l'unica fonte, oltre al file giornaliero, che scenda **sotto la provincia**, e ha un **URL stabile e prevedibile** (`https://demo.istat.it/data/d7b/D7B<anno>.csv.zip`, ~4,3 MB per anno) invece di un link che cambia a ogni rilascio. Serve come **validazione per ridondanza** del canale A (i decessi giornalieri sommati per mese devono tornare) e come scorciatoia se la grana del confronto sarà mensile.
- **Fonte**: <https://demo.istat.it/app/?i=D7B> — **licenza CC BY 4.0**.
- **Limiti**: **nessuna causa di morte**; file scaricabili fermi al **2024** (2025 e gennaio-maggio 2026 esistono come provvisori ma solo nelle viste a video); è un dato di fonte **anagrafica**, non le schede di morte.

### 2. ISTAT — Mortalità per causa di morte (API SDMX)

Scheda completa: `istat/ISTAT.md` (canale B).

- **Cosa ci procureremmo**: decessi (e tassi grezzi/standardizzati) per **provincia di residenza**, anno e **causa iniziale** secondo la European Short List — serie **2003 → 2023**. Cause direttamente rilevanti per l'aria: `8` sistema respiratorio, `8_1` influenza, `8_2` polmonite, `8_3` croniche delle basse vie respiratorie (`8_3_1` asma), `8_4` altre; `2_1_8` tumori di trachea/bronchi/polmoni; `7` sistema circolatorio (`7_1` ischemiche, `7_3` cerebrovascolari); `99` totale. **La selezione finale delle cause è ⏳ da confermare.**
- **Fonte**: API SDMX `https://esploradati.istat.it/SDMXWS/rest` — dataflow `IT1,39_494_DF_DCIS_CMORTE1_RES_1,1.0`; territori `ITF45` Lecce, `ITF44` Brindisi, `ITF43` Taranto.
- **Licenza**: CC BY 4.0
- **Limiti** (verificati con query reali): **solo provinciale**; **nessuna causa per mese**; **nessuna causa per classe d'età**; pubblicazione a ~2 anni dall'anno di riferimento.

### 3. Eurostat — decessi settimanali per provincia (NUTS 3)

Scheda completa: `eurostat/Eurostat.md`. Questa scheda chiarisce anche **cos'è "ESDS"**: non una fonte di dati, ma lo **sportello di assistenza** coordinato da Eurostat (in Italia ospitato da ISTAT) — v. docs/Regole_dei_dati.md.

- **Cosa ci procureremmo**: **decessi per settimana e provincia** (`demo_r_mwk3_t`, e varianti per sesso e classi d'età), serie **2011-W01 → 2026-W27** per Lecce, Brindisi e Taranto.
- **Fonte**: API JSON-stat pubblica `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_r_mwk3_t?format=JSON&geo=ITF45...` (nessuna chiave).
- **Licenza**: CC BY 4.0 (politica di riuso Eurostat; dicitura esatta da copiare dalla pagina del dataset).
- **A cosa serve**: **validazione per ridondanza** del file ISTAT (gli stessi decessi, ridistribuiti da Eurostat: la somma settimanale provinciale deve coincidere) e scorciatoia leggera quando basta la grana provinciale. Le **cause di morte** su Eurostat si fermano a NUTS 2 (Puglia intera), quindi peggio di ISTAT.
- **Stato: client scritto e validazione eseguita il 02/10/2026** (`api/salute/eurostat.py`, `scripts/salute/valida_decessi.py`). Esito su 2.424 settimane provinciali complete: **100 % identiche dal 2011 al 2023** e sul 2026, 63,5 % sul 2024 e 76,3 % sul 2025 (gli anni che Eurostat non ha ancora rivisto). Il confronto ha fatto emergere il problema del **comune fuso** Presicce-Acquarica contato due volte nelle somme.

### 4. PNE / AGENAS — ospedalizzazione per BPCO e asma (API pubblica)

Scheda completa: `pne_agenas/PNE_AGENAS.md`. **Reinserita il 01/10/2026** (era stata eliminata per errore): è l'**unica fonte di ricoveri** rimasta in perimetro.

- **Cosa ci procureremmo**: indicatori di **ospedalizzazione calcolati sui residenti della ASL** — `56` BPCO, `47` asma adulti, `46` asma pediatrico, `44` influenza, più ipertensione e scompenso per confronto — con conteggio dei ricoveri, tassi grezzi e aggiustati, intervalli di confidenza e **serie storica per anno** nello stesso payload.
- **Fonte**: **API JSON pubblica** `https://pne.agenas.it/pne` (nessuna chiave): `/edizioni`, `/indicatori`, `/asl`, `/valori/by?...`. Edizione corrente **2025**.
- **Esempio verificato**: ASL Lecce, BPCO, edizione 2025 → 1.425 ricoveri di residenti, tasso grezzo 2,16‰ (IC 2,06-2,28), tasso aggiustato 2,08‰, con il dettaglio per struttura e la serie storica (2022: 1.082 ricoveri).
- **Licenza**: **non dichiarata** — ⏳ da chiarire con AGENAS prima di usarla in tesi.
- **Limiti**: grana **ASL di residenza** (nel Salento ASL = provincia); annuale; API **non documentata** (ricostruita leggendo il bundle JavaScript del sito), quindi potenzialmente instabile.

### 5. AReSS Puglia — open data su dati.puglia.it (CKAN)

Scheda completa: `aress_puglia/AReSS_Puglia.md` (canale 3).

- **Cosa ci procureremmo**: **75 dataset** AReSS, tutti **CC BY 4.0** e in gran parte con **datastore attivo** (interrogabili anche in SQL). Rilevanti: *Pazienti cronici affetti da broncopneumopatia cronica ostruttiva* (2006-2019, 2020-2022, 2023; campi `ASL, ANNO, SESSO, ETA, NUMERO`) e *Accessi in PS e ricoveri urgenti di pazienti cronici* (malattie cerebrovascolari e renali, 2018-2023).
- **Fonte**: `https://dati.puglia.it/ckan/api/3/action/...` — client già nel repo (`api/comune/dati_puglia_ckan.py`).
- **Limiti**: grana **ASL** (e regione), mai distretto né comune; **nessun dataset di ricoveri per patologia respiratoria** (la BPCO c'è solo come prevalenza di pazienti cronici).

### 6. AReSS Puglia — PugliaStat (ospedalizzazioni e decessi per distretto)

- **Cosa darebbe**: ospedalizzazioni e decessi dei residenti con grana **provinciale, distrettuale e comunale** — esattamente la zonizzazione di OneHealth, sia per la mortalità sia per i ricoveri. Sarebbe la fonte ideale.
- **Stato verificato**: **nessun accesso pubblico.** È un *software tool* interno ad AReSS che produce report su richiesta; la pagina non pubblica dati, export né endpoint. Servirebbe una **richiesta formale ad AReSS** (procedura e bozza di lettera: `aress_puglia/Accesso_Open_Salute.md` §4).
- **Fonte**: <https://aress.regione.puglia.it/en/aree-tematiche/mappe-e-dati-per-la-salute/pugliastat> — **licenza**: non dichiarata (nessun dato pubblicato).

### 7. AReSS Puglia — Open Salute Puglia (malattie croniche e tumori)

- **Cosa darebbe**: prevalenza e incidenza di malattie croniche (**BPCO**, diabete, ipertensione, scompenso) e di oltre 25 tipi di tumore (compresi polmone e mesotelioma).
- **Stato verificato**: **nessuna API pubblica documentata.** Front-end Next.js con dashboard **Apache Superset** (`superset.aress.regione.puglia.it`); le API dati richiedono un *guest token* e una richiesta anonima all'elenco dashboard restituisce `count: 0`. **Il 01/10/2026 è stato però ricostruito dal bundle JavaScript del portale l'intero flusso che emette il guest token** — v. `aress_puglia/Accesso_Open_Salute.md`: il flusso non è ancora stato eseguito, e la licenza dei dati resta non dichiarata.
- **Aggiornamento 02/10/2026**: Matteo ha scaricato a mano i **CSV** dal menu dei grafici (nessun token). Il primo, *Incidenza della BPCO per Comuni* (2024), è a grana **comune** (144 comuni su 146 del Salento) con casi, popolazione 40+, tassi e rischio relativo — quindi **più fine di ogni altra fonte per causa**, ma **solo annuale**. Uso deciso: **confronto visivo e supporto alle tesi, non integrazione nel dataset salute**. Scheda completa, tracciato e limiti: `open_salute_puglia/Open_Salute_Puglia.md`; file in `data/raw/salute/open_puglia_salute/{incidenza,prevalenza}/`.
- **Fonte**: <https://opensalute.aress.regione.puglia.it/> — **licenza**: non dichiarata (blocco per l'uso in tesi).

---

## Fonti storiche o di solo riscontro

- **OER Puglia — Atlante delle cause di morte 2000-2005** — comunale, PDF + Excel; riferimento storico. Funzioni OER passate ad AReSS dal 2024; la pagina `sanita.puglia.it/web/oer` **risponde 404 al 01/10/2026**.
- **ASL Taranto — Le cause di mortalità in Provincia di Taranto, Rapporto 2023** — comunale 2012-2021, solo provincia di Taranto, report PDF (non dataset).
- **Regione Puglia — "Assistenza ospedaliera"** (dati.puglia.it, IODL 2.0) — ricoveri aggregati del **solo 2014**.
- **ISS / SiSMG — sorveglianza della mortalità giornaliera** *(verificato il 01/10/2026, v. `iss/ISS.md` §1)* — decessi giornalieri degli over-65 per tutte le cause in **54 città campione**. L'elenco delle città è stato recuperato: nel Salento c'è **solo Taranto** (Lecce e Brindisi **non** sono incluse; in Puglia ci sono anche Bari e Foggia). Nessun dato grezzo pubblicato: solo bollettini settimanali PDF (su `salute.gov.it`, dietro un servizio anti-bot che blocca `curl`) e rapporti stagionali con tabelle per città aggregate per periodo. Licenza non dichiarata. Resta un riferimento metodologico per l'eccesso di mortalità da caldo (UHRI, v. `Lista_dataset_calore.md`).
- **ISS — profilidisalute.it** *(verificato, v. `iss/ISS.md` §2)* — mortalità per 37 cause (ICD-10) e ospedalizzazione da SDO: in chiaro solo **nazionale e regionale**, il livello **ASL** è in **area riservata agli operatori sanitari**; nessuna API, nessuna licenza dichiarata. Dove è pubblico dà **meno** di ISTAT SDMX, che arriva alla provincia.
- **ISS — SENTIERI** *(verificato, v. `iss/ISS.md` §3)* — mortalità (63 cause), ricoveri, incidenza tumorale e malformazioni **per comune**, ma solo per i comuni dei Siti di Interesse Nazionale (nel Salento: **Taranto e Statte**, area di **Brindisi**; nulla in provincia di Lecce) e su **periodi chiusi** (ricoveri 2005-2010), pubblicati come monografie PDF. Precedente metodologico importante per la tesi, non una fonte di dati.
- **ISS — RespiVirNet (ex InfluNet)** *(verificato, v. `iss/ISS.md` §4)* — incidenza **settimanale** delle sindromi respiratorie, ma solo **per regione**, e **flussi sospesi dal 06/03/2026** per motivi di protezione dei dati personali. Utile al massimo come profilo di stagionalità regionale.
- **ARPA Puglia / ASL / AReSS — Valutazione del Danno Sanitario (VDS)**, L.R. 21/2012 — mortalità, ospedalizzazione, incidenza tumorale e malformazioni per le aree ad alto rischio ambientale di **Taranto** e **Brindisi**, con dettaglio fino al **quartiere** (Tamburi, Paolo VI) e periodi 2006-2016 (mortalità) / 2006-2019 (ospedalizzazione). Solo **report PDF**, periodi chiusi, nessun dataset: riscontro autorevole per la tesi, non una fonte della pipeline.
- **Centro Salute Ambiente (CSA) Puglia** — avrebbe dovuto essere il canale della "sorveglianza epidemiologica basata sul registro di mortalità e sul registro tumori di Taranto, Brindisi e Lecce". Verificato il 01/10/2026: le pagine `sanita.puglia.it/web/csa/*` rispondono **404** e `sist.sanita.puglia.it/web/csa` fa **301 verso la home** — come già accaduto all'OER, i contenuti non sono più pubblicati.
- **AGENAS — portale statistico `stat.agenas.it`** — citato dall'Ufficio Statistico della Regione Puglia per gli accessi al pronto soccorso: ha un'area pubblica e una riservata, non documenta dataset né API, e i dati PS diffusi sono **aggregati per regione e anno** (codici triage, esiti), senza comune di residenza né diagnosi. Non utilizzabile.
- **dati.puglia.it — decessi comunali sparsi** — la ricerca CKAN per "decessi"/"mortalità" restituisce solo dataset episodici di singoli comuni (es. *Progressivo decessi giornalieri anno 2020* del Comune di Lecce, elenchi di Bitonto, Montemesola, San Marco in Lamis): nessuna copertura sistematica del Salento, quindi non utilizzabili.

## Scartate su decisione di Matteo (01/10/2026)

Fonti **verificate e funzionanti**, escluse per scelta di perimetro: non vanno riproposte. Le schede tecniche restano nel repo, marcate come scartate, per non ripetere il lavoro di verifica se un domani la decisione cambia.

| Fonte | Cos'era | Perché era stata proposta | Conseguenza dell'esclusione |
|---|---|---|---|
| **ISTAT — Health for All** (`istat/ISTAT.md` canale C) | dimissioni per malattie respiratorie e mortalità per patologia, provincia × anno, 1999-2024 | unica fonte pubblica di ricoveri **respiratori** nel Salento | i ricoveri restano coperti dal **PNE** (grana ASL), ma si perde la serie 1999-2024 e il dettaglio "apparato respiratorio" |
| **ReNCaM** delle ASL di Lecce, Brindisi e Taranto | decessi con **comune × data × causa** ICD-10 — il dato ideale | unico modo di avere causa e grana comunale insieme | nessuna fonte per causa sotto la provincia: **limite da dichiarare in tesi**. Scartato perché richiedeva tre richieste formali, troppo lente per la consegna del 24/10 |
| **ISS** (SiSMG, profilidisalute, SENTIERI, RespiVirNet) | v. "Fonti storiche o di solo riscontro" e `iss/ISS.md` | ricognizione richiesta il 01/10/2026 | nessuna: nessuno dei quattro canali era utilizzabile (copertura, area riservata, periodi chiusi, flussi sospesi) |
| **IPRES — Decessi in Puglia** | decessi per comune e sesso, anni sparsi (2015, 2019, 2021, 2023) | riscontro comunale | nessuna: era ridondante rispetto al file ISTAT giornaliero |
| **Ministero della Salute — SDO aggregati** | dimissioni per azienda e tipo di trauma, solo 2022 | completezza della ricognizione | nessuna: non aveva né diagnosi né comune di residenza |
| **Registri tumori** (RTP/AReSS, PugliaCan Live, ASL Lecce, AIRTUM) | incidenza/mortalità tumorale, provincia × anno (ASL Lecce fino a comune e distretto), solo PDF | unica fonte con grana comunale per patologia | nessuna per il dataset: la latenza dei tumori (10-30 anni) li rende inadatti al confronto con l'aria. Restano citabili come contesto in tesi |

## Fuori perimetro MVP

- **SDO regionali (sistema Edotto)** — microdati per paziente, non open: richiedono autorizzazione formale. Escluso (docs/Regole_dei_dati.md: nessuna credenziale a sistemi ASL).
- **ISTAT — cause di morte per comune** — solo su richiesta motivata al Contact Centre ISTAT.
- **ESDS** — **non è una fonte**: è il servizio di assistenza di Eurostat (v. punto 3). Dove serviva "ESDS", la fonte da usare e citare è **Eurostat**.

## Punti aperti ⏳

Aggiornati il 01/10/2026 dopo la riduzione del perimetro.

**In corso (azione, non decisione):** **Open Salute** — Matteo recupera i dati in autonomia seguendo `aress_puglia/Accesso_Open_Salute.md`; nello stesso documento c'è la bozza di richiesta ad AReSS per PugliaStat e per la licenza, da inviare se serve.

**Ancora da decidere:**

1. **Quale fonte integrare per prima** e in che ordine (proposta: 1 ISTAT giornaliero → 3 Eurostat come validazione → 1bis bilancio mensile come secondo controllo → 2 ISTAT cause provinciali → 4 PNE per i ricoveri; 5 AReSS CKAN solo se servono le croniche).
2. **Selezione delle cause di morte** da tracciare (lista proposta al punto 2, oppure tutte le 87 con filtro solo in dashboard).
3. ~~**Ricoveri**: con quale fonte.~~ **Chiuso il 01/10/2026**: HFA eliminato, **PNE confermato** → i ricoveri restano nell'MVP a grana **ASL annuale**.
4. **Come rappresentare un dato solo provinciale** nel JSON annidato (proposta: livello comune fittizio, come `nessuna_stazione` per l'aria).
5. **Grana del confronto aria ↔ salute**.
6. **Dettaglio per sesso**: tenere M/F o solo il totale.
7. **Licenza del PNE**: non dichiarata, da chiarire con AGENAS prima dell'uso in tesi (punto riaperto con il reinserimento della fonte).
8. ~~**SiSMG**: verificare se include città del Salento.~~ **Chiuso il 01/10/2026**: copre **Taranto** ma non Lecce né Brindisi, e non pubblica dati grezzi (v. `iss/ISS.md` §1).
9. **Validazione mensile con il bilancio demografico ISTAT**: se usare il canale D (`demo.istat.it`, morti per comune e mese, 2019-2024) come controllo di ridondanza del file giornaliero, come si fa per l'aria con ARPA ↔ OpenAQ ↔ EEA. Costa poco (CSV da 4,3 MB con URL stabile) e darebbe una verifica vera su due flussi ISTAT distinti.
10. **Ripartizione temporale dei dati a grana grossa**: nessuna fonte pubblica dà "morti o ricoveri per causa respiratoria, per comune, per giorno". Se un domani arrivasse un dato mensile o annuale da ripartire (es. dal ReNCaM o da PugliaStat), l'unico profilo temporale disponibile sarebbero i **decessi giornalieri comunali per tutte le cause** (canale A). Sarebbe una **stima nostra, non un dato della fonte**: da marcare nel dataset (nota + stato diverso da `VALORE`) e dichiarare in tesi. Proposta: **non farlo nell'MVP** e tenere ogni indicatore alla grana della sua fonte.



