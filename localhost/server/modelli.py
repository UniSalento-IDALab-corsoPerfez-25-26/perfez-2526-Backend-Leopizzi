"""Contratto dell'API locale (Pydantic): da qui FastAPI genera lo schema OpenAPI da cui
il frontend può ricavare i tipi TypeScript. Gli stati VALORE / NULL / NO_DATA arrivano
fino al frontend: non si convertono in 0 né si tolgono (v. docs/Regole_dei_dati.md)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Stato = Literal["VALORE", "NULL", "NO_DATA"]

AVVERTENZA_ESPLORATIVA = (
    "Analisi esplorativa, non causale: fumo, età, comorbidità e qualità dell'aria indoor sono "
    "fattori confondenti non considerati. I valori delle fonti non sono mediati fra loro."
)


class RichiestaValori(BaseModel):
    """Una zona (un comune **oppure** un distretto) e un giorno."""

    giorno: date = Field(description="Giorno richiesto, YYYY-MM-DD (fuso UTC+1 come i dataset)")
    comune: str | None = Field(default=None, description="id_comune: codice ISTAT a 6 cifre, es. '075035'")
    distretto: str | None = Field(default=None, description="id_distretto, es. 'LE-51'")

    @model_validator(mode="after")
    def _una_sola_zona(self):
        if (self.comune is None) == (self.distretto is None):
            raise ValueError("indicare esattamente uno fra 'comune' e 'distretto'")
        return self


class Zona(BaseModel):
    tipo: Literal["comune", "distretto"]
    id: str
    denominazione: str
    id_distretto: str
    id_provincia: str
    comuni: list[str] = Field(description="id_comune dei comuni della zona (uno solo se la zona è un comune)")


class Valore(BaseModel):
    valore: float | None
    stato: Stato
    nota: str | None = None


class StazioneAria(BaseModel):
    id_stazione: str
    denominazione: str | None
    tipo: Literal["fisica", "virtuale_modello", "assente"] = Field(
        description="fisica = stazione di misura; virtuale_modello = una per comune per le fonti a griglia (CAMS), "
                    "non è una stazione fisica; assente = comune senza stazioni (tutte le celle NO_DATA)")
    lat: float | None = None
    lon: float | None = None
    valori: dict[str, dict[str, Valore]] = Field(description="fonte → inquinante → valore (un valore per fonte, mai mediato)")


class ComuneAria(BaseModel):
    id_comune: str
    denominazione: str
    stazioni: list[StazioneAria]
    celle_per_stato: dict[str, dict[str, dict[str, int]]] = Field(
        description="fonte → inquinante → {VALORE|NULL|NO_DATA: n celle}: serve a dichiarare i buchi, non è una media")


class SezioneAria(BaseModel):
    stato: Literal["DISPONIBILE", "NON_DISPONIBILE"]
    motivo: str | None = None
    dataset: str | None = Field(default=None, description="file del dataset da cui vengono i valori")
    generato_il: str | None = None
    fonti: list[str] = []
    inquinanti: dict[str, str | None] = Field(default={}, description="sigla → unità di misura")
    comuni: list[ComuneAria] = []


class SezioneNonIntegrata(BaseModel):
    stato: Literal["NON_INTEGRATO"] = "NON_INTEGRATO"
    motivo: str


class ComuneCalore(BaseModel):
    id_comune: str
    denominazione: str
    media: Valore | None = None
    massima: Valore | None = None
    minima: Valore | None = None


class SezioneCalore(BaseModel):
    """Dominio calore (UHRI, componente 1: temperatura ERA5-Land). `NON_INTEGRATO` = nessun dato scaricato;
    `NON_DISPONIBILE` = dati scaricati ma non per il periodo chiesto; `DISPONIBILE` = ci sono valori."""
    stato: Literal["NON_INTEGRATO", "NON_DISPONIBILE", "DISPONIBILE"] = "NON_INTEGRATO"
    motivo: str | None = None
    fonte: str | None = None
    licenza: str | None = None
    unita: str | None = None
    mesi: dict[str, list[str]] = Field(default={}, description="per statistica, i mesi già in cache locale")
    comuni: list[ComuneCalore] = []


class RispostaValori(BaseModel):
    giorno: date
    zona: Zona
    aria: SezioneAria
    salute: SezioneNonIntegrata
    calore: SezioneCalore
    avvertenza: str = AVVERTENZA_ESPLORATIVA


# --- Dashboard (02/10/2026): territorio, disponibilità, aggregati per mappa, serie e confronti ---------------

class ComuneTerritorio(BaseModel):
    id_comune: str
    denominazione: str
    residenti: int | None = None
    nome_confine: str | None = Field(default=None, description="nome del poligono in comuni_salento.geojson")
    nota: str | None = None
    stazioni_fisiche: int = Field(default=0, description="stazioni fisiche dell'aria nel comune, di qualunque fonte "
                                                         "(anagrafica stazioni.json, escluse le virtuali CAMS)")
    senza_stazioni: bool = Field(default=True, description="nessuna stazione fisica di nessuna fonte: l'unico dato aria "
                                                          "è CAMS, modellato. Non dipende dal periodo")
    lat: float | None = Field(default=None, description="latitudine del centroide del confine (per il nome sulla mappa)")
    lon: float | None = Field(default=None, description="longitudine del centroide del confine")
    area_kmq: float | None = Field(default=None, description="superficie del confine comunale")
    copertura_arborea_pct: float | None = Field(default=None, description="% media di chioma arborea sul comune "
                                                                          "(CLMS Tree Cover Density 2024, 10 m)")
    suolo_impermeabile_pct: float | None = Field(default=None, description="% media di suolo impermeabile sul comune "
                                                                           "(CLMS Imperviousness Density 2018, 10 m)")


class DistrettoTerritorio(BaseModel):
    id_distretto: str
    denominazione: str
    id_comune_sede: str | None = None
    sede: str | None = Field(default=None, description="denominazione del comune sede")
    residenti: int = 0
    stazioni_fisiche: int = Field(default=0, description="somma delle stazioni fisiche dei suoi comuni")
    senza_stazioni: bool = Field(default=True, description="nessun comune del distretto ha stazioni fisiche: "
                                                          "l'unico dato aria è CAMS, modellato")
    copertura_arborea_pct: float | None = Field(default=None, description="media dei comuni pesata sull'area "
                                                                          "(è una quota di superficie, non per residente)")
    suolo_impermeabile_pct: float | None = Field(default=None, description="media dei comuni pesata sull'area")
    comuni: list[ComuneTerritorio]


class ProvinciaTerritorio(BaseModel):
    id_provincia: str
    denominazione: str
    distretti: list[DistrettoTerritorio]


class RiferimentoLimite(BaseModel):
    """Un valore limite/obiettivo di un quadro normativo, con la statistica su cui è definito."""
    statistica: str = Field(description="media_annua | media_24h | massimo_orario | massimo_8h | peak_season | media_10min")
    valore: float | None = None
    unita: str
    superamenti_ammessi: int | None = Field(default=None, description="giorni di superamento ammessi per anno civile")
    nota: str | None = None


class SogliaAcuta(BaseModel):
    valore: float
    unita: str
    statistica: str
    nota: str | None = None


class InfoInquinante(BaseModel):
    id: str
    descrizione: str | None = None
    unita: str | None = None
    riferimento: bool = Field(description="true per i 5 inquinanti di riferimento della dashboard (docs/Regole_dei_dati.md)")
    valore_limite: float | None = Field(default=None, description="riferimento primario (D.Lgs. 155/2010), per retrocompatibilità")
    periodo_limite: str | None = Field(default=None, description="statistica del riferimento primario")
    soglia_allarme: float | None = None
    riferimenti: dict[str, list[RiferimentoLimite]] | None = Field(
        default=None, description="quadro normativo → limiti (dlgs_155_2010, oms_2021, ue_2024_2881), v. Valori_Riferimento_Normativi.md")
    soglie_acute: dict[str, SogliaAcuta | None] | None = Field(
        default=None, description="soglie di informazione/allarme (D.Lgs. 155/2010)")


Banda = Literal["buona", "accettabile", "scadente", "cattiva", "non_confrontabile"]


class EsitoRiferimento(BaseModel):
    """Esito del confronto di una fonte con un singolo limite di un quadro normativo, nella finestra.
    `giorni_superamento`: giorni (con VALORE) oltre il limite 24h/orario. `media_indicativa`: media della
    finestra vs limite di media annua (indicativo se la finestra non è un anno intero)."""
    fonte: str
    quadro: Literal["dlgs_155_2010", "oms_2021", "ue_2024_2881"]
    statistica: str = Field(description="statistica del limite confrontato")
    statistica_misura: str = Field(description="statistica del dato misurato (media_giornaliera | massimo_giornaliero)")
    limite: float
    unita: str
    tipo: Literal["giorni_superamento", "media_indicativa"]
    valore: float | None = Field(default=None, description="media della finestra (solo media_indicativa)")
    giorni_superamento: int | None = None
    giorni_con_valore: int | None = None
    superamenti_ammessi_anno: int | None = None
    rapporto: float | None = Field(default=None, description="valore/limite (media_indicativa) o frazione di giorni oltre soglia")
    superato: bool
    indicativo: bool = Field(default=False, description="media annua valutata su una finestra più corta dell'anno")
    banda: Banda
    nota: str | None = None


class SalubritaInquinante(BaseModel):
    inquinante: str
    confrontabile: bool
    banda: Banda = Field(description="banda della mappa/intestazione: peggiore esito rispetto al D.Lgs. 155/2010 in vigore")
    statistiche_misura: dict[str, str | None] = Field(default={}, description="fonte → statistica del dato misurato")
    esiti: list[EsitoRiferimento] = Field(default=[], description="confronti per fonte e quadro normativo")
    nota: str | None = None


class SalubritaZonaMappa(BaseModel):
    """Banda sintetica di una zona, per colorare la mappa in modalità «salubrità»."""
    banda: Banda
    inquinante_peggiore: str | None = None


class RispostaSalubritaMappa(BaseModel):
    """Banda di salubrità di **tutte** le zone della finestra, per l'interruttore «valore»/«salubrità» della mappa.
    Stessa finestra di /api/aria/finestra; banda guidata dal D.Lgs. 155/2010 in vigore (v. SalubritaZona)."""
    da: date
    a: date
    giorni: int
    giorni_coperti: int
    distretti: dict[str, SalubritaZonaMappa]
    comuni: dict[str, SalubritaZonaMappa]
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class SalubritaZona(BaseModel):
    """Indice di salubrità dell'aria rispetto ai limiti di legge (docs/Regole_dei_dati.md, 11/10/2026): per inquinante e
    complessivo = **peggiore inquinante** (stile EAQI/IQA, nessun peso). La banda della mappa segue il D.Lgs. 155/2010
    in vigore; i tre quadri (D.Lgs./OMS/UE) sono negli esiti. Confronto solo a parità di statistica."""
    banda: Banda
    inquinante_peggiore: str | None = None
    per_inquinante: list[SalubritaInquinante] = []
    nota: str = Field(default="Indice rispetto ai limiti di legge; confronto solo a parità di statistica "
                             "(un massimo giornaliero con i limiti orari/8h, una media con i limiti 24h o, indicativo, con la media annua).")


class DatiInLocale(BaseModel):
    """Cosa c'è nei file locali del server (solo conteggi, nessuna lettura pesante)."""
    mesi_aria: int = Field(description="mesi con un dataset aria generato")
    ultimo_mese_aria: str | None = Field(default=None, description="AAAA-MM dell'ultimo mese d'aria generato")
    mesi_calore: int = Field(description="mesi ERA5-Land in cache (massimo fra le statistiche)")
    decessi: bool = Field(description="decessi ISTAT scaricati")
    dimissioni: bool = Field(description="dimissioni Health for All scaricate")
    simulati: bool = Field(description="dati sanitari simulati generati")
    consuntivi_pronti: int = Field(description="consuntivi mensili dell'aria pronti (scripts/dashboard/prepara_consuntivi.py)")
    stagionalita_pronta: bool = Field(description="riassunti della Stagionalità pronti (scripts/dashboard/prepara_stagionalita.py)")


