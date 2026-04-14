#!/usr/bin/env python3
"""Canonical pipeline entrypoint for okoljski_raziskovalni_model."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PIPELINE_SCRIPT = ROOT_DIR / "scripts" / "run_environment_pipeline.py"


def main() -> None:
    subprocess.run([sys.executable, str(PIPELINE_SCRIPT)], check=True, cwd=ROOT_DIR)


if __name__ == "__main__":
    main()
