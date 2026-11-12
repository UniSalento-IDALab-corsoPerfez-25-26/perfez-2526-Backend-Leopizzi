---
argomenti: [fonti_aria]
soggetti: [ARPA Puglia, OpenAQ, EEA, Copernicus CAMS, Tutte, dato misurato, dato modellato, validazione, valore giornaliero, licenze]
fonte: docs/fonti/Lista_dataset_aria.md; docs/Regole_dei_dati.md; localhost/dashboard/src/componenti/Informazioni.tsx
aggiornato: 2026-10-30
---

# Fonti dei dati sull'aria

## Le quattro fonti
I dati sull'aria vengono da quattro fonti pubbliche: ARPA Puglia, OpenAQ, l'Agenzia europea dell'ambiente (EEA) e il servizio europeo Copernicus CAMS. Le prime tre riportano misure di stazioni; CAMS è un modello. Ogni fonte resta separata nei dati: un valore per fonte, stazione, giorno e inquinante.

## ARPA Puglia
È la fonte principale: l'agenzia regionale che gestisce la rete di stazioni di qualità dell'aria. Pubblica un valore al giorno per stazione. Per PM10 e PM2.5 il valore è la media del giorno; per NO2, O3 e SO2 è il massimo orario del giorno; per il CO è il massimo della media mobile su 8 ore. Licenza CC BY 4.0.

## OpenAQ
Piattaforma internazionale che raccoglie e ridistribuisce le misure delle stazioni, fra cui quelle del Salento. Fornisce misure orarie, da cui il progetto ricava la media del giorno. Licenza ODC-BY; due stazioni del progetto partecipativo HabitatMap non dichiarano una licenza.

## EEA
L'Agenzia europea dell'ambiente pubblica le misure orarie che le agenzie nazionali le trasmettono, quindi in gran parte le stesse stazioni di ARPA. Il progetto ne ricava la media del giorno. I dati degli anni passati sono verificati; quelli dell'anno in corso sono provvisori e possono avere ore mancanti. Licenza CC BY 4.0.

## Copernicus CAMS
Servizio europeo che stima la qualità dell'aria con un modello su una griglia di circa 10 km. Copre tutto il territorio, anche dove non ci sono stazioni, ma è una stima, non una misura. Per ogni comune il valore è la media delle celle della griglia pesata sulla parte di territorio comunale che ciascuna copre. Licenza CC BY 4.0.

## Dato misurato e dato modellato
Un dato misurato viene da una stazione fisica. Un dato modellato viene da un modello matematico, come CAMS per l'aria o ERA5-Land per la temperatura: copre ogni zona ma descrive il fondo regionale, non l'esposizione di una strada o di un quartiere. La dashboard segna sempre il dato modellato con un'icona a forma di cubo.

## Zone dove c'è solo il dato modellato
In 124 comuni su 145 e in 8 distretti su 20 non ci sono stazioni fisiche: lì l'unico dato sull'aria è CAMS. Le analisi si fanno comunque, ma vanno lette come basate su un dato modellato.

## Un valore al giorno
Per ogni fonte, stazione e inquinante si tiene un solo valore al giorno. Quando la fonte dà misure orarie (OpenAQ, EEA, CAMS) il valore è la media delle ore disponibili, anche se il giorno è incompleto: la nota del dato dice su quante ore è calcolato. ARPA si tiene come la pubblica. I giorni sono calcolati sull'ora solare italiana.

## Perché le fonti si confrontano
Che più fonti riportino le stesse stazioni non è un doppione: permette di verificare i dati confrontandoli cella per cella. OpenAQ, EEA e CAMS calcolano il valore del giorno nello stesso modo e formano il gruppo di validazione. ARPA, che per alcuni inquinanti pubblica il massimo invece della media, si confronta a parte e solo in modo qualitativo.

## La vista «Tutte»
Nella vista «Tutte» la dashboard mostra, per ogni comune e giorno, la media delle sole fonti che concordano fra loro: entro 3 µg/m³ (0,1 mg/m³ per il CO) o entro il 20% della mediana. La fonte che si discosta viene scartata e la dashboard lo segnala. ARPA entra solo per PM10 e PM2.5, perché per gli altri inquinanti pubblica il massimo e un massimo non si media con delle medie. Dove non ci sono stazioni resta CAMS. È l'unica media fra fonti diverse ed è solo una lettura di sintesi: non entra nella salubrità né nel confronto fra fonti.

## Valori implausibili
Un valore di una stazione fuori misura per quell'inquinante (oltre la soglia di allarme di legge o, dove manca, oltre dieci volte il limite) esce dalla media del comune, ma resta nei dati della sua fonte.
