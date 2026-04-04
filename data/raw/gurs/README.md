# GURS

Ta mapa vsebuje surove prostorske podatke iz Geodetske uprave Republike Slovenije (GURS).

## Občine iz registra prostorskih enot

- Datoteka: `obcine-gurs-rpe.geojson`
- Vsebina: poligoni slovenskih občin
- Vir: GeoHub Slovenije, GURS, sloj `TEMELJNE_VSEBINE/GH_Prostorske_enote/MapServer/1530` (`občine`)
- Datum prevzema: `2026-04-04`
- Koordinatni sistem izvoza: `EPSG:4326` (`outSR=4326`)
- Format izvoza: `GeoJSON`
- REST sloj: <https://geohub.gov.si/ags/rest/services/TEMELJNE_VSEBINE/GH_Prostorske_enote/MapServer/1530>
- Query endpoint za prenos: <https://geohub.gov.si/ags/rest/services/TEMELJNE_VSEBINE/GH_Prostorske_enote/MapServer/1530/query?where=1%3D1&outFields=OBJECTID,EID_OBCINA,OB_MID,SIFRA,NAZIV,OZN_MEST_OB,OZN_MEST_OB_OPIS,DATUM_SYS,NAZIV_DJ,GEOM_AREA,NAPAKA_V_GEOMETRIJI&outSR=4326&f=geojson>

Datoteka je shranjena kot originalni prenos brez ročnih popravkov. Morebitno čiščenje ali poenostavljanje geometrije naj se izvede ločeno izven `data/raw/`. Po trenutnih pravilih v `.gitignore` je sam GeoJSON lokalna surova datoteka in ni verzioniran v Git.
