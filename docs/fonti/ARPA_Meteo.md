# ARPA Puglia — Rete meteo (temperatura misurata)

Scheda della fonte, **verificata il 01/10/2026**. Ruolo nel progetto: **validazione per ridondanza** della serie di temperatura di ERA5-Land (v. `Lista_dataset_calore.md` §3.2), non fonte primaria — la serie accessibile copre solo 2023-2024.

- **Servizio**: ARPA Puglia, monitoraggio meteorologico.
- **Portale dati**: https://dati.puglia.it/ckan/dataset?q=meteo (CKAN della Regione Puglia, lo stesso già usato per l'aria).
- **Linea guida API**: "Linea guida interoperabilità ARPAP API - Meteo RRQA - ITA.pdf", allegata al dataset `dati-meteo-rrqa-2024`.
- **Licenza**: **CC BY 4.0** (dichiarata `CC-BY-4.0` nei metadati CKAN, coerente con la decisione di progetto sui dataset ARPA su dati.puglia.it — docs/Regole_dei_dati.md).

> **Aggiornamento 14/10/2026 — il limite 2023-2024 è superato.** Le risorse CKAN puntano a un host che la verifica del 01/10 non aveva provato: **`https://dati.arpa.puglia.it/Meteo/`**, che serve CSV annuali **dal 2020 al 2026 (fino a ieri)**, senza chiave. Endpoint: `stazioni.jsp` (GeoJSON, 27 stazioni), `dati_rrqa.jsp?id_station=<id>&year=<aaaa>` (rete RRQA, **oraria**, `temperatura`) e `dati.jsp?id_station=<id>&year=<aaaa>` (rete dedicata, **ogni 30 minuti**, `temperatura_min|avg|max`). Fuori da 2020-2026 risponde HTTP 400. `data_ora` è in **UTC+1 fisso** (verificato sul ciclo diurno). Le stazioni nel Salento sono **15**, non 11: rete dedicata 3 (Taranto), 4 (Brindisi), 5 (Lecce); RRQA 6 (Taranto S. Vito), 7 (Brindisi SISRI), 10 (Lecce Cerrate), 12 (Torchiarolo), 13 (Galatina), 14 (Cisternino), 15 (S. Pancrazio), 18 (Grottaglie), 23 (Francavilla F.), **24 (Maglie)**, 25 (Massafra), **26 (Brindisi Cappuccini)**. L'ambiguità «18 per Maglie e Grottaglie» era dei metadati CKAN: Maglie è 24. Client: `api/calore/arpa_meteo.py`; cache: `scripts/calore/scarica_arpa_meteo.py` → `data/raw/calore/arpa_meteo/`. Le sezioni 2-5 qui sotto descrivono la verifica originale del 01/10 e sono superate dove contraddicono questo riquadro.

## 1. Le due reti

ARPA Puglia gestisce due reti meteorologiche distinte:

1. **Rete dedicata** — 5 stazioni automatiche presso le sedi provinciali: Bari, Brindisi, Foggia, **Lecce**, **Taranto** (nel Salento: Brindisi, Lecce, Taranto).
2. **Rete meteo a corredo della RRQA** — 19 stazioni **co-localizzate con le centraline della qualità dell'aria**. Nel Salento (province LE, BR, TA):

| Stazione | `id_station` | Provincia |
|---|---|---|
| Brindisi area industriale SISRI | 7 | BR |
| Cisternino | 14 | BR |
| Francavilla Fontana *(scritta "Fancavilla" nei metadati)* | 23 | BR |
| San Pancrazio Salentino | 15 | BR |
| Torchiarolo | 12 | BR |
| Galatina | 13 | LE |
| Lecce Cerrate | 10 | LE |
| Maglie | 18 *(da verificare: i metadati ripetono 18 anche per Grottaglie)* | LE |
| Grottaglie | 18 *(idem)* | TA |
| Massafra | 25 | TA |
| Taranto San Vito | 6 | TA |

Fuori Salento: Andria (11), Barletta Casardi (17), Candela (22), Carbonara (16), Manfredonia (20), Molfetta (21), Monopoli (9), San Severo (19).

**Perché conta la co-localizzazione**: queste stazioni sono le stesse della RRQA già presenti in `stazioni.json`, quindi la temperatura si aggancia all'anagrafica esistente senza nuovo abbinamento per coordinate.

## 2. Dataset su CKAN (canale accessibile)

