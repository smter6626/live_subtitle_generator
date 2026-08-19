#!/usr/bin/env python3
"""Verify the final App's Manifest-defined whisper Runtime without modifying it."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = REPO_ROOT / "packaging" / "runtime_manifest.json"
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from model_integrity import load_model_contract  # noqa: E402


class VerificationError(RuntimeError):
    pass


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(
    arguments: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def checked_run(
    runner: CommandRunner,
    arguments: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = runner(arguments, env=env)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise VerificationError(
            f"command failed ({result.returncode}): {' '.join(arguments)}"
            + (f"\n{detail}" if detail else "")
        )
    return result


def required_components(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    components = [
        component
        for component in manifest["frozen"]["runtime_components"]
        if component.get("required") is True
    ]
    if not components:
        raise VerificationError("Manifest declares no required Runtime components")
    filenames = [component["bundle_filename"] for component in components]
    if len(filenames) != len(set(filenames)):
        raise VerificationError("Manifest Runtime bundle filenames are not unique")
    return components


def component_bundle_path(app_path: Path, component: dict[str, Any]) -> Path:
    relative = PurePosixPath(component["bundle_directory"]) / component["bundle_filename"]
    if relative.is_absolute() or ".." in relative.parts:
        raise VerificationError(f"unsafe Runtime bundle path: {relative}")
    return app_path.joinpath(*relative.parts)


def resolve_bundle_file(app_path: Path, logical_path: Path) -> Path:
    if not logical_path.is_file():
        raise VerificationError(f"required bundled file is missing: {logical_path}")
    try:
        resolved = logical_path.resolve(strict=True)
    except OSError as exc:
        raise VerificationError(f"cannot resolve bundled file: {logical_path}: {exc}") from exc
    if not resolved.is_relative_to(app_path.resolve()):
        raise VerificationError(
            f"bundled file resolves outside the App: {logical_path} -> {resolved}"
        )
    return resolved


def collect_artifacts(
    app_path: Path, manifest: dict[str, Any]
) -> tuple[dict[str, Path], dict[str, Path]]:
    logical_paths: dict[str, Path] = {}
    resolved_paths: dict[str, Path] = {}
    for component in required_components(manifest):
        name = component["name"]
        logical = component_bundle_path(app_path, component)
        logical_paths[name] = logical
        resolved_paths[name] = resolve_bundle_file(app_path, logical)
        if component["kind"] == "executable":
            if not os.access(logical, os.X_OK):
                raise VerificationError(f"bundled executable is not executable: {logical}")
        elif not os.access(logical, os.R_OK):
            raise VerificationError(f"bundled dynamic library is not readable: {logical}")
    return logical_paths, resolved_paths


def parse_dependencies(output: str) -> list[str]:
    dependencies: list[str] = []
    for line in output.splitlines()[1:]:
        stripped = line.strip()
        if stripped:
            dependencies.append(stripped.split(" (", 1)[0])
    return dependencies


def parse_rpaths(output: str) -> list[str]:
    lines = output.splitlines()
    rpaths: list[str] = []
    for index, line in enumerate(lines):
        if line.strip() != "cmd LC_RPATH":
            continue
        for candidate in lines[index + 1 : index + 7]:
            match = re.match(r"\s*path (.+) \(offset \d+\)\s*$", candidate)
            if match:
                rpaths.append(match.group(1))
                break
    return rpaths


def is_system_dependency(dependency: str, manifest: dict[str, Any]) -> bool:
    prefixes = manifest["frozen"]["packaged_runtime"][
        "allowed_system_dependency_prefixes"
    ]
    return any(dependency.startswith(prefix) for prefix in prefixes)


def expand_runtime_token(
    value: str,
    *,
    loader_directory: Path,
    executable_directory: Path,
) -> Path:
    token_roots = {
        "@loader_path": loader_directory,
        "@executable_path": executable_directory,
    }
    for token, root in token_roots.items():
        if value == token:
            return root
        prefix = token + "/"
        if value.startswith(prefix):
            return root / value[len(prefix) :]
    raise VerificationError(f"unsupported packaged Runtime location token: {value}")


def assert_inside_app(app_path: Path, candidate: Path, description: str) -> Path:
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise VerificationError(f"{description} does not resolve: {candidate}: {exc}") from exc
    if not resolved.is_relative_to(app_path.resolve()):
        raise VerificationError(f"{description} resolves outside the App: {resolved}")
    return resolved


def verify_architectures(
    resolved_paths: dict[str, Path], runner: CommandRunner
) -> None:
    for name, artifact in resolved_paths.items():
        output = checked_run(runner, ["file", "-L", str(artifact)]).stdout.strip()
        if "Mach-O 64-bit" not in output or not re.search(r"\barm64\b", output):
            raise VerificationError(f"{name} is not Mach-O arm64: {output}")
        if "x86_64" in output or "universal binary" in output:
            raise VerificationError(f"{name} is not arm64-only: {output}")
    print("[packaged-runtime] required component architecture PASS")


def verify_dependency_closure(
    app_path: Path,
    manifest: dict[str, Any],
    resolved_paths: dict[str, Path],
    runner: CommandRunner,
) -> None:
    components = required_components(manifest)
    filename_to_path = {
        component["bundle_filename"]: resolved_paths[component["name"]]
        for component in components
    }
    cli_component = next(
        component for component in components if component["kind"] == "executable"
    )
    cli_path = resolved_paths[cli_component["name"]]
    executable_directory = cli_path.parent
    required_rpath = manifest["frozen"]["packaged_runtime"]["runtime_rpath"]

    for component in components:
        artifact = resolved_paths[component["name"]]
        rpaths = parse_rpaths(checked_run(runner, ["otool", "-l", str(artifact)]).stdout)
        if rpaths != [required_rpath]:
            raise VerificationError(
                f"{component['name']} LC_RPATH is {rpaths!r}; expected only {required_rpath!r}"
            )

        dependencies = parse_dependencies(
            checked_run(runner, ["otool", "-L", str(artifact)]).stdout
        )
        for dependency in dependencies:
            if is_system_dependency(dependency, manifest):
                continue
            dependency_name = PurePosixPath(dependency).name
            if dependency_name not in filename_to_path:
                raise VerificationError(
                    f"{component['name']} has undeclared non-system dependency: {dependency}"
                )
            if dependency.startswith("@rpath/"):
                suffix = dependency[len("@rpath/") :]
                resolved = False
                for rpath in rpaths:
                    root = expand_runtime_token(
                        rpath,
                        loader_directory=artifact.parent,
                        executable_directory=executable_directory,
                    )
                    candidate = root / suffix
                    if candidate.exists():
                        assert_inside_app(app_path, candidate, "@rpath dependency")
                        resolved = True
                        break
                if not resolved:
                    raise VerificationError(
                        f"{component['name']} @rpath dependency does not resolve in bundle: "
                        f"{dependency}"
                    )
            elif dependency.startswith(("@loader_path", "@executable_path")):
                candidate = expand_runtime_token(
                    dependency,
                    loader_directory=artifact.parent,
                    executable_directory=executable_directory,
                )
                assert_inside_app(app_path, candidate, "relative dependency")
            else:
                raise VerificationError(
                    f"{component['name']} has illegal absolute or relative dependency: "
                    f"{dependency}"
                )
    print("[packaged-runtime] dependency closure and RPath PASS")


def verify_downloader(
    app_path: Path,
    manifest: dict[str, Any],
    runner: CommandRunner,
) -> None:
    for resource in manifest["frozen"]["vendored_resources"]:
        if resource.get("required") is not True:
            continue
        target = app_path.joinpath(*PurePosixPath(resource["bundle_target"]).parts)
        resolve_bundle_file(app_path, target)
        if not os.access(target, os.R_OK | os.X_OK):
            raise VerificationError(f"bundled downloader is not readable/executable: {target}")
        checked_run(runner, ["sh", "-n", str(target)])
    print("[packaged-runtime] downloader PASS")


def verify_model_integrity_resource(
    app_path: Path,
    manifest: dict[str, Any],
) -> None:
    model_integrity = manifest["frozen"]["model_integrity"]
    if model_integrity["required_packaged_resource"] is not True:
        raise VerificationError("model integrity manifest is not a required packaged resource")
    relative = PurePosixPath(model_integrity["manifest_bundle_target"])
    if relative.is_absolute() or ".." in relative.parts:
        raise VerificationError(f"unsafe model manifest bundle path: {relative}")
    target = app_path.joinpath(*relative.parts)
    resolved = resolve_bundle_file(app_path, target)
    try:
        load_model_contract(resolved)
    except RuntimeError as exc:
        raise VerificationError(f"invalid bundled model integrity manifest: {exc}") from exc
    print("[packaged-runtime] model integrity manifest PASS")


def smoke_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for variable in (
        "DYLD_LIBRARY_PATH",
        "DYLD_FALLBACK_LIBRARY_PATH",
        "DYLD_FRAMEWORK_PATH",
        "DYLD_INSERT_LIBRARIES",
    ):
        environment.pop(variable, None)
    return environment


def run_smoke(
    cli_path: Path,
    manifest: dict[str, Any],
    runner: CommandRunner,
) -> None:
    smoke = manifest["frozen"]["whisper_cpp"]["minimal_runtime_smoke"]
    result = runner([str(cli_path), *smoke["arguments"]], env=smoke_environment())
    if result.returncode != smoke["expected_exit_code"]:
        detail = (result.stderr or result.stdout).strip()
        raise VerificationError(
            f"packaged Runtime smoke exited {result.returncode}; "
            f"expected {smoke['expected_exit_code']}"
            + (f"\n{detail}" if detail else "")
        )


def verify_smoke_and_bundle_independence(
    manifest: dict[str, Any],
    logical_paths: dict[str, Path],
    resolved_paths: dict[str, Path],
    runner: CommandRunner,
) -> None:
    smoke = manifest["frozen"]["whisper_cpp"]["minimal_runtime_smoke"]
    cli_name = smoke["component"]
    run_smoke(logical_paths[cli_name], manifest, runner)
    print("[packaged-runtime] bundled whisper-cli smoke PASS")

    with tempfile.TemporaryDirectory(prefix="classroom-runtime-isolation-") as temp:
        isolated_root = Path(temp)
        for component in required_components(manifest):
            destination = isolated_root / component["bundle_filename"]
            shutil.copy2(resolved_paths[component["name"]], destination)
        isolated_cli = isolated_root / next(
            component["bundle_filename"]
            for component in required_components(manifest)
            if component["name"] == cli_name
        )
        isolated_cli.chmod(isolated_cli.stat().st_mode | 0o111)
        run_smoke(isolated_cli, manifest, runner)
    print("[packaged-runtime] isolated Runtime smoke PASS")


def verify_packaged_runtime(
    app_path: Path,
    manifest: dict[str, Any],
    runner: CommandRunner = run_command,
) -> None:
    app_path = app_path.resolve()
    if not app_path.is_dir() or app_path.suffix != ".app":
        raise VerificationError(f"App bundle is missing or invalid: {app_path}")
    logical_paths, resolved_paths = collect_artifacts(app_path, manifest)
    print("[packaged-runtime] required components PASS")
    verify_architectures(resolved_paths, runner)
    verify_dependency_closure(app_path, manifest, resolved_paths, runner)
    verify_downloader(app_path, manifest, runner)
    verify_model_integrity_resource(app_path, manifest)
    checked_run(
        runner,
        ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app_path)],
    )
    print("[packaged-runtime] ad-hoc signature verification PASS")
    verify_smoke_and_bundle_independence(
        manifest, logical_paths, resolved_paths, runner
    )
    print("[packaged-runtime] post-build Runtime verifier PASS")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app_path", type=Path, help="ClassroomTranscriber.app path")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Runtime Manifest path",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    runner: CommandRunner = run_command,
) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        verify_packaged_runtime(
            arguments.app_path, load_manifest(arguments.manifest), runner
        )
    except (KeyError, OSError, VerificationError) as exc:
        print(f"[packaged-runtime] ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
