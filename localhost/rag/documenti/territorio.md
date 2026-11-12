---
argomenti: [territorio]
soggetti: [province, distretti socio-sanitari, comuni, stazioni fisiche]
fonte: data/territorio/anagrafica/territorio.json; docs/fonti/Anagrafiche_relazionali.md
aggiornato: 2026-10-30
---

# Territorio

## Province, distretti e comuni
Il territorio del progetto è il Salento: le province di Lecce, Brindisi e Taranto. È diviso in 20 distretti socio-sanitari, che raggruppano 145 comuni. Ogni comune appartiene a un solo distretto.

## I distretti della provincia di Lecce
Dieci distretti, indicati con il numero e il comune sede: 51 Lecce, 52 Campi Salentina, 53 Nardò, 54 Martano, 55 Galatina, 56 Gallipoli, 57 Maglie, 58 Poggiardo, 59 Casarano, 60 Gagliano del Capo.

## I distretti della provincia di Brindisi
Quattro distretti: 1 Brindisi, 2 Fasano, 3 Francavilla Fontana, 4 Mesagne.

## I distretti della provincia di Taranto
Sei distretti: 1 Ginosa, 2 Massafra, 5 Martina Franca, 6 Grottaglie, 7 Manduria, 8 Taranto.

## Il comune di Presicce-Acquarica
Presicce e Acquarica del Capo sono un solo comune, Presicce-Acquarica, come lo pubblica l'ISTAT. Nel progetto compare sempre come un comune unico.

## Zone con e senza stazioni di misura
Le stazioni fisiche che misurano l'aria si trovano in 21 comuni su 145 e in 12 distretti su 20. Gli altri 8 distretti non hanno nessuna stazione: i distretti 53, 54, 56, 58, 59 e 60 della provincia di Lecce e i distretti 1 e 7 della provincia di Taranto. In questi distretti, e nei 124 comuni senza stazioni, l'unico dato sull'aria è quello modellato di Copernicus CAMS. Questa situazione non dipende dal periodo scelto.

## Da comune a distretto
Il valore di un distretto si ottiene dai suoi comuni. Per concentrazioni e temperature è la media pesata sui residenti dei comuni che hanno un valore: un comune di molti abitanti pesa più di uno piccolo. Per i conteggi, come i decessi, è la somma dei comuni. Per alberi e suolo impermeabile è la media pesata sulla superficie.

## Da stazione a comune
Il valore di un comune è la media delle sue stazioni fisiche che hanno un valore nel giorno. Il dato modellato CAMS è tenuto a parte e non entra in questa media.
