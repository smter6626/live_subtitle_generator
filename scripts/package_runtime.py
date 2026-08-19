#!/usr/bin/env python3
"""Validate source Runtime inputs and normalize only their packaged App copies."""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from verify_packaged_runtime import (
    DEFAULT_MANIFEST_PATH,
    CommandRunner,
    VerificationError,
    checked_run,
    collect_artifacts,
    is_system_dependency,
    load_manifest,
    parse_dependencies,
    parse_rpaths,
    required_components,
    run_command,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from model_integrity import load_model_contract  # noqa: E402


def assert_source_file(repo_root: Path, relative_path: str) -> Path:
    path = repo_root.joinpath(*PurePosixPath(relative_path).parts)
    if not path.is_file():
        raise VerificationError(f"required packaging source is missing: {relative_path}")
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(repo_root.resolve()):
        raise VerificationError(f"packaging source resolves outside repository: {relative_path}")
    return path


def validate_sources(
    manifest: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
    runner: CommandRunner = run_command,
) -> None:
    for component in required_components(manifest):
        source = assert_source_file(repo_root, component["source_path"])
        if source.name != component["bundle_filename"]:
            raise VerificationError(
                f"Runtime source filename mismatch for {component['name']}: {source.name}"
            )
        if component["kind"] == "executable" and not os.access(source, os.X_OK):
            raise VerificationError(f"required Runtime source is not executable: {source}")
        if component["kind"] == "dynamic_library" and not os.access(source, os.R_OK):
            raise VerificationError(f"required Runtime source is not readable: {source}")

    for resource in manifest["frozen"]["vendored_resources"]:
        if resource.get("required") is not True:
            continue
        source = assert_source_file(repo_root, resource["repository_path"])
        checked_run(runner, ["sh", "-n", str(source)])

    model_integrity = manifest["frozen"]["model_integrity"]
    if model_integrity["required_packaged_resource"] is True:
        model_manifest = assert_source_file(
            repo_root, model_integrity["manifest_repository_path"]
        )
        try:
            load_model_contract(model_manifest)
        except RuntimeError as exc:
            raise VerificationError(f"invalid model integrity manifest: {exc}") from exc
    print("[package-runtime] required source preflight PASS")


def dylib_install_id(runner: CommandRunner, artifact: Path) -> str | None:
    output = checked_run(runner, ["otool", "-D", str(artifact)]).stdout.splitlines()
    values = [line.strip() for line in output[1:] if line.strip()]
    return values[0] if values else None


def normalize_app(
    app_path: Path,
    manifest: dict[str, Any],
    *,
    runner: CommandRunner = run_command,
) -> None:
    app_path = app_path.resolve()
    _logical_paths, resolved_paths = collect_artifacts(app_path, manifest)
    components = required_components(manifest)
    known_filenames = {component["bundle_filename"] for component in components}
    required_rpath = manifest["frozen"]["packaged_runtime"]["runtime_rpath"]

    for component in components:
        artifact = resolved_paths[component["name"]]
        install_id = (
            dylib_install_id(runner, artifact)
            if component["kind"] == "dynamic_library"
            else None
        )
        dependencies = parse_dependencies(
            checked_run(runner, ["otool", "-L", str(artifact)]).stdout
        )
        rpaths = parse_rpaths(
            checked_run(runner, ["otool", "-l", str(artifact)]).stdout
        )

        for rpath in rpaths:
            checked_run(
                runner,
                ["install_name_tool", "-delete_rpath", rpath, str(artifact)],
            )
        checked_run(
            runner,
            ["install_name_tool", "-add_rpath", required_rpath, str(artifact)],
        )

        if component["kind"] == "dynamic_library":
            checked_run(
                runner,
                [
                    "install_name_tool",
                    "-id",
                    f"@rpath/{component['bundle_filename']}",
                    str(artifact),
                ],
            )

        for dependency in dependencies:
            if dependency == install_id or is_system_dependency(dependency, manifest):
                continue
            filename = PurePosixPath(dependency).name
            if filename not in known_filenames:
                raise VerificationError(
                    f"cannot normalize undeclared Runtime dependency for "
                    f"{component['name']}: {dependency}"
                )
            normalized = f"@rpath/{filename}"
            if dependency != normalized:
                checked_run(
                    runner,
                    [
                        "install_name_tool",
                        "-change",
                        dependency,
                        normalized,
                        str(artifact),
                    ],
                )

    for component in components:
        if component["kind"] == "executable":
            path = resolved_paths[component["name"]]
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    for resource in manifest["frozen"]["vendored_resources"]:
        if resource.get("required") is not True:
            continue
        target = app_path.joinpath(*PurePosixPath(resource["bundle_target"]).parts)
        if not target.is_file() or not target.resolve().is_relative_to(app_path):
            raise VerificationError(f"required bundled resource is missing: {target}")
        target.chmod(target.stat().st_mode | 0o111)
        checked_run(runner, ["sh", "-n", str(target)])
    print("[package-runtime] packaged Runtime normalization PASS")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=DEFAULT_MANIFEST_PATH
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate-sources")
    normalize = subparsers.add_parser("normalize-app")
    normalize.add_argument("app_path", type=Path)
    return parser


def main(
    argv: list[str] | None = None,
    *,
    runner: CommandRunner = run_command,
    repo_root: Path = REPO_ROOT,
) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        manifest = load_manifest(arguments.manifest)
        if arguments.command == "validate-sources":
            validate_sources(manifest, repo_root=repo_root, runner=runner)
        elif arguments.command == "normalize-app":
            normalize_app(arguments.app_path, manifest, runner=runner)
    except (KeyError, OSError, VerificationError) as exc:
        print(f"[package-runtime] ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
