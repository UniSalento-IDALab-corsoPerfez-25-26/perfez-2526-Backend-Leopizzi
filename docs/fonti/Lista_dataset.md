# Lista dataset — Indice

Il progetto costruisce **due dataset separati**, da mettere a confronto in serie temporale per distretto socio-sanitario, più un **terzo dominio** deciso il 01/10/2026 (UHRI, calore urbano):

| Dataset | Cosa contiene | Fonti in uso / candidate | Output (gitignored) |
|---|---|---|---|
| **Aria** | qualità dell'aria misurata (e in futuro modellata) | `aria/Lista_dataset_aria.md` — ARPA Puglia, OpenAQ, EEA | `data/interim/aria/` |
| **Salute** | mortalità, ricoveri, patologie della popolazione | `salute/Lista_dataset_salute.md` — **verificate il 01/10/2026**: ISTAT (decessi comunali giornalieri, cause di morte via SDMX, Health for All con le dimissioni respiratorie provinciali), PNE/AGENAS (ospedalizzazione BPCO/asma per ASL), Eurostat (decessi settimanali per provincia, validazione), AReSS Puglia (open data CKAN). Schede in `salute/istat/`, `salute/pne_agenas/`, `salute/eurostat/`, `salute/aress_puglia/`; nessuna ancora integrata nel codice | `data/interim/salute/` |
| **Calore/UHRI** *(deciso 01/10/2026, nessuna fonte ancora integrata)* | temperatura dell'aria giornaliera per comune (esposizione al calore) e, dopo l'MVP, intensità dell'isola di calore; copertura arborea e suolo impermeabile come fattori di mitigazione, tenuti nell'anagrafica territorio | `calore/Lista_dataset_calore.md` — **ERA5-Land** (primaria), **ARPA meteo** (validazione, 2023-2024), Copernicus Tree Cover Density e Imperviousness Density; Landsat LST rimandato | `data/interim/calore/` |

Aria e salute seguono le stesse regole (v. docs/Regole_dei_dati.md): JSON annidato **provincia → distretto → … → giorno → fonte → inquinante/indicatore**, un valore per fonte (mai aggregato tra fonti), e ogni cella dice perché un valore c'è o manca: `VALORE`, `NULL` (la fonte copre ma il valore non è usabile) o `NO_DATA` (la fonte non copre). Il dominio **calore** segue le stesse regole per la serie giornaliera di temperatura; i due fattori di mitigazione, che cambiano al più una volta l'anno, stanno invece nell'anagrafica territorio — v. `calore/Lista_dataset_calore.md`. Il confronto aria/UHRI ↔ salute è sempre **esplorativo, non causale**.

**Stato reale di tutte le fonti, incroci e confronti per granularità:** `Comparazione_fonti.md` (02/10/2026).

Regole comuni:

- Ogni lista tiene traccia delle fonti **realmente usate** (non della ricognizione completa), con cosa se ne preleva, fonte e licenza. Ricognizione completa: `ricerca/`ricerca/03_Datasets_List.md` del repository Presentation del repository Presentation.
- Accesso ai dati sempre via chiamate API dirette, senza database (docs/Architettura.md); `data/raw/` e `data/interim/` sono in `.gitignore`.
- Ogni nuovo servizio dati ha una sua cartella con un `.md` di riferimento (es. `aria/openaq/OpenAQ.md`).

---

## Fonti territoriali (comuni ad aria e salute)

Servono a ricondurre stazioni e dati comunali ai distretti. Codice condiviso: `api/comune/distretti_salento.py`; script: `scripts/territorio/costruisci_distretti_salento.py`.

### Regione Puglia — Anagrafe distretti socio-sanitari

**Cosa ci procuriamo**: elenco e anagrafica dei distretti socio-sanitari delle ASL di Lecce, Taranto e Brindisi, usati come unità di zonizzazione (v. docs/Regole_dei_dati.md) per aggregare aria e salute e per disegnare i confini sulla mappa OSM.

- Dataset: https://dati.puglia.it/ckan/dataset/anagrafe-distretti-socio-sanitari
  - **Licenza**: Italian Open Data License 2.0 (IODL 2.0)
  - **Formato**: CSV, XML (+ XSD, ODS)
  - **Ente**: Regione Puglia
  - **Copia locale**: `data/territorio/lista_presidi/Presidi_Puglia.json` (45 distretti pugliesi; per il Salento: 10 in provincia di Lecce, 4 di Brindisi, 6 di Taranto), con elenco dei comuni e codici ISTAT per ogni distretto
  - **Limite noto**: il dataset in anagrafica copre il periodo 01/10/2015–31/07/2017 (aggiornamento dichiarato annuale, ultimo update rilevato 06/12/2025) — **da verificare se i confini/l'elenco dei distretti sono ancora quelli attuali** prima di usarli per disegnare la mappa.

### Comuni-Italiani.it (Prometheo Srl)

**Cosa ci procuriamo**: elenco dei comuni delle tre province (Lecce `075`, Brindisi `074`, Taranto `073`) con residenti, densità (ab./km²) e numero di famiglie; serve come anagrafica comuni e come peso di popolazione per aggregare i dati per distretto (anche per calcolare tassi di mortalità/ricovero per abitante).

- Sito: https://www.comuni-italiani.it/ — elenco per provincia es. https://www.comuni-italiani.it/075/lista.html
  - **Licenza**: nessuna licenza open dichiarata; "© 2004/2023 Prometheo" (non è un dataset open data). I dati di popolazione riportati sono di origine ISTAT (note sui dati: https://www.comuni-italiani.it/note.html); il sito declina responsabilità su errori/aggiornamento. **Da chiarire come citare/riusare in tesi**: in alternativa, ricavare residenti e codici comune direttamente da ISTAT (CC BY 4.0).
  - **Formato**: pagine HTML (nessuna API); copie locali estratte in `data/territorio/lista_presidi/Comuni_Lecce.json`, `Comuni_Brindisi.json`, `Comuni_Taranto.json`
  - **Limite noto**: il sito **non** indica l'appartenenza dei comuni ai distretti socio-sanitari. La mappatura comune → distretto viene dall'anagrafica Regione Puglia (`data/territorio/lista_presidi/Presidi_Puglia.json`, campi `COMUNI` e `COD_ISTAT_COMUNI` per distretto), da incrociare con questa lista per nome/codice comune.
