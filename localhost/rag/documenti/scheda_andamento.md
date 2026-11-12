---
argomenti: [scheda]
card: andamento
soggetti: [giorno per giorno, grafico, inquinante, zone a confronto]
fonte: localhost/dashboard/src/componenti/GraficoAndamento.tsx; Informazioni (Giorno per giorno)
aggiornato: 2026-11-01
---

# Inquinante giorno per giorno

## Cosa mostra il grafico «giorno per giorno»
Il grafico mostra l'inquinante scelto nella testata, giorno per giorno, nel mese in cui finisce la finestra, per le zone a confronto: fino a quattro distretti o comuni, ciascuno con il suo colore. Serve a vedere i picchi del mese, i giorni critici e le differenze fra le zone.

## Quali dati contiene il grafico «giorno per giorno»
Un valore al giorno per zona, dalla fonte scelta sulla carta: ARPA Puglia, OpenAQ, EEA, Copernicus CAMS oppure la vista «Tutte», che è la media delle sole fonti concordi. Il valore di un comune è la media delle sue stazioni; quello di un distretto è la media dei suoi comuni pesata sui residenti. Nei comuni senza stazioni l'unico dato è quello modellato di CAMS. I valori sono in µg/m³, il CO in mg/m³.

## Come si legge il grafico «giorno per giorno»
Più è alta la linea, più è alta la concentrazione. Un buco nella linea è un giorno senza valore: passandoci sopra, il riquadro dice se il valore è non disponibile o nullo e perché. I colori sono quelli delle zone a confronto, non bande di salubrità: il grafico da solo non dice se un limite di legge è superato. Il pulsante con la freccia verso il basso, «Scarica CSV», dà gli stessi valori in un file.
