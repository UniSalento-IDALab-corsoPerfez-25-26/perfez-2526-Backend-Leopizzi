---
argomenti: [scheda]
card: riepilogo
soggetti: [riepilogo, tabella, distretti, colonne, Δ, variazione, salubrità]
fonte: localhost/dashboard/src/componenti/TabellaRiepilogo.tsx; Informazioni (Riepilogo)
aggiornato: 2026-11-03
---

# Riepilogo per distretto

## Cosa mostra il «Riepilogo per distretto»
Una tabella con una riga per ciascuno dei 20 distretti e tutti i dati della finestra della testata, a gruppi di colonne: territorio, aria, salubrità, salute, ricoveri della provincia, salute simulata e calore. In fondo la Δ dell'inquinante della testata rispetto alla finestra precedente della stessa ampiezza. Serve a confrontare tutti i distretti su tutto in un colpo d'occhio.

## Quali dati contiene il «Riepilogo per distretto»
Aria: la media della finestra dalla fonte scelta in testa alla tabella. Salubrità: il peggiore inquinante su tutte le fonti, non solo quella scelta. Decessi: somma dei mesi toccati dalla finestra, tutte le cause, dati provvisori, con la media al giorno. Ricoveri: dimissioni annuali della provincia, uguali per i distretti della stessa provincia, solo informative. Salute simulata: dati simulati, non reali, per 100.000 residenti al giorno. Calore: temperatura media, massima e minima ERA5-Land, un dato modellato.

## Come si legge il «Riepilogo per distretto»
Un clic su un'intestazione ordina la tabella per quella colonna; un clic su una riga mette il distretto fra le zone a confronto o lo toglie. La colonna dei distretti resta ferma mentre la tabella scorre; il bordo destro sfumato dice che ci sono altre colonne. Una cella senza valore mostra il segno del dato mancante, col motivo nel riquadro che compare passandoci sopra.
