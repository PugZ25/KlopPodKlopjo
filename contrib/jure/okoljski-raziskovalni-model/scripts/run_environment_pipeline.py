#!/usr/bin/env python3
"""Run the okoljski_raziskovalni_model pipeline end to end."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"

PIPELINE_STEPS = [
    "normalize_slovenia_local_data.py",
    "build_master_weekly_panel.py",
    "build_master_panel_variable_flags.py",
    "build_environment_model_ready.py",
    "run_environment_grouped_factor_ablation.py",
    "build_environment_graphs.py",
    "run_environment_validation.py",
]


def main() -> None:
    for script_name in PIPELINE_STEPS:
        script_path = SCRIPTS_DIR / script_name
        print(f"\n=== Running {script_name} ===")
        subprocess.run([sys.executable, str(script_path)], check=True, cwd=ROOT_DIR)

    print("\nokoljski_raziskovalni_model pipeline completed successfully.")


if __name__ == "__main__":
    main()
