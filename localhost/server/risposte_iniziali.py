"""Risposte della finestra iniziale tenute in memoria, già serializzate (03/11/2026): l'apertura della dashboard non
ricalcola nulla.

All'apertura la dashboard manda una quindicina di richieste insieme (finestra aria, finestra precedente, scheda della
zona, confronto fra domini...): da sole costano 1-2,5 s l'una, in parallelo si contendono il GIL e arrivavano a 8-11 s
a server caldo e a ~30 s a server freddo (misure del 03/11/2026). Il preriscaldamento (`_preriscalda` in main.py) le
chiede una volta all'app stessa, una dopo l'altra, e il middleware ne tiene il corpo JSON: le richieste uguali del
browser escono dalla memoria in pochi millisecondi.

Solo le richieste dichiarate con `tieni()` (quelle dell'apertura, dai valori predefiniti del frontend): le altre
passano senza toccare nulla. Una risposta vale finché non cambia la **firma** dei dati: il giorno (alcune risposte
dipendono dalla data di oggi) e numero e mtime più recente dei file che il server legge. Il server rilegge i file
cambiati da sé (mtime): se la firma cambia, le risposte si scartano e `al_cambio` rifà il preriscaldamento in
background, perché anche la finestra iniziale può essersi spostata.
"""

import asyncio
import os
import threading
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

RADICE = Path(__file__).resolve().parents[2]
# i file che il server legge: dataset e consuntivi, cache ERA5-Land e ARPA meteo, territorio e celle CAMS
CARTELLE_DATI = (RADICE / "data" / "interim", RADICE / "data" / "raw" / "calore", RADICE / "data" / "territorio")
FILE_DATI = (RADICE / "data" / "dataset" / "aria" / "copernicus_cams" / "Celle_Comuni.json",)
ESCLUSE = {RADICE / "data" / "interim" / "rag"}  # prove dell'assistente: non cambiano i dati della dashboard
VALIDITA_FIRMA_S = 2.0  # all'apertura arrivano ~15 richieste in un secondo: la firma (~25 ms) si calcola una volta


def chiave(percorso, query=""):
    """La richiesta in forma canonica: parametri decodificati e in ordine, così «LE,BR» e «LE%2CBR» coincidono."""
    if isinstance(query, bytes):
        query = query.decode("latin-1")
    parametri = sorted(parse_qsl(query, keep_blank_values=True)) if isinstance(query, str) else sorted(query.items())
    return f"{percorso}?{urlencode(parametri)}"


def _scansione(cartella):
    n, recente = 0, 0
    with os.scandir(cartella) as voci:
        for v in voci:
            if v.is_dir(follow_symlinks=False):
                if Path(v.path) not in ESCLUSE:
                    a, b = _scansione(v.path)
                    n, recente = n + a, max(recente, b)
            else:
                n, recente = n + 1, max(recente, v.stat().st_mtime_ns)
    return n, recente


def firma_dati():
    n, recente = 0, 0
    for c in CARTELLE_DATI:
        if c.exists():
            a, b = _scansione(c)
            n, recente = n + a, max(recente, b)
    for f in FILE_DATI:
        if f.exists():
            n, recente = n + 1, max(recente, f.stat().st_mtime_ns)
    return date.today().isoformat(), n, recente