class StatoServizio(BaseModel):
    """Risposta di GET /api/stato: serve al Frontend per dire «server senza dati» o «versione diversa» (piano F0.3)."""
    servizio: str
    versione_api: str = Field(description="versione dell'API: Frontend e Backend vanno insieme alla stessa versione")
    con_dati: bool = Field(description="false se non c'è nessun dato scaricato: il server risponde ma la dashboard resta vuota")
    dati: DatiInLocale


class MeseDisponibile(BaseModel):
    mese: str = Field(description="AAAA-MM")
    giorni_coperti: int
    giorni_del_mese: int


class PeriodoDecessi(BaseModel):
    da: str = Field(description="primo mese, AAAA-MM")
    a: str = Field(description="ultimo mese con almeno un VALORE, AAAA-MM")
    copertura_fino_al: str | None = Field(default=None, description="ultimo giorno con un VALORE nel file")
    fonte: str
    licenza: str


class PeriodoDimissioni(BaseModel):
    da: int = Field(description="primo anno con un VALORE")
    a: int = Field(description="ultimo anno con un VALORE")
    fonte: str
    licenza: str
    grana: str = "provincia × anno"


# ------------------------------------------------------------------------------- salute simulata (25/10/2026)

class IndicatoreSimulato(BaseModel):
    id: str = Field(description="es. ps_accessi, ricoveri_respiratori, adi_accessi_ps")
    etichetta: str = Field(description="descrizione completa, da parametri.json")
    breve: str = Field(description="etichetta breve per tabelle e grafici")
    unita: str = Field(description="per 100.000 residenti al giorno (assistiti in carico per lo stock ADI)")


