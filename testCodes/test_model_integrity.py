import hashlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

from model_integrity import (  # noqa: E402
    ModelIntegrityError,
    downloaded_model_status,
    execute_model_download,
    load_model_contract,
    verification_receipt_path,
    verify_model_file,
)
from model_manager import (  # noqa: E402
    DOWNLOADABLE_MODELS,
    download_and_publish_model,
    scan_model_dirs,
)
from settings import MIN_MODEL_FILE_SIZE_BYTES  # noqa: E402


MODEL_MANIFEST_PATH = REPO_ROOT / "packaging" / "model_manifest.json"
EXPECTED_DOWNLOADABLE_MODELS = (
    "large-v3",
    "large-v3-turbo",
    "medium.en",
    "small.en",
    "base.en",
)
FIXTURE_PAYLOAD = b"Classroom Transcriber verified model fixture\n"


def write_fixture_contract(root: Path, payload: bytes = FIXTURE_PAYLOAD):
    revision = "a" * 40
    filename = "ggml-base.en.bin"
    data = {
        "schema_version": "1.0.0",
        "status": "frozen",
        "integrity_algorithm": "sha256",
        "upstream": {
            "repository": "https://huggingface.co/ggerganov/whisper.cpp",
            "repository_revision": revision,
            "metadata_api_url": (
                "https://huggingface.co/api/models/ggerganov/whisper.cpp/"
                f"revision/{revision}?blobs=true"
            ),
            "metadata_kind": "official Hugging Face model repository blob and LFS metadata",
            "vendored_downloader_url_template": (
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{filename}"
            ),
            "immutable_artifact_url_template": (
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/"
                f"{revision}/{{filename}}"
            ),
            "validation_policy": "fixture validates exact size and SHA-256",
        },
        "transaction": {
            "staging_directory_prefix": ".classroom-model-download-",
            "verification_receipt_suffix": ".integrity.json",
            "publish_method": "os.replace from staging",
            "scan_policy": "receipt required",
            "retry_policy": "remove stale staging before retry",
            "custom_import_policy": "explicit imports remain supported",
        },
        "models": [
            {
                "name": "base.en",
                "filename": filename,
                "expected_size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "upstream_blob_id": "b" * 40,
                "immutable_artifact_url": (
                    "https://huggingface.co/ggerganov/whisper.cpp/resolve/"
                    f"{revision}/{filename}"
                ),
            }
        ],
    }
    path = root / "model_manifest.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return load_model_contract(path)


