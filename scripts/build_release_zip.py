#!/usr/bin/env python3
"""Create and verify the formal macOS Apple Silicon Release ZIP."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from verify_packaged_runtime import (
    VerificationError,
    load_manifest,
    verify_packaged_runtime,
)
from release_identity import (
    IdentityError,
    PRODUCT_VERSION,
    load_contract as load_product_contract,
    validate_build_provenance,
    validate_release_identity,
    validate_repository_identity,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_APP_PATH = REPO_ROOT / "dist" / "ClassroomTranscriber.app"
CANONICAL_PROVENANCE_PATH = REPO_ROOT / "dist" / "ClassroomTranscriber.app.provenance.json"
CANONICAL_MANIFEST_PATH = REPO_ROOT / "packaging" / "runtime_manifest.json"
DOWNLOADS_ROOT = Path.home() / "Downloads"
ZIP_TOOL = Path("/usr/bin/zip")
DITTO_TOOL = Path("/usr/bin/ditto")
VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]*$")
SOURCE_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
PROHIBITED_PATH_PARTS = {
    ".git",
    ".pytest_cache",
    ".tools",
    ".venv",
    "__MACOSX",
    "__pycache__",
    "external",
}
PROHIBITED_FILENAMES = {".DS_Store", "app_settings.json", "settings.json"}
ReleaseVerifier = Callable[[Path, dict[str, Any]], None]


class ReleaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class BundleEntry:
    kind: str
    mode: int
    size: int | None = None
    sha256: str | None = None
    link_target: str | None = None


@dataclass(frozen=True)
class ReleaseMetadata:
    version: str
    source_commit: str
    artifact_path: Path
    artifact_bytes: int
    sha256: str
    extracted_app_path: Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_version(version: str) -> str:
    if not VERSION_PATTERN.fullmatch(version):
        raise ReleaseError(
            "version must be an explicit filename-safe value containing only "
            "ASCII letters, digits, '.', '_', '+', or '-'"
        )
    if version != PRODUCT_VERSION:
        raise ReleaseError(f"formal Release version must be exactly {PRODUCT_VERSION}")
    return version


def release_contract(manifest: dict[str, Any]) -> tuple[str, str]:
    release = manifest["frozen"]["release"]
    template = release["artifact_name_template"]
    payload = release["primary_payload"]
    if template.count("<version>") != 1:
        raise ReleaseError("Manifest Release name template must contain <version> once")
    if Path(template).name != template or not template.endswith(".zip"):
        raise ReleaseError("Manifest Release name template is not a safe ZIP filename")
    if Path(payload).name != payload or not payload.endswith(".app"):
        raise ReleaseError("Manifest Release payload is not a safe App bundle name")
    return template, payload


def artifact_filename(version: str, manifest: dict[str, Any]) -> str:
    template, _payload = release_contract(manifest)
    return template.replace("<version>", validate_version(version))


def validate_host() -> None:
    if sys.platform != "darwin":
        raise ReleaseError("formal Release ZIP packaging requires macOS")
    if platform.machine() != "arm64":
        raise ReleaseError("formal Release ZIP packaging requires an arm64 host")
    for tool in (ZIP_TOOL, DITTO_TOOL):
        if not tool.is_file() or not os.access(tool, os.X_OK):
            raise ReleaseError(f"required macOS archive tool is missing: {tool}")


def validate_formal_python(manifest: dict[str, Any]) -> None:
    python_contract = manifest["frozen"]["python"]
    formal_relative = manifest["frozen"]["developer_build_entry"][
        "formal_python_path"
    ]
    formal_python = REPO_ROOT / formal_relative
    if not formal_python.is_file():
        raise ReleaseError(f"formal project Python is missing: {formal_relative}")
    if not os.path.samefile(sys.executable, formal_python):
        raise ReleaseError(
            f"Release ZIP entry must run with {formal_relative}, got {sys.executable}"
        )
    actual_version = platform.python_version()
    if actual_version != python_contract["exact_version"]:
        raise ReleaseError(
            f"formal Release Python is {actual_version}; expected "
            f"{python_contract['exact_version']}"
        )


def source_commit(repo_root: Path = REPO_ROOT) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    if result.returncode != 0 or not SOURCE_COMMIT_PATTERN.fullmatch(commit):
        detail = (result.stderr or result.stdout).strip()
        raise ReleaseError(
            "cannot resolve the 40-character source commit"
            + (f": {detail}" if detail else "")
        )
    return commit


def validate_clean_source(repo_root: Path = REPO_ROOT) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ReleaseError(
            "cannot inspect source worktree"
            + (f": {detail}" if detail else "")
        )
    if result.stdout.strip():
        raise ReleaseError(
            "formal Release ZIP requires a clean source worktree; commit or remove "
            "the listed changes first:\n"
            + result.stdout.rstrip()
        )
    commit = source_commit(repo_root)
    try:
        validate_repository_identity(repo_root)
    except IdentityError as exc:
        raise ReleaseError(str(exc)) from exc
    return commit


def validate_expected_source_commit(actual: str, expected: str) -> str:
    if not SOURCE_COMMIT_PATTERN.fullmatch(expected):
        raise ReleaseError("expected source commit must be a 40-character lowercase Git SHA")
    if actual != expected:
        raise ReleaseError("source HEAD differs from the explicit expected source commit")
    return actual


def validate_formal_source_paths(
    app_path: Path,
    build_provenance_path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> tuple[Path, Path]:
    try:
        canonical_repo = repo_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ReleaseError("canonical source repository must exist") from exc
    if not canonical_repo.is_dir():
        raise ReleaseError("canonical source repository must be a directory")

    canonical_dist_path = canonical_repo / "dist"
    canonical_app_path = canonical_dist_path / "ClassroomTranscriber.app"
    canonical_provenance_path = (
        canonical_dist_path / "ClassroomTranscriber.app.provenance.json"
    )
    app_candidate = Path(os.path.abspath(app_path))
    provenance_candidate = Path(os.path.abspath(build_provenance_path))
    if app_candidate != canonical_app_path:
        raise ReleaseError(
            "formal Release ZIP must consume this clone's dist/ClassroomTranscriber.app"
        )
    if provenance_candidate != canonical_provenance_path:
        raise ReleaseError(
            "formal Release ZIP must consume the App-adjacent canonical provenance"
        )
    try:
        dist_mode = canonical_dist_path.stat(follow_symlinks=False).st_mode
        resolved_dist = canonical_dist_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ReleaseError("canonical dist must already exist") from exc
    if not stat.S_ISDIR(dist_mode) or resolved_dist != canonical_dist_path:
        raise ReleaseError("canonical dist must be this clone's real directory")
    try:
        app_mode = canonical_app_path.stat(follow_symlinks=False).st_mode
        provenance_mode = canonical_provenance_path.stat(follow_symlinks=False).st_mode
    except (OSError, RuntimeError) as exc:
        raise ReleaseError("canonical App and provenance must already exist") from exc
    if not stat.S_ISDIR(app_mode):
        raise ReleaseError("canonical App must be a real directory, not a symbolic link")
    if not stat.S_ISREG(provenance_mode):
        raise ReleaseError(
            "canonical provenance must be a real regular file, not a symbolic link"
        )
    try:
        resolved_app = canonical_app_path.resolve(strict=True)
        resolved_provenance = canonical_provenance_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ReleaseError("canonical App and provenance must resolve strictly") from exc
    if (
        resolved_app != canonical_app_path
        or resolved_provenance != canonical_provenance_path
        or resolved_app.parent != resolved_dist
        or resolved_provenance.parent != resolved_dist
    ):
        raise ReleaseError(
            "canonical App and provenance must remain directly inside this clone's dist"
        )
    return resolved_app, resolved_provenance


def validate_managed_output_paths(
    task_root: Path,
    artifact_path: Path,
    extraction_dir: Path,
    *,
    downloads_root: Path = DOWNLOADS_ROOT,
) -> tuple[Path, Path, Path]:
    try:
        downloads = downloads_root.resolve(strict=True)
        managed_root = task_root.resolve(strict=True)
        artifact_parent = artifact_path.parent.resolve(strict=True)
        extraction_parent = extraction_dir.parent.resolve(strict=True)
    except OSError as exc:
        raise ReleaseError(
            "Downloads, task root, and output parent directories must already exist"
        ) from exc
    if not downloads.is_dir():
        raise ReleaseError("current user's Downloads path is not a directory")
    if (
        not managed_root.is_dir()
        or managed_root == downloads
        or not managed_root.is_relative_to(downloads)
    ):
        raise ReleaseError(
            "task root must be an explicit managed directory under the current user's Downloads"
        )
    final_artifact = artifact_parent / artifact_path.name
    extract_root = extraction_parent / extraction_dir.name
    if final_artifact == managed_root or not final_artifact.is_relative_to(managed_root):
        raise ReleaseError("Release artifact must be a descendant of the task root")
    if extract_root == managed_root or not extract_root.is_relative_to(managed_root):
        raise ReleaseError("Human-review extraction must be a descendant of the task root")
    return managed_root, final_artifact, extract_root


def validate_payload_path(relative: PurePosixPath) -> None:
    if relative.is_absolute() or ".." in relative.parts:
        raise ReleaseError(f"unsafe Release payload path: {relative}")
    if any(part in PROHIBITED_PATH_PARTS for part in relative.parts):
        raise ReleaseError(f"development or metadata path is forbidden: {relative}")
    if relative.name in PROHIBITED_FILENAMES or relative.name.endswith(".local.json"):
        raise ReleaseError(f"user-specific file is forbidden: {relative}")
    lower_name = relative.name.lower()
    if lower_name.endswith(".gguf") or (
        lower_name.startswith("ggml-") and lower_name.endswith(".bin")
    ):
        raise ReleaseError(f"model binary is forbidden in the Release ZIP: {relative}")


def snapshot_bundle(app_path: Path) -> dict[PurePosixPath, BundleEntry]:
    entries: dict[PurePosixPath, BundleEntry] = {}
    if not app_path.is_dir() or app_path.suffix != ".app":
        raise ReleaseError(f"App bundle is missing or invalid: {app_path}")
    bundle_root = app_path.resolve(strict=True)

    def visit(directory: Path, relative_directory: PurePosixPath) -> None:
        for item in sorted(os.scandir(directory), key=lambda entry: entry.name):
            relative = relative_directory / item.name
            validate_payload_path(relative)
            item_stat = item.stat(follow_symlinks=False)
            mode = stat.S_IMODE(item_stat.st_mode)
            if item.is_symlink():
                try:
                    resolved_target = Path(item.path).resolve(strict=True)
                except OSError as exc:
                    raise ReleaseError(f"broken App bundle symlink: {relative}") from exc
                if not resolved_target.is_relative_to(bundle_root):
                    raise ReleaseError(
                        f"App bundle symlink resolves outside the App: {relative}"
                    )
                entries[relative] = BundleEntry(
                    kind="symlink", mode=mode, link_target=os.readlink(item.path)
                )
            elif item.is_dir(follow_symlinks=False):
                entries[relative] = BundleEntry(kind="directory", mode=mode)
                visit(Path(item.path), relative)
            elif item.is_file(follow_symlinks=False):
                path = Path(item.path)
                entries[relative] = BundleEntry(
                    kind="file",
                    mode=mode,
                    size=item_stat.st_size,
                    sha256=sha256_file(path),
                )
            else:
                raise ReleaseError(f"unsupported App bundle entry: {relative}")

    visit(app_path, PurePosixPath())
    if not entries:
        raise ReleaseError(f"App bundle is empty: {app_path}")
    return entries


def validate_archive(archive_path: Path, payload_name: str) -> None:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if not names:
                raise ReleaseError("Release ZIP is empty")
            for name in names:
                relative = PurePosixPath(name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ReleaseError(f"unsafe ZIP entry: {name}")
                if not relative.parts or relative.parts[0] != payload_name:
                    raise ReleaseError(f"ZIP entry is outside {payload_name}: {name}")
                if len(relative.parts) > 1:
                    validate_payload_path(PurePosixPath(*relative.parts[1:]))
            corrupt = archive.testzip()
            if corrupt is not None:
                raise ReleaseError(f"Release ZIP CRC verification failed: {corrupt}")
    except zipfile.BadZipFile as exc:
        raise ReleaseError(f"invalid Release ZIP: {archive_path}") from exc


def checked_command(arguments: list[str], *, cwd: Path | None = None) -> None:
    result = subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ReleaseError(
            f"command failed ({result.returncode}): {' '.join(arguments)}"
            + (f"\n{detail}" if detail else "")
        )


def verify_round_trip(
    source_snapshot: dict[PurePosixPath, BundleEntry], extracted_app: Path
) -> None:
    extracted_snapshot = snapshot_bundle(extracted_app)
    if source_snapshot != extracted_snapshot:
        source_paths = set(source_snapshot)
        extracted_paths = set(extracted_snapshot)
        missing = sorted(str(path) for path in source_paths - extracted_paths)
        unexpected = sorted(str(path) for path in extracted_paths - source_paths)
        changed = sorted(
            str(path)
            for path in source_paths & extracted_paths
            if source_snapshot[path] != extracted_snapshot[path]
        )
        details = []
        if missing:
            details.append(f"missing={missing[:5]}")
        if unexpected:
            details.append(f"unexpected={unexpected[:5]}")
        if changed:
            details.append(f"changed={changed[:5]}")
        raise ReleaseError(
            "App bundle changed during ZIP round-trip"
            + (f": {', '.join(details)}" if details else "")
        )


def create_release_zip(
    *,
    version: str,
    app_path: Path,
    artifact_path: Path,
    extraction_dir: Path,
    task_root: Path,
    build_provenance_path: Path,
    manifest: dict[str, Any],
    verifier: ReleaseVerifier = verify_packaged_runtime,
    commit: str,
    tag: str | None = None,
    title: str | None = None,
    notes_path: Path | None = None,
    repo_root: Path = REPO_ROOT,
    downloads_root: Path = DOWNLOADS_ROOT,
    enforce_formal_source_paths: bool = True,
) -> ReleaseMetadata:
    validate_host()
    product_contract = load_product_contract(
        repo_root / "packaging" / "release_contract.json"
    )
    template, payload_name = release_contract(manifest)
    version = validate_version(version)
    repo_root = repo_root.resolve()
    if enforce_formal_source_paths:
        app_path, build_provenance_path = validate_formal_source_paths(
            app_path, build_provenance_path, repo_root=repo_root
        )
    else:
        app_path = app_path.resolve()
    _managed_root, final_artifact, extract_root = validate_managed_output_paths(
        task_root,
        artifact_path,
        extraction_dir,
        downloads_root=downloads_root,
    )
    if app_path.name != payload_name:
        raise ReleaseError(
            f"Release App must be named {payload_name}, got {app_path.name}"
        )
    if final_artifact.is_relative_to(repo_root):
        raise ReleaseError("Release artifact path must be outside the source tree")
    if extract_root.is_relative_to(repo_root):
        raise ReleaseError("Human-review extraction path must be outside the source tree")
    if extraction_dir.name in {"", ".", ".."}:
        raise ReleaseError("Human-review extraction must name a new directory")
    if os.path.lexists(final_artifact):
        raise ReleaseError("Release artifact target already exists; clobber is forbidden")
    if os.path.lexists(extract_root):
        raise ReleaseError("Human-review extraction target already exists")
    if not SOURCE_COMMIT_PATTERN.fullmatch(commit):
        raise ReleaseError("source commit must be a 40-character lowercase Git SHA")
    tag = tag or product_contract["tag"]
    title = title or product_contract["title"]
    notes_path = notes_path or repo_root / product_contract["release_notes_path"]
    expected_asset = template.replace("<version>", version)
    if final_artifact.name != expected_asset:
        raise ReleaseError("Release artifact filename disagrees with fixed identity")
    try:
        validate_release_identity(
            repo_root=repo_root,
            app_path=app_path,
            manifest=manifest,
            version=version,
            tag=tag,
            title=title,
            asset_name=final_artifact.name,
            notes_path=notes_path,
            contract=product_contract,
        )
        validate_build_provenance(
            build_provenance_path,
            app_path,
            commit,
            repo_root=repo_root,
        )
    except IdentityError as exc:
        raise ReleaseError(str(exc)) from exc

    print(f"[release-zip] verify source App: {app_path}")
    verifier(app_path, manifest)
    print("[release-zip] source App Runtime verification PASS")
    source_snapshot = snapshot_bundle(app_path)

    extracted_app_path: Path | None = None
    artifact_size: int | None = None
    artifact_digest: str | None = None
    try:
        with tempfile.TemporaryDirectory(
            prefix=".classroom-release-stage-", dir=final_artifact.parent
        ) as stage_temp:
            stage_root = Path(stage_temp)
            extract_root.mkdir(parents=False, exist_ok=False)
            staged_artifact = stage_root / final_artifact.name
            checked_command(
                [
                    str(ZIP_TOOL),
                    "-q",
                    "-r",
                    "-y",
                    "-X",
                    str(staged_artifact),
                    app_path.name,
                ],
                cwd=app_path.parent,
            )
            validate_archive(staged_artifact, payload_name)
            print("[release-zip] archive content boundary and CRC PASS")

            checked_command(
                [
                    str(DITTO_TOOL),
                    "-x",
                    "-k",
                    "--norsrc",
                    str(staged_artifact),
                    str(extract_root),
                ]
            )
            top_level = sorted(path.name for path in extract_root.iterdir())
            if top_level != [payload_name]:
                raise ReleaseError(
                    f"extracted ZIP must contain only {payload_name}, got {top_level}"
                )
            extracted_app = extract_root / payload_name
            verify_round_trip(source_snapshot, extracted_app)
            print("[release-zip] bundle structure, bytes, permissions, and symlinks PASS")
            print(f"[release-zip] verify extracted App: {extracted_app}")
            verifier(extracted_app, manifest)
            print("[release-zip] extracted App Runtime verification PASS")
            extracted_app_path = extracted_app
            artifact_size = staged_artifact.stat().st_size
            artifact_digest = sha256_file(staged_artifact)
            try:
                os.link(staged_artifact, final_artifact)
            except FileExistsError as exc:
                raise ReleaseError(
                    "Release artifact appeared during publication; clobber is forbidden"
                ) from exc
    except Exception:
        if extract_root.is_dir():
            shutil.rmtree(extract_root)
        raise

    if extracted_app_path is None or artifact_size is None or artifact_digest is None:
        raise ReleaseError("extracted App verification did not run")
    return ReleaseMetadata(
        version=version,
        source_commit=commit,
        artifact_path=final_artifact,
        artifact_bytes=artifact_size,
        sha256=artifact_digest,
        extracted_app_path=extracted_app_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="explicit Release version")
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--human-review-extraction", type=Path, required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--tag", default=PRODUCT_VERSION)
    parser.add_argument("--title", default="Classroom Transcriber 1.1.0")
    parser.add_argument(
        "--notes", type=Path, default=REPO_ROOT / "RELEASE_NOTES_1.1.0.md"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        manifest = load_manifest(CANONICAL_MANIFEST_PATH)
        validate_formal_python(manifest)
        commit = validate_clean_source()
        validate_expected_source_commit(commit, arguments.expected_source_commit)
        metadata = create_release_zip(
            version=arguments.version,
            app_path=CANONICAL_APP_PATH,
            artifact_path=arguments.artifact,
            extraction_dir=arguments.human_review_extraction,
            task_root=arguments.task_root,
            build_provenance_path=CANONICAL_PROVENANCE_PATH,
            manifest=manifest,
            commit=commit,
            tag=arguments.tag,
            title=arguments.title,
            notes_path=arguments.notes,
        )
    except (KeyError, OSError, ReleaseError, VerificationError, IdentityError) as exc:
        print(f"[release-zip] ERROR: {exc}", file=sys.stderr)
        return 1

    print("[release-zip] Release ZIP PASS")
    print(f"version: {metadata.version}")
    print(f"source_commit: {metadata.source_commit}")
    print(f"artifact: {metadata.artifact_path.name}")
    print(f"artifact_path: {metadata.artifact_path}")
    print(f"artifact_bytes: {metadata.artifact_bytes}")
    print(f"sha256: {metadata.sha256}")
    print("extracted_app_verification: PASS")
    print(f"human_review_extraction: {metadata.extracted_app_path.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