class InfoSimulati(BaseModel):
    """Cosa c'è dei dati sanitari simulati: periodo, scenari, indicatori e la **dicitura**, unica fonte del testo."""
    disponibile: bool
    motivo: str | None = Field(default=None, description="perché non ci sono, se non ci sono")
    versione: str | None = None
    generato_il: str | None = None
    da: str | None = Field(default=None, description="primo giorno simulato, AAAA-MM-GG")
    a: str | None = Field(default=None, description="ultimo giorno simulato")
    scenari: list[str] = []
    scenario_predefinito: str = "letteratura"
    dicitura: str | None = Field(default=None, description="testo completo da riportare ovunque compaiano (parametri.json)")
    dicitura_breve: str = "Dato simulato, non reale"
    indicatori: list[IndicatoreSimulato] = []


class ValoreSimulato(BaseModel):
    indicatore: str
    etichetta: str
    totale: float | None = Field(default=None, description="somma della finestra (per lo stock ADI: media giornaliera)")
    al_giorno: float | None = None
    per_100k: float | None = Field(default=None, description="per 100.000 residenti al giorno")
    giorni: int = 0


class DettaglioSimulati(BaseModel):
    """Ricoveri, PS e ADI simulati di una zona nella finestra. Comune o distretto (somma dei comuni); il dato è
    sintetico, quindi la privacy dei decessi non si applica. Mai da confondere col reale: v. `dicitura_breve`."""
    stato: Stato
    scenario: str
    residenti: int | None = None
    giorni: int = Field(default=0, description="giorni della finestra con dato simulato")
    giorni_finestra: int = 0
    valori: list[ValoreSimulato] = []
    quota_bassa_urgenza: float | None = Field(default=None, description="accessi ADI a bassa urgenza / accessi ADI, 0-1")
    quota_ritorni: float | None = Field(default=None, description="ritorni ADI entro 30 giorni / accessi ADI, 0-1")
    nota: str | None = None
    dicitura_breve: str = "Dato simulato, non reale"


class PuntoSimulato(BaseModel):
    mese: str
    giorni: int = Field(description="giorni del mese con dato simulato")
    nullo: float | None = Field(default=None, description="per 100.000 residenti al giorno, scenario nullo")
    letteratura: float | None = Field(default=None, description="per 100.000 residenti al giorno, scenario letteratura")
    differenza_percentuale: float | None = Field(default=None, description="(letteratura − nullo) / nullo")


class SerieSimulata(BaseModel):
    zona: "ZonaRif"
    residenti: int | None = None
    punti: list[PuntoSimulato]


class RispostaSerieSimulata(BaseModel):
    """Un indicatore simulato mese per mese per fino a 4 zone, **entrambi gli scenari** in ogni punto: la distanza fra
    le due linee è l'effetto di aria e caldo imposto nello scenario «letteratura»."""
    da: str
    a: str
    indicatore: str
    etichetta: str
    unita: str
    serie: list[SerieSimulata]
    dicitura: str
    dicitura_breve: str = "Dato simulato, non reale"
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class RispostaDisponibilita(BaseModel):
    aria: list[MeseDisponibile] = Field(description="mesi coperti da almeno un dataset aria generato")
    inquinanti: list[InfoInquinante]
    decessi: PeriodoDecessi | None = None
    dimissioni: PeriodoDimissioni | None = None
    simulati: InfoSimulati | None = Field(default=None, description="dati sanitari simulati (ricoveri, PS, ADI)")
    calore: SezioneCalore
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class PeriodoCompleto(BaseModel):
    """L'ultimo mese di calendario coperto per intero da tutti i domini presenti (aria, calore ERA5-Land, decessi
    ISTAT, dati simulati): la finestra con cui la dashboard si apre, così il primo colpo d'occhio non è fatto di N/D
    (decisione del 28/10/2026). I ricoveri HFA non contano: sono annuali e si mostra comunque l'ultimo anno."""
    da: date
    a: date
    fino_al: dict[str, date | None] = Field(description="per dominio, l'ultimo giorno coperto (null = dominio assente, non conta)")
    limitato_da: list[str] = Field(description="i domini che fermano il periodo prima dell'ultimo giorno d'aria")


class RispostaCalendarioAria(BaseModel):
    """I giorni che l'archivio aria copre davvero, per la barra temporale della dashboard:
    la barra scorre giorno per giorno su una finestra che l'utente può allargare o stringere.
    Si apre su `periodo_completo`; senza, sugli ultimi `finestra_predefinita` giorni."""
    da: date | None = Field(default=None, description="primo giorno coperto, null se l'archivio è vuoto")
    a: date | None = Field(default=None, description="ultimo giorno coperto")
    giorni: list[date] = Field(description="tutti i giorni coperti, in ordine")
    buchi: list[str] = Field(default_factory=list,
                             description="intervalli dentro [da, a] che nessun dataset copre, 'AAAA-MM-GG → AAAA-MM-GG'")
    finestra_predefinita: int = Field(default=7, description="ampiezza in giorni della finestra «ultimi giorni»")
    finestra_massima: int = Field(description="ampiezza massima consentita a /api/aria/finestra")
    periodo_completo: PeriodoCompleto | None = Field(default=None, description="finestra iniziale; null se nessun mese è coperto da tutti i domini")


class CellaMensile(BaseModel):
    """Valore di una zona in un mese per una fonte e un inquinante, con la sua copertura."""
    valore: float | None
    stato: Stato
    nota: str | None = None
    giorni: int = Field(description="giorni del mese nel dataset")
    giorni_con_valore: int
    con_valore: int | None = Field(default=None, description="stazioni fisiche (comune) o comuni (distretto) "
                                                             "con almeno un VALORE nel mese")
    totale: int | None = Field(default=None, description="stazioni fisiche del comune o comuni del distretto")
    quota_residenti: float | None = Field(default=None, description="solo distretto: quota di residenti nei comuni "
                                                                    "con almeno un VALORE nel mese")


class InfoFonte(BaseModel):
    nome: str
    modellata: bool = Field(description="true per le fonti a griglia (CAMS): dato modellato, non misurato")
    copertura_da: str | None = None
    statistiche: dict[str, str | None] = Field(description="inquinante → statistica giornaliera dichiarata")
    licenza: str


