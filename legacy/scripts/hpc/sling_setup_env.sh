#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_DIR="${1:-$ROOT_DIR/.venv-sling}"

cd "$ROOT_DIR"

python3 -m venv "$ENV_DIR"
source "$ENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r ml/training/requirements-sling.txt

echo "SLING Python environment is ready: $ENV_DIR"
echo "Activate with: source $ENV_DIR/bin/activate"
