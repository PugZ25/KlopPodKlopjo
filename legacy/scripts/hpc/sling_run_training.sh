#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_PATH="${1:-ml/training/example_tick_borne_lyme_config.json}"
ENV_DIR="${ENV_DIR:-$ROOT_DIR/.venv-sling}"
REBUILD_DATASET="${REBUILD_DATASET:-1}"
VALIDATE_ONLY="${VALIDATE_ONLY:-0}"

cd "$ROOT_DIR"

if [[ ! -x "$ENV_DIR/bin/python" ]]; then
  echo "Python environment not found: $ENV_DIR" >&2
  echo "Run: bash scripts/hpc/sling_setup_env.sh $ENV_DIR" >&2
  exit 1
fi

source "$ENV_DIR/bin/activate"

THREADS="${SLURM_CPUS_PER_TASK:-${OMP_NUM_THREADS:-1}}"
export OMP_NUM_THREADS="$THREADS"
export OPENBLAS_NUM_THREADS="$THREADS"
export MKL_NUM_THREADS="$THREADS"
export NUMEXPR_NUM_THREADS="$THREADS"
export PYTHONUNBUFFERED=1

echo "Python: $(python --version 2>&1)"
echo "Config: $CONFIG_PATH"
echo "Threads: $THREADS"

if [[ "$REBUILD_DATASET" == "1" ]]; then
  echo "Rebuilding final CatBoost dataset..."
  python scripts/data/build_obcina_weekly_tick_borne_catboost_dataset.py
fi

if [[ "$VALIDATE_ONLY" == "1" ]]; then
  python -m ml.training.train --config "$CONFIG_PATH" --validate-only
else
  python -m ml.training.train --config "$CONFIG_PATH"
fi
