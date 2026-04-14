from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = PIPELINE_ROOT / "output"
MODEL_A_OUTPUT_ROOT = OUTPUT_ROOT / "model_a"
MODEL_C_OUTPUT_ROOT = OUTPUT_ROOT / "model_c"
VALIDATION_ROOT = OUTPUT_ROOT / "validation"
SLOVENIA_BBOX_NWSE = [46.9, 13.3, 45.3, 16.6]
PROXY_ENV_VARS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: object) -> None:
    ensure_dirs(path.parent)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clear_proxy_environment() -> list[str]:
    cleared: list[str] = []
    for name in PROXY_ENV_VARS:
        if os.environ.get(name):
            os.environ.pop(name, None)
            cleared.append(name)
    return cleared


def bytes_to_mb(size_bytes: int) -> float:
    return round(size_bytes / (1024 * 1024), 3)
