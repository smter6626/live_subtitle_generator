import json
import os
import re
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER_PATH = REPO_ROOT / "Build ClassroomTranscriber.command"
ORCHESTRATOR_PATH = REPO_ROOT / "scripts" / "bootstrap_and_build.sh"
MANIFEST_PATH = REPO_ROOT / "packaging" / "runtime_manifest.json"


class BuildOrchestrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wrapper_text = WRAPPER_PATH.read_text(encoding="utf-8")
        cls.orchestrator_text = ORCHESTRATOR_PATH.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.build_entry = cls.manifest["frozen"]["developer_build_entry"]

    def test_entry_scripts_exist_are_executable_and_have_valid_shell_syntax(self):
        for script in (WRAPPER_PATH, ORCHESTRATOR_PATH):
            with self.subTest(script=script.name):
                self.assertTrue(script.is_file())
                self.assertTrue(os.access(script, os.X_OK))
                result = subprocess.run(
                    ["bash", "-n", str(script)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_finder_entry_is_a_thin_exec_wrapper(self):
        meaningful_lines = [
            line
            for line in self.wrapper_text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertLessEqual(len(meaningful_lines), 5)
        self.assertIn('exec "$ROOT_DIR/scripts/bootstrap_and_build.sh" "$@"', self.wrapper_text)
        for forbidden_detail in (
            "bootstrap_python_env.sh",
            "bootstrap_whisper_runtime.sh",
            "build_macos.sh",
            "PyInstaller",
            "whisper.cpp",
        ):
            self.assertNotIn(forbidden_detail, self.wrapper_text)

    def test_orchestrator_calls_formal_stages_in_order(self):
        stage_calls = (
            '\n"$PYTHON_BOOTSTRAP"\n',
            '\n"$WHISPER_BOOTSTRAP"\n',
            '\nPYTHON="$FORMAL_PYTHON" "$RELEASE_BUILD"\n',
        )
        positions = [self.orchestrator_text.index(call) for call in stage_calls]
        self.assertEqual(positions, sorted(positions))

    def test_orchestrator_uses_only_the_formal_python_for_release_build(self):
        self.assertIn(
            'FORMAL_PYTHON="$ROOT_DIR/.venv/bin/python"',
            self.orchestrator_text,
        )
        self.assertIn(
            'PYTHON="$FORMAL_PYTHON" "$RELEASE_BUILD"',
            self.orchestrator_text,
        )
        self.assertIsNone(
            re.search(r'(?<!\.)/venv/bin/python', self.orchestrator_text)
        )
        self.assertNotIn("CONDA_PREFIX", self.orchestrator_text)
        self.assertNotIn("brew", self.orchestrator_text.lower())

    def test_orchestrator_checks_the_expected_app_without_step_6_gates(self):
        self.assertIn(
            'APP_PATH="$ROOT_DIR/dist/ClassroomTranscriber.app"',
            self.orchestrator_text,
        )
        self.assertIn("Contents/MacOS/ClassroomTranscriber", self.orchestrator_text)
        for step_6_detail in ("otool", "install_name_tool", "codesign"):
            self.assertNotIn(step_6_detail, self.orchestrator_text)

    def test_manifest_build_entry_matches_repository_files(self):
        expected = {
            "finder_wrapper_path": "Build ClassroomTranscriber.command",
            "implementation_path": "scripts/bootstrap_and_build.sh",
            "python_bootstrap_path": "scripts/bootstrap_python_env.sh",
            "whisper_runtime_bootstrap_path": "scripts/bootstrap_whisper_runtime.sh",
            "formal_python_path": ".venv/bin/python",
            "release_build_script_path": "scripts/build_macos.sh",
            "expected_app_path": "dist/ClassroomTranscriber.app",
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(self.build_entry[key], value)
        for tracked_path_key in (
            "finder_wrapper_path",
            "implementation_path",
            "python_bootstrap_path",
            "whisper_runtime_bootstrap_path",
            "release_build_script_path",
        ):
            self.assertTrue((REPO_ROOT / self.build_entry[tracked_path_key]).is_file())
        self.assertEqual(self.build_entry["implementation_status"], "implemented")

    def test_entry_scripts_are_repo_relative_and_machine_portable(self):
        for script_text in (self.wrapper_text, self.orchestrator_text):
            self.assertNotIn("/" + "Users/", script_text)
            self.assertIn("BASH_SOURCE[0]", script_text)


if __name__ == "__main__":
    unittest.main()
