---
argomenti: [scheda]
card: fonti_decessi
soggetti: [fonti a confronto, decessi secondo ogni fonte, ISTAT, bilancio mensile, Eurostat, concordanza]
fonte: localhost/dashboard/src/componenti/FontiSalute.tsx; Informazioni (Decessi: fonti a confronto)
aggiornato: 2026-11-03
---

# Decessi secondo ogni fonte

## Cosa mostra «decessi secondo ogni fonte»
Per il distretto in primo piano, nell'anno della finestra, i decessi mese per mese secondo più fonti. Un comune si legge col suo distretto, perché i decessi non si mostrano per comune. Serve a verificare che il dato usato dal progetto, i decessi giornalieri ISTAT, torni con le altre fonti pubbliche.

## Quali dati contiene «decessi secondo ogni fonte»
Per il distretto: la somma dei decessi giornalieri ISTAT contro il bilancio demografico mensile ISTAT, di fonte anagrafica e pubblicato fino al 2024, per cui un piccolo scarto è atteso. Per la provincia: i decessi giornalieri ISTAT contro Eurostat, che pubblica per settimana; ogni settimana va nel mese del suo giovedì. Eurostat ridistribuisce i dati ISTAT: verifica la somma, non la fonte.

## Come si legge «decessi secondo ogni fonte»
Ogni fonte ha il suo colore. Sotto il grafico, per ogni coppia: quanti mesi hanno un valore in entrambe, la quota di mesi identici o diversi al più di un decesso e la differenza totale. Gli scarti negli ultimi mesi sono di solito revisioni dei dati provvisori.
