---
argomenti: [assistente]
soggetti: [assistente, ONE, scopo, nome, chat, cuore, domande proposte, dati usati, numeretti, verifica, rifiuto, Qwen, Ollama]
fonte: localhost/dashboard/src/componenti/Informazioni.tsx (argomento Assistente)
aggiornato: 2026-11-10
---

# ONE, l'assistente

## Che cosa fa ONE
L'assistente della dashboard si chiama ONE. Il suo scopo è guidare chi organizza i servizi sanitari verso la medicina di iniziativa, per ridurre l'ospedalizzazione evitabile: dal sommario «Quando intervenire» della Stagionalità dice quando, dove e su cosa concentrare le azioni e propone le linee d'azione dei documenti del progetto. ONE risponde a domande sui dati raccolti e visualizzati della sezione selezionata, passando per un processo di validazione che si compone di sei passi: un filtro che scarta le domande che cercano di cambiare le regole; la scelta del tipo di domanda da un elenco chiuso di argomenti e di analisi; il controllo di zona, periodo e inquinante; il calcolo dei numeri con il codice della dashboard, oppure la scelta dei brani dei documenti del progetto; la scrittura della risposta; la verifica finale, che controlla che ogni numero sia nei dati ricevuti e che il testo sia in italiano. Si apre dal cuore accanto all'icona della guida e risponde sulla scheda da cui è stato aperto.

## La chat e i suoi strumenti
La chat sta ferma sulla destra della finestra, sempre intera: il resto della pagina si stringe a sinistra e scorre per conto suo. Si apre con un messaggio di benvenuto e tre domande proposte; le altre si vedono scorrendo l'elenco. Il pulsante «Nuova chat» svuota la conversazione e ricomincia sulla stessa scheda. Il pulsante «Copia in Markdown» copia negli appunti domande, risposte, avvertenze e dati usati in formato Markdown, pronti da incollare in un documento. Si chiude con la croce in alto o con il tasto Esc.

## Le domande che si possono fare
Ci sono tre tipi di domande. Sulla scheda aperta: «Cosa sto guardando?», «Come si legge?», «Quali dati contiene?». Sul significato dei dati: «Cosa vuol dire dato modellato?», «Cosa sono i dati simulati?», «Che cos'è l'ozono?», «Perché i decessi sono solo per distretto?». Sui numeri della scheda aperta: sul grafico «giorno per giorno» «Qual è stato il giorno peggiore?», «Quanti giorni oltre i limiti di legge?», «L'inquinante sale quando fa caldo?»; su «Aria e salute per distretto e mese» «Quale distretto ha avuto più decessi?», «Aria e decessi salgono insieme?», «Caldo e decessi sono collegati?»; sulla carta «Qual è la zona peggiore?», «Com'è la zona in primo piano?»; nella «Sintesi della finestra» e nel «Riepilogo per distretto» «Dove si collocano le zone a confronto?», «Dove è cambiato di più l'inquinante?»; in «Fonti a confronto» «Le fonti sono d'accordo?»; sui ricoveri «I ricoveri stanno aumentando?»; nella Stagionalità «Quando conviene prepararsi?», e su «Quando intervenire» «Come si può ridurre l'ospedalizzazione?», «Quali zone privilegiare per l'assistenza ADI?», «Come ridurre le ospedalizzazioni ripetute?», «Prepara un report con le linee d'azione», «Il mese peggiore torna ogni anno?», «Questo mese è cambiato rispetto agli anni precedenti?», «Cosa è cambiato di più?». In fondo alla chat ci sono le domande proposte della scheda, già pronte da cliccare.

## Leggere una risposta di ONE
I numeretti nel testo indicano le basi della risposta: passandoci sopra si vede il fatto calcolato o il brano del documento usato, e la voce «Dati usati» li elenca. Le avvertenze sotto la risposta, come dato modellato, dato simulato o relazione esplorativa, le aggiunge il sistema. Se la verifica finale non passa, il testo non si mostra e restano solo i dati calcolati. Il controllo riguarda i numeri, non le parole: nel dubbio fanno fede i dati usati.

## Cosa ONE non fa
ONE risponde solo a un elenco chiuso di argomenti e analisi. A ogni altra richiesta risponde sempre con lo stesso messaggio: «La richiesta non può essere processata o non esiste nessun dato a riguardo nel sistema.» Vale anche per i consigli medici, le terapie e i farmaci per una persona, i nomi di pazienti o di medici, i giudizi su enti o professionisti, le previsioni, le zone fuori dal Salento, i testi creativi, le richieste sulle sue istruzioni, i decessi per comune e per giorno e i periodi che non sono in archivio. Su «Aria e salute per distretto e mese» i numeri riguardano solo l'inquinante, la temperatura e i decessi: le domande sui numeri dei dati simulati o dei ricoveri ricevono lo stesso messaggio.

## Dove gira ONE
ONE usa Qwen3.5 4B, un modello linguistico open source e preaddestrato, usato così com'è, senza addestramento sui dati del progetto, ed eseguito con Ollama sullo stesso computer della dashboard. Domande, dati e risposte non escono dal computer, per scelta del committente Parsec 3,26. Se il modello è spento, la chat lo dice e mostra i soli dati calcolati e le descrizioni della scheda, senza commento.
