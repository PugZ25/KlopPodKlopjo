# Zagon Na ARNES SLING

Ta mapa vsebuje pripravljene skripte za zagon CatBoost modela na SLING prek `SLURM`.

## Datoteke

- `scripts/hpc/sling_setup_env.sh`: ustvari Python okolje in namesti pakete
- `scripts/hpc/sling_run_training.sh`: lokalni ali batch zagon build + train pipeline-a
- `scripts/hpc/sling_catboost_train.sbatch`: predloga za `sbatch`

## Hiter postopek

Na prijavnem vozliscu v korenu repozitorija:

```bash
bash scripts/hpc/sling_setup_env.sh
sbatch --export=ALL,CONFIG_PATH=ml/training/example_tick_borne_lyme_config.json scripts/hpc/sling_catboost_train.sbatch
```

Za KME:

```bash
sbatch --export=ALL,CONFIG_PATH=ml/training/example_tick_borne_kme_config.json scripts/hpc/sling_catboost_train.sbatch
```

Za priporoceni `KME v2` pristop z redkim dogodkom:

```bash
sbatch --export=ALL,CONFIG_PATH=ml/training/example_tick_borne_kme_v2_config.json scripts/hpc/sling_catboost_train.sbatch
```

## Opombe

- Privzeto se finalni CatBoost dataset pred vsakim zagonom ponovno zgradi.
- Ce ga ne zelis ponovno graditi, dodaj `REBUILD_DATASET=0`.
- Ce zelis samo preveriti shemo in split brez ucenja, dodaj `VALIDATE_ONLY=1`.
- `thread_count` se avtomatsko prilagodi iz `SLURM_CPUS_PER_TASK`, ce ni podan v konfiguraciji.
