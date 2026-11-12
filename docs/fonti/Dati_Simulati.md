# Dati sanitari simulati

*Creato il 25/10/2026 su decisione di Matteo. Scheda della "fonte" simulata, con la stessa convenzione delle fonti reali. Codice: `api/salute/simulazione.py`, script `scripts/salute/simula_dati_salute.py`; verifica in `Report_simulazione.md` (rigenerato dallo script).*

## 1. Dicitura

Da riportare **ovunque compaiano questi dati**: dashboard (in ogni card e nel pannello che li mostra), report, tesi, presentazione. Il testo autorevole è la costante `DICITURA` del modulo, che finisce anche in `parametri.json`.

> **Dati sanitari simulati.** Ricoveri, accessi in pronto soccorso e accessi degli assistiti in ADI sono generati da un modello statistico calibrato su aggregati pubblici (ISTAT, Health for All, Annuario SSN) e servono come **dati di partenza** per sviluppare e collaudare la piattaforma, in attesa dei dati richiesti ad AReSS Puglia e a Parsec 3,26, non ancora ricevuti. **Non descrivono la situazione sanitaria reale del Salento**: non vanno usati per decisioni né citati come risultati. Nello scenario «letteratura» l'effetto di aria e caldo è imposto da noi con coefficienti tratti dalla letteratura: le correlazioni che ne risultano riflettono queste ipotesi.

Versione breve, per etichette e tooltip: **«Dato simulato, non reale»**.

## 2. Perché si simula

- Nessuna fonte pubblica dà ricoveri, accessi in pronto soccorso o assistiti in ADI sotto la provincia/ASL e con passo inferiore all'anno (`Inventario_Dati.md` §3).
- I dati richiesti ad **AReSS Puglia** (tramite il prof. Patrono) e a **Parsec 3,26** non sono arrivati.
- Senza un dato sanitario a grana fine, le parti della piattaforma che servono al decisore (pronto soccorso, ADI, confronto con aria e caldo) non si possono costruire né collaudare. I dati simulati hanno **la forma che avranno quelli reali** (distretto × giorno, stati `VALORE`/`NULL`/`NO_DATA`) e si sostituiscono senza cambiare l'interfaccia quando arrivano.

**Restano reali:** i decessi (ISTAT, comune × giorno), le dimissioni HFA (provincia × anno, informative), aria e calore. Non si simula nulla che esista già.

## 3. Cosa si simula

Grana: **comune × giorno** (145 comuni; dal 25/10/2026, prima distretto × giorno), con il distretto in ogni riga per aggregare (somma, perché sono conteggi). Periodo di default dal 2024-01-01 all'ultimo giorno con aria e temperatura per tutti i comuni (oggi 2026-09-30). I dati sono sintetici, quindi la regola di privacy dei decessi (docs/Regole_dei_dati.md) non li riguarda; la grana da mostrare in dashboard si decide all'integrazione. Ogni cella è `VALORE` con nota «simulato, scenario …».

| Indicatore | Significato |
|---|---|
| `ricoveri_respiratori` | ricoveri per malattie respiratorie |
| `ricoveri_circolatori` | ricoveri per malattie del sistema circolatorio |
| `ps_accessi` | accessi in pronto soccorso, tutte le cause (somma delle tre componenti sotto) |
| `ps_respiratori` | accessi in PS per cause respiratorie |
| `ps_cardiovascolari` | accessi in PS per cause cardiovascolari |
| `adi_assistiti` | assistiti in assistenza domiciliare integrata (over 65), stock del distretto |
| `adi_accessi_ps` | accessi in PS degli assistiti in ADI |
| `adi_accessi_bassa_urgenza` | di questi, accessi a bassa urgenza al triage: **potenzialmente gestibili a domicilio** |
| `adi_ritorni_30g` | accessi di assistiti già passati dal PS nei 30 giorni precedenti |

Scartate su scelta di Matteo (25/10/2026): **malattie croniche** (prevalenza e incidenza), che restano `N/D` in attesa di AReSS.

### Due scenari, selezionabili