class FileDataset(BaseModel):
    nome: str
    generato_il: str | None = None
    giorni: int


class StazioneMappa(BaseModel):
    id_stazione: str
    denominazione: str | None = None
    lat: float | None = None
    lon: float | None = None
    id_comune: str
    id_distretto: str | None = None
    fonti: list[str]
    inquinanti_con_valore: dict[str, list[str]] = Field(description="fonte → inquinanti con almeno un VALORE nel mese")


class RispostaAriaMese(BaseModel):
    mese: str
    fonte: str
    fonte_modellata: bool
    giorni_coperti: int
    giorni_del_mese: int
    dataset: list[FileDataset]
    fonti: list[InfoFonte] = Field(description="fonti presenti nel dataset del mese")
    inquinanti: list[str] = Field(description="inquinanti presenti nel dataset del mese")
    distretti: dict[str, dict[str, CellaMensile]] = Field(description="id_distretto → inquinante → valore del mese")
    comuni: dict[str, dict[str, CellaMensile]] = Field(description="id_comune → inquinante → valore del mese")
    stazioni: list[StazioneMappa]
    regole: str
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class RispostaAriaFinestra(BaseModel):
    """Stessa forma di RispostaAriaMese ma su una finestra di giorni qualsiasi: è quello
    che la mappa ridisegna a ogni passo della barra temporale."""
    da: date
    a: date
    giorni: int = Field(description="giorni della finestra richiesta")
    giorni_coperti: int = Field(description="giorni della finestra presenti in un dataset generato")
    fonte: str
    fonte_modellata: bool
    dataset: list[FileDataset]
    fonti: list[InfoFonte]
    inquinanti: list[str]
    distretti: dict[str, dict[str, CellaMensile]] = Field(description="id_distretto → inquinante → valore della finestra")
    comuni: dict[str, dict[str, CellaMensile]] = Field(description="id_comune → inquinante → valore della finestra")
    stazioni: list[StazioneMappa]
    regole: str
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class ZonaRif(BaseModel):
    tipo: Literal["distretto", "comune"]
    id: str
    denominazione: str
    id_distretto: str


class DettaglioFonteAria(BaseModel):
    """Una fonte nel pannello di dettaglio: un valore per inquinante, della finestra, mai mediato con le altre fonti."""
    fonte: str
    modellata: bool
    licenza: str
    celle: dict[str, CellaMensile] = Field(description="inquinante → valore della finestra")
    statistiche: dict[str, str | None] = Field(description="inquinante → statistica giornaliera dichiarata dalla fonte")


class DettaglioDecessi(BaseModel):
    """Decessi della zona nei mesi che la finestra tocca: la grana minima consentita dalla privacy è distretto × mese.
    La media giornaliera è solo presentazione (convenzione '~', docs/Regole_dei_dati.md), non entra nei dataset."""
    stato: Stato
    mesi: list[str] = Field(description="mesi toccati dalla finestra")
    mesi_con_valore: int = 0
    valore: float | None = Field(default=None, description="somma dei mesi con VALORE nel distretto")
    giorni: int = Field(default=0, description="giorni dei mesi con VALORE")
    media_giornaliera: float | None = Field(default=None, description="valore / giorni: valore derivato")
    nota: str | None = None
    fonte: str | None = None


class ValoreDimissioni(BaseModel):
    gruppo: str = Field(description="respiratorio | bpco | circolatorio | ischemiche | cerebrovascolari")
    etichetta: str
    anno: int | None = None
    dimissioni: float | None = Field(default=None, description="dimissioni dell'anno, maschi + femmine")
    tasso: float | None = Field(default=None, description="per 10.000 abitanti, già calcolato da ISTAT")
    media_giornaliera: float | None = Field(default=None, description="dimissioni / giorni dell'anno: valore derivato (~)")
    stato: Stato
    nota: str | None = None


class DettaglioDimissioni(BaseModel):
    """Dimissioni ospedaliere della **provincia** della zona, per gruppo di patologia: dato annuale, solo informativo
    (non è riferito alla zona né alla finestra e non entra nelle correlazioni). Vale anche per i comuni."""
    stato: Stato
    provincia: str
    denominazione_provincia: str
    anno: int | None = Field(default=None, description="anno mostrato: quello della finestra se coperto, altrimenti l'ultimo")
    valori: list[ValoreDimissioni] = []
    nota: str | None = None
    fonte: str | None = None
    grana: str = "provincia × anno"


class PuntoDimissioni(BaseModel):
    anno: int
    dimissioni: float | None = None
    tasso: float | None = None
    media_giornaliera: float | None = None
    stato: Stato
    nota: str | None = None


class SerieDimissioni(BaseModel):
    provincia: str
    denominazione_provincia: str
    gruppo: str
    etichetta: str
    punti: list[PuntoDimissioni]


class RispostaDimissioni(BaseModel):
    da: int
    a: int
    grana: str = "provincia × anno"
    fonte: str
    licenza: str
    serie: list[SerieDimissioni]
    nota: str
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class DettaglioCalore(BaseModel):
    stato: Literal["NON_INTEGRATO", "NON_DISPONIBILE", "DISPONIBILE"]
    motivo: str | None = None
    fonte: str | None = None
    unita: str | None = None
    media: CellaMensile | None = None
    massima: CellaMensile | None = None
    minima: CellaMensile | None = None
    arpa_fonte: str | None = Field(default=None, description="temperatura misurata da ARPA meteo, se ci sono dati scaricati")
    arpa_media: CellaMensile | None = Field(default=None, description="comune: media delle stazioni fisiche; distretto: media "
                                            "pesata sui residenti dei soli comuni con una stazione (dichiarato nella nota)")
    arpa_massima: CellaMensile | None = None
    arpa_minima: CellaMensile | None = None


class UsoFonteAccorpata(BaseModel):
    """Quanto una fonte è entrata nella vista «Tutte» per un inquinante, nella zona e nella finestra."""
    fonte: str
    usata: int = Field(description="giorni (comune) o comuni × giorni (distretto) in cui è entrata nella media")
    scartata: int = Field(description="giorni (o comuni × giorni) in cui è stata scartata perché si discostava dalle altre")
    base: int = Field(description="giorni (o comuni × giorni) con un valore nella vista «Tutte»")


