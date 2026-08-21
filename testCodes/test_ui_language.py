import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_PATH = REPO_ROOT / "ui_app.py"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import ui_app as ui_module  # noqa: E402
from model_manager import load_app_settings, save_app_settings  # noqa: E402
from settings import (  # noqa: E402
    DEFAULT_UI_LANGUAGE,
    ORIGINAL_LANGUAGE_CHINESE,
    ORIGINAL_LANGUAGE_ENGLISH,
    ORIGINAL_LANGUAGE_MIXED,
    UI_LANGUAGE_EN,
    UI_LANGUAGE_ZH,
    whisper_language_code_for_label,
)


class UiLanguageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = UI_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.text_assignment = next(
            node
            for node in cls.tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "TEXT" for target in node.targets)
        )
        cls.translations = ast.literal_eval(cls.text_assignment.value)
        cls.main_window = next(
            node
            for node in cls.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
        )
        cls.main_methods = {
            node.name: ast.unparse(node)
            for node in cls.main_window.body
            if isinstance(node, ast.FunctionDef)
        }
        cls.dialog = next(
            node
            for node in cls.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "ModelManagerDialog"
        )
        cls.dialog_methods = {
            node.name: ast.unparse(node)
            for node in cls.dialog.body
            if isinstance(node, ast.FunctionDef)
        }

    def tearDown(self):
        ui_module.set_current_language(DEFAULT_UI_LANGUAGE)

    def test_translation_catalogs_are_complete_and_semantically_distinct(self):
        self.assertEqual(
            set(self.translations["zh"]),
            set(self.translations["en"]),
        )
        for language in ("zh", "en"):
            for key, value in self.translations[language].items():
                self.assertTrue(value.strip(), f"empty {language} translation for {key}")

        self.assertEqual(self.translations["zh"]["ui_language"], "界面语言")
        self.assertEqual(
            self.translations["zh"]["original_language"],
            "音频原始语言",
        )
        self.assertEqual(self.translations["en"]["ui_language"], "Interface Language")
        self.assertEqual(
            self.translations["en"]["original_language"],
            "Audio / Original Language",
        )

    def test_dynamic_translation_keeps_original_language_codes_canonical(self):
        expectations = {
            UI_LANGUAGE_ZH: {
                ORIGINAL_LANGUAGE_ENGLISH: "英语",
                ORIGINAL_LANGUAGE_CHINESE: "中文",
                ORIGINAL_LANGUAGE_MIXED: "中英混合",
            },
            UI_LANGUAGE_EN: {
                ORIGINAL_LANGUAGE_ENGLISH: "English",
                ORIGINAL_LANGUAGE_CHINESE: "Chinese",
                ORIGINAL_LANGUAGE_MIXED: "Mixed Chinese/English",
            },
        }
        expected_codes = {
            ORIGINAL_LANGUAGE_ENGLISH: "en",
            ORIGINAL_LANGUAGE_CHINESE: "zh",
            ORIGINAL_LANGUAGE_MIXED: "auto",
        }
        for ui_language, labels in expectations.items():
            ui_module.set_current_language(ui_language)
            for original_language, displayed in labels.items():
                self.assertEqual(
                    ui_module.display_original_language(original_language),
                    displayed,
                )
                self.assertEqual(
                    whisper_language_code_for_label(original_language),
                    expected_codes[original_language],
                )

    def test_ui_language_is_backward_compatible_and_persistent(self):
        with tempfile.TemporaryDirectory(prefix="ui_language_settings_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            settings_path = tmp_path / "config" / "settings.json"
            model_dir = tmp_path / "models"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(
                json.dumps(
                    {
                        "download_model_dir": str(model_dir),
                        "model_dirs": [str(model_dir)],
                        "imported_model_paths": [],
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_app_settings(settings_path=settings_path)
            self.assertEqual(loaded.ui_language, DEFAULT_UI_LANGUAGE)
            loaded.ui_language = UI_LANGUAGE_EN
            save_app_settings(loaded, settings_path=settings_path)
            reloaded = load_app_settings(settings_path=settings_path)
            self.assertEqual(reloaded.ui_language, UI_LANGUAGE_EN)
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8"))["ui_language"],
                UI_LANGUAGE_EN,
            )

    def test_switch_updates_only_ui_language_and_retranslates(self):
        app_settings = SimpleNamespace(
            ui_language=UI_LANGUAGE_ZH,
            selected_model_path=Path("/models/ggml-large-v3.bin"),
            selected_model_name="large-v3",
            default_beam_size=7,
            output_base_dir=Path("/chosen/output-base"),
            download_model_dir=Path("/chosen/models"),
        )
        before = vars(app_settings).copy()
        fake_window = SimpleNamespace(
            app_settings=app_settings,
            ui_language_combo=SimpleNamespace(itemData=lambda _index: UI_LANGUAGE_EN),
            _retranslate_ui=lambda: setattr(fake_window, "retranslated", True),
            retranslated=False,
            controller=object(),
        )

        with patch.object(ui_module, "save_app_settings") as save_settings:
            ui_module.MainWindow._on_ui_language_changed(fake_window, 0)

        self.assertEqual(app_settings.ui_language, UI_LANGUAGE_EN)
        self.assertTrue(fake_window.retranslated)
        save_settings.assert_called_once_with(app_settings)
        for key, value in before.items():
            if key != "ui_language":
                self.assertEqual(getattr(app_settings, key), value)

        switch_text = self.main_methods["_on_ui_language_changed"]
        for forbidden in (
            "controller.start",
            "controller.stop",
            "selected_model",
            "default_beam_size",
            "output_base_dir",
            "original_language",
        ):
            self.assertNotIn(forbidden, switch_text)

    def test_retranslation_covers_main_window_and_model_manager_semantics(self):
        controls = self.main_methods["_build_controls"]
        retranslate = self.main_methods["_retranslate_ui"]
        start = self.main_methods["start_recording"]
        self.assertIn("UI_LANGUAGE_OPTIONS", controls)
        self.assertIn("UI_LANGUAGE_LABELS[language]", controls)
        self.assertIn("addItem(display_original_language(label), label)", controls)
        self.assertIn("original_language_label = self.language_combo.currentData()", start)
        self.assertIn("output_base_dir=self.app_settings.output_base_dir", start)

        expected_surfaces = (
            "status_title_labels",
            "controls_group",
            "start_button",
            "stop_button",
            "ui_language_title_label",
            "original_language_title_label",
            "model_group",
            "output_group",
            "session_group",
            "session_title_labels",
            "clean_table.retranslate_ui()",
            "raw_table.retranslate_ui()",
            "tabs.setTabText",
        )
        for surface in expected_surfaces:
            self.assertIn(surface, retranslate)

        dialog_init = self.dialog_methods["__init__"]
        self.assertIn("set_current_language(app_settings.ui_language)", dialog_init)
        self.assertIn("tr('model_manager')", dialog_init)
        self.assertNotIn(
            "Model is not available:",
            self.dialog_methods["select_current_row"],
        )
        self.assertIn(
            "tr('model_download_still_running')",
            self.dialog_methods["reject"],
        )

    def test_offscreen_main_window_switch_retranslates_without_runtime_mutation(self):
        app = ui_module.QApplication.instance() or ui_module.QApplication([])
        app_settings = SimpleNamespace(
            ui_language=UI_LANGUAGE_ZH,
            selected_model_path=None,
            selected_model_name="",
            default_beam_size=7,
            output_base_dir=Path("/chosen/output-base"),
            download_model_dir=Path("/chosen/models"),
            model_dirs=[],
            imported_model_paths=[],
        )
        with (
            patch.object(ui_module, "load_app_settings", return_value=app_settings),
            patch.object(ui_module, "save_app_settings"),
            patch.object(ui_module, "scan_model_dirs", return_value=[]),
            patch.object(ui_module, "crash_log"),
        ):
            window = ui_module.MainWindow()

            controller = window.controller
            original_language = window.language_combo.currentData()
            beam = window.beam_combo.currentData()
            output_base = window.app_settings.output_base_dir
            english_index = window.ui_language_combo.findData(UI_LANGUAGE_EN)
            window.ui_language_combo.setCurrentIndex(english_index)
            app.processEvents()

            self.assertEqual(window.windowTitle(), "Whisper Classroom Transcriber")
            self.assertEqual(window.start_button.text(), "Start Recording")
            self.assertEqual(
                window.original_language_title_label.text(),
                "Audio / Original Language",
            )
            self.assertEqual(window.clean_table.table.horizontalHeaderItem(1).text(), "Text")
            self.assertIs(window.controller, controller)
            self.assertEqual(window.language_combo.currentData(), original_language)
            self.assertEqual(window.beam_combo.currentData(), beam)
            self.assertEqual(window.app_settings.output_base_dir, output_base)

            chinese_index = window.ui_language_combo.findData(UI_LANGUAGE_ZH)
            window.ui_language_combo.setCurrentIndex(chinese_index)
            app.processEvents()
            self.assertEqual(window.windowTitle(), "Whisper 课堂实时转写")
            self.assertEqual(window.start_button.text(), "开始录音")
            self.assertEqual(window.original_language_title_label.text(), "音频原始语言")
            self.assertEqual(window.clean_table.table.horizontalHeaderItem(1).text(), "正文")
            window.safe_shutdown()


if __name__ == "__main__":
    unittest.main()
