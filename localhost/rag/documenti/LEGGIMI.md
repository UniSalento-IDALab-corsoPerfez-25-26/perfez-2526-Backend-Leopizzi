# Documenti dell'assistente

Questa cartella contiene **l'unica base delle descrizioni** che l'assistente della dashboard può dare. Se un argomento non è scritto qui, l'assistente risponde: «La richiesta non può essere processata o non esiste nessun dato a riguardo nel sistema.»

I numeri che cambiano con i dati (medie, massimi, giorni oltre soglia) **non** vanno qui: li calcolano le analisi del catalogo in `localhost/rag/analisi/`. Questo file (`LEGGIMI.md`) non viene letto dall'assistente.

## Formato di un documento

Un file `.md` per argomento o soggetto, con in testa le proprietà fra due righe `---`:

```markdown
---
argomenti: [inquinanti]
soggetti: [PM2.5]
fonte: data/dataset/aria/anagrafica/inquinanti.json
aggiornato: 2026-10-30
---

# PM2.5

## Che cos'è
Particolato con diametro inferiore a 2,5 micrometri...

## Come lo misura il progetto
Un valore al giorno per fonte...
```

- **`argomenti`**: uno o più id dell'elenco qui sotto. Un id che non è nell'elenco rende il documento invisibile all'assistente.
- **`soggetti`**: le cose di cui parla il documento (un inquinante, una fonte, una vista della mappa). Servono a scegliere la sezione giusta.
- **`fonte`**: il documento del progetto da cui il testo è tratto, per poterlo ricontrollare.
- **`aggiornato`**: data dell'ultima revisione.
- **`card`** (solo per l'argomento `scheda`): l'id della card che il documento descrive, uno di `CARD` in `localhost/rag/schede.py`. Le sue sezioni si vedono solo quando la domanda arriva da quella card e, con l'argomento `scheda`, entrano tutte. Ogni documento di card ha tre sezioni: cosa mostra, quali dati contiene, come si legge.

## Regole di scrittura

1. **Sezioni `##` brevi e autonome.** L'assistente riceve singole sezioni, non il file intero: ogni sezione deve reggersi da sola, senza «come detto sopra».
2. **Solo contenuti stabili e verificati**, tratti dai documenti del progetto. Niente opinioni, niente note di lavoro interne.
3. **Scritti per chi legge la dashboard**: un responsabile di distretto o di presidio, non uno sviluppatore. Italiano semplice.
4. **Numeri solo se fissi** (un limite di legge, una soglia di caldo, il numero di distretti). L'assistente può citare solo i numeri presenti nel testo.
5. **Correlazioni sempre esplorative**, dato modellato e dato simulato sempre dichiarati, come nel resto del progetto.

## Argomenti ammessi

L'elenco è chiuso: un argomento nuovo si aggiunge qui e nel codice (`localhost/rag/`) nello stesso momento.

| id | Argomento |
|---|---|
| `progetto` | Che cos'è OneHealth, per chi è, che territorio copre |
| `territorio` | Province, distretti socio-sanitari, comuni |
| `inquinanti` | Cosa sono gli inquinanti tracciati e le loro unità di misura |
| `limiti_legge` | D.Lgs. 155/2010, OMS 2021, direttiva UE 2024/2881, confronto a parità di statistica |
| `fonti_aria` | ARPA, OpenAQ, EEA, CAMS; dato misurato e modellato; vista «Tutte» |
| `calore` | UHRI, temperatura ERA5-Land e ARPA meteo, soglie di caldo, copertura arborea, suolo impermeabile |
| `salute` | Decessi ISTAT, dimissioni HFA, perché i dati sono per distretto e mese |
| `dati_simulati` | Dati simulati di PS e ADI, scenari, dicitura |
| `lettura_dashboard` | Stati `N/D` e `null`, segni, viste della mappa, Stagionalità, salubrità |
| `limiti_analisi` | Perché le relazioni sono esplorative e non causali |
| `scheda` | La card aperta: cosa mostra, quali dati contiene, come si legge. Un documento per card (`scheda_<card>.md`), con la proprietà `card` |
| `assistente` | L'assistente stesso: cosa fa, come controlla le risposte, che domande gli si possono fare |
| `medicina_iniziativa` | Lo scopo di ONE (10/11/2026): medicina di iniziativa e riduzione dell'ospedalizzazione evitabile, leve organizzative, scelta di zone e periodi, report delle linee d'azione |