class RispostaDettaglioZona(BaseModel):
    """Tutto ciò che si sa di una zona in una finestra di giorni, per dominio: alimenta il pannello a sinistra della mappa."""
    zona: ZonaRif
    da: date
    a: date
    giorni: int
    giorni_coperti: int = Field(description="giorni della finestra presenti in un dataset aria generato")
    inquinanti: list[str]
    aria: list[DettaglioFonteAria]
    aria_motivo: str | None = Field(default=None, description="perché l'aria manca, se manca")
    salubrita: SalubritaZona | None = Field(default=None, description="indice di salubrità rispetto ai limiti di legge, se c'è aria")
    fonti_accorpata: dict[str, list[UsoFonteAccorpata]] = Field(
        default_factory=dict, description="per inquinante: le fonti entrate o scartate nella vista «Tutte» (evidenziate nel pannello)")
    salute: DettaglioDecessi
    dimissioni: DettaglioDimissioni
    simulati: DettaglioSimulati | None = Field(default=None, description="ricoveri, PS e ADI simulati (non reali)")
    calore: DettaglioCalore
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class PuntoGiorno(BaseModel):
    giorno: date
    valore: float | None
    stato: Stato
    nota: str | None = None


class SerieZona(BaseModel):
    zona: ZonaRif
    punti: list[PuntoGiorno]


class RispostaSerieCalore(BaseModel):
    mese: str
    statistica: Literal["media", "massima", "minima"]
    unita: str
    fonte: str
    licenza: str
    fonte_modellata: bool = True
    serie: list[SerieZona]
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class RispostaCaloreMappa(BaseModel):
    """Temperatura di tutte le zone nella finestra, per la modalità «temperatura» della mappa (ERA5-Land: l'unica
    fonte con un valore per ogni comune; ARPA meteo copre solo i comuni con una stazione)."""
    da: date
    a: date
    giorni: int
    statistica: Literal["media", "massima", "minima"]
    unita: str
    fonte: str
    fonte_modellata: bool = True
    distretti: dict[str, CellaMensile]
    comuni: dict[str, CellaMensile]
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class ComponentiEventi(BaseModel):
    """Le tre parti degli eventi sanitari di un distretto, ciascuna per 100.000 residenti al giorno."""
    decessi: float | None = Field(default=None, description="decessi ISTAT (reali) dei mesi toccati dalla finestra")
    ricoveri: float | None = Field(default=None, description="ricoveri respiratori + circolatori simulati nei giorni della finestra")
    ps: float | None = Field(default=None, description="accessi in PS simulati nei giorni della finestra")


class RispostaSaluteMappa(BaseModel):
    """Eventi sanitari di tutte le zone nella finestra, per la vista «Salute» della mappa (29/10/2026, scelte di
    Matteo): decessi + ricoveri + accessi in PS per 100.000 residenti al giorno, ogni evento conta 1 (nessun peso).
    I decessi sono reali (ISTAT, distretto × mese), ricoveri e PS **simulati**: il valore è quindi un dato simulato.
    I comuni prendono il valore del loro distretto, perché i decessi per comune non si mostrano (privacy)."""
    da: date
    a: date
    giorni: int
    scenario: str
    unita: str = "eventi per 100.000 residenti al giorno"
    dicitura_breve: str
    distretti: dict[str, CellaMensile]
    comuni: dict[str, CellaMensile]
    componenti: dict[str, ComponentiEventi] = Field(description="per distretto: le tre parti del valore")
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class RispostaDisponibilitaCalore(BaseModel):
    fonte: str
    licenza: str
    mesi: dict[str, list[str]] = Field(description="per statistica, i mesi AAAA-MM già in cache locale")
    come_scaricare: str


class StatoAssistente(BaseModel):
    """Se l'assistente della dashboard può rispondere: Ollama attivo e modello scaricato (piano del modulo AI §12)."""
    pronto: bool = Field(description="true se Ollama risponde e il modello configurato è scaricato")
    modello: str = Field(description="modello configurato (variabile d'ambiente ONEHEALTH_LLM, default qwen3.5:4b)")
    ollama_attivo: bool
    versione_ollama: str | None = None
    modello_installato: bool
    motivo: str | None = Field(default=None, description="perché l'assistente non è pronto e cosa fare")


class FattoAssistente(BaseModel):
    id: str = Field(description="f1, f2…: il modello li cita fra parentesi quadre")
    analisi: str = Field(description="analisi generica che ha prodotto il fatto (piano del modulo AI §13.3)")
    testo: str = Field(description="frase in italiano con i numeri già calcolati e formattati")


class SerieAssistente(BaseModel):
    zona_id: str
    zona: str
    variabile: str
    unita: str | None = None
    grana: Literal["giorno", "mese", "anno"]
    natura: Literal["misurato", "modellato", "misto", "simulato", "reale"]
    fonte: str
    statistica: str | None = None
    punti: int
    punti_con_valore: int


class RispostaFattiAssistente(BaseModel):
    """Scheda dei fatti di una card, calcolata senza modello di linguaggio: è ciò che l'assistente racconta. `serie` è
    vuota per le card della Stagionalità, che leggono i riassunti già calcolati della tab."""
    card: str
    contesto: dict[str, bool | int | float | str | list[str] | None]
    serie: list[SerieAssistente]
    fatti: list[FattoAssistente]
    avvertenze: list[str]


CardAssistente = Literal["andamento", "domini", "consiglio", "anno_su_anno", "dettaglio_mese", "cambiamenti",
                         "mappa", "sintesi", "riepilogo", "fonti_aria", "fonti_decessi", "fonti_calore", "ricoveri"]
"""Card con l'assistente: lo stesso elenco di localhost/rag/schede.py (CARD) e di stato/assistente.ts."""


class ContestoAssistente(BaseModel):
    """Lo stato della card aperta, come per /api/assistente/fatti. Modello, istruzioni e opzioni non si passano: stanno
    nel server (barriera 1 del piano del modulo AI §12.3). «andamento» vuole mese, inquinante e almeno una zona;
    «domini» anche `da` per le domande sui numeri; le card della Stagionalità non hanno né mese né inquinante, e per il
    Salento nessuna zona."""
    mese: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="mese della card, AAAA-MM")
    da: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
                           description="primo mese del periodo («Aria e salute per distretto e mese»); `mese` è l'ultimo")
    inquinante: str | None = None
    fonte: str = "Tutte"
    zone: list[str] = Field(default_factory=list, max_length=4, description="id di distretti o comuni; vuota = Salento")
    indicatore: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_:.]{1,40}$",
                                   description="indicatore scelto nella card (anno su anno)")
    mese_dell_anno: int | None = Field(default=None, ge=1, le=12, description="mese scelto nella card (mese anno per anno)")
    scenario: Literal["nullo", "letteratura"] | None = Field(default=None, description="scenario dei simulati della Stagionalità")
    simulati_nella_sintesi: bool | None = Field(default=None, description="interruttore «nella sintesi» della "
                                                                           "Stagionalità; assente = acceso")
    statistica_calore: Literal["media", "massima", "minima"] | None = Field(
        default=None, description="statistica giornaliera della temperatura («Aria e salute per distretto e mese», "
                                  "«temperatura secondo ogni fonte»); assente = massima per la prima, media per la seconda")
    giorno_da: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$",
                                  description="primo giorno della finestra (mappa, sintesi, riepilogo)")
    giorno_a: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="ultimo giorno della finestra")
    vista: Literal["valore", "salubrita", "temperatura", "alberi", "suolo", "salute"] | None = Field(
        default=None, description="vista della carta")
    livello: Literal["distretti", "comuni"] | None = Field(default=None, description="livello della carta e della classifica")
    primo_piano: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{1,12}$",
                                    description="zona in primo piano sulla carta (la sua scheda risponde con la mappa)")


