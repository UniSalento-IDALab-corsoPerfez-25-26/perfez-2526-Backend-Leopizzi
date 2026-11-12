"""Formato comune delle serie su cui lavorano le analisi dell'assistente (piano del modulo AI §13.3).

Ogni grafico della dashboard consegna le sue serie in questo formato; le analisi (analisi.py) leggono solo questo e
non sanno da quale grafico vengono. I valori arrivano già calcolati dalle funzioni del server (aggregazioni, stati
VALORE/NULL/NO_DATA, privacy): qui non si rifà nessuna media.
"""

from dataclasses import dataclass
from datetime import date

GRANE = ("giorno", "mese", "anno")
# misto: distretto con comuni misurati e comuni solo modellati; reale: conteggi ufficiali (decessi ISTAT), non stazioni
NATURE = ("misurato", "modellato", "misto", "simulato", "reale")


@dataclass(frozen=True)
class Punto:
    tempo: str  # AAAA-MM-GG, AAAA-MM o AAAA secondo la grana della serie
    valore: float | None
    stato: str  # VALORE | NULL | NO_DATA
    nota: str | None = None

    @property
    def valido(self):
        return self.stato == "VALORE" and self.valore is not None


@dataclass
class Serie:
    zona_id: str
    zona: str  # nome leggibile, come in dashboard: «Lecce (LE 51)», «Galatina»
    variabile: str  # «PM2.5», «temperatura massima»
    unita: str | None
    grana: str
    natura: str
    fonte: str
    statistica: str | None  # statistica giornaliera dichiarata dalla fonte (decide il confronto con i limiti)
    punti: list[Punto]

    def validi(self):
        return [p for p in self.punti if p.valido]

    @property
    def temperatura(self):
        return self.unita == "°C"


def ordinale(tempo, grana):
    """Posizione del punto sull'asse del tempo, in unità della grana (giorni, mesi, anni): serve a tendenze e ritardi."""
    if grana == "giorno":
        return date.fromisoformat(tempo).toordinal()
    anno = int(tempo[:4])
    return anno * 12 + int(tempo[5:7]) if grana == "mese" else anno


def da_punti(punti, **meta):
    """Serie da una lista di punti del server (PuntoGiorno, con `giorno`, o PuntoMese, con `mese`)."""
    convertiti = []
    for p in punti:
        tempo = getattr(p, "giorno", None) or getattr(p, "mese")
        convertiti.append(Punto(tempo=str(tempo), valore=p.valore, stato=p.stato, nota=p.nota))
    return Serie(punti=convertiti, **meta)
