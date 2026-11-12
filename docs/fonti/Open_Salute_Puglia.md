# Open Salute Puglia — export CSV (incidenza e prevalenza)

*Scheda del 02/10/2026.* Servizio: portale **Open Salute Puglia** di AReSS Puglia, <https://opensalute.aress.regione.puglia.it/>. Qui sono documentati i **CSV scaricati a mano** dal menu dei grafici (Strada A di `../aress_puglia/Accesso_Open_Salute.md` §2bis): **nessun token e nessuna chiamata a Superset da parte del progetto**. Per il flusso del *guest token* e la richiesta ad AReSS resta valido `../aress_puglia/Accesso_Open_Salute.md`.

## 1. Ruolo nel progetto

**Decisione di Matteo del 02/10/2026:** questi dati servono per **confronto visivo** e per **avvalorare o discutere tesi**, **non** entrano nel dataset salute della pipeline (docs/Regole_dei_dati.md: niente griglia `VALORE`/`NULL`/`NO_DATA`, nessun adattatore in `api/salute/`). Restano quindi file di riferimento, non una fonte integrata. Se in futuro la grana comune × anno dovesse entrare nel confronto con aria e calore, è una decisione ⏳ da riaprire (v. `../Lista_dataset_salute.md`, punti aperti).

## 2. Dove stanno i file

`data/raw/salute/open_puglia_salute/` (gitignored, v. docs/Regole_dei_dati.md: mai committare dati sanitari):

- `incidenza/` — un CSV per anno (BPCO, 2014-2024), scaricati dal portale.
- `prevalenza/` — idem.

File **rinominati il 02/10/2026** da `Incidenza della BPCO per Comuni (N).csv` (nome del portale, con un numero progressivo) a `Incidenza_BPCO_Comuni_<anno>.csv` e `Prevalenza_BPCO_Comuni_<anno>.csv`, con l'anno letto dalla colonna `Anno` di ciascun file. Sono **11 file per misura, anni 2014-2024**: il 2011-2013 non è stato scaricato (o non è offerto dal portale: da verificare).

**Versione filtrata sul Salento** (generata, gitignored): `data/interim/salute/open_salute/{incidenza,prevalenza}_BPCO_salento.csv`, prodotta da `scripts/salute/filtra_open_salute.py` (`uv run scripts/salute/filtra_open_salute.py`). Tiene i soli **146 comuni** dell'anagrafica per 11 anni = **1.606 righe per misura**, con `id_provincia`, `id_distretto`, `id_comune` aggiunti e colonne rinominate (`casi`, `popolazione`, `tasso_std`, `tasso_grezzo`, `rr`, con i rispettivi `_lcl`/`_ucl`). Non aggrega e non calcola nulla.

## 3. Che cosa misurano (definizioni del glossario del portale)

- **Incidenza** — quanti **nuovi casi** di una malattia vengono diagnosticati in un intervallo di tempo, di norma l'anno solare (*casi incidenti*). Misura l'impatto della malattia sul territorio.
- **Prevalenza** — il numero di pazienti **viventi con la malattia**, anche se diagnosticata in passato (*casi prevalenti*): approssima chi, in un dato istante, ha bisogno di percorsi diagnostici, terapeutici o controlli. Due malattie con stessa incidenza possono avere prevalenza diversa se la prognosi cambia.

Sono definizioni **generali**, non l'algoritmo con cui il portale identifica un caso di BPCO (da ricoveri, esenzioni, farmaci?). Quell'algoritmo **non è noto**: va cercato nella nota metodologica del portale prima di descrivere il dato in tesi (⏳). Fonte della definizione: testo del glossario del portale, riportato da Matteo il 02/10/2026; l'URL della pagina esatta va annotato quando lo si ritrova.

Per la tesi: incidenza e prevalenza **non sono intercambiabili** e non vanno messe sullo stesso asse come se fossero la stessa cosa. L'incidenza reagisce a un'esposizione ambientale in tempi più brevi; la prevalenza accumula anche i casi vecchi.

## 4. Tracciato del CSV (verificato sul file BPCO 2024)

Separatore `;`, UTF-8, punto decimale. 257 righe = 257 comuni (tutta la Puglia fuori dalla provincia di Bari: BAT, Foggia, Brindisi, Lecce, Taranto).

