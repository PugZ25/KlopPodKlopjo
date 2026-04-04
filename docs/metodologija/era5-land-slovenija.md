# ERA5-Land za Slovenijo

Ta dokument opisuje, kako v projektu `KlopPodKlopjo` uporabljamo Copernicus ERA5-Land podatke za vremenske in talne razmere v Sloveniji.

## Vir podatkov

- vir: Copernicus Climate Data Store
- dataset: `ERA5-Land hourly data from 1950 to present`
- CDS dataset ID: `reanalysis-era5-land`
- prostorska ločljivost: privzeta ERA5-Land mreža `0.1° x 0.1°`
- prostorski izrez za Slovenijo: `north=46.9`, `west=13.3`, `south=45.3`, `east=16.6`

## Časovno okno

Privzeto jemljemo zadnjih 10 let od najnovejšega razpoložljivega dne, ne nujno od današnjega datuma. Skripta zato privzeto uporabi:

- `end_date = today - 5 dni`
- `start_date = end_date - 10 let`

Za datum `2026-04-04` to pomeni privzeti interval:
- `2016-03-30` do `2026-03-30`

Če želimo strogo koledarsko okno od točno določenega dne, ga eksplicitno podamo z `--start-date` in `--end-date`.

## Zahtevane spremenljivke

| CDS zahteva | Tipična kratka oznaka | Projektni pomen |
| --- | --- | --- |
| `2m_temperature` | `t2m` | temperatura zraka |
| `2m_dewpoint_temperature` | `d2m` | iz tega izračunamo relativno vlago |
| `total_precipitation` | `tp` | padavine |
| `soil_temperature_level_1` | `stl1` | temperatura tal, plast 0-7 cm |
| `soil_temperature_level_2` | `stl2` | temperatura tal, plast 7-28 cm |
| `volumetric_soil_water_layer_1` | `swvl1` | volumetrična vlažnost tal, plast 0-7 cm |
| `volumetric_soil_water_layer_2` | `swvl2` | volumetrična vlažnost tal, plast 7-28 cm |

## Obdelava podatkov

Iz surovih `.nc` datotek pripravimo projektne značilke:

1. `t2m`, `d2m`, `stl1` in `stl2` pretvorimo iz Kelvina v stopinje Celzija.
2. Relativno vlago zraka izračunamo iz temperature zraka in rosišča po Magnusovi aproksimaciji:

```text
RH = 100 * exp((17.625 * Td) / (243.04 + Td) - (17.625 * T) / (243.04 + T))
```

kjer sta `T` in `Td` izražena v `degC`.

3. `total_precipitation` pretvorimo iz metrov vodnega ekvivalenta v milimetre.
4. Ker je `total_precipitation` v ERA5-Land akumulirana spremenljivka, jo deakumuliramo v urne padavine `precipitation_hourly_mm`.
5. `swvl1` in `swvl2` ohranimo v izvorni enoti volumetričnega deleža `m3/m3`.

## Izhodne mape

Surovi prenos:
- `data/raw/copernicus/era5land_slovenia/hourly/*.nc`

Manifest prenosa:
- `data/raw/copernicus/era5land_slovenia/manifest.json`

Izpeljane značilke:
- `data/interim/features/copernicus/era5land_slovenia/hourly/*.nc`

Manifest izpeljanih značilk:
- `data/interim/features/copernicus/era5land_slovenia/manifest.json`

## Reproducibilnost

Namestitev odvisnosti:

```bash
python3 -m pip install -r scripts/data/copernicus/requirements.txt
```

Privzeti prenos in priprava:

```bash
python3 scripts/data/copernicus/download_era5land_slovenia.py
```

Preverjanje brez prenosa:

```bash
python3 scripts/data/copernicus/download_era5land_slovenia.py --dry-run
```

## Pomen za metodologijo projekta

Ta vir uporabimo zato, ker daje enoten, prostorsko skladen in dolg časovni niz za:
- temperaturo zraka
- relativno vlago zraka
- padavine
- temperaturo tal
- vlažnost tal

To so ključni abiotski dejavniki, ki lahko vplivajo na aktivnost klopov, mikroklimatsko primernost habitata in posledično na prostorsko-časovno tveganje.
