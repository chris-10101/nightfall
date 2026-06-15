from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
from dataclasses import dataclass

from core.paths import config_dir


REGISTRY_PATH = config_dir() / "agent_tools.json"
REGISTRY_EXAMPLE_PATH = Path(__file__).resolve().parents[2] / "config" / "agent_tools.json"


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    command: list[str]
    mutates_state: bool
    requires_review: bool
    can_send_email: bool
    allowed_args: set[str]


def load_tools() -> dict[str, AgentTool]:
    path = REGISTRY_PATH if REGISTRY_PATH.exists() else REGISTRY_EXAMPLE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    tools = {}
    for item in payload.get("tools", []):
        tool = AgentTool(
            name=item["name"],
            description=item.get("description", ""),
            command=list(item["command"]),
            mutates_state=bool(item.get("mutates_state")),
            requires_review=bool(item.get("requires_review")),
            can_send_email=bool(item.get("can_send_email")),
            allowed_args=set(item.get("allowed_args", [])),
        )
        tools[tool.name] = tool
    return tools


def require_tool(name: str) -> AgentTool:
    tools = load_tools()
    if name not in tools:
        raise SystemExit(f"Unknown agent tool: {name}")
    return tools[name]
