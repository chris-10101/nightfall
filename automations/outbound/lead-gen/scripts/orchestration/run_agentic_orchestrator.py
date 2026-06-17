from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import os
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from core.csv_store import append_csv_atomic, read_csv, write_csv_atomic
from core.icp_profiles import profile_for_row
from core.monitoring import init_sentry
from core.paths import data_dir, orchestration_dir
from imports.import_hr_consultancies import HEADERS as PROSPECT_HEADERS
from orchestration import run_daily_orchestrator
from orchestration.tool_executor import execute as execute_tool
from orchestration.tool_registry import AgentTool, load_tools
from outreach.build_campaign_queue import QUEUE_HEADERS


UK_TZ = ZoneInfo("Europe/London")
DATA_DIR = data_dir()
ORCHESTRATION_DIR = orchestration_dir()
PROSPECTS_PATH = DATA_DIR / "prospects.csv"
QUEUE_PATH = DATA_DIR / "campaign_queue.csv"
AGENT_EVENTS_PATH = DATA_DIR / "agent_events.csv"

POLICY_VERSION = "agentic-v1"
MAX_REASON_LENGTH = 700

AGENTIC_FIELDS = [
    "agentic_policy_version",
    "agentic_decision_at",
    "agentic_state",
    "agentic_confidence",
    "agentic_reasoning",
    "agentic_selected_tool",
    "agentic_tool_args",
    "agentic_tool_status",
    "agentic_tool_run_id",
    "agentic_handoff_reason",
]

EVENT_HEADERS = [
    "event_id",
    "run_id",
    "created_at",
    "lead_id",
    "company_name",
    "email",
    "profile",
    "agentic_state",
    "selected_tool",
    "tool_args",
    "tool_status",
    "tool_run_id",
    "confidence",
    "reasoning",
    "handoff_reason",
]

NON_EMAIL_AUTO_TOOLS = {
    "discover_icp_contacts",
    "enrich_public_web",
    "enrich_decision_maker",
    "qualify_and_queue",
    "retrieve_kb_context",
}


@dataclass
class AgentPlan:
    lead_id: str
    company_name: str
    email: str
    profile: str
    lifecycle_state: str
    next_action: str
    selected_tool: str
    tool_args: dict
    confidence: float
    reasoning: str
    agentic_state: str
    handoff_reason: str = ""
    tool_status: str = "not_run"
    tool_run_id: str = ""


def now_uk() -> datetime:
    return datetime.now(UK_TZ)


