# Lista dataset — Calore / isola di calore urbana (UHRI)

Terzo parametro del progetto, accanto ad **aria** e **salute**: la misura del **calore urbano** per comune, da correlare con mortalità/ricoveri. Indice generale: `Lista_dataset.md`. Ricognizione completa delle fonti: `ricerca/`ricerca/03_Datasets_List.md` del repository Presentation del repository Presentation.

> **Nota sul nome.** `UHRI` sta per **Urban Heat Island (UHI) Mitigation & Resilience** — *la misurazione delle isole di calore urbano* (definizione data da Matteo il 01/10/2026). Non è un acronimo pubblicato: la ricerca del 01/10/2026 ha trovato solo famiglie di indici affini (UHI/SUHI *intensity*, *Heat Vulnerability Index*, HERI di Ibimet-CNR). In tesi va quindi presentato come **nome proprio del progetto**, con la definizione operativa qui sotto, non come indice standard citabile.

---

## 1. Definizione operativa — chiusa il 01/10/2026

L'UHRI **non è un punteggio unico** per comune: è un insieme di **due misure** e **due fattori**, mostrati accanto fra loro, senza pesi né formule nostre. La scelta (fra tre alternative, incluso un indice composito 0-100) è stata presa per non dover difendere in tesi dei pesi arbitrari e per restare dentro la regola "analisi esplorativa, non causale" (docs/Regole_dei_dati.md).

| Componente | Che cos'è | Grana | Stato |
|---|---|---|---|
| **1. Esposizione al calore** | temperatura dell'aria a 2 m — media, massima e minima giornaliera; da qui giornate di caldo estremo e notti tropicali | **comune × giorno** (serie temporale, da incrociare con i decessi giornalieri ISTAT) | **nell'MVP** |
| **2. Intensità dell'isola di calore** | differenza di temperatura superficiale (LST) fra area urbanizzata e campagna circostante, media sulla stagione calda | comune, un valore per anno/stagione | **rimandata** dopo l'MVP (v. §3.3 e §4) |
| **3. Mitigazione — copertura arborea** | % di chioma arborea sulla superficie comunale | comune, un valore per edizione (annuale) | attributo semi-statico |
| **4. Mitigazione — suolo impermeabile** | % di suolo sigillato (asfalto, edificato) sulla superficie comunale | comune, un valore per edizione (triennale) | attributo semi-statico |

**Perché 3 e 4 non sono "il" parametro**: la copertura arborea è una **causa** del raffrescamento, non una misura di calore. Nella prima formulazione del 01/10/2026 l'UHRI era stato inteso come la sola % di alberi per comune; chiarita la definizione, gli alberi e il suolo sigillato diventano i **fattori di mitigazione** che spiegano l'isola di calore, mentre la misura è la temperatura.

**Collocazione nella pipeline** (decisa il 01/10/2026): le componenti 1 e 2 formano un **terzo dominio dati `calore/`**, parallelo ad `aria/` e `salute/` (`data/dataset/calore/`, `api/calore/`, `scripts/calore/`, `data/interim/calore/`), con le stesse regole multi-fonte e gli stessi stati `VALORE` / `NULL` / `NO_DATA` del dataset aria (docs/Regole_dei_dati.md). Le componenti 3 e 4, che cambiano al più una volta l'anno, diventano **campi per comune nell'anagrafica territorio** (`data/territorio/anagrafica/territorio.json`), accanto a residenti e superficie.

---

## 2. Perché non esiste un dato UHI già pronto per il Salento

Verificato il 01/10/2026. Il dato europeo di riferimento sull'isola di calore è il modello **UrbClim** di VITO applicato alla rianalisi ERA5, distribuito in due forme:

- **C3S — "Climate variables for cities in Europe from 2008 to 2017"** (Climate Data Store, 100 m, orario, CC BY): copre **100 città europee** scelte dalla comunità *health*. In Italia: Bari, Bologna, Genova, Milano, Napoli, Padova, Palermo, Roma, Trieste. **In Puglia solo Bari** → fuori dal Salento. Il dataset è inoltre **marcato come deprecato dal 10/05/2024**.
  Fonte: https://cds.climate.copernicus.eu/datasets/sis-urban-climate-cities
- **EEA — "Urban Heat Island (UHI) intensity modelling, Jan. 2020"** (catalogo SDI dell'EEA, raster 100 m, EPSG:3035, CC BY 4.0): la stessa simulazione UrbClim pubblicata come intensità UHI estiva (giugno-agosto: temperatura media meno il 10° percentile rurale), **stesse 100 città** → stesso limite.
  Fonte: https://sdi.eea.europa.eu/catalogue/srv/api/records/45b703bb-d4f3-4eaa-8b73-13fde2041f01
- Un'estensione a **142 città** nel mondo (Zenodo, https://zenodo.org/records/13361538) includerebbe **Taranto**, ma non Lecce né Brindisi: eventuale riscontro per la sola Taranto, non fonte del progetto.

**Conseguenza**: per i 146 comuni del Salento l'isola di calore **va calcolata da noi**, dalle fonti della sezione 3. È la stessa situazione già vista per il dato sanitario: il dato pronto, alla grana che serve, non esiste.

**Letteratura locale di riferimento**: l'intensità dell'isola di calore di **Lecce** è stata misurata e pubblicata (Pappaccogli et al., 2024, v. `Bibliografia.md` del repository Presentation): studio su stagionalità, ciclo diurno e influenza delle ondate di calore. Serve come **riferimento metodologico e termine di paragone** per i valori che calcoleremo, non come dataset.

---

## 3. Fonti — scelte il 01/10/2026

### 3.1 Esposizione al calore (componente 1) — fonte primaria: Copernicus ERA5-Land ✅

- **Cosa preleviamo**: temperatura dell'aria a 2 m oraria → media / massima / minima **giornaliera per comune**.
- **Perché primaria**: è l'unica fonte gratuita, senza quote e con **copertura di tutti i 146 comuni** su tutta la finestra temporale del progetto (serie dal 1950, quindi anche i 5-10 anni richiesti). La chiave Copernicus è **già nel repo** (`COPERNICUS_API_KEY` in `.env`) e `cdsapi` è **già fra le dipendenze** (aggiunta per CAMS, v. `Copernicus_CAMS.md`): nessun costo e nessun servizio nuovo.
- **Limite principale**: è una **rianalisi** (modello), non una misura, a **0,1° (~9 km)**: non distingue il centro urbano dalla campagna dentro lo stesso comune. Per l'isola di calore in senso stretto serve la componente 2 (LST).
- **Scheda**: `ERA5_Land.md`.

### 3.2 Esposizione al calore — validazione per ridondanza: ARPA Puglia rete meteo ✅

- **Cosa preleviamo**: temperatura oraria **misurata** dalle stazioni meteo ARPA, con i codici di validazione della fonte, per confrontarla con ERA5-Land cella per cella (stessa logica di validazione già usata per l'aria fra ARPA, OpenAQ ed EEA — docs/Regole_dei_dati.md).
- **Perché è un buon riscontro**: 19 stazioni meteo sono **co-localizzate con le centraline della qualità dell'aria** (rete RRQA) → ricadono nell'anagrafica stazioni che già esiste, e si leggono con il client CKAN già scritto (`api/comune/dati_puglia_ckan.py`). Licenza **CC BY 4.0**, coerente con la decisione già presa per tutti i dataset ARPA su dati.puglia.it.
- **Limite**: via canale accessibile ci sono **solo il 2023 e il 2024**, e nel Salento ~13 stazioni su 146 comuni. L'API ufficiale è su `cloud.arpa.puglia.it` (irraggiungibile, come per l'aria) e sull'host legacy `old.arpa.puglia.it`, da cui prendiamo l'aria, il meteo **non è esposto** (404 verificato il 01/10/2026 su `meteo.jsp`, `meteorrqa.jsp`, `meteo_rrqa.jsp`, `datimeteo.jsp`, `dati_meteo.jsp`, `stazionimeteo.jsp`).
- **Scheda**: `ARPA_Meteo.md`.

### 3.3 Intensità dell'isola di calore (componente 2) — Landsat Collection 2 Level-2 Surface Temperature 🕐

- **Cosa preleveremmo**: temperatura superficiale (ST) a **30 m**, archivio dal 1984, da cui l'intensità SUHI per comune = LST dell'area urbanizzata − LST rurale di riferimento, mediata sulla stagione calda.
- **Perché è la strada giusta per l'UHI**: è l'unica risoluzione che distingue il tessuto urbano dalla campagna all'interno di un comune salentino. Il prodotto è gratuito e senza restrizioni d'uso (USGS), accessibile via API STAC senza chiave (es. Microsoft Planetary Computer, `https://planetarycomputer.microsoft.com/api/stac/v1`) oltre che dai canali USGS.
- **Perché è rimandata**: ~1 scena ogni 8-16 giorni e **solo a cielo sereno** (nessuna serie giornaliera), raster da scaricare e ritagliare con statistica zonale, nuove dipendenze (`rasterio`/GDAL) e giorni di lavoro che la finestra fino al 24/10/2026 non concede. Decisione del 01/10/2026: **fuori dall'MVP**, documentata in tesi come sviluppo successivo.
- Alternativa a grana più grossa valutata: **Sentinel-3 SLSTR LST** (~1 km, due passaggi al giorno incluso quello notturno) — più adatta alla serie temporale, troppo grossa per il contrasto urbano/rurale di comuni piccoli.

