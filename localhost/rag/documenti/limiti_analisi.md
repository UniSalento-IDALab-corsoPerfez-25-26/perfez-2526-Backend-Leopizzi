---
argomenti: [limiti_analisi]
soggetti: [correlazione, causalità, confondenti, analisi esplorativa, dato modellato, stagionalità, potenza statistica, dato aggregato]
fonte: docs/Regole_dei_dati.md; docs/fonti/Dati_Simulati.md
aggiornato: 2026-10-30
---

# Limiti delle analisi

## Esplorativo, non causale
Tutte le relazioni che la dashboard mostra fra aria, calore e salute sono esplorative. Indicano che due grandezze si muovono insieme in una certa zona e in un certo periodo, non che una provochi l'altra. Servono a scegliere dove e quando guardare meglio, non a dimostrare un effetto.

## I fattori che la dashboard non vede
Sulla salute pesano molti fattori che i dati pubblici non contengono: l'età della popolazione, il fumo, le malattie già presenti, l'aria degli ambienti chiusi, l'accesso alle cure. Questi fattori, detti confondenti, possono creare o nascondere una relazione fra aria e salute.

## La stagione inganna
Molte grandezze cambiano con la stagione per conto loro: d'inverno ci sono più ricoveri e più decessi, d'estate più ozono e più caldo. Confrontando i dati senza tener conto della stagione si possono vedere relazioni che non esistono, o di segno opposto a quello vero. Nei dati simulati, ad esempio, la correlazione grezza fra temperatura massima e ricoveri respiratori è negativa anche se il caldo li fa aumentare.

## Dati aggregati, non persone
I dati descrivono zone e periodi, non persone. Una relazione osservata per distretto e per mese non dice nulla sul rischio di un singolo individuo. Per questo l'assistente non dà indicazioni mediche personali.

## Dato modellato
Dove non ci sono stazioni, l'aria è stimata dal modello CAMS e la temperatura dalla rianalisi ERA5-Land, su griglie di circa 10 e 9 km. Sono stime del fondo regionale: le analisi fatte su questi dati vanno lette come basate su un modello, non su una misura.

## Effetti piccoli e pochi anni
Gli effetti dell'inquinamento sulla salute sono di solito piccoli, dell'ordine di meno dell'1% ogni 10 µg/m³. Con pochi anni di dati e popolazioni piccole, effetti di questa dimensione non si distinguono dalle oscillazioni casuali. Una relazione assente non dimostra che l'effetto non esista.

## Correlazioni con pochi giorni
Una correlazione calcolata su pochi giorni, ad esempio su un solo mese, è fragile: basta un giorno anomalo a cambiarla. Per questo ogni correlazione va letta insieme al numero di giorni o di mesi su cui è calcolata.
