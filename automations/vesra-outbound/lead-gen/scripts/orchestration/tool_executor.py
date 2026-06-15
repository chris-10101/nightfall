from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone

from core.monitoring import init_sentry
from core.paths import orchestration_dir
from orchestration.tool_registry import require_tool


def validate_args(tool_name: str, argv: list[str]) -> None:
    tool = require_tool(tool_name)
    index = 0
    while index < len(argv):
        value = argv[index]
        if not value.startswith("--"):
            raise SystemExit(f"Positional args are not allowed for tool {tool_name}: {value}")
        key = value.split("=", 1)[0]
        if key not in tool.allowed_args:
            raise SystemExit(f"Argument {key} is not allowed for tool {tool_name}.")
        if "=" not in value and index + 1 < len(argv) and not argv[index + 1].startswith("--"):
            index += 2
        else:
            index += 1


def log_result(payload: dict) -> None:
    directory = orchestration_dir() / "tool-runs"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"tool_{payload['run_id']}_{payload['tool']}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def execute(tool_name: str, argv: list[str], *, dry_run: bool = False) -> dict:
    init_sentry("tool-executor")
    validate_args(tool_name, argv)
    tool = require_tool(tool_name)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    command = tool.command + argv
    payload = {
        "run_id": run_id,
        "tool": tool.name,
        "description": tool.description,
        "command": command,
        "dry_run": dry_run,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "can_send_email": tool.can_send_email,
        "requires_review": tool.requires_review,
    }
    if dry_run:
        payload.update({"returncode": 0, "stdout": "", "stderr": "", "status": "dry_run"})
        log_result(payload)
        return payload

    result = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[2],
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        timeout=60 * 30,
    )
    payload.update(
        {
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "returncode": result.returncode,
            "stdout": result.stdout[-8000:],
            "stderr": result.stderr[-8000:],
            "status": "ok" if result.returncode == 0 else "failed",
        }
    )
    log_result(payload)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute one approved Vesra agent tool.")
    parser.add_argument("tool")
    parser.add_argument("--dry-run", action="store_true")
    args, remainder = parser.parse_known_args()
    payload = execute(args.tool, remainder, dry_run=args.dry_run)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
