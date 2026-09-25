import os
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import transcript_store as store_module  # noqa: E402
import ui_app  # noqa: E402
from settings import UI_LANGUAGE_EN, UI_LANGUAGE_ZH  # noqa: E402
from transcript_store import CleanRenameError, TranscriptStore  # noqa: E402
from transcription_controller import EngineState, TranscriptionController  # noqa: E402


class StoreRenameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="clean_rename_store_")
        self.store = TranscriptStore(Path(self.tmp.name), session_id="session")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_active_append_repeat_rename_and_stop_preserve_bytes_and_inode(self):
        store = self.store
        original = store.clean_path
        inode = original.stat().st_ino
        self.assertEqual(store.rename_clean("clean"), original)
        store.append_clean(["first", "你好"])
        first = store.rename_clean("notes")
        self.assertFalse(original.exists())
        self.assertEqual(first.stat().st_ino, inode)
        store.append_clean(["third"])
        second = store.rename_clean("讲座")
        store.append_clean(["fourth"])
        store.close()
        self.assertEqual(second.stat().st_ino, inode)
        self.assertEqual(second.read_bytes(), "first\n你好\nthird\nfourth\n".encode())
        self.assertEqual(store.rename_clean("after-stop"), second.with_name("after-stop.txt"))
        self.assertEqual(store.clean_path.read_bytes(), "first\n你好\nthird\nfourth\n".encode())

    def test_invalid_names_do_not_change_path(self):
        for name in ("", " ", ".", "..", " ../x", "../x", "a/b", "a\\b", "a:b", "a\nx", "a\u0085x", "name.txt", "name.TXT", " x "):
            with self.subTest(name=name), self.assertRaises(CleanRenameError):
                self.store.rename_clean(name)
            self.assertEqual(self.store.clean_path.name, "clean.txt")
        self.store.append_clean(["still usable"])
        self.assertEqual(self.store.clean_path.read_text(), "still usable\n")

    def test_missing_symlink_existing_and_race_leave_source_usable(self):
        store = self.store
        source = store.clean_path
        target = store.session_dir / "target.txt"
        target.write_text("keep")
        with self.assertRaises(CleanRenameError):
            store.rename_clean("target")
        self.assertEqual(target.read_text(), "keep")
        target.unlink()
        target.symlink_to(source)
        with self.assertRaises(CleanRenameError):
            store.rename_clean("target")
        target.unlink()
        real_noreplace = store_module._rename_noreplace

        def competing_create(src, dst, dir_fd):
            dst.write_text("competitor")
            return real_noreplace(src, dst, dir_fd)

        with patch.object(store_module, "_rename_noreplace", side_effect=competing_create):
            with self.assertRaises(CleanRenameError):
                store.rename_clean("target")
        self.assertEqual(target.read_text(), "competitor")
        target.unlink()
        with patch.object(store_module, "_rename_noreplace", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                store.rename_clean("target")
        self.assertEqual(store.clean_path, source)
        store.append_clean(["safe"])
        self.assertEqual(source.read_text(), "safe\n")
        source.unlink()
        with self.assertRaises(CleanRenameError):
            store.rename_clean("missing")
        source.symlink_to(target)
        with self.assertRaises(CleanRenameError):
            store.rename_clean("linked")
        source.unlink()
        source.mkdir()
        with self.assertRaisesRegex(CleanRenameError, "source_unsafe"):
            store.rename_clean("directory")
        source.rmdir()

    def test_unavailable_primitive_fails_closed(self):
        with patch.object(store_module.sys, "platform", "unsupported"):
            with self.assertRaisesRegex(CleanRenameError, "rename_unavailable"):
                self.store.rename_clean("other")
        self.assertTrue(self.store.clean_path.exists())

    def test_cleanup_error_preserves_pre_rename_failure(self):
        source = self.store.clean_path
        real_close = os.close

        def close_then_raise(fd):
            real_close(fd)
            raise OSError("injected directory close error")

        with patch.object(store_module, "_rename_noreplace", side_effect=PermissionError("denied")):
            with patch.object(store_module.os, "close", side_effect=close_then_raise):
                with self.assertRaisesRegex(PermissionError, "denied"):
                    self.store.rename_clean("other")
        self.assertEqual(self.store.clean_path, source)
        self.assertTrue(source.exists())

    def test_unverified_destination_is_not_reported_as_success(self):
        source = self.store.clean_path
        with patch.object(store_module, "_rename_noreplace", return_value=None):
            with self.assertRaisesRegex(CleanRenameError, "rename_outcome_ambiguous"):
                self.store.rename_clean("not_moved")
        self.assertEqual(self.store.clean_path, source)
        self.assertTrue(source.exists())
        self.assertFalse((self.store.session_dir / "not_moved.txt").exists())

    def test_background_close_and_rename_finish_without_deadlock(self):
        self.store.append_clean(["before"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            rename = pool.submit(self.store.rename_clean, "concurrent")
            close = pool.submit(self.store.close)
            self.assertEqual(rename.result(timeout=3).name, "concurrent.txt")
            close.result(timeout=3)
        self.assertEqual(self.store.clean_path.read_bytes(), b"before\n")

    def test_append_waits_for_rename_and_keeps_complete_lines(self):
        store = self.store
        source = store.clean_path
        inode = source.stat().st_ino
        store.append_clean(["before"])
        rename_entered = threading.Event()
        release_rename = threading.Event()
        append_started = threading.Event()
        append_finished = threading.Event()
        real_noreplace = store_module._rename_noreplace

        def held_rename(src, dst, dir_fd):
            rename_entered.set()
            if not release_rename.wait(3):
                raise TimeoutError("rename was not released")
            return real_noreplace(src, dst, dir_fd)

        def append_during_rename():
            append_started.set()
            store.append_clean(["during one", "during two"])
            append_finished.set()

        with patch.object(store_module, "_rename_noreplace", side_effect=held_rename):
            with ThreadPoolExecutor(max_workers=2) as pool:
                try:
                    rename = pool.submit(store.rename_clean, "interleaved")
                    self.assertTrue(rename_entered.wait(3))
                    append = pool.submit(append_during_rename)
                    self.assertTrue(append_started.wait(3))
                    self.assertFalse(append_finished.wait(0.05))
                    self.assertEqual(store.clean_lines, 1)
                finally:
                    release_rename.set()
                destination = rename.result(timeout=3)
                append.result(timeout=3)
        store.append_clean(["after"])
        self.assertFalse(source.exists())
        self.assertEqual(destination.stat().st_ino, inode)
        self.assertEqual(store.clean_path, destination)
        self.assertEqual(store.clean_lines, 4)
        self.assertEqual(destination.read_bytes(), b"before\nduring one\nduring two\nafter\n")

    def test_replaced_session_directory_is_rejected(self):
        store = self.store
        replacement = Path(self.tmp.name) / "replacement"
        replacement.mkdir()
        moved = Path(self.tmp.name) / "moved"
        store.session_dir.rename(moved)
        store.session_dir.symlink_to(replacement, target_is_directory=True)
        with self.assertRaisesRegex(CleanRenameError, "source_unsafe"):
            store.rename_clean("escape")
        store.session_dir.unlink()
        moved.rename(store.session_dir)
        self.assertEqual(store.rename_clean("safe").name, "safe.txt")


class ControllerRenameTests(unittest.TestCase):
    def test_generation_guards_current_store_and_new_session(self):
        with tempfile.TemporaryDirectory(prefix="clean_rename_controller_") as temp:
            first = TranscriptStore(Path(temp), "first")
            second = TranscriptStore(Path(temp), "second")
            controller = TranscriptionController()
            controller.store = first
            controller.active_session_id = "one"
            controller.active_session_generation = 1
            first.append_clean(["old"])
            self.assertEqual(controller.rename_clean("renamed", "one", 1), first.clean_path)
            first.close()
            controller.store = second
            controller.active_session_id = "two"
            controller.active_session_generation = 2
            with self.assertRaisesRegex(ValueError, "stale_session"):
                controller.rename_clean("stale", "one", 1)
            self.assertEqual(controller.state, EngineState.IDLE)
            self.assertEqual(second.clean_path.name, "clean.txt")
            self.assertEqual(first.clean_path.read_text(), "old\n")
            second.close()


class WindowRenameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ui_app.QApplication.instance() or ui_app.QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="clean_rename_window_")
        root = Path(self.tmp.name)
        settings = SimpleNamespace(
            ui_language=UI_LANGUAGE_ZH, selected_model_path=None,
            selected_model_name="", default_beam_size=5,
            output_base_dir=root, download_model_dir=root / "models",
            model_dirs=[], imported_model_paths=[],
        )
        self.patchers = [
            patch.object(ui_app, "load_app_settings", return_value=settings),
            patch.object(ui_app, "save_app_settings"),
            patch.object(ui_app, "scan_model_dirs", return_value=[]),
            patch.object(ui_app, "crash_log"),
            patch.object(ui_app.QMessageBox, "information"),
            patch.object(ui_app.QMessageBox, "warning"),
        ]
        started = [item.start() for item in self.patchers]
        self.info_mock, self.warn_mock = started[-2:]
        self.window = ui_app.MainWindow()
        self.store = TranscriptStore(root, "session")
        self.window.controller.store = self.store
        self.window.controller.active_session_id = "owner"
        self.window.controller.active_session_generation = 1
        self.window.handle_event({
            "type": "session", "session_id": "owner", "session_generation": 1,
            "session_dir": str(self.store.session_dir), "clean_path": str(self.store.clean_path),
        })

    def tearDown(self):
        self.window.safe_shutdown()
        self.window.close()
        self.store.close()
        for item in reversed(self.patchers):
            item.stop()
        ui_app.set_current_language(UI_LANGUAGE_ZH)
        self.tmp.cleanup()

    def test_toolbar_path_buttons_cursor_and_stale_event(self):
        window = self.window
        toolbar = window.clean_table.toolbar
        self.assertLess(toolbar.indexOf(window.rename_clean_button), toolbar.indexOf(window.copy_clean_text_button))
        self.assertLess(toolbar.indexOf(window.copy_clean_text_button), toolbar.indexOf(window.clean_table.jump_button))
        self.assertEqual(window.raw_table.toolbar.indexOf(window.rename_clean_button), -1)
        self.assertEqual(window.raw_table.toolbar.indexOf(window.copy_clean_text_button), -1)
        window.handle_event({"type": "clean_lines", "session_id": "owner", "session_generation": 1,
                             "lines": ["[0.00s -> 1.00s] first"], "clean_count": 1})
        window.copy_clean_text()
        self.assertEqual(window.clean_copy_row_cursor, 1)
        old = self.store.clean_path
        window.rename_clean_file("notes")
        self.assertFalse(old.exists())
        self.assertEqual(window.current_clean_path, self.store.clean_path)
        self.assertEqual(window.clean_copy_row_cursor, 1)
        self.assertEqual(window.clean_table.table.rowCount(), 1)
        with patch.object(ui_app.subprocess, "run") as run:
            window.reveal_clean_file()
            run.assert_called_once_with(["open", "-R", str(self.store.clean_path)], check=False)
        window.copy_clean_path()
        self.assertEqual(self.app.clipboard().text(), str(self.store.clean_path.resolve()))
        window.handle_event({"type": "session", "session_id": "stale", "session_generation": 1,
                             "session_dir": str(old.parent), "clean_path": str(old)})
        self.assertEqual(window.current_clean_path, self.store.clean_path)
        window.rename_clean_file("notes.txt")
        self.assertEqual(self.store.clean_path.name, "notes.txt")
        self.warn_mock.assert_called_once()
        self.assertEqual(window.clean_copy_row_cursor, 1)
        self.store.close()
        window.handle_event({"type": "state", "state": "Idle", "session_id": "owner",
                             "session_generation": 1})
        window.rename_clean_file("after-stop")
        self.assertEqual(window.current_clean_path.name, "after-stop.txt")
        self.assertEqual(window.clean_copy_row_cursor, 1)
        next_store = TranscriptStore(Path(self.tmp.name), "next")
        window.controller.store = next_store
        window.controller.active_session_id = "next-owner"
        window.controller.active_session_generation = 2
        window.handle_event({"type": "session", "session_id": "next-owner", "session_generation": 2,
                             "session_dir": str(next_store.session_dir), "clean_path": str(next_store.clean_path)})
        window.handle_event({"type": "session", "session_id": "owner", "session_generation": 1,
                             "session_dir": str(self.store.session_dir), "clean_path": str(self.store.clean_path)})
        self.assertEqual(window.current_clean_path, next_store.clean_path)
        self.assertEqual(window.clean_copy_row_cursor, 0)
        self.assertEqual(next_store.clean_path.name, "clean.txt")
        next_store.close()

    def test_dialog_cancellation_and_language_feedback(self):
        old = self.store.clean_path
        def reject_dialog(dialog):
            labels = [label.text() for label in dialog.findChildren(ui_app.QLabel)]
            self.assertIn(".txt", labels)
            self.assertEqual(len(dialog.findChildren(ui_app.QLineEdit)), 1)
            return ui_app.QDialog.Rejected

        with patch.object(ui_app.QDialog, "exec", reject_dialog):
            self.window.rename_clean_file()
        self.assertEqual(self.store.clean_path, old)
        self.info_mock.assert_not_called()
        self.warn_mock.assert_not_called()
        index = self.window.ui_language_combo.findData(UI_LANGUAGE_EN)
        self.window.ui_language_combo.setCurrentIndex(index)
        self.window.rename_clean_file("bad.txt")
        self.assertEqual(self.store.clean_path, old)
        self.assertIn("suffix", self.warn_mock.call_args.args[2])
        self.assertIn("absolute path", self.window.copy_clean_path_button.toolTip())
        self.window.rename_clean_file("good")
        self.assertIn("good.txt", self.info_mock.call_args.args[2])

    def test_cleanup_error_after_rename_updates_ui_and_keeps_writer(self):
        source = self.store.clean_path
        inode = source.stat().st_ino
        self.store.append_clean(["before"])
        real_close = os.close

        def close_then_raise(fd):
            real_close(fd)
            raise OSError("injected directory close error")

        with patch.object(store_module.os, "close", side_effect=close_then_raise) as close_mock:
            self.window.rename_clean_file("after_cleanup_error")
        close_mock.assert_called_once()
        destination = self.store.clean_path
        self.assertFalse(source.exists())
        self.assertEqual(destination.name, "after_cleanup_error.txt")
        self.assertEqual(self.window.current_clean_path, destination)
        self.assertEqual(destination.stat().st_ino, inode)
        self.info_mock.assert_called_once()
        self.warn_mock.assert_not_called()
        self.store.append_clean(["after"])
        self.assertEqual(destination.read_bytes(), b"before\nafter\n")


if __name__ == "__main__":
    unittest.main()