### 3.4 Mitigazione — Copernicus Tree Cover Density (copertura arborea) ✅

- **Cosa preleveremmo**: % di copertura arborea per pixel (0-100), **10 m**, edizioni annuali dal 2018 (o 20 m, triennale, per 2012/2015/2018) → statistica zonale per comune su `data/territorio/confini/comuni_salento.geojson`.
- **Perché**: unica fonte di copertura arborea con **tutti i 146 comuni**.
- **Fonte**: https://land.copernicus.eu/en/products/high-resolution-layer-forests-and-tree-cover/tree-cover-density-2018-present-raster-10-m-europe-yearly
- **Licenza**: accesso pieno, libero e gratuito (Reg. delegato UE 1159/2013), con obbligo di citare la fonte e dichiarare le modifiche — **confermata il 15/10/2026** dal record EEA.
- **Stato (16/10/2026)**: ✅ **calcolato per i 145 comuni** sull'edizione **2024** scaricata dal portale CLMS (media 12,5%). **Si usa solo il 2024**: l'edizione 2018 (anche quella del servizio pubblico EEA) è scartata. In mappa come vista «Alberi».
- **Limiti**: nessuna API "per comune" (si chiede un riquadro per comune e si calcola la media); media sull'intero comune, non sull'area urbana; una sola edizione (2018) dai servizi pubblici.

