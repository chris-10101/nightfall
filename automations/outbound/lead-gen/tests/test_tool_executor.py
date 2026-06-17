import os
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from orchestration import tool_executor
from orchestration.tool_registry import AgentTool


class ToolExecutorTest(unittest.TestCase):
    def failing_tool(self) -> AgentTool:
        return AgentTool(
            name="failing_tool",
            description="Intentional failure",
            command=[sys.executable, "-c", "import sys; sys.exit(2)"],
            mutates_state=False,
            requires_review=False,
            can_send_email=False,
            allowed_args=set(),
        )

    def test_can_capture_failed_tool_without_exiting(self) -> None:
        original_require_tool = tool_executor.require_tool
        original_orchestration_dir = os.environ.get("VESRA_LEAD_GEN_ORCHESTRATION_DIR")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["VESRA_LEAD_GEN_ORCHESTRATION_DIR"] = temp_dir
            tool_executor.require_tool = lambda name: self.failing_tool()
            try:
                payload = tool_executor.execute("failing_tool", [], raise_on_failure=False)
            finally:
                tool_executor.require_tool = original_require_tool
                if original_orchestration_dir is None:
                    os.environ.pop("VESRA_LEAD_GEN_ORCHESTRATION_DIR", None)
                else:
                    os.environ["VESRA_LEAD_GEN_ORCHESTRATION_DIR"] = original_orchestration_dir

        self.assertEqual(payload["returncode"], 2)
        self.assertEqual(payload["status"], "failed")

    def test_default_failed_tool_still_exits(self) -> None:
        original_require_tool = tool_executor.require_tool
        original_orchestration_dir = os.environ.get("VESRA_LEAD_GEN_ORCHESTRATION_DIR")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["VESRA_LEAD_GEN_ORCHESTRATION_DIR"] = temp_dir
            tool_executor.require_tool = lambda name: self.failing_tool()
            try:
                with self.assertRaises(SystemExit):
                    tool_executor.execute("failing_tool", [])
            finally:
                tool_executor.require_tool = original_require_tool
                if original_orchestration_dir is None:
                    os.environ.pop("VESRA_LEAD_GEN_ORCHESTRATION_DIR", None)
                else:
                    os.environ["VESRA_LEAD_GEN_ORCHESTRATION_DIR"] = original_orchestration_dir


if __name__ == "__main__":
    unittest.main()
