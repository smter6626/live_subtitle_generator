import copy
import json
import plistlib
import shutil
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import release_identity  # noqa: E402


MANIFEST_PATH = REPO_ROOT / "packaging" / "runtime_manifest.json"
EXPECTED_LOCKED_PACKAGES = {
    "altgraph": "0.17.5",
    "cffi": "2.1.1",
    "classroom-live-transcriber": "1.1.0",
    "macholib": "1.16.4",
    "numpy": "2.5.2",
    "packaging": "26.3",
    "pefile": "2024.8.26",
    "pycparser": "3.0",
    "pyinstaller": "6.22.1",
    "pyinstaller-hooks-contrib": "2026.6",
    "pyside6": "6.11.1",
    "pyside6-addons": "6.11.1",
    "pyside6-essentials": "6.11.1",
    "pywin32-ctypes": "0.2.3",
    "setuptools": "84.0.0",
    "shiboken6": "6.11.1",
    "sounddevice": "0.5.6",
}


class ReleaseIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_corrected_candidate_notes_have_fixed_reviewed_hash(self):
        expected = "69013bcae2de876202b3c6d2633fcb75a659b1f5f413cd905295eb6431a12703"
        self.assertEqual(release_identity.EXPECTED_CONTRACT["release_notes_sha256"], expected)
        self.assertEqual(release_identity.load_contract()["release_notes_sha256"], expected)
        self.assertEqual(release_identity.sha256_file(REPO_ROOT / "RELEASE_NOTES_1.1.0.md"), expected)
        text = (REPO_ROOT / "RELEASE_NOTES_1.1.0.md").read_text(encoding="utf-8")
        self.assertNotIn("remain pending", text)
        self.assertNotIn("These candidate bytes have not been built", text)
        self.assertIn("Every published 1.1.0 artifact must be bound", text)
        self.assertIn("not evidence that any particular ZIP", text)

    def make_app(self, root: Path) -> Path:
        app = root / "ClassroomTranscriber.app"
        executable = app / "Contents" / "MacOS" / "ClassroomTranscriber"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"fixture executable\n")
        executable.chmod(0o755)
        with (app / "Contents" / "Info.plist").open("wb") as handle:
            plistlib.dump(
                {
                    "CFBundleShortVersionString": "1.1.0",
                    "CFBundleVersion": "1.1.0",
                },
                handle,
            )
        return app

    def copy_identity_repo(self, root: Path) -> Path:
        for relative in (
            "pyproject.toml",
            "uv.lock",
            "RELEASE_NOTES_1.1.0.md",
            "packaging/release_contract.json",
            *release_identity.REQUIRED_TOOL_PATHS,
        ):
            source = REPO_ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return root

    def test_project_lock_spec_notes_asset_and_dependency_identity_agree(self):
        contract = release_identity.load_contract()
        self.assertIn(
            release_identity.validate_repository_identity(REPO_ROOT),
            contract["canonical_origins"],
        )
        self.assertEqual(release_identity.project_versions(REPO_ROOT), ("1.1.0", "1.1.0"))
        self.assertEqual(self.manifest["schema_version"], "1.0.0")
        self.assertEqual(
            self.manifest["frozen"]["release"]["artifact_name_template"].replace(
                "<version>", contract["product_version"]
            ),
            contract["asset_name"],
        )
        self.assertEqual(
            self.manifest["frozen"]["release"]["primary_payload"],
            contract["app_name"],
        )
        self.assertEqual(
            release_identity.sha256_file(REPO_ROOT / contract["release_notes_path"]),
            contract["release_notes_sha256"],
        )
        spec = (REPO_ROOT / "packaging/ClassroomTranscriber.spec").read_text(
            encoding="utf-8"
        )
        self.assertIn('"CFBundleShortVersionString": "1.1.0"', spec)
        self.assertIn('"CFBundleVersion": "1.1.0"', spec)
        lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
        self.assertEqual(
            {package["name"]: package["version"] for package in lock["package"]},
            EXPECTED_LOCKED_PACKAGES,
        )

    def test_wrong_release_fields_app_versions_and_notes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root / "app")
            base = {
                "repo_root": REPO_ROOT,
                "app_path": app,
                "manifest": self.manifest,
                "version": "1.1.0",
                "tag": "1.1.0",
                "title": "Classroom Transcriber 1.1.0",
                "asset_name": "ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip",
                "notes_path": REPO_ROOT / "RELEASE_NOTES_1.1.0.md",
            }
            for key, wrong in (
                ("version", "1.0.0"),
                ("tag", "v1.1.0"),
                ("title", "wrong"),
                ("asset_name", "wrong.zip"),
                ("notes_path", root / "wrong.md"),
            ):
                with self.subTest(key=key), self.assertRaises(release_identity.IdentityError):
                    release_identity.validate_release_identity(**{**base, key: wrong})
            plist_path = app / "Contents" / "Info.plist"
            with plist_path.open("rb") as handle:
                info = plistlib.load(handle)
            info["CFBundleVersion"] = "1.0.0"
            with plist_path.open("wb") as handle:
                plistlib.dump(info, handle)
            with self.assertRaises(release_identity.IdentityError):
                release_identity.validate_release_identity(**base)

            copied_repo = self.copy_identity_repo(root / "copied-repo")
            copied_notes = copied_repo / "RELEASE_NOTES_1.1.0.md"
            copied_notes.write_text(copied_notes.read_text() + "edited\n")
            with self.assertRaises(release_identity.IdentityError):
                release_identity.validate_release_identity(
                    **{
                        **base,
                        "repo_root": copied_repo,
                        "app_path": None,
                        "notes_path": copied_notes,
                    }
                )

    def test_runtime_manifest_must_equal_tracked_canonical_object(self):
        weakened = copy.deepcopy(self.manifest)
        weakened["frozen"]["packaged_runtime"][
            "allowed_system_dependency_prefixes"
        ] = ["/"]
        with self.assertRaises(release_identity.IdentityError):
            release_identity.validate_runtime_manifest(weakened)
        self.assertEqual(
            release_identity.validate_runtime_manifest(self.manifest), self.manifest
        )

    def test_provenance_binds_complete_app_contract_source_and_required_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root / "app")
            provenance = root / "provenance.json"
            value = release_identity.write_build_provenance(
                provenance, app, "a" * 40
            )
            self.assertEqual(
                set(value["required_tool_sha256"]),
                set(release_identity.REQUIRED_TOOL_PATHS),
            )
            self.assertIn(
                "packaging/runtime_manifest.json", value["required_tool_sha256"]
            )
            self.assertEqual(
                release_identity.validate_build_provenance(
                    provenance, app, "a" * 40
                ),
                value,
            )
            with self.assertRaises(release_identity.IdentityError):
                release_identity.write_build_provenance(provenance, app, "a" * 40)

            original = provenance.read_bytes()
            for mutation in ("missing", "extra", "wrong-tools", "stale-source"):
                changed = json.loads(original)
                if mutation == "missing":
                    del changed["app_name"]
                elif mutation == "extra":
                    changed["unexpected"] = True
                elif mutation == "wrong-tools":
                    changed["required_tool_sha256"] = {}
                else:
                    changed["source_commit"] = "b" * 40
                provenance.write_bytes(release_identity.canonical_json(changed))
                with self.subTest(mutation=mutation), self.assertRaises(
                    release_identity.IdentityError
                ):
                    release_identity.validate_build_provenance(
                        provenance, app, "a" * 40
                    )
            provenance.write_bytes(original)
            app.joinpath("Contents/MacOS/ClassroomTranscriber").write_bytes(b"changed")
            with self.assertRaises(release_identity.IdentityError):
                release_identity.validate_build_provenance(provenance, app, "a" * 40)

    def test_provenance_rejects_changed_contract_or_required_tool(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.copy_identity_repo(Path(temp) / "repo")
            app = self.make_app(Path(temp) / "app")
            provenance = Path(temp) / "provenance.json"
            release_identity.write_build_provenance(
                provenance, app, "c" * 40, repo_root=root
            )
            tool = root / release_identity.REQUIRED_TOOL_PATHS[0]
            tool.write_bytes(tool.read_bytes() + b"\n# edited\n")
            with self.assertRaises(release_identity.IdentityError):
                release_identity.validate_build_provenance(
                    provenance, app, "c" * 40, repo_root=root
                )
            shutil.copy2(REPO_ROOT / release_identity.REQUIRED_TOOL_PATHS[0], tool)
            contract = root / "packaging/release_contract.json"
            contract.write_bytes(contract.read_bytes() + b"\n")
            with self.assertRaises(release_identity.IdentityError):
                release_identity.validate_build_provenance(
                    provenance, app, "c" * 40, repo_root=root
                )


if __name__ == "__main__":
    unittest.main()