class DomandaAssistente(BaseModel):
    """Una domanda libera **oppure** l'id di una domanda proposta della card (GET /api/assistente/domande)."""
    card: CardAssistente = "andamento"
    contesto: ContestoAssistente
    domanda: str | None = Field(default=None, max_length=4000,
                                description="testo libero; oltre 400 caratteri riceve il rifiuto fisso")
    id_domanda_proposta: str | None = None

    @model_validator(mode="after")
    def _una_sola_domanda(self):
        if (self.domanda is None) == (self.id_domanda_proposta is None):
            raise ValueError("indicare esattamente uno fra 'domanda' e 'id_domanda_proposta'")
        return self


class DomandaProposta(BaseModel):
    id: str
    testo: str


class RispostaDomandeAssistente(BaseModel):
    card: str
    con_fatti: bool = Field(description="true se la card ha una scheda dei fatti: altrimenti l'assistente risponde solo "
                                        "alle descrizioni")
    domande: list[DomandaProposta]


class SezioneAssistente(BaseModel):
    id: str = Field(description="d1, d2…: il modello le cita fra parentesi quadre")
    documento: str = Field(description="file di localhost/rag/documenti/")
    titolo: str
    testo: str


class InstradamentoAssistente(BaseModel):
    tipo: Literal["analisi", "descrizione"]
    analisi: list[str]
    argomenti: list[str]
    parametri: dict[str, str | float | list[str] | None]


class RispostaAssistente(BaseModel):
    """Esito di una domanda (piano del modulo AI §13.1). Il testo del modello compare solo con esito «risposta»; negli
    altri casi `testo` è il rifiuto fisso o una nota, e `fatti`/`sezioni` sono ciò che la finestra mostra."""
    esito: Literal["risposta", "rifiuto", "non_verificata", "assistente_spento"]
    domanda: str | None = None
    testo: str | None = None
    citati: list[str] = Field(description="id dei fatti e delle sezioni citati nel testo")
    fatti: list[FattoAssistente]
    sezioni: list[SezioneAssistente]
    avvertenze: list[str] = Field(description="aggiunte dal codice, non dal modello: vanno sempre mostrate")
    instradamento: InstradamentoAssistente | None = None
    fermata_da: Literal["filtro", "instradamento", "parametri", "modello", "verifica"] | None = Field(
        default=None, description="barriera che ha fermato la domanda (per la prova del perimetro, non per l'utente)")
    motivo: str | None = None
    modello: str
    tempi: dict[str, float] = Field(description="instradamento_s, risposta_s, totale_s")


class RispostaSerieAria(BaseModel):
    mese: str
    inquinante: str
    unita: str | None = None
    fonte: str
    fonte_modellata: bool
    statistica: str | None = Field(default=None, description="statistica giornaliera dichiarata dalla fonte")
    serie: list[SerieZona]
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class SerieFonte(BaseModel):
    fonte: str
    modellata: bool
    statistica: str | None = None
    punti: list[PuntoGiorno]


class ConfrontoFonti(BaseModel):
    fonte_a: str
    fonte_b: str
    livello: str = Field(description="stazione × giorno (fonti misurate) o comune × giorno (modello contro misura)")
    celle_comuni: int = Field(description="celle in cui entrambe le fonti hanno un VALORE")
    quota_concordanti: float | None = Field(default=None, description="quota di celle con |b − a| ≤ soglia")
    differenza_media: float | None = Field(default=None, description="media di (b − a)")
    differenza_massima: float | None = Field(default=None, description="massimo di |b − a|")
    statistica_a: str | None = None
    statistica_b: str | None = None
    stessa_statistica: bool | None = None
    nota: str


class RispostaFontiAria(BaseModel):
    mese: str
    inquinante: str
    unita: str | None = None
    zona: ZonaRif
    serie: list[SerieFonte]
    confronti: list[ConfrontoFonti]
    soglia_concordanza: float
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class ConfrontoTemperatura(BaseModel):
    """ERA5-Land (modellato) contro ARPA meteo (misurato) sulle sole coppie comune × giorno in cui entrambe hanno un
    VALORE: nei distretti ARPA copre solo i comuni con una stazione, quindi il confronto si fa sugli stessi comuni."""
    fonte_a: str
    fonte_b: str
    livello: str = "comune × giorno"
    coppie: int = Field(description="coppie comune × giorno con un VALORE in entrambe le fonti")
    comuni: list[str] = Field(default_factory=list, description="comuni confrontati (quelli con una stazione ARPA meteo)")
    bias: float | None = Field(default=None, description="media di (b − a), in °C")
    errore_medio: float | None = Field(default=None, description="media di |b − a|, in °C")
    rmse: float | None = None
    correlazione: float | None = None
    nota: str


class SogliaFonti(BaseModel):
    indicatore: str
    descrizione: str
    soglia: float
    giorni_a: int = Field(description="coppie comune × giorno sopra soglia secondo la fonte a")
    giorni_b: int


class RispostaFontiCalore(BaseModel):
    mese: str
    statistica: Literal["media", "massima", "minima"]
    unita: str
    zona: ZonaRif
    serie: list[SerieFonte]
    confronto: ConfrontoTemperatura
    soglie: list[SogliaFonti] = Field(description="giorni sopra le soglie di caldo della statistica scelta, sulle coppie confrontate")
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class PuntoPeriodo(BaseModel):
    periodo: str = Field(description="mese AAAA-MM")
    valore: float | None
    stato: Stato
    nota: str | None = None


class SerieFontePeriodo(BaseModel):
    chiave: str = Field(description="A = ISTAT giornaliero, D = ISTAT bilancio mensile, Eurostat")
    fonte: str
    descrizione: str
    punti: list[PuntoPeriodo]


