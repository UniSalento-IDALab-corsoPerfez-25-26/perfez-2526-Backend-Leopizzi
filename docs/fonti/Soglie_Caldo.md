# Soglie di caldo (UHRI, componente 1)

*Scelte il 14/10/2026 (Matteo: «le soglie utilizzate più comunemente»). Dato autorevole nel codice: `api/calore/soglie.py` (`SOGLIE`).*

## 1. Cosa si calcola

Dalla temperatura dell'aria a 2 m di ERA5-Land (massima e minima giornaliera per comune, UTC+1) si derivano **quattro indicatori giornalieri 0/1**: 1 = soglia raggiunta nel giorno e nel comune.

| Indicatore | Statistica | Soglia | Nome in letteratura | Uso tipico |
|---|---|---|---|---|
| `giorno_caldo` | T max | **≥ 30 °C** | *hot day* / giornata calda | caldo diffuso, primo livello di esposizione |
| `giorno_molto_caldo` | T max | **≥ 35 °C** | *very hot day* / «caldo estremo» | soglia di rischio sanitario più citata |
| `notte_tropicale` | T min | **≥ 20 °C** | *tropical night* (indice TR20 di ETCCDI) | assenza di recupero notturno |
| `notte_equatoriale` | T min | **≥ 25 °C** | *equatorial/ tropical night* estrema | notti di caldo eccezionale |

## 2. Perché soglie fisse

- Sono le **più usate e più leggibili** (dashboard e confronto con la stampa e i bollettini); una soglia fissa vale allo stesso modo per tutti i comuni.
- L'alternativa, un **percentile locale** (es. 95° estivo del comune), è più difendibile in tesi perché si adatta al clima del luogo, ma richiede una serie di riferimento lunga e rende i comuni non confrontabili fra loro. **Non è stata scartata**: resta come sviluppo (⏳ se aggiungerla in parallelo), perché le **soglie sanitarie vere** dipendono dal luogo (le ondate di calore dei sistemi HHWW italiani usano la temperatura apparente massima con soglie per città).
- Gli indicatori sono 0/1 con lo **stato della temperatura da cui derivano** (`VALORE`/`NULL`/`NO_DATA`, docs/Regole_dei_dati.md), quindi **si sommano** a distretto e a mese come ogni conteggio (`api/comune/aggregazione.py`), senza medie.

## 3. Limiti dichiarati

- **ERA5-Land è una rianalisi a ~9 km**, mediata sull'area del comune: **smussa i picchi** e tende a sottostimare le massime di una stazione urbana; i conteggi di giorni sopra 35 °C sono quindi un **limite inferiore** rispetto alla misura in stazione. La validazione con ARPA meteo (`report/Report_validazione_calore.md`) lo quantifica: sui giorni confrontati ERA5-Land conta circa un terzo in meno di giorni ≥ 35 °C e un po' di notti tropicali in più rispetto alle stazioni.
- Le soglie sono sulla **temperatura dell'aria**, non sulla **temperatura apparente** (umidità, vento) che è quella delle ondate di calore sanitarie: ERA5-HEAT/UTCI è stata scartata alla grana comunale (v. `documentazione/Scelte_Progettuali.md` del repository Presentation).
- **Disuguaglianza larga (≥)** per tutte le soglie; la definizione ETCCDI di TR20 è stretta (> 20 °C): su valori continui a due decimali la differenza è trascurabile.
- Isola di calore **non** è qui: questi indicatori misurano l'**esposizione al caldo**, non il contrasto urbano/rurale (SUHI, rimandato dopo l'MVP).

## 4. Riferimenti (stile Chicago, voci complete in `Bibliografia.md` del repository Presentation)

- **ETCCDI** — gli indici *summer days* (T max > 25 °C) e *tropical nights* (T min > 20 °C): Zhang et al. 2011. Le soglie 30 e 35 °C per T max e 25 °C per T min sono di uso corrente in climatologia e nella sanità pubblica ma **non sono un unico standard**: **da agganciare a una fonte primaria** (bollettini del Ministero della Salute sulle ondate di calore, studi su Lecce come Pappaccogli et al. 2024) prima della citazione in tesi.

## 5. Dataset

`scripts/calore/genera_dataset_calore.py` → `data/interim/calore/dataset_calore_<da>_<a>.json` (un mese per file, gitignored). Struttura `provincia → distretto → comune → giorno → fonte → indicatore`; indicatori: `temperatura_media|massima|minima` (°C) e i quattro 0/1 sopra.
