---
argomenti: [scheda]
card: fonti_calore
soggetti: [fonti a confronto, temperatura secondo ogni fonte, ERA5-Land, ARPA meteo, concordanza, soglie di caldo]
fonte: localhost/dashboard/src/componenti/FontiCalore.tsx; Informazioni (Calore: fonti a confronto)
aggiornato: 2026-11-03
---

# Temperatura secondo ogni fonte

## Cosa mostra «temperatura secondo ogni fonte»
Per la zona in primo piano, nel mese in cui finisce la finestra, la temperatura giorno per giorno secondo le due fonti del progetto: ERA5-Land, un modello, e le stazioni ARPA meteo, una misura. Si sceglie la statistica giornaliera: media, massima o minima. Serve a vedere quanto il modello si avvicina alla misura.

## Quali dati contiene «temperatura secondo ogni fonte»
ERA5-Land è una rianalisi Copernicus a circa 9 km, disponibile per tutti i comuni. ARPA meteo misura solo nei comuni con una stazione: in un distretto il confronto si fa sugli stessi comuni, quelli con una stazione. Le due fonti non si mediano mai fra loro. Le soglie di caldo del progetto sono fisse: temperatura massima di almeno 30 °C e 35 °C, minima di almeno 20 °C e 25 °C.

## Come si legge «temperatura secondo ogni fonte»
ERA5-Land è tratteggiato perché è un dato modellato. Sotto il grafico: lo scarto medio fra le due fonti, l'errore medio, la correlazione e, per ogni soglia di caldo, quanti giorni la superano secondo ciascuna fonte. Uno scarto piccolo e costante dice che il modello segue la misura.
