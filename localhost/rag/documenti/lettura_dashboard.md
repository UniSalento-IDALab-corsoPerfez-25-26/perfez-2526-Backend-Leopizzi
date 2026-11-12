---
argomenti: [lettura_dashboard]
soggetti: [N/D, null, stati del dato, segni, beuta, cubo, massimo giornaliero, tilde, mappa, colori, tratteggio, finestra, testata, Stagionalità, rango, Riepilogo, Fonti a confronto, giorno per giorno]
fonte: localhost/dashboard/src/componenti/Informazioni.tsx
aggiornato: 2026-11-02
---

# Come leggere la dashboard

## Le sezioni
La barra laterale porta alle tab, in quest'ordine: Mappa, Stagionalità, Fonti a confronto, Riepilogo e Informazioni, l'unico posto in cui sono raccolte tutte le spiegazioni. Informazioni è divisa per argomenti (Segni e stati, Periodo e navigazione, Carta e zone, Numeri grafici e Riepilogo, Stagionalità, Aria, Calore, Salute, Assistente ONE, Fonti e licenze), ciascuno con i suoi sottoargomenti. Ogni scheda ha, in alto a destra, l'icona della guida (un libro in un cerchio): apre il sottoargomento di Informazioni che la spiega.

## Valore non disponibile (N/D)
N/D, segnato con un'icona di divieto, vuol dire che la fonte non copre quella zona o quel periodo: non c'è una stazione, l'inquinante non è misurato, il periodo è fuori dalla copertura, il dato non è ancora integrato oppure non può essere mostrato per riservatezza. Passandoci sopra, la dashboard dice il motivo.

## Valore nullo (null)
Null, segnato con un punto esclamativo, vuol dire che la fonte copre la zona ma il valore non è utilizzabile: è nullo, non valido, oppure la fonte ha restituito un errore. È diverso da N/D: lì il dato non esiste, qui esiste ma non si può usare.

## Dato modellato e dato simulato
L'icona a forma di cubo indica un dato modellato, non misurato: Copernicus CAMS per l'aria, ERA5-Land per la temperatura. L'icona a forma di beuta indica un dato simulato, non reale: ricoveri, pronto soccorso e assistenza domiciliare, che nessuna fonte pubblica dà a questa grana.

## Massimo giornaliero
La sigla «max» accanto a un valore indica un massimo giornaliero, non la media delle ore: è il caso di ARPA per NO2, O3, SO2 e CO. Un massimo non si confronta con una media.

## Il segno «~»
Il segno «~» davanti a un numero indica un valore derivato per comodità di lettura: un totale mensile diviso per i giorni del mese, ad esempio «~5,2 decessi al giorno». Non entra in nessun calcolo.

## La finestra e la testata
La testata in alto sceglie il periodo e l'inquinante per tutta la pagina. Il periodo è una finestra di al più 31 giorni, sull'asse che parte dal 1° gennaio 2024. La pagina si apre sull'ultimo mese coperto da tutti i domini, perché decessi e temperatura arrivano in ritardo rispetto all'aria. La stessa testata resta ferma in alto anche nella Stagionalità, dove al posto dell'inquinante porta la zona, la fonte dell'aria e i dati simulati.

## La sintesi della finestra
Sotto la mappa, la scheda «Sintesi della finestra» mette insieme i numeri di testa e la classifica delle zone, divisi per dominio. Nella parte Aria: il valore più alto dell'inquinante, quanti distretti hanno una misura e, sotto, le zone in ordine di valore, di default solo quelle a confronto col loro posto in classifica fra tutte (un pulsante apre l'elenco completo). Nella parte Salute, per il Salento: decessi, ricoveri respiratori e accessi in PS simulati. I numeri mostrano solo l'etichetta; la freccia in fondo alla scheda apre sotto ogni numero la sua nota.

## I colori della mappa
Nelle viste Aria, Temperatura e Salute i colori dividono i valori in cinque classi uguali fra il minimo e il massimo del periodo: dicono quale zona è più alta delle altre, non se supera un limite di legge. La vista Salubrità colora le zone secondo i limiti di legge. Alberi e Suolo sono dati statici.

## Zone grigie, puntinate e tratteggiate
Sulla mappa il grigio pieno indica un valore nullo, il contorno puntinato un valore non disponibile, il tratteggio una zona senza stazioni fisiche, dove l'unico dato sull'aria è quello modellato di CAMS.

## Le zone a confronto
Si possono mettere a confronto fino a quattro zone, distretti o comuni. Le zone a confronto compaiono nei grafici con un colore ciascuna.

## Il grafico giorno per giorno
Il grafico «giorno per giorno» mostra l'inquinante scelto, nel mese in cui finisce la finestra, per le zone a confronto e la fonte scelta. Un buco nella linea è un giorno senza valore.

## I grafici per distretto e mese
La scheda «Aria e salute per distretto e mese» impila, con lo stesso asse dei mesi, l'inquinante, la temperatura ERA5-Land (massima, media o minima giornaliera, a scelta, come media del mese), i decessi per tutte le cause e i dati simulati, per i soli distretti a confronto. È la grana del confronto fra i domini: distretto per mese.

## La Stagionalità
La tab Stagionalità confronta i 12 mesi dell'anno su tutto l'archivio, per il Salento o per un distretto: la finestra della barra temporale non ne cambia i numeri. I blocchi, in ordine: Quando intervenire, Periodi critici, Cosa sta cambiando, 12 mesi a confronto (con il mese anno per anno nello stesso blocco, in tre righe di sintesi aria, calore e salute che si aprono sul dettaglio), l'anno su anno e i ricoveri (dimissioni ospedaliere annuali per provincia, solo informative). Ordina i mesi per tema (aria, temperatura massima, decessi e i dati simulati): rango 1 è il mese peggiore, 12 il migliore. Un mese è critico per un tema se è fra i suoi 3 mesi peggiori; più mesi vicini critici per almeno due temi formano un periodo critico. I consigli in cima sono spunti da valutare, non prescrizioni. Dal cuore di Quando intervenire si apre ONE con le domande sulla medicina di iniziativa: come ridurre l'ospedalizzazione, quali zone privilegiare per l'ADI, come ridurre le ospedalizzazioni ripetute e il report delle linee d'azione.

## Fonti a confronto e Riepilogo
Fonti a confronto mostra, per la zona scelta, quanto le fonti concordano su aria, decessi e temperatura. Il Riepilogo è una tabella con una riga per distretto e tutti i dati della finestra, con la variazione dell'inquinante rispetto alla finestra precedente.
