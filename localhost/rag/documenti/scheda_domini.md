---
argomenti: [scheda]
card: domini
soggetti: [aria e salute, distretto, mese, decessi, temperatura, caldo, ricoveri, dati simulati]
fonte: localhost/dashboard/src/componenti/ConfrontoDomini.tsx; Informazioni (Aria e salute per distretto e mese)
aggiornato: 2026-11-03
---

# Aria e salute per distretto e mese

## Cosa mostra «Aria e salute per distretto e mese»
Grafici impilati con lo stesso asse dei mesi, per i distretti a confronto: l'inquinante scelto nella testata, la temperatura, i decessi per tutte le cause e i dati sanitari simulati. Serve a mettere accanto aria, caldo e salute alla stessa grana, distretto per mese, e a vedere se i mesi peggiori coincidono. Il periodo finisce con il mese della finestra e dura 6, 12 o 24 mesi, a scelta in alto nella scheda.

## Quali dati contiene «Aria e salute per distretto e mese»
Aria: la media del mese dell'inquinante scelto, pesata sui residenti dei comuni con un valore, dalla fonte scelta sulla carta. Temperatura: la media del mese della temperatura massima, media o minima giornaliera (a scelta sopra il grafico, massima all'apertura), da ERA5-Land, un dato modellato e non misurato (rianalisi a circa 9 km), pesata sui residenti dei comuni del distretto. Decessi: la somma dei decessi ISTAT per tutte le cause dei comuni del distretto, provvisori negli ultimi mesi e senza la causa di morte. Simulati: ricoveri, accessi in pronto soccorso e accessi degli assistiti in assistenza domiciliare, dati simulati e non reali. Ricoveri: le dimissioni ospedaliere annuali della provincia di residenza, da ISTAT Health for All, per gruppo di patologia, solo informative.

## Come si legge «Aria e salute per distretto e mese»
I grafici hanno lo stesso asse dei mesi e il cursore si muove su tutti insieme: passando su un mese si leggono l'aria, la temperatura e i decessi di quel mese. Ogni grafico ha la sua scala: aria e temperatura non si mettono mai sullo stesso asse. Ogni distretto ha il suo colore. I comuni a confronto non compaiono nei grafici di aria e decessi, perché i decessi si pubblicano solo per distretto: compaiono solo fra i dati simulati. I ricoveri (dimissioni ospedaliere annuali per provincia) non sono qui: sono l'ultimo blocco della Stagionalità. Due curve che salgono insieme non dimostrano che una causi l'altra: la lettura è esplorativa.
