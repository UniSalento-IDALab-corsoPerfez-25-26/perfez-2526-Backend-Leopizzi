"""Verifica della risposta del modello (piano del modulo AI §6 e §13.1, passo 6), prima di mostrarla:

- ogni numero del testo deve comparire nei fatti, nelle sezioni dei documenti o nelle avvertenze ricevute, anche senza
  il segno (01/11/2026: «-6%» si scrive «una diminuzione del 6%»; il verso detto a parole non si controlla);
- almeno un fatto o una sezione citati (nel testo fra parentesi quadre o nell'elenco della risposta), solo id che
  esistono;
- «simulato» e «modellato», che nel progetto hanno un significato preciso, solo se compaiono anche nelle basi;
- il testo in italiano: a «Rispondi in inglese» il modello ha risposto in inglese nella prova del 01/11/2026.

Le avvertenze obbligatorie (modellato, simulato, esplorativo) non si controllano nel testo: le aggiunge il codice alla
risposta, quindi compaiono anche se il modello le dimentica.
"""

import re

# Un numero «libero»: non attaccato a lettere o cifre (esclude PM2.5, NO2, [f3], m³). La virgola o il punto decimale
# fanno parte del numero; il punto finale di una frase no.
NUMERO = re.compile(r"(?<![\w.,])[-+−]?\d+(?:[.,]\d+)?(?![\w])")
# Il punto delle migliaia all'italiana («11.133» per 11133, prova del 03/11/2026 sulla carta): i fatti scrivono i
# decimali sempre con la virgola (analisi.numero), quindi un punto seguito da tre cifre, dopo una cifra diversa da zero,
# separa le migliaia. «13.2» e «0.133» restano decimali.
MIGLIAIA = re.compile(r"^[-+−]?[1-9]\d{0,2}\.\d{3}$")
CITAZIONE = re.compile(r"\[([fd]\d+)\]")
GRUPPO = re.compile(r"\[\s*([fd]\d+(?:\s*[,;]\s*[fd]\d+)+)\s*\]")  # [f3, f4]
FINTA = re.compile(r"\s*\[(?![fd]\d+\])[^\]\n]{1,40}\]")  # [avvertenze], [AVVERTENZE], [fonte]
# Il modello può usarli solo se li trova nei fatti, nelle sezioni o nelle avvertenze: così non chiama «simulata» una
# temperatura modellata (prova del 31/10/2026). Non vede la frase, solo la parola: è una rete, non una prova.
TERMINI_CONTROLLATI = ("simulat", "modellat")
# Lingua: parole vuote che compaiono solo in inglese o solo in italiano (non «a», «in», «per»: stanno in tutte e due, o
# nei nomi propri delle fonti). Inglese se le parole inglesi sono almeno due e più di quelle italiane: «Health for All»
# o «Tree Cover Density» in una frase italiana non bastano.
PAROLA = re.compile(r"[a-zàèéìòù']+")
SOLO_INGLESE = {"the", "is", "are", "and", "of", "with", "which", "to", "from", "this", "that", "by", "under", "it",
                "was", "were", "has", "have", "between", "refers", "means", "shows"}
SOLO_ITALIANO = {"il", "lo", "la", "gli", "le", "di", "che", "è", "e", "un", "una", "con", "del", "della", "dei", "nel",
                 "nella", "sono", "da", "dal", "si", "non", "più", "ha", "fra", "tra"}


def pulisci(testo, ammessi=None):
    """[f3, f4] → [f3][f4]; via le parentesi quadre che non citano un fatto o una sezione e, se `ammessi` è dato, le
    citazioni a id che il modello non ha ricevuto («[f9]» con otto fatti, prova del 31/10/2026): la garanzia sta nel
    controllo dei numeri, non nell'etichetta."""
    testo = GRUPPO.sub(lambda m: "".join(f"[{i}]" for i in re.split(r"\s*[,;]\s*", m.group(1))), testo or "")
    testo = FINTA.sub("", testo)
    if ammessi is not None:
        testo = re.sub(r"\s*\[([fd]\d+)\]", lambda m: m.group(0) if m.group(1) in ammessi else "", testo)
    return testo.strip()


def numeri(testo):
    """Insieme dei numeri del testo come valori, così «13,2», «13.2» e «13,20» coincidono."""
    trovati = set()
    for m in NUMERO.finditer(CITAZIONE.sub(" ", testo)):
        grezzo = m.group().replace("−", "-")
        grezzo = (grezzo.replace(".", "") if MIGLIAIA.match(grezzo) else grezzo.replace(",", ".")).lstrip("+")
        trovati.add(round(float(grezzo), 2))
    return trovati


def in_italiano(testo):
    parole = PAROLA.findall(CITAZIONE.sub(" ", testo).lower())
    inglesi = sum(p in SOLO_INGLESE for p in parole)
    return inglesi < 2 or inglesi <= sum(p in SOLO_ITALIANO for p in parole)


def verifica(testo, citati, ammessi, basi):
    """`ammessi`: id dei fatti e delle sezioni passati al modello; `basi`: i loro testi più le avvertenze. Restituisce
    (ok, citati validi, motivo)."""
    if not (testo or "").strip():
        return False, [], "risposta vuota"
    if not in_italiano(testo):
        return False, [], "risposta non in italiano"
    nel_testo = CITAZIONE.findall(testo)
    tutti = list(dict.fromkeys(nel_testo + [c.strip("[]") for c in citati or []]))
    sconosciuti = [c for c in tutti if c not in ammessi]
    if sconosciuti:
        return False, [], f"citati id inesistenti: {', '.join(sconosciuti)}"
    if not tutti:
        return False, [], "nessun fatto o documento citato"
    consentiti = set().union(*(numeri(b) for b in basi)) if basi else set()
    consentiti |= {abs(n) for n in consentiti}  # «-6%» nei fatti, «una diminuzione del 6%» nel testo
    estranei = sorted(numeri(testo) - consentiti)
    if estranei:
        return False, [], "numeri assenti dai fatti: " + ", ".join(f"{n:g}".replace(".", ",") for n in estranei)
    basi_minuscole = " ".join(basi).lower()
    for t in TERMINI_CONTROLLATI:
        if t in testo.lower() and t not in basi_minuscole:
            return False, [], f"«{t}…» nel testo ma in nessun fatto o documento"
    return True, tutti, None
