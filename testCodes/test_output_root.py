import ast
import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_PATH = REPO_ROOT / "ui_app.py"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import settings as settings_module  # noqa: E402
import transcription_controller as controller_module  # noqa: E402
from model_manager import load_app_settings, save_app_settings  # noqa: E402
from settings import (  # noqa: E402
    DEFAULT_OUTPUT_BASE_DIR,
    MIN_MODEL_FILE_SIZE_BYTES,
    TranscriptionSettings,
    default_settings,
    output_root_for_base,
    validate_runtime_paths,
)
from transcript_store import TranscriptStore  # noqa: E402


def make_runtime_fixture(root: Path):
    cli = root / "whisper-cli"
    cli.write_text("#!/bin/sh\n", encoding="utf-8")
    os.chmod(cli, 0o755)
    model = root / "ggml-large-v3.bin"
    with open(model, "wb") as model_file:
        model_file.truncate(MIN_MODEL_FILE_SIZE_BYTES + 1)
    return cli, model


class OutputRootContractTests(unittest.TestCase):
    def test_legacy_settings_default_and_custom_root_persistence(self):
        with tempfile.TemporaryDirectory(prefix="output_root_settings_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            settings_path = tmp_path / "config" / "settings.json"
            model_dir = tmp_path / "models"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(
                json.dumps(
                    {
                        "whisper_cpp_cli": str(tmp_path / "whisper-cli"),
                        "selected_model_path": "",
                        "selected_model_name": "",
                        "default_beam_size": 5,
                        "download_model_dir": str(model_dir),
                        "model_dirs": [str(model_dir)],
                        "imported_model_paths": [],
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_app_settings(settings_path=settings_path)
            self.assertEqual(loaded.output_base_dir, DEFAULT_OUTPUT_BASE_DIR)

            custom_base = tmp_path / "custom classroom location"
            loaded.output_base_dir = custom_base
            save_app_settings(loaded, settings_path=settings_path)
            reloaded = load_app_settings(settings_path=settings_path)
            self.assertEqual(reloaded.output_base_dir, custom_base)
            saved = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["output_base_dir"], str(custom_base))

    def test_configured_base_maps_to_actual_outputs_directory(self):
        with tempfile.TemporaryDirectory(prefix="output_root_mapping_") as tmp_dir:
            base = Path(tmp_dir) / "chosen-root"
            configured = default_settings(output_base_dir=base)
            self.assertEqual(configured.output_root, base / "outputs")
            self.assertEqual(output_root_for_base(base), base / "outputs")

    def test_invalid_and_unwritable_output_fail_preflight_without_fallback(self):
        with tempfile.TemporaryDirectory(prefix="output_root_preflight_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            cli, model = make_runtime_fixture(tmp_path)
            invalid_base = tmp_path / "not-a-directory"
            invalid_base.write_text("file", encoding="utf-8")
            expected_output = invalid_base / "outputs"
            invalid_settings = TranscriptionSettings(
                whisper_cpp_cli=cli,
                whisper_cpp_model=model,
                output_root=expected_output,
            )

            errors = validate_runtime_paths(invalid_settings)
            self.assertTrue(any("output directory is not writable" in error for error in errors))
            self.assertTrue(any(str(expected_output) in error for error in errors))
            self.assertEqual(invalid_settings.output_root, expected_output)
            self.assertFalse(expected_output.exists())

            writable_output = tmp_path / "probe-failure" / "outputs"
            probe_settings = replace(invalid_settings, output_root=writable_output)
            with patch.object(
                settings_module.tempfile,
                "NamedTemporaryFile",
                side_effect=PermissionError("permission denied"),
            ):
                probe_errors = validate_runtime_paths(probe_settings)
            self.assertTrue(any("permission denied" in error for error in probe_errors))
            self.assertEqual(probe_settings.output_root, writable_output)

    def test_controller_creates_only_new_sessions_under_chosen_root(self):
        with tempfile.TemporaryDirectory(prefix="output_root_controller_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            cli, model = make_runtime_fixture(tmp_path)
            chosen_base = tmp_path / "chosen-root"
            historical = chosen_base / "outputs" / "historical-session" / "marker.txt"
            historical.parent.mkdir(parents=True)
            historical.write_text("keep", encoding="utf-8")

            real_default_settings = settings_module.default_settings

            def isolated_default_settings(**kwargs):
                return replace(
                    real_default_settings(**kwargs),
                    whisper_cpp_cli=cli,
                )

            class SequencedStore(TranscriptStore):
                counter = 0

                def __init__(self, output_root):
                    type(self).counter += 1
                    super().__init__(output_root, session_id=f"session-{type(self).counter}")

            class FakeEngine:
                def __init__(self, _settings, store, event_callback=None):
                    self.store = store

                def start(self):
                    pass

                def stop(self):
                    self.store.close()

            with (
                patch.object(controller_module, "default_settings", isolated_default_settings),
                patch.object(controller_module, "TranscriptStore", SequencedStore),
                patch.object(controller_module, "TranscriptionEngine", FakeEngine),
            ):
                controller = controller_module.TranscriptionController()
                first_session = controller.start(
                    beam_size=5,
                    original_language_label="English",
                    selected_model_path=model,
                    selected_model_name="large-v3",
                    output_base_dir=chosen_base,
                )
                controller.stop()
                second_session = controller.start(
                    beam_size=5,
                    original_language_label="English",
                    selected_model_path=model,
                    selected_model_name="large-v3",
                    output_base_dir=chosen_base,
                )
                controller.stop()

            self.assertEqual(first_session, chosen_base / "outputs" / "session-1")
            self.assertEqual(second_session, chosen_base / "outputs" / "session-2")
            for session_dir in (first_session, second_session):
                self.assertEqual(
                    {path.name for path in session_dir.iterdir()},
                    {"raw.txt", "clean.txt", "session.log", "config.json"},
                )
            self.assertEqual(historical.read_text(encoding="utf-8"), "keep")

    def test_main_window_exposes_persistent_future_session_selection(self):
        source = UI_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        text_assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "TEXT" for target in node.targets)
        )
        translations = ast.literal_eval(text_assignment.value)
        self.assertEqual(translations["zh"]["choose_output_base"], "选择输出位置")
        self.assertEqual(translations["en"]["choose_output_base"], "Choose Output Location")

        main_window = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
        )
        methods = {
            node.name: ast.unparse(node)
            for node in main_window.body
            if isinstance(node, ast.FunctionDef)
        }
        controls = methods["_build_controls"]
        choose = methods["choose_output_base"]
        start = methods["start_recording"]
        status = methods["_set_status"]

        self.assertIn("self.output_base_label", controls)
        self.assertIn("self.choose_output_base_button", controls)
        self.assertIn("QFileDialog.getExistingDirectory", choose)
        self.assertIn("self.app_settings.output_base_dir = Path(folder).expanduser()", choose)
        self.assertIn("save_app_settings(self.app_settings)", choose)
        self.assertIn("output_base_dir=self.app_settings.output_base_dir", start)
        self.assertIn("choose_output_base_button.setEnabled(is_idle or is_error)", status)


if __name__ == "__main__":
    unittest.main()
