import json
import os
import re
import select
import signal
import tempfile
import shutil
import time
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER_PATH = REPO_ROOT / "Build ClassroomTranscriber.command"
ORCHESTRATOR_PATH = REPO_ROOT / "scripts" / "bootstrap_and_build.sh"
RELEASE_BUILD_PATH = REPO_ROOT / "scripts" / "build_macos.sh"
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

    def test_release_build_rejects_a_non_project_python_without_fallback(self):
        text = RELEASE_BUILD_PATH.read_text(encoding="utf-8")
        self.assertIn('FORMAL_PYTHON="$ROOT_DIR/.venv/bin/python"', text)
        self.assertNotIn("PYTHON_CANDIDATES", text)
        self.assertNotIn('PYTHON_BIN="python3"', text)
        result = subprocess.run(
            ["bash", str(RELEASE_BUILD_PATH)],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHON": "/usr/bin/python3"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rejects non-project PYTHON", result.stderr + result.stdout)

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


class ControlledOrchestrationTests(unittest.TestCase):
    def make_entry(self, *, failure=None, active=False):
        root = Path(tempfile.mkdtemp(prefix='shell-checkpoint-', dir=tempfile.gettempdir()))
        scripts = root / 'scripts'
        scripts.mkdir()
        shutil.copy2(ORCHESTRATOR_PATH, scripts / ORCHESTRATOR_PATH.name)
        for name, stage in (('bootstrap_python_env.sh', 'python'),
                            ('bootstrap_whisper_runtime.sh', 'runtime'), ('build_macos.sh', 'app')):
            text = '#!/bin/bash\nset -eu\ncd "$(dirname "$0")/.."\n'
            text += 'printf "' + stage + ':argc=%s:python=%s\\n" "$#" "${PYTHON:-}" >> stages.log\n'
            if active and stage == 'python':
                text += 'touch active-child\nwhile true; do sleep 0.1; done\n'
            if failure == stage:
                text += 'exit 17\n'
            if stage == 'python':
                text += 'mkdir -p .venv/bin\nprintf "#!/bin/bash\\nexit 0\\n" > .venv/bin/python\nchmod 755 .venv/bin/python\n'
            if stage == 'app':
                text += 'mkdir -p dist/ClassroomTranscriber.app/Contents/{MacOS,Resources}\ntouch dist/ClassroomTranscriber.app/Contents/MacOS/ClassroomTranscriber\nchmod 755 dist/ClassroomTranscriber.app/Contents/MacOS/ClassroomTranscriber\n'
            path = scripts / name
            path.write_text(text)
            path.chmod(0o755)
        return root

    def controlled(self, root, *, reply=lambda event: 'allow:' + event, drop_lifetime=False):
        r, w = os.pipe()
        ar, aw = os.pipe()
        lr, lw = os.pipe()
        fds = {r, w, ar, aw, lr, lw}
        events = []
        process = None
        log = root / 'shell.log'
        try:
            with log.open('wb') as output:
                env = {'PATH': '/usr/bin:/bin', 'REL1C_EVENT_FD': str(w),
                       'REL1C_ACK_FD': str(ar), 'REL1C_LIFETIME_FD': str(lr)}
                process = subprocess.Popen(['/bin/bash', str(root / 'scripts/bootstrap_and_build.sh')],
                                           env=env, pass_fds=(w, ar, lr), start_new_session=True,
                                           stdout=output, stderr=subprocess.STDOUT)
                for fd in (w, ar, lr):
                    os.close(fd)
                    fds.remove(fd)
                deadline = time.monotonic() + 8
                pending = b''
                while time.monotonic() < deadline:
                    if select.select([r], [], [], 0.1)[0]:
                        chunk = os.read(r, 128)
                        if not chunk:
                            break
                        pending += chunk
                        while b'\n' in pending:
                            raw, pending = pending.split(b'\n', 1)
                            event = raw.decode()
                            events.append(event)
                            answer = reply(event)
                            if answer is None:
                                os.close(aw)
                                fds.remove(aw)
                            else:
                                os.write(aw, (answer + '\n').encode())
                            if drop_lifetime:
                                # Let the child actually enter its stage before
                                # simulating parent death by lifetime EOF.
                                until = time.monotonic() + 2
                                while not (root / 'active-child').exists() and time.monotonic() < until:
                                    time.sleep(0.01)
                                os.close(lw)
                                fds.remove(lw)
                    if process.poll() is not None:
                        break
                return process.wait(timeout=3), events
        finally:
            for fd in fds:
                os.close(fd)
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()

    def test_six_synchronous_events_preserve_original_argv_order_and_python(self):
        root = self.make_entry()
        code, events = self.controlled(root)
        self.assertEqual(code, 0, (root / 'shell.log').read_text())
        self.assertEqual(events, ['before:python', 'after:python', 'before:runtime',
                                  'after:runtime', 'before:app', 'after:app'])
        self.assertEqual((root / 'stages.log').read_text().splitlines(),
                         ['python:argc=0:python=', 'runtime:argc=0:python=',
                          'app:argc=0:python=' + str(root / '.venv/bin/python')])

    def test_denial_eof_wrong_duplicate_ack_stops_before_child(self):
        for answer in ('deny', None, 'allow:before:runtime', 'allow:before:python\nallow:before:python'):
            root = self.make_entry()
            code, events = self.controlled(root, reply=lambda _, answer=answer: answer)
            self.assertNotEqual(code, 0)
            # A buffered duplicate cannot authorize the next after checkpoint.
            if isinstance(answer, str) and '\n' in answer:
                self.assertEqual((root / 'stages.log').read_text().splitlines(), ['python:argc=0:python='])
            else:
                self.assertFalse((root / 'stages.log').exists())
            self.assertEqual(events[0], 'before:python')
            self.assertNotIn('before:runtime', events)

    def test_child_failure_preserves_exit_and_never_enters_next_stage(self):
        for stage in ('python', 'runtime', 'app'):
            root = self.make_entry(failure=stage)
            code, events = self.controlled(root)
            self.assertEqual(code, 17)
            self.assertNotIn('after:' + stage, events)
            self.assertEqual(events[-1], 'before:' + stage)

    def test_parent_lifetime_eof_stops_active_session(self):
        root = self.make_entry(active=True)
        code, events = self.controlled(root, drop_lifetime=True)
        self.assertNotEqual(code, 0)
        self.assertTrue((root / 'active-child').exists())
        self.assertEqual(events, ['before:python'])

    def test_ordinary_developer_invocation_still_runs_original_three_children(self):
        root = self.make_entry()
        result = subprocess.run(['/bin/bash', str(root / 'scripts/bootstrap_and_build.sh')],
                                env={'PATH': '/usr/bin:/bin'}, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len((root / 'stages.log').read_text().splitlines()), 3)


if __name__ == "__main__":
    unittest.main()
