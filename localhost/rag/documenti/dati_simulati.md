---
argomenti: [dati_simulati]
soggetti: [dati simulati, pronto soccorso, PS, ADI, assistenza domiciliare integrata, ricoveri, scenario letteratura, scenario nullo, dicitura]
fonte: docs/fonti/Dati_Simulati.md
aggiornato: 2026-10-30
---

# Dati sanitari simulati

## Dicitura
Dati sanitari simulati: ricoveri, accessi in pronto soccorso e accessi degli assistiti in assistenza domiciliare integrata sono generati da un modello statistico calibrato su dati pubblici e servono come dati di partenza per costruire e collaudare la piattaforma. Non descrivono la situazione sanitaria reale del Salento: non vanno usati per decisioni né citati come risultati. Nella dashboard sono segnati da un'icona a forma di beuta, con la scritta «Dato simulato, non reale».

## Perché si simula
Nessuna fonte pubblica dà ricoveri, accessi in pronto soccorso o assistiti in assistenza domiciliare per comune o distretto e per giorno. I dati richiesti ad AReSS Puglia e a Parsec 3,26 non sono arrivati e il progetto usa solo i dati che ha già. I dati simulati hanno la stessa forma che avrebbero quelli reali, così la piattaforma potrebbe riceverli senza cambiare l'interfaccia.

## Cosa si simula
Ricoveri per malattie respiratorie e circolatorie; accessi in pronto soccorso, in totale, per cause respiratorie e per cause cardiovascolari; accessi in pronto soccorso degli assistiti in assistenza domiciliare integrata (ADI), con la quota a bassa urgenza e i ritorni entro 30 giorni. Tutti per comune e per giorno. I decessi restano quelli reali dell'ISTAT; le malattie croniche non si simulano.

## Gli scenari
Ci sono due scenari, scelti nella testata della dashboard. Nello scenario «nullo» contano solo popolazione, stagione, giorno della settimana e caso: aria e caldo non hanno alcun effetto. Nello scenario «letteratura», quello predefinito, all'aria e al caldo è assegnato un effetto tratto da studi pubblicati. I due scenari usano lo stesso generatore casuale, quindi la differenza fra i due è l'effetto imposto, non il caso.

## Gli effetti dello scenario letteratura
Il PM10 aumenta i ricoveri e gli accessi respiratori dello 0,75% ogni 10 µg/m³ (studio EpiAir2). L'NO2 aumenta gli eventi cardiovascolari dello 0,57% ogni 10 µg/m³ (EpiAir2). Il caldo aumenta gli eventi respiratori del 4,5% per ogni grado di temperatura massima oltre 30 °C (Michelozzi e colleghi, 2009). L'esposizione di ogni comune è presa da CAMS per l'aria e da ERA5-Land per la temperatura. Questi effetti sono imposti dal progetto: le relazioni che si vedono nei dati simulati riflettono queste ipotesi, non la realtà.

## Come si legge l'unità
I dati simulati sono espressi in eventi per 100.000 residenti al giorno, con il totale del periodo accanto. Il valore di un distretto o del Salento è la somma dei suoi comuni.

## Su cosa sono calibrati
I ricoveri sono calibrati sulle dimissioni ospedaliere ISTAT per provincia. Gli accessi in pronto soccorso su 311 accessi ogni 1.000 abitanti l'anno, il dato nazionale dell'Annuario statistico del Servizio sanitario nazionale 2023. La stagionalità sull'andamento medio dei decessi reali del Salento. L'assistenza domiciliare su uno studio piemontese del 2021.

## Il caso dell'assistenza domiciliare
L'obiettivo è far emergere i periodi in cui gli assistiti in assistenza domiciliare arrivano più spesso in pronto soccorso, la quota di accessi a bassa urgenza che una visita a domicilio potrebbe evitare e gli assistiti che tornano entro 30 giorni. Con dati reali, servirebbe al distretto per organizzare in anticipo medici di famiglia, volontariato e protezione civile, con telefonate mirate e visite domiciliari.

## Cosa mostra la verifica dei dati simulati
L'effetto del caldo imposto si ritrova nei dati. Gli effetti di PM10 e NO2, alla loro dimensione reale, non si distinguono dal caso in meno di tre anni di dati: è un limite che vale anche per i dati reali. Senza togliere l'effetto della stagione, la correlazione fra temperatura massima e ricoveri respiratori risulta negativa anche quando il caldo li aumenta, perché d'inverno i ricoveri sono di più. È la prova, con dati di cui si conosce la verità, che una correlazione grezza può ingannare.