class ConfrontoConteggi(BaseModel):
    fonte_a: str
    fonte_b: str
    livello: str
    celle_comuni: int = Field(description="periodi con un VALORE in entrambe le fonti")
    identiche: float | None = Field(default=None, description="quota di periodi con lo stesso numero di decessi")
    entro_uno: float | None = Field(default=None, description="quota di periodi con |b − a| ≤ 1")
    differenza_totale: float | None = None
    differenza_media: float | None = None
    differenza_massima: float | None = None
    correlazione: float | None = None
    nota: str


class RispostaFontiSalute(BaseModel):
    anno: int
    zona: ZonaRif = Field(description="sempre un distretto: i decessi non si mostrano per comune (privacy)")
    zona_richiesta: ZonaRif
    id_provincia: str
    denominazione_provincia: str
    mensile: list[SerieFontePeriodo] = Field(description="distretto × mese: ISTAT giornaliero e bilancio mensile")
    provinciale: list[SerieFontePeriodo] = Field(description="provincia × mese: ISTAT giornaliero ed Eurostat, le settimane "
                                                             "ISO portate al mese del loro giovedì")
    confronti: list[ConfrontoConteggi]
    licenza: str
    generato_il: str = Field(description="data delle tabelle scritte da scripts/salute/valida_decessi.py")
    nota_privacy: str
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class PuntoMese(BaseModel):
    mese: str
    valore: float | None
    stato: Stato
    nota: str | None = None


class PuntoDecessi(PuntoMese):
    comuni: int | None = None
    comuni_con_valore: int | None = None
    quota_residenti: float | None = None


class SerieDecessi(BaseModel):
    id_distretto: str
    punti: list[PuntoDecessi]


class RispostaDecessi(BaseModel):
    da: str
    a: str
    grana: str = "distretto × mese"
    fonte: str
    licenza: str
    copertura_fino_al: str | None = None
    distretti: list[SerieDecessi]
    nota_privacy: str
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class SerieConfronto(BaseModel):
    zona: ZonaRif
    aria: list[PuntoMese]
    decessi: list[PuntoDecessi]
    calore: list[PuntoMese] = Field(default=[], description="temperatura del mese (ERA5-Land), statistica `statistica_calore`")


class RispostaConfronto(BaseModel):
    da: str
    a: str
    grana: str = "distretto × mese"
    inquinante: str
    unita: str | None = None
    fonte_aria: str
    serie: list[SerieConfronto]
    fonte_decessi: str | None = None
    statistica_calore: Literal["media", "massima", "minima"] = "media"
    calore: SezioneCalore
    avvertenza: str = AVVERTENZA_ESPLORATIVA


class ColonnaRiepilogo(BaseModel):
    """Una colonna della tabella di riepilogo per distretto. La tabella è **generica**: un dato nuovo (isole di calore,
    copertura arborea...) è una colonna in più, senza cambiare il frontend."""
    id: str
    gruppo: str = Field(description="intestazione di gruppo: Territorio, Aria, Salubrità, Salute, Calore, ...")
    etichetta: str
    unita: str | None = None
    formato: Literal["decimale", "intero", "percentuale", "banda", "testo"] = "decimale"
    nota: str | None = Field(default=None, description="come si legge la colonna (tooltip dell'intestazione)")
    modellata: bool = Field(default=False, description="dato modellato, non misurato (CAMS, ERA5-Land)")
    simulata: bool = Field(default=False, description="dato simulato, non reale (ricoveri, PS, ADI simulati)")


class CellaRiepilogo(BaseModel):
    valore: float | None = None
    testo: str | None = Field(default=None, description="per i formati banda e testo (es. la banda di salubrità)")
    stato: Stato = "NO_DATA"
    nota: str | None = None
    modellata: bool = Field(default=False, description="true se il valore di questa cella viene solo da una fonte modellata "
                                                       "(es. la salubrità di un distretto senza stazioni fisiche)")


class RigaRiepilogo(BaseModel):
    id_distretto: str
    denominazione: str
    celle: dict[str, CellaRiepilogo] = Field(description="id colonna → cella")


class RispostaRiepilogo(BaseModel):
    """Tutti i dati per distretto nella finestra della barra temporale, una riga per distretto. Esplorativo, non causale."""
    da: date
    a: date
    giorni: int
    fonte: str = Field(description="fonte delle colonne dell'aria")
    colonne: list[ColonnaRiepilogo]
    righe: list[RigaRiepilogo]
    avvertenza: str = AVVERTENZA_ESPLORATIVA



# ------------------------------------------------------------------------------------------- stagionalità (16/10/2026)

class CellaStagione(BaseModel):
    """Il valore di un indicatore in un mese di un anno (es. NO2 di luglio 2025)."""
    valore: float | None = None
    stato: Stato = "NO_DATA"
    nota: str | None = None
    completo: bool = Field(default=False, description="mese completo: solo questi entrano nei ranghi e nell'andamento")
    extra: dict[str, float | None] = Field(default_factory=dict, description="es. t_media per il calore, totale per i decessi")
    limite_superato: bool | None = Field(default=None, description="D.Lgs. 155/2010; None = nessun limite confrontabile")
    limiti: list[str] = Field(default_factory=list, description="esito di ogni limite confrontabile, per fonte")
    limiti_superati: list[str] = Field(default_factory=list)


class MeseStagione(BaseModel):
    """Un mese dell'anno (1-12) mediato sugli anni del confronto, col suo rango."""
    mese: int = Field(ge=1, le=12)
    valore: float | None = Field(default=None, description="media sugli anni del confronto (per l'aria complessiva: media dei ranghi dei 5 inquinanti)")
    anni: list[int] = Field(default_factory=list, description="anni con un mese completo entrati nella media")
    rango: float | None = Field(default=None, description="1 = mese peggiore, 12 = migliore; pari merito = rango medio")
    limite_superato: bool | None = Field(default=None, description="D.Lgs. 155/2010 superato in almeno un anno del confronto; None = nessun limite confrontabile")
    limiti_nota: str | None = None


class AndamentoStagione(BaseModel):
    """Ultimo mese completo rispetto alla media dello stesso mese negli anni precedenti."""
    classe: Literal["in_aumento", "stabile", "in_calo", "storico_insufficiente", "nessun_dato"]
    mese_riferimento: str | None = Field(default=None, description="AAAA-MM: l'ultimo mese completo del dominio")
    valore: float | None = None
    media_anni_precedenti: float | None = None
    anni_precedenti: list[int] = Field(default_factory=list)
    delta: float | None = None
    delta_percentuale: float | None = None
    soglia: str = Field(description="±10% (aria, decessi) o ±1 °C (temperatura)")
    indicativo: bool = Field(default=False, description="un solo anno di storico")
    mesi_senza_dati: list[str] = Field(default_factory=list, description="mesi dopo il riferimento fino a oggi, senza dato completo")
    motivo_senza_dati: str | None = None
    nota: str | None = None


