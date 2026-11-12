---
argomenti: [calore]
soggetti: [UHRI, isola di calore, ERA5-Land, ARPA meteo, temperatura, soglie di caldo, giornata calda, notte tropicale, copertura arborea, alberi, suolo impermeabile, CLMS]
fonte: docs/fonti/Lista_dataset_calore.md; docs/fonti/Soglie_Caldo.md; docs/fonti/CLMS.md; localhost/dashboard/src/componenti/Informazioni.tsx
aggiornato: 2026-10-30
---

# Calore urbano

## Che cos'è l'UHRI
UHRI (Urban Heat Island Mitigation & Resilience) è il nome che il progetto dà alla misura del calore urbano. Non è un punteggio unico: sono grandezze mostrate una accanto all'altra, senza pesi né formule che le combinino. Oggi la dashboard ne mostra tre: la temperatura dell'aria, la copertura arborea e il suolo impermeabile. La quarta, l'intensità dell'isola di calore misurata da satellite, è rimandata a uno sviluppo futuro.

## Perché il calore va calcolato dal progetto
Nessun dato pubblico già pronto sulle isole di calore copre il Salento: il servizio europeo che le stima copre cento città, in Puglia solo Bari. Per questo il progetto ricava l'esposizione al caldo dalla temperatura dell'aria per comune.

## Temperatura da ERA5-Land
La fonte principale della temperatura è ERA5-Land, del servizio europeo Copernicus: temperatura dell'aria a 2 metri, media, massima e minima del giorno, su una griglia di circa 9 km. Copre tutti i comuni, ma è una rianalisi, cioè un dato modellato, non una misura. Per ogni comune il valore è la media delle celle pesata sulla parte di territorio comunale che ciascuna copre. Per Corsano e Patù, coperti da una sola cella quasi tutta sul mare, si usa la cella di terra più vicina. Licenza CC BY.

## Temperatura dalle stazioni ARPA meteo
La seconda fonte è la rete meteorologica di ARPA Puglia, con stazioni nel Salento che misurano la temperatura. Copre solo i comuni dove c'è una stazione e serve soprattutto a verificare ERA5-Land. Le due fonti non vengono mai mediate fra loro. Licenza CC BY 4.0.

## Le soglie di caldo
Dalla temperatura il progetto ricava quattro indicatori, uno per giorno e comune. Giornata calda: temperatura massima di almeno 30 °C. Giornata di caldo estremo: temperatura massima di almeno 35 °C. Notte tropicale: temperatura minima di almeno 20 °C. Notte equatoriale: temperatura minima di almeno 25 °C. Sono soglie fisse, uguali per tutti i comuni.

## Limiti delle soglie di caldo
ERA5-Land media la temperatura su celle di circa 9 km e smussa i picchi: rispetto alle stazioni conta circa un terzo in meno di giornate oltre 35 °C. I conteggi di caldo estremo vanno quindi letti come un valore minimo. Le soglie riguardano la temperatura dell'aria, non la temperatura percepita, che tiene conto anche di umidità e vento.

## Copertura arborea (vista Alberi)
È la percentuale di superficie del comune coperta dalla chioma degli alberi, uliveti e frutteti compresi, dal prodotto Tree Cover Density 2024 del servizio Copernicus di monitoraggio del territorio, a 10 metri di risoluzione. Gli alberi rinfrescano soprattutto di giorno.

## Suolo impermeabile (vista Suolo)
È la percentuale di superficie del comune coperta da asfalto, edifici e altre superfici sigillate, dal prodotto Imperviousness Density 2018 del servizio Copernicus di monitoraggio del territorio, l'ultima edizione pubblicata, a 10 metri di risoluzione. Il suolo sigillato trattiene il calore, soprattutto di notte.

## Come leggere alberi e suolo
Sono dati statici: non cambiano con il periodo scelto. Sono medie sull'intero comune, campagna compresa, quindi un comune grande e con molta campagna può avere poco suolo sigillato anche se il centro è molto costruito. Il valore del distretto è la media pesata sulla superficie dei comuni. Le due edizioni sono di anni diversi (2024 e 2018): descrivono il territorio e non si confrontano nel tempo. Non si combinano mai con la temperatura in un punteggio.
