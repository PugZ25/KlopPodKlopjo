# Zunanji Prispevki

Mapa `contrib/` hrani zunanje ali naknadno uvožene delovne veje, ki:

- niso del uradnega glavnega pipeline toka projekta
- se ne smejo neposredno mešati z mapami `data/`, `pipelines/`, `ml/`, `frontend/` ali `backend/`
- jih hranimo zaradi revizijske sledljivosti, metodološke reference ali kasnejše selektivne integracije

Pravilo:

- če je nekaj zunanji snapshot ali ločen eksperimentalni workspace, najprej sodi v `contrib/`
- v glavni del repozitorija se prenese šele po namenskem refaktorju in ločeni metodološki odločitvi

Trenutno:

- [contrib/jure/README.md](/Users/zankespert/Desktop/KlopPodKlopjo/contrib/jure/README.md): kuriran uvoz Juretovega zunanjega workspacea
