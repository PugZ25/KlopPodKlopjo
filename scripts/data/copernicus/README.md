# Copernicus NetCDF

Za hitro pregledovanje `.nc` datotek uporabi:

```bash
pip install xarray netCDF4
python scripts/data/copernicus/inspect_nc.py path/to/file.nc
```

Primer za dodatne informacije o posamezni spremenljivki:

```bash
python scripts/data/copernicus/inspect_nc.py data/raw/copernicus/slovenia_test.nc --variable t2m --stats
```

Skripta izpiše:
- dimenzije
- koordinate
- spremenljivke in njihove tipe
- globalne atribute
- podrobnosti in osnovno statistiko za izbrano spremenljivko
