---
argomenti: [scheda]
card: fonti_aria
soggetti: [fonti a confronto, inquinante secondo ogni fonte, concordanza, validazione, ARPA, OpenAQ, EEA, CAMS]
fonte: localhost/dashboard/src/componenti/ConfrontoFonti.tsx; Informazioni (Aria: fonti a confronto)
aggiornato: 2026-11-03
---

# Inquinante secondo ogni fonte

## Cosa mostra «inquinante secondo ogni fonte»
Per la zona in primo piano, nel mese in cui finisce la finestra, l'inquinante della testata giorno per giorno secondo ciascuna fonte: ARPA Puglia, OpenAQ, EEA e Copernicus CAMS. Serve a vedere quanto le fonti si somigliano: la ridondanza fra fonti è il modo in cui il progetto le valida.

## Quali dati contiene «inquinante secondo ogni fonte»
Un valore al giorno per fonte, mai mediato fra fonti. OpenAQ, EEA e CAMS hanno la stessa statistica giornaliera, la media del giorno, e formano il gruppo di validazione. ARPA tiene il massimo giornaliero per NO2, O3, SO2 e CO: con le altre fonti si confronta solo qualitativamente. CAMS è un modello, a griglia di circa 10 km, e si confronta con la media delle stazioni del comune.

## Come si legge «inquinante secondo ogni fonte»
Ogni fonte ha il suo colore; CAMS è tratteggiato perché è un dato modellato. Sotto il grafico, per ogni coppia di fonti: quante celle hanno un valore in entrambe, la quota concordante entro una soglia e la differenza media. Due fonti che concordano si somigliano, ma questo non dice quale sia quella giusta.
