from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


OUTBOUND_ROOT = Path(__file__).resolve().parents[1]
TENANTS_DIR = OUTBOUND_ROOT / "tenants"


def load_tenant(tenant: str) -> dict:
    path = TENANTS_DIR / tenant / "tenant.json"
    if not path.exists():
        raise SystemExit(f"Unknown outbound tenant: {tenant}")
    return json.loads(path.read_text(encoding="utf-8"))


def legacy_working_dir(config: dict) -> Path:
    value = config.get("legacy_automation_path", "")
    if not value:
        raise SystemExit("Tenant has no legacy_automation_path.")
    path = Path(value)
    if path.is_absolute():
        return path
    return (OUTBOUND_ROOT / path).resolve()


def execute(tenant: str, tool_name: str, args: list[str]) -> int:
    config = load_tenant(tenant)
    tools = config.get("tools", {})
    if tool_name not in tools:
        available = ", ".join(sorted(tools))
        raise SystemExit(f"Unknown tool {tool_name!r} for tenant {tenant}. Available: {available}")
    cwd = legacy_working_dir(config)
    if not cwd.exists():
        raise SystemExit(f"Tenant working directory does not exist: {cwd}")
    command = list(tools[tool_name]) + args
    result = subprocess.run(command, cwd=cwd, env=os.environ.copy())
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a registered outbound tenant tool.")
    parser.add_argument("--tenant", default=os.environ.get("NIGHTFALL_OUTBOUND_TENANT", "vesra"))
    parser.add_argument("tool")
    parsed, remainder = parser.parse_known_args()
    raise SystemExit(execute(parsed.tenant, parsed.tool, remainder))


if __name__ == "__main__":
    main()
