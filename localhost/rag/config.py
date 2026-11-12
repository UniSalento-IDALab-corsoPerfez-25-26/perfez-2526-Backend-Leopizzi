"""Impostazioni dell'assistente: l'unico posto in cui si scelgono il
modello e il modo in cui risponde. Il client della dashboard non può cambiarle (barriera 1 del §12.3).

Il modello si cambia senza toccare il codice con la variabile d'ambiente ONEHEALTH_LLM (default qwen3.5:4b, scelto
da Matteo il 30/10/2026), l'indirizzo di Ollama con OLLAMA_HOST, come fa Ollama stesso.
"""

import os

MODELLO = os.environ.get("ONEHEALTH_LLM", "qwen3.5:4b")
URL_OLLAMA = "http://" + os.environ.get("OLLAMA_HOST", "127.0.0.1:11434").removeprefix("http://")

# Risposta fedele ai fatti: temperatura bassa, seme fisso per risposte ripetibili, ragionamento spento (il modello
# non fa conti: li fa il codice), contesto da 8k token, tetto alla lunghezza della risposta.
OPZIONI = {"temperature": 0.2, "num_ctx": 8192, "num_predict": 450, "seed": 42}
# Instradamento (§13.1, passo 2): temperatura 0 e un JSON corto; il tetto basta per tutti i campi dello schema.
NUM_PREDICT_INSTRADAMENTO = 160
# Il report delle linee d'azione (10/11/2026, card «Quando intervenire»): fino a 300 parole più il JSON delle citazioni.
NUM_PREDICT_REPORT = 1100
PENSIERO = False
TIMEOUT_S = 120

LUNGHEZZA_MAX_DOMANDA = 400  # caratteri

RIFIUTO = "La richiesta non può essere processata o non esiste nessun dato a riguardo nel sistema."
