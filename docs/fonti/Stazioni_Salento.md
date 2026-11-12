# Stazioni ARPA Puglia nel Salento (Lecce, Brindisi, Taranto)

Anagrafica ufficiale ARPA Puglia (`stazioni_di_monitoraggio.json`, rigenerabile con `scripts/aria/aggiorna_stazioni_arpa.py`), incrociata con i distretti socio-sanitari (`data/territorio/lista_presidi/Distretti_Salento.json`).

**49 stazioni** nelle tre province (incluse le 6 private della rete ADI ex-ILVA a Taranto). Colonna "Inquinanti osservati 2023" = sigle realmente misurate secondo i dati scaricati (v. `scripts/aria/scarica_qualita_aria_2023.py`).

| Distretto | Provincia | Comune | Stazione | id | Rete | Interesse | Inquinanti osservati 2023 |
|---|---|---|---|---|---|---|---|
| BR-01 — DISTRETTO 1 | Brindisi | Brindisi | Brindisi - Cappuccini | 78 | IL | PUBBLICO | CO, NO2, PM10, SO2 |
| BR-01 — DISTRETTO 1 | Brindisi | Brindisi | Brindisi - Casale | 35 | RRQA | PUBBLICO | NO2, O3, PM10, PM2.5 |
| BR-01 — DISTRETTO 1 | Brindisi | Brindisi | Brindisi - Perrino | 77 | RRQA | PUBBLICO | CO, NO2, PM10, SO2 |
| BR-01 — DISTRETTO 1 | Brindisi | Brindisi | Brindisi - SISRI | 36 | RRQA | PUBBLICO | C6H6, CO, IPA, NO2, PM10, SO2 |
| BR-01 — DISTRETTO 1 | Brindisi | Brindisi | Brindisi - Terminal Passeggeri | 67 | RRQA | PUBBLICO | C6H6, CO, NO2, O3, PM10, PM2.5, SO2 |
| BR-01 — DISTRETTO 1 | Brindisi | Brindisi | Brindisi - Via Taranto | 24 | RRQA | PUBBLICO | C6H6, CO, NO2, PM10, PM2.5 |
| BR-01 — DISTRETTO 1 | Brindisi | Brindisi | Brindisi - Via dei Mille | 33 | RRQA | PUBBLICO | C6H6, NO2, PM10 |
| BR-01 — DISTRETTO 1 | Brindisi | Brindisi | C1 - Lato sud ovest impianti, Area imprese | 114 | VERSALIS | PRIVATO | C6H6, CO, NO2, PM10, PM2.5 |
| BR-01 — DISTRETTO 1 | Brindisi | Brindisi | C2 - Area bacino idrico | 115 | VERSALIS | PRIVATO | C6H6, CO, NO2, PM10, PM2.5 |
| BR-01 — DISTRETTO 1 | Brindisi | Brindisi | C3 - Area impianto P1CR Cracking | 116 | VERSALIS | PRIVATO | C6H6, CO, NO2, PM10, PM2.5 |
| BR-01 — DISTRETTO 1 | Brindisi | Brindisi | C4 - Area impianto Butadiene | 117 | VERSALIS | PRIVATO | C6H6, CO, NO2 |
| BR-01 — DISTRETTO 1 | Brindisi | Brindisi | C5 - Area Pontile | 118 | VERSALIS | PRIVATO | C6H6, CO, IPA, NO2, PM10, PM2.5, SO2 |
| BR-01 — DISTRETTO 1 | Brindisi | Brindisi | C6 - Area PE1/2 lato sud impianti | 119 | VERSALIS | PRIVATO | C6H6, CO, IPA, NO2, PM10, PM2.5, SO2 |
| BR-02 — DISTRETTO 2 | Brindisi | Cisternino | Cisternino | 108 | RRQA | PUBBLICO | NO2, O3, PM10, SO2 |
| BR-03 — DISTRETTO 3 | Brindisi | Ceglie Messapica | Ceglie Messapica | 96 | RRQA | PUBBLICO | C6H6, CO, NO2, PM10, PM2.5, SO2 |
| BR-03 — DISTRETTO 3 | Brindisi | Francavilla Fontana | Francavilla Fontana | 72 | RRQA | PUBBLICO | C6H6, NO2, PM10 |
| BR-04 — DISTRETTO 4 | Brindisi | Mesagne | Mesagne - Via Udine | 23 | RRQA | PUBBLICO | NO2, PM10 |
| BR-04 — DISTRETTO 4 | Brindisi | San Pancrazio Salentino | San Pancrazio | 25 | RRQA | PUBBLICO | NO2, PM10 |
| BR-04 — DISTRETTO 4 | Brindisi | San Pietro Vernotico | San Pietro Vernotico | 26 | RRQA | PUBBLICO | NO2, PM10 |
| BR-04 — DISTRETTO 4 | Brindisi | Torchiarolo | Torchiarolo - Don Minzoni | 27 | RRQA | PUBBLICO | C6H6, CO, IPA, NO2, PM10, PM2.5, SO2 |
| BR-04 — DISTRETTO 4 | Brindisi | Torchiarolo | Torchiarolo - Fanin      | 93 | RRQA | PUBBLICO | NO2, PM10, PM2.5, SO2 |
| BR-04 — DISTRETTO 4 | Brindisi | Torchiarolo | Torchiarolo-Lendinuso | 94 | IL | PUBBLICO | NO2, PM10, SO2 |
| LE-51 — DISTRETTO 51 | Lecce | Arnesano | Arnesano - Riesci | 31 | RRQA | PUBBLICO | O3, PM10 |
| LE-51 — DISTRETTO 51 | Lecce | Lecce | Lecce - Cerrate | 29 | RRQA | PUBBLICO | NO2, O3, PM10, PM2.5 |
| LE-51 — DISTRETTO 51 | Lecce | Lecce | Lecce - Garigliano | 47 | RRQA | PUBBLICO | C6H6, CO, NO2, PM10, PM2.5 |
| LE-51 — DISTRETTO 51 | Lecce | Lecce | Lecce - Libertini | 62 | RRQA | PUBBLICO | C6H6, CO, NO2, PM10, PM2.5 |
| LE-51 — DISTRETTO 51 | Lecce | Surbo | Surbo - Croce  | 95 | RRQA | PUBBLICO | NO2, PM10, SO2 |
| LE-52 — DISTRETTO 52 | Lecce | Campi Salentina | Campi Salentina | 51 | RRQA | PUBBLICO | NO2, PM10, PM2.5 |
| LE-52 — DISTRETTO 52 | Lecce | Guagnano | Guagnano - Villa Baldassarri | 28 | RRQA | PUBBLICO | NO2, PM10 |
| **LE-53 — DISTRETTO 53** | LE | *(nessuna stazione)* | | | | | |
| **LE-54 — DISTRETTO 54** | LE | *(nessuna stazione)* | | | | | |
| LE-55 — DISTRETTO 55 | Lecce | Galatina | Galatina - I.T.C.  La Porta  | 50 | RRQA | PUBBLICO | CO, NO2, O3, PM10, PM2.5 |
| LE-55 — DISTRETTO 55 | Lecce | Galatina | Galatina-Colacem | 113 | IL | PUBBLICO | C6H6, CO, NO2, PM10, PM2.5, SO2 |
| **LE-56 — DISTRETTO 56** | LE | *(nessuna stazione)* | | | | | |
| LE-57 — DISTRETTO 57 | Lecce | Maglie | Maglie | 49 | IL | PUBBLICO | CO, NO2, O3, PM10, PM2.5, SO2 |
| **LE-58 — DISTRETTO 58** | LE | *(nessuna stazione)* | | | | | |
| **LE-59 — DISTRETTO 59** | LE | *(nessuna stazione)* | | | | | |
| **LE-60 — DISTRETTO 60** | LE | *(nessuna stazione)* | | | | | |
| **TA-01 — DISTRETTO 1** | TA | *(nessuna stazione)* | | | | | |
| TA-02 — DISTRETTO 2 | Taranto | Massafra | Massafra | 75 | RRQA | PUBBLICO | C6H6, NO2, PM10, SO2 |
| TA-02 — DISTRETTO 2 | Taranto | Statte | Statte - Sorgenti | 18 | RRQA | PUBBLICO | CO, H2S, IPA, NO2, PM10, PM2.5, SO2 |
| TA-02 — DISTRETTO 2 | Taranto | Statte | Statte - Wind | 40 | RRQA | PUBBLICO | NO2, PM10, SO2 |
| TA-05 — DISTRETTO 5 | Taranto | Martina Franca | Martina Franca | 42 | RRQA | PUBBLICO | C6H6, NO2, PM10 |
| TA-06 — DISTRETTO 6 | Taranto | Grottaglie | Grottaglie | 41 | RRQA | PUBBLICO | NO2, O3, PM10 |
| **TA-07 — DISTRETTO 7** | TA | *(nessuna stazione)* | | | | | |
| TA-08 — DISTRETTO 8 | ILVA | Taranto | Cokeria | 100 | ADI | PRIVATO | — |
| TA-08 — DISTRETTO 8 | ILVA | Taranto | Direzione | 103 | ADI | PRIVATO | — |
| TA-08 — DISTRETTO 8 | ILVA | Taranto | Meteo Parchi | 104 | ADI | PRIVATO | — |
| TA-08 — DISTRETTO 8 | ILVA | Taranto | Portineria C | 105 | ADI | PRIVATO | — |
| TA-08 — DISTRETTO 8 | ILVA | Taranto | Riv1 | 102 | ADI | PRIVATO | — |
| TA-08 — DISTRETTO 8 | ILVA | Taranto | Tamburi - Via Orsini | 101 | ADI | PRIVATO | — |
| TA-08 — DISTRETTO 8 | Taranto | Taranto | Taranto - Alto Adige | 22 | RRQA | PUBBLICO | C6H6, CO, IPA, NO2, PM10, PM2.5, SO2 |
| TA-08 — DISTRETTO 8 | Taranto | Taranto | Taranto - Archimede | 19 | RRQA | PUBBLICO | CO, H2S, NO2, PM10, PM2.5, SO2 |
| TA-08 — DISTRETTO 8 | Taranto | Taranto | Taranto - CISI | 37 | RRQA | PUBBLICO | C6H6, CO, H2S, IPA, NO2, PM10, PM2.5, SO2 |
| TA-08 — DISTRETTO 8 | Taranto | Taranto | Taranto - Machiavelli | 20 | RRQA | PUBBLICO | C6H6, CO, IPA, NO2, PM10, PM2.5, SO2 |
| TA-08 — DISTRETTO 8 | Taranto | Taranto | Taranto - San Vito | 21 | RRQA | PUBBLICO | CO, IPA, NO2, O3, PM10, SO2 |
| TA-08 — DISTRETTO 8 | Taranto | Taranto | Taranto - Talsano | 38 | RRQA | PUBBLICO | IPA, NO2, O3, PM10, PM2.5, SO2 |
