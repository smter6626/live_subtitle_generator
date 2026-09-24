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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import ui_app as ui_module  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, QRect, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QWidget  # noqa: E402
from settings import UI_LANGUAGE_EN, UI_LANGUAGE_ZH  # noqa: E402


class MainWindowLayoutTests(unittest.TestCase):
    matrix = []

    @classmethod
    def setUpClass(cls):
        cls.app = ui_module.QApplication.instance() or ui_module.QApplication([])

    @classmethod
    def tearDownClass(cls):
        evidence_path = os.environ.get("WINDOW_LAYOUT_EVIDENCE_PATH")
        if evidence_path:
            Path(evidence_path).write_text(
                json.dumps(cls.matrix, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="window_layout_ui_")
        root = Path(self.tmp.name)
        self.app_settings = SimpleNamespace(
            ui_language=UI_LANGUAGE_ZH,
            selected_model_path=None,
            selected_model_name="",
            default_beam_size=5,
            output_base_dir=root,
            download_model_dir=root / "models",
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
        self.windows = []

    def tearDown(self):
        for window in reversed(self.windows):
            window.safe_shutdown()
            window.close()
        self.app.processEvents()
        for patcher in reversed(self.patchers):
            patcher.stop()
        ui_module.set_current_language(UI_LANGUAGE_ZH)
        self.tmp.cleanup()

    def make_window(self, geometry):
        available = [QRect(geometry)]
        window = ui_module.MainWindow(lambda: QRect(available[0]))
        self.windows.append(window)
        window.show()
        self.app.processEvents()
        self.app.processEvents()
        return window, available

    def is_visible_in_controls_viewport(self, window, widget):
        viewport = window.controls_scroll_area.viewport()
        center = widget.mapTo(viewport, widget.rect().center())
        return viewport.rect().contains(center)

    def send_wheel(self, target, delta=-120):
        center = target.rect().center()
        event = QWheelEvent(
            QPointF(center),
            QPointF(target.mapToGlobal(center)),
            QPoint(),
            QPoint(0, delta),
            Qt.NoButton,
            Qt.NoModifier,
            Qt.ScrollUpdate,
            False,
        )
        self.app.sendEvent(target, event)
        self.app.processEvents()
        return event.isAccepted()

    def matrix_row(self, name, injected, window, right_side=None):
        first = window.start_button
        last = window.copy_clean_text_button
        scroll_bar = window.controls_scroll_area.verticalScrollBar()
        return {
            "case": name,
            "injected_available_geometry": [
                injected.x(),
                injected.y(),
                injected.width(),
                injected.height(),
            ],
            "frame_size": [
                window.frameGeometry().width(),
                window.frameGeometry().height(),
            ],
            "client_size": [window.width(), window.height()],
            "minimum_size": [window.minimumWidth(), window.minimumHeight()],
            "minimum_size_hint": [
                window.minimumSizeHint().width(),
                window.minimumSizeHint().height(),
            ],
            "controls_scroll_range": [scroll_bar.minimum(), scroll_bar.maximum()],
            "controls_scroll_value": scroll_bar.value(),
            "first_visible": self.is_visible_in_controls_viewport(window, first),
            "last_visible": self.is_visible_in_controls_viewport(window, last),
            "focus_widget": (
                self.app.focusWidget().objectName()
                if self.app.focusWidget() is not None
                else None
            ),
            "focus_visible": (
                self.is_visible_in_controls_viewport(window, self.app.focusWidget())
                if self.app.focusWidget() is not None
                and window.controls_panel.isAncestorOf(self.app.focusWidget())
                else None
            ),
            "right_side_scroll_results": right_side or {},
        }

    def test_show_path_bounds_multiple_available_geometries_and_scrolls_controls(self):
        cases = (
            ("normal", QRect(0, 0, 1600, 1000), False),
            ("short", QRect(0, 0, 1400, 480), True),
            ("very_short", QRect(0, 0, 1200, 320), True),
        )
        for name, geometry, expect_scroll in cases:
            with self.subTest(name=name):
                window, _available = self.make_window(geometry)
                self.assertLessEqual(window.frameGeometry().height(), geometry.height())
                self.assertLessEqual(window.height(), geometry.height())
                self.assertEqual(window.minimumHeight(), 0)
                scroll_bar = window.controls_scroll_area.verticalScrollBar()
                if expect_scroll:
                    self.assertGreater(scroll_bar.maximum(), 0)
                self.assertIs(window.controls_scroll_area.widget(), window.controls_panel)
                self.assertFalse(window.controls_panel.isAncestorOf(window.status_strip))
                self.assertFalse(window.controls_panel.isAncestorOf(window.tabs))
                type(self).matrix.append(self.matrix_row(name, geometry, window))

    def test_scrollbar_and_tab_traversal_reach_first_and_last_controls(self):
        geometry = QRect(0, 0, 1400, 480)
        window, _available = self.make_window(geometry)
        scroll_bar = window.controls_scroll_area.verticalScrollBar()
        self.assertGreater(scroll_bar.maximum(), 0)

        scroll_bar.setValue(scroll_bar.minimum())
        self.app.processEvents()
        self.assertTrue(self.is_visible_in_controls_viewport(window, window.start_button))
        scroll_bar.setValue(scroll_bar.maximum())
        self.app.processEvents()
        self.assertTrue(
            self.is_visible_in_controls_viewport(window, window.copy_clean_text_button)
        )

        for widget in window.controls_panel.findChildren(QWidget):
            if widget.focusPolicy() & Qt.TabFocus:
                widget.setEnabled(True)
        scroll_bar.setValue(0)
        window.activateWindow()
        window.start_button.setFocus(Qt.OtherFocusReason)
        self.app.processEvents()
        for _attempt in range(40):
            if self.app.focusWidget() is window.copy_clean_text_button:
                break
            QTest.keyClick(self.app.focusWidget(), Qt.Key_Tab)
            self.app.processEvents()
        self.assertIs(self.app.focusWidget(), window.copy_clean_text_button)
        self.assertTrue(
            self.is_visible_in_controls_viewport(window, window.copy_clean_text_button)
        )

        for _attempt in range(40):
            if self.app.focusWidget() is window.start_button:
                break
            QTest.keyClick(self.app.focusWidget(), Qt.Key_Tab, Qt.ShiftModifier)
            self.app.processEvents()
        self.assertIs(self.app.focusWidget(), window.start_button)
        self.assertTrue(self.is_visible_in_controls_viewport(window, window.start_button))
        type(self).matrix.append(self.matrix_row("keyboard_round_trip", geometry, window))

    def test_wheel_ownership_is_left_local_and_right_surfaces_remain_independent(self):
        geometry = QRect(0, 0, 1400, 480)
        window, _available = self.make_window(geometry)
        controls_bar = window.controls_scroll_area.verticalScrollBar()
        controls_bar.setValue(0)
        self.assertTrue(self.send_wheel(window.controls_scroll_area.viewport()))
        self.assertGreater(controls_bar.value(), 0)

        right_results = {}
        for tab_index, name, table in (
            (0, "clean", window.clean_table.table),
            (1, "raw", window.raw_table.table),
        ):
            for row in range(80):
                table.insertRow(row)
                table.setItem(row, 0, ui_module.QTableWidgetItem(str(row)))
                table.setItem(row, 1, ui_module.QTableWidgetItem(f"{name} {row}"))
            window.tabs.setCurrentIndex(tab_index)
            self.app.processEvents()
            table.verticalScrollBar().setValue(0)
            controls_before = controls_bar.value()
            accepted = self.send_wheel(table.viewport())
            right_results[name] = {
                "accepted": accepted,
                "value": table.verticalScrollBar().value(),
                "controls_unchanged": controls_bar.value() == controls_before,
            }
            self.assertGreater(table.verticalScrollBar().value(), 0)
            self.assertEqual(controls_bar.value(), controls_before)

        for row in range(200):
            window.logs_text.appendPlainText(f"log {row}")
        window.tabs.setCurrentIndex(2)
        self.app.processEvents()
        logs_bar = window.logs_text.verticalScrollBar()
        logs_bar.setValue(0)
        controls_before = controls_bar.value()
        accepted = self.send_wheel(window.logs_text.viewport())
        right_results["logs"] = {
            "accepted": accepted,
            "value": logs_bar.value(),
            "controls_unchanged": controls_bar.value() == controls_before,
        }
        self.assertGreater(logs_bar.value(), 0)
        self.assertEqual(controls_bar.value(), controls_before)
        type(self).matrix.append(
            self.matrix_row("scroll_ownership", geometry, window, right_results)
        )

    def test_geometry_handler_resize_and_retranslation_preserve_bounds_and_reachability(self):
        normal = QRect(0, 0, 1600, 1000)
        short = QRect(0, 0, 1400, 480)
        window, available = self.make_window(normal)
        window.resize(window.width(), 900)
        self.app.processEvents()
        self.assertGreater(window.height(), short.height())

        available[0] = short
        window._on_available_geometry_changed(short)
        self.app.processEvents()
        self.assertLessEqual(window.frameGeometry().height(), short.height())
        self.assertGreater(window.controls_scroll_area.verticalScrollBar().maximum(), 0)

        english_index = window.ui_language_combo.findData(UI_LANGUAGE_EN)
        window.ui_language_combo.setCurrentIndex(english_index)
        self.app.processEvents()
        self.assertEqual(window.start_button.text(), "Start Recording")
        self.assertLessEqual(window.frameGeometry().height(), short.height())
        window.controls_scroll_area.ensureWidgetVisible(window.copy_clean_text_button)
        self.app.processEvents()
        self.assertTrue(
            self.is_visible_in_controls_viewport(window, window.copy_clean_text_button)
        )

        chinese_index = window.ui_language_combo.findData(UI_LANGUAGE_ZH)
        window.ui_language_combo.setCurrentIndex(chinese_index)
        window._on_effective_screen_changed(window._effective_screen())
        self.app.processEvents()
        self.assertEqual(window.start_button.text(), "开始录音")
        self.assertLessEqual(window.frameGeometry().height(), short.height())
        self.assertGreater(window.controls_scroll_area.verticalScrollBar().maximum(), 0)
        type(self).matrix.append(self.matrix_row("resize_retranslate", short, window))

        available[0] = normal
        window._on_available_geometry_changed(normal)
        window.resize(window.width(), 800)
        self.app.processEvents()
        self.assertEqual(window.height(), 800)
        self.assertLessEqual(window.frameGeometry().height(), normal.height())
        type(self).matrix.append(self.matrix_row("normal_resize_restored", normal, window))


if __name__ == "__main__":
    unittest.main()