### 3.5 Mitigazione — Copernicus Imperviousness Density (suolo impermeabile) ✅ *(aggiunta il 01/10/2026)*

- **Cosa preleveremmo**: grado di impermeabilizzazione/sigillatura del suolo per pixel (0-100%), **10 m** (disponibile anche a 100 m), edizione 2018, serie triennale → statistica zonale per comune.
- **Perché**: nella letteratura sull'isola di calore il suolo sigillato spiega soprattutto il **calore notturno**, mentre la chioma arborea agisce di giorno: i due fattori insieme descrivono la capacità di mitigazione di un comune molto meglio della sola % di alberi.
- **Fonte**: https://land.copernicus.eu/en/products/high-resolution-layer-imperviousness/imperviousness-density-2018
- **Licenza**: come sopra, confermata il 15/10/2026.
- **Stato (16/10/2026)**: ✅ calcolato per i 145 comuni (edizione 2018, media 6,4%; è l'ultima disponibile sul portale), identico al servizio EEA. In mappa come vista «Suolo». V. `clms/CLMS.md`.

### 3.6 Riscontri secondari (nessuno è fonte primaria)

| Fonte | Cosa darebbe | Perché non primaria |
|---|---|---|
| **ESA WorldCover** (10 m, 2020-2021, CC BY 4.0) — https://esa-worldcover.org/en | classe "Tree cover" (binaria, ≥10% di chioma) | solo due anni e classe binaria invece della percentuale continua; utile come riscontro del TCD |
| **ISTAT — Ambiente urbano / verde urbano** (`609_1_DF_DCCV_URBANENV_18`, SDMX, CC BY 4.0) — scheda in `ISTAT.md` canale E | % di verde urbano e di aree protette sulla superficie comunale, parchi storici per area edificata, 2016-2024 | copre solo i **3 capoluoghi** del Salento (Lecce, Brindisi, Taranto), non gli altri 142 comuni. **Confermata il 18/10/2026 come sola fonte di confronto** con il Tree Cover Density sui tre capoluoghi: non entra in dataset né in anagrafica |
| **Copernicus ERA5-HEAT / UTCI** (`derived-utci-historical`, 0,25°, 1979→oggi, CDS) | indice di stress termico percepito (UTCI) e temperatura media radiante | ~28 km: troppo grosso per la grana comunale; eventuale riferimento metodologico in tesi sullo stress termico |

### 3.7 Mortalità da caldo già aggregata: non esiste per il Salento ⛔

Confermato il 01/10/2026 (coerente con `ISS.md`): **ISS/SiSMG** copre 54 città e nel Salento solo **Taranto**, senza dati grezzi (soli bollettini PDF); l'indicatore **ISPRA "Ondate di calore e mortalità"** usa la stessa base delle città del Piano nazionale prevenzione effetti del caldo. Nessuna delle due dà Lecce o Brindisi.

**Conseguenza**: la correlazione caldo ↔ salute si fa con il **dataset salute già pianificato** (decessi comunali giornalieri ISTAT), incrociato per data con le giornate di caldo della componente 1. Nessuna fonte "mortalità da caldo" da integrare.

---

## 4. Che cosa entra nell'MVP (24/10/2026)

Deciso il 01/10/2026, con il dataset salute ancora non integrato e tre settimane alla consegna:

- **Sì**: serie **temperatura giornaliera per comune** da ERA5-Land (componente 1); **copertura arborea** e **suolo impermeabile** come attributi comunali (componenti 3 e 4).
- **No**: intensità SUHI da LST satellitare (componente 2) → documentata in tesi come sviluppo futuro.
- **Sì, se il tempo lo permette**: validazione ERA5-Land ↔ ARPA meteo su 2023-2024, che riusa la logica di report di ridondanza già scritta per l'aria (`api/aria/report_aria.py`).

---

## 5. Punti aperti

1. **Da cella ERA5-Land (9 km) a comune**: cella che contiene il centroide, oppure media pesata sull'area di sovrapposizione del confine comunale. È **lo stesso problema già aperto per Copernicus/CAMS**: da decidere una volta per entrambi, con la stessa regola.
2. ~~**Soglie di "caldo"**~~ — **chiuso il 14/10/2026**: soglie fisse 30/35 °C (T max) e 20/25 °C (T min), v. `Soglie_Caldo.md`. Testo originale della domanda: cosa conta come giornata di caldo estremo e notte tropicale — soglia fissa (es. T max ≥ 35 °C, T min ≥ 20 °C) o percentile locale della serie (es. 95° percentile estivo del comune). La seconda è più difendibile in tesi, la prima più leggibile in dashboard.
3. ~~**Latenza di ERA5-Land**~~ — **chiuso il 03/11/2026**: **6 giorni** (ultimo giorno = oggi − 6), misurata col catalogo CDS e con una richiesta oltre il limite; il CDS omette senza errore i giorni non ancora pubblicati, che restano `NO_DATA` (v. `era5_land/ERA5_Land.md` §3). La variante giornaliera è quella in uso dal 09/10. Testo originale: la pagina CDS dichiara aggiornamento giornaliero, ma la rianalisi arriva con qualche giorno di ritardo → da misurare alla prima chiamata reale e da marcare `NO_DATA` sui giorni non ancora coperti. Da verificare anche la variante con statistiche giornaliere già calcolate (`derived-era5-land-daily-statistics`), che eviterebbe di scaricare le 24 ore.
4. ~~**Statistica zonale dei raster**~~ — **chiuso il 15/10/2026**: `rasterio` 1.5.2 (wheel con GDAL, nessuna installazione di sistema), `api/calore/clms.py` e `scripts/calore/calcola_mitigazione_comuni.py`; 145 comuni in pochi minuti. Restano aperti il passaggio all'**area urbana** (maschera Urban Atlas/CLC) e le edizioni più recenti (solo da portale CLMS con EU Login).
5. ~~**Licenza Copernicus CLMS**~~ — **chiuso il 15/10/2026**: testo confermato dal record EEA (v. `clms/CLMS.md` §3).
6. **Grana del confronto calore ↔ salute**: eredita il punto già aperto per l'aria — la temperatura è giornaliera, la salute quasi sempre annuale/provinciale.
7. **Serie storica del meteo misurato**: se servisse oltre il 2023-2024, l'unica via è una richiesta formale al Centro Funzionale Decentrato della Protezione Civile Puglia (rete di 157 termometri, dati su richiesta) o ad Assocodipuglia per la rete agrometeorologica — con i tempi che questo comporta.
