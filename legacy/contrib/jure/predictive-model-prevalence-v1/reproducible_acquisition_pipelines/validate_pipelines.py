from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from common import VALIDATION_ROOT, ensure_dirs, timestamp_utc, write_json


PIPELINE_ROOT = Path(__file__).resolve().parent


def run_command(label: str, command: list[str]) -> dict[str, object]:
    result = subprocess.run(
        command,
        cwd=str(PIPELINE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "label": label,
        "command": command,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main() -> int:
    ensure_dirs(VALIDATION_ROOT)
    checks = [
        run_command(
            "model_a_dry_run",
            [
                sys.executable,
                str(PIPELINE_ROOT / "model_a_forecast" / "run_download.py"),
                "--dry-run",
                "--year",
                "2026",
                "--months",
                "01",
                "02",
                "03",
                "04",
            ],
        ),
        run_command(
            "model_c_dry_run",
            [
                sys.executable,
                str(PIPELINE_ROOT / "model_c_climate" / "run_download.py"),
                "--dry-run",
            ],
        ),
    ]
    payload = {
        "generated_at_utc": timestamp_utc(),
        "checks": checks,
        "all_passed": all(item["exit_code"] == 0 for item in checks),
    }
    write_json(VALIDATION_ROOT / "validation_report.json", payload)
    lines = [
        "# Reproducible Pipeline Validation",
        "",
        f"- generated at: `{payload['generated_at_utc']}`",
        f"- all passed: `{payload['all_passed']}`",
        "",
    ]
    for check in checks:
        lines.extend(
            [
                f"## {check['label']}",
                "",
                f"- exit code: `{check['exit_code']}`",
                "",
                "```text",
                (check["stdout"] or "<empty>").rstrip(),
                "```",
                "",
            ]
        )
    (VALIDATION_ROOT / "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Validation report written to: {VALIDATION_ROOT / 'validation_report.md'}")
    return 0 if payload["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
