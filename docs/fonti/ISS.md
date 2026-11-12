# ISS — Istituto Superiore di Sanità (e sorveglianze collegate)

Scheda di riferimento per il servizio dati, secondo la convenzione del repo. **Stato al 01/10/2026: verificato, nessun canale utilizzabile dalla pipeline.** Indice delle fonti salute: `Lista_dataset_salute.md`.

> ⛔ **Decisione del 01/10/2026 (Matteo): l'ISS esce completamente dal perimetro.** Prima era stato tenuto il solo **ReNCaM** (§5), poi scartato anche quello perché la richiesta formale a tre ASL distinte è **troppo lenta** per la consegna del 24/10. La scheda resta come documentazione di ciò che è stato verificato: **non riproporre nessuno di questi canali**. Motivazioni in `documentazione/Scelte_Progettuali.md` del repository Presentation.

Tutto ciò che segue è stato **verificato il 01/10/2026** con chiamate reali (fetch delle pagine, download dei PDF, estrazione del testo) salvo dove indicato "non verificato".

**Sintesi: l'ISS non pubblica nessun dato di mortalità o di ricovero a grana comunale o distrettuale in forma riutilizzabile.** I suoi quattro canali danno: una sorveglianza giornaliera che nel Salento copre **la sola città di Taranto** e non pubblica dati grezzi (SiSMG); un sito di profili di salute che si ferma alla **ASL** e solo in **area riservata** agli operatori sanitari (profilidisalute.it); uno studio su aree inquinate con grana comunale ma **in forma di report, su periodi chiusi** (SENTIERI); una sorveglianza delle infezioni respiratorie **regionale e sospesa dal marzo 2026** (RespiVirNet). L'ISS è però la fonte dell'**indirizzario dei registri di mortalità**, cioè dei contatti ReNCaM delle tre ASL salentine (v. §5).

| Canale | Grana territoriale | Grana temporale | Causa / patologia | Accesso |
|---|---|---|---|---|
| **1. SiSMG** — sorveglianza mortalità giornaliera | 54 città campione (nel Salento: **solo Taranto**) | **giorno** | ❌ tutte le cause, 65+ | solo bollettini/rapporti PDF, nessun dato grezzo |
| **2. profilidisalute.it** | nazionale e regionale in chiaro; **ASL solo in area riservata** | anno | ✅ 37 cause + ospedalizzazione | sito consultabile, CSV dichiarato; nessuna API |
| **3. SENTIERI** | **comune** (solo comuni dei SIN: Taranto, Statte; area di Brindisi) | periodi chiusi pluriennali | ✅ mortalità, ricoveri, tumori, malformazioni | monografie PDF (Epidemiologia & Prevenzione) |
| **4. RespiVirNet** | **regione** | settimana | ✅ sindromi respiratorie (incidenza) | bollettini; **flussi sospesi dal 06/03/2026** |

---

## 1. SiSMG — Sistema di Sorveglianza della Mortalità Giornaliera

