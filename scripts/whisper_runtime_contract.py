#!/usr/bin/env python3
"""Read and verify the Manifest-backed whisper.cpp Runtime contract."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "packaging" / "runtime_manifest.json"


class ContractError(RuntimeError):
    pass


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def nested_value(value: Any, dotted_path: str) -> Any:
    current = value
    for key in dotted_path.split("."):
        if not isinstance(current, dict) or key not in current:
            raise ContractError(f"manifest key not found: {dotted_path}")
        current = current[key]
    return current


def scalar_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def cmake_value(value: Any) -> str:
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    if not isinstance(value, (str, int, float)):
        raise ContractError(f"unsupported CMake option value: {value!r}")
    return str(value)


def cmake_arguments(manifest: dict[str, Any]) -> list[str]:
    profile = manifest["frozen"]["whisper_cpp"]["build_profile"]
    arguments = [f"-DCMAKE_BUILD_TYPE={profile['build_type']}"]
    arguments.extend(
        f"-D{name}={cmake_value(value)}"
        for name, value in profile["cmake_options"].items()
    )
    return arguments


def run_command(
    arguments: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        arguments,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ContractError(
            f"command failed ({result.returncode}): {' '.join(arguments)}"
            + (f"\n{detail}" if detail else "")
        )
    return result


def parse_cmake_cache(cache_path: Path) -> dict[str, str]:
    if not cache_path.is_file():
        raise ContractError(f"CMake cache is missing: {cache_path}")
    values: dict[str, str] = {}
    for raw_line in cache_path.read_text(encoding="utf-8").splitlines():
        if not raw_line or raw_line.startswith(("//", "#")) or "=" not in raw_line:
            continue
        declaration, value = raw_line.split("=", 1)
        if ":" not in declaration:
            continue
        name, _cache_type = declaration.split(":", 1)
        values[name] = value
    return values


def cmake_cache_matches(actual: str | None, expected: Any) -> bool:
    if actual is None:
        return False
    if isinstance(expected, bool):
        truthy = {"1", "ON", "TRUE", "YES", "Y"}
        falsy = {"0", "OFF", "FALSE", "NO", "N", "IGNORE", "NOTFOUND", ""}
        normalized = actual.upper()
        return normalized in (truthy if expected else falsy)
    return actual == str(expected)


def validate_source_repository(manifest: dict[str, Any]) -> Path:
    whisper = manifest["frozen"]["whisper_cpp"]
    source_root = REPO_ROOT / whisper["local_rebuild_root_path"]
    if not source_root.is_dir():
        raise ContractError(f"whisper.cpp source is missing: {source_root}")

    inside = run_command(
        ["git", "-C", str(source_root), "rev-parse", "--is-inside-work-tree"]
    ).stdout.strip()
    if inside != "true":
        raise ContractError(f"whisper.cpp path is not a Git worktree: {source_root}")

    remote = run_command(
        ["git", "-C", str(source_root), "remote", "get-url", "origin"]
    ).stdout.strip()
    if remote.rstrip("/") != whisper["repository"].rstrip("/"):
        raise ContractError(
            f"unexpected whisper.cpp origin: {remote}; expected {whisper['repository']}"
        )

    status = run_command(
        [
            "git",
            "-C",
            str(source_root),
            "status",
            "--porcelain",
            "--untracked-files=all",
        ]
    ).stdout.strip()
    if status:
        raise ContractError(f"whisper.cpp worktree is not clean:\n{status}")

    head = run_command(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"]
    ).stdout.strip()
    if head != whisper["commit"]:
        raise ContractError(
            f"whisper.cpp HEAD is {head}; expected pinned {whisper['commit']}"
        )

    symbolic = run_command(
        ["git", "-C", str(source_root), "symbolic-ref", "-q", "HEAD"],
        check=False,
    )
    if symbolic.returncode == 0:
        raise ContractError(
            f"whisper.cpp must be detached at the pinned commit, not {symbolic.stdout.strip()}"
        )
    return source_root


def validate_cmake_cache(
    manifest: dict[str, Any], source_root: Path
) -> dict[str, str]:
    profile = manifest["frozen"]["whisper_cpp"]["build_profile"]
    cache = parse_cmake_cache(source_root / "build" / "CMakeCache.txt")

    expected_values: dict[str, Any] = {
        "CMAKE_BUILD_TYPE": profile["build_type"],
        **profile["cmake_options"],
    }
    for name, expected in expected_values.items():
        actual = cache.get(name)
        if not cmake_cache_matches(actual, expected):
            raise ContractError(
                f"CMake cache mismatch for {name}: {actual!r}; expected {expected!r}"
            )

    generator = cache.get("CMAKE_GENERATOR")
    if generator != profile["cmake_generator"]:
        raise ContractError(
            f"CMake generator is {generator!r}; expected {profile['cmake_generator']!r}"
        )
    return cache


def parse_dependencies(otool_output: str) -> list[str]:
    dependencies = []
    for line in otool_output.splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        dependencies.append(stripped.split(" (", 1)[0])
    return dependencies


def parse_rpaths(otool_output: str) -> list[str]:
    lines = otool_output.splitlines()
    rpaths = []
    for index, line in enumerate(lines):
        if line.strip() != "cmd LC_RPATH":
            continue
        for candidate in lines[index + 1 : index + 7]:
            match = re.match(r"\s*path (.+) \(offset \d+\)\s*$", candidate)
            if match:
                rpaths.append(match.group(1))
                break
    return rpaths


def validate_dependency_path(dependency: str) -> None:
    allowed_prefixes = (
        "@rpath/",
        "@loader_path/",
        "@executable_path/",
        "/usr/lib/",
        "/System/Library/",
    )
    if not dependency.startswith(allowed_prefixes):
        raise ContractError(f"unexpected dynamic dependency path: {dependency}")


def verify_runtime(manifest: dict[str, Any]) -> None:
    source_root = validate_source_repository(manifest)
    validate_cmake_cache(manifest, source_root)

    components = manifest["frozen"]["runtime_components"]
    artifact_paths: dict[str, Path] = {}
    for component in components:
        artifact = REPO_ROOT / component["source_path"]
        if not artifact.exists() or not artifact.is_file():
            raise ContractError(
                f"required Runtime artifact is missing: {component['source_path']}"
            )
        artifact_paths[component["name"]] = artifact

        file_output = run_command(["file", "-L", str(artifact)]).stdout.strip()
        if "Mach-O 64-bit" not in file_output or not re.search(r"\barm64\b", file_output):
            raise ContractError(
                f"Runtime artifact is not Mach-O arm64: {component['source_path']}\n"
                f"{file_output}"
            )
        if "x86_64" in file_output or "universal binary" in file_output:
            raise ContractError(
                f"Runtime artifact is not arm64-only: {component['source_path']}\n"
                f"{file_output}"
            )
        print(f"[whisper-contract] architecture PASS: {file_output}")

        dependency_output = run_command(["otool", "-L", str(artifact)]).stdout
        for dependency in parse_dependencies(dependency_output):
            validate_dependency_path(dependency)

    cli_path = artifact_paths["whisper-cli"]
    cli_dependency_output = run_command(["otool", "-L", str(cli_path)]).stdout
    cli_dependencies = set(parse_dependencies(cli_dependency_output))
    required_abi_names = {
        component["abi_filename"]
        for component in components
        if component["kind"] == "dynamic_library"
    }
    for abi_name in required_abi_names:
        expected_reference = f"@rpath/{abi_name}"
        if expected_reference not in cli_dependencies:
            raise ContractError(
                f"whisper-cli dependency is missing: {expected_reference}"
            )

    build_root = (source_root / "build").resolve()
    cli_rpaths = parse_rpaths(
        run_command(["otool", "-l", str(cli_path)]).stdout
    )
    if not cli_rpaths:
        raise ContractError("whisper-cli declares no LC_RPATH entries")
    for rpath in cli_rpaths:
        if rpath.startswith("@"):
            continue
        path = Path(rpath)
        if not path.is_absolute() or not path.resolve().is_relative_to(build_root):
            raise ContractError(f"unexpected source-build LC_RPATH: {rpath}")

    print("[whisper-contract] whisper-cli dependency closure PASS")
    print(
        "[whisper-contract] source-build RPaths: " + ", ".join(cli_rpaths)
    )

    smoke = manifest["frozen"]["whisper_cpp"]["minimal_runtime_smoke"]
    smoke_path = artifact_paths[smoke["component"]]
    smoke_command = [str(smoke_path), *smoke["arguments"]]
    smoke_result = run_command(smoke_command, check=False)
    if smoke_result.returncode != smoke["expected_exit_code"]:
        detail = (smoke_result.stderr or smoke_result.stdout).strip()
        raise ContractError(
            f"Runtime smoke exited {smoke_result.returncode}; "
            f"expected {smoke['expected_exit_code']}"
            + (f"\n{detail}" if detail else "")
        )
    print(
        "[whisper-contract] runtime smoke PASS: "
        + " ".join([smoke["component"], *smoke["arguments"]])
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    get_parser = subparsers.add_parser("get", help="print a Manifest value")
    get_parser.add_argument("path", help="dot-separated Manifest key path")

    subparsers.add_parser(
        "cmake-arguments",
        help="print one Manifest-derived CMake -D argument per line",
    )
    subparsers.add_parser(
        "artifact-records",
        help="print one JSON Runtime component record per line",
    )
    subparsers.add_parser(
        "verify-runtime",
        help="verify the existing source/build Runtime without modifying it",
    )
    return parser


def main() -> int:
    parser = build_parser()
    arguments = parser.parse_args()
    try:
        manifest = load_manifest()
        if arguments.command == "get":
            print(scalar_text(nested_value(manifest, arguments.path)))
        elif arguments.command == "cmake-arguments":
            print(*cmake_arguments(manifest), sep="\n")
        elif arguments.command == "artifact-records":
            for component in manifest["frozen"]["runtime_components"]:
                print(json.dumps(component, sort_keys=True, separators=(",", ":")))
        elif arguments.command == "verify-runtime":
            verify_runtime(manifest)
        else:  # pragma: no cover - argparse enforces this branch is unreachable.
            parser.error(f"unsupported command: {arguments.command}")
    except ContractError as exc:
        print(f"[whisper-contract] ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
