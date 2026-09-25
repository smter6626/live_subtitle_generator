import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import transcription_controller as controller_module  # noqa: E402
import ui_app as ui_module  # noqa: E402
from settings import UI_LANGUAGE_EN, UI_LANGUAGE_ZH  # noqa: E402
from transcript_store import TranscriptStore  # noqa: E402
from transcription_controller import EngineState  # noqa: E402


class SequencedStore(TranscriptStore):
    counter = 0

    def __init__(self, output_root):
        type(self).counter += 1
        super().__init__(output_root, session_id=f"session-{type(self).counter}")


class FakeEngine:
    instances = []

    def __init__(self, _settings, store, event_callback=None):
        self.store = store
        self.event_callback = event_callback
        type(self).instances.append(self)

    def start(self):
        pass

    def stop(self):
        self.store.close()
        self.emit({"type": "stopped", "message": "Stop complete."})

    def emit(self, event):
        self.event_callback(event)


class ControllerSessionOwnershipTests(unittest.TestCase):
    def setUp(self):
        SequencedStore.counter = 0
        FakeEngine.instances = []

    def test_engine_callbacks_are_owned_scoped_and_rejected_when_stale(self):
        with tempfile.TemporaryDirectory(prefix="controller_session_scope_") as tmp_dir:
            base = Path(tmp_dir)
            historical = base / "outputs" / "historical" / "transcript.txt"
            historical.parent.mkdir(parents=True)
            historical.write_bytes(b"historical transcript\n")
            historical_before = historical.read_bytes()
            events = []

            with (
                patch.object(controller_module, "validate_runtime_paths", return_value=[]),
                patch.object(controller_module, "TranscriptStore", SequencedStore),
                patch.object(controller_module, "TranscriptionEngine", FakeEngine),
            ):
                controller = controller_module.TranscriptionController(events.append)
                first_dir = controller.start(
                    beam_size=5,
                    original_language_label="English",
                    selected_model_path=base / "model.bin",
                    selected_model_name="test-model",
                    output_base_dir=base,
                )
                first_id = controller.active_session_id
                first_generation = controller.active_session_generation
                first_engine = FakeEngine.instances[-1]
                controller.store.append_raw(["[0.00s -> 1.00s] raw one"])
                controller.store.append_clean(["[0.00s -> 1.00s] clean one"])
                first_engine.emit({"type": "recording"})
                self.assertEqual(controller.state, EngineState.RECORDING)
                controller.stop()

                first_files_before = {
                    path.name: path.read_bytes() for path in first_dir.iterdir()
                }
                second_dir = controller.start(
                    beam_size=5,
                    original_language_label="Chinese",
                    selected_model_path=base / "model.bin",
                    selected_model_name="test-model",
                    output_base_dir=base,
                )
                second_id = controller.active_session_id
                second_generation = controller.active_session_generation
                second_engine = FakeEngine.instances[-1]
                accepted_event_count = len(events)

                for stale_event in (
                    {"type": "raw_lines", "lines": ["stale raw"], "raw_count": 99},
                    {"type": "clean_lines", "lines": ["stale clean"], "clean_count": 99},
                    {"type": "recording"},
                    {"type": "error", "message": "stale error"},
                ):
                    first_engine.emit(stale_event)

                self.assertEqual(len(events), accepted_event_count)
                self.assertEqual(controller.state, EngineState.STARTING)
                self.assertEqual(controller.active_session_id, second_id)
                self.assertNotEqual(first_id, second_id)
                self.assertEqual(second_generation, first_generation + 1)

                second_engine.emit(
                    {"type": "clean_lines", "lines": ["current clean"], "clean_count": 1}
                )
                self.assertEqual(events[-1]["session_id"], second_id)
                self.assertEqual(events[-1]["session_generation"], second_generation)
                self.assertEqual(events[-1]["type"], "clean_lines")

                for event in events:
                    if event["type"] == "session" or "session_id" in event:
                        self.assertIn("session_generation", event)

                self.assertEqual(
                    {path.name: path.read_bytes() for path in first_dir.iterdir()},
                    first_files_before,
                )
                self.assertEqual(historical.read_bytes(), historical_before)
                controller.stop()

            self.assertTrue(second_dir.is_dir())


class MainWindowClipboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ui_module.QApplication.instance() or ui_module.QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="session_clipboard_ui_")
        self.root = Path(self.tmp.name)
        self.app_settings = SimpleNamespace(
            ui_language=UI_LANGUAGE_ZH,
            selected_model_path=None,
            selected_model_name="",
            default_beam_size=5,
            output_base_dir=self.root,
            download_model_dir=self.root / "models",
            model_dirs=[],
            imported_model_paths=[],
        )
        self.patchers = (
            patch.object(ui_module, "load_app_settings", return_value=self.app_settings),
            patch.object(ui_module, "save_app_settings"),
            patch.object(ui_module, "scan_model_dirs", return_value=[]),
            patch.object(ui_module, "crash_log"),
        )
        for patcher in self.patchers:
            patcher.start()
        self.window = ui_module.MainWindow()
        self.clipboard = self.app.clipboard()

    def tearDown(self):
        self.window.safe_shutdown()
        self.window.close()
        for patcher in reversed(self.patchers):
            patcher.stop()
        ui_module.set_current_language(UI_LANGUAGE_ZH)
        self.tmp.cleanup()

    def make_session(self, name, generation, clean_bytes=b""):
        session_dir = self.root / name
        session_dir.mkdir()
        clean_path = session_dir / "clean.txt"
        raw_path = session_dir / "raw.txt"
        log_path = session_dir / "session.log"
        clean_path.write_bytes(clean_bytes)
        raw_path.write_bytes(b"raw file bytes\n")
        log_path.write_bytes(b"log file bytes\n")
        return {
            "type": "session",
            "session_id": f"owner-{generation}",
            "session_generation": generation,
            "session_dir": str(session_dir),
            "clean_path": str(clean_path),
            "raw_path": str(raw_path),
            "raw_count": 0,
            "clean_count": 0,
            "config": {"original_language_label": "English", "model": "test-model"},
        }

    def emit_for_active(self, event_type, **payload):
        self.window.handle_event(
            {
                "type": event_type,
                "session_id": self.window.active_session_id,
                "session_generation": self.window.active_session_generation,
                **payload,
            }
        )

    def test_path_copy_no_session_active_stopped_and_replaced_session(self):
        self.clipboard.setText("leave unchanged")
        self.window.clean_copy_row_cursor = 7
        self.window.copy_clean_path()
        self.assertEqual(self.clipboard.text(), "leave unchanged")
        self.assertEqual(self.window.clean_copy_row_cursor, 7)

        first = self.make_session("first", 1)
        first_snapshot = {
            path.name: path.read_bytes() for path in Path(first["session_dir"]).iterdir()
        }
        self.window.handle_event(first)
        self.window.copy_clean_path()
        self.assertEqual(self.clipboard.text(), str(Path(first["clean_path"]).resolve()))
        self.assertEqual(self.window.clean_copy_row_cursor, 0)

        self.emit_for_active("state", state=EngineState.IDLE.value, message="")
        self.clipboard.setText("after stop")
        self.window.copy_clean_path()
        self.assertEqual(self.clipboard.text(), str(Path(first["clean_path"]).resolve()))

        second = self.make_session("second", 2)
        self.window.handle_event(second)
        self.window.copy_clean_path()
        self.assertEqual(self.clipboard.text(), str(Path(second["clean_path"]).resolve()))
        self.assertEqual(
            {path.name: path.read_bytes() for path in Path(first["session_dir"]).iterdir()},
            first_snapshot,
        )

    def test_new_session_resets_tables_counts_and_cursor_but_stop_preserves_them(self):
        first = self.make_session("reset-first", 1)
        self.window.handle_event(first)
        self.emit_for_active(
            "raw_lines", lines=["[0.00s -> 1.00s] raw"], raw_count=1
        )
        self.emit_for_active(
            "clean_lines", lines=["[0.00s -> 1.00s] clean"], clean_count=1
        )
        self.window.clean_copy_row_cursor = 1

        self.emit_for_active("stopped", message="done")
        self.emit_for_active("state", state=EngineState.IDLE.value, message="")
        self.assertEqual(self.window.raw_table.table.rowCount(), 1)
        self.assertEqual(self.window.clean_table.table.rowCount(), 1)
        self.assertEqual(self.window.clean_copy_row_cursor, 1)
        self.assertEqual(self.window.current_clean_path, Path(first["clean_path"]))

        second = self.make_session("reset-second", 2)
        self.window.handle_event(second)
        self.assertEqual(self.window.raw_table.table.rowCount(), 0)
        self.assertEqual(self.window.clean_table.table.rowCount(), 0)
        self.assertEqual(self.window.raw_count, 0)
        self.assertEqual(self.window.clean_count, 0)
        self.assertEqual(self.window.raw_lines_label.text(), "0")
        self.assertEqual(self.window.clean_lines_label.text(), "0")
        self.assertEqual(self.window.clean_copy_row_cursor, 0)
        self.assertEqual(self.window.current_clean_path, Path(second["clean_path"]))

    def test_start_failure_before_session_creation_preserves_previous_ui(self):
        session = self.make_session("preserved", 1)
        self.window.handle_event(session)
        self.emit_for_active(
            "raw_lines", lines=["[0.00s -> 1.00s] old raw"], raw_count=1
        )
        self.emit_for_active(
            "clean_lines", lines=["[0.00s -> 1.00s] old clean"], clean_count=1
        )
        self.window.clean_copy_row_cursor = 1
        self.window.selected_model = SimpleNamespace(
            is_available=True,
            path=self.root / "model.bin",
            name="test-model",
        )
        preserved = (
            self.window.raw_table.table.rowCount(),
            self.window.clean_table.table.rowCount(),
            self.window.raw_count,
            self.window.clean_count,
            self.window.raw_lines_label.text(),
            self.window.clean_lines_label.text(),
            self.window.clean_copy_row_cursor,
            self.window.current_clean_path,
        )

        def fail_before_session(**_kwargs):
            self.window.handle_event(
                {"type": "state", "state": EngineState.ERROR.value, "message": "preflight"}
            )
            raise RuntimeError("preflight")

        with (
            patch.object(self.window.controller, "start", side_effect=fail_before_session),
            patch.object(ui_module.QMessageBox, "critical"),
        ):
            self.window.start_recording()

        self.assertEqual(
            (
                self.window.raw_table.table.rowCount(),
                self.window.clean_table.table.rowCount(),
                self.window.raw_count,
                self.window.clean_count,
                self.window.raw_lines_label.text(),
                self.window.clean_lines_label.text(),
                self.window.clean_copy_row_cursor,
                self.window.current_clean_path,
            ),
            preserved,
        )
        self.clipboard.setText("replace me")
        self.window.copy_clean_path()
        self.assertEqual(self.clipboard.text(), str(Path(session["clean_path"]).resolve()))

    def test_text_copy_uses_only_displayed_clean_text_and_is_incremental(self):
        session = self.make_session(
            "unicode",
            1,
            clean_bytes="[9.00s -> 10.00s] undisplayed file content\n".encode("utf-8"),
        )
        self.window.handle_event(session)
        self.emit_for_active(
            "raw_lines", lines=["[1.00s -> 2.00s] raw secret"], raw_count=1
        )
        self.window._append_log("log secret")
        self.emit_for_active(
            "clean_lines",
            lines=["[1.00s -> 2.00s] 你好", "[2.00s -> 3.00s] café"],
            clean_count=2,
        )

        self.window.copy_clean_text()
        self.assertEqual(self.clipboard.text(), "你好\ncafé")
        self.assertNotIn("00:01", self.clipboard.text())
        self.assertNotIn("raw secret", self.clipboard.text())
        self.assertNotIn("log secret", self.clipboard.text())
        self.assertNotIn("undisplayed", self.clipboard.text())
        self.assertEqual(self.window.clean_copy_row_cursor, 2)

        self.emit_for_active(
            "clean_lines", lines=["[3.00s -> 4.00s] 新しい行"], clean_count=3
        )
        self.window.copy_clean_text()
        self.assertEqual(self.clipboard.text(), "新しい行")
        self.assertEqual(self.window.clean_copy_row_cursor, 3)

        self.clipboard.setText("empty slice sentinel")
        self.window.copy_clean_text()
        self.assertEqual(self.clipboard.text(), "empty slice sentinel")
        self.assertEqual(self.window.clean_copy_row_cursor, 3)

        self.window.copy_clean_path()
        self.assertEqual(self.window.clean_copy_row_cursor, 3)
        self.assertEqual(self.clipboard.text(), str(Path(session["clean_path"]).resolve()))

    def test_failed_clipboard_write_does_not_advance_text_cursor(self):
        session = self.make_session("write-failure", 1)
        self.window.handle_event(session)
        self.emit_for_active(
            "clean_lines", lines=["[0.00s -> 1.00s] retry me"], clean_count=1
        )
        self.clipboard.setText("original clipboard")

        class FailingClipboard:
            def setText(self, _text):
                raise RuntimeError("fail")

        failing_clipboard = FailingClipboard()
        with patch.object(ui_module.QApplication, "clipboard", return_value=failing_clipboard):
            with self.assertRaises(RuntimeError):
                self.window.copy_clean_text()
        self.assertEqual(self.window.clean_copy_row_cursor, 0)
        self.assertEqual(self.clipboard.text(), "original clipboard")

    def test_new_session_restarts_text_slice_from_its_displayed_rows(self):
        first = self.make_session("slice-first", 1)
        self.window.handle_event(first)
        self.emit_for_active(
            "clean_lines", lines=["[0.00s -> 1.00s] first session"], clean_count=1
        )
        self.window.copy_clean_text()
        self.assertEqual(self.window.clean_copy_row_cursor, 1)

        second = self.make_session("slice-second", 2)
        self.window.handle_event(second)
        self.emit_for_active(
            "clean_lines",
            lines=["[0.00s -> 1.00s] second A", "[1.00s -> 2.00s] second B"],
            clean_count=2,
        )
        self.window.copy_clean_text()
        self.assertEqual(self.clipboard.text(), "second A\nsecond B")
        self.assertEqual(self.window.clean_copy_row_cursor, 2)

    def test_main_window_independently_ignores_queued_old_session_events(self):
        first = self.make_session("queued-first", 1)
        second = self.make_session("queued-second", 2)
        self.window.handle_event(first)
        self.window.handle_event(second)
        self.emit_for_active(
            "clean_lines", lines=["[0.00s -> 1.00s] current clean"], clean_count=1
        )
        self.emit_for_active(
            "raw_lines", lines=["[0.00s -> 1.00s] current raw"], raw_count=1
        )
        before = (
            self.window.clean_table.table.rowCount(),
            self.window.raw_table.table.rowCount(),
            self.window.clean_count,
            self.window.raw_count,
            self.window.status_label.text(),
            self.window.logs_text.toPlainText(),
        )
        old_scope = {
            "session_id": first["session_id"],
            "session_generation": first["session_generation"],
        }
        with patch.object(ui_module.QMessageBox, "critical") as critical:
            self.window.handle_event(
                {"type": "clean_lines", "lines": ["late clean"], "clean_count": 99, **old_scope}
            )
            self.window.handle_event(
                {"type": "raw_lines", "lines": ["late raw"], "raw_count": 99, **old_scope}
            )
            self.window.handle_event(
                {
                    "type": "state",
                    "state": EngineState.ERROR.value,
                    "message": "late state",
                    **old_scope,
                }
            )
            self.window.handle_event(
                {"type": "error", "message": "late error", **old_scope}
            )
            self.window.handle_event(first)
            critical.assert_not_called()

        self.assertEqual(
            (
                self.window.clean_table.table.rowCount(),
                self.window.raw_table.table.rowCount(),
                self.window.clean_count,
                self.window.raw_count,
                self.window.status_label.text(),
                self.window.logs_text.toPlainText(),
            ),
            before,
        )
        self.assertEqual(self.window.current_clean_path, Path(second["clean_path"]))

    def test_bilingual_labels_retranslate_immediately(self):
        self.assertEqual(self.window.ui_language_title_label.text(), "语言/Language")
        self.assertEqual(self.window.original_language_title_label.text(), "音频原始语言")
        self.assertEqual(self.window.copy_clean_path_button.text(), "复制 Clean 路径")
        self.assertEqual(self.window.copy_clean_text_button.text(), "复制新增文本")
        self.assertEqual(self.window.rename_clean_button.text(), "重命名 Clean TXT")

        english_index = self.window.ui_language_combo.findData(UI_LANGUAGE_EN)
        self.window.ui_language_combo.setCurrentIndex(english_index)
        self.app.processEvents()
        self.assertEqual(self.window.ui_language_title_label.text(), "Interface Language")
        self.assertEqual(
            self.window.original_language_title_label.text(),
            "Audio / Original Language",
        )
        self.assertEqual(self.window.copy_clean_path_button.text(), "Copy Clean Path")
        self.assertEqual(self.window.copy_clean_text_button.text(), "Copy New Text")
        self.assertEqual(self.window.rename_clean_button.text(), "Rename Clean TXT")


if __name__ == "__main__":
    unittest.main()
