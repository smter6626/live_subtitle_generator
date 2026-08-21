#!/usr/bin/env python3
"""Build the repository-owned macOS App icon from its approved source artwork."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = REPO_ROOT / "packaging" / "runtime_manifest.json"
ICONUTIL_PATH = Path("/usr/bin/iconutil")
MASTER_ICON_SIZE = 1024
LIGHT_MATTE_THRESHOLD = 220
LIGHT_MATTE_FLOOR = 4


class IconBuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppIconContract:
    source_path: Path
    generated_icns_path: Path
    source_sha256: str
    minimum_source_pixels: int
    bundle_filename: str
    bundle_target: PurePosixPath


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative_path(value: str, description: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise IconBuildError(f"{description} must be a safe repository-relative path")
    return path


def contract_from_manifest(
    manifest: dict[str, Any], *, repo_root: Path = REPO_ROOT
) -> AppIconContract:
    raw = manifest["frozen"]["app_icon"]
    if raw.get("required") is not True:
        raise IconBuildError("Manifest App icon must be required")
    source_relative = _relative_path(raw["source_path"], "App icon source_path")
    generated_relative = _relative_path(
        raw["generated_icns_path"], "App icon generated_icns_path"
    )
    bundle_target = _relative_path(raw["bundle_target"], "App icon bundle_target")
    bundle_filename = raw["bundle_filename"]
    if PurePosixPath(bundle_filename).name != bundle_filename:
        raise IconBuildError("Manifest App icon bundle_filename must be a filename")
    if generated_relative.name != bundle_filename or bundle_target.name != bundle_filename:
        raise IconBuildError("Manifest App icon filenames do not agree")
    return AppIconContract(
        source_path=repo_root.joinpath(*source_relative.parts),
        generated_icns_path=repo_root.joinpath(*generated_relative.parts),
        source_sha256=raw["source_sha256"],
        minimum_source_pixels=int(raw["minimum_source_pixels"]),
        bundle_filename=bundle_filename,
        bundle_target=bundle_target,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_source_image(contract: AppIconContract) -> QImage:
    if not contract.source_path.is_file():
        raise IconBuildError(f"App icon source is missing: {contract.source_path}")
    actual_digest = sha256_file(contract.source_path)
    if actual_digest != contract.source_sha256:
        raise IconBuildError(
            "App icon source SHA-256 mismatch: "
            f"expected {contract.source_sha256}, got {actual_digest}"
        )
    image = QImage(str(contract.source_path))
    if image.isNull():
        raise IconBuildError(f"App icon source is not a readable image: {contract.source_path}")
    if image.width() != image.height():
        raise IconBuildError(
            f"App icon source must be square, got {image.width()}x{image.height()}"
        )
    if image.width() < contract.minimum_source_pixels:
        raise IconBuildError(
            "App icon source is too small: "
            f"{image.width()}px; expected at least {contract.minimum_source_pixels}px"
        )
    return image


def _connected_light_matte_mask(difference: np.ndarray) -> np.ndarray:
    height, width = difference.shape
    eligible = (difference < LIGHT_MATTE_THRESHOLD).ravel()
    visited = bytearray(width * height)
    queue: deque[int] = deque()

    def enqueue(index: int) -> None:
        if eligible[index] and not visited[index]:
            visited[index] = 1
            queue.append(index)

    for x in range(width):
        enqueue(x)
        enqueue((height - 1) * width + x)
    for y in range(1, height - 1):
        enqueue(y * width)
        enqueue(y * width + width - 1)

    while queue:
        index = queue.popleft()
        x = index % width
        if index >= width:
            enqueue(index - width)
        if index < (height - 1) * width:
            enqueue(index + width)
        if x:
            enqueue(index - 1)
        if x < width - 1:
            enqueue(index + 1)

    return np.frombuffer(visited, dtype=np.uint8).reshape(height, width).astype(bool)


def remove_connected_light_matte(image: QImage) -> QImage:
    if image.hasAlphaChannel():
        return image.convertToFormat(QImage.Format.Format_RGBA8888)

    result = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = result.width(), result.height()
    pixels = np.frombuffer(result.bits(), dtype=np.uint8).reshape(
        height, result.bytesPerLine()
    )[:, : width * 4].reshape(height, width, 4)
    rgb = pixels[:, :, :3].copy()
    difference = 255 - rgb.min(axis=2)
    exterior = _connected_light_matte_mask(difference)
    if exterior[height // 2, width // 2]:
        raise IconBuildError("light-matte detection reached the App icon foreground")

    alpha = np.clip(
        np.rint(
            (difference.astype(np.float32) - LIGHT_MATTE_FLOOR)
            * 255.0
            / (LIGHT_MATTE_THRESHOLD - LIGHT_MATTE_FLOOR)
        ),
        0,
        255,
    ).astype(np.uint8)
    nonzero_alpha = alpha > 0
    for channel in range(3):
        values = rgb[:, :, channel].astype(np.float32)
        recovered = np.zeros_like(values)
        recovered[nonzero_alpha] = 255.0 - (
            (255.0 - values[nonzero_alpha]) * 255.0 / alpha[nonzero_alpha]
        )
        pixels[:, :, channel][exterior] = np.clip(
            np.rint(recovered[exterior]), 0, 255
        ).astype(np.uint8)
    pixels[:, :, 3][exterior] = alpha[exterior]
    return result


def render_master_icon(source: QImage) -> QImage:
    normalized = remove_connected_light_matte(source)
    return normalized.scaled(
        MASTER_ICON_SIZE,
        MASTER_ICON_SIZE,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def write_iconset(master: QImage, iconset_path: Path) -> None:
    sizes = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }
    iconset_path.mkdir(parents=True)
    for filename, size in sizes.items():
        image = master.scaled(
            size,
            size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        destination = iconset_path / filename
        if not image.save(str(destination), "PNG"):
            raise IconBuildError(f"failed to write App icon size: {destination}")


def verify_icns(path: Path) -> None:
    if not path.is_file():
        raise IconBuildError(f"generated App icon is missing: {path}")
    with path.open("rb") as handle:
        header = handle.read(8)
    if len(header) != 8 or header[:4] != b"icns":
        raise IconBuildError(f"generated App icon has an invalid ICNS header: {path}")
    declared_size = int.from_bytes(header[4:], "big")
    if declared_size != path.stat().st_size:
        raise IconBuildError(
            f"generated App icon length mismatch: header={declared_size}, "
            f"file={path.stat().st_size}"
        )


def generate_icns(source: QImage, destination: Path) -> None:
    if sys.platform != "darwin" or not ICONUTIL_PATH.is_file():
        raise IconBuildError("App icon generation requires macOS /usr/bin/iconutil")
    destination.parent.mkdir(parents=True, exist_ok=True)
    master = render_master_icon(source)
    with tempfile.TemporaryDirectory(prefix="classroom-app-icon-") as temp:
        iconset_path = Path(temp) / "ClassroomTranscriber.iconset"
        write_iconset(master, iconset_path)
        result = subprocess.run(
            [str(ICONUTIL_PATH), "-c", "icns", str(iconset_path), "-o", str(destination)],
            check=False,
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise IconBuildError(
            f"iconutil failed ({result.returncode})" + (f": {detail}" if detail else "")
        )
    verify_icns(destination)


def build_app_icon(
    manifest_path: Path = DEFAULT_MANIFEST_PATH, *, repo_root: Path = REPO_ROOT
) -> Path:
    contract = contract_from_manifest(load_manifest(manifest_path), repo_root=repo_root)
    source = load_source_image(contract)
    generate_icns(source, contract.generated_icns_path)
    return contract.generated_icns_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Runtime Manifest path",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        output = build_app_icon(arguments.manifest)
    except (KeyError, OSError, ValueError, IconBuildError) as exc:
        print(f"[app-icon] ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"[app-icon] generated {output.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