| Colonna | Contenuto |
|---|---|
| `Tipo Area Geografica` | sempre `Comune` in questo file |
| `Area Geografica` | **nome** del comune (nessun codice ISTAT) |
| `Patologia` | `BPCO` |
| `Anno` | `2024` |
| `Genere` | `Maschi e Femmine` (nessun dettaglio per sesso) |
| `Classi eta`` | fasce 40-44 … ≥85 in un'unica cella (nessun dettaglio per età) |
| `Casi` | numero di casi; **`(*)`** quando la cella è oscurata |
| `Popolazione` | residenti nella fascia d'età considerata (40+) |
| `Tasso standardizzato`, `lcl`, `ucl` | tasso standardizzato per età e intervallo di confidenza |
| `Tasso grezzo`, `lcl`, `ucl` | casi / popolazione × **1.000**, con intervallo di confidenza |
| `Rischio relativo`, `lcl`, `ucl` | rispetto al riferimento regionale, con intervallo di confidenza |

Le colonne `lcl`/`ucl` compaiono tre volte con lo stesso nome: pandas le rinomina `lcl`, `lcl.1`, `lcl.2` (rispettivamente tasso standardizzato, tasso grezzo, rischio relativo).

## 5. Qualità e limiti noti

- **Copertura del Salento:** tutti i **146 comuni** in tutti gli 11 anni, per entrambe le misure. 144 corrispondono per nome; **Acquarica del Capo e Presicce** compaiono nel file come **un solo comune fuso, "Presicce-Acquarica"** (fusione del 2019, applicata dal portale anche agli anni precedenti). L'anagrafica li ha già entrambi con `nome_confine` = "Presicce-Acquarica" e stesso distretto (LE-60): il valore del comune fuso **non è separabile** e nel file filtrato è ripetuto sui due comuni, con una `nota`. **Non sommare i due comuni nelle analisi: si conterebbe due volte.** Gli altri 113 comuni del file sono fuori Salento e scartati.
- **Nessun codice ISTAT:** il collegamento all'anagrafica è per nome, normalizzato in minuscolo e senza spazi di bordo (nessun nome discorde in nessun anno).
- **Celle oscurate:** `(*)` nei casi. Nel Salento solo **3 celle, tutte nell'incidenza**: Giuggianello 2020, Cannole 2021, Sanarica 2022. Nel file filtrato hanno `stato` = `NULL` e `casi` vuoto (popolazione, tassi e intervalli restano valorizzati: la fonte oscura solo il numero di casi). In prevalenza nessuna.
- **Andamento nel tempo, da interpretare con cautela:** sul Salento il tasso grezzo di incidenza per 1.000 passa da **17,2 (2014) a 8,7 (2020)** e risale a 10,1 (2024); la prevalenza da 81,0 a 68,3 (2021) e a 70,8 (2024). Un calo così netto e simultaneo in tutti i comuni può dipendere dal **metodo** (finestra di osservazione per riconoscere un caso "nuovo", cambi di codifica) e dalla pandemia più che da un cambiamento reale. **Non va letto come tendenza epidemiologica finché non è nota la definizione di caso** (punto aperto 1).
- **Numeri piccoli:** comuni con 8-13 casi e intervalli di confidenza molto larghi; il tasso non è confrontabile tra comuni di dimensioni diverse senza guardare l'intervallo.
- **Solo annuale:** nessuna grana mensile o giornaliera, quindi non confrontabile con la serie giornaliera di aria e calore se non aggregando quelle.
- **Privacy:** comuni piccoli = rischio di re-identificazione (§7). Per grafici e tesi usare **distretto** o intervalli di tassi, non i numeri di casi dei comuni più piccoli.
- **Come si legge in analisi:** esplorativa, non causale (docs/Regole_dei_dati.md). Fumo, età, comorbidità e aria indoor restano confondenti.

## 6. Licenza

**Non dichiarata** sul portale. Scaricare un CSV dal menu del grafico è l'uso previsto dal portale, ma non è una licenza di riuso. **Prima di mostrare questi numeri in tesi o in dashboard** serve la risposta di AReSS: la bozza della richiesta (che ora si può ridurre al solo chiarimento sulla licenza) è in `../aress_puglia/Accesso_Open_Salute.md` §4. Fino ad allora i file restano solo per consultazione interna.

## 7. Riproducibilità

Per ogni file scaricato annotare qui sotto: patologia, misura (incidenza/prevalenza), anno, data di download. Nessuno script lo scarica: l'export è manuale.

| File | Misura | Patologia | Anno | Scaricato il |
|---|---|---|---|---|
| `incidenza/Incidenza_BPCO_Comuni_<anno>.csv` (11 file) | incidenza | BPCO | 2014-2024 | 02/10/2026 |
| `prevalenza/Prevalenza_BPCO_Comuni_<anno>.csv` (11 file) | prevalenza | BPCO | 2014-2024 | 02/10/2026 |

## 8. Punti aperti ⏳

1. **Algoritmo di identificazione dei casi** (nota metodologica del portale).
2. **Anni 2011-2013:** non scaricati; il portale li offre? (Il tracciato è identico in tutti gli 11 anni disponibili: 17 colonne, stesse intestazioni.)
3. **Calo dell'incidenza 2014 → 2020** (v. §5): reale o effetto del metodo?
4. **Licenza** (v. §6).
5. **Quali patologie oltre alla BPCO** (il portale ne ha altre).
