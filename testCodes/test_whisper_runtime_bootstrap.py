import json
import re
import stat
import subprocess
import sys
import unittest
from pathlib import Path, PurePosixPath


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "packaging" / "runtime_manifest.json"
BOOTSTRAP_PATH = REPO_ROOT / "scripts" / "bootstrap_whisper_runtime.sh"
HELPER_PATH = REPO_ROOT / "scripts" / "whisper_runtime_contract.py"
PINNED_COMMIT = "8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae"
REQUIRED_COMPONENTS = {
    "whisper-cli",
    "libwhisper",
    "libggml",
    "libggml-base",
    "libggml-cpu",
    "libggml-blas",
    "libggml-metal",
}


def cmake_value(value):
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    return str(value)


class WhisperRuntimeBootstrapContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_manifest = MANIFEST_PATH.read_text(encoding="utf-8")
        cls.manifest = json.loads(cls.raw_manifest)
        cls.bootstrap_source = BOOTSTRAP_PATH.read_text(encoding="utf-8")
        cls.helper_source = HELPER_PATH.read_text(encoding="utf-8")

    def test_cmake_acquisition_is_exact_official_and_frozen(self):
        cmake = self.manifest["frozen"]["cmake"]
        acquisition = cmake["acquisition"]
        self.assertEqual(cmake["exact_version"], "4.2.3")
        self.assertEqual(acquisition["asset"], "cmake-4.2.3-macos-universal.tar.gz")
        self.assertEqual(
            acquisition["official_release_url"],
            "https://github.com/Kitware/CMake/releases/tag/v4.2.3",
        )
        self.assertTrue(acquisition["asset_url"].startswith("https://github.com/Kitware/CMake/"))
        self.assertTrue(
            acquisition["checksum_source_url"].startswith(
                "https://github.com/Kitware/CMake/"
            )
        )
        self.assertRegex(acquisition["asset_sha256"], re.compile(r"^[0-9a-f]{64}$"))
        self.assertFalse(cmake["system_fallback_allowed"])
        self.assertNotIn("cmake_acquisition_method", self.manifest["pending"])

    def test_cmake_paths_are_project_relative(self):
        cmake = self.manifest["frozen"]["cmake"]
        for field in ("project_local_install_root_path", "binary_path"):
            value = cmake[field]
            path = PurePosixPath(value)
            self.assertFalse(path.is_absolute())
            self.assertNotIn("..", path.parts)
            self.assertTrue(value.startswith(".tools/cmake/4.2.3"))
        self.assertNotIn("/Users/", self.raw_manifest)

    def test_formal_build_profile_is_reproducible(self):
        whisper = self.manifest["frozen"]["whisper_cpp"]
        profile = whisper["build_profile"]
        options = profile["cmake_options"]
        self.assertEqual(whisper["repository"], "https://github.com/ggml-org/whisper.cpp.git")
        self.assertEqual(whisper["commit"], PINNED_COMMIT)
        self.assertEqual(profile["cmake_version"], "4.2.3")
        self.assertEqual(profile["cmake_generator"], "Unix Makefiles")
        self.assertEqual(profile["build_type"], "Release")
        self.assertEqual(profile["target_architecture"], "arm64")
        self.assertEqual(options["CMAKE_OSX_ARCHITECTURES"], "arm64")
        self.assertIs(options["GGML_OPENMP"], False)
        self.assertIs(options["GGML_NATIVE"], True)
        self.assertEqual(profile["build_target"], "whisper-cli")
        self.assertIn("--fresh", profile["fresh_configuration_policy"])

    def test_old_openmp_evidence_is_preserved(self):
        observed = self.manifest["observed"]["old_machine_whisper_cpp_build"]
        self.assertIs(observed["cmake_cache_requested_openmp"], True)
        self.assertIs(observed["effective_openmp_enabled"], False)
        self.assertIs(
            self.manifest["frozen"]["whisper_cpp"]["build_profile"][
                "cmake_options"
            ]["GGML_OPENMP"],
            False,
        )

    def test_runtime_components_and_smoke_contract_are_complete(self):
        frozen = self.manifest["frozen"]
        components = frozen["runtime_components"]
        self.assertEqual({item["name"] for item in components}, REQUIRED_COMPONENTS)
        for component in components:
            self.assertTrue(component["required"])
            path = PurePosixPath(component["source_path"])
            self.assertFalse(path.is_absolute())
            self.assertNotIn("..", path.parts)
            if component["kind"] == "dynamic_library":
                self.assertRegex(component["abi_filename"], r"\.dylib$")
        smoke = frozen["whisper_cpp"]["minimal_runtime_smoke"]
        self.assertEqual(smoke["component"], "whisper-cli")
        self.assertEqual(smoke["arguments"], ["--help"])
        self.assertEqual(smoke["expected_exit_code"], 0)
        self.assertFalse(smoke["requires_model"])
        self.assertFalse(smoke["requires_audio"])

    def test_bootstrap_and_helper_are_present(self):
        whisper = self.manifest["frozen"]["whisper_cpp"]
        self.assertEqual(
            whisper["bootstrap_script_path"],
            "scripts/bootstrap_whisper_runtime.sh",
        )
        self.assertEqual(
            whisper["contract_helper_path"],
            "scripts/whisper_runtime_contract.py",
        )
        self.assertTrue(BOOTSTRAP_PATH.is_file())
        self.assertTrue(HELPER_PATH.is_file())
        self.assertTrue(BOOTSTRAP_PATH.stat().st_mode & stat.S_IXUSR)
        self.assertIn("--verify-only", self.bootstrap_source)
        self.assertIn("--fresh", self.bootstrap_source)
        self.assertIn("--clean-first", self.bootstrap_source)

    def test_bootstrap_consumes_manifest_profile_without_flag_copy(self):
        self.assertIn("whisper_runtime_contract.py", self.bootstrap_source)
        self.assertIn("cmake-arguments", self.bootstrap_source)
        self.assertNotIn("-DGGML_", self.bootstrap_source)
        self.assertNotIn(PINNED_COMMIT, self.bootstrap_source)
        self.assertNotIn("cmake-4.2.3-macos-universal", self.bootstrap_source)
        self.assertIn("runtime_manifest.json", self.helper_source)

        result = subprocess.run(
            [sys.executable, str(HELPER_PATH), "cmake-arguments"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        emitted = result.stdout.splitlines()
        profile = self.manifest["frozen"]["whisper_cpp"]["build_profile"]
        expected = [f"-DCMAKE_BUILD_TYPE={profile['build_type']}"]
        expected.extend(
            f"-D{name}={cmake_value(value)}"
            for name, value in profile["cmake_options"].items()
        )
        self.assertEqual(emitted, expected)

    def test_helper_emits_manifest_artifact_records(self):
        result = subprocess.run(
            [sys.executable, str(HELPER_PATH), "artifact-records"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        emitted = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(emitted, self.manifest["frozen"]["runtime_components"])


if __name__ == "__main__":
    unittest.main()
