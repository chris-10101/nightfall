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

    def project_root_probe_tool(self) -> AgentTool:
        return AgentTool(
            name="project_root_probe",
            description="Checks executor cwd",
            command=[
                sys.executable,
                "-c",
                "from pathlib import Path; import sys; sys.exit(0 if Path('lead-gen/scripts').exists() else 2)",
            ],
            mutates_state=False,
            requires_review=False,
            can_send_email=False,
            allowed_args=set(),
        )


    def python3_probe_tool(self) -> AgentTool:
        return AgentTool(
            name="python3_probe",
            description="Checks interpreter rewrite",
            command=["python3", "-c", "print('ok')"],
            mutates_state=False,
            requires_review=False,
            can_send_email=False,
            allowed_args=set(),
        )

    def test_executes_registry_commands_from_outbound_root(self) -> None:
        original_require_tool = tool_executor.require_tool
        original_orchestration_dir = os.environ.get("VESRA_LEAD_GEN_ORCHESTRATION_DIR")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["VESRA_LEAD_GEN_ORCHESTRATION_DIR"] = temp_dir
            tool_executor.require_tool = lambda name: self.project_root_probe_tool()
            try:
                payload = tool_executor.execute("project_root_probe", [])
            finally:
                tool_executor.require_tool = original_require_tool
                if original_orchestration_dir is None:
                    os.environ.pop("VESRA_LEAD_GEN_ORCHESTRATION_DIR", None)
                else:
                    os.environ["VESRA_LEAD_GEN_ORCHESTRATION_DIR"] = original_orchestration_dir

        self.assertEqual(payload["returncode"], 0)
        self.assertEqual(payload["status"], "ok")


    def test_python3_registry_commands_use_current_interpreter(self) -> None:
        original_require_tool = tool_executor.require_tool
        original_orchestration_dir = os.environ.get("VESRA_LEAD_GEN_ORCHESTRATION_DIR")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["VESRA_LEAD_GEN_ORCHESTRATION_DIR"] = temp_dir
            tool_executor.require_tool = lambda name: self.python3_probe_tool()
            try:
                payload = tool_executor.execute("python3_probe", [])
            finally:
                tool_executor.require_tool = original_require_tool
                if original_orchestration_dir is None:
                    os.environ.pop("VESRA_LEAD_GEN_ORCHESTRATION_DIR", None)
                else:
                    os.environ["VESRA_LEAD_GEN_ORCHESTRATION_DIR"] = original_orchestration_dir

        self.assertEqual(payload["command"][0], sys.executable)
        self.assertEqual(payload["status"], "ok")

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
