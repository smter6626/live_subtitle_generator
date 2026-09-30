#!/usr/bin/env python3
"""Validate the fixed 1.1.0 identity and canonical App build provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import stat
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "packaging" / "release_contract.json"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
PRODUCT_VERSION = "1.1.0"
REQUIRED_TOOL_PATHS = (
    "packaging/ClassroomTranscriber.spec",
    "packaging/runtime_manifest.json",
    "scripts/build_app_icon.py",
    "scripts/build_macos.sh",
    "scripts/build_release_zip.py",
    "scripts/package_runtime.py",
    "scripts/release_identity.py",
    "scripts/verify_packaged_runtime.py",
)
EXPECTED_CONTRACT = {
    "schema_version": 1,
    "product_version": PRODUCT_VERSION,
    "tag": PRODUCT_VERSION,
    "title": "Classroom Transcriber 1.1.0",
    "asset_name": "ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip",
    "app_name": "ClassroomTranscriber.app",
    "release_notes_path": "RELEASE_NOTES_1.1.0.md",
    "release_notes_sha256": "d7c90520a247cf2a743dc780e38a5a0abd5bc309a024e2c3d4f91f73bbaab938",
    "repository": "smter6626/live_subtitle_generator",
    "canonical_origins": [
        "git@github.com:smter6626/live_subtitle_generator.git",
        "https://github.com/smter6626/live_subtitle_generator.git",
    ],
    "models": "external",
    "signing": "ad-hoc",
    "notarized": False,
    "status": "candidate-unbuilt-unpublished",
}


class IdentityError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value != EXPECTED_CONTRACT:
        raise IdentityError("release contract is missing, extra, or differs from fixed 1.1.0 identity")
    return value


def validate_runtime_manifest(
    manifest: dict[str, Any], repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    path = repo_root / "packaging" / "runtime_manifest.json"
    try:
        canonical = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityError("canonical Runtime Manifest is missing or invalid JSON") from exc
    if manifest != canonical:
        raise IdentityError(
            "Runtime Manifest object differs from the tracked canonical input"
        )
    return canonical


def release_contract_sha256(repo_root: Path = REPO_ROOT) -> str:
    path = repo_root / "packaging" / "release_contract.json"
    load_contract(path)
    return sha256_file(path)


def git_output(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise IdentityError(f"git {' '.join(arguments)} failed" + (f": {detail}" if detail else ""))
    return result.stdout.strip()


def validate_repository_identity(repo_root: Path = REPO_ROOT) -> str:
    contract = load_contract(repo_root / "packaging" / "release_contract.json")
    origin = git_output(repo_root, "remote", "get-url", "origin")
    if origin not in contract["canonical_origins"]:
        raise IdentityError("repository origin is not an allowlisted canonical identity")
    return origin


def validate_clean_source(repo_root: Path = REPO_ROOT) -> str:
    status = git_output(repo_root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise IdentityError("formal Release requires a clean tracked and untracked source worktree")
    commit = git_output(repo_root, "rev-parse", "--verify", "HEAD")
    if not COMMIT_RE.fullmatch(commit):
        raise IdentityError("source commit is not a 40-character lowercase Git SHA")
    validate_repository_identity(repo_root)
    return commit


def project_versions(repo_root: Path) -> tuple[str, str]:
    with (repo_root / "pyproject.toml").open("rb") as handle:
        project_version = tomllib.load(handle)["project"]["version"]
    lock = tomllib.loads((repo_root / "uv.lock").read_text(encoding="utf-8"))
    matches = [
        package["version"]
        for package in lock["package"]
        if package["name"] == "classroom-live-transcriber"
    ]
    if len(matches) != 1:
        raise IdentityError("uv.lock must contain exactly one root-project package")
    return project_version, matches[0]


def validate_release_spec_versions(repo_root: Path) -> None:
    text = (repo_root / "packaging" / "ClassroomTranscriber.spec").read_text(
        encoding="utf-8"
    )
    for key in ("CFBundleShortVersionString", "CFBundleVersion"):
        declaration = f'"{key}": "{PRODUCT_VERSION}"'
        if text.count(declaration) != 1:
            raise IdentityError(f"Release App spec must declare {key} exactly once as 1.1.0")


def read_plist_versions(app_path: Path) -> tuple[Any, Any]:
    try:
        with (app_path / "Contents" / "Info.plist").open("rb") as handle:
            info = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as exc:
        raise IdentityError("cannot read App Info.plist") from exc
    return info.get("CFBundleShortVersionString"), info.get("CFBundleVersion")


def validate_release_identity(
    *,
    repo_root: Path,
    app_path: Path | None,
    manifest: dict[str, Any],
    version: str,
    tag: str,
    title: str,
    asset_name: str,
    notes_path: Path,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = contract or load_contract(repo_root / "packaging" / "release_contract.json")
    validate_runtime_manifest(manifest, repo_root)
    supplied = {
        "product_version": version,
        "tag": tag,
        "title": title,
        "asset_name": asset_name,
    }
    for key, actual in supplied.items():
        if actual != contract[key]:
            raise IdentityError(f"{key} disagrees with the release contract")
    if project_versions(repo_root) != (PRODUCT_VERSION, PRODUCT_VERSION):
        raise IdentityError("project and lock product versions must both be 1.1.0")
    validate_release_spec_versions(repo_root)
    if manifest.get("schema_version") != "1.0.0":
        raise IdentityError("Runtime Manifest schema_version must remain 1.0.0")
    release = manifest["frozen"]["release"]
    if release["artifact_name_template"].replace("<version>", version) != asset_name:
        raise IdentityError("Runtime Manifest asset template disagrees with release contract")
    if release["primary_payload"] != contract["app_name"]:
        raise IdentityError("Runtime Manifest payload disagrees with release contract")
    expected_notes = (repo_root / contract["release_notes_path"]).resolve()
    if notes_path.resolve() != expected_notes or not expected_notes.is_file():
        raise IdentityError("release notes path disagrees with release contract")
    if sha256_file(expected_notes) != contract["release_notes_sha256"]:
        raise IdentityError("release notes bytes disagree with the release contract")
    if app_path is not None:
        if app_path.name != contract["app_name"]:
            raise IdentityError("App payload name disagrees with release contract")
        if read_plist_versions(app_path) != (PRODUCT_VERSION, PRODUCT_VERSION):
            raise IdentityError("both App plist versions must be exactly 1.1.0")
    return contract


def tree_snapshot(root: Path) -> dict[str, dict[str, Any]]:
    if not root.is_dir():
        raise IdentityError("App tree root is missing")
    snapshot: dict[str, dict[str, Any]] = {
        ".": {
            "kind": "directory",
            "mode": stat.S_IMODE(root.lstat().st_mode),
        }
    }
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        item_stat = path.lstat()
        mode = stat.S_IMODE(item_stat.st_mode)
        if path.is_symlink():
            snapshot[relative] = {
                "kind": "symlink",
                "mode": mode,
                "target": os.readlink(path),
            }
        elif path.is_dir():
            snapshot[relative] = {"kind": "directory", "mode": mode}
        elif path.is_file():
            snapshot[relative] = {
                "kind": "file",
                "mode": mode,
                "bytes": item_stat.st_size,
                "sha256": sha256_file(path),
            }
        else:
            raise IdentityError(f"unsupported App tree entry: {relative}")
    if len(snapshot) == 1:
        raise IdentityError("App tree is empty")
    return snapshot


def app_tree_sha256(app_path: Path) -> str:
    return sha256_bytes(canonical_json(tree_snapshot(app_path)))


def required_tool_hashes(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in REQUIRED_TOOL_PATHS:
        path = repo_root / relative
        if not path.is_file():
            raise IdentityError(f"required REL1A tool is missing: {relative}")
        hashes[relative] = sha256_file(path)
    return hashes


def expected_build_provenance(
    app_path: Path,
    source_commit: str,
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    if not COMMIT_RE.fullmatch(source_commit):
        raise IdentityError("build provenance source commit is invalid")
    return {
        "schema_version": 1,
        "source_commit": source_commit,
        "app_name": app_path.name,
        "app_tree_sha256": app_tree_sha256(app_path),
        "release_contract_sha256": release_contract_sha256(repo_root),
        "required_tool_sha256": required_tool_hashes(repo_root),
    }


def write_build_provenance(
    output_path: Path,
    app_path: Path,
    source_commit: str,
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    payload = expected_build_provenance(app_path, source_commit, repo_root=repo_root)
    try:
        with output_path.open("xb") as handle:
            handle.write(canonical_json(payload))
    except FileExistsError as exc:
        raise IdentityError("build provenance output already exists") from exc
    return payload


def validate_build_provenance(
    path: Path,
    app_path: Path,
    source_commit: str,
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityError("build provenance is missing or invalid JSON") from exc
    expected = expected_build_provenance(app_path, source_commit, repo_root=repo_root)
    if value != expected:
        raise IdentityError("build provenance is missing, extra, stale, edited, or bound to different inputs")
    if path.read_bytes() != canonical_json(value):
        raise IdentityError("build provenance is not canonical JSON")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check-clean-source")
    check.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    write = subparsers.add_parser("write-build-provenance")
    write.add_argument("--app", type=Path, required=True)
    write.add_argument("--output", type=Path, required=True)
    write.add_argument("--source-commit", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "check-clean-source":
            print(validate_clean_source(arguments.repo_root))
        else:
            write_build_provenance(
                arguments.output,
                arguments.app,
                arguments.source_commit,
            )
    except (IdentityError, KeyError, OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"[release-identity] ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
