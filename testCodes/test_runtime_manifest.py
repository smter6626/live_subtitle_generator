import hashlib
import json
import re
import tomllib
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
        cls.pyproject = tomllib.loads(
            (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )

    def test_manifest_is_valid_json_with_schema_version(self):
        self.assertIsInstance(self.manifest, dict)
        self.assertIsInstance(self.manifest.get("schema_version"), str)
        self.assertTrue(self.manifest["schema_version"].strip())

    def test_frozen_observed_pending_are_distinct(self):
        for section in ("frozen", "observed", "pending"):
            self.assertIn(section, self.manifest)
            self.assertIsInstance(self.manifest[section], dict)
        self.assertEqual(
            self.manifest.get("status"), "model-download-integrity-gated"
        )

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

    def test_model_integrity_contract_is_separate_and_packaged(self):
        model_integrity = self.manifest["frozen"]["model_integrity"]
        self.assertEqual(
            model_integrity["manifest_repository_path"],
            "packaging/model_manifest.json",
        )
        self.assertEqual(
            model_integrity["manifest_bundle_target"],
            "Contents/Resources/model_manifest.json",
        )
        self.assertTrue(model_integrity["required_packaged_resource"])
        self.assertFalse(model_integrity["model_binaries_are_runtime_components"])
        self.assertTrue(
            (REPO_ROOT / model_integrity["manifest_repository_path"]).is_file()
        )
        self.assertNotIn(
            "model_checksum_and_model_manifest_strategy",
            self.manifest["pending"],
        )

    def test_app_icon_contract_is_tracked_reproducible_and_packaged(self):
        app_icon = self.manifest["frozen"]["app_icon"]
        self.assertTrue(app_icon["required"])
        self.assertEqual(app_icon["minimum_source_pixels"], 1024)
        self.assertEqual(app_icon["bundle_filename"], "ClassroomTranscriber.icns")
        self.assertEqual(
            app_icon["bundle_target"],
            "Contents/Resources/ClassroomTranscriber.icns",
        )
        source_path = REPO_ROOT / app_icon["source_path"]
        self.assertTrue(source_path.is_file())
        self.assertEqual(
            hashlib.sha256(source_path.read_bytes()).hexdigest(),
            app_icon["source_sha256"],
        )
        self.assertTrue((REPO_ROOT / app_icon["generation_script_path"]).is_file())

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

    def test_python_toolchain_and_direct_packages_are_frozen(self):
        python_contract = self.manifest["frozen"]["python"]
        self.assertEqual(python_contract["minimum_version"], ">=3.11")
        self.assertEqual(python_contract["exact_version"], EXPECTED_PYTHON_VERSION)
        self.assertEqual(python_contract["uv_exact_version"], EXPECTED_UV_VERSION)
        self.assertEqual(
            python_contract["direct_dependencies"]["runtime"],
            EXPECTED_RUNTIME_PACKAGES,
        )
        self.assertEqual(
            python_contract["direct_dependencies"]["development"],
            EXPECTED_DEVELOPMENT_PACKAGES,
        )

        for completed_key in (
            "python_exact_minor_patch",
            "python_package_exact_versions",
            "uv_exact_version_and_lock_update_policy",
        ):
            self.assertNotIn(completed_key, self.manifest["pending"])

    def test_python_contract_matches_repository_declarations(self):
        python_contract = self.manifest["frozen"]["python"]
        version_file = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()
        self.assertEqual(version_file, EXPECTED_PYTHON_VERSION)
        self.assertEqual(
            self.pyproject["project"]["requires-python"],
            python_contract["requires_python"],
        )
        self.assertEqual(
            set(self.pyproject["project"]["dependencies"]),
            {
                f"{name}=={version}"
                for name, version in EXPECTED_RUNTIME_PACKAGES.items()
            },
        )
        self.assertEqual(
            set(self.pyproject["dependency-groups"]["dev"]),
            {
                f"{name}=={version}"
                for name, version in EXPECTED_DEVELOPMENT_PACKAGES.items()
            },
        )
        self.assertEqual(python_contract["sync_policy"], "uv sync --frozen")
        self.assertEqual(
            python_contract["bootstrap_script_path"],
            "scripts/bootstrap_python_env.sh",
        )
        self.assertTrue((REPO_ROOT / python_contract["bootstrap_script_path"]).is_file())

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
        self.assertEqual(options["CMAKE_OSX_ARCHITECTURES"], "arm64")
        for option in (
            "BUILD_SHARED_LIBS",
            "GGML_ACCELERATE",
            "GGML_BLAS",
            "GGML_METAL",
            "GGML_NATIVE",
        ):
            self.assertIs(options[option], True)
        self.assertIs(options["GGML_OPENMP"], False)
        self.assertEqual(options["GGML_BLAS_VENDOR"], "Apple")

        observed = self.manifest["observed"]["old_machine_whisper_cpp_build"]
        self.assertIs(observed["cmake_cache_requested_openmp"], True)
        self.assertIs(observed["effective_openmp_enabled"], False)

    def test_cmake_bootstrap_tool_is_frozen(self):
        cmake = self.manifest["frozen"]["cmake"]
        self.assertEqual(cmake["exact_version"], "4.2.3")
        self.assertRegex(
            cmake["acquisition"]["asset_sha256"],
            re.compile(r"^[0-9a-f]{64}$"),
        )
        self.assertEqual(
            cmake["binary_path"],
            ".tools/cmake/4.2.3/CMake.app/Contents/bin/cmake",
        )
        self.assertFalse(cmake["system_fallback_allowed"])
        self.assertNotIn("cmake_acquisition_method", self.manifest["pending"])

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
        formal_source_paths = {
            component["name"]: component["source_path"]
            for component in self.manifest["frozen"]["runtime_components"]
        }
        self.assertEqual(
            formal_source_paths,
            {
                artifact["component"]: artifact["source_path"]
                for artifact in artifacts
            },
        )

    def test_packaged_runtime_gate_is_frozen_and_manifest_driven(self):
        packaged = self.manifest["frozen"]["packaged_runtime"]
        self.assertEqual(packaged["runtime_rpath"], "@loader_path")
        self.assertEqual(
            packaged["allowed_system_dependency_prefixes"],
            ["/usr/lib/", "/System/Library/"],
        )
        self.assertTrue(packaged["isolated_runtime_smoke_required"])
        self.assertFalse(packaged["source_tree_dependency_allowed"])
        self.assertTrue(
            packaged["ad_hoc_codesign"]["required_after_runtime_normalization"]
        )
        self.assertFalse(packaged["ad_hoc_codesign"]["developer_id_required"])
        for path_key in ("packaging_helper_path", "verifier_path"):
            path = REPO_ROOT / packaged[path_key]
            self.assertTrue(path.is_file())

        components = self.manifest["frozen"]["runtime_components"]
        self.assertEqual(
            {component["bundle_filename"] for component in components},
            {
                "whisper-cli",
                "libwhisper.1.dylib",
                "libggml.0.dylib",
                "libggml-base.0.dylib",
                "libggml-cpu.0.dylib",
                "libggml-blas.0.dylib",
                "libggml-metal.0.dylib",
            },
        )


if __name__ == "__main__":
    unittest.main()