Attivo dal 2004, coordinato dal **Dipartimento di Epidemiologia del SSR Lazio — ASL Roma 1** per il **Ministero della Salute** (non è dell'ISS in senso stretto, ma è il canale che più si avvicina a ciò che servirebbe al progetto, ed è citato su EpiCentro).

- **Cosa contiene**: numero di **decessi giornalieri per tutte le cause nella popolazione 65+**, rilevati dagli uffici di stato civile comunali, confrontati con un valore atteso (baseline) per stimare l'**eccesso di mortalità** — è il sistema usato per misurare l'impatto delle ondate di calore e, nel 2020, del Covid.
- **Città incluse — verificato**: **54 città**; nel Mezzogiorno Foggia, **Bari**, **Taranto**, Napoli, Giugliano, Salerno, Potenza, Catanzaro, Reggio Calabria, Messina, Palermo, Catania, Siracusa, Sassari, Cagliari. ⚠️ **Nel Salento c'è solo Taranto: Lecce e Brindisi non sono incluse** (chiude il punto aperto "SiSMG" di `Lista_dataset_salute.md`).
- **Grana reale**: il **comune capoluogo**, non la provincia né il distretto. Un distretto socio-sanitario non è ricostruibile.
- **Accesso — verificato**: non esiste né API né dataset. I bollettini di sintesi stanno su `salute.gov.it` (es. `https://www.salute.gov.it/new/sites/default/files/SISMG_sintesi_2025w28.pdf`), ma il sito è dietro un **servizio di protezione che blocca le richieste programmatiche**: `curl` riceve la pagina "This website uses a security service", non il PDF. I rapporti stagionali del Centro di Competenza Nazionale per la Protezione Civile sono invece scaricabili (es. `rapporto-hhwws-sismg-maggio-giugno-2026.pdf`, 44 pagine, scaricato e letto): riportano **tabelle per città di decessi osservati/attesi ed eccesso %, aggregate per periodo**, non serie giornaliere — e quel rapporto specifico non include Taranto, perché è costruito sulle città dei sistemi di allarme caldo-salute (HHWWS).
- **Licenza**: non dichiarata.
- **Conclusione per OneHealth**: **non utilizzabile come fonte del dataset salute.** Resta utile come (a) riferimento metodologico per l'eccesso di mortalità da caldo, tema collegato all'UHRI (v. `Lista_dataset_calore.md`), e (b) possibile riscontro qualitativo per Taranto città. I dati giornalieri grezzi si otterrebbero solo con una richiesta al DEP Lazio.

## 2. profilidisalute.it — profili di salute ISS

Sito dell'**Ufficio di Statistica dell'ISS** (con Ministero della Salute e CCM).

- **Cosa contiene** (dalla scheda tecnica `https://www.profilidisalute.it/download/ProSa_ST_MRT.pdf`, scaricata e letta): **mortalità per causa** elaborata dall'ISS a partire dall'**indagine ISTAT sulle cause di morte** e dalle popolazioni comunali ISTAT, classificata **ICD-10**, con la mortalità generale e **37 cause specifiche** selezionate (grandi gruppi più singole cause, es. infarto miocardico acuto); indicatori derivati come l'età media al decesso per causa. In più **ospedalizzazione** dai flussi SDO del Ministero e, in via sperimentale, incidenza dai Registri Tumori.
- **Grana — verificato**: l'accesso libero mostra il livello **nazionale e regionale**; il dettaglio **per ASL** è in **area riservata agli operatori sanitari**. Nessun livello comunale o distrettuale, in nessuna delle due aree: la scheda tecnica parla esplicitamente di "profilo di salute **della ASL**".
- **Accesso**: sito di sola consultazione (Joomla statico: nessun endpoint dati nel sorgente della home, solo asset del template); il download in CSV è dichiarato dalla documentazione, ma vale per le tabelle visualizzate dall'interfaccia. **Nessuna API.**
- **Licenza**: non dichiarata.
- **Conclusione per OneHealth**: **inutile.** Dove è pubblico (regione) dà meno di ISTAT, che per le stesse cause arriva alla provincia via SDMX (v. `istat/ISTAT.md` canale B); dove sarebbe interessante (ASL) è chiuso, e comunque non scenderebbe sotto la ASL.

## 3. SENTIERI — Studio epidemiologico nazionale dei territori e degli insediamenti esposti a rischio da inquinamento

Progetto ISS (Programma Strategico Nazionale "Ambiente e Salute", Ministero della Salute), pubblicato come monografie di *Epidemiologia & Prevenzione*.

- **Cosa contiene**: **mortalità per 63 cause, ricoveri ospedalieri, incidenza tumorale e malformazioni congenite** per i comuni compresi nel perimetro dei **Siti di Interesse Nazionale (SIN)**, confrontati con il riferimento regionale e corretti per deprivazione socioeconomica. L'aggiornamento complessivo ha riguardato **319 comuni e 5,9 milioni di abitanti**; i ricoveri sono stati analizzati per il periodo **2005-2010**, la mortalità fino al 2010, con aggiornamenti successivi (V Rapporto, 2019) per singoli siti.
- **Territori salentini coperti**: il SIN di **Taranto** (comuni di Taranto e Statte) e l'area di **Brindisi**. **Nessuna copertura della provincia di Lecce.**
- **Accesso**: **report e monografie PDF**, con tabelle per comune; nessun dataset, nessuna API.
- **Conclusione per OneHealth**: **non utilizzabile come serie temporale.** È la fonte giusta da citare in tesi per lo stato dell'arte (v. `documentazione/Stato_Arte.md` del repository Presentation) e come precedente metodologico di correlazione ambiente-salute a grana comunale, non come fonte di dati della pipeline.

## 4. RespiVirNet (ex InfluNet) — sorveglianza delle infezioni respiratorie acute

Sorveglianza integrata epidemiologica e virologica coordinata dall'ISS con il Ministero della Salute, basata su medici sentinella (MMG e pediatri) e laboratori regionali di riferimento.

- **Cosa contiene**: **incidenza settimanale** dei casi di sindrome simil-influenzale / infezione respiratoria acuta per 1.000 assistiti, **per regione**, con la quota di campioni positivi per virus; bollettini settimanali nella stagione novembre-aprile.
- **Limiti decisivi**: grana **regionale** (Puglia intera), non comunale; copre solo la stagione invernale; e — verificato — **dal 06/03/2026 le Regioni hanno sospeso i flussi** che alimentano la sorveglianza, in attesa di un inquadramento conforme alla normativa sulla protezione dei dati personali, quindi i bollettini non sono più aggiornati.
- **Conclusione per OneHealth**: non è un dato di mortalità né di ricovero e non scende sotto la regione. Unico uso possibile: **profilo di stagionalità respiratoria regionale**, se mai servisse per ripartire nel tempo un dato annuale (v. §6).

## 5. Indirizzario dei registri di mortalità (ReNCaM) — l'unico canale ISS davvero utile

EpiCentro mantiene l'**indirizzario dei registri di mortalità** italiani: <https://www.epicentro.iss.it/mortalita/indirizzario> (PDF: `https://www.epicentro.iss.it/mortalita/pdf/indirizzario_registri.pdf`, aggiornamento **1 giugno 2017** → i nominativi vanno riverificati).

I **ReNCaM** sono i registri nominativi delle cause di morte tenuti dalle **ASL**: contengono copia delle schede di morte ISTAT, quindi **comune di residenza + data del decesso + causa**. Sono esattamente il dato che servirebbe a OneHealth (comune × giorno × causa) e **non sono pubblici**: si ottengono solo con richiesta formale alla ASL, in forma aggregata. L'indirizzario riporta per la Puglia un coordinamento regionale presso l'Osservatorio epidemiologico (Università di Bari) e un referente per ogni ASL — per il Salento **ASL Lecce**, **ASL Brindisi** e **ASL Taranto** (nomi e telefoni nel PDF del 2017; per ASL Taranto il riferimento è la struttura di *Epidemiologia e Statistica*).

Questo conferma dall'altro lato quanto già verificato su AReSS: il dato comunale per causa **esiste**, è gestito dalle ASL ed è raggiungibile solo per via istituzionale (v. punto aperto sulla richiesta ad AReSS/ASL in `Lista_dataset_salute.md`).

## 6. Nota metodologica: usare le sorveglianze come profilo temporale

Nessuna delle fonti qui sopra dà "malattie respiratorie per comune e per giorno". Se si vorrà scendere a una grana più fine di quella della fonte (es. ripartire ricoveri annuali provinciali su mesi o giorni), i profili temporali disponibili sono: i **decessi giornalieri comunali ISTAT** (tutte le cause, `istat/ISTAT.md` canale A) e, come riscontro stagionale regionale, **RespiVirNet**. Qualsiasi ripartizione di questo tipo è una **stima costruita da noi**, non un dato della fonte: va marcata come tale nel dataset (stato `NULL`/nota, non `VALORE`) e dichiarata in tesi. La scelta se farlo è ⏳ di Matteo.

## Citazioni

Le fonti di questa scheda vanno riportate in `Bibliografia.md` del repository Presentation:

- Ministero della Salute, *Sistema di sorveglianza della mortalità giornaliera (SiSMG)*, <https://www.salute.gov.it/new/it/tema/ondate-di-calore/sistema-di-sorveglianza-mortalita-giornaliera/>
- ISS, *profilidisalute.it — Profilo di salute della popolazione italiana*, <https://www.profilidisalute.it/>
- ISS, *SENTIERI — Studio epidemiologico nazionale dei territori e degli insediamenti esposti a rischio da inquinamento*, monografie in *Epidemiologia & Prevenzione*
- ISS, *Sorveglianza delle infezioni respiratorie acute (RespiVirNet)*, <https://www.epicentro.iss.it/sorveglianza-infezioni-respiratorie-acute/>
- ISS, *Indirizzario dei registri di mortalità*, <https://www.epicentro.iss.it/mortalita/indirizzario>
