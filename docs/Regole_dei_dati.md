# Regole dei dati

Le regole con cui OneHealth acquisisce, valida, unifica e mostra i dati di **aria**, **calore** e **salute** nel Salento. Valgono per tutto il codice del Backend (`api/`, `scripts/`, `localhost/server/`) e per ciò che la dashboard mostra. Le schede delle singole fonti stanno in [`fonti/`](fonti/); l'architettura in [`Architettura.md`](Architettura.md); gli endpoint in [`Endpoint.md`](Endpoint.md).

## 1. Principi

- **Solo fonti pubbliche con licenza**: nessuna credenziale verso sistemi privati o gestionali ASL, nessun dataset fornito da terzi. Le fonti usate e le loro licenze sono in [`../ATTRIBUZIONI.md`](../ATTRIBUZIONI.md).
- **Correlazione esplorativa, non causale.** Fumo, età, comorbidità e aria indoor sono confondenti che nessuna di queste fonti misura. Lo dichiarano anche l'interfaccia e l'assistente.
- **Nessun database persistente.** I dati arrivano da chiamate API dirette e si salvano in JSON o parquet; per interrogarli si ricostruisce, a ogni avvio, un SQLite **in memoria** (v. [`Architettura.md`](Architettura.md)).
- **Dataset non aggregati**: un valore per fonte. Le medie esistono solo in visualizzazione e nelle analisi su un comune (v. §6).
- **Mai un valore inventato né una cella vuota**: ogni assenza ha un tipo e un motivo (v. §2).

## 2. Stati del dato: `VALORE`, `NULL`, `NO_DATA`

Ogni foglia dei dataset è `{"valore", "stato", "nota"}` con `stato` in:

| Stato | Significato | Esempio |
|---|---|---|
| `VALORE` | La fonte copre la combinazione e il valore è utilizzabile | media giornaliera di NO2 di una stazione |
| `NULL` | La fonte copre la combinazione ma il valore **non è utilizzabile** | misura implausibile, righe discordanti, errore della chiamata |
| `NO_DATA` | La fonte **non copre** la combinazione | stazione che non misura quell'inquinante; anno non pubblicato |

Il motivo sta nella `nota` e **sopravvive all'aggregazione**: in dashboard diventa un segno col perché nel tooltip (beuta = simulato, cubo = modellato, divieto = `NO_DATA`, punto esclamativo = `NULL`). Gli stati sono definiti una volta sola in `api/comune/stati.py`.

## 3. Formato del dataset aria

JSON annidato **provincia → distretto → comune → stazione → giorno → fonte → inquinante**, con un valore per fonte (chiavi sorelle). I comuni senza stazioni hanno la stazione fittizia `nessuna_stazione`. L'archivio è **incrementale, un mese per file**, in `data/interim/aria/` (generato, non versionato); i mesi completi si saltano, il mese aperto si rifà, un mese generato con un elenco di comuni diverso si rifà da sé (impronta `territorio`).

Ogni fonte è un adattatore in `api/aria/fonti/`, registrato in `fonti/__init__.py`: per aggiungere una fonte non si tocca il generatore.

## 4. Controlli e errori

- **Controllo a monte nei client**: campi attesi presenti, valore numerico finito e non negativo; righe discordanti per la stessa cella → `NULL`.
- **Errori delle API** gestiti senza interrompere la generazione: celle `NULL`, dettaglio in `data/interim/<dominio>/errori_api.csv` e **una riga di riepilogo per esecuzione** in `data/interim/aria/riepilogo_errori.md`.
- **Zona o inquinante nuovo**: un distretto o una zona sconosciuti si segnalano nel riepilogo (non si scartano né si mappano a intuito); un inquinante nuovo si aggiunge a `data/dataset/aria/anagrafica/inquinanti.json`.
- **Soglie di plausibilità** (`api/aria/anagrafica_aria.py`): una cella implausibile esce dalla media per comune ma resta nel dataset per fonte («niente filtri silenziosi»).
- **Riproducibilità**: ogni dataset ha uno script o una nota con fonte, data di download e licenza.

## 5. Aria: quattro fonti, un valore al giorno

- **Fonti**: ARPA Puglia (primaria), OpenAQ, EEA (solo stazioni del Salento) e Copernicus CAMS (modellato, 0,1°). La **ridondanza serve a validare** le fonti fra loro.
- **Un valore al giorno** per fonte, stazione e inquinante, **giorni in UTC+1**:
  - OpenAQ, EEA, CAMS: media pesata sul tempo delle misure, **senza soglia di ore**, con la completezza in nota;
  - ARPA si tiene com'è (massimo giornaliero per NO2, O3, SO2, CO).
