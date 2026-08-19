"""Manifest-backed integrity and atomic publish helpers for downloadable models."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from resource_paths import default_model_manifest_path


HASH_CHUNK_SIZE = 8 * 1024 * 1024


class ModelIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelMetadata:
    name: str
    filename: str
    expected_size_bytes: int
    sha256: str
    upstream_blob_id: str
    immutable_artifact_url: str


@dataclass(frozen=True)
class ModelContract:
    path: Path
    schema_version: str
    upstream_revision: str
    metadata_api_url: str
    staging_directory_prefix: str
    verification_receipt_suffix: str
    models: tuple[ModelMetadata, ...]

    @property
    def by_name(self) -> dict[str, ModelMetadata]:
        return {model.name: model for model in self.models}

    @property
    def by_filename(self) -> dict[str, ModelMetadata]:
        return {model.filename: model for model in self.models}


@dataclass(frozen=True)
class ModelVerification:
    valid: bool
    reason: str
    actual_size_bytes: int = 0
    actual_sha256: str = ""


@dataclass(frozen=True)
class ModelDownloadResult:
    model_name: str
    path: Path
    disposition: str


DownloadIntoStaging = Callable[
    [ModelMetadata, Path, Callable[[str], None] | None], int
]


def _require_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ModelIntegrityError(f"model manifest field must be a non-empty string: {key}")
    return value


def validate_model_manifest_data(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ModelIntegrityError("model manifest root must be an object")
    _require_string(data, "schema_version")
    if data.get("status") != "frozen":
        raise ModelIntegrityError("model manifest status must be frozen")
    if data.get("integrity_algorithm") != "sha256":
        raise ModelIntegrityError("model manifest integrity_algorithm must be sha256")

    upstream = data.get("upstream")
    if not isinstance(upstream, dict):
        raise ModelIntegrityError("model manifest upstream must be an object")
    repository = _require_string(upstream, "repository")
    revision = _require_string(upstream, "repository_revision")
    metadata_api_url = _require_string(upstream, "metadata_api_url")
    _require_string(upstream, "metadata_kind")
    _require_string(upstream, "validation_policy")
    immutable_template = _require_string(upstream, "immutable_artifact_url_template")
    downloader_template = _require_string(upstream, "vendored_downloader_url_template")
    if repository != "https://huggingface.co/ggerganov/whisper.cpp":
        raise ModelIntegrityError("unexpected model upstream repository")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ModelIntegrityError("upstream repository_revision must be 40-char hex")
    if revision not in metadata_api_url or "{filename}" not in immutable_template:
        raise ModelIntegrityError("model provenance URLs are not revision-pinned templates")
    if revision not in immutable_template or "{filename}" not in downloader_template:
        raise ModelIntegrityError("model download URL templates are incomplete")

    transaction = data.get("transaction")
    if not isinstance(transaction, dict):
        raise ModelIntegrityError("model manifest transaction must be an object")
    staging_prefix = _require_string(transaction, "staging_directory_prefix")
    receipt_suffix = _require_string(transaction, "verification_receipt_suffix")
    _require_string(transaction, "publish_method")
    _require_string(transaction, "scan_policy")
    _require_string(transaction, "retry_policy")
    _require_string(transaction, "custom_import_policy")
    if not staging_prefix.startswith(".") or "/" in staging_prefix:
        raise ModelIntegrityError("staging directory prefix must be a hidden filename prefix")
    if not receipt_suffix.startswith(".") or "/" in receipt_suffix:
        raise ModelIntegrityError("verification receipt suffix must be a filename suffix")

    models = data.get("models")
    if not isinstance(models, list) or not models:
        raise ModelIntegrityError("model manifest must contain models")
    names: set[str] = set()
    filenames: set[str] = set()
    for model in models:
        if not isinstance(model, dict):
            raise ModelIntegrityError("model manifest entries must be objects")
        name = _require_string(model, "name")
        filename = _require_string(model, "filename")
        sha256 = _require_string(model, "sha256")
        blob_id = _require_string(model, "upstream_blob_id")
        artifact_url = _require_string(model, "immutable_artifact_url")
        expected_size = model.get("expected_size_bytes")
        if name in names:
            raise ModelIntegrityError(f"duplicate downloadable model name: {name}")
        if filename in filenames:
            raise ModelIntegrityError(f"duplicate downloadable model filename: {filename}")
        if Path(filename).name != filename or not filename.startswith("ggml-") or not filename.endswith(".bin"):
            raise ModelIntegrityError(f"unsafe downloadable model filename: {filename}")
        if not isinstance(expected_size, int) or expected_size <= 0:
            raise ModelIntegrityError(f"invalid expected size for {name}")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ModelIntegrityError(f"invalid SHA-256 for {name}")
        if not re.fullmatch(r"[0-9a-f]{40}", blob_id):
            raise ModelIntegrityError(f"invalid upstream blob id for {name}")
        expected_url = immutable_template.format(filename=filename)
        if artifact_url != expected_url:
            raise ModelIntegrityError(f"immutable artifact URL mismatch for {name}")
        names.add(name)
        filenames.add(filename)


def load_model_contract(path: Path | None = None) -> ModelContract:
    manifest_path = Path(path or default_model_manifest_path())
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelIntegrityError(f"cannot load model manifest: {manifest_path}: {exc}") from exc
    validate_model_manifest_data(data)
    upstream = data["upstream"]
    transaction = data["transaction"]
    models = tuple(
        ModelMetadata(
            name=model["name"],
            filename=model["filename"],
            expected_size_bytes=model["expected_size_bytes"],
            sha256=model["sha256"],
            upstream_blob_id=model["upstream_blob_id"],
            immutable_artifact_url=model["immutable_artifact_url"],
        )
        for model in data["models"]
    )
    return ModelContract(
        path=manifest_path,
        schema_version=data["schema_version"],
        upstream_revision=upstream["repository_revision"],
        metadata_api_url=upstream["metadata_api_url"],
        staging_directory_prefix=transaction["staging_directory_prefix"],
        verification_receipt_suffix=transaction["verification_receipt_suffix"],
        models=models,
    )


def metadata_for_model(model_name: str, contract: ModelContract) -> ModelMetadata:
    try:
        return contract.by_name[model_name]
    except KeyError as exc:
        raise ModelIntegrityError(
            f"downloadable model has no integrity metadata: {model_name}"
        ) from exc


def verify_model_file(path: Path, metadata: ModelMetadata) -> ModelVerification:
    path = Path(path)
    if not path.exists():
        return ModelVerification(False, "model file is missing")
    if not path.is_file():
        return ModelVerification(False, "model path is not a file")
    try:
        size = path.stat().st_size
    except OSError as exc:
        return ModelVerification(False, f"cannot stat model file: {exc}")
    if size != metadata.expected_size_bytes:
        return ModelVerification(
            False,
            f"size mismatch: expected {metadata.expected_size_bytes}, got {size}",
            actual_size_bytes=size,
        )

    digest = hashlib.sha256()
    try:
        with path.open("rb") as model_file:
            while chunk := model_file.read(HASH_CHUNK_SIZE):
                digest.update(chunk)
    except OSError as exc:
        return ModelVerification(False, f"cannot read model file: {exc}", size)
    actual_sha256 = digest.hexdigest()
    if actual_sha256 != metadata.sha256:
        return ModelVerification(
            False,
            f"SHA-256 mismatch: expected {metadata.sha256}, got {actual_sha256}",
            actual_size_bytes=size,
            actual_sha256=actual_sha256,
        )
    return ModelVerification(True, "size and SHA-256 match", size, actual_sha256)


def verification_receipt_path(
    model_path: Path, contract: ModelContract
) -> Path:
    model_path = Path(model_path)
    return model_path.parent / (
        f".{model_path.name}{contract.verification_receipt_suffix}"
    )


def _receipt_payload(
    model_path: Path,
    metadata: ModelMetadata,
    contract: ModelContract,
) -> dict[str, Any]:
    stat_result = model_path.stat()
    return {
        "schema_version": "1.0.0",
        "model_name": metadata.name,
        "filename": metadata.filename,
        "expected_size_bytes": metadata.expected_size_bytes,
        "sha256": metadata.sha256,
        "upstream_revision": contract.upstream_revision,
        "file_size_bytes": stat_result.st_size,
        "file_mtime_ns": stat_result.st_mtime_ns,
    }


def write_verification_receipt(
    model_path: Path,
    metadata: ModelMetadata,
    contract: ModelContract,
) -> Path:
    receipt_path = verification_receipt_path(model_path, contract)
    temporary_path = receipt_path.parent / (
        f".{receipt_path.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with temporary_path.open("x", encoding="utf-8") as receipt_file:
            json.dump(
                _receipt_payload(model_path, metadata, contract),
                receipt_file,
                indent=2,
                sort_keys=True,
            )
            receipt_file.write("\n")
            receipt_file.flush()
            os.fsync(receipt_file.fileno())
        os.replace(temporary_path, receipt_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return receipt_path


def has_current_verification_receipt(
    model_path: Path,
    metadata: ModelMetadata,
    contract: ModelContract,
) -> bool:
    model_path = Path(model_path)
    receipt_path = verification_receipt_path(model_path, contract)
    if not model_path.is_file() or not receipt_path.is_file():
        return False
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        return receipt == _receipt_payload(model_path, metadata, contract)
    except (OSError, json.JSONDecodeError):
        return False


def downloaded_model_status(
    model_path: Path,
    metadata: ModelMetadata,
    contract: ModelContract,
) -> str:
    model_path = Path(model_path)
    if not model_path.exists():
        return "missing"
    if not model_path.is_file():
        return "not a file"
    if model_path.stat().st_size != metadata.expected_size_bytes:
        return "integrity invalid"
    if has_current_verification_receipt(model_path, metadata, contract):
        return "available"
    receipt_path = verification_receipt_path(model_path, contract)
    return "integrity invalid" if receipt_path.exists() else "integrity unverified"


def remove_stale_staging_directories(
    target_dir: Path,
    contract: ModelContract,
    log_callback: Callable[[str], None] | None = None,
) -> None:
    target_dir = Path(target_dir)
    for candidate in target_dir.iterdir():
        if not candidate.name.startswith(contract.staging_directory_prefix):
            continue
        if candidate.is_symlink() or not candidate.is_dir():
            candidate.unlink(missing_ok=True)
        else:
            shutil.rmtree(candidate)
        if log_callback:
            log_callback(f"Removed stale model download staging: {candidate.name}")


def execute_model_download(
    model_name: str,
    target_dir: Path,
    downloader: DownloadIntoStaging,
    *,
    contract: ModelContract | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> ModelDownloadResult:
    contract = contract or load_model_contract()
    metadata = metadata_for_model(model_name, contract)
    target_dir = Path(target_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    if not target_dir.is_dir():
        raise ModelIntegrityError(f"model download target is not a directory: {target_dir}")

    remove_stale_staging_directories(target_dir, contract, log_callback)
    final_path = target_dir / metadata.filename
    receipt_path = verification_receipt_path(final_path, contract)
    if final_path.exists():
        if has_current_verification_receipt(final_path, metadata, contract):
            if log_callback:
                log_callback(f"Model integrity already verified: {final_path}")
            return ModelDownloadResult(model_name, final_path, "reused")
        verification = verify_model_file(final_path, metadata)
        if verification.valid:
            write_verification_receipt(final_path, metadata, contract)
            if log_callback:
                log_callback(f"Existing model verified and reused: {final_path}")
            return ModelDownloadResult(model_name, final_path, "reused")
        receipt_path.unlink(missing_ok=True)
        if log_callback:
            log_callback(f"Existing model is invalid and will be replaced: {verification.reason}")
    else:
        receipt_path.unlink(missing_ok=True)

    free_bytes = shutil.disk_usage(target_dir).free
    if free_bytes < metadata.expected_size_bytes:
        raise ModelIntegrityError(
            "insufficient free space for staged model download: "
            f"need {metadata.expected_size_bytes} bytes, have {free_bytes} bytes"
        )

    with tempfile.TemporaryDirectory(
        prefix=contract.staging_directory_prefix,
        dir=target_dir,
    ) as staging:
        staging_dir = Path(staging)
        if log_callback:
            log_callback(f"Downloading into isolated staging directory: {staging_dir.name}")
        try:
            return_code = downloader(metadata, staging_dir, log_callback)
        except Exception as exc:
            raise ModelIntegrityError(f"model downloader failed: {exc}") from exc
        if return_code != 0:
            raise ModelIntegrityError(
                f"model downloader failed with exit code {return_code}"
            )

        staged_path = staging_dir / metadata.filename
        verification = verify_model_file(staged_path, metadata)
        if not verification.valid:
            raise ModelIntegrityError(
                f"downloaded model integrity validation failed: {verification.reason}"
            )
        if log_callback:
            log_callback("Model size and SHA-256 validation PASS")

        os.replace(staged_path, final_path)
        write_verification_receipt(final_path, metadata, contract)

    if log_callback:
        log_callback(f"Atomic model publish PASS: {final_path}")
    return ModelDownloadResult(model_name, final_path, "downloaded")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the downloadable model integrity contract."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=default_model_manifest_path(),
        help="model manifest path",
    )
    arguments = parser.parse_args(argv)
    try:
        contract = load_model_contract(arguments.manifest)
    except ModelIntegrityError as exc:
        print(f"[model-integrity] ERROR: {exc}")
        return 1
    print(
        "[model-integrity] model metadata validation PASS: "
        f"{len(contract.models)} models at upstream revision {contract.upstream_revision}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
