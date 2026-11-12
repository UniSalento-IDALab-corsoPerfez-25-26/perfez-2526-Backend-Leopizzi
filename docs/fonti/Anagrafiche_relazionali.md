# Anagrafiche relazionali (territorio, stazioni, inquinanti)

*Aggiunto 28/09/2026.* I dataset sono organizzati **provincia → distretto → comune → stazione → giorno → fonte → inquinante** e restano **non aggregati**: la **media dei valori delle stazioni di un comune** (per fonte, inquinante e giorno) si calcola solo per la **mappa** e per le **analisi su un comune specifico**. I comuni stanno dentro i distretti socio-sanitari, che stanno dentro le province. Per farlo servono tre anagrafiche, in JSON ma progettate come **tabelle SQL**: ogni tabella ha una chiave primaria (PK) e le relazioni sono chiavi esterne (FK), così si interrogano con `JOIN` senza codice ad hoc.

| File | Tabelle | Aggiornamento |
|---|---|---|
| `data/territorio/anagrafica/territorio.json` | `province`, `distretti`, `comuni` | `uv run scripts/territorio/costruisci_anagrafica_territorio.py` (quando cambia la zonizzazione) |
| `stazioni.json` | `fonti`, `stazioni`, `stazioni_fonti` | a ogni `genera_dataset_aria.py` e con `aggiorna_anagrafiche_aria.py` |
| `inquinanti.json` | `inquinanti`, `stazioni_inquinanti` | come sopra; le descrizioni con `inquinanti_arpa.py` |

Ogni file contiene `descrizione`, `schema` (per ogni tabella: `chiave_primaria`, `chiavi_esterne`, `colonne` con il significato di ciascuna) e `tabelle` (una riga JSON per riga di tabella). I nomi delle tabelle sono **univoci fra tutti i file**, quindi una FK si scrive sempre `tabella.colonna`, anche fra file diversi.

## Relazioni

```
province (PK id_provincia)
   ▲
distretti (PK id_distretto; FK id_provincia, id_comune_sede → comuni)
   ▲
comuni (PK id_comune = codice ISTAT a 6 cifre; FK id_distretto)
   ▲
stazioni (PK id_stazione; FK id_comune, fonte_riferimento → fonti)
   ▲                                              
stazioni_fonti (PK id_stazione_fonte "ARPA:24"; FK id_stazione, fonte → fonti)
   ▲
stazioni_inquinanti (PK id_stazione_fonte + id_inquinante; FK → stazioni_fonti, inquinanti)
                                                                     ▼
                                                     inquinanti (PK id_inquinante, es. "NO2")
```

- **`stazioni` vs `stazioni_fonti`.** `stazioni` è la stazione fisica, con la stessa chiave unificata del dataset aria (id ARPA, oppure `<fonte>-<id>` — es. `OpenAQ-<id>`, `EEA-<codice EoI>` — se non ricondotta a una stazione ARPA). `stazioni_fonti` è il *record* della stazione in una fonte (`ARPA:24`, `OpenAQ:8378`); una stazione può averne più d'uno, anche della stessa fonte (OpenAQ ha cambiato id il 01/06/2026). **La media per comune (mappa e analisi su un comune) si fa sulle stazioni, non sui record**, così una stazione con due id non pesa il doppio.
- **`id_comune`** è il codice ISTAT come testo (`'074001'`, con lo zero iniziale).
- **Chiavi esterne nulle.** `stazioni.id_comune` è nullo se la stazione è fuori dal Salento o non assegnabile (il motivo è in `nota`); resta nella tabella per non perdere la traccia.

## Come una stazione è collegata al comune

In ordine (`api/aria/anagrafica_aria.py`, `comune_della_stazione`):

1. il **comune dichiarato dalla fonte di riferimento** (ARPA, poi OpenAQ, poi EEA, v. `fonti.priorita`), se è tra i 146 comuni del Salento → `metodo_comune = comune_dichiarato_dalla_fonte`;
2. se la fonte dichiara un comune **fuori dal Salento** (es. Monopoli): nessun comune, con nota;
3. se la fonte **non dichiara** un comune: quello il cui **confine contiene le coordinate** (`dentro_il_confine`), altrimenti il **comune con il confine più vicino entro 5 km** (`confine_piu_vicino`, con `distanza_comune_km`); oltre 5 km nessun comune;
4. se le coordinate cadono nel confine di un altro comune rispetto a quello dichiarato, resta il dichiarato e la discrepanza va in `nota`;
5. se il confine è condiviso da due comuni (Presicce e Acquarica del Capo, fusi nel 2019 in un unico confine sulla mappa): nessun comune, da assegnare a mano.

