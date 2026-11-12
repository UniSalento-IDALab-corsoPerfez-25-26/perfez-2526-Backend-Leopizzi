# Parametri di qualità dell'aria monitorati da ARPA Puglia

Generato automaticamente da `scripts/aria/inquinanti_arpa.py` il 2026-09-27, da ARPA Puglia (`old.arpa.puglia.it/ARPA_ARIA/inquinanti.jsp`, stesso contratto del servizio documentato `QualitaAria/Pollutants` — v. `api/aria/arpa_puglia.py`).

I 5 inquinanti di riferimento per la dashboard (CO, NO2, O3, PM2.5, SO2, v. `docs/Specifiche_Design.md` del repository Frontend) sono marcati con ✅; gli altri sono comunque monitorati da ARPA ma non fanno parte dell'elenco di riferimento, salvo diversa indicazione.

| Rif. dashboard | Sigla | Descrizione | Periodo di misurazione | Valore limite | Soglia di allarme | Unità |
|---|---|---|---|---|---|---|
|  | BLACK CARB | Prodotto della combustione incompleta di combustibili fossili e biomassa; può essere emesso da sorgenti naturali ed antropiche sotto forma di fuliggine. | null | null | null | ng/m³ |
|  | C6H6 | Liquido volatile e dall'odore dolciastro. Deriva dalla combustione incompleta del carbone e del petrolio, dai gas esausti dei veicoli a motore, dal fumo di tabacco. | Media annua | 5 | null | µg/m³ |
| ✅ | CO | Sostanza gassosa, si forma per combustione incompleta di materiale organico, ad esempio nei motori degli autoveicoli e nei processi industriali. | Max media mobile 8h giornaliera | 10 | null | mg/m³ |
|  | H2S | Gas incolore dal caratteristico odore di uova marce, caratterizzato da una soglia olfattiva bassa.  E' generato nella produzione di carbon coke, nella lavorazione del petrolio,  di fertilizzanti, dei rifiutie di altri procedimenti industriali. | null | null | null | µg/m³ |
|  | IPA | Classe di composti organici semi-volatili, con 2 o più da anelli benzenici condensati tra loro, generati dalla combustione incompleta di materiale organico. Il dato fornito si riferisce agli IPA adsorbiti su particelle carboniose con un diametro aerodinamico tra 0.01 e 1 micron | null | null | null | ng/m³ |
| ✅ | NO2 | Gas tossico che si forma nelle combustioni ad alta temperatura. Sue principali sorgenti sono i motori a scoppio, gli impianti termici, le centrali termoelettriche. | Massimo giornaliero | 200 | 400 | µg/m³ |
| ✅ | O3 | Sostanza non emessa direttamente in atmosfera, si forma per reazione tra altri inquinanti, principalmente NO2 e idrocarburi, in presenza di radiazione solare. | Massimo orario | 180 | null | µg/m³ |
|  | PM10 | Insieme di sostanze solide e liquide con diametro inferiore a 10 micron. Derivano  da emissioni di autoveicoli, processi industriali, fenomeni naturali. | Media giornaliera | 50 | null | µg/m³ |
| ✅ | PM2.5 | Insieme di sostanze solide e liquide con diametro inferiore a 2.5 micron. Derivano  da processi industriali, processi di combustione, emissionidi autoveicoli, fenomeni naturali. | Media annua | 25 | null | µg/m³ |
| ✅ | SO2 | Gas irritante, si forma soprattutto in seguito all'utilizzo di combustibili (carbone, petrolio, gasolio) contenenti impurezze di zolfo. | Massimo giornaliero | 350 | 500 | µg/m³ |
