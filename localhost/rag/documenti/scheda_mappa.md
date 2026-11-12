---
argomenti: [scheda]
card: mappa
soggetti: [carta, mappa, zona in primo piano, scheda della zona, particelle, vista, livello, distretti, comuni, salubrità]
fonte: localhost/dashboard/src/App.tsx (card-mappa), DettaglioZona.tsx, MappaZone.tsx; Informazioni (La carta, La scheda della zona)
aggiornato: 2026-11-03
---

# Carta e zona in primo piano

## Cosa mostra la carta
La carta colora i 20 distretti o i 145 comuni del Salento secondo la vista scelta: l'inquinante della testata, la salubrità dell'aria, la temperatura media, la copertura arborea, il suolo impermeabile o gli eventi sanitari. Vale per la finestra della testata, al più 31 giorni. Appoggiata a sinistra c'è la scheda della zona in primo piano, con i dati di quella zona dominio per dominio. ONE risponde sia sulla carta sia sulla scheda della zona.

## Quali dati contiene la carta
Aria: la media della finestra dalla fonte scelta in testa alla carta, una fonte alla volta oppure «Tutte», la media delle fonti concordi; nei comuni senza stazioni fisiche c'è solo il dato modellato di CAMS. Salubrità: il peggiore inquinante rispetto ai limiti del D.Lgs. 155/2010. Temperatura: ERA5-Land, un dato modellato. Alberi e suolo: CLMS, valori fissi del territorio. Eventi sanitari: decessi reali più ricoveri e accessi in pronto soccorso simulati, per 100.000 residenti al giorno. La scheda della zona aggiunge i decessi del distretto, i dati simulati e i ricoveri della provincia.

## Come si legge la carta
I colori dividono i valori in cinque classi fra il minimo e il massimo della finestra: dicono quale zona è più alta delle altre, non se supera un limite di legge; solo la vista Salubrità ha le bande dei limiti. Il grigio pieno è un valore nullo, il contorno puntinato un valore non disponibile, il tratteggio una zona senza stazioni fisiche. Un clic su una zona la porta nella scheda a sinistra; il doppio clic la mette fra le zone a confronto. Nella scheda, le sei particelle sul bordo scelgono la vista e accanto a ognuna c'è il dato della zona.
