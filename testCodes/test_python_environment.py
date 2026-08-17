import importlib
import importlib.metadata
import json
import sys
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "packaging" / "runtime_manifest.json"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
PYTHON_VERSION_PATH = REPO_ROOT / ".python-version"

EXPECTED_PYTHON_VERSION = "3.12.14"
EXPECTED_UV_VERSION = "0.12.5"
EXPECTED_RUNTIME_PACKAGES = {
    "numpy": "2.5.2",
    "PySide6": "6.11.1",
    "sounddevice": "0.5.6",
}
EXPECTED_DEVELOPMENT_PACKAGES = {
    "PyInstaller": "6.22.1",
}
SAFE_PROJECT_MODULES = (
    "resource_paths",
    "stream_transcribe",
    "settings",
    "model_manager",
    "transcript_store",
    "transcription_engine",
    "transcription_controller",
)


def exact_dependency_map(entries):
    result = {}
    for entry in entries:
        name, separator, version = entry.partition("==")
        if not separator or not name or not version:
            raise AssertionError(f"direct dependency is not exactly pinned: {entry}")
        result[name] = version
    return result


class PythonEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    def test_exact_python_version_matches_contract(self):
        version_file = PYTHON_VERSION_PATH.read_text(encoding="utf-8").strip()
        actual = ".".join(str(part) for part in sys.version_info[:3])
        python_contract = self.manifest["frozen"]["python"]

        self.assertEqual(version_file, EXPECTED_PYTHON_VERSION)
        self.assertEqual(actual, EXPECTED_PYTHON_VERSION)
        self.assertEqual(python_contract["exact_version"], EXPECTED_PYTHON_VERSION)
        self.assertEqual(
            self.pyproject["project"]["requires-python"],
            ">=3.12,<3.13",
        )

    def test_environment_is_project_local_and_uses_managed_python(self):
        expected_venv = (REPO_ROOT / ".venv").resolve()
        old_venv = (REPO_ROOT / "venv").resolve()
        managed_python_root = (REPO_ROOT / ".tools" / "python").resolve()
        actual_prefix = Path(sys.prefix).resolve()
        base_executable = Path(getattr(sys, "_base_executable", sys.executable)).resolve()

        self.assertEqual(actual_prefix, expected_venv)
        self.assertNotEqual(actual_prefix, old_venv)
        self.assertTrue(
            base_executable.is_relative_to(managed_python_root),
            f"base Python is not project-managed: {base_executable}",
        )

    def test_direct_dependencies_match_pyproject_and_manifest(self):
        runtime_from_project = exact_dependency_map(
            self.pyproject["project"]["dependencies"]
        )
        development_from_project = exact_dependency_map(
            self.pyproject["dependency-groups"]["dev"]
        )
        python_contract = self.manifest["frozen"]["python"]

        self.assertEqual(runtime_from_project, EXPECTED_RUNTIME_PACKAGES)
        self.assertEqual(development_from_project, EXPECTED_DEVELOPMENT_PACKAGES)
        self.assertEqual(
            python_contract["direct_dependencies"]["runtime"],
            EXPECTED_RUNTIME_PACKAGES,
        )
        self.assertEqual(
            python_contract["direct_dependencies"]["development"],
            EXPECTED_DEVELOPMENT_PACKAGES,
        )
        self.assertEqual(python_contract["uv_exact_version"], EXPECTED_UV_VERSION)

    def test_required_packages_import_and_report_frozen_versions(self):
        for module_name in ("PySide6", "numpy", "sounddevice", "PyInstaller"):
            with self.subTest(module=module_name):
                importlib.import_module(module_name)

        expected = {**EXPECTED_RUNTIME_PACKAGES, **EXPECTED_DEVELOPMENT_PACKAGES}
        actual = {
            distribution: importlib.metadata.version(distribution)
            for distribution in expected
        }
        self.assertEqual(actual, expected)
        print(
            "Python environment versions: "
            + ", ".join(f"{name}={version}" for name, version in actual.items())
        )

    def test_safe_project_import_surface(self):
        for module_name in SAFE_PROJECT_MODULES:
            with self.subTest(module=module_name):
                importlib.import_module(module_name)


if __name__ == "__main__":
    unittest.main()
