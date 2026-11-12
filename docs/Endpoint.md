# Endpoint

API locale di OneHealth, versione **1.0.0**. File generato da `scripts/backend/esporta_openapi.py` dallo schema [`openapi.json`](openapi.json): non modificarlo a mano. Documentazione interattiva a server avviato su `http://127.0.0.1:8000/docs`.

Dove un periodo non è coperto dai dati scaricati, gli endpoint rispondono `404` con il motivo (mai un `500`). La correlazione fra i domini è sempre esplorativa, non causale.

| Metodo | Percorso | Cosa fa | Parametri |
|---|---|---|---|
| POST | `/api/valori` | Tutti i valori di un comune o distretto in un giorno | corpo JSON |
| GET | `/api/territorio` | Province, distretti e comuni per i selettori | — |
| GET | `/api/territorio/confini` | Confini GeoJSON di distretti e comuni | — |
| GET | `/api/stato` | Il servizio è vivo? Che versione? Ci sono dati in locale? | — |
| GET | `/api/disponibilita` | Cosa c'è da mostrare: mesi, inquinanti, decessi | — |
| GET | `/api/aria/mese` | Valore del mese per distretto e comune, una fonte | `mese`, `fonte`? |
| GET | `/api/aria/calendario` | I giorni coperti dall'archivio, per la barra temporale | — |
| GET | `/api/aria/finestra` | Valore di una finestra di giorni (fino a un mese) per distretto e comune, una fonte | `da`, `a`, `fonte`? |
| GET | `/api/salute/simulati/finestra` | Ricoveri, PS e ADI simulati di una zona (o del Salento) in una finestra di giorni | `zona`?, `da`, `a`, `scenario`? |
| GET | `/api/salute/mappa` | Eventi sanitari (decessi + ricoveri + accessi in PS) di tutte le zone nella finestra (vista «Salute» della mappa) | `da`, `a`, `scenario`? |
| GET | `/api/salute/simulati/serie` | Un indicatore simulato mese per mese, entrambi gli scenari, fino a 4 zone (comuni ammessi) | `zone`, `da`, `a`, `indicatore`? |
| GET | `/api/zona/dettaglio` | Aria (ogni fonte), decessi, ricoveri, simulati e calore di una zona in una finestra di giorni | `zona`, `da`, `a`, `scenario`? |
| GET | `/api/riepilogo` | Tutti i dati per distretto nella finestra: territorio, aria, salubrità, salute, calore | `da`, `a`, `fonte`?, `scenario`? |
| GET | `/api/aria/salubrita` | Banda di salubrità di tutte le zone della finestra (modalità «salubrità» della mappa) | `da`, `a` |
| GET | `/api/aria/serie` | Serie giornaliera di fino a 3 zone, una fonte | `mese`, `inquinante`, `fonte`?, `zone` |
| GET | `/api/calore/disponibilita` | Mesi di temperatura ERA5-Land già scaricati | — |
| GET | `/api/calore/serie` | Temperatura giornaliera di fino a 3 zone, un mese (ERA5-Land o ARPA meteo) | `mese`, `zone`, `statistica`?, `fonte`? |
| GET | `/api/calore/mappa` | Temperatura di tutte le zone nella finestra (modalità «temperatura» della mappa) | `da`, `a`, `statistica`? |
| GET | `/api/aria/fonti` | Ogni fonte nella stessa zona, con la concordanza | `mese`, `inquinante`, `zona` |
| GET | `/api/calore/fonti` | Temperatura secondo ERA5-Land e ARPA meteo nella stessa zona, con la concordanza | `mese`, `zona`, `statistica`? |
| GET | `/api/salute/fonti` | Decessi secondo ISTAT giornaliero, bilancio mensile ed Eurostat, in un anno | `anno`, `zona` |
| GET | `/api/salute/decessi` | Decessi ISTAT per distretto × mese | `da`, `a`, `distretti`? |
| GET | `/api/salute/dimissioni` | Dimissioni ospedaliere ISTAT HFA per provincia × anno (solo informativo) | `da`, `a`, `province`?, `gruppi`? |
| GET | `/api/confronto` | Aria, temperatura e decessi per distretto × mese (esplorativo) | `da`, `a`, `inquinante`, `fonte`?, `distretti`, `statistica_calore`? |
| GET | `/api/stagionalita` | I 12 mesi dell'anno a confronto: aria, calore, decessi, PS/ADI/ricoveri simulati e criticità (tab Stagionalità) | `zona`?, `fonte`?, `scenario`?, `simulati_nella_sintesi`? |
| GET | `/api/assistente/stato` | Se l'assistente può rispondere: Ollama attivo e modello scaricato | — |
| GET | `/api/assistente/fatti` | Scheda dei fatti di una card, senza modello di linguaggio | `card`?, `mese`?, `da`?, `inquinante`?, `fonte`?, `zone`?, `soglia`?, `indicatore`?, `mese_dell_anno`?, `scenario`?, `simulati_nella_sintesi`?, `statistica_calore`?, `giorno_da`?, `giorno_a`?, `vista`?, `livello`?, `primo_piano`? |
| GET | `/api/assistente/domande` | Domande proposte di una card | `card`? |
| POST | `/api/assistente` | Risposta dell'assistente a una domanda sulla card aperta | corpo JSON |

`?` = parametro facoltativo.