| Scenario | Effetto di aria e caldo | A cosa serve |
|---|---|---|
| `nullo` | nessuno: solo popolazione, stagione, giorno della settimana, caso | mostrare che anche **senza alcun effetto** una correlazione grezza compare (confondimento stagionale) |
| `letteratura` | coefficienti di letteratura (tabella in §4) | una dashboard credibile e una prova che il metodo **ritrova l'effetto solo quando c'è** |

I due scenari usano lo **stesso seme**: la differenza fra i due viene dall'effetto, non dal caso. Il parametro `--moltiplicatore` dello script amplifica gli effetti dello scenario `letteratura` (di default 1, cioè i valori pubblicati).

## 4. Come si genera

| Componente | Valore | Fonte |
|---|---|---|
| Livello dei ricoveri | dimissioni per provincia × anno (2025-2026 = livello 2024), ripartite sui distretti per residenti | ISTAT Health for All (reale) |
| Livello del PS | 311 accessi ogni 1.000 residenti l'anno | Annuario statistico SSN 2023, via Quotidiano Sanità (nazionale) |
| Quote del PS per causa | respiratorie 8%, cardiovascolari 6% | **ipotesi**, da sostituire col flusso EMUR |
| Assistiti ADI | 24,5% di over 65 × 4% in ADI | **ipotesi** (quota over 65) + Italpress 2023 (nazionale; il Ministero dichiara oltre l'8% con un altro denominatore) |
| Accessi in PS per assistito ADI | 0,66 l'anno, fragilità gamma con k = 0,38 | Campagna et al. 2021 (Piemonte); uso come tasso annuo = **ipotesi** |
| Quota a bassa urgenza | 60% | Campagna et al. 2021 |
| Stagionalità | profilo medio dei decessi reali del Salento 2011-2019, due armoniche | ISTAT (reale) |
| Giorno della settimana | ricoveri più bassi nel fine settimana, PS più alto il lunedì | **ipotesi** |
| PM10 → respiratori (PS e ADI compresi) | +0,75% per 10 µg/m³, lag 0-5 | EpiAir2, Scarinzi et al. 2013 (25 città, Brindisi e Taranto comprese) |
| NO2 → cardiovascolari | +0,57% per 10 µg/m³, lag 0 | EpiAir2, Scarinzi et al. 2013 |
| Caldo → respiratori (PS e ADI compresi) | +4,5% per °C di T max (media lag 0-3) oltre 30 °C | Michelozzi et al. 2009 (75+, città mediterranee); soglia, lag ed estensione a tutte le età = **ipotesi** |
| Caldo → cardiovascolari | nessun effetto | Michelozzi et al. 2009 (non significativo) |
| Conteggi | Poisson, seme 20261025 | — |

**Esposizione del comune:** PM10 e NO2 della stazione virtuale **CAMS** del comune (l'unica aria che copre tutti i 145 comuni; dato modellato) e T max di **ERA5-Land** del comune. Si usa un solo inquinante per esito, per non sommare stime *single-pollutant* correlate fra loro.

**ADI:** coorte sintetica per comune (17.476 assistiti nel Salento, da 12 a 1.956 per comune); ogni assistito ha una fragilità individuale, ricampionata a inizio anno, che fa sì che pochi assistiti accedano molte volte. I ritorni entro 30 giorni (16% degli accessi) **non sono imposti**: emergono dalla fragilità.

## 5. Il caso ADI: la criticità da far emergere

Idea di Matteo (25/10/2026): una parte degli accessi in PS viene da assistiti in ADI che, con un contatto a domicilio nel momento giusto, potrebbero non arrivarci. La dashboard deve rendere visibili:

1. **i periodi critici**: giorni e settimane in cui gli accessi degli assistiti ADI salgono (ondate di calore, picchi invernali, giorni di aria peggiore);
2. **la quota evitabile**: gli accessi a bassa urgenza, gestibili con una visita domiciliare;
3. **chi torna**: gli accessi ripetuti entro 30 giorni, segno di un assistito non seguito abbastanza;

così che il distretto possa **organizzare in anticipo** medici di famiglia, volontariato e protezione civile con **telefonate mirate** e **visite domiciliari** agli assistiti più fragili, e far sapere quali sono i periodi più critici e come prevenire l'accesso al PS.

Nello scenario `letteratura`, nei mesi estivi gli assistiti ADI accedono al PS il **21% in più** nei giorni oltre i 30 °C (contro il 2% dello scenario nullo, solo stagione e caso); circa 6 accessi su 10 sono a bassa urgenza (`Report_simulazione.md` §4). Sono numeri **costruiti dalle nostre ipotesi**: mostrano come la piattaforma leggerà i dati reali, non quanto accade davvero.

**Limite di fondo, già noto:** il dato reale che servirebbe (ricorrenza per paziente) non esiste in nessuna fonte pubblica e richiede un dato anonimizzato di AReSS/ASL.

## 6. Cosa mostra la verifica

`Report_simulazione.md`, rigenerato a ogni esecuzione:

- **calibrazione**: ricoveri entro ±1,5% dalle dimissioni HFA 2024 per provincia, PS a 311 accessi per 1.000;
- **effetti**: un modello di Poisson standard ritrova l'effetto del caldo imposto (+4,5% → stime fra +4,7% e +5,3%) e nessun effetto nello scenario nullo. Gli effetti di PM10 e NO2, alla loro dimensione reale (meno dell'1%), **non si distinguono dal caso** in quasi tre anni di dati: è il limite di potenza statistica che vale anche per i dati reali, da dichiarare in tesi;
- **correlazione grezza**: senza togliere la stagione, la correlazione fra T max e ricoveri respiratori è **negativa anche quando il caldo li aumenta** (inverno con più ricoveri). È l'argomento più forte, con dati di cui si conosce la verità, per presentare ogni correlazione come esplorativa.

## 7. Limiti

- **Non sono dati reali** e non si validano: si verificano solo contro i parametri dati.
- Livelli nazionali (PS, ADI) applicati al Salento; quote per causa e fattori settimanali ipotetici.
- I ricoveri HFA sono per provincia di residenza e comprendono anche i ricoveri programmati, mentre i coefficienti EpiAir2 riguardano quelli urgenti.
- Poisson senza sovradispersione per ricoveri e PS (i dati reali sono più variabili).
- L'esposizione è dato modellato (CAMS, ERA5-Land): l'effetto è costruito sul modello, non sulla misura delle stazioni.
- ADI: coorte chiusa a numero fisso, nessuna entrata o uscita durante l'anno; gli accessi ADI sono generati a parte e non sono sottratti dal totale del PS (pesano circa il 2%).

## 8. Come si sostituiscono con i dati reali

1. Il dato reale entra come nuova fonte in `api/salute/` con gli stessi indicatori (o un sottoinsieme) e la sua grana nativa.
2. Le viste che leggeranno `salute_simulata.parquet` passano alla fonte reale; dove il reale manca, resta il simulato **sempre con la dicitura**.
3. Il confronto reale ↔ simulato diventa a sua volta una verifica delle ipotesi della §4.

**Dove li legge la dashboard** (25/10/2026): `localhost/server/dati_simulati.py` (`ArchivioSimulato`, parquet in forma larga, si
ricarica se il file cambia) e gli endpoint `GET /api/salute/simulati/finestra` (zona o Salento in una finestra),
`GET /api/salute/simulati/serie` (un indicatore mese per mese, i due scenari insieme), il campo `simulati` di
`/api/disponibilita` (con la **dicitura**, unica fonte del testo) e di `/api/zona/dettaglio`, le colonne `sim:*` di
`/api/riepilogo` e la riga `pronto_soccorso` di `/api/stagionalita` (parametri `scenario` e `simulati_nel_peggiore`).
Valori per **100.000 residenti al giorno**; distretto e Salento = somma dei comuni. Per passare al dato reale basta che
questi endpoint leggano la nuova fonte: il frontend non cambia.

## 9. Rigenerazione

```
uv run scripts/salute/simula_dati_salute.py                      # periodo di default, entrambi gli scenari
uv run scripts/salute/simula_dati_salute.py --da 2021-01-01      # quando ERA5-Land 2021-2023 sarà in cache
uv run scripts/salute/simula_dati_salute.py --moltiplicatore 3   # effetti amplificati (solo a scopo didattico)
```

Uscite (gitignored) in `data/interim/salute/simulati/`: `salute_simulata.parquet` (2,6 milioni di celle, ~1,3 MB), `esposizione_comuni.csv`, `parametri.json`. Circa 15 secondi.
