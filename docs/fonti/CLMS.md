# Copernicus Land Monitoring Service (CLMS) — copertura arborea e suolo impermeabile

Fattori di mitigazione dell'UHRI (componenti 3 e 4, v. `../Lista_dataset_calore.md` §3.4 e §3.5). Verificato il **15/10/2026**; aggiornato il **16/10/2026** con i raster scaricati dal portale e con le due viste della mappa.

## 1. Cosa si preleva

| Campo in `territorio.json` | Prodotto | Risoluzione | Edizione | Valori |
|---|---|---|---|---|
| `copertura_arborea_pct` | **Tree Cover Density** 2018-present, yearly (`CLMS_HRLVLCC_TCD_ITF4_0`, file unico per la Puglia) | 10 m, EPSG:3035 | **2024** (la più recente; si usa solo questa) | % di chioma per pixel, 0-100 |
| `suolo_impermeabile_pct` | High Resolution Layer **Imperviousness Density** (`IMD_2018_010m_it_03035_v020`) | 10 m, EPSG:3035 | 2018 (dati 2017-2019; l'ultima pubblicata) | % di suolo sigillato per pixel, 0-100 |

Per comune: **media dei pixel** il cui centro cade nel confine (EPSG:3035 è equivalente, quindi la media è anche media sull'area).
Per distretto (solo dashboard, `/api/territorio`): **media dei comuni pesata sulla superficie**, perché è una quota di superficie, non una grandezza per residente.
Risultato: `mitigazione_comuni.json` in questa cartella, **dato autorevole**; `scripts/territorio/costruisci_anagrafica_territorio.py`
ne riporta i valori in `data/territorio/anagrafica/territorio.json` (così una rigenerazione dell'anagrafica non li azzera).

## 2. Accesso

- **File scaricati a mano dal portale CLMS** (`land.copernicus.eu`, account **EU Login**), in `data/raw/calore/clms/locale/` (gitignored):
  - Tree Cover Density **2024**: un GeoTIFF per la Puglia (716 MB). Gli anni successivi al 2024 non sono pubblicati.
  - Imperviousness Density **2018 v020**: 74 tile da 100 km dell'Italia (270 MB); il portale non ne ha di più recenti.
- **Solo per l'Imperviousness**, se i file locali mancano: **ImageServer pubblico di EEA, senza chiave**,
  `https://image.discomap.eea.europa.eu/arcgis/rest/services/GioLandPublic/HRL_ImperviousnessDensity_2018/ImageServer/exportImage`
  (un riquadro per comune nel piano nativo EPSG:3035, allineato ai 10 m, `NearestNeighbor`, U8, GeoTIFF; limite 15000 × 4100 px per richiesta).
  Dà gli stessi valori del file locale in tutti i 145 comuni (scarto massimo 0,00, verificato il 16/10/2026).
- **Per il TCD nessun ripiego**: il servizio EEA ha solo l'edizione 2018, che non si usa (decisione del 16/10/2026). Senza il file locale il comune resta `NULL` con la nota di come scaricarlo.
- Client: `api/calore/clms.py`. Script: `scripts/calore/calcola_mitigazione_comuni.py` (145 comuni in pochi secondi dai file locali).
  Dipendenza: `rasterio` (wheel con GDAL incluso, nessuna installazione di sistema).

## 3. Licenza

Dai record del catalogo EEA (`sdi.eea.europa.eu`, 15/10/2026): i prodotti CLMS sono «made available on a principle of **full, open and free access**»
(Regolamento delegato (UE) n. 1159/2013). Condizioni: (1) citare la fonte quando si distribuiscono o comunicano i prodotti; (2) dichiarare le
modifiche se i prodotti sono stati adattati. Il calcolo della media comunale è un'elaborazione nostra e va dichiarato come tale (la dashboard
lo fa nel piè di pagina). Chiude il punto 5 di `../Lista_dataset_calore.md` §5.

## 4. Qualità e limiti

- **Edizioni diverse per i due fattori**: chioma 2024, suolo sigillato 2018 (non ce n'è una più recente). Sono attributi quasi statici; da dichiarare in tesi.
- **Media sull'intero comune, non sull'area urbana**: Lecce (234 km², molta campagna) risulta al 7,1% di suolo sigillato, Aradeo (piccolo e compatto) al 14,9%.
  Il valore descrive il comune, non il tessuto urbano; per quello servirebbe la maschera dell'urbanizzato (Urban Atlas / CLC), non integrata.
- È **chioma arborea**, non verde urbano: gli uliveti contano come alberi.
- I codici > 100 (nodata 240 e riempimento 255) sono esclusi dalla media e contati nella nota: in tutto il Salento 163 pixel nel TCD 2024 e 4 nell'Imperviousness.

## 5. Risultati (16/10/2026)

145 comuni su 145 con `VALORE`, nessun `NULL`.

- Copertura arborea 2024: media 12,5%, da 2,1% (Monteparano) a 35,0% (Palagiano); in testa i comuni della Murgia e dell'alto Brindisino (Ceglie Messapica 32,9%, San Michele Salentino 32,9%).
- Suolo impermeabile 2018: media 6,4%, da 1,2% (Castellaneta) a 15,2% (Sogliano Cavour).

## 6. In dashboard

Due viste nel selettore «Colore» della mappa (16/10/2026): **Alberi** (rampa verde) e **Suolo** (rampa grigio-terra), a livello distretti e comuni,
con scala relativa min-max fra le zone (dato statico: non segue la barra temporale) e tooltip con edizione e limiti. Dati da `/api/territorio`.

## 7. Citazione (Chicago)

Copernicus Land Monitoring Service. "Tree Cover Density 2018-Present (Raster 10 m), Europe, Yearly." Edizione 2024. Consultato il 16 ottobre 2026. https://land.copernicus.eu/en/products/high-resolution-layer-forests-and-tree-cover/tree-cover-density-2018-present-raster-10-m-europe-yearly.

European Environment Agency. *Imperviousness Density 2018 (raster 10 m), Europe, 3-yearly, Aug. 2020*. Copernicus Land Monitoring Service. https://land.copernicus.eu/en/products/high-resolution-layer-imperviousness/imperviousness-density-2018.
