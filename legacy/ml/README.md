# ML

`ml/` vsebuje modelni del projekta: konfiguracije, trening pipeline in referenčne
baseline modele za napovedovanje tveganja.

## Jedro mape

- `training/`: reproducibilen trening s CatBoost
- `features/`: rezerviran prostor za namensko modelno feature logiko
- `inference/`: rezerviran prostor za prihodnje produkcijske izračune napovedi

## Trenutni referenčni modeli

- borelioza: `catboost_tick_borne_lyme_v1`
- KME: priporočena eksperimentalna smer je `kme v2` z bolj konzervativno klasifikacijsko formulacijo

Za trening pipeline in konfiguracije glej:

- [training/README.md](training/README.md)
- [training/example_tick_borne_lyme_config.json](training/example_tick_borne_lyme_config.json)
- [training/example_tick_borne_kme_v2_config.json](training/example_tick_borne_kme_v2_config.json)
