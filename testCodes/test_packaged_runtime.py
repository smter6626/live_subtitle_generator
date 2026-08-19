import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import package_runtime  # noqa: E402
import verify_packaged_runtime as verifier  # noqa: E402


MANIFEST_PATH = REPO_ROOT / "packaging" / "runtime_manifest.json"
RELEASE_SPEC_PATH = REPO_ROOT / "packaging" / "ClassroomTranscriber.spec"
DEBUG_SPEC_PATH = REPO_ROOT / "packaging" / "ClassroomTranscriberDebug.spec"
BUILD_SCRIPT_PATH = REPO_ROOT / "scripts" / "build_macos.sh"


class FakeMacOSTools:
    def __init__(self, *, illegal_dependency=False, smoke_returncode=0, wrong_arch=False):
        self.illegal_dependency = illegal_dependency
        self.smoke_returncode = smoke_returncode
        self.wrong_arch = wrong_arch
        self.calls = []

    def __call__(self, arguments, *, env=None):
        self.calls.append((list(arguments), env))
        command = Path(arguments[0]).name
        target_name = Path(arguments[-1]).name
        if command == "file":
            architecture = "x86_64" if self.wrong_arch else "arm64"
            return subprocess.CompletedProcess(
                arguments,
                0,
                f"{arguments[-1]}: Mach-O 64-bit executable {architecture}\n",
                "",
            )
        if command == "otool" and arguments[1] == "-l":
            return subprocess.CompletedProcess(
                arguments,
                0,
                "Load command 1\n      cmd LC_RPATH\n  cmdsize 40\n"
                "     path @loader_path (offset 12)\n",
                "",
            )
        if command == "otool" and arguments[1] == "-L":
            dependencies = []
            if target_name == "whisper-cli":
                dependencies = [
                    f"@rpath/{component['bundle_filename']}"
                    for component in self.manifest["frozen"]["runtime_components"]
                    if component["kind"] == "dynamic_library"
                ]
                if self.illegal_dependency:
                    dependencies.append(
                        "/private/tmp/external/whisper.cpp/build/libundeclared.dylib"
                    )
            elif target_name.endswith(".dylib"):
                dependencies = [f"@rpath/{target_name}"]
            output = f"{arguments[-1]}:\n" + "".join(
                f"\t{dependency} (compatibility version 0.0.0, current version 1.0.0)\n"
                for dependency in dependencies
            )
            return subprocess.CompletedProcess(arguments, 0, output, "")
        if command in {"sh", "codesign"}:
            return subprocess.CompletedProcess(arguments, 0, "", "")
        if command == "whisper-cli" and arguments[1:] == ["--help"]:
            return subprocess.CompletedProcess(
                arguments, self.smoke_returncode, "fixture help\n", "fixture smoke error\n"
            )
        raise AssertionError(f"unexpected fixture command: {arguments}")


class PackagedRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        FakeMacOSTools.manifest = cls.manifest

    def make_app_fixture(self, root: Path) -> Path:
        app = root / "Fixture.app"
        for component in self.manifest["frozen"]["runtime_components"]:
            path = verifier.component_bundle_path(app, component)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture Mach-O")
            if component["kind"] == "executable":
                path.chmod(0o755)
        for resource in self.manifest["frozen"]["vendored_resources"]:
            path = app.joinpath(*Path(resource["bundle_target"]).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(0o755)
        return app

    def verifier_exit(self, app: Path, fake: FakeMacOSTools) -> int:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(
            io.StringIO()
        ):
            return verifier.main(
                [str(app), "--manifest", str(MANIFEST_PATH)], runner=fake
            )

    def test_manifest_drives_both_specs_without_optional_collection(self):
        source_paths = {
            component["source_path"]
            for component in self.manifest["frozen"]["runtime_components"]
        }
        for spec_path in (RELEASE_SPEC_PATH, DEBUG_SPEC_PATH):
            text = spec_path.read_text(encoding="utf-8")
            with self.subTest(spec=spec_path.name):
                self.assertIn("runtime_manifest.json", text)
                self.assertIn("required_resource", text)
                self.assertNotIn("existing_resource", text)
                self.assertTrue(all(source_path not in text for source_path in source_paths))

    def test_formal_build_orders_preflight_normalize_sign_and_verify_before_success(self):
        text = BUILD_SCRIPT_PATH.read_text(encoding="utf-8")
        markers = (
            "validate-sources",
            "-m PyInstaller",
            "normalize-app",
            "codesign --force --deep --sign -",
            '\n"$PYTHON_BIN" "$PACKAGED_RUNTIME_VERIFIER" "$APP_PATH"\n',
            "Build complete:",
        )
        positions = [text.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("|| true", text)

    def test_missing_required_source_returns_nonzero(self):
        fake = FakeMacOSTools()
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stderr(
            io.StringIO()
        ):
            result = package_runtime.main(
                ["--manifest", str(MANIFEST_PATH), "validate-sources"],
                runner=fake,
                repo_root=Path(temp),
            )
        self.assertNotEqual(result, 0)

    def test_complete_fixture_passes_and_runs_bundle_and_isolation_smokes(self):
        fake = FakeMacOSTools()
        with tempfile.TemporaryDirectory() as temp:
            app = self.make_app_fixture(Path(temp))
            self.assertEqual(self.verifier_exit(app, fake), 0)
        smoke_calls = [
            call for call, _env in fake.calls if Path(call[0]).name == "whisper-cli"
        ]
        self.assertEqual(len(smoke_calls), 2)

    def test_missing_bundled_component_returns_nonzero(self):
        fake = FakeMacOSTools()
        with tempfile.TemporaryDirectory() as temp:
            app = self.make_app_fixture(Path(temp))
            missing = verifier.component_bundle_path(
                app, self.manifest["frozen"]["runtime_components"][1]
            )
            missing.unlink()
            self.assertNotEqual(self.verifier_exit(app, fake), 0)

    def test_illegal_developer_dependency_path_returns_nonzero(self):
        fake = FakeMacOSTools(illegal_dependency=True)
        with tempfile.TemporaryDirectory() as temp:
            app = self.make_app_fixture(Path(temp))
            self.assertNotEqual(self.verifier_exit(app, fake), 0)

    def test_missing_downloader_returns_nonzero(self):
        fake = FakeMacOSTools()
        with tempfile.TemporaryDirectory() as temp:
            app = self.make_app_fixture(Path(temp))
            downloader = app.joinpath(
                *Path(
                    self.manifest["frozen"]["vendored_resources"][0]["bundle_target"]
                ).parts
            )
            downloader.unlink()
            self.assertNotEqual(self.verifier_exit(app, fake), 0)

    def test_packaged_cli_smoke_failure_returns_nonzero(self):
        fake = FakeMacOSTools(smoke_returncode=9)
        with tempfile.TemporaryDirectory() as temp:
            app = self.make_app_fixture(Path(temp))
            self.assertNotEqual(self.verifier_exit(app, fake), 0)

    def test_wrong_architecture_returns_nonzero(self):
        fake = FakeMacOSTools(wrong_arch=True)
        with tempfile.TemporaryDirectory() as temp:
            app = self.make_app_fixture(Path(temp))
            self.assertNotEqual(self.verifier_exit(app, fake), 0)

    def test_packaging_tools_are_standard_library_and_machine_portable(self):
        for path in (
            REPO_ROOT / "scripts" / "package_runtime.py",
            REPO_ROOT / "scripts" / "verify_packaged_runtime.py",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("/" + "Users/", text)
            self.assertNotIn("external/whisper.cpp/build/", text)


if __name__ == "__main__":
    unittest.main()
