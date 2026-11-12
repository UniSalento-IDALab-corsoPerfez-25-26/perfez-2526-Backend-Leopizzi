"""Client minimo dell'API HTTP locale di Ollama: stato del servizio, modelli scaricati e /api/chat.

Il ragionamento («thinking») è spento per default: allunga i tempi e non serve, perché il modello non fa conti
(li fa la scheda dei fatti). Se il modello non accetta il parametro, si riprova senza.
"""

import requests

from localhost.rag import config


class OllamaNonDisponibile(RuntimeError):
    pass


def versione(url=config.URL_OLLAMA):
    """Versione di Ollama, o None se il servizio non risponde."""
    try:
        r = requests.get(f"{url}/api/version", timeout=2)
        return r.json().get("version") if r.ok else None
    except (requests.RequestException, ValueError):
        return None


def modelli_installati(url=config.URL_OLLAMA):
    """Nomi dei modelli scaricati in locale (es. 'qwen3.5:4b'); lista vuota se Ollama non risponde."""
    try:
        r = requests.get(f"{url}/api/tags", timeout=5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except (requests.RequestException, ValueError, KeyError):
        return []


def chat(messaggi, modello=config.MODELLO, schema=None, opzioni=None, pensiero=config.PENSIERO,
         timeout=config.TIMEOUT_S, url=config.URL_OLLAMA):
    """Una risposta completa (senza stream). Restituisce testo, eventuale ragionamento e tempi in secondi:
    `primo_token_s` ≈ caricamento del modello + lettura del prompt. `opzioni` si aggiungono a config.OPZIONI."""
    corpo = {"model": modello, "messages": messaggi, "stream": False, "think": pensiero, "keep_alive": "15m",
             "options": {**config.OPZIONI, **(opzioni or {})}}
    if schema is not None:
        corpo["format"] = schema
    try:
        r = requests.post(f"{url}/api/chat", json=corpo, timeout=timeout)
        if r.status_code == 400 and "think" in r.text:
            corpo.pop("think")
            r = requests.post(f"{url}/api/chat", json=corpo, timeout=timeout)
        r.raise_for_status()  # 404: modello non scaricato
    except requests.ConnectionError as e:
        raise OllamaNonDisponibile(f"Ollama non risponde su {url}") from e
    except requests.RequestException as e:
        raise OllamaNonDisponibile(f"Ollama ha risposto con un errore: {e}") from e
    d = r.json()
    s = lambda k: d.get(k, 0) / 1e9  # noqa: E731 — durate di Ollama in nanosecondi
    return {"testo": d["message"]["content"], "pensiero": d["message"].get("thinking") or None,
            "token_prompt": d.get("prompt_eval_count"), "token_risposta": d.get("eval_count"),
            "caricamento_s": s("load_duration"), "primo_token_s": s("load_duration") + s("prompt_eval_duration"),
            "totale_s": s("total_duration"),
            "token_al_s": d["eval_count"] / s("eval_duration") if d.get("eval_duration") else None}
