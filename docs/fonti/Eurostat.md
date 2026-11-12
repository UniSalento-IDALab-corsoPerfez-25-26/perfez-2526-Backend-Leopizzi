# Eurostat — decessi settimanali per provincia (NUTS 3) e cause di morte

Scheda di riferimento per il servizio dati, secondo la convenzione del repo. **Stato al 02/10/2026: client scritto (`api/salute/eurostat.py`) e usato per validare i decessi ISTAT** (`scripts/salute/valida_decessi.py` → `Report_validazione_decessi.md`); non entra nel dataset salute, è un controllo di ridondanza. Esito: **100 % di settimane identiche dal 2011 al 2023**, differenze solo sul 2024 (63,5 %) e 2025 (76,3 %), cioè gli anni non ancora rivisti da Eurostat. Indice delle fonti salute: `Lista_dataset_salute.md`.

Tutto ciò che segue è stato **verificato il 01/10/2026 con chiamate reali** all'API.

## Perché Eurostat entra nel progetto: il caso "ESDS"

La ricognizione iniziale riportava la fonte citata da Matteo come **ESDS — European Statistical Data Support**, con ente e URL "da verificare". **Verificato il 01/10/2026: ESDS non è una fonte di dati.** La pagina ISTAT "European data support" lo dice esplicitamente: «L'European statistical data support (ESDS) fa parte di un network europeo **coordinato da Eurostat** e fornisce **assistenza** per la ricerca dei dati statistici armonizzati e comparabili relativi agli Stati membri dell'UE» (<https://www.istat.it/attivita-e-servizi-per-tipo-di-utenti/tutti/european-data-support/>).

Quindi ESDS è lo **sportello di assistenza** (in Italia ospitato da ISTAT) che aiuta a trovare i dati; i **dati** sono quelli della **banca dati Eurostat**. Il punto aperto su "ESDS" si chiude così: dove i documenti di ricerca iniziali parlano di ESDS come fonte, la fonte vera da citare è **Eurostat** (ed eventualmente ESDS come canale di supporto a cui scrivere per chiarimenti).

## API

- Base: `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/<dataset>`
- Formato: `?format=JSON&lang=en` (JSON-stat 2.0) — nessuna chiave, nessuna registrazione
- Filtri: `&geo=<codice>` (ripetibile), `&time=<periodo>` (ripetibile), `&sinceTimePeriod=`, `&lastTimePeriod=`
- Catalogo completo dei dataset: `https://ec.europa.eu/eurostat/api/dissemination/catalogue/toc/txt?lang=en` (~2 MB, 12.237 righe)
- Codici territoriali: gli stessi NUTS usati da ISTAT via SDMX — **`ITF45` Lecce, `ITF44` Brindisi, `ITF43` Taranto**, `ITF4` Puglia
- **Licenza: CC BY 4.0** secondo la politica di riuso Eurostat (citare Eurostat come fonte; la copia esatta della dicitura va presa dalla pagina del dataset prima di citarla in tesi — **non verificata** parola per parola).

## Dataset rilevanti

| Dataset | Contenuto | Grana | Periodo dichiarato |
|---|---|---|---|
| **`demo_r_mwk3_t`** | **decessi per settimana e provincia (NUTS 3)** | provincia × settimana | 2000-W01 → 2026-W32 |
| `demo_r_mwk3_ts` | come sopra, per sesso | provincia × settimana × sesso | 2000-W01 → 2026-W32 |
| `demo_r_mwk3_10` / `_20` | come sopra, per classi d'età di 10 / 20 anni | provincia × settimana × età | 2000-W01 → 2026-W32 |
| `demo_r_mweek3` | come sopra, classi d'età di 5 anni | provincia × settimana × età × sesso | 2000-W01 → 2026-W32 |
| `demo_r_magec3` | decessi per classe d'età, sesso e provincia | provincia × anno | 2013 → 2024 |
| `hlth_cd_acdr2`, `hlth_cd_asdr2` | **cause di morte**, tassi grezzi e standardizzati | **solo NUTS 2** (= Puglia intera) | 2011 → 2023 |

## Copertura reale per il Salento (verificata)

- `demo_r_mwk3_t` per `ITF45` (Lecce): dati **dal 2011-W01 al 2026-W27** (809 settimane valorizzate su 971 richieste a partire dal 2008); **prima del 2011 la serie è vuota** per questa provincia, e le ultime settimane sono `null` (ritardo di pubblicazione di qualche mese; aggiornamento dichiarato 16/09/2026).
- Valori di esempio: Lecce 2015-W30 = 233, 2024-W30 = 199, 2026-W20 = 170, 2026-W27 = 166; Taranto 2026-W27 = 98; Brindisi 2026-W27 = 75.

## A cosa ci serve

- **Validazione per ridondanza**, come EEA e OpenAQ fanno con ARPA per l'aria: Eurostat ridistribuisce i decessi che ISTAT gli trasmette, quindi la somma settimanale dei decessi comunali ISTAT per provincia deve coincidere con `demo_r_mwk3_t`. È un controllo a costo quasi zero (payload di pochi KB contro gli 827 MB del CSV ISTAT).
- **Scorciatoia** quando basta la grana provinciale/settimanale: niente download da centinaia di MB.
- **Non** aggiunge nulla sulle cause di morte: lì si ferma a NUTS 2 (Puglia), peggio di ISTAT che arriva alla provincia.
- Nota: la serie parte dal 2011 come quella ISTAT, quindi **non** allunga la copertura storica.
