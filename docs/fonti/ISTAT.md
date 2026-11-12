# ISTAT — Decessi e cause di morte

Scheda di riferimento per il servizio dati, secondo la convenzione del repo. **Stato al 01/10/2026: verificato, non ancora integrato nel codice** (`api/salute/` è vuoto). Indice delle fonti salute: `Lista_dataset_salute.md`.

Tutto ciò che segue è stato **verificato il 01/10/2026 con chiamate reali** (download dello ZIP, lettura del tracciato ufficiale, query SDMX), salvo dove indicato "non verificato".

ISTAT offre quattro canali diversi, con proprietà molto diverse: un **file ZIP rigenerato a ogni rilascio** (decessi comunali giornalieri, grana fine, nessuna causa), una **vera API SDMX** (cause di morte, solo provinciale e annuale), il database **Health for All** (indicatori provinciali di mortalità **e di ricovero** per patologia, serie lunghissime, in formato binario proprietario) e il **bilancio demografico mensile** di `demo.istat.it` (morti per comune e mese, CSV con URL stabile — aggiunto il 01/10/2026, v. canale D).

| Canale | Grana territoriale | Grana temporale | Causa / patologia | Periodo | Tipo di accesso |
|---|---|---|---|---|---|
| **A. Decessi comunali giornalieri** | comune di residenza | **giorno** | ❌ nessuna | 01/01/2011 → 30/06/2026 | ZIP/CSV, URL che cambia a ogni rilascio |
| **B. Mortalità per causa (SDMX)** | **provincia** | anno | ✅ European Short List | 2003 → 2023 | API SDMX REST |
| **C. Health for All (HFA)** 🟡 **riaperto il 18/10/2026 per le sole dimissioni, solo informativo** (era ⛔ dal 01/10) | **provincia** | anno | ✅ mortalità **e dimissioni ospedaliere** per gruppo di patologia | mortalità 1990 → 2023; dimissioni **1999 → 2024** | ZIP con database binario (decodificato, v. canale C) |
| **D. Bilancio demografico mensile (`demo.istat.it`)** | comune di residenza | **mese** | ❌ nessuna | 2019 → 2024 (CSV); 2025-2026 solo a video | CSV zippato, **URL stabile e prevedibile** |
| **E. Verde urbano, Ambiente urbano (SDMX)** ⚠️ *non salute: riscontro del calore, solo confronto* | **comune, ma solo i 3 capoluoghi** (Lecce, Brindisi, Taranto) | anno | — | 2016 → 2024 | API SDMX REST (stessa base del canale B) |

---

## A. Decessi comunali giornalieri (ZIP + CSV)

### Link

- Pagina di riferimento (IT): <https://www.istat.it/notizia/dati-di-mortalita-cosa-produce-listat/> — versione EN: <https://www.istat.it/en/news/mortality-data/>
- File del rilascio corrente (giugno 2026), tutti sotto `https://www.istat.it/storage/dati_mortalita/giugno-2026/`:
  - `decessi-comunali-giornalieri-provvisori-4.zip` → **il file che ci interessa**
  - `decessi-comunali-mese-provvisori-3.zip` → stessa cosa ma **per mese** (è lo ZIP che la pagina EN chiama `mortality-data-30-06-2026-provisional-data.zip`)
  - `tabella-provinciale-decessi-totali-2.xlsx`, `tabella-regionale-decessi-totali-1.xlsx` → totali mensili per provincia/regione
- Classificazione dei comuni usata (al 31/03/2026): <https://www.istat.it/it/archivio/6789>

> ⚠️ **Non è un endpoint stabile.** L'URL contiene il mese del rilascio (`giugno-2026/`, `marzo-2026/`, `dicembre-2025/`...) e il nome del file cambia tra i rilasci. Per aggiornare i dati bisogna **leggere la pagina e pescare il link corrente**, non salvare l'URL nel codice. I rilasci sono a cadenza irregolare (mensile/trimestrale) e i dati sono **provvisori**.

### Contenuto verificato

