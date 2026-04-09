#!/bin/bash
#SBATCH --job-name=klop-catboost
#SBATCH --partition=gridlong
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=slurm-%x-%j.out

set -euo pipefail

cd "${SLURM_SUBMIT_DIR:-$PWD}"

export CONFIG_PATH="${CONFIG_PATH:-ml/training/example_tick_borne_lyme_config.json}"
export ENV_DIR="${ENV_DIR:-$PWD/.venv-sling}"
export REBUILD_DATASET="${REBUILD_DATASET:-1}"
export VALIDATE_ONLY="${VALIDATE_ONLY:-0}"

bash scripts/hpc/sling_run_training.sh "$CONFIG_PATH"
