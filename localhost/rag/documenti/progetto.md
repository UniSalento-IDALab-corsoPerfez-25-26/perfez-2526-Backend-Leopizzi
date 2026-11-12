---
argomenti: [progetto]
soggetti: [OneHealth, dashboard, Salento, destinatari, assistente]
fonte: repository Presentation, documentazione/Descrizione_Progetto.md
aggiornato: 2026-11-01
---

# Il progetto OneHealth

## Che cos'è OneHealth
OneHealth è una dashboard di supporto alle decisioni per presidi medici e aziende sanitarie, pubbliche e private, del Salento. Confronta per zona e nel tempo tre domini: la qualità dell'aria, il calore urbano e la salute. Serve a capire quali zone e quali periodi dell'anno sono critici e dove conviene concentrare le risorse.

## A chi serve
La dashboard è pensata per due figure, con pari peso. Il direttore di distretto o di azienda sanitaria, che decide dove e quando concentrare le risorse (pronto soccorso, assistenza domiciliare, medici di famiglia, volontariato, protezione civile) e legge soprattutto sintesi e criticità. La seconda figura è l'analista del controllo di gestione, che confronta zone, fonti e domini e verifica la qualità di ogni dato. Non è previsto l'utilizzo dell'interfaccia da parte del cittadino.

## Che territorio copre
Il Salento, inteso come le tre province di Lecce, Brindisi e Taranto. Il territorio è diviso in 20 distretti socio-sanitari e 145 comuni. Il distretto è l'unità con cui ragionano le aziende sanitarie ed è anche la grana minima a cui si mostrano i dati di salute.

## Su quali dati si basa
Solo dati pubblici, con licenza, scaricati dalle fonti ufficiali: nessun sensore, nessuna rilevazione sul campo e nessun accesso ai gestionali delle aziende sanitarie. Non esiste un dataset già pronto che unisca aria e salute per il Salento: OneHealth lo costruisce incrociando le fonti e confrontandole fra loro per verificarle.

## Cosa non fa
OneHealth non stabilisce cause. Le relazioni fra aria, calore e salute che mostra sono esplorative: aiutano a individuare periodi e zone da guardare meglio, non dimostrano che una cosa provochi l'altra. Non dà indicazioni mediche alle persone: i dati sono aggregati per zona e servono a organizzare i servizi.

## L'assistente
L'assistente della dashboard risponde solo sui dati e sui documenti del progetto. Usa Qwen3.5 4B, un modello linguistico open source e preaddestrato, senza addestramento sui dati del progetto, eseguito con Ollama. Gira interamente sul computer locale, senza inviare dati a servizi esterni, per scelta del committente Parsec 3,26. Per le descrizioni usa questi documenti; per i numeri usa le analisi già programmate nel progetto. A ogni altra domanda risponde che la richiesta non può essere processata.

## Chi lo ha realizzato
OneHealth è un progetto di Matteo Leopizzi per il Corso di Perfezionamento in Tecnologie Digitali per Ambienti e Sistemi Intelligenti dell'Università del Salento (IDA Lab), sviluppato con l'azienda partner Parsec 3,26 di Lecce.