- ZIP di **51.592.163 byte**, con due file:
  - `comuni_giornaliero_30giugno26.csv` — **827.195.928 byte**, **5.332.983 righe** (compresa l'intestazione), separatore `,`
  - `Descrizione e tracciato record dati comunali giornalieri.pdf` (25 agosto 2026) — tracciato ufficiale
- Periodo di riferimento: **01/01/2011 → 30/06/2026**.
- Base dati: integrazione a livello di micro-dato di **rilevazione ISTAT P.5** (cancellati dall'anagrafe per decesso), **ANPR** e **Anagrafe Tributaria**.
- **Nessun dettaglio di causa di morte.**

### Tracciato record

| Campo | Significato |
|---|---|
| `REG`, `PROV` | codice ISTAT di regione e provincia di residenza |
| `NOME_REGIONE`, `NOME_PROVINCIA`, `NOME_COMUNE` | denominazioni |
| `COD_PROVCOM` | **codice ISTAT del comune a 6 cifre** — è la stessa PK di `data/territorio/anagrafica/territorio.json` (tabella `comuni`), quindi il collegamento comune → distretto → provincia è diretto |
| `TIPO_COMUNE` | 1 = dati fino al 30/06/2026; 2 = dati assenti nel 2026 |
| `CL_ETA` | classe di età in anni compiuti al decesso: `0`=0, `1`=1-4, `2`=5-9, `3`=10-14, `4`=15-19, `5`=20-24, `6`=25-29, `7`=30-34, `8`=35-39, `9`=40-44, `10`=45-49, `11`=50-54, `12`=55-59, `13`=60-64, `14`=65-69, `15`=70-74, `16`=75-79, `17`=80-84, `18`=85-89, `19`=90-94, `20`=95-99, `21`=100+ |
| `GE` | giorno di decesso, formato **MMGG** (es. `0415` = 15 aprile) |
| `M_11`...`M_26` | decessi maschili negli anni 2011...2026 |
| `F_11`...`F_26` | decessi femminili negli anni 2011...2026 |
| `T_11`...`T_26` | decessi totali negli anni 2011...2026 |

È un formato **largo**: una riga = comune × classe di età × giorno dell'anno, con 16 colonne-anno per ciascuno dei tre sessi.

### Come si traduce nei nostri stati `VALORE` / `NULL` / `NO_DATA`

Due note del tracciato ISTAT si mappano direttamente sulle regole di docs/Regole_dei_dati.md:

- **Riga assente** per un dato comune/classe/giorno = «dal 2011 al 2026 non è deceduto né un maschio né una femmina con quelle caratteristiche» → è un **`VALORE` pari a 0**, non un `NO_DATA`. Va scritto 0 esplicitamente, perché per noi lo zero è un'informazione (giornata senza decessi).
- **`n.d.`** compare **solo** nelle colonne `M_26`, `F_26`, `T_26` e significa "informazione 2026 non ancora disponibile" → è la situazione di **`NO_DATA`** (la fonte non copre ancora quel giorno), non di `NULL`.
- Date successive al 30/06/2026 (fine copertura del rilascio) → **`NO_DATA`**; comuni con `TIPO_COMUNE = 2` → `NO_DATA` per tutto il 2026.

### Decisioni di progetto su questa fonte

- **Classi di età: non si usano** (decisione di Matteo, 01/10/2026). L'indicatore è il **totale giornaliero per comune, sommando tutte le 22 classi di età**. Le classi restano nel file sorgente, ma non entrano nel dataset: niente dimensione età nel JSON della salute.
- **Privacy (docs/Regole_dei_dati.md, confermata il 01/10/2026):** il dato grezzo è comune × giorno × classe di età, cioè numeri molto piccoli (0, 1, 2) → **rischio di re-identificazione**. La somma su tutte le classi di età è il primo passo di mitigazione; in dashboard il dato va mostrato **aggregato almeno a distretto e a grana temporale non giornaliera** (mese).
- **Sesso:** il file dà maschi, femmine e totale. Proposta (⏳ da confermare): usare il **totale `T_*`** come indicatore, senza pubblicare M/F per cella fine.

### Licenza

- **CC BY 4.0** — note legali ISTAT: <https://www.istat.it/note-legali/>. Citare ISTAT come fonte.

### Note operative

- 827 MB di CSV per tutta Italia: va **scaricato una volta** in `data/raw/salute/istat/` (gitignored) e filtrato sui **146 comuni del Salento** via `COD_PROVCOM`, leggendolo a blocchi (`pandas.read_csv(..., chunksize=...)`) per non caricarlo tutto in memoria.
- Il formato largo va riportato a formato lungo (comune, giorno, anno → decessi) prima di costruire la griglia del dataset.

**Client implementato e verificato il 02/10/2026** — `api/salute/istat.py`, script `scripts/salute/scarica_decessi_istat.py` (`uv run scripts/salute/scarica_decessi_istat.py`):

- `trova_rilascio_corrente()` legge la pagina ISTAT e sceglie il link `.../storage/dati_mortalita/<mese>-<anno>/...giornalieri...zip` più recente; `scarica_zip()` lo mette in `data/raw/salute/istat/<mese-anno>_<nome>.zip` (il nome del file ISTAT non cambia tra i rilasci, per questo il mese è nel nome in cache). Download misurato: 51.592.163 byte in ~4 minuti.
- `leggi_decessi()` legge il CSV a blocchi (≈77 s), tiene i 146 comuni, **somma sesso e 22 classi di età** e scrive `data/interim/salute/istat/decessi_giornalieri_salento.csv`: 853.224 righe = 146 comuni × 5.844 giorni (2011-01-01 → 2026-12-31), colonne `id_comune, data, decessi, stato, nota`.
- **Il CSV è in latin-1, non UTF-8** (lo si legge con `encoding="latin-1"`).
- **Stati verificati sui dati reali:** `n.d.` compare **solo in `T_26` e per tutti e soli i giorni dal 01/07 al 31/12** (nessun `n.d.` altrove, nessun valore non numerico): la fine della copertura (30/06/2026) si ricava quindi dal file, non è scritta nel codice. Righe assenti → `VALORE` = 0. Giorni dopo la fine → `NO_DATA` (26.864 celle). Nessuna cella `NULL`.
- **Presicce-Acquarica:** ISTAT usa il codice **075098** (fusione del 2019, retroattiva su tutti gli anni). **Dal 14/10/2026** anche l'anagrafica del territorio tiene un solo comune (075098, residenti sommati, v. `scripts/territorio/costruisci_anagrafica_territorio.py`, `FUSIONI_COMUNE`): il codice del client coincide sempre con quello del file, niente più riga ripetuta da scartare nelle somme (prima: due comuni 075001/075062 nell'anagrafica, valore ripetuto, da tenere una sola volta — v. `api/salute/istat.py` e `scripts/salute/valida_decessi.py`).
- **Controllo di plausibilità:** decessi totali nei 146 comuni ≈ 17.200-19.300 l'anno nel 2011-2019, picco **21.450 nel 2021** e 20.000 nel 2020 (anni Covid), 9.957 nel primo semestre 2026. Max 20 decessi in un giorno in un solo comune.
- Il file nazionale **non è un'API**: un nuovo rilascio ISTAT si prende rilanciando lo script con `--forza`.

---

## B. Mortalità per causa di morte — API SDMX

### Endpoint

- Base: `https://esploradati.istat.it/SDMXWS/rest`
- Banca dati (interfaccia web): <https://esploradati.istat.it/databrowser/#/it/dw/categories/IT1,Z0810HEA,1.0/HEA_DEATH>
- Dati in CSV: `GET /data/IT1,<dataflow>,1.0/<key>` con header `Accept: application/vnd.sdmx.data+csv;version=1.0.0`
- Parametri utili: `startPeriod`, `endPeriod`, `lastNObservations`
- Strutture: `/datastructure/IT1/DCIS_CMORTE1_RES/1.0`; codelist `/codelist/IT1/CL_CAUSEMORTE_SL/1.0` (cause, 118 codici) e `/codelist/IT1/CL_ITTER107/1.0` (territori, 12.471 codici)
- Elenco completo dei dataflow: `/dataflow/IT1?format=sdmx-2.1` (4.911 dataflow, ~13 MB)

### Dataflow rilevanti

| Dataflow | Nome ISTAT | Cosa dà |
|---|---|---|
| `39_494_DF_DCIS_CMORTE1_RES_1` | Mortalità per territorio di **residenza** — Causa - prov. | **quello che ci serve**: decessi e tassi per provincia, anno e causa |
| `39_494_DF_DCIS_CMORTE1_RES_2` | Causa ed età | causa **oppure** età, non entrambe in dettaglio (v. limiti) |
| `39_494_DF_DCIS_CMORTE1_RES_5` | Istruzione, stato civile e mese di decesso | ha il **mese**, ma **solo con causa = 99 (totale)** |
| `39_493_DF_DCIS_CMORTE1_EV_*` | Mortalità per territorio di **evento** | stessa struttura, ma per luogo del decesso invece che di residenza — per noi serve la **residenza** |
| `26_29_DF_DCIS_DECESSI_2` | Decessi — Morti | decessi senza causa; **anche qui solo provinciale** (comune → `NoRecordsFound`, verificato) |

### Chiave della serie (DSD `DCIS_CMORTE1_RES`)

Nell'ordine, 13 dimensioni + `TIME_PERIOD`:

`FREQ . REF_AREA . DATA_TYPE . AGE . SEX . MARITAL_STATUS . EDU_LEV_HIGHEST . MONTH_DEATH . YEAR_BIRTH . AGE_SURV_SPOUSE . YEAR_MARRIAGE . CITIZENSHIP . UNDERLY_DEATH_EUSL`

- `REF_AREA`: **`ITF45` Lecce, `ITF44` Brindisi, `ITF43` Taranto** (`ITF4` = Puglia)
- `DATA_TYPE`: `DEATH` (conteggi), `MRATE` (quoziente di mortalità), `STMRATE` (tasso standardizzato)
- `SEX`: `1` maschi, `2` femmine, `9` totale
- `UNDERLY_DEATH_EUSL`: causa iniziale, **European Short List** (87 codici presenti nei dati provinciali)

Esempio verificato (decessi, tutte le età, totale per sesso, le tre province, cause respiratorie e di confronto):

```
GET /data/IT1,39_494_DF_DCIS_CMORTE1_RES_1,1.0/A.ITF45+ITF44+ITF43.DEATH.TOTAL.9.99.99.YEAR.ALL.TOTAL.ALL.WORLD.8+8_1+8_2+8_3+2_1_8+7+99
Accept: application/vnd.sdmx.data+csv;version=1.0.0
```

### Cause rilevanti per la correlazione con l'aria

Codici `CL_CAUSEMORTE_SL` candidati (selezione **da confermare**, v. `Lista_dataset_salute.md`):

| Codice | Causa |
|---|---|
| `8` | malattie del sistema respiratorio *(gruppo principale)* |
| `8_1` | influenza |
| `8_2` | polmonite |
| `8_3` | malattie croniche delle basse vie respiratorie *(comprende la BPCO)* |
| `8_3_1` | di cui asma |
| `8_4` | altre malattie del sistema respiratorio |
| `2_1_8` | tumori maligni della trachea, dei bronchi e dei polmoni |
| `7` | malattie del sistema circolatorio |
| `7_1` | malattie ischemiche del cuore |
| `7_3` | malattie cerebrovascolari |
| `99` | **totale** (riferimento obbligatorio: la decisione di docs/Regole_dei_dati.md è "tutte le cause, non solo respiratorie") |

Valori reali estratti per **Lecce, 2023, decessi totali**: respiratorio (`8`) **893**, croniche basse vie respiratorie (`8_3`) **485**, tumore polmonare (`2_1_8`) **440**, tutte le cause (`99`) **9.322**.

### Copertura e limiti (tutti verificati con query reali)

- Serie **2003 → 2023**, annuale. La diffusione avviene a circa due anni dall'anno di riferimento.
- **Nessun dato comunale**: la causa di morte per comune non è nella banca dati pubblica (`REF_AREA = 075035`, comune di Lecce → `NoRecordsFound`), anche se i codici comunali esistono nella codelist dei territori. Il dettaglio comunale richiede **richiesta motivata al Contact Centre ISTAT** (fuori MVP).
- **Nessuna causa per mese** *(riverificato il 01/10/2026 sulle chiavi di serie del dataflow `39_494_DF_DCIS_CMORTE1_RES_5`, "Istruzione, stato civile e mese di decesso")*: la dimensione `MONTH_DEATH` esiste e ha tutti i 12 mesi (`JAN`…`DEC`, più `YEAR` per il totale annuo), ma per quelle chiavi `UNDERLY_DEATH_EUSL` assume **solo il valore `99`** (totale). Quindi: **decessi provinciali per mese sì, cause di morte per mese no.**
  Il risvolto utile: se la grana del confronto aria ↔ salute sarà **mensile**, i decessi *per tutte le cause* per provincia e mese si prendono da questo dataflow via API, senza passare dal file da 827 MB del canale A — che resta necessario solo quando serve il **comune** o il **giorno**.
- **Nessuna causa per classe di età**: nei dati provinciali il dettaglio per età esiste solo per la causa `99`, e le singole cause esistono solo con `AGE = TOTAL`.
- Conseguenza per il progetto: la causa di morte è utilizzabile come **serie annuale provinciale** (3 province), non come serie per distretto. La grana del confronto con l'aria resta ⏳.

### Licenza

- **CC BY 4.0** — note legali ISTAT: <https://www.istat.it/note-legali/>.

---

## C. Health for All — Italia (HFA) — 🟡 RIAPERTO il 18/10/2026 (solo dimissioni, solo informativo)

> **Storia.** Eliminato il 01/10/2026. **Riaperto il 18/10/2026 su richiesta di Matteo** dopo aver guardato la lista indicatori (giugno 2026), con un perimetro stretto: **solo le dimissioni ospedaliere** (non la mortalità, già coperta da ISTAT giornaliero, Eurostat e SDMX), **solo a titolo informativo**, affiancate ai decessi in dashboard. Cinque gruppi: **respiratorio** (8550; 8556+8557), **BPCO** (8610; 8616+8617), **circolatorio** (8430; 8436+8437), **ischemiche** (8460; 8466+8467), **cerebrovascolari** (8520; 8526+8527): per ciascuno il tasso M+F per 10.000 e il conteggio come somma di maschi e femmine. Il valore mancante è `-1e8`.
> **Dove.** Client `api/salute/istat_hfa.py`, script `scripts/salute/scarica_dimissioni_hfa.py` → `data/interim/salute/istat_hfa/dimissioni_province.csv` (gitignored; ZIP in `data/raw/salute/istat_hfa/`), endpoint `GET /api/salute/dimissioni`, campo `dimissioni` in `/api/zona/dettaglio`, colonne `dimissioni:*` in `/api/riepilogo`. **Verificato** sui valori di questa scheda (Lecce 2023: 4.019 + 3.017 = 7.036 dimissioni respiratorie, tasso 91,47).
> **Regole.** Dato **annuale e provinciale**: non entra nelle correlazioni né in `/api/confronto`, si mostra con la convenzione `~` (totale annuo / giorni dell'anno), vale anche per i comuni (sono migliaia di casi, nessuna privacy) con la provincia dichiarata. Grafico a parte con l'asse degli **anni** nel confronto fra domini; la tab Stagionalità non lo include (la grana non è mensile).

*Verificato il 01/10/2026 scaricando e decodificando il database.* Era il canale che **avrebbe risolto i ricoveri**: contiene le **dimissioni ospedaliere per malattie dell'apparato respiratorio a livello provinciale, 1999-2024**, che nessun'altra fonte pubblica dà.

### Link e licenza

- Pagina: <https://www.istat.it/sistema-informativo-6/health-for-all-italia/> — versione **giugno 2026**, ~4.000 indicatori
- Database: `https://www.istat.it/wp-content/uploads/2026/04/HFA_giugno.zip` (ZIP di 26 MB, 1.093 file)
- Elenco indicatori: `https://www.istat.it/wp-content/uploads/2026/04/Lista-indicatori_giu2026.zip` (un `.docx` con codice, descrizione, anni e livello territoriale di ogni indicatore)
- Guida: `https://www.istat.it/wp-content/uploads/2026/04/help_giugno2026.zip`
- **Licenza: CC BY 4.0** (note legali ISTAT). ⚠️ Gli URL contengono la data di rilascio: come per il canale A, il link corrente va letto dalla pagina.

### Indicatori rilevanti (livello **provincia**)

| Codice | Indicatore | Anni |
|---|---|---|
| `8550`-`8569`+ | **Tasso di dimissioni per malattie dell'apparato respiratorio** (per 10.000 ab.), per sesso, 65+, classi d'età; e **conteggi** di dimissioni (`8556` M, `8557` F, `8558`/`8559` 65+) | **1999-2024** |
| `1600`-`1611`+ | **Tasso di mortalità per malattie dell'apparato respiratorio** e decessi, per sesso e classi d'età | **1990-2023** |
| `1210`-`1233`+ | Mortalità per **tumori maligni dell'apparato respiratorio** e organi intratoracici | 1990-2023 |
| `0000`+ | Popolazione residente per sesso e classe d'età (denominatori dei tassi) | 1982-2024 |
| — | Gruppo 9 "Attività ospedaliera per patologia" ha una sezione per ciascun gruppo di patologie (infettive, circolatorio, respiratorio, digerente...), sempre a livello provinciale | 1999-2024 |

### Formato: binario proprietario, ma decodificato

Il pacchetto è pensato per il software desktop WHO/ISTAT `HFA.exe` (solo Windows), ma i dati sono leggibili direttamente. Struttura verificata:

- `HFA/Data/<dataset>.<anno>` — matrice di **float32 little-endian**, ordinata **per indicatore** (offset del valore = `(indice_indicatore × n_territori + indice_territorio) × 4`)
- `HFA/Data/<dataset>.ind` — `uint16` con il numero di indicatori, seguito dai loro **codici** in `uint16`
- `HFA/Data/<dataset>.rid` — codici dei territori, record a **16 byte** terminati da `\0`
- `HFA/Data/<dataset>.par` — nomi dei territori
- Un dataset per livello: `10000` = regioni + ripartizioni + ITALIA (29 territori); `10100`…`12000` = province di ciascuna regione. **La Puglia è il dataset `11600`**, 2.526 indicatori × 7 territori: `1601` Foggia, `1602` Bari, `1603` **Taranto**, `1604` **Brindisi**, `1605` **Lecce**, `1606` Barletta-Andria-Trani, `1607` PUGLIA. La dimensione dei file (`2526 × 7 × 4 = 70.728` byte) conferma il layout.

Valori reali letti per il **2023** (controprova: la popolazione coincide con quella nota):

| Provincia | Popolazione | Tasso dimissioni resp. (×10.000) | Dimissioni resp. M | Tasso mortalità resp. (×10.000) |
|---|---|---|---|---|
| Lecce | 769.230 | 91,47 | 4.019 | 11,61 |
| Taranto | 555.096 | 90,61 | 2.923 | 9,13 |
| Brindisi | 378.381 | 99,58 | 2.180 | 9,99 |
| Puglia | 3.899.172 | 84,23 | 18.770 | 8,98 |

### Limiti

- Grana **provinciale**, annuale: non dà il distretto.
- Formato non documentato ufficialmente: la decodifica è nostra (reverse engineering verificato su valori noti), quindi va **ricontrollata a ogni nuovo rilascio** e dichiarata in tesi come tale.
- Gli indicatori sono in gran parte **tassi già calcolati**; i conteggi grezzi ci sono solo per alcune combinazioni (es. dimissioni M/F e 65+).

---

## D. Bilancio demografico mensile per comune (`demo.istat.it`)

*Canale trovato e verificato il 01/10/2026* (pagina esplorata, CSV scaricato e letto). È il quarto canale ISTAT e il secondo — dopo il canale A — a scendere **sotto la provincia**.

### Link e formato

- Pagina: <https://demo.istat.it/app/?i=D7B> ("Bilancio demografico mensile e popolazione residente per sesso"), con viste per area, vista territoriale e **area download**.
- Download: **`https://demo.istat.it/data/d7b/D7B<anno>.csv.zip`** — URL **stabile e prevedibile**, quindi usabile da uno script senza scraping (a differenza del canale A, il cui link cambia a ogni rilascio).
- Anni disponibili come CSV — verificato uno per uno con richieste HTTP: **2019, 2020, 2021, 2022, 2023, 2024** (`200`); **2011-2018, 2025, 2026** rispondono **404**. I dati 2025 e gennaio-maggio 2026 esistono come **provvisori** ma solo nelle viste a video: l'area download delle pagine `a=2025` e `a=2026` continua a elencare i soli file fino al 2024.
- Dimensioni: ZIP di ~4,3 MB per anno → CSV di **337.302 righe** (≈7.900 comuni × 12 mesi × 3 valori di sesso), separatore `;`, codifica UTF-8.

### Tracciato (verificato sul file 2024)

`Anno; Mese; Nome mese; Sesso; Popolazione inizio periodo; Nati vivi; **Morti**; Saldo naturale; Immigrati da altro comune; Emigrati per altro comune; Saldo migratorio interno; Immigrati dall'estero; Emigrati per l'estero; Saldo migratorio con l'estero; Unità in più/meno dovute a variazioni territoriali; Popolazione fine periodo; Codice comune; Comune; Codice provincia; Provincia; Codice regione; Regione; Codice ripartizione; Ripartizione; Codice nazione; Nazione`

- Nome del file dentro lo ZIP: `Bilancio_demografico_mensile_<anno>.csv` (verificato sul 2024, 4.313.199 byte zippati). Le ultime due colonne sono `Codice nazione; Nazione`, non `Codice Italia; Italia` come annotato il 01/10/2026 — corretto il 02/10 leggendo il file con il client.

- `Codice comune` è il **codice ISTAT a 6 cifre** (es. `001001`): è la stessa chiave primaria delle anagrafiche del repo (`data/territorio/anagrafica/territorio.json`), quindi l'aggancio a comune → distretto → provincia è immediato con `api/comune/distretti_salento.py`.
- `Sesso` vale `Maschi`, `Femmine`, `Totale` (le righe sono già sommate: per il dataset salute basta `Totale`, coerentemente con la decisione di non usare le classi d'età).
- **Nessuna causa di morte**, come nel canale A.

### A cosa serve nel progetto

1. **Validazione per ridondanza del canale A** (stessa logica usata per l'aria con ARPA ↔ OpenAQ ↔ EEA): i decessi giornalieri comunali sommati per mese devono coincidere con i `Morti` di questo file. Due pubblicazioni ISTAT distinte, due flussi diversi (stato civile / anagrafe) → un controllo vero, non una tautologia. **Fatto il 02/10/2026** con `scripts/salute/valida_decessi.py` (client: `scarica_bilancio_mensile` + `leggi_bilancio_mensile` in `api/salute/istat.py`): sui 2019-2024, celle comune × mese identiche nel **73,6-96,6 %** per anno, entro ±1 nel 94-100 %, correlazione ≥ 0,9995; lo scarto è maggiore sul 2019-2021 (canale A sopra il bilancio) e minimo sul 2022-2024. Esito completo in `Report_validazione_decessi.md`.
2. **Scorciatoia quando la grana del confronto è mensile**: 4,3 MB per anno con URL stabile, contro uno ZIP da 51 MB (CSV 827 MB) di cui l'URL va letto dalla pagina a ogni rilascio.
3. **Denominatori**: la popolazione a inizio/fine mese per comune dà i denominatori dei tassi senza ricorrere ad altre tabelle.

### Limiti

- **Nessuna causa di morte**, quindi non risolve il vincolo di fondo del progetto.
- Fermo al **2024** come file scaricabile: per il 2025-2026 servirebbe interrogare la vista a video (nessun endpoint dati trovato nel sorgente della pagina, che usa DataTables su HTML già reso).
- Attenzione a non confonderlo con il canale A: qui il passo è il **mese**, e i dati sono **di fonte anagrafica** (bilancio demografico), non le schede di morte.

### Licenza

- **CC BY 4.0** — note legali ISTAT: <https://www.istat.it/note-legali/>.

---

## E. Ambiente urbano — Verde urbano (`609_1_DF_DCCV_URBANENV_18`) — solo confronto

*Aggiunto il 18/10/2026 su richiesta di Matteo, **solo come fonte di confronto**. Non è un dato di salute: sta in questa scheda perché è lo stesso servizio SDMX ISTAT del canale B; il dominio di riferimento è il **calore** (mitigazione), v. `Lista_dataset_calore.md` §3.6.*

### Link e accesso

- Banca dati: <https://esploradati.istat.it/databrowser/#/it/dw> → "Ambiente urbano", sezione "Verde urbano - densità" (famiglia `609_1`, dataflow `609_1_DF_DCCV_URBANENV_18`).
- API: `GET https://esploradati.istat.it/SDMXWS/rest/data/IT1,609_1_DF_DCCV_URBANENV_18,1.0/A.075035+073027+074001..?startPeriod=2016` con `Accept: application/vnd.sdmx.data+csv;version=1.0.0`. Dimensioni: `FREQ`, `REF_AREA`, `DATA_TYPE`, `TIME_PERIOD`. Nessuna chiave.
- **Licenza: CC BY 4.0** (note legali ISTAT, come gli altri canali).

### Contenuto (verificato il 18/10/2026 con query reali)

Solo i **tre capoluoghi** (Lecce `075035`, Brindisi `074001`, Taranto `073027`); gli altri 142 comuni del Salento non ci sono.

| `DATA_TYPE` | Indicatore | Anni | Lecce (ultimo anno) |
|---|---|---|---|
| `URGRDPINC` | densità di verde urbano, % della superficie comunale | 2016-2024 | 0,4 % (2024) |
| `DPROPINC` | densità di aree naturali protette, % della superficie comunale | 2017-2024 | 12,7 % (2024) |
| `TDGREARPINC` | verde urbano + aree protette, al netto delle sovrapposizioni, % della superficie comunale | 2023-2024 | 13,2 % (2024) |
| `DHIPA100SQ` | parchi e giardini storici e altri parchi urbani di interesse pubblico, per 100 m² di area edificata | 2021-2024 | 0,8 (2024) |

Dato **annuale**, quasi statico (Lecce: 0,4 % per nove anni di fila).

### A cosa serve nel progetto

**Solo confronto, non entra in nessun dataset né nel calcolo di `copertura_arborea_pct`**: serve a verificare con un riscontro indipendente l'ordine di grandezza della mitigazione che calcoliamo da raster (Tree Cover Density, `CLMS.md`) sui tre capoluoghi. Va letto con cautela: sono grandezze diverse (verde pubblico gestito dal comune contro chioma arborea su tutto il territorio comunale, uliveti compresi), quindi ci si aspetta che **non coincidano**; il confronto dice se l'ordine fra i tre capoluoghi è lo stesso, non se i numeri sono uguali.

### Limiti

- Solo 3 comuni su 145: nessuna grana di distretto.
- Indicatori su definizioni ISTAT/ISPRA diverse da quelle CLMS (verde pubblico contro chioma; il denominatore di `DHIPA100SQ` è l'area edificata del Censimento 2021, dati provvisori).
- Nessun client né script nel repo: la lettura si è fatta con interrogazioni dirette. Se servisse in dashboard, il client va in `api/calore/istat_verde.py`.
