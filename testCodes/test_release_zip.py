import contextlib
import hashlib
import io
import os
import plistlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import build_release_zip as release_zip  # noqa: E402


MANIFEST_PATH = REPO_ROOT / "packaging" / "runtime_manifest.json"


class ReleaseZipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = release_zip.load_manifest(MANIFEST_PATH)

    def make_app(self, root: Path) -> Path:
        app = root / "ClassroomTranscriber.app"
        executable = app / "Contents" / "MacOS" / "ClassroomTranscriber"
        framework = app / "Contents" / "Frameworks" / "fixture-runtime"
        resource_link = app / "Contents" / "Resources" / "fixture-runtime"
        executable.parent.mkdir(parents=True)
        framework.parent.mkdir(parents=True)
        resource_link.parent.mkdir(parents=True)
        executable.write_bytes(b"fixture executable\n")
        executable.chmod(0o755)
        framework.write_bytes(b"fixture Runtime\n")
        framework.chmod(0o644)
        resource_link.symlink_to(Path("../Frameworks/fixture-runtime"))
        app_icon = self.manifest["frozen"]["app_icon"]
        icon = app.joinpath(*Path(app_icon["bundle_target"]).parts)
        icon.write_bytes(b"icns" + (12).to_bytes(4, "big") + b"TEST")
        with (app / "Contents" / "Info.plist").open("wb") as handle:
            plistlib.dump({"CFBundleIconFile": app_icon["bundle_filename"]}, handle)
        return app

    def test_version_is_explicit_and_filename_safe(self):
        self.assertEqual(
            release_zip.artifact_filename("0.0.0-step9a", self.manifest),
            "ClassroomTranscriber-0.0.0-step9a-macOS-AppleSilicon.zip",
        )
        for invalid in ("", "../1.0", "1.0 beta", "/tmp/release"):
            with self.subTest(version=invalid), self.assertRaises(
                release_zip.ReleaseError
            ):
                release_zip.artifact_filename(invalid, self.manifest)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            release_zip.build_parser().parse_args([])

    def test_formal_entry_uses_locked_project_python(self):
        release_zip.validate_formal_python(self.manifest)

    def test_formal_entry_rejects_a_dirty_source_worktree(self):
        dirty = release_zip.subprocess.CompletedProcess(
            ["git", "status"], 0, " M README.md\n", ""
        )
        with mock.patch.object(release_zip.subprocess, "run", return_value=dirty):
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.validate_clean_source(REPO_ROOT)

    def test_round_trip_preserves_bytes_modes_and_symlinks(self):
        verifier_calls = []

        def fake_verifier(app_path, _manifest):
            verifier_calls.append(app_path.resolve())

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root / "source")
            output = root / "artifacts"
            metadata = release_zip.create_release_zip(
                version="0.0.0-step9a",
                app_path=app,
                output_dir=output,
                manifest=self.manifest,
                verifier=fake_verifier,
                commit="a" * 40,
            )
            self.assertEqual(len(verifier_calls), 2)
            self.assertEqual(verifier_calls[0], app.resolve())
            self.assertFalse(verifier_calls[1].is_relative_to(REPO_ROOT.resolve()))
            self.assertEqual(
                metadata.artifact_path.name,
                "ClassroomTranscriber-0.0.0-step9a-macOS-AppleSilicon.zip",
            )
            self.assertEqual(metadata.artifact_bytes, metadata.artifact_path.stat().st_size)
            self.assertEqual(metadata.sha256, release_zip.sha256_file(metadata.artifact_path))

            extracted = root / "independent-extract"
            extracted.mkdir()
            release_zip.checked_command(
                [
                    str(release_zip.DITTO_TOOL),
                    "-x",
                    "-k",
                    "--norsrc",
                    str(metadata.artifact_path),
                    str(extracted),
                ]
            )
            extracted_app = extracted / app.name
            link = extracted_app / "Contents" / "Resources" / "fixture-runtime"
            executable = extracted_app / "Contents" / "MacOS" / "ClassroomTranscriber"
            app_icon = self.manifest["frozen"]["app_icon"]
            icon = extracted_app.joinpath(*Path(app_icon["bundle_target"]).parts)
            self.assertTrue(link.is_symlink())
            self.assertEqual(os.readlink(link), "../Frameworks/fixture-runtime")
            self.assertTrue(os.access(executable, os.X_OK))
            self.assertEqual(executable.read_bytes(), b"fixture executable\n")
            self.assertEqual(
                icon.read_bytes(), b"icns" + (12).to_bytes(4, "big") + b"TEST"
            )

    def test_same_app_produces_byte_identical_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root / "source")
            output = root / "artifacts"
            arguments = {
                "version": "0.0.0-step9a",
                "app_path": app,
                "output_dir": output,
                "manifest": self.manifest,
                "verifier": lambda _app_path, _manifest: None,
                "commit": "c" * 40,
            }
            first = release_zip.create_release_zip(**arguments)
            first_bytes = first.artifact_path.read_bytes()
            second = release_zip.create_release_zip(**arguments)
            self.assertEqual(first.sha256, second.sha256)
            self.assertEqual(first_bytes, second.artifact_path.read_bytes())

    def test_verification_failure_does_not_publish_artifact(self):
        calls = 0

        def failing_extracted_verifier(_app_path, _manifest):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise release_zip.VerificationError("injected extracted-App failure")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root / "source")
            output = root / "artifacts"
            with self.assertRaises(release_zip.VerificationError):
                release_zip.create_release_zip(
                    version="0.0.0-step9a",
                    app_path=app,
                    output_dir=output,
                    manifest=self.manifest,
                    verifier=failing_extracted_verifier,
                    commit="b" * 40,
                )
            self.assertFalse(
                (output / release_zip.artifact_filename("0.0.0-step9a", self.manifest)).exists()
            )

    def test_model_and_development_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root)
            forbidden_files = (
                app / "Contents" / "Resources" / "ggml-large-v3.bin",
                app / "Contents" / "Resources" / ".venv" / "pyvenv.cfg",
                app / "Contents" / "Resources" / "settings.json",
            )
            for forbidden in forbidden_files:
                with self.subTest(path=forbidden):
                    forbidden.parent.mkdir(parents=True, exist_ok=True)
                    forbidden.write_bytes(b"forbidden")
                    with self.assertRaises(release_zip.ReleaseError):
                        release_zip.snapshot_bundle(app)
                    forbidden.unlink()

    def test_archive_rejects_entries_outside_the_app(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("ClassroomTranscriber.app/Contents/Info.plist", b"fixture")
                archive.writestr("source-tree/README.md", b"forbidden")
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.validate_archive(archive_path, "ClassroomTranscriber.app")

    def test_bundle_rejects_symlinks_into_the_source_or_host(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root / "source")
            external_file = root / "host-only-runtime"
            external_file.write_bytes(b"host dependency")
            unsafe_link = app / "Contents" / "Resources" / "host-only-runtime"
            unsafe_link.symlink_to(external_file)
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.snapshot_bundle(app)

    def test_reported_sha256_is_exact(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "artifact.zip"
            fixture.write_bytes(b"release artifact fixture")
            self.assertEqual(
                release_zip.sha256_file(fixture),
                hashlib.sha256(b"release artifact fixture").hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
