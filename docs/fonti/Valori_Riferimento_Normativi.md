# Valori di riferimento normativi per la qualità dell'aria

*Report, 11/10/2026. Base per l'**indice di salubrità dell'aria** della dashboard (Tappa B, v. `docs/Specifiche_Design.md` del repository Frontend) e materiale per la tesi. Valori verificati da fonti autorevoli: EEA per la direttiva UE, OMS/IQAir per le linee guida, Gazzetta Ufficiale per il D.Lgs.*

## 1. A cosa serve

Per dire se l'aria di una zona è «salubre» rispetto alla legge servono i **valori limite** per ogni inquinante. Il progetto confronta il valore misurato con **tre riferimenti**, scelti da Matteo l'11/10/2026 (docs/Regole_dei_dati.md, decisione «Valori di riferimento dell'aria»):

1. **D.Lgs. 155/2010** — la norma **italiana in vigore** (recepisce la direttiva 2008/50/CE). È il metro legale attuale.
2. **Linee guida OMS 2021** (*WHO Global Air Quality Guidelines*) — le soglie **sanitarie più severe**, base della letteratura epidemiologica. Non sono legge: sono l'obiettivo di salute.
3. **Direttiva (UE) 2024/2881** — la **nuova** direttiva europea, limiti **in vigore dal 1° gennaio 2030**: mostra dove la norma si sta spostando (più vicina all'OMS).

L'indice complessivo per zona è il **peggiore inquinante** (stile EAQI europeo / IQA italiano): non una somma né una media, per non introdurre pesi arbitrari (coerente con il rifiuto dell'indice composito dell'UHRI, docs/Regole_dei_dati.md).

## 2. Regola fondamentale: confronto solo a parità di statistica

**Un valore si confronta con un limite solo se è calcolato sulla stessa statistica.** È il vincolo già fissato (docs/Regole_dei_dati.md «Come si confrontano le fonti», design §«Valori di riferimento»):

- **ARPA** pubblica il **massimo giornaliero** per NO2, O3, SO2 e CO (per PM10/PM2.5 la media giornaliera);
- **OpenAQ, EEA, CAMS** pubblicano la **media delle ore** del giorno.

Confrontare una media giornaliera con un limite **orario** sovrastima la conformità (una media è sempre ≤ del picco). Quindi, alla grana del dataset (**comune × giorno**):

| Dato disponibile | Si confronta con | Non si confronta con |
|---|---|---|
| media giornaliera (OpenAQ/EEA/CAMS; ARPA per PM) | limiti/linee guida **su 24 ore** | limiti **orari** e **medie annue** (serve l'anno intero) |
| massimo giornaliero (ARPA per NO2/O3/SO2/CO) | soglie **orarie** (il max del giorno è il picco orario) e soglia **info/allarme** | medie su 24 h e medie annue |

Dove la statistica non corrisponde a nessun riferimento → la cella dice **«non confrontabile»**, senza percentuale. Le **medie annue** (PM2.5, PM10, NO2, benzene) hanno senso solo su un'aggregazione annuale, non sulla finestra giornaliera della dashboard: in Tappa B vanno usate solo quando si guarda un anno intero.

## 3. Tabella dei valori limite (salute umana)

Concentrazioni in **µg/m³**, salvo il CO in **mg/m³**. «g/anno» = giorni di superamento ammessi per anno civile.

### PM2.5 — particolato fine
| Statistica | D.Lgs. 155/2010 | OMS 2021 | UE 2024/2881 (dal 2030) |
|---|---|---|---|
| media annua | **25** | **5** | **10** |
| media 24 h | — | **15** | **25** (max 18 g/anno) |

### PM10 — particolato
| Statistica | D.Lgs. 155/2010 | OMS 2021 | UE 2024/2881 (dal 2030) |
|---|---|---|---|
| media annua | **40** | **15** | **20** |
| media 24 h | **50** (max 35 g/anno) | **45** | **45** (max 18 g/anno) |

### NO2 — biossido di azoto
| Statistica | D.Lgs. 155/2010 | OMS 2021 | UE 2024/2881 (dal 2030) |
|---|---|---|---|
| media annua | **40** | **10** | **20** |
| media 24 h | — | **25** | **50** (max 18 g/anno) |
| massimo orario | **200** (max 18 g/anno) | **200** (non rivalutata dal 2005) | **200** (max 3 g/anno) |

### O3 — ozono
| Statistica | D.Lgs. 155/2010 | OMS 2021 | UE 2024/2881 (dal 2030) |
|---|---|---|---|
| massimo giornaliero media 8 h | **120** valore obiettivo (max 25 g/anno, media su 3 anni) | **100** | **120** valore obiettivo (max 18 g/anno, media su 3 anni) |
| peak season (media del max 8 h sui 6 mesi più caldi) | — | **60** | — |

### SO2 — biossido di zolfo
| Statistica | D.Lgs. 155/2010 | OMS 2021 | UE 2024/2881 (dal 2030) |
|---|---|---|---|
| media annua | — (20 solo per ecosistemi, non salute) | — | **20** |
| media 24 h | **125** (max 3 g/anno) | **40** | **50** (max 18 g/anno) |
| massimo orario | **350** (max 24 g/anno) | — | **350** (max 3 g/anno) |
| 10 minuti | — | **500** (non rivalutata dal 2005) | — |

### CO — monossido di carbonio (mg/m³)
| Statistica | D.Lgs. 155/2010 | OMS 2021 | UE 2024/2881 (dal 2030) |
|---|---|---|---|
| massimo giornaliero media 8 h | **10** | **10** (non rivalutata dal 2005) | **10** |
| media 24 h | — | **4** | **4** (max 18 g/anno) |

### C6H6 — benzene (inquinante tracciato, non di riferimento dashboard)
| Statistica | D.Lgs. 155/2010 | OMS 2021 | UE 2024/2881 (dal 2030) |
|---|---|---|---|
| media annua | **5** | **nessuna soglia** (cancerogeno senza soglia: solo stima del rischio unitario) | **3,4** |

## 4. Soglie di informazione e di allarme (gas acuti)

Confermate dal D.Lgs. 155/2010 (in vigore). La direttiva (UE) 2024/2881 **rivede le soglie di informazione/allarme e ne aggiunge per il particolato**: i valori esatti dei gas sembrano confermati ma vanno ripresi dall'Allegato I del testo EUR-Lex prima della citazione puntuale in tesi (⏳).

| Inquinante | Soglia di informazione | Soglia di allarme |
|---|---|---|
| O3 | **180** µg/m³ (media oraria) | **240** µg/m³ (media oraria) |
| NO2 | — | **400** µg/m³ (3 ore consecutive) |
| SO2 | — | **500** µg/m³ (3 ore consecutive) |

Per l'indice di salubrità si usano i **valori limite/obiettivo** della §3; le soglie di allarme restano un riferimento per i picchi (ARPA, massimo giornaliero).

## 5. Mappatura sul dataset e correzioni all'anagrafica ✅ 12/10/2026

`inquinanti.json` aveva **un solo** `valore_limite` con `periodo_misurazione`, con alcune **imprecisioni** ora **corrette** (12/10/2026):

- **NO2**: `valore_limite` 200 etichettato «Massimo giornaliero» → i 200 µg/m³ sono il **limite orario**, non giornaliero. Il riferimento primario è ora la **media annua 40**.
- **O3**: `valore_limite` 180 «Massimo orario» → 180 è la **soglia di informazione**, non il valore obiettivo (che è 120 sul max 8 h). Il primario è ora **120 su max 8 h**; l'allarme è 240.
- **SO2**: `valore_limite` 350 «Massimo giornaliero» → 350 è il **limite orario**; il primario è ora la **media 24 h 125**; l'allarme 500.
- **PM2.5** 25, **PM10** 50, **CO** 10 mg/m³, **C6H6** 5: già corretti, invariati come primario.

Il campo singolo (`valore_limite`/`periodo_misurazione`/`soglia_allarme`) è **mantenuto corretto** per retrocompatibilità (è il limite D.Lgs. 155/2010 in vigore con la sua vera statistica) ed è stato affiancato da **tre blocchi** `riferimenti.{dlgs_155_2010, oms_2021, ue_2024_2881}`, ciascuno una lista di `{statistica, valore, unita, superamenti_ammessi, nota}`, più `soglie_acute.{informazione, allarme}`. Così la dashboard sceglie automaticamente il riferimento **compatibile con la statistica** del valore misurato.

**Vocabolario di `statistica`** (chiavi che il codice confronta): `media_annua`, `media_24h`, `massimo_orario`, `massimo_8h` (max della media mobile 8 h del giorno), `peak_season` (O3), `media_10min` (SO2 OMS). Le statistiche del dato misurato nel dataset sono due: `media_giornaliera` (OpenAQ/EEA/CAMS e ARPA per PM) e `massimo_giornaliero` (ARPA per NO2/O3/SO2/CO).

### 5bis. Confronto per grana del dato (risposta alle due domande operative)

**(1) Limiti orari/8 h ma noi abbiamo solo il giornaliero.** Un limite **orario** o **su 8 h** si confronta **solo con il massimo giornaliero** (ARPA per NO2/O3/SO2/CO): il massimo del giorno *è* il picco orario/8 h, quindi `max ≤ limite` ⇒ nessuna ora in superamento (conforme), `max > limite` ⇒ almeno un'ora in superamento (giorno di superamento). La **media giornaliera** (OpenAQ/EEA/CAMS) con un limite orario è **«non confrontabile»**: una media nasconde i picchi e sovrastima la conformità. Regola già in §2.

**(2) Dato mensile (finestra della dashboard) vs normativa.** Il dataset **conserva i valori giornalieri**: non si collassa in una media mensile per valutare i limiti. Nella finestra (anche un mese) si usano due metriche, coerenti con come la legge esprime i limiti:

- **limiti su 24 h** (PM10 50, PM2.5, SO2 125, NO2/SO2 OMS 24 h, …) → **conteggio dei giorni di superamento** nella finestra, confrontato con i superamenti ammessi/anno (es. «3 giorni > 50 µg/m³ dei 35 ammessi/anno»). È esattamente la metrica normativa, calcolabile a qualunque grana.
- **limiti orari/8 h** → conteggio dei **giorni in cui il massimo giornaliero supera** la soglia (solo ARPA).
- **limiti di media annua** (PM2.5, PM10, NO2, C6H6) → la **media della finestra** confrontata col limite annuo, ma **solo come indicativo** (stessa statistica — media — su un periodo più corto), etichettata «non è la media annua ufficiale». Diventa un confronto reale **solo su una finestra di un anno intero**.

Per il **sotto-indice di salubrità per inquinante** (rapporto al limite, poi indice complessivo = peggiore inquinante) si usa, in ordine: la media della finestra / limite di media annua dove esiste; altrimenti il conteggio dei giorni di superamento. Dove nessuna statistica corrisponde → «non confrontabile», senza percentuale. *(Punto (2) proposto il 12/10/2026, da confermare con Matteo prima di scrivere l'aggregazione server.)*

## 6. Fonti (stile Chicago, voci complete in `Bibliografia.md` del repository Presentation)

- **D.Lgs. 155/2010** — Decreto legislativo 13 agosto 2010, n. 155, *Attuazione della direttiva 2008/50/CE…*, Gazzetta Ufficiale n. 216 del 15 settembre 2010, S.O. n. 217. Chiave LaTeX: `dlgs_155_2010`.
- **OMS 2021** — World Health Organization, *WHO Global Air Quality Guidelines: Particulate Matter (PM2.5 and PM10), Ozone, Nitrogen Dioxide, Sulfur Dioxide and Carbon Monoxide* (Geneva: WHO, 2021). Chiave: `who_aqg_2021`.
- **Direttiva (UE) 2024/2881** — del Parlamento europeo e del Consiglio, 23 ottobre 2024, *sulla qualità dell'aria ambiente e per un'aria più pulita in Europa (rifusione)*, GUUE serie L, 20 novembre 2024. Chiave: `dir_ue_2024_2881`.

Valori verificati l'11/10/2026 su: EEA, *Benchmark analysis against the standards in the revised Directive (EU) 2024/2881* (per la tabella UE 2030); OMS via IQAir, *New WHO air quality guidelines* (per le linee guida 2021); testo del D.Lgs. 155/2010 (Allegati VII, XI, XII).

## 7. Per la tesi

Questo report è materiale del capitolo su qualità dell'aria/metodo: documenta i tre quadri normativi, la loro progressiva convergenza verso le soglie sanitarie dell'OMS e il **limite metodologico** del confronto a parità di statistica (perché alcune celle restano «non confrontabili» alla grana giornaliera). Va letto insieme alla regola, già dichiarata, che la **scala di colore della mappa non usa soglie di legge** (è relativa min-max): l'indice di salubrità è un **secondo livello di lettura**, selezionabile, non la colorazione di default.

### Punti da inserire in tesi (accodati il 12/10/2026)

- **Il caso dell'O3 come limite metodologico onesto.** L'ozono risulta quasi sempre **«non confrontabile»** con i limiti di legge alla grana del progetto: i suoi riferimenti sono sul **massimo della media mobile 8 h** (valore obiettivo) e sulla **peak season**, statistiche che né la media giornaliera delle fonti (OpenAQ/EEA/CAMS) né il massimo orario di ARPA ricostruiscono. Da presentare in tesi come esempio concreto del principio di confronto a parità di statistica, non come lacuna dei dati.
- **Indice di salubrità dell'aria su tre riferimenti legislativi.** La dashboard introduce un livello di salubrità dell'aria calcolato rispetto a **tre quadri normativi** (D.Lgs. 155/2010 in vigore, linee guida OMS 2021, direttiva UE 2024/2881 dal 2030): sotto-indice per inquinante e indice complessivo = peggiore inquinante (stile EAQI/IQA, senza pesi), banda guidata dalla norma italiana in vigore con OMS e UE come secondo piano di lettura. Da descrivere come contributo di metodo (confronto multi-norma e multi-statistica) nel capitolo su dashboard/qualità dell'aria.
