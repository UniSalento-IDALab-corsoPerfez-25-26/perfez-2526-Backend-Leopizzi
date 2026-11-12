---
argomenti: [limiti_legge]
soggetti: [D.Lgs. 155/2010, OMS 2021, direttiva UE 2024/2881, salubrità, superamenti, statistica, CO, NO2, O3, PM2.5, SO2, PM10, C6H6]
fonte: api/aria/anagrafica_aria.py (RIFERIMENTI_NORMATIVI); docs/fonti/Valori_Riferimento_Normativi.md; localhost/server/salubrita.py
aggiornato: 2026-10-30
---

# Limiti di legge e salubrità dell'aria

## I tre riferimenti
La dashboard confronta l'aria con tre riferimenti. Il D.Lgs. 155/2010 è la legge italiana in vigore. Le linee guida dell'Organizzazione Mondiale della Sanità del 2021 (OMS 2021) sono raccomandazioni, più severe, senza valore di legge. La direttiva (UE) 2024/2881 fissa i nuovi limiti europei, che si applicheranno dal 2030. Il giudizio della dashboard segue il D.Lgs. 155/2010; OMS e UE compaiono come confronto.

## Confronto solo a parità di statistica
Un valore si confronta con un limite solo se è calcolato nello stesso modo. Un massimo giornaliero si confronta con un limite orario o su 8 ore; una media giornaliera con un limite sulle 24 ore e, solo come indicazione, con un limite sulla media annua. In ogni altro caso la dashboard scrive «non confrontabile», senza percentuali.

## Perché l'ozono è quasi sempre non confrontabile
I limiti dell'ozono sono definiti sul massimo della media mobile su 8 ore e sulla media della stagione calda. Le fonti che danno una media giornaliera non usano nessuna delle due statistiche, quindi per l'ozono il confronto con la legge quasi sempre non si può fare.

## Media annua confrontata con un mese
La finestra della dashboard dura al più un mese. Quando si confronta la media del periodo con un limite di media annua, il confronto è solo indicativo: è la stessa statistica, ma calcolata su un periodo più breve di quello previsto dalla legge.

## Superamenti ammessi
Per alcuni limiti la legge ammette un certo numero di giorni o di ore di superamento per anno civile. Un giorno oltre il limite quindi non è per forza una violazione: dipende da quanti superamenti si accumulano nell'anno.

## Limiti per il PM2.5
D.Lgs. 155/2010: media annua 25 µg/m³. OMS 2021: media annua 5 µg/m³, media sulle 24 ore 15 µg/m³. Direttiva UE 2024/2881, dal 2030: media annua 10 µg/m³, media sulle 24 ore 25 µg/m³ con 18 superamenti ammessi all'anno.

## Limiti per il PM10
D.Lgs. 155/2010: media annua 40 µg/m³, media sulle 24 ore 50 µg/m³ con 35 superamenti ammessi all'anno. OMS 2021: media annua 15 µg/m³, media sulle 24 ore 45 µg/m³. Direttiva UE 2024/2881, dal 2030: media annua 20 µg/m³, media sulle 24 ore 45 µg/m³ con 18 superamenti ammessi all'anno.

## Limiti per l'NO2
D.Lgs. 155/2010: media annua 40 µg/m³, limite orario 200 µg/m³ con 18 superamenti ammessi all'anno, soglia di allarme 400 µg/m³ per 3 ore consecutive. OMS 2021: media annua 10 µg/m³, media sulle 24 ore 25 µg/m³. Direttiva UE 2024/2881, dal 2030: media annua 20 µg/m³, media sulle 24 ore 50 µg/m³ con 18 superamenti ammessi, limite orario 200 µg/m³ con 3 superamenti ammessi.

## Limiti per l'O3
D.Lgs. 155/2010: valore obiettivo 120 µg/m³ sul massimo della media mobile su 8 ore, con 25 superamenti ammessi all'anno calcolati come media su 3 anni; soglia di informazione 180 µg/m³ e soglia di allarme 240 µg/m³ come media oraria. OMS 2021: 100 µg/m³ sul massimo su 8 ore e 60 µg/m³ come media della stagione calda. Direttiva UE 2024/2881, dal 2030: 120 µg/m³ sul massimo su 8 ore con 18 superamenti ammessi.

## Limiti per l'SO2
D.Lgs. 155/2010: media sulle 24 ore 125 µg/m³ con 3 superamenti ammessi all'anno, limite orario 350 µg/m³ con 24 superamenti ammessi, soglia di allarme 500 µg/m³ per 3 ore consecutive. OMS 2021: media sulle 24 ore 40 µg/m³. Direttiva UE 2024/2881, dal 2030: media annua 20 µg/m³, media sulle 24 ore 50 µg/m³ con 18 superamenti ammessi, limite orario 350 µg/m³ con 3 superamenti ammessi.

## Limiti per il CO
D.Lgs. 155/2010: 10 mg/m³ sul massimo della media mobile su 8 ore. OMS 2021: 10 mg/m³ sul massimo su 8 ore e 4 mg/m³ come media sulle 24 ore. Direttiva UE 2024/2881: 10 mg/m³ sul massimo su 8 ore e, dal 2030, 4 mg/m³ come media sulle 24 ore con 18 superamenti ammessi.

## Limiti per il benzene (C6H6)
D.Lgs. 155/2010: media annua 5 µg/m³. Direttiva UE 2024/2881, dal 2030: media annua 3,4 µg/m³. L'OMS non fissa un valore: considera il benzene cancerogeno senza una soglia sicura.

## Le bande di salubrità
Per ogni inquinante la dashboard assegna una banda: buona, accettabile, scadente, cattiva, oppure non confrontabile. Quando si contano i giorni oltre un limite, la banda è buona se non ce n'è nessuno, accettabile fino al 10% dei giorni con un valore, scadente fino al 25%, cattiva oltre. Quando si confronta una media con un limite, la banda è buona fino a metà del limite, accettabile fino al limite, scadente fino a una volta e mezzo il limite, cattiva oltre.

## La salubrità di una zona
La salubrità di una zona è quella del suo inquinante peggiore, come nell'indice europeo della qualità dell'aria. Non si usano pesi né punteggi combinati.

## I colori della mappa e i limiti
Nelle viste Aria, Temperatura e Salute i colori della mappa dicono soltanto quale zona ha un valore più alto delle altre nel periodo: non indicano se un limite è superato. Il confronto con la legge è nella vista Salubrità.
