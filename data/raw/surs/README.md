# SURS

Ta mapa vsebuje surove podatke iz Statističnega urada Republike Slovenije (SURS).

## Občinsko prebivalstvo

- Datoteka: `obcina_population_sistat.json`
- Vsebina: uradni `json-stat2` izvoz občina x leto za mero `Population - Total - 1 January`
- Vir: SURS SiStat, tabela `2640010S` (`Selected data on municipalities, Slovenia, annually`)
- Datum prevzema: `2026-04-09`
- API endpoint: <https://pxweb.stat.si/SiStatData/api/v1/en/Data/2640010S.px>
- Izvorna spletna tabela: <https://pxweb.stat.si/SiStatData/pxweb/en/Data/-/2640010S.px/>

Uporabljen je originalni odgovor API brez ročnih popravkov. Čiščenje, normalizacija občinskih šifer in morebitni fallback za manjkajoče objave se izvajajo šele v `pipelines/features/`.

## Statistične regije in občine

- Datoteka: `statistical_regions_municipalities_2022.xlsx`
- Vsebina: uradni hierarhični šifrant statističnih regij, občin in naselij `NUTS3,_SKTE5,7`, različica 2022
- Vir: SURS Klasje, klasifikacijska tabela `17597`
- Različica velja od: `2022-11-17`
- Datum prevzema: `2026-08-14`
- Izvoz: <https://www.stat.si/Klasje/Klasje/createXlsx?q=17597&s=1>
- Stran klasifikacije: <https://www.stat.si/Klasje/Klasje/Tabela/17597>
- SHA-256: `b032009504dee70a17dd454bc1718c8c7f4eb776ff03583be29245dcf4fbbbc9`

Datoteka je nespremenjen SURS Excel izvoz. V njem so ravni: `1` statistična regija, `2` občina in `3` naselje. Aktivni model_v3 uporablja samo ravni 1 in 2 ter občine poveže s kanonično občinsko dimenzijo izključno po trimestni občinski šifri.