class RigaStagionalita(BaseModel):
    id: str = Field(description="aria:<inquinante> | aria | calore | decessi | pronto_soccorso | adi_accessi_ps | ricoveri_respiratori")
    dominio: Literal["aria", "calore", "salute"]
    etichetta: str
    unita: str | None = None
    formato: Literal["decimale", "rango"] = "decimale"
    modellata: bool = False
    nota: str | None = None
    disponibile: bool
    motivo: str | None = Field(default=None, description="perché la riga è vuota (es. nessuna fonte del PS)")
    simulata: bool = Field(default=False, description="dato simulato, non reale (PS, ADI, ricoveri)")
    anni: dict[str, list[CellaStagione]] = Field(default_factory=dict, description="anno → 12 celle (gennaio-dicembre)")
    clima: list[MeseStagione] = Field(description="12 mesi dell'anno")
    mese_peggiore: int | None = None
    andamento: AndamentoStagione | None = None


class TemaCriticita(BaseModel):
    """Un tema del riepilogo delle criticità (un indicatore per tema) e i suoi 3 mesi peggiori."""
    id: str = Field(description="id della riga della griglia: aria | calore | decessi | pronto_soccorso | adi_accessi_ps | ricoveri_respiratori")
    tema: Literal["aria", "caldo", "decessi", "ps", "adi", "ricoveri"]
    nome: str
    etichetta: str
    unita: str | None = None
    formato: Literal["decimale", "rango"] = "decimale"
    simulata: bool = False
    modellata: bool = False
    disponibile: bool
    entra: bool = Field(description="conta nei periodi critici (False se senza dati o simulato escluso dalla sintesi)")
    motivo: str | None = None
    mesi_critici: list[int] = Field(default_factory=list, description="i 3 mesi peggiori (di più a pari merito)")
    ranghi: list[float | None] = Field(default_factory=list, description="rango dei 12 mesi, 1 = peggiore")
    mese_peggiore: int | None = None
    valore_peggiore: float | None = None


class MeseCriticita(BaseModel):
    mese: int = Field(ge=1, le=12)
    conteggio: int = Field(description="per quanti temi il mese è fra i 3 peggiori")
    temi: list[str] = Field(default_factory=list, description="id dei temi critici nel mese")
    livello: Literal["alta", "media", "bassa"] | None = Field(
        default=None, description="alta = almeno metà dei temi (e almeno 2), media = 2 o più, bassa = 1")


class MotivoCriticita(BaseModel):
    """Perché un periodo è critico per un indicatore: il suo mese peggiore dentro il periodo."""
    id: str
    etichetta: str
    unita: str | None = None
    formato: Literal["decimale", "rango"] = "decimale"
    mese: int
    mesi: list[int] = Field(description="mesi del periodo fra i 3 peggiori dell'indicatore")
    valore: float | None = None
    rango: float | None = None
    posizione: int | None = Field(default=None, description="1 = mese peggiore dell'anno, 2 = secondo, 3 = terzo")
    scarto: float | None = Field(default=None, description="sulla media dei 12 mesi: °C per la temperatura, frazione per gli altri")
    scarto_assoluto: bool = False
    simulata: bool = False
    modellata: bool = False


class SpuntoCriticita(BaseModel):
    """Dove agire in un periodo critico: da valutare, non una prescrizione."""
    tema: Literal["aria", "caldo", "decessi", "ps", "adi", "ricoveri"]
    titolo: str = Field(description="es. «ADI», «Reparti»")
    breve: str = Field(description="testo breve per il consiglio")
    esteso: str = Field(description="testo esteso per il tooltip")


class PeriodoCriticita(BaseModel):
    mesi: list[int] = Field(description="mesi consecutivi (dicembre vicino a gennaio)")
    etichetta: str
    massimo: int = Field(description="temi critici nel mese di picco")
    somma: int
    mese_picco: int
    livello: Literal["alta", "media", "bassa"] | None = None
    motivi: list[MotivoCriticita] = Field(description="temi critici nel periodo")
    anche: list[MotivoCriticita] = Field(default_factory=list, description="indicatori di dettaglio critici nel periodo (inquinanti, PS per causa, ADI, ricoveri circolatori): non pesano sul conteggio")
    limiti_superati: list[str] = Field(default_factory=list, description="inquinanti oltre un limite del D.Lgs. 155/2010 in un mese del periodo")
    spunti: list[SpuntoCriticita] = Field(default_factory=list, description="dove agire, dai temi critici: da valutare, non prescrizioni")
    simulati: list[str] = Field(default_factory=list, description="indicatori simulati fra motivi e dettaglio")


class MeseAttenzione(BaseModel):
    mese: int
    temi: list[str]


class CriticitaAnno(BaseModel):
    """Riepilogo delle criticità dell'anno (27/10/2026): quali mesi, per quali temi. Esplorativo, non causale."""
    temi: list[TemaCriticita]
    mesi: list[MeseCriticita]
    periodi: list[PeriodoCriticita] = Field(description="dal più critico")
    attenzione: list[MeseAttenzione] = Field(default_factory=list, description="mesi critici per un solo tema, fuori dai periodi")
    temi_contati: int
    mesi_critici_per_tema: int = 3
    simulati_nella_sintesi: bool = True
    sintesi: str


class RispostaStagionalita(BaseModel):
    """I 12 mesi dell'anno a confronto su aria, calore e decessi (tab «Stagionalità»). Esplorativo, non causale."""
    zona: ZonaRif | None = Field(default=None, description="None = Salento intero")
    denominazione: str
    fonte: str = Field(description="fonte dell'aria (o «Tutte»)")
    scenario: str | None = Field(default=None, description="scenario dei dati simulati (riga del pronto soccorso)")
    simulati_nella_sintesi: bool = Field(default=True, description="se PS, ADI e ricoveri simulati contano fra i temi critici")
    anni_confronto: list[int] = Field(description="anni di medie, ranghi e andamento: quelli comuni a tutti i domini, dal 2024")
    anni_storico: list[int] = Field(default_factory=list, description="tutti gli anni preparati, per il dettaglio anno per anno e il grafico anno su anno")
    oggi: date
    peggiori: list[int] = Field(description="i mesi peggiori, dal primo: i picchi dei periodi critici, poi i mesi critici per più temi")
    sintesi: str
    righe: list[RigaStagionalita]
    criticita: CriticitaAnno | None = None
    mesi_aria: list[str] = Field(description="mesi d'aria preparati per la tab")
    mesi_calore: list[str]
    mesi_da_preparare: list[str] = Field(default_factory=list, description="mesi dell'archivio senza riassunto aggiornato")
    regole: str
    avvertenza: str = AVVERTENZA_ESPLORATIVA


SerieSimulata.model_rebuild()