class RisposteIniziali:
    def __init__(self):
        self._blocco = threading.Lock()
        self._da_tenere = set()
        self._risposte = {}  # chiave -> (firma, corpo, intestazioni)
        self._firma = None
        self._firma_letta = 0.0
        self.al_cambio = None  # chiamata (in un thread) quando la firma cambia: main.py rifà il preriscaldamento

    def firma(self):
        with self._blocco:
            if time.monotonic() - self._firma_letta < VALIDITA_FIRMA_S and self._firma is not None:
                return self._firma
        nuova = firma_dati()
        with self._blocco:
            cambiata = self._firma is not None and nuova != self._firma
            self._firma, self._firma_letta = nuova, time.monotonic()
            if cambiata:
                self._risposte.clear()
        if cambiata and self.al_cambio:
            threading.Thread(target=self.al_cambio, daemon=True).start()
        return nuova

    def tieni(self, chiavi):
        """Le richieste da tenere in memoria (sostituiscono le precedenti: la finestra iniziale può essere cambiata)."""
        with self._blocco:
            self._da_tenere = set(chiavi)
            self._risposte = {k: v for k, v in self._risposte.items() if k in self._da_tenere}

    def da_tenere(self, k):
        with self._blocco:
            return k in self._da_tenere

    def leggi(self, k):
        trovata = self._risposte.get(k)
        if trovata is None:
            return None
        return trovata if trovata[0] == self.firma() else None

    def salva(self, k, firma, corpo, intestazioni):
        with self._blocco:
            if k in self._da_tenere and firma == self._firma:
                self._risposte[k] = (firma, corpo, intestazioni)

    def mancanti(self):
        with self._blocco:
            return sorted(self._da_tenere - set(self._risposte))


class MiddlewareRisposteIniziali:
    """Middleware ASGI: serve dalla memoria le GET dichiarate, e ne tiene il corpo la prima volta che vanno a buon fine."""

    def __init__(self, app, memoria: RisposteIniziali):
        self.app = app
        self.memoria = memoria

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "GET":
            return await self.app(scope, receive, send)
        k = chiave(scope["path"], scope.get("query_string", b""))
        if not self.memoria.da_tenere(k):
            return await self.app(scope, receive, send)
        trovata = self.memoria.leggi(k)
        if trovata is not None:
            _, corpo, intestazioni = trovata
            await send({"type": "http.response.start", "status": 200, "headers": intestazioni})
            await send({"type": "http.response.body", "body": corpo})
            return
        firma = self.memoria.firma()  # presa prima del calcolo: se i file cambiano durante, la risposta non vale
        stato, intestazioni, parti = None, [], []

        async def invia(messaggio):
            nonlocal stato, intestazioni
            if messaggio["type"] == "http.response.start":
                stato, intestazioni = messaggio["status"], list(messaggio.get("headers", []))
            elif messaggio["type"] == "http.response.body":
                parti.append(messaggio.get("body", b""))
                if not messaggio.get("more_body") and stato == 200:
                    # le intestazioni CORS dipendono dall'origine di chi chiede: si riaggiungono a ogni risposta
                    tenute = [(n, v) for n, v in intestazioni if not n.lower().startswith(b"access-control-")]
                    self.memoria.salva(k, firma, b"".join(parti), tenute)
            await send(messaggio)

        await self.app(scope, receive, invia)


async def _chiedi(app, k):
    """Una GET all'app nel processo stesso, senza rete: passa dal middleware, che ne tiene la risposta."""
    percorso, _, query = k.partition("?")
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "scheme": "http",
             "path": percorso, "raw_path": percorso.encode(), "query_string": query.encode(), "root_path": "",
             "headers": [(b"host", b"127.0.0.1")], "client": ("127.0.0.1", 0), "server": ("127.0.0.1", 0)}
    stato = {}

    async def ricevi():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def invia(messaggio):
        if messaggio["type"] == "http.response.start":
            stato["codice"] = messaggio["status"]

    await app(scope, ricevi, invia)
    return stato.get("codice")


def prepara(app, memoria: RisposteIniziali, chiavi):
    """Dichiara le richieste dell'apertura e le chiede una alla volta (in parallelo si rallenterebbero a vicenda).
    Restituisce {chiave: codice HTTP}; una richiesta che fallisce resta fuori dalla memoria e si calcola come prima."""
    memoria.tieni(chiavi)
    memoria.firma()

    async def tutte():
        return {k: await _chiedi(app, k) for k in chiavi}

    return asyncio.run(tutte())
