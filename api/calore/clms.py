#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client dei due fattori di mitigazione dell'UHRI (componenti 3 e 4, v. docs/Regole_dei_dati.md): **copertura arborea**
(Tree Cover Density **2024**) e **suolo impermeabile** (Imperviousness Density **2018**, l'ultima pubblicata) dei
Copernicus Land Monitoring Service (CLMS), raster a **10 m** in EPSG:3035 (valori 0-100 %).
Scheda: data/dataset/calore/clms/CLMS.md.

Accesso: i raster si scaricano a mano dal portale CLMS con un account EU Login e si mettono in
`data/raw/calore/clms/locale/` (Tree Cover Density 2024: un file per la Puglia; Imperviousness Density 2018 v020:
tile da 100 km dell'Italia). Per il **TCD si usa solo il 2024** (scelta del 16/10/2026): senza il file locale il
comune resta `NULL`, nessun ripiego sul 2018. Per l'Imperviousness, che è 2018 in entrambi i canali (identici su tutti
i 145 comuni, verificato il 16/10/2026), il ripiego è l'**ImageServer pubblico EEA, senza chiave**
(`image.discomap.eea.europa.eu`): una `exportImage` per riquadro comunale, allineato ai 10 m nel piano nativo
EPSG:3035, senza ricampionamento (`NearestNeighbor`):

    GioLandPublic/HRL_ImperviousnessDensity_2018/ImageServer/exportImage

Statistica zonale: **media dei pixel** il cui centro cade nel confine del comune. EPSG:3035 è equivalente
(LAEA), quindi ogni pixel pesa uguale e la media è anche la media sull'area. Il confine si riproietta da
lon/lat con `rasterio.warp.transform_geom`, senza `pyproj`. I valori fuori da 0-100 (codici di "fuori area",
che il servizio non dichiara come nodata) sono esclusi dalla media e contati nella nota.

Stati come nel resto del progetto: `VALORE` se c'è almeno un pixel valido, `NULL` se il comune è coperto ma la
richiesta fallisce o nessun pixel è valido (nota con il motivo). Un errore di rete non interrompe il calcolo.
"""

import json
import re
import time
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from rasterio.merge import merge as rasterio_merge
from rasterio.warp import transform_geom
from rasterio.windows import from_bounds
from shapely.geometry import mapping, shape

from api.comune.confini_comuni import FILE_CONFINI
from api.comune.stati import STATO_NULL, STATO_VALORE

RADICE = Path(__file__).resolve().parents[2]
DIR_CACHE = RADICE / "data" / "raw" / "calore" / "clms"
BASE_URL = "https://image.discomap.eea.europa.eu/arcgis/rest/services/GioLandPublic"
EPSG_NATIVO = 3035
PASSO_M = 10
MAX_PIXEL = (15000, 4100)  # maxImageWidth × maxImageHeight dichiarati dal servizio
TIMEOUT = 180
TENTATIVI = 3
VALORE_MAX = 100  # sopra questo valore il pixel è un codice di "fuori area", non una percentuale

PRODOTTI = {
    "copertura_arborea": {
        "nome": "Tree Cover Density 2018-present (raster 10 m), Europe, yearly — edizione 2024",
        "servizio": None,  # solo il file locale 2024: il servizio EEA ha il 2018, che non si usa
        "id_prodotto": "CLMS_HRLVLCC_TCD_ITF4_0",
        "edizione": 2024,
        "scheda_eea": None,
        "pagina_clms": "https://land.copernicus.eu/en/products/high-resolution-layer-forests-and-tree-cover/tree-cover-density-2018-present-raster-10-m-europe-yearly",
    },
    "suolo_impermeabile": {
        "nome": "Imperviousness Density 2018 (raster 10 m)",
        "servizio": "HRL_ImperviousnessDensity_2018",
        "id_prodotto": "copernicus_r_3035_10_m_imd-2018_p_2017-2018_v01_r00",
        "edizione": 2018,
        "scheda_eea": "https://sdi.eea.europa.eu/catalogue/srv/api/records/3bf542bd-eebd-4d73-b53c-a0243f2ed862",
        "pagina_clms": "https://land.copernicus.eu/en/products/high-resolution-layer-imperviousness/imperviousness-density-2018",
    },
}


# Raster scaricati a mano dal portale CLMS (account EU Login) in DIR_LOCALE: hanno sempre la precedenza.
# Il TCD è un unico file (2024, Puglia), l'Imperviousness un insieme di tile da 100 km (2018 v020: il portale
# non ne ha di più recenti).
DIR_LOCALE = DIR_CACHE / "locale"
LOCALI = {
    "copertura_arborea": {
        "pattern": "Tree Cover Density*/*/*.tif", "edizione": 2024,
        "id_prodotto": "CLMS_HRLVLCC_TCD_ITF4_0 (Tree Cover Density 2024, 10 m, Puglia)",
    },
    "suolo_impermeabile": {
        "pattern": "IMD_2018_010m_*/DATA/*.tif", "edizione": 2018,
        "id_prodotto": "IMD_2018_010m_it_03035_v020 (Imperviousness Density 2018, 10 m, Italia)",
    },
}
LATO_TILE_M = 100_000
FUORI_AREA = 255  # riempimento fuori dai raster locali: escluso dalla media come ogni valore > 100


class ClmsError(RuntimeError):
    """Errore nella richiesta di un raster CLMS."""


def file_locali(prodotto):
    """File del prodotto scaricati a mano (lista vuota se non ci sono)."""
    return sorted(DIR_LOCALE.glob(LOCALI[prodotto]["pattern"])) if DIR_LOCALE.exists() else []


def sorgente(prodotto):
    """Descrizione della sorgente che `media_zonale` userà: edizione, id del prodotto e canale di accesso."""
    if file_locali(prodotto):
        return {"canale": "file locale dal portale CLMS", **{k: LOCALI[prodotto][k] for k in ("edizione", "id_prodotto")}}
    p = PRODOTTI[prodotto]
    if p["servizio"] is None:
        return {"canale": "assente: file locale non trovato", "edizione": p["edizione"], "id_prodotto": p["id_prodotto"]}
    return {"canale": "ImageServer pubblico EEA", "edizione": p["edizione"], "id_prodotto": p["id_prodotto"]}


def _tile_che_toccano(file, bbox):
    """Tile (nome E<x>N<y> = angolo in unità da 100 km) il cui quadrato interseca il riquadro."""
    xmin, ymin, xmax, ymax = bbox
    scelti = []
    for f in file:
        m = re.search(r"_E(\d+)N(\d+)_", f.name)
        x, y = int(m.group(1)) * LATO_TILE_M, int(m.group(2)) * LATO_TILE_M
        if x < xmax and x + LATO_TILE_M > xmin and y < ymax and y + LATO_TILE_M > ymin:
            scelti.append(f)
    return scelti


def _leggi_locale(prodotto, bbox):
    """(array 2D, trasformazione affine) del riquadro dai file locali; i pixel fuori dai raster valgono FUORI_AREA."""
    file = file_locali(prodotto)
    if len(file) == 1:  # raster unico (TCD): lettura a finestra
        with rasterio.open(file[0]) as ds:
            finestra = from_bounds(*bbox, transform=ds.transform).round_offsets().round_lengths()
            return ds.read(1, window=finestra, boundless=True, fill_value=FUORI_AREA), ds.window_transform(finestra)
    tile = _tile_che_toccano(file, bbox)
    if not tile:
        raise ClmsError("nessun tile locale copre il comune")
    aperti = [rasterio.open(f) for f in tile]
    try:
        a, trasf = rasterio_merge(aperti, bounds=bbox, res=PASSO_M, nodata=FUORI_AREA, dtype="uint8")
    finally:
        for ds in aperti:
            ds.close()
    return a[0], trasf


def confini_3035(_cache={}):
    """{nome_confine: geometria shapely in EPSG:3035} dal geojson dei confini comunali."""
    if not _cache:
        with open(FILE_CONFINI, encoding="utf-8") as f:
            for feat in json.load(f)["features"]:
                geom = transform_geom("EPSG:4326", f"EPSG:{EPSG_NATIVO}", feat["geometry"])
                _cache[feat["properties"]["nome"]] = shape(geom)
    return _cache


def riquadro(geometria):
    """Riquadro (xmin, ymin, xmax, ymax) del confine, allineato ai multipli di 10 m."""
    x0, y0, x1, y1 = geometria.bounds
    return tuple(int(v) for v in (
        np.floor(x0 / PASSO_M) * PASSO_M, np.floor(y0 / PASSO_M) * PASSO_M,
        np.ceil(x1 / PASSO_M) * PASSO_M, np.ceil(y1 / PASSO_M) * PASSO_M,
    ))


def _percorso_cache(prodotto, nome_confine):
    sicuro = "".join(c if c.isalnum() else "_" for c in nome_confine)
    return DIR_CACHE / prodotto / f"{sicuro}_{PRODOTTI[prodotto]['edizione']}.tif"


def _scarica(prodotto, bbox):
    """GeoTIFF (byte) del riquadro, da ImageServer. Alza ClmsError dopo `TENTATIVI` tentativi."""
    xmin, ymin, xmax, ymax = bbox
    larghezza, altezza = (xmax - xmin) // PASSO_M, (ymax - ymin) // PASSO_M
    if larghezza > MAX_PIXEL[0] or altezza > MAX_PIXEL[1]:
        raise ClmsError(f"riquadro {larghezza}×{altezza} px oltre il limite del servizio {MAX_PIXEL}")
    url = f"{BASE_URL}/{PRODOTTI[prodotto]['servizio']}/ImageServer/exportImage"
    params = {
        "bbox": f"{xmin},{ymin},{xmax},{ymax}", "bboxSR": EPSG_NATIVO, "imageSR": EPSG_NATIVO,
        "size": f"{larghezza},{altezza}", "format": "tiff", "pixelType": "U8",
        "interpolation": "RSP_NearestNeighbor", "f": "image",
    }
    ultimo = None
    for tentativo in range(TENTATIVI):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            if not r.headers.get("content-type", "").startswith("image"):
                raise ClmsError(f"risposta non raster: {r.text[:200]!r}")  # ArcGIS risponde 200 anche con l'errore
            return r.content
        except (requests.RequestException, ClmsError) as exc:
            ultimo = exc
            time.sleep(2 * (tentativo + 1))
    raise ClmsError(f"{PRODOTTI[prodotto]['servizio']}: {ultimo}")


def ritaglio(prodotto, nome_confine):
    """Byte del GeoTIFF del comune: dalla cache locale, altrimenti scaricato e salvato."""
    cache = _percorso_cache(prodotto, nome_confine)
    if cache.exists():
        return cache.read_bytes()
    dati = _scarica(prodotto, riquadro(confini_3035()[nome_confine]))
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporanea = cache.with_suffix(".tmp")
    temporanea.write_bytes(dati)
    temporanea.replace(cache)
    return dati


def media_zonale(prodotto, nome_confine):
    """
    Media (%) del prodotto sui pixel del comune.
    Restituisce {"valore", "stato", "nota", "pixel", "pixel_fuori_scala"}; non alza eccezioni di rete.
    """
    base = {"valore": None, "pixel": 0, "pixel_fuori_scala": 0}
    try:
        geometria = confini_3035()[nome_confine]
        if file_locali(prodotto):
            a, trasf = _leggi_locale(prodotto, riquadro(geometria))
            dentro = geometry_mask([mapping(geometria)], out_shape=a.shape, transform=trasf, invert=True)
        elif PRODOTTI[prodotto]["servizio"] is None:
            raise ClmsError(f"{PRODOTTI[prodotto]['nome']}: file non trovato in data/raw/calore/clms/locale/ "
                            "(si scarica dal portale CLMS, v. CLMS.md)")
        else:
            with MemoryFile(ritaglio(prodotto, nome_confine)) as mf, mf.open() as ds:
                a = ds.read(1)
                dentro = geometry_mask([mapping(geometria)], out_shape=a.shape, transform=ds.transform, invert=True)
    except (ClmsError, KeyError, rasterio.errors.RasterioError) as exc:
        return {**base, "stato": STATO_NULL, "nota": f"raster non ottenuto: {exc}"}

    pixel = a[dentro]
    validi = pixel[pixel <= VALORE_MAX]
    fuori_scala = int(pixel.size - validi.size)
    base.update(pixel=int(pixel.size), pixel_fuori_scala=fuori_scala)
    if validi.size == 0:
        return {**base, "stato": STATO_NULL, "nota": "nessun pixel valido dentro il confine del comune"}
    nota = f"media su {validi.size} pixel da 10 m"
    if fuori_scala:
        nota += f"; {fuori_scala} pixel fuori scala esclusi"
    return {**base, "valore": round(float(validi.mean()), 2), "stato": STATO_VALORE, "nota": nota}