| Dataset CKAN | Contenuto | Grana |
|---|---|---|
| `dati-meteo-2023` | rete dedicata, 5 capoluoghi, anno 2023 | oraria per stazione |
| `dati-meteo-2024` | rete dedicata, 5 capoluoghi, anno 2024 | oraria per stazione |
| `dati-meteo-rrqa-2024` | rete RRQA, 19 stazioni, anno 2024 | oraria per stazione |
| `stazioni-meteo` | anagrafica delle stazioni meteo e UV (GeoJSON) | — |
| `musica-dati-meteo-near-real-time-fonte-arpa` | dati meteo *near real time* (riuso di terzi) | da verificare |

Le risorse CSV hanno `datastore_active: true`, quindi sono interrogabili in SQL con il client già scritto (`api/comune/dati_puglia_ckan.py`, `datastore_search` / `datastore_search_sql`).

**Copertura verificata**: 2023 e 2024 (per la RRQA solo 2024). Un anno di una stazione sono ~8.784 righe orarie (verificato su Galatina 2024, risorsa `875561dd-c213-4a48-bccd-703f975fa31f`: 8.784 record = 366 × 24).

## 3. Tracciato record

Campi di una risorsa oraria (verificati su Galatina 2024):

`_id`, `data_ora` (ISO, es. `2024-01-01T00:00:00`), `id_station`, `denominazione`, `temperatura`, `cod_validazione_temperatura`, `umidita`, `cod_validazione_umidita_rel`, `precipitazione`, `cod_validazione_precipitazione`, `velocita_vento`, `cod_validazione_velocita_vento`, `direzione_vento`, `cod_validazione_direzione_vento`, `rad_solare_globale`, `cod_validazione_rad_solare_globale`, `pressione_atmosferica`, `cod_validazione_pressione_atmosferica`, `Latitude`, `Longitude`.

**Codici di validazione** (dichiarati dalla fonte): `1` dato corretto · `2` dato sospetto · `3` dato errato · `4` dato non valido · `5` dato ricostruito · `6` dato mancante.

**Mappatura sugli stati del progetto** (docs/Regole_dei_dati.md), da applicare nel client:

| Codice fonte | Stato | Nota |
|---|---|---|
| `1` | `VALORE` | — |
| `5` | `VALORE` | nota `dato ricostruito dalla fonte` |
| `2` | `NULL` | nota `dato sospetto (cod. 2)` — proposta: scartare, non mediare |
| `3`, `4`, `6` | `NULL` | dato errato / non valido / mancante, la stazione copre ma il valore non è usabile |
| stazione/periodo non in rete | `NO_DATA` | la fonte non copre |

Esempio reale: a Galatina il 01/01/2024 la temperatura e l'umidità sono valide (cod. 1), mentre vento e radiazione solare sono `null` con cod. 6 → `NULL`.

**Valore giornaliero**: la fonte è oraria, quindi vale la regola già decisa per OpenAQ ed EEA (docs/Regole_dei_dati.md) — un solo valore al giorno per stazione, senza soglia minima di ore e con la completezza nella nota. Differenza rispetto all'aria: per il calore servono **tre statistiche** giornaliere (media, massima, minima), non una.

## 4. API diretta: non accessibile

- Endpoint ufficiale dichiarato nella linea guida: `https://cloud.arpa.puglia.it/MeteoRRQA?id_station=<id>&year=<anno>` (JSON) e `https://cloud.arpa.puglia.it/Meteo?JSONRequest={format:"CSV",year:<anno>,id_station:<id>}` (CSV). **`cloud.arpa.puglia.it` è irraggiungibile**, come già verificato per la qualità dell'aria.
- L'host legacy che usiamo per l'aria, `http://old.arpa.puglia.it/ARPA_ARIA/`, **non espone il meteo**: HTTP 404 il 01/10/2026 su `meteo.jsp`, `meteorrqa.jsp`, `meteo_rrqa.jsp`, `datimeteo.jsp`, `dati_meteo.jsp`, `stazionimeteo.jsp`.

**Conseguenza**: il meteo ARPA si legge **solo dal CKAN**, quindi solo 2023-2024, e non si aggiorna a "ieri" come l'aria. Da qui la scelta di ERA5-Land come fonte primaria del calore.

## 5. Se servisse la serie storica misurata

Due canali, entrambi su richiesta formale (fuori perimetro per la consegna del 24/10/2026):

- **Protezione Civile Puglia — Centro Funzionale Decentrato**: rete telemetrica regionale con **157 termometri** a frequenza semioraria; gli Annali Idrologici (parte I) pubblicano la termometria annuale, i dati non ancora pubblicati sono forniti **su richiesta**. https://protezionecivile.regione.puglia.it/rete-di-monitoraggio-e-dati-meteo-idrometrici
- **Assocodipuglia — rete agrometeorologica regionale**: dati in tempo reale su mappa, storico **su registrazione/richiesta**. https://www.agrometeopuglia.it/osservazioni/mappa-stazioni-puglia
