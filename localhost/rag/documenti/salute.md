---
argomenti: [salute]
soggetti: [decessi, ISTAT, mortalità, privacy, dimissioni ospedaliere, ricoveri, Health for All, Eurostat, bilancio demografico, malattie croniche]
fonte: docs/fonti/ISTAT.md; docs/Regole_dei_dati.md (Salute, Privacy)
aggiornato: 2026-10-30
---

# Dati di salute

## Quali dati di salute sono reali
I dati di salute reali della dashboard sono due: i decessi dell'ISTAT e le dimissioni ospedaliere dell'ISTAT. Ricoveri giornalieri, accessi in pronto soccorso e assistenza domiciliare sono invece simulati: nessuna fonte pubblica li dà per comune o distretto e per giorno.

## I decessi ISTAT
L'ISTAT pubblica i decessi giornalieri per comune, per tutte le cause, dal 2011. Il progetto li somma su tutte le classi di età. Il file non contiene la causa di morte. Gli ultimi mesi pubblicati sono provvisori e possono essere rivisti. Licenza CC BY 4.0.

## Perché i decessi si vedono solo per distretto e mese
I decessi di un singolo comune in un singolo giorno sono numeri molto piccoli e potrebbero permettere di riconoscere le persone. Per proteggere la riservatezza la dashboard li mostra solo sommati per distretto e per mese. Per un comune il dato risulta non disponibile.

## Come si verificano i decessi
I decessi giornalieri ISTAT sono confrontati con altre due pubblicazioni: il bilancio demografico mensile per comune dell'ISTAT, che viene dalle anagrafi, ed Eurostat, che pubblica i decessi per provincia e settimana. Eurostat ridistribuisce gli stessi dati ISTAT: il confronto verifica che le somme tornino, e gli scarti degli anni più recenti sono revisioni dei dati provvisori. Con il bilancio demografico un piccolo scarto è atteso, perché le due fonti registrano i decessi in modo diverso.

## Le dimissioni ospedaliere
Le dimissioni ospedaliere vengono dalla banca dati ISTAT Health for All: ricoveri per malattie respiratorie, broncopneumopatia cronica ostruttiva, malattie circolatorie, ischemiche e cerebrovascolari, per provincia e per anno. Sono uguali per tutti i distretti della stessa provincia. Sono solo informative: non entrano nelle relazioni con aria e calore, perché un dato annuale e provinciale non si confronta con dati giornalieri o mensili per distretto. Licenza CC BY 4.0.

## Cosa manca
Nessuna fonte pubblica dà ricoveri, accessi in pronto soccorso o malattie per comune o per distretto: appena serve una causa o una patologia, il dato pubblico più fine è per provincia e per anno. Le malattie croniche non sono integrate e risultano non disponibili. I dati richiesti all'agenzia sanitaria regionale AReSS Puglia non sono ancora arrivati.

## La grana del confronto con aria e calore
Aria, calore e salute si confrontano per distretto e per mese: è la grana più fine comune ai tre domini e quella consentita dalla tutela della riservatezza. Per questo, quando la finestra scelta tocca più mesi, i decessi si sommano sui mesi toccati.

## Decessi al giorno con il segno «~»
Quando la dashboard scrive, ad esempio, «~5,2 decessi al giorno», il valore è il totale del mese diviso per i giorni del mese. Serve solo a leggere meglio il dato: non entra in nessun calcolo.
