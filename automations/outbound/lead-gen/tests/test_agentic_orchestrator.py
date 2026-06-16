import unittest
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from orchestration.run_agentic_orchestrator import (
    plan_for_contact,
    should_execute,
    tool_args_to_argv,
)
from orchestration.tool_registry import AgentTool


def tool(name: str, *, can_send_email: bool = False, requires_review: bool = False) -> AgentTool:
    return AgentTool(
        name=name,
        description=name,
        command=["python3", f"{name}.py"],
        mutates_state=True,
        requires_review=requires_review,
        can_send_email=can_send_email,
        allowed_args={"--profile", "--limit", "--max-pages", "--checkpoint", "--send"},
    )


class AgenticOrchestratorTest(unittest.TestCase):
    def tools(self) -> dict[str, AgentTool]:
        return {
            "discover_icp_contacts": tool("discover_icp_contacts"),
            "enrich_public_web": tool("enrich_public_web"),
            "retrieve_kb_context": tool("retrieve_kb_context", requires_review=False),
            "send_approved_campaign": tool("send_approved_campaign", can_send_email=True, requires_review=True),
        }

    def test_adds_profile_to_discovery_tool_args(self) -> None:
        row = {
            "lead_id": "lead-1",
            "company_name": "Acme HR",
            "segment": "HR Consultancy",
            "planned_tool": "discover_icp_contacts",
            "planned_tool_args": '{"--max-new": "20", "--checkpoint": true}',
            "planned_reason": "Missing website and email.",
        }
        plan = plan_for_contact(row, None, self.tools())
        self.assertEqual(plan.agentic_state, "tool_ready")
        self.assertEqual(plan.selected_tool, "discover_icp_contacts")
        self.assertEqual(plan.tool_args["--profile"], "hr_consultancy_partner")

    def test_email_tool_is_handed_off_not_executed(self) -> None:
        row = {
            "lead_id": "lead-2",
            "company_name": "Acme HR",
            "segment": "HR Consultancy",
            "planned_tool": "send_approved_campaign",
            "planned_tool_args": '{"--limit": "5", "--send": true}',
            "planned_reason": "Approved send worker can process this row.",
        }
        plan = plan_for_contact(row, None, self.tools())
        can_run, reason = should_execute(plan, self.tools()[plan.selected_tool], execute_safe_tools=True)
        self.assertFalse(can_run)
        self.assertEqual(plan.agentic_state, "handoff")
        self.assertEqual(plan.handoff_reason, "email_requires_existing_approval_gate")
        self.assertEqual(reason, "email_requires_existing_approval_gate")

    def test_tool_args_to_argv_handles_flags_and_values(self) -> None:
        argv = tool_args_to_argv({"--checkpoint": True, "--max-pages": "2", "--send": False})
        self.assertEqual(argv, ["--checkpoint", "--max-pages", "2"])


if __name__ == "__main__":
    unittest.main()