- **ARPA a sé**; OpenAQ + EEA + CAMS formano un gruppo di validazione diretta. Il confronto con ARPA è qualitativo dove la statistica è diversa.
- **Inquinanti di riferimento della dashboard**: CO, NO2, O3, PM2.5, SO2. Gli altri (C6H6, H2S, IPA, PM10) restano nel dataset.
- **Valori limite autorevoli** nel codice (`RIFERIMENTI_NORMATIVI` in `api/aria/anagrafica_aria.py`): D.Lgs. 155/2010, OMS 2021, UE 2024/2881. Il confronto si fa **solo a parità di statistica**, altrimenti «non confrontabile» (O3 quasi sempre). L'**indice di salubrità** di una zona è il **peggiore inquinante**, senza pesi.
- **Vista «Tutte»** (solo presentazione): media delle fonti concordi per comune × giorno, con ARPA solo per PM10 e PM2.5. È l'eccezione dichiarata alla regola «le fonti non si mediano».
- **Casi singoli**: centraline private VERSALIS incluse come le altre; stazioni HabitatMap di OpenAQ incluse e segnalate; «Surbo - Croce» assegnata a Lecce; «Monopoli - Aldo Moro» esclusa (fuori Salento); il salto di unità del CO di OpenAQ a maggio 2026 si lascia com'è; gli orari di OpenAQ non si correggono (si converte fedelmente l'orario dichiarato: limite noto).

## 6. Dato modellato e aggregazione

- **CAMS** è un modello, non una misura. Da cella a comune con **media pesata sull'area**; per ogni comune è una **stazione virtuale** che **non entra nella media delle stazioni fisiche**.
- **Dato modellato sempre dichiarato**: dove non ci sono stazioni (124 comuni su 145, 8 distretti su 20) c'è solo CAMS; le correlazioni si calcolano comunque, etichettate come modellate.
- **Stazione → comune**: media delle **stazioni fisiche** con valore. **Comune → distretto**: media **pesata sui residenti** (concentrazioni, temperature) o **somma** (conteggi). Codice in `api/comune/aggregazione.py`.
- **Grane**: aria comune × giorno; salute e calore distretto × mese; **confronto fra domini a distretto × mese**. Le zone senza stazioni fisiche sono marcate (`senza_stazioni`).
- **Dati mensili e annuali** mostrati come media giornaliera con **`~`**: solo presentazione, mai nelle correlazioni.
- **Territorio**: Salento = province di Lecce, Brindisi, Taranto, divise in **20 distretti socio-sanitari** e **145 comuni** (Presicce-Acquarica è un comune solo, 075098, come lo pubblica ISTAT). Anagrafiche relazionali (PK/FK) in `data/territorio/anagrafica/` e `data/dataset/*/anagrafica/`.

## 7. Salute

- **Decessi ISTAT** comunali giornalieri, tutte le cause, somma delle classi d'età. Validati per ridondanza con il bilancio demografico mensile ISTAT ed Eurostat. Nessuna fonte pubblica dà cause o ricoveri sotto la provincia.
- **Ricoveri ISTAT Health for All** (dimissioni provincia × anno): solo informativi, non entrano nelle correlazioni.
- **Dati sanitari simulati**: ricoveri per causa, accessi in pronto soccorso e accessi in PS degli assistiti in ADI, per comune × giorno, in due scenari (`nullo`, `letteratura`; in uso `letteratura`), calibrati su dati pubblici. **Mai presentati come reali**: in dashboard la beuta col tooltip «Dato simulato, non reale».

## 8. Calore urbano (UHRI)

**UHRI** = Urban Heat Island Mitigation & Resilience: **quattro grandezze mostrate accanto, senza punteggio unico**, senza pesi né formule nostre.

| Componente | Grana | Fonte | Stato |
|---|---|---|---|
| Esposizione al calore (T media, max, min a 2 m) | comune × giorno | ERA5-Land + ARPA meteo | in uso |
| Intensità dell'isola di calore (LST urbano − rurale) | comune × anno | Landsat C2 L2 | rimandata |
| Copertura arborea | comune | CLMS Tree Cover Density 2024 | in `territorio.json` |
| Suolo impermeabile | comune | CLMS Imperviousness Density 2018 | in `territorio.json` |

- **ERA5-Land** è la fonte primaria (media pesata sull'area; cella di terra più vicina per Corsano e Patù; latenza di circa 6 giorni); **ARPA meteo** è la seconda fonte e non si media con la prima. Soglie fisse di caldo: T max ≥ 30/35 °C, T min ≥ 20/25 °C.
- **CLMS**: media dei pixel per comune.
- Nessun dato UHI pubblico copre il Salento; per Lecce esiste letteratura misurata come termine di paragone.

## 9. Privacy

Si lavora su dati pubblici e aggregati; il rischio principale è la **re-identificazione** con zone o celle troppo piccole.

- **Decessi mai per comune × giorno**: in dashboard almeno **distretto × mese** (anche per un comune si mostra il suo distretto, dichiarandolo).
- I dati sanitari simulati sono sintetici: questa regola non li riguarda e i comuni sono ammessi.
- **Mai committare** microdati sanitari o dati personali: `data/raw/` e `data/interim/` sono esclusi dal repository.
