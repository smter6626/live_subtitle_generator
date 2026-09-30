import contextlib
import copy
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
import release_identity  # noqa: E402


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
            plistlib.dump(
                {
                    "CFBundleIconFile": app_icon["bundle_filename"],
                    "CFBundleShortVersionString": "1.1.0",
                    "CFBundleVersion": "1.1.0",
                },
                handle,
            )
        return app

    def release_arguments(self, root: Path, app: Path, **overrides):
        root.mkdir(parents=True, exist_ok=True)
        artifact_dir = root / "artifacts"
        artifact_dir.mkdir()
        provenance = root / "build-provenance.json"
        release_identity.write_build_provenance(provenance, app, "a" * 40)
        arguments = {
            "version": "1.1.0",
            "app_path": app,
            "artifact_path": artifact_dir
            / "ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip",
            "extraction_dir": root / "human-review",
            "task_root": root,
            "build_provenance_path": provenance,
            "manifest": self.manifest,
            "verifier": lambda _app_path, _manifest: None,
            "commit": "a" * 40,
            "downloads_root": root.parent,
            "enforce_formal_source_paths": False,
        }
        arguments.update(overrides)
        return arguments

    def test_version_is_explicit_and_filename_safe(self):
        self.assertEqual(
            release_zip.artifact_filename("1.1.0", self.manifest),
            "ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip",
        )
        for invalid in ("", "../1.0", "1.0 beta", "/tmp/release", "1.0.0"):
            with self.subTest(version=invalid), self.assertRaises(
                release_zip.ReleaseError
            ):
                release_zip.artifact_filename(invalid, self.manifest)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            release_zip.build_parser().parse_args([])

    def test_formal_cli_rejects_alternate_manifest_app_and_provenance(self):
        base = [
            "--version",
            "1.1.0",
            "--task-root",
            str(Path.home() / "Downloads" / "managed-release"),
            "--artifact",
            str(Path.home() / "Downloads" / "managed-release" / "release.zip"),
            "--human-review-extraction",
            str(Path.home() / "Downloads" / "managed-release" / "human-review"),
            "--expected-source-commit",
            "a" * 40,
        ]
        for option, value in (
            ("--manifest", "/tmp/weakened.json"),
            ("--app-path", "/tmp/old.app"),
            ("--build-provenance", "/tmp/old.provenance.json"),
        ):
            with self.subTest(option=option), contextlib.redirect_stderr(
                io.StringIO()
            ), self.assertRaises(SystemExit):
                release_zip.build_parser().parse_args([*base, option, value])

    def test_altered_manifest_object_is_rejected(self):
        weakened = copy.deepcopy(self.manifest)
        weakened["frozen"]["packaged_runtime"][
            "allowed_system_dependency_prefixes"
        ] = ["/"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root / "source")
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.create_release_zip(
                    **self.release_arguments(root, app, manifest=weakened)
                )

    def test_formal_entry_uses_locked_project_python(self):
        release_zip.validate_formal_python(self.manifest)

    def test_formal_entry_rejects_a_dirty_source_worktree(self):
        dirty = release_zip.subprocess.CompletedProcess(
            ["git", "status"], 0, " M README.md\n", ""
        )
        with mock.patch.object(release_zip.subprocess, "run", return_value=dirty):
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.validate_clean_source(REPO_ROOT)

    def test_formal_entry_rejects_wrong_expected_source_commit(self):
        with self.assertRaises(release_zip.ReleaseError):
            release_zip.validate_expected_source_commit("a" * 40, "b" * 40)
        with self.assertRaises(release_zip.ReleaseError):
            release_zip.validate_expected_source_commit("a" * 40, "not-a-sha")

    def test_round_trip_preserves_bytes_modes_and_symlinks(self):
        verifier_calls = []

        def fake_verifier(app_path, _manifest):
            verifier_calls.append(app_path.resolve())

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root / "source")
            metadata = release_zip.create_release_zip(
                **self.release_arguments(root, app, verifier=fake_verifier)
            )
            self.assertEqual(len(verifier_calls), 2)
            self.assertEqual(verifier_calls[0], app.resolve())
            self.assertFalse(verifier_calls[1].is_relative_to(REPO_ROOT.resolve()))
            self.assertEqual(
                metadata.artifact_path.name,
                "ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip",
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
            self.assertEqual(
                metadata.extracted_app_path.parent, (root / "human-review").resolve()
            )
            self.assertTrue(metadata.extracted_app_path.is_dir())

    def test_same_app_produces_byte_identical_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root / "source")
            arguments = self.release_arguments(root / "first", app)
            first = release_zip.create_release_zip(**arguments)
            first_bytes = first.artifact_path.read_bytes()
            arguments = self.release_arguments(root / "second", app)
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
            arguments = self.release_arguments(
                root, app, verifier=failing_extracted_verifier
            )
            with self.assertRaises(release_zip.VerificationError):
                release_zip.create_release_zip(**arguments)
            self.assertFalse(arguments["artifact_path"].exists())
            self.assertFalse(arguments["extraction_dir"].exists())

    def test_identity_provenance_locations_and_no_clobber_are_enforced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root / "source")
            for index, override in enumerate(
                (
                    {"version": "1.0.0"},
                    {"tag": "v1.1.0"},
                    {"title": "wrong"},
                    {
                        "artifact_path": root
                        / "wrong"
                        / "ClassroomTranscriber-wrong.zip"
                    },
                    {"notes_path": root / "wrong.md"},
                )
            ):
                case_root = root / f"case-{index}"
                arguments = self.release_arguments(case_root, app)
                if "artifact_path" in override:
                    override["artifact_path"].parent.mkdir()
                with self.subTest(override=override), self.assertRaises(
                    release_zip.ReleaseError
                ):
                    release_zip.create_release_zip(**{**arguments, **override})

            stale = self.release_arguments(root / "stale", app)
            app.joinpath("Contents/MacOS/ClassroomTranscriber").write_bytes(b"changed")
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.create_release_zip(**stale)

            app = self.make_app(root / "source-second")
            arguments = self.release_arguments(root / "no-clobber", app)
            first = release_zip.create_release_zip(**arguments)
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.create_release_zip(**arguments)
            self.assertTrue(first.artifact_path.is_file())

            preexisting = self.release_arguments(root / "preexisting-extract", app)
            preexisting["extraction_dir"].mkdir()
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.create_release_zip(**preexisting)

            in_repo = self.release_arguments(root / "in-repo", app)
            in_repo["artifact_path"] = REPO_ROOT / first.artifact_path.name
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.create_release_zip(**in_repo)
            in_repo["artifact_path"] = root / "in-repo/artifacts" / first.artifact_path.name
            in_repo["extraction_dir"] = REPO_ROOT / "human-review"
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.create_release_zip(**in_repo)

    def test_formal_source_and_managed_download_paths_are_enforced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            downloads = root / "Downloads"
            task_root = downloads / "managed-release"
            artifact_parent = task_root / "artifacts"
            downloads.mkdir()
            task_root.mkdir()
            artifact_parent.mkdir()
            artifact = artifact_parent / "ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip"
            extraction = task_root / "human-review"

            self.assertEqual(
                release_zip.validate_managed_output_paths(
                    task_root,
                    artifact,
                    extraction,
                    downloads_root=downloads,
                ),
                (task_root.resolve(), artifact.resolve(), extraction.resolve()),
            )
            for bad_root, bad_artifact, bad_extraction in (
                (root / "outside", artifact, extraction),
                (task_root, root / "outside.zip", extraction),
                (task_root, artifact, downloads / "outside-review"),
            ):
                if bad_root == root / "outside":
                    bad_root.mkdir()
                with self.subTest(
                    task_root=bad_root,
                    artifact=bad_artifact,
                    extraction=bad_extraction,
                ), self.assertRaises(release_zip.ReleaseError):
                    release_zip.validate_managed_output_paths(
                        bad_root,
                        bad_artifact,
                        bad_extraction,
                        downloads_root=downloads,
                    )

    def test_formal_source_paths_require_real_clone_local_dist_and_leaves(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            repo = root / "repo"
            dist = repo / "dist"
            canonical_app = dist / "ClassroomTranscriber.app"
            canonical_provenance = dist / "ClassroomTranscriber.app.provenance.json"
            canonical_app.mkdir(parents=True)
            canonical_provenance.write_text("{}\n", encoding="utf-8")

            self.assertEqual(
                release_zip.validate_formal_source_paths(
                    canonical_app, canonical_provenance, repo_root=repo
                ),
                (canonical_app.resolve(), canonical_provenance.resolve()),
            )
            for bad_app, bad_provenance in (
                (root / "old/ClassroomTranscriber.app", canonical_provenance),
                (canonical_app, root / "old.provenance.json"),
            ):
                with self.subTest(
                    app=bad_app, provenance=bad_provenance
                ), self.assertRaises(release_zip.ReleaseError):
                    release_zip.validate_formal_source_paths(
                        bad_app, bad_provenance, repo_root=repo
                    )

            canonical_app.rmdir()
            external_app = root / "external.app"
            external_app.mkdir()
            canonical_app.symlink_to(external_app, target_is_directory=True)
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.validate_formal_source_paths(
                    canonical_app, canonical_provenance, repo_root=repo
                )

            canonical_app.unlink()
            canonical_app.mkdir()
            canonical_provenance.unlink()
            external_provenance = root / "external.provenance.json"
            external_provenance.write_text("{}\n", encoding="utf-8")
            canonical_provenance.symlink_to(external_provenance)
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.validate_formal_source_paths(
                    canonical_app, canonical_provenance, repo_root=repo
                )

            canonical_provenance.unlink()
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.validate_formal_source_paths(
                    canonical_app, canonical_provenance, repo_root=repo
                )

            canonical_provenance.write_text("{}\n", encoding="utf-8")
            canonical_app.rmdir()
            canonical_app.write_text("not an App directory\n", encoding="utf-8")
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.validate_formal_source_paths(
                    canonical_app, canonical_provenance, repo_root=repo
                )

            canonical_app.unlink()
            canonical_app.mkdir()
            canonical_provenance.unlink()
            canonical_provenance.mkdir()
            with self.assertRaises(release_zip.ReleaseError):
                release_zip.validate_formal_source_paths(
                    canonical_app, canonical_provenance, repo_root=repo
                )

    def test_formal_source_paths_reject_symlinked_dist_parent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            repo = root / "repo"
            external_dist = root / "external-dist"
            external_app = external_dist / "ClassroomTranscriber.app"
            external_provenance = (
                external_dist / "ClassroomTranscriber.app.provenance.json"
            )
            repo.mkdir()
            external_app.mkdir(parents=True)
            external_provenance.write_text("{}\n", encoding="utf-8")
            (repo / "dist").symlink_to(external_dist, target_is_directory=True)

            with self.assertRaisesRegex(release_zip.ReleaseError, "canonical dist"):
                release_zip.validate_formal_source_paths(
                    repo / "dist" / "ClassroomTranscriber.app",
                    repo / "dist" / "ClassroomTranscriber.app.provenance.json",
                    repo_root=repo,
                )

            (repo / "dist").unlink()
            with self.assertRaisesRegex(release_zip.ReleaseError, "canonical dist"):
                release_zip.validate_formal_source_paths(
                    repo / "dist" / "ClassroomTranscriber.app",
                    repo / "dist" / "ClassroomTranscriber.app.provenance.json",
                    repo_root=repo,
                )

    def test_publication_race_is_true_no_clobber(self):
        source = (SCRIPTS_DIR / "build_release_zip.py").read_text(encoding="utf-8")
        self.assertNotIn("os.replace", source)
        self.assertIn("os.link", source)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self.make_app(root / "source")
            arguments = self.release_arguments(root, app)
            with mock.patch.object(release_zip.os, "link", side_effect=FileExistsError):
                with self.assertRaises(release_zip.ReleaseError):
                    release_zip.create_release_zip(**arguments)
            self.assertFalse(arguments["artifact_path"].exists())
            self.assertFalse(arguments["extraction_dir"].exists())

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
