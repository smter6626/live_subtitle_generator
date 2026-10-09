import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from settings import (  # noqa: E402
    MIN_MODEL_FILE_SIZE_BYTES,
    ORIGINAL_LANGUAGE_AUTO_DETECT,
    ORIGINAL_LANGUAGE_CHOICES,
    ORIGINAL_LANGUAGE_ENGLISH,
    ORIGINAL_LANGUAGE_OPTIONS,
    TranscriptionSettings,
    is_english_only_whisper_model,
    normalize_original_language_label,
    validate_runtime_paths,
    whisper_language_code_for_label,
)
from stream_transcribe import build_whisper_cpp_command  # noqa: E402


class MultilingualLanguageSelectionTests(unittest.TestCase):
    def test_canonical_choice_order_and_codes(self):
        self.assertEqual(
            ORIGINAL_LANGUAGE_CHOICES,
            (
                "English",
                "Chinese",
                "Japanese",
                "French",
                "Spanish",
                "German",
                "Korean",
                "Auto Detect",
            ),
        )
        self.assertEqual(
            tuple(ORIGINAL_LANGUAGE_OPTIONS),
            ORIGINAL_LANGUAGE_CHOICES,
        )
        self.assertEqual(
            tuple(ORIGINAL_LANGUAGE_OPTIONS.values()),
            ("en", "zh", "ja", "fr", "es", "de", "ko", "auto"),
        )

    def test_legacy_automatic_language_aliases_normalize_to_canonical_label(self):
        for alias in ("Mixed Chinese/English", "中英混合", "mixed", "auto"):
            self.assertEqual(
                normalize_original_language_label(alias),
                ORIGINAL_LANGUAGE_AUTO_DETECT,
            )
            self.assertEqual(whisper_language_code_for_label(alias), "auto")

    def test_session_config_records_canonical_label_and_code(self):
        for label, expected_code in ORIGINAL_LANGUAGE_OPTIONS.items():
            settings = TranscriptionSettings(original_language_label=label).normalized()
            config = settings.to_config()
            self.assertEqual(config["original_language_label"], label)
            self.assertEqual(config["whisper_language_code"], expected_code)

        legacy_settings = TranscriptionSettings(
            original_language_label="Mixed Chinese/English"
        ).normalized()
        self.assertEqual(legacy_settings.to_config()["original_language_label"], "Auto Detect")
        self.assertEqual(legacy_settings.to_config()["whisper_language_code"], "auto")

    def test_whisper_cpp_receives_each_canonical_language_code(self):
        for label, expected_code in ORIGINAL_LANGUAGE_OPTIONS.items():
            command = build_whisper_cpp_command(
                cli_path="/tmp/whisper-cli",
                model_path="/tmp/ggml-large-v3.bin",
                wav_path="/tmp/chunk.wav",
                language_code=whisper_language_code_for_label(label),
                beam_size=5,
                task="transcribe",
            )
            self.assertEqual(command[command.index("-l") + 1], expected_code)

    def test_english_only_models_are_recognized_by_identity_and_filename(self):
        self.assertTrue(is_english_only_whisper_model("small.en"))
        self.assertTrue(
            is_english_only_whisper_model(
                "Custom Model", "/models/ggml-base.en.bin"
            )
        )
        self.assertFalse(
            is_english_only_whisper_model("large-v3", "/models/ggml-large-v3.bin")
        )

    def test_english_only_models_reject_every_non_english_choice(self):
        with tempfile.TemporaryDirectory(prefix="language_model_compatibility_") as tmp_dir:
            root = Path(tmp_dir)
            cli = root / "whisper-cli"
            cli.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(cli, 0o755)
            english_only_model = root / "ggml-small.en.bin"
            with english_only_model.open("wb") as model_file:
                model_file.truncate(MIN_MODEL_FILE_SIZE_BYTES + 1)

            for label in ORIGINAL_LANGUAGE_CHOICES:
                settings = TranscriptionSettings(
                    model="small.en",
                    model_display="small.en",
                    whisper_cpp_cli=cli,
                    whisper_cpp_model=english_only_model,
                    output_root=root / label / "outputs",
                    original_language_label=label,
                )
                errors = validate_runtime_paths(settings)
                if label == ORIGINAL_LANGUAGE_ENGLISH:
                    self.assertEqual(errors, [])
                else:
                    self.assertTrue(
                        any("English-only .en Whisper models support only English" in error for error in errors),
                        label,
                    )

            multilingual_model = root / "ggml-large-v3.bin"
            with multilingual_model.open("wb") as model_file:
                model_file.truncate(MIN_MODEL_FILE_SIZE_BYTES + 1)
            for label in ORIGINAL_LANGUAGE_CHOICES:
                settings = TranscriptionSettings(
                    model="large-v3",
                    whisper_cpp_cli=cli,
                    whisper_cpp_model=multilingual_model,
                    output_root=root / "multilingual" / label / "outputs",
                    original_language_label=label,
                )
                self.assertEqual(validate_runtime_paths(settings), [], label)


if __name__ == "__main__":
    unittest.main()