class ModelIntegrityContractTests(unittest.TestCase):
    def test_official_metadata_is_complete_unique_and_matches_downloadable_models(self):
        contract = load_model_contract(MODEL_MANIFEST_PATH)
        self.assertEqual(tuple(model.name for model in contract.models), DOWNLOADABLE_MODELS)
        self.assertEqual(DOWNLOADABLE_MODELS, EXPECTED_DOWNLOADABLE_MODELS)
        self.assertEqual(len({model.name for model in contract.models}), len(contract.models))
        self.assertEqual(
            len({model.filename for model in contract.models}), len(contract.models)
        )
        self.assertRegex(contract.upstream_revision, re.compile(r"^[0-9a-f]{40}$"))
        self.assertIn(contract.upstream_revision, contract.metadata_api_url)
        for model in contract.models:
            with self.subTest(model=model.name):
                self.assertGreater(model.expected_size_bytes, 0)
                self.assertRegex(model.sha256, re.compile(r"^[0-9a-f]{64}$"))
                self.assertIn(contract.upstream_revision, model.immutable_artifact_url)
                self.assertTrue(model.immutable_artifact_url.endswith(model.filename))

    def test_success_stages_validates_atomically_publishes_and_becomes_available(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = write_fixture_contract(root)
            target_dir = root / "models"
            final_path = target_dir / "ggml-base.en.bin"
            observations = []

            def runner(command, cwd=None, log_callback=None):
                staging_dir = Path(cwd)
                observations.append((list(command), staging_dir.name, final_path.exists()))
                (staging_dir / final_path.name).write_bytes(FIXTURE_PAYLOAD)
                return 0

            result = download_and_publish_model(
                "base.en",
                target_dir,
                contract=contract,
                command_runner=runner,
            )
            self.assertEqual(result.disposition, "downloaded")
            self.assertEqual(result.path, final_path)
            self.assertEqual(final_path.read_bytes(), FIXTURE_PAYLOAD)
            self.assertTrue(verification_receipt_path(final_path, contract).is_file())
            self.assertEqual(observations[0][2], False)
            self.assertTrue(observations[0][1].startswith(contract.staging_directory_prefix))
            self.assertFalse(
                any(
                    path.name.startswith(contract.staging_directory_prefix)
                    for path in target_dir.iterdir()
                )
            )
            models = scan_model_dirs(
                [target_dir],
                download_model_dir=target_dir,
                contract=contract,
            )
            matching = [
                model
                for model in models
                if model.path.resolve() == final_path.resolve()
            ]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0].status, "available")

    def test_downloader_failure_and_partial_never_publish_final(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = write_fixture_contract(root)
            target_dir = root / "models"
            final_path = target_dir / "ggml-base.en.bin"

            def failed_downloader(_metadata, staging_dir, _log_callback):
                (staging_dir / final_path.name).write_bytes(FIXTURE_PAYLOAD[:8])
                return 23

            with self.assertRaisesRegex(ModelIntegrityError, "exit code 23"):
                execute_model_download(
                    "base.en", target_dir, failed_downloader, contract=contract
                )
            self.assertFalse(final_path.exists())
            self.assertEqual(list(target_dir.iterdir()), [])

    def test_checksum_mismatch_never_publishes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = write_fixture_contract(root)
            target_dir = root / "models"
            final_path = target_dir / "ggml-base.en.bin"
            bad_payload = b"X" + FIXTURE_PAYLOAD[1:]

            def corrupt_downloader(_metadata, staging_dir, _log_callback):
                (staging_dir / final_path.name).write_bytes(bad_payload)
                return 0

            with self.assertRaisesRegex(ModelIntegrityError, "SHA-256 mismatch"):
                execute_model_download(
                    "base.en", target_dir, corrupt_downloader, contract=contract
                )
            self.assertFalse(final_path.exists())

    def test_size_mismatch_never_publishes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = write_fixture_contract(root)
            target_dir = root / "models"
            final_path = target_dir / "ggml-base.en.bin"

            def short_downloader(_metadata, staging_dir, _log_callback):
                (staging_dir / final_path.name).write_bytes(FIXTURE_PAYLOAD[:-1])
                return 0

            with self.assertRaisesRegex(ModelIntegrityError, "size mismatch"):
                execute_model_download(
                    "base.en", target_dir, short_downloader, contract=contract
                )
            self.assertFalse(final_path.exists())

    def test_existing_corrupt_final_is_not_available_and_retry_repairs_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = write_fixture_contract(root)
            target_dir = root / "models"
            target_dir.mkdir()
            final_path = target_dir / "ggml-base.en.bin"
            final_path.write_bytes(b"X" + FIXTURE_PAYLOAD[1:])
            self.assertNotEqual(
                downloaded_model_status(final_path, contract.models[0], contract),
                "available",
            )

            def repaired_downloader(_metadata, staging_dir, _log_callback):
                (staging_dir / final_path.name).write_bytes(FIXTURE_PAYLOAD)
                return 0

            result = execute_model_download(
                "base.en", target_dir, repaired_downloader, contract=contract
            )
            self.assertEqual(result.disposition, "downloaded")
            self.assertTrue(verify_model_file(final_path, contract.models[0]).valid)
            self.assertEqual(
                downloaded_model_status(final_path, contract.models[0], contract),
                "available",
            )

    def test_existing_valid_final_is_verified_reused_and_not_downloaded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = write_fixture_contract(root)
            target_dir = root / "models"
            target_dir.mkdir()
            final_path = target_dir / "ggml-base.en.bin"
            final_path.write_bytes(FIXTURE_PAYLOAD)
            calls = []

            def forbidden_downloader(*_args):
                calls.append(True)
                return 0

            result = execute_model_download(
                "base.en", target_dir, forbidden_downloader, contract=contract
            )
            self.assertEqual(result.disposition, "reused")
            self.assertEqual(calls, [])
            self.assertTrue(verification_receipt_path(final_path, contract).is_file())

    def test_first_failure_then_retry_success_recovers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = write_fixture_contract(root)
            target_dir = root / "models"
            final_path = target_dir / "ggml-base.en.bin"
            attempt = 0

            def retrying_downloader(_metadata, staging_dir, _log_callback):
                nonlocal attempt
                attempt += 1
                if attempt == 1:
                    (staging_dir / final_path.name).write_bytes(FIXTURE_PAYLOAD[:5])
                    return 9
                (staging_dir / final_path.name).write_bytes(FIXTURE_PAYLOAD)
                return 0

            with self.assertRaises(ModelIntegrityError):
                execute_model_download(
                    "base.en", target_dir, retrying_downloader, contract=contract
                )
            self.assertFalse(final_path.exists())
            result = execute_model_download(
                "base.en", target_dir, retrying_downloader, contract=contract
            )
            self.assertEqual(result.disposition, "downloaded")
            self.assertEqual(attempt, 2)
            self.assertTrue(verify_model_file(final_path, contract.models[0]).valid)

    def test_stale_hidden_partial_is_not_scanned_and_does_not_block_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = write_fixture_contract(root)
            target_dir = root / "models"
            stale = target_dir / ".classroom-model-download-stale"
            stale.mkdir(parents=True)
            with (stale / "ggml-base.en.bin").open("wb") as partial:
                partial.truncate(MIN_MODEL_FILE_SIZE_BYTES + 1)
            models = scan_model_dirs(
                [target_dir],
                download_model_dir=target_dir,
                contract=contract,
            )
            self.assertFalse(
                any(model.path.is_relative_to(target_dir) for model in models)
            )

            def downloader(_metadata, staging_dir, _log_callback):
                (staging_dir / "ggml-base.en.bin").write_bytes(FIXTURE_PAYLOAD)
                return 0

            result = execute_model_download(
                "base.en", target_dir, downloader, contract=contract
            )
            self.assertEqual(result.disposition, "downloaded")
            self.assertFalse(stale.exists())

    def test_known_downloadable_outside_target_is_unavailable_unless_imported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = b"X" * (MIN_MODEL_FILE_SIZE_BYTES + 1)
            contract = write_fixture_contract(root, payload=payload)
            scan_dir = root / "legacy-models"
            scan_dir.mkdir()
            model_path = scan_dir / "ggml-base.en.bin"
            model_path.write_bytes(payload)

            automatic = scan_model_dirs(
                [scan_dir],
                download_model_dir=root / "downloads",
                contract=contract,
            )
            automatic_match = next(
                model
                for model in automatic
                if model.path.resolve() == model_path.resolve()
            )
            self.assertEqual(automatic_match.status, "integrity unverified")

            imported = scan_model_dirs(
                [scan_dir],
                extra_paths=[model_path],
                download_model_dir=root / "downloads",
                contract=contract,
            )
            imported_match = next(
                model
                for model in imported
                if model.path.resolve() == model_path.resolve()
            )
            self.assertEqual(imported_match.status, "available")

    def test_custom_import_is_not_subject_to_download_checksum_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = write_fixture_contract(root)
            target_dir = root / "models"
            target_dir.mkdir()
            imported = target_dir / "ggml-base.en.bin"
            with imported.open("wb") as imported_file:
                imported_file.truncate(MIN_MODEL_FILE_SIZE_BYTES + 1)
            models = scan_model_dirs(
                [target_dir],
                extra_paths=[imported],
                download_model_dir=target_dir,
                contract=contract,
            )
            matching = [
                model
                for model in models
                if model.path.resolve() == imported.resolve()
            ]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0].status, "available")

    def test_unknown_downloadable_model_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = write_fixture_contract(root)
            called = []

            def downloader(*_args):
                called.append(True)
                return 0

            with self.assertRaisesRegex(ModelIntegrityError, "no integrity metadata"):
                execute_model_download(
                    "unknown-model", root / "models", downloader, contract=contract
                )
            self.assertEqual(called, [])

    def test_receipt_invalidates_after_file_stat_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = write_fixture_contract(root)
            target_dir = root / "models"

            def downloader(_metadata, staging_dir, _log_callback):
                (staging_dir / "ggml-base.en.bin").write_bytes(FIXTURE_PAYLOAD)
                return 0

            result = execute_model_download(
                "base.en", target_dir, downloader, contract=contract
            )
            stat_result = result.path.stat()
            os.utime(
                result.path,
                ns=(stat_result.st_atime_ns, stat_result.st_mtime_ns + 1_000_000),
            )
            self.assertEqual(
                downloaded_model_status(result.path, contract.models[0], contract),
                "integrity invalid",
            )


if __name__ == "__main__":
    unittest.main()
