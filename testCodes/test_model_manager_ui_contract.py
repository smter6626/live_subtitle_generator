import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_PATH = REPO_ROOT / "ui_app.py"


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
