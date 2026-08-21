import ast
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_PATH = REPO_ROOT / "ui_app.py"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from model_manager import ModelInfo  # noqa: E402


def call_names(node):
    names = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            names.append(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            names.append(child.func.attr)
    return names


class ModelManagerUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = UI_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.dialog = next(
            node
            for node in cls.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "ModelManagerDialog"
        )
        cls.methods = {
            node.name: node
            for node in cls.dialog.body
            if isinstance(node, ast.FunctionDef)
        }
        cls.main_window = next(
            node
            for node in cls.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
        )
        cls.main_methods = {
            node.name: node
            for node in cls.main_window.body
            if isinstance(node, ast.FunctionDef)
        }

    def test_long_path_current_summaries_are_concise_with_full_path_tooltips(self):
        long_path = Path("/Volumes/Classroom Models") / ("nested-folder-" * 8) / "ggml-large-v3.bin"
        model = ModelInfo(
            name="large-v3",
            path=long_path,
            size_bytes=3 * 1024 * 1024 * 1024,
            status="integrity unverified",
        )

        self.assertEqual(
            model.current_summary_label,
            "large-v3 | 3.0 GB | integrity unverified",
        )
        self.assertNotIn(str(long_path), model.current_summary_label)
        self.assertIn(str(long_path), model.display_label)

        dialog_update = ast.unparse(self.methods["_update_current_label"])
        main_update = ast.unparse(self.main_methods["_update_model_labels"])
        for method_text in (dialog_update, main_update):
            self.assertIn("current_summary_label", method_text)
            self.assertIn("setToolTip(str(self.selected_model.path))", method_text)

    def test_full_model_presentation_remains_for_table_combo_and_logs(self):
        table_refresh = ast.unparse(self.methods["refresh_models"])
        dialog_selection = ast.unparse(self.methods["_select_model"])
        combo_population = ast.unparse(self.main_methods["_populate_model_combo"])
        unavailable_log = ast.unparse(self.main_methods["_on_model_combo_changed"])

        self.assertIn("QTableWidgetItem(model.display_path)", table_refresh)
        self.assertIn("model.display_label", dialog_selection)
        self.assertIn("model.display_label", combo_population)
        self.assertIn("model.display_label", unavailable_log)

    def test_selection_confirmation_uses_bilingual_non_modal_timer_contract(self):
        text_assignment = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "TEXT" for target in node.targets)
        )
        translations = ast.literal_eval(text_assignment.value)
        self.assertEqual(translations["zh"]["model_selected"], "已选择模型")
        self.assertEqual(translations["en"]["model_selected"], "Model selected")

        for init_method, methods in (
            (self.methods["__init__"], self.methods),
            (self.main_methods["__init__"], self.main_methods),
        ):
            init_text = ast.unparse(init_method)
            show_text = ast.unparse(methods["_show_model_selection_confirmation"])
            clear_text = ast.unparse(methods["_clear_model_selection_confirmation"])

            self.assertIn("QTimer(self)", init_text)
            self.assertIn("setSingleShot(True)", init_text)
            self.assertIn("setInterval(2000)", init_text)
            self.assertIn(
                "timeout.connect(self._clear_model_selection_confirmation)",
                init_text,
            )
            self.assertIn("tr('model_selected')", show_text)
            self.assertIn("model.name", show_text)
            self.assertIn("model_selection_confirmation_label.show()", show_text)
            self.assertIn("model_selection_confirmation_timer.start()", show_text)
            self.assertNotIn("QMessageBox", show_text)
            self.assertNotIn("sleep", show_text)
            self.assertNotIn("Thread", show_text)
            self.assertIn("model_selection_confirmation_timer.stop()", clear_text)
            self.assertIn("model_selection_confirmation_label.clear()", clear_text)
            self.assertIn("model_selection_confirmation_label.hide()", clear_text)

    def test_only_explicit_changed_available_selection_triggers_confirmation(self):
        dialog_explicit = ast.unparse(self.methods["select_current_row"])
        main_explicit = ast.unparse(self.main_methods["_on_model_combo_changed"])

        for method_text, setter_name in (
            (dialog_explicit, "self._select_model(model)"),
            (main_explicit, "self._set_selected_model(model)"),
        ):
            self.assertIn("self._clear_model_selection_confirmation()", method_text)
            self.assertIn("if not model.is_available", method_text)
            self.assertIn("selection_changed", method_text)
            self.assertIn(
                "self.selected_model.path.resolve() != model.path.resolve()",
                method_text,
            )
            self.assertIn(setter_name, method_text)
            self.assertIn("if selection_changed:", method_text)
            self.assertEqual(
                method_text.count("self._show_model_selection_confirmation(model)"),
                1,
            )
            self.assertLess(
                method_text.index(setter_name),
                method_text.index("self._show_model_selection_confirmation(model)"),
            )
            self.assertLess(
                method_text.index("self._clear_model_selection_confirmation()"),
                method_text.index("if not model.is_available"),
            )

    def test_restore_propagation_and_download_auto_selection_do_not_confirm(self):
        dialog_automatic_methods = (
            "refresh_models",
            "import_existing_model",
            "_handle_download_finished",
            "_select_model",
            "_update_current_label",
        )
        main_automatic_methods = (
            "refresh_models",
            "_reload_models_from_settings",
            "_set_selected_model",
            "_populate_model_combo",
            "_update_model_labels",
        )

        download_finished = ast.unparse(self.methods["_handle_download_finished"])
        self.assertIn("self._select_model(selected)", download_finished)
        dialog_setter = ast.unparse(self.methods["_select_model"])
        self.assertIn("self._clear_model_selection_confirmation()", dialog_setter)
        main_setter = ast.unparse(self.main_methods["_set_selected_model"])
        self.assertIn("self._clear_model_selection_confirmation()", main_setter)
        self.assertIn("save_app_settings(self.app_settings)", main_setter)

        for method_name in dialog_automatic_methods:
            self.assertNotIn(
                "_show_model_selection_confirmation",
                ast.unparse(self.methods[method_name]),
            )
        for method_name in main_automatic_methods:
            self.assertNotIn(
                "_show_model_selection_confirmation",
                ast.unparse(self.main_methods[method_name]),
            )

        open_manager = ast.unparse(self.main_methods["open_model_manager"])
        self.assertIn("dialog.model_selected.connect(self._set_selected_model)", open_manager)

    def test_download_transaction_runs_in_existing_background_worker(self):
        method = self.methods["download_selected_model"]
        worker = next(
            node
            for node in method.body
            if isinstance(node, ast.FunctionDef) and node.name == "worker"
        )
        self.assertIn("download_and_publish_model", call_names(worker))
        direct_calls = [
            name
            for statement in method.body
            if statement is not worker
            for name in call_names(statement)
        ]
        self.assertNotIn("download_and_publish_model", direct_calls)
        thread_calls = [
            node
            for node in ast.walk(method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Thread"
        ]
        self.assertEqual(len(thread_calls), 0)
        self.assertIn("threading.Thread", ast.unparse(method))
        self.assertIn(".start()", ast.unparse(method))

    def test_ui_no_longer_short_circuits_on_final_file_existence(self):
        method_text = ast.unparse(self.methods["download_selected_model"])
        self.assertNotIn("target_path.exists", method_text)
        self.assertNotIn("run_download_command", method_text)
        self.assertNotIn("build_download_command", method_text)
        self.assertNotIn("DOWNLOAD_SCRIPT_PATH", method_text)

    def test_failure_handler_reenables_retry_and_refreshes_integrity_state(self):
        handler_text = ast.unparse(self.methods["_handle_download_finished"])
        self.assertIn("self.downloading = False", handler_text)
        self.assertIn("self._set_download_controls(True)", handler_text)
        self.assertIn("self.refresh_models()", handler_text)
        self.assertIn("QMessageBox.critical", handler_text)


if __name__ == "__main__":
    unittest.main()