I confini sono in `data/territorio/confini/comuni_salento.geojson` (145 poligoni ISTAT semplificati da openpolis/geojson-italy, estratti dal mockup della mappa con `scripts/territorio/estrai_confini_comuni.py`).

## Uso nel dataset aria

`api/aria/dataset_aria.py` usa queste anagrafiche per costruire la griglia: per ogni stazione (di qualunque fonte) `comune_della_stazione()` dà il comune, da cui derivano distretto e provincia; il dataset ha una sezione per **ognuno dei 146 comuni**, e quelli senza stazioni hanno la stazione fittizia `nessuna_stazione` (tutto `NO_DATA`). Le chiavi `distretto` e `comune` del JSON sono `id_distretto` e `id_comune`. Le stazioni senza comune (fuori dal Salento, confine condiviso) non entrano nella griglia e finiscono nel riepilogo degli errori (`data/interim/aria/riepilogo_errori.md`).

## Aggiornamento cumulativo

Le anagrafiche stazioni/inquinanti **non perdono mai righe**: ogni corsa aggiunge stazioni, record di fonte, inquinanti e coppie stazione/inquinante osservati, ed estende `visto_da`/`visto_a`. Una stazione che in un periodo non restituisce righe per un inquinante non lo "perde" per questo. Gli inquinanti nuovi entrano con `riferimento_dashboard = false` (i 5 di docs/Regole_dei_dati.md sono `true`) e la regola di docs/Regole_dei_dati.md continua a valere. `inquinanti.json` **sostituisce** il vecchio `inquinanti_tracciati.json`.

Dopo un aggiornamento, lo script verifica le chiavi (PK uniche, FK che puntano a righe esistenti) e segnala i problemi senza perdere il lavoro. Le stazioni senza comune finiscono anche in `data/interim/aria/riepilogo_errori.md`.

## Interrogare in SQL

```python
from api.comune.anagrafiche import apri_sqlite

conn = apri_sqlite()   # SQLite in memoria, ricreato dai JSON: nessun database persistente (docs/Regole_dei_dati.md)
conn.execute("""
    SELECT k.denominazione AS comune, d.id_distretto, COUNT(DISTINCT s.id_stazione) AS stazioni
    FROM comuni k
    JOIN distretti d USING (id_distretto)
    JOIN stazioni s ON s.id_comune = k.id_comune
    GROUP BY k.id_comune
""").fetchall()
```

`carica_anagrafiche()` restituisce invece le stesse tabelle come DataFrame pandas, e `verifica_integrita()` controlla PK e FK.

## Stato al 28/09/2026

- **Territorio:** 3 province, 20 distretti, 146 comuni (1.782.644 residenti, come `Distretti_Salento.json`). Due codici ISTAT malformati nella fonte (`Presidi_Puglia.json`: Oria `07401`, Taranto `73027`) corretti a mano in `costruisci_anagrafica_territorio.py`.
- **Stazioni e inquinanti — popolamento iniziale offline**, perché il 28/09 l'host ARPA non rispondeva (errore SSL) e mancava la chiave OpenAQ: 37 stazioni ARPA (anagrafica locale, rete privata ADI esclusa), 167 coppie stazione/inquinante dagli inquinanti osservati nel 2023, descrizioni dei 9 inquinanti da `Parametri_Qualita_Aria.md`. **Mancano** le stazioni OpenAQ, le 6 VERSALIS di Brindisi (id 114-119, assenti dall'anagrafica ARPA) e le coppie osservate dopo il 2023: si aggiungono al primo `aggiorna_anagrafiche_aria.py` (o `genera_dataset_aria.py`) con la rete e `OPENAQ_API_KEY`.
- **01/10/2026**: le 6 VERSALIS sono state aggiunte anche a `stazioni_di_monitoraggio.json` (anagrafica ARPA, v. `arpa_puglia/`, decisione di Matteo), non più solo riconosciute tramite il comune.
- 12 distretti su 20 hanno almeno una stazione; **Surbo - Croce** (id 95) è dichiarata in comune di Surbo ma le sue coordinate cadono nel confine (semplificato) di Lecce: resta Surbo, con nota.
