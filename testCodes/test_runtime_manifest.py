import json
import re
import unittest
from pathlib import Path, PurePosixPath


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "packaging" / "runtime_manifest.json"
PINNED_WHISPER_CPP_COMMIT = "8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae"
REQUIRED_COMPONENTS = {
    "whisper-cli",
    "libwhisper",
    "libggml",
    "libggml-base",
    "libggml-cpu",
    "libggml-blas",
    "libggml-metal",
}


def walk_items(value, key_path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_items(child, key_path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_items(child, key_path + (str(index),))
    else:
        yield key_path, value


class RuntimeManifestContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_manifest = MANIFEST_PATH.read_text(encoding="utf-8")
        cls.manifest = json.loads(cls.raw_manifest)

    def test_manifest_is_valid_json_with_schema_version(self):
        self.assertIsInstance(self.manifest, dict)
        self.assertIsInstance(self.manifest.get("schema_version"), str)
        self.assertTrue(self.manifest["schema_version"].strip())

    def test_frozen_observed_pending_are_distinct(self):
        for section in ("frozen", "observed", "pending"):
            self.assertIn(section, self.manifest)
            self.assertIsInstance(self.manifest[section], dict)
        self.assertEqual(self.manifest.get("status"), "contract-only")

    def test_platform_is_macos_arm64(self):
        platform = self.manifest["frozen"]["platform"]
        self.assertEqual(platform["os"], "macOS")
        self.assertEqual(platform["architecture"], "arm64")
        self.assertEqual(platform["distribution"], "Apple Silicon")

    def test_whisper_cpp_upstream_is_pinned(self):
        whisper_cpp = self.manifest["frozen"]["whisper_cpp"]
        self.assertEqual(
            whisper_cpp["repository"],
            "https://github.com/ggml-org/whisper.cpp.git",
        )
        self.assertEqual(whisper_cpp["commit"], PINNED_WHISPER_CPP_COMMIT)
        self.assertRegex(whisper_cpp["commit"], re.compile(r"^[0-9a-f]{40}$"))

    def test_all_required_runtime_components_are_frozen(self):
        components = self.manifest["frozen"]["runtime_components"]
        names = {component["name"] for component in components}
        self.assertEqual(names, REQUIRED_COMPONENTS)
        self.assertTrue(all(component["required"] for component in components))

    def test_vendored_downloader_path_and_file(self):
        resources = self.manifest["frozen"]["vendored_resources"]
        self.assertEqual(len(resources), 1)
        resource = resources[0]
        expected_path = "vendor/whisper.cpp/download-ggml-model.sh"
        self.assertEqual(resource["repository_path"], expected_path)
        self.assertEqual(resource["upstream_commit"], PINNED_WHISPER_CPP_COMMIT)
        self.assertTrue((REPO_ROOT / expected_path).is_file())

    def test_all_manifest_paths_are_relative_and_portable(self):
        for key_path, value in walk_items(self.manifest):
            if not isinstance(value, str):
                continue
            key = key_path[-1].lower()
            if "path" not in key and key not in {
                "bundle_directory",
                "dynamic_library_directory",
                "bundle_target",
                "whisper_cli_target",
                "model_downloader_target",
            }:
                continue
            with self.subTest(key_path=".".join(key_path), value=value):
                path = PurePosixPath(value)
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
                self.assertFalse(value.startswith("~"))
                self.assertNotIn("\\", value)

    def test_manifest_contains_no_sensitive_or_machine_specific_values(self):
        self.assertNotIn("/Users/", self.raw_manifest)
        self.assertNotIn("CMakeCache", self.raw_manifest)
        self.assertNotRegex(
            self.raw_manifest.lower(),
            re.compile(r"api[ _-]?key|secret"),
        )
        self.assertNotRegex(
            self.raw_manifest.lower(),
            re.compile(r"(?:^|[\"/])[^\"/]+\.(?:bin|gguf)(?:[\"/]|$)"),
        )

    def test_minimum_macos_remains_pending(self):
        self.assertNotIn("minimum_macos", self.manifest["frozen"]["platform"])
        minimum_macos = self.manifest["pending"]["minimum_macos"]
        self.assertIsNone(minimum_macos["value"])

    def test_python_exact_version_and_packages_remain_pending(self):
        python_contract = self.manifest["frozen"]["python"]
        self.assertEqual(python_contract["minimum_version"], ">=3.11")
        self.assertNotIn("exact_version", python_contract)
        self.assertIsNone(
            self.manifest["pending"]["python_exact_minor_patch"]["value"]
        )
        package_versions = self.manifest["pending"][
            "python_package_exact_versions"
        ]
        for package in ("PySide6", "PyInstaller", "numpy", "sounddevice"):
            self.assertIn(package, package_versions)
            self.assertIsNone(package_versions[package])

    def test_hardware_claims_do_not_overstate_verification(self):
        hardware = self.manifest["observed"]["hardware_validation_targets"]
        chips = {target["chip"] for target in hardware}
        self.assertEqual(chips, {"Apple M5", "Apple M4 Max"})
        self.assertTrue(
            all(
                target["deployment_validation_status"]
                == "pending_clean_machine_e2e"
                for target in hardware
            )
        )

        compatibility = self.manifest["frozen"]["compatibility"]
        for generation in ("M1", "M2", "M3"):
            self.assertEqual(
                compatibility[generation]["current_verification_status"],
                "theoretical_unverified",
            )
            self.assertFalse(compatibility[generation]["guaranteed"])
        for generation in ("M4", "M5"):
            self.assertEqual(
                compatibility[generation]["current_verification_status"],
                "pending_clean_machine_e2e",
            )

    def test_models_are_not_bundled_runtime_components(self):
        components = self.manifest["frozen"]["runtime_components"]
        self.assertTrue(
            all("model" not in component["name"].lower() for component in components)
        )
        self.assertNotIn("models", self.manifest["frozen"])

    def test_frozen_build_profile_matches_old_machine_contract(self):
        profile = self.manifest["frozen"]["whisper_cpp"]["build_profile"]
        options = profile["cmake_options"]
        self.assertEqual(profile["cmake_generator"], "Unix Makefiles")
        self.assertEqual(profile["cmake_version"], "4.2.3")
        self.assertEqual(profile["build_type"], "Release")
        self.assertEqual(profile["target_architecture"], "arm64")
        for option in (
            "BUILD_SHARED_LIBS",
            "GGML_ACCELERATE",
            "GGML_BLAS",
            "GGML_METAL",
            "GGML_NATIVE",
        ):
            self.assertIs(options[option], True)
        self.assertEqual(options["GGML_BLAS_VENDOR"], "Apple")

    def test_observed_runtime_artifacts_cover_frozen_components(self):
        artifacts = self.manifest["observed"]["old_machine_whisper_cpp_build"][
            "runtime_artifacts"
        ]
        self.assertEqual(
            {artifact["component"] for artifact in artifacts},
            REQUIRED_COMPONENTS,
        )
        self.assertTrue(
            all(artifact["architecture"] == "arm64" for artifact in artifacts)
        )
        observed_filenames = {
            artifact["component"]: artifact.get(
                "abi_filename", artifact.get("observed_filename")
            )
            for artifact in artifacts
        }
        self.assertEqual(
            observed_filenames,
            {
                "whisper-cli": "whisper-cli",
                "libwhisper": "libwhisper.1.dylib",
                "libggml": "libggml.0.dylib",
                "libggml-base": "libggml-base.0.dylib",
                "libggml-cpu": "libggml-cpu.0.dylib",
                "libggml-blas": "libggml-blas.0.dylib",
                "libggml-metal": "libggml-metal.0.dylib",
            },
        )


if __name__ == "__main__":
    unittest.main()