def utc_iso(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def ensure_headers(rows: list[dict[str, str]], base_headers: list[str]) -> list[str]:
    headers = list(base_headers)
    for field in AGENTIC_FIELDS:
        if field not in headers:
            headers.append(field)
    for row in rows:
        for field in headers:
            row.setdefault(field, "")
    return headers


def queue_lookup() -> dict[str, dict[str, str]]:
    return {row.get("lead_id", ""): row for row in read_csv(QUEUE_PATH) if row.get("lead_id")}


def parse_tool_args(value: str) -> dict:
    value = (value or "").strip()
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def tool_args_to_argv(args: dict) -> list[str]:
    argv: list[str] = []
    for key in sorted(args):
        value = args[key]
        if value is False or value is None or value == "":
            continue
        if not str(key).startswith("--"):
            key = f"--{key}"
        if value is True:
            argv.append(str(key))
        else:
            argv.extend([str(key), str(value)])
    return argv


def trim_reason(value: str) -> str:
    value = " ".join((value or "").split())
    return value[:MAX_REASON_LENGTH]


def enrich_planned_args(row: dict[str, str], planned_tool: str, planned_args: dict) -> dict:
    args = dict(planned_args)
    profile_key, _ = profile_for_row(row)
    if planned_tool == "discover_icp_contacts" and profile_key and "--profile" not in args and "profile" not in args:
        args["--profile"] = profile_key
    return args


def plan_for_contact(row: dict[str, str], queue_row: dict[str, str] | None, tools: dict[str, AgentTool]) -> AgentPlan:
    combined = dict(row)
    if queue_row:
        combined.update({key: value for key, value in queue_row.items() if value})

    planned_tool = (combined.get("planned_tool") or "").strip()
    planned_args = enrich_planned_args(combined, planned_tool, parse_tool_args(combined.get("planned_tool_args", "")))
    profile_key, _ = profile_for_row(combined)
    lifecycle_state = combined.get("lifecycle_state", "")
    next_action = combined.get("agent_next_action", "")
    reason = combined.get("planned_reason") or combined.get("agent_last_decision") or "No lifecycle reason recorded."

    if not planned_tool:
        return AgentPlan(
            lead_id=combined.get("lead_id", ""),
            company_name=combined.get("company_name", ""),
            email=combined.get("email", ""),
            profile=profile_key,
            lifecycle_state=lifecycle_state,
            next_action=next_action,
            selected_tool="",
            tool_args={},
            confidence=0.35 if combined.get("agent_requires_review") == "true" else 0.6,
            reasoning=trim_reason(f"No tool needed. Lifecycle says: {reason}"),
            agentic_state="waiting" if next_action in {"wait_until_due", "none"} else "needs_review",
            handoff_reason="human_review_required" if combined.get("agent_requires_review") == "true" else "",
        )

    if planned_tool not in tools:
        return AgentPlan(
            lead_id=combined.get("lead_id", ""),
            company_name=combined.get("company_name", ""),
            email=combined.get("email", ""),
            profile=profile_key,
            lifecycle_state=lifecycle_state,
            next_action=next_action,
            selected_tool=planned_tool,
            tool_args=planned_args,
            confidence=0.2,
            reasoning=trim_reason(f"Lifecycle selected unregistered tool {planned_tool}. Reason: {reason}"),
            agentic_state="blocked",
            handoff_reason="unregistered_tool",
        )

    tool = tools[planned_tool]
    if tool.can_send_email:
        return AgentPlan(
            lead_id=combined.get("lead_id", ""),
            company_name=combined.get("company_name", ""),
            email=combined.get("email", ""),
            profile=profile_key,
            lifecycle_state=lifecycle_state,
            next_action=next_action,
            selected_tool=planned_tool,
            tool_args=planned_args,
            confidence=0.85,
            reasoning=trim_reason(
                "Email-capable tool selected, but agentic orchestrator will not send mail. "
                f"The approved-send worker and VESRA_AUTO_SEND_ENABLED gate must handle it. Reason: {reason}"
            ),
            agentic_state="handoff",
            handoff_reason="email_requires_existing_approval_gate",
        )

    if tool.requires_review:
        return AgentPlan(
            lead_id=combined.get("lead_id", ""),
            company_name=combined.get("company_name", ""),
            email=combined.get("email", ""),
            profile=profile_key,
            lifecycle_state=lifecycle_state,
            next_action=next_action,
            selected_tool=planned_tool,
            tool_args=planned_args,
            confidence=0.75,
            reasoning=trim_reason(f"Tool requires human review before use. Reason: {reason}"),
            agentic_state="needs_review",
            handoff_reason="tool_requires_review",
        )

    return AgentPlan(
        lead_id=combined.get("lead_id", ""),
        company_name=combined.get("company_name", ""),
        email=combined.get("email", ""),
        profile=profile_key,
        lifecycle_state=lifecycle_state,
        next_action=next_action,
        selected_tool=planned_tool,
        tool_args=planned_args,
        confidence=0.9 if planned_tool in NON_EMAIL_AUTO_TOOLS else 0.7,
        reasoning=trim_reason(f"Selected {planned_tool} from lifecycle plan. Reason: {reason}"),
        agentic_state="tool_ready" if planned_tool in NON_EMAIL_AUTO_TOOLS else "planned",
    )


def should_execute(plan: AgentPlan, tool: AgentTool | None, *, execute_safe_tools: bool) -> tuple[bool, str]:
    if not execute_safe_tools:
        return False, "execution_disabled"
    if not plan.selected_tool or not tool:
        return False, "no_tool"
    if plan.agentic_state != "tool_ready":
        return False, plan.handoff_reason or "not_tool_ready"
    if tool.can_send_email:
        return False, "email_tool_blocked"
    if tool.requires_review:
        return False, "review_required"
    if plan.selected_tool not in NON_EMAIL_AUTO_TOOLS:
        return False, "not_auto_allowed"
    return True, ""


def update_rows_with_plan(
    prospects: list[dict[str, str]],
    queue_rows: list[dict[str, str]],
    plans: dict[str, AgentPlan],
    decision_at: str,
) -> None:
    for row in prospects:
        plan = plans.get(row.get("lead_id", ""))
        if not plan:
            continue
        write_plan_fields(row, plan, decision_at)
    for row in queue_rows:
        plan = plans.get(row.get("lead_id", ""))
        if not plan:
            continue
        write_plan_fields(row, plan, decision_at)


def write_plan_fields(row: dict[str, str], plan: AgentPlan, decision_at: str) -> None:
    row["agentic_policy_version"] = POLICY_VERSION
    row["agentic_decision_at"] = decision_at
    row["agentic_state"] = plan.agentic_state
    row["agentic_confidence"] = f"{plan.confidence:.2f}"
    row["agentic_reasoning"] = plan.reasoning
    row["agentic_selected_tool"] = plan.selected_tool
    row["agentic_tool_args"] = json.dumps(plan.tool_args, sort_keys=True)
    row["agentic_tool_status"] = plan.tool_status
    row["agentic_tool_run_id"] = plan.tool_run_id
    row["agentic_handoff_reason"] = plan.handoff_reason


def append_events(run_id: str, decision_at: str, plans: list[AgentPlan]) -> None:
    for index, plan in enumerate(plans, start=1):
        append_csv_atomic(
            AGENT_EVENTS_PATH,
            {
                "event_id": f"{run_id}-{index:05d}",
                "run_id": run_id,
                "created_at": decision_at,
                "lead_id": plan.lead_id,
                "company_name": plan.company_name,
                "email": plan.email,
                "profile": plan.profile,
                "agentic_state": plan.agentic_state,
                "selected_tool": plan.selected_tool,
                "tool_args": json.dumps(plan.tool_args, sort_keys=True),
                "tool_status": plan.tool_status,
                "tool_run_id": plan.tool_run_id,
                "confidence": f"{plan.confidence:.2f}",
                "reasoning": plan.reasoning,
                "handoff_reason": plan.handoff_reason,
            },
            EVENT_HEADERS,
        )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def run(
    *,
    rebuild_queue: bool,
    execute_safe_tools: bool,
    max_contacts: int,
    max_tool_runs: int,
    dry_run_tools: bool,
) -> dict:
    init_sentry("agentic-orchestrator")
    lifecycle_summary = run_daily_orchestrator.run(rebuild_queue=rebuild_queue)
    current = now_uk()
    run_id = current.strftime("%Y%m%dT%H%M%S%z")
    decision_at = utc_iso(current)

    tools = load_tools()
    prospects = read_csv(PROSPECTS_PATH)
    queue_rows = read_csv(QUEUE_PATH)
    prospect_headers = ensure_headers(prospects, PROSPECT_HEADERS)
    queue_headers = ensure_headers(queue_rows, QUEUE_HEADERS)
    queue = queue_lookup()

    selected_plans: list[AgentPlan] = []
    plans_by_lead_id: dict[str, AgentPlan] = {}
    for row in prospects:
        if max_contacts and len(selected_plans) >= max_contacts:
            break
        lead_id = row.get("lead_id", "")
        plan = plan_for_contact(row, queue.get(lead_id), tools)
        selected_plans.append(plan)
        plans_by_lead_id[lead_id] = plan

    executed_keys: set[str] = set()
    tool_runs = 0
    for plan in selected_plans:
        tool = tools.get(plan.selected_tool)
        should_run, skip_reason = should_execute(plan, tool, execute_safe_tools=execute_safe_tools)
        tool_key = json.dumps({"tool": plan.selected_tool, "args": plan.tool_args}, sort_keys=True)
        if should_run and tool_key in executed_keys:
            plan.tool_status = "deduped"
            plan.tool_run_id = ""
            continue
        if should_run and max_tool_runs and tool_runs >= max_tool_runs:
            should_run = False
            skip_reason = "tool_run_cap_reached"
        if not should_run:
            plan.tool_status = skip_reason
            continue
        result = execute_tool(
            plan.selected_tool,
            tool_args_to_argv(plan.tool_args),
            dry_run=dry_run_tools,
            raise_on_failure=False,
        )
        executed_keys.add(tool_key)
        tool_runs += 1
        plan.tool_status = result.get("status", "unknown")
        plan.tool_run_id = result.get("run_id", "")
        if result.get("status") == "failed":
            plan.agentic_state = "blocked"
            plan.handoff_reason = "tool_failed"

    update_rows_with_plan(prospects, queue_rows, plans_by_lead_id, decision_at)
    write_csv_atomic(PROSPECTS_PATH, prospects, prospect_headers)
    write_csv_atomic(QUEUE_PATH, queue_rows, queue_headers)
    append_events(run_id, decision_at, selected_plans)

    state_counts = Counter(plan.agentic_state for plan in selected_plans)
    tool_counts = Counter(plan.selected_tool or "none" for plan in selected_plans)
    status_counts = Counter(plan.tool_status for plan in selected_plans)
    summary = {
        "run_id": run_id,
        "ran_at": decision_at,
        "policy_version": POLICY_VERSION,
        "rebuild_queue": rebuild_queue,
        "execute_safe_tools": execute_safe_tools,
        "dry_run_tools": dry_run_tools,
        "max_contacts": max_contacts,
        "max_tool_runs": max_tool_runs,
        "contacts_considered": len(selected_plans),
        "tool_runs": tool_runs,
        "state_counts": dict(sorted(state_counts.items())),
        "tool_counts": dict(sorted(tool_counts.items())),
        "tool_status_counts": dict(sorted(status_counts.items())),
        "lifecycle_summary": lifecycle_summary,
        "samples": [asdict(plan) for plan in selected_plans[:25]],
    }
    write_json(ORCHESTRATION_DIR / f"agentic_orchestrator_{run_id}.json", summary)
    return summary


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "y", "on"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Vesra agentic contact orchestrator.")
    parser.add_argument("--rebuild-queue", action="store_true", help="Rebuild campaign queue before planning.")
    parser.add_argument(
        "--execute-safe-tools",
        action="store_true",
        default=env_flag("VESRA_AGENTIC_EXECUTE_SAFE_TOOLS"),
        help="Execute capped non-email, non-review tools selected by the agent policy.",
    )
    parser.add_argument("--dry-run-tools", action="store_true", help="Plan tool execution without running commands.")
    parser.add_argument("--max-contacts", type=int, default=int(os.environ.get("VESRA_AGENTIC_MAX_CONTACTS", "500")))
    parser.add_argument("--max-tool-runs", type=int, default=int(os.environ.get("VESRA_AGENTIC_MAX_TOOL_RUNS", "3")))
    parser.add_argument("--summary", action="store_true", help="Print JSON summary.")
    args = parser.parse_args()

    summary = run(
        rebuild_queue=args.rebuild_queue,
        execute_safe_tools=args.execute_safe_tools,
        max_contacts=args.max_contacts,
        max_tool_runs=args.max_tool_runs,
        dry_run_tools=args.dry_run_tools,
    )
    if args.summary:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return
    print(
        f"Agentic orchestrator considered {summary['contacts_considered']} contacts; "
        f"tool_runs={summary['tool_runs']}; states={summary['state_counts']}"
    )


if __name__ == "__main__":
    main()
