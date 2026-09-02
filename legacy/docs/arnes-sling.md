# ARNES SLING

Repo je pripravljen za zagon CatBoost treninga na SLING prek prijavnega vozlisca in `SLURM`.

## Priporocen nacin

Po uradni SLING dokumentaciji so za programsko okolje na grucah podprti uporabniski pristopi, kot so `conda` in vsebniki, za oddajo poslov pa `SLURM` na podprtih grucah. Za ta projekt je pripravljen lahek pristop z lastnim Python virtualnim okoljem in `sbatch` skripto.

Viri:

- SLING software navodila: https://doc.sling.si/en/navodila/sw/
- SLING SLURM navodila: https://doc.sling.si/en/navodila/slurm-usage/
- CatBoost Python install: https://catboost.ai/docs/en/concepts/python-installation

## Kaj prenesete na SLING

Na SLING prenesite:

- cel repozitorij
- posebej pomembno mapo `data/processed/training/`
- ce zelite rebuild finalnega dataseta na SLING, tudi vse CSV vhode v `data/processed/training/`

Najpomembnejsi vhod za sam trening je:

- `data/processed/training/obcina_weekly_tick_borne_catboost_ready.csv`

## Koraki na prijavnem vozliscu

V korenu projekta:

```bash
bash scripts/hpc/sling_setup_env.sh
```

To ustvari `.venv-sling` in namesti:

- `catboost`
- `pandas`

## Test brez ucenja

```bash
ENV_DIR=$PWD/.venv-sling VALIDATE_ONLY=1 REBUILD_DATASET=0 \
bash scripts/hpc/sling_run_training.sh ml/training/example_tick_borne_lyme_config.json
```

## Oddaja pravega treninga

Za boreliozo:

```bash
sbatch --export=ALL,CONFIG_PATH=ml/training/example_tick_borne_lyme_config.json scripts/hpc/sling_catboost_train.sbatch
```

Za KME:

```bash
sbatch --export=ALL,CONFIG_PATH=ml/training/example_tick_borne_kme_config.json scripts/hpc/sling_catboost_train.sbatch
```

Za priporoceni `KME v2` klasifikacijski zagon:

```bash
sbatch --export=ALL,CONFIG_PATH=ml/training/example_tick_borne_kme_v2_config.json scripts/hpc/sling_catboost_train.sbatch
```

## Privzeti viri v `sbatch`

Predloga trenutno zahteva:

- `--partition=gridlong`
- `--cpus-per-task=8`
- `--mem=16G`
- `--time=04:00:00`

To je namenoma konzervativno za CatBoost CPU trening na vasem datasetu. Po potrebi prilagodite particijo in cas pravilom konkretne gruce.

## Kje bodo rezultati

Rezultati treninga se zapisujejo v direktorija iz konfiguracij:

- `data/processed/training/catboost_tick_borne_lyme_v1/`
- `data/processed/training/catboost_tick_borne_kme_v1/`
- `data/processed/training/catboost_tick_borne_kme_presence_v2/`

V vsakem dobite:

- `model.cbm`
- `metadata.json`
- `holdout_predictions.csv`

## Operativne opombe

- Trening pipeline uporablja casovni split po `week_start`, ne random splita.
- Ce `catboost.thread_count` ni nastavljen v JSON configu, se avtomatsko uporabi `SLURM_CPUS_PER_TASK`.
- Ce zelite hitrejsi zagon in ne potrebujete rebuilda finalnega dataseta, nastavite `REBUILD_DATASET=0`.
- Ce imate na SLING samo ARC dostop in ne neposrednega `SLURM` dostopa, je treba pripraviti se XRSL ovojnico posebej.
