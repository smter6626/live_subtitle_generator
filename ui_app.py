import subprocess
import sys
import threading
import time
from pathlib import Path

from crash_debug import (
    CRASH_LOG_PATH,
    install as install_crash_logging,
    log as crash_log,
    log_exception,
    log_startup_environment,
)

try:
    from PySide6.QtCore import QObject, Qt, QTimer, Signal
    from PySide6.QtGui import QBrush, QColor
    from PySide6.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QComboBox,
        QDialog,
        QFileDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHeaderView,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError:
    print("PySide6 is not installed.")
    print("Install it with: python -m pip install PySide6")
    raise SystemExit(1)

from settings import (
    BACKEND_DISPLAY,
    DEFAULT_BEAM_SIZE,
    DEFAULT_ORIGINAL_LANGUAGE_LABEL,
    DEFAULT_UI_LANGUAGE,
    MAX_BEAM_SIZE,
    MIN_BEAM_SIZE,
    ORIGINAL_LANGUAGE_OPTIONS,
    UI_LANGUAGE_ZH,
)
from model_manager import (
    DOWNLOADABLE_MODELS,
    choose_default_model,
    default_scan_model_dirs,
    download_and_publish_model,
    download_target_path,
    ensure_model_dir,
    format_model_path,
    load_app_settings,
    save_app_settings,
    scan_model_dirs,
    validate_import_model,
)
from transcript_store import format_runtime, parse_transcript_line
from transcription_controller import EngineState, TranscriptionController


TEXT = {
    "zh": {
        "window_title": "Whisper 课堂实时转写",
        "status": "状态",
        "backend": "后端",
        "model": "模型",
        "beam": "Beam",
        "language": "Language",
        "original_language": "Original Language",
        "runtime": "运行时长",
        "queue": "队列",
        "output_folder": "输出目录",
        "idle": "空闲",
        "starting": "启动中",
        "recording": "录音中",
        "stopping": "停止中 / 完成转写中",
        "error": "错误",
        "controls": "控制",
        "start_recording": "开始录音",
        "stop_recording": "停止录音",
        "beam_size": "Beam Size",
        "mark_now": "标记当前",
        "mark_tooltip": "TODO：之后会加入课堂时间点标记。",
        "model_group": "模型",
        "current_model": "当前",
        "model_dropdown": "选择模型",
        "manage_models": "管理模型",
        "refresh_models": "刷新模型",
        "no_model_selected": "未选择模型",
        "model_manager": "模型管理",
        "local_models": "本地模型",
        "name": "名称",
        "size": "大小",
        "path": "路径",
        "status_column": "状态",
        "select_model": "选择模型",
        "import_existing_model": "导入已有模型",
        "download_model": "下载模型",
        "download_location": "下载位置",
        "choose_folder": "选择文件夹",
        "download_target": "下载目标",
        "close": "关闭",
        "model_already_exists": "Model already exists.",
        "cannot_create_model_download_directory": "无法创建模型下载目录",
        "model_import_error": "模型导入失败",
        "model_download_error": "模型下载失败",
        "model_download_started": "开始下载模型",
        "model_download_complete": "模型下载完成",
        "model_download_failed": "模型下载失败",
        "model_selected": "已选择模型",
        "open_output_folder": "打开输出目录",
        "export_clean_txt": "定位 Clean TXT",
        "session": "本次 Session",
        "start_time": "开始时间",
        "raw_lines": "Raw 行数",
        "clean_lines": "Clean 行数",
        "clean_transcript": "Clean 转写",
        "raw_transcript": "Raw 转写",
        "logs": "日志",
        "jump_to_live": "跳到最新",
        "time": "时间",
        "text": "正文",
        "starting_session": "正在启动 session。",
        "stopping_session": "正在停止 session。",
        "transcription_error": "转写错误",
        "unknown_error": "未知错误。",
        "stop_dialog_title": "停止录音",
        "stop_dialog_body": "录音仍在运行。关闭窗口前是否停止录音？",
        "stop_complete": "停止完成。",
    },
    "en": {
        "window_title": "Whisper Classroom Transcriber",
        "status": "Status",
        "backend": "Backend",
        "model": "Model",
        "beam": "Beam",
        "language": "Language",
        "original_language": "Original Language",
        "runtime": "Runtime",
        "queue": "Queue",
        "output_folder": "Output folder",
        "idle": "Idle",
        "starting": "Starting",
        "recording": "Recording",
        "stopping": "Stopping / Finishing transcription",
        "error": "Error",
        "controls": "Controls",
        "start_recording": "Start Recording",
        "stop_recording": "Stop Recording",
        "beam_size": "Beam Size",
        "mark_now": "Mark Now",
        "mark_tooltip": "TODO: session markers will be added later.",
        "model_group": "Model",
        "current_model": "Current",
        "model_dropdown": "Model",
        "manage_models": "Manage Models",
        "refresh_models": "Refresh Models",
        "no_model_selected": "No model selected",
        "model_manager": "Model Manager",
        "local_models": "Local models",
        "name": "Name",
        "size": "Size",
        "path": "Path",
        "status_column": "Status",
        "select_model": "Select Model",
        "import_existing_model": "Import Existing Model",
        "download_model": "Download Model",
        "download_location": "Download Location",
        "choose_folder": "Choose Folder",
        "download_target": "Download target",
        "close": "Close",
        "model_already_exists": "Model already exists.",
        "cannot_create_model_download_directory": "Cannot create model download directory",
        "model_import_error": "Model Import Error",
        "model_download_error": "Model Download Error",
        "model_download_started": "Starting model download",
        "model_download_complete": "Model download complete",
        "model_download_failed": "Model download failed",
        "model_selected": "Model selected",
        "open_output_folder": "Open Output Folder",
        "export_clean_txt": "Export Clean TXT",
        "session": "Session",
        "start_time": "Start time",
        "raw_lines": "Raw lines",
        "clean_lines": "Clean lines",
        "clean_transcript": "Clean Transcript",
        "raw_transcript": "Raw Transcript",
        "logs": "Logs",
        "jump_to_live": "Jump to Live",
        "time": "Time",
        "text": "Text",
        "starting_session": "Starting session.",
        "stopping_session": "Stopping session.",
        "transcription_error": "Transcription Error",
        "unknown_error": "Unknown error.",
        "stop_dialog_title": "Stop Recording",
        "stop_dialog_body": "Recording is still running. Stop it before closing?",
        "stop_complete": "Stop complete.",
    },
}


def current_language():
    return DEFAULT_UI_LANGUAGE if DEFAULT_UI_LANGUAGE in TEXT else UI_LANGUAGE_ZH


def tr(key):
    language = current_language()
    return TEXT[language].get(key, TEXT["en"].get(key, key))


def display_status(status):
    mapping = {
        EngineState.IDLE.value: tr("idle"),
        EngineState.STARTING.value: tr("starting"),
        EngineState.RECORDING.value: tr("recording"),
        EngineState.STOPPING.value: tr("stopping"),
        EngineState.ERROR.value: tr("error"),
    }
    return mapping.get(status, status)


class EventBridge(QObject):
    event_received = Signal(dict)


class TranscriptTable(QWidget):
    def __init__(self, title: str):
        super().__init__()
        self.live_mode = True
        self.title = title

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        self.jump_button = QPushButton(tr("jump_to_live"))
        self.jump_button.clicked.connect(self.jump_to_live)
        toolbar.addWidget(self.jump_button)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([tr("time"), tr("text")])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 90)
        self.table.verticalScrollBar().valueChanged.connect(self._on_scroll)
        layout.addWidget(self.table)

    def append_lines(self, lines):
        should_scroll = self.live_mode or self._is_at_bottom()
        for line in lines:
            parsed = parse_transcript_line(line)
            row = self.table.rowCount()
            self.table.insertRow(row)

            time_item = QTableWidgetItem(parsed["time"])
            time_item.setToolTip(parsed["range"])
            time_item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)

            text_item = QTableWidgetItem(parsed["text"])
            text_item.setToolTip(parsed["range"])
            text_item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)

            time_item.setForeground(QBrush(QColor("#4b5563")))
            text_item.setForeground(QBrush(QColor("#111827")))

            self.table.setItem(row, 0, time_item)
            self.table.setItem(row, 1, text_item)
            self.table.resizeRowToContents(row)

        if should_scroll:
            self.jump_to_live()

    def jump_to_live(self):
        self.live_mode = True
        self.table.scrollToBottom()

    def _is_at_bottom(self):
        scroll_bar = self.table.verticalScrollBar()
        return scroll_bar.value() >= scroll_bar.maximum() - 3

    def _on_scroll(self):
        self.live_mode = self._is_at_bottom()


class ModelManagerDialog(QDialog):
    model_selected = Signal(object)
    models_changed = Signal()
    log_message = Signal(str, str)
    download_finished = Signal(bool, str)

    def __init__(self, app_settings, selected_model, parent=None):
        super().__init__(parent)
        crash_log("ModelManagerDialog init")
        self.setWindowTitle(tr("model_manager"))
        self.resize(900, 540)
        self.app_settings = app_settings
        self.selected_model = selected_model
        self.models = []
        self.downloading = False
        self.downloading_model_name = None
        self.download_finished.connect(self._handle_download_finished)

        layout = QVBoxLayout(self)

        self.current_label = QLabel()
        layout.addWidget(self.current_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [tr("name"), tr("size"), tr("path"), tr("status_column")]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.itemDoubleClicked.connect(lambda _item: self.select_current_row())
        layout.addWidget(self.table, stretch=1)

        location_row = QHBoxLayout()
        location_row.addWidget(QLabel(tr("download_location")))
        self.download_location_label = QLabel(format_model_path(self.app_settings.download_model_dir))
        self.download_location_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.download_location_label.setToolTip(str(self.app_settings.download_model_dir))
        location_row.addWidget(self.download_location_label, stretch=1)
        self.choose_download_folder_button = QPushButton(tr("choose_folder"))
        self.choose_download_folder_button.clicked.connect(self.choose_download_location)
        location_row.addWidget(self.choose_download_folder_button)
        layout.addLayout(location_row)

        download_row = QHBoxLayout()
        download_row.addWidget(QLabel(tr("download_model")))
        self.download_combo = QComboBox()
        for model_name in DOWNLOADABLE_MODELS:
            self.download_combo.addItem(model_name, model_name)
        download_row.addWidget(self.download_combo, stretch=1)
        self.download_button = QPushButton(tr("download_model"))
        self.download_button.clicked.connect(self.download_selected_model)
        download_row.addWidget(self.download_button)
        layout.addLayout(download_row)

        button_row = QHBoxLayout()
        self.select_button = QPushButton(tr("select_model"))
        self.select_button.clicked.connect(self.select_current_row)
        self.import_button = QPushButton(tr("import_existing_model"))
        self.import_button.clicked.connect(self.import_existing_model)
        self.refresh_button = QPushButton(tr("refresh_models"))
        self.refresh_button.clicked.connect(self.refresh_models)
        self.close_button = QPushButton(tr("close"))
        self.close_button.clicked.connect(self.reject)

        button_row.addWidget(self.select_button)
        button_row.addWidget(self.import_button)
        button_row.addWidget(self.refresh_button)
        button_row.addStretch()
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

        self.refresh_models()

    def refresh_models(self):
        self.models = scan_model_dirs(
            self.app_settings.model_dirs,
            self.app_settings.imported_model_paths,
            download_model_dir=self.app_settings.download_model_dir,
        )
        self.table.setRowCount(0)
        selected_key = self._selected_key()

        for model in self.models:
            row = self.table.rowCount()
            self.table.insertRow(row)
            items = [
                QTableWidgetItem(model.name),
                QTableWidgetItem(model.size_label),
                QTableWidgetItem(model.display_path),
                QTableWidgetItem(model.status),
            ]
            for item in items:
                item.setData(Qt.UserRole, str(model.path))
            if not model.is_available:
                for item in items:
                    item.setForeground(QBrush(QColor("#b45309")))
            for col, item in enumerate(items):
                self.table.setItem(row, col, item)
            if selected_key and selected_key == str(model.path.resolve()):
                self.table.selectRow(row)

        self._update_current_label()
        self._update_download_location_label()
        self.models_changed.emit()

    def choose_download_location(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("download_location"),
            str(self.app_settings.download_model_dir),
        )
        if not folder:
            return

        path = Path(folder).expanduser()
        try:
            ensure_model_dir(path)
        except RuntimeError as exc:
            QMessageBox.critical(
                self,
                tr("cannot_create_model_download_directory"),
                str(exc),
            )
            return

        self.app_settings.download_model_dir = path
        self.app_settings.model_dirs = default_scan_model_dirs(
            path,
            self.app_settings.model_dirs,
        )
        save_app_settings(self.app_settings)
        self._update_download_location_label()
        self.log_message.emit(f"{tr('download_location')}: {path}", "INFO")
        self.refresh_models()

    def import_existing_model(self):
        file_path, _filter = QFileDialog.getOpenFileName(
            self,
            tr("import_existing_model"),
            str(Path.home()),
            "Whisper models (*.bin *.gguf);;All files (*)",
        )
        if not file_path:
            return

        path = Path(file_path).expanduser()
        errors = validate_import_model(path)
        if errors:
            QMessageBox.warning(self, tr("model_import_error"), "\n".join(errors))
            return

        existing = {str(path.resolve()) for path in self.app_settings.imported_model_paths}
        if str(path.resolve()) not in existing:
            self.app_settings.imported_model_paths.append(path)
        self.app_settings.selected_model_path = path
        self.app_settings.selected_model_name = ""
        save_app_settings(self.app_settings)
        self.refresh_models()
        selected = self._model_by_path(path)
        if selected:
            self._select_model(selected)

    def download_selected_model(self):
        model_name = self.download_combo.currentData()
        try:
            download_dir = ensure_model_dir(self.app_settings.download_model_dir)
        except RuntimeError as exc:
            QMessageBox.critical(
                self,
                tr("cannot_create_model_download_directory"),
                str(exc),
            )
            self.log_message.emit(str(exc), "ERROR")
            return

        self.downloading = True
        self.downloading_model_name = model_name
        self.app_settings.download_model_dir = download_dir
        self.app_settings.model_dirs = default_scan_model_dirs(
            download_dir,
            self.app_settings.model_dirs,
        )
        save_app_settings(self.app_settings)
        self._set_download_controls(False)
        self.log_message.emit(f"{tr('model_download_started')}: {model_name}", "INFO")

        def worker():
            try:
                result = download_and_publish_model(
                    model_name,
                    target_dir=download_dir,
                    log_callback=lambda line: self.log_message.emit(line, "INFO"),
                )
                action = "verified existing model" if result.disposition == "reused" else "downloaded"
                self.download_finished.emit(
                    True,
                    f"{tr('model_download_complete')}: {model_name} ({action})",
                )
            except Exception as exc:
                self.download_finished.emit(False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_download_finished(self, ok: bool, message: str):
        model_name = self.downloading_model_name
        self.downloading = False
        self.downloading_model_name = None
        self._set_download_controls(True)
        self.log_message.emit(message, "INFO" if ok else "ERROR")
        if not ok:
            self.refresh_models()
            QMessageBox.critical(self, tr("model_download_error"), message)
            return

        self.refresh_models()
        target_path = download_target_path(
            model_name,
            self.app_settings.download_model_dir,
        )
        selected = self._model_by_path(target_path)
        if selected:
            self._select_model(selected)

    def select_current_row(self):
        model = self._selected_row_model()
        if not model:
            return
        if not model.is_available:
            QMessageBox.warning(
                self,
                tr("model_manager"),
                f"Model is not available: {model.status}\n{model.path}",
            )
            return
        self._select_model(model)

    def _select_model(self, model):
        self.selected_model = model
        self.app_settings.selected_model_path = model.path
        self.app_settings.selected_model_name = model.name
        save_app_settings(self.app_settings)
        self._update_current_label()
        self.model_selected.emit(model)
        self.log_message.emit(f"{tr('model_selected')}: {model.display_label}", "INFO")

    def _selected_row_model(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            return None
        path_text = selected_items[0].data(Qt.UserRole)
        return self._model_by_path(Path(path_text))

    def _model_by_path(self, path):
        key = str(Path(path).expanduser().resolve())
        for model in self.models:
            if str(model.path.resolve()) == key:
                return model
        return None

    def _selected_key(self):
        if self.selected_model:
            return str(self.selected_model.path.resolve())
        if self.app_settings.selected_model_path:
            return str(self.app_settings.selected_model_path.resolve())
        return ""

    def _update_current_label(self):
        if self.selected_model:
            self.current_label.setText(f"{tr('current_model')}: {self.selected_model.display_label}")
        else:
            self.current_label.setText(f"{tr('current_model')}: {tr('no_model_selected')}")

    def _update_download_location_label(self):
        if hasattr(self, "download_location_label"):
            path = self.app_settings.download_model_dir
            self.download_location_label.setText(format_model_path(path))
            self.download_location_label.setToolTip(str(path))

    def _set_download_controls(self, enabled: bool):
        self.download_combo.setEnabled(enabled)
        self.download_button.setEnabled(enabled)
        self.choose_download_folder_button.setEnabled(enabled)
        self.import_button.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)
        self.close_button.setEnabled(enabled)

    def reject(self):
        if self.downloading:
            QMessageBox.information(
                self,
                tr("download_model"),
                "A model download is still running.",
            )
            return
        crash_log("ModelManagerDialog reject")
        super().reject()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        crash_log("MainWindow init entered")
        self.setWindowTitle(tr("window_title"))
        self.resize(1200, 800)
        self._shutdown_started = False
        self._shutdown_complete = False
        self._stop_thread = None
        self.model_manager_dialog = None

        self.bridge = EventBridge()
        self.bridge.event_received.connect(lambda event: self._safe_slot(self.handle_event, event))
        self.controller = TranscriptionController(event_callback=self.bridge.event_received.emit)
        self.app_settings = load_app_settings()
        self.models = scan_model_dirs(
            self.app_settings.model_dirs,
            self.app_settings.imported_model_paths,
            download_model_dir=self.app_settings.download_model_dir,
        )
        self.selected_model = choose_default_model(
            self.models,
            self.app_settings.selected_model_path,
        )
        if self.selected_model:
            self.app_settings.selected_model_path = self.selected_model.path
            self.app_settings.selected_model_name = self.selected_model.name
        save_app_settings(self.app_settings)

        self.current_output_dir = None
        self.current_clean_path = None
        self.session_started_at = None
        self.queue_size = 0
        self.raw_count = 0
        self.clean_count = 0

        self._build_ui()
        self._apply_styles()
        self._populate_model_combo()
        self._update_model_labels()
        self._set_status(EngineState.IDLE.value)

        self.runtime_timer = QTimer(self)
        self.runtime_timer.timeout.connect(self._update_runtime_labels)
        self.runtime_timer.start(1000)
        crash_log("MainWindow init completed")

    def _build_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)
        root_layout.addWidget(self._build_status_strip())

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self._build_controls())
        body.addWidget(self._build_tabs(), stretch=1)
        root_layout.addLayout(body, stretch=1)

        self.setCentralWidget(root)

    def _build_status_strip(self):
        strip = QFrame()
        strip.setObjectName("statusStrip")
        layout = QGridLayout(strip)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(4)

        self.status_label = QLabel(display_status(EngineState.IDLE.value))
        self.backend_label = QLabel(BACKEND_DISPLAY)
        self.model_label = QLabel(self._selected_model_name())
        self.beam_status_label = QLabel(str(DEFAULT_BEAM_SIZE))
        self.language_status_label = QLabel(DEFAULT_ORIGINAL_LANGUAGE_LABEL)
        self.runtime_label = QLabel("00:00:00")
        self.queue_label = QLabel("0")
        self.output_folder_label = QLabel("-")
        self.output_folder_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        pairs = [
            (tr("status"), self.status_label),
            (tr("backend"), self.backend_label),
            (tr("model"), self.model_label),
            (tr("beam"), self.beam_status_label),
            (tr("language"), self.language_status_label),
            (tr("runtime"), self.runtime_label),
            (tr("queue"), self.queue_label),
            (tr("output_folder"), self.output_folder_label),
        ]
        for col, (name, label) in enumerate(pairs):
            title = QLabel(name)
            title.setObjectName("statusTitle")
            layout.addWidget(title, 0, col)
            layout.addWidget(label, 1, col)

        layout.setColumnStretch(len(pairs) - 1, 1)
        return strip

    def _build_controls(self):
        panel = QWidget()
        panel.setFixedWidth(310)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        controls = QGroupBox(tr("controls"))
        controls_layout = QVBoxLayout(controls)

        self.start_button = QPushButton(tr("start_recording"))
        self.start_button.clicked.connect(lambda: self._safe_slot(self.start_recording))
        self.stop_button = QPushButton(tr("stop_recording"))
        self.stop_button.clicked.connect(lambda: self._safe_slot(self.stop_recording))
        self.stop_button.setEnabled(False)

        self.beam_combo = QComboBox()
        for beam in range(MIN_BEAM_SIZE, MAX_BEAM_SIZE + 1):
            self.beam_combo.addItem(str(beam), beam)
        default_beam = self.app_settings.default_beam_size
        if default_beam < MIN_BEAM_SIZE or default_beam > MAX_BEAM_SIZE:
            default_beam = DEFAULT_BEAM_SIZE
        self.beam_combo.setCurrentText(str(default_beam))

        self.language_combo = QComboBox()
        for label in ORIGINAL_LANGUAGE_OPTIONS:
            self.language_combo.addItem(label, label)
        self.language_combo.setCurrentText(DEFAULT_ORIGINAL_LANGUAGE_LABEL)

        self.mark_button = QPushButton(tr("mark_now"))
        self.mark_button.setEnabled(False)
        self.mark_button.setToolTip(tr("mark_tooltip"))

        self.open_folder_button = QPushButton(tr("open_output_folder"))
        self.open_folder_button.clicked.connect(lambda: self._safe_slot(self.open_output_folder))
        self.open_folder_button.setEnabled(False)

        self.export_clean_button = QPushButton(tr("export_clean_txt"))
        self.export_clean_button.clicked.connect(lambda: self._safe_slot(self.reveal_clean_file))
        self.export_clean_button.setEnabled(False)

        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addSpacing(8)
        controls_layout.addWidget(QLabel(tr("beam_size")))
        controls_layout.addWidget(self.beam_combo)
        controls_layout.addWidget(QLabel(tr("original_language")))
        controls_layout.addWidget(self.language_combo)
        controls_layout.addSpacing(8)

        model_group = QGroupBox(tr("model_group"))
        model_layout = QVBoxLayout(model_group)
        self.model_current_label = QLabel(tr("no_model_selected"))
        self.model_current_label.setWordWrap(True)
        self.model_combo = QComboBox()
        self.model_combo.currentIndexChanged.connect(
            lambda index: self._safe_slot(self._on_model_combo_changed, index)
        )
        self.refresh_models_button = QPushButton(tr("refresh_models"))
        self.refresh_models_button.clicked.connect(lambda: self._safe_slot(self.refresh_models))
        self.manage_models_button = QPushButton(tr("manage_models"))
        self.manage_models_button.clicked.connect(lambda: self._safe_slot(self.open_model_manager))
        model_layout.addWidget(QLabel(tr("current_model")))
        model_layout.addWidget(self.model_current_label)
        model_layout.addWidget(QLabel(tr("model_dropdown")))
        model_layout.addWidget(self.model_combo)
        model_layout.addWidget(self.refresh_models_button)
        model_layout.addWidget(self.manage_models_button)
        controls_layout.addWidget(model_group)
        controls_layout.addSpacing(8)

        controls_layout.addWidget(self.mark_button)
        controls_layout.addWidget(self.open_folder_button)
        controls_layout.addWidget(self.export_clean_button)
        layout.addWidget(controls)

        session = QGroupBox(tr("session"))
        session_layout = QGridLayout(session)
        self.session_start_label = QLabel("-")
        self.session_runtime_label = QLabel("00:00:00")
        self.raw_lines_label = QLabel("0")
        self.clean_lines_label = QLabel("0")
        self.session_backend_label = QLabel(BACKEND_DISPLAY)
        self.session_model_label = QLabel(self._selected_model_name())
        self.session_beam_label = QLabel(str(DEFAULT_BEAM_SIZE))
        self.session_language_label = QLabel(DEFAULT_ORIGINAL_LANGUAGE_LABEL)

        rows = [
            (tr("start_time"), self.session_start_label),
            (tr("runtime"), self.session_runtime_label),
            (tr("raw_lines"), self.raw_lines_label),
            (tr("clean_lines"), self.clean_lines_label),
            (tr("backend"), self.session_backend_label),
            (tr("model"), self.session_model_label),
            (tr("beam"), self.session_beam_label),
            (tr("language"), self.session_language_label),
        ]
        for row, (name, label) in enumerate(rows):
            session_layout.addWidget(QLabel(name), row, 0)
            session_layout.addWidget(label, row, 1)
        layout.addWidget(session)
        layout.addStretch()
        return panel

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.clean_table = TranscriptTable(tr("clean_transcript"))
        self.raw_table = TranscriptTable(tr("raw_transcript"))
        self.logs_text = QPlainTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setMaximumBlockCount(5000)

        logs_container = QWidget()
        logs_layout = QVBoxLayout(logs_container)
        logs_layout.addWidget(self.logs_text)

        self.tabs.addTab(self.clean_table, tr("clean_transcript"))
        self.tabs.addTab(self.raw_table, tr("raw_transcript"))
        self.tabs.addTab(logs_container, tr("logs"))
        return self.tabs

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f3f4f6;
                color: #111827;
                font-size: 13px;
            }
            #statusStrip {
                background: #ffffff;
                color: #111827;
                border: 1px solid #d1d5db;
                border-radius: 6px;
            }
            #statusTitle {
                background: transparent;
                color: #4b5563;
                font-size: 11px;
            }
            QLabel {
                background: transparent;
                color: #111827;
            }
            QGroupBox {
                background: #ffffff;
                color: #111827;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                margin-top: 12px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 4px;
                background: #ffffff;
                color: #111827;
            }
            QPushButton {
                background: #ffffff;
                color: #111827;
                border: 1px solid #9ca3af;
                border-radius: 4px;
                padding: 5px 10px;
                min-height: 30px;
            }
            QPushButton:hover {
                background: #f3f4f6;
                border-color: #6b7280;
            }
            QPushButton:pressed {
                background: #e5e7eb;
            }
            QPushButton:disabled {
                background: #e5e7eb;
                color: #6b7280;
                border-color: #d1d5db;
            }
            QComboBox {
                background: #ffffff;
                color: #111827;
                border: 1px solid #9ca3af;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 24px;
            }
            QComboBox:disabled {
                background: #e5e7eb;
                color: #6b7280;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #111827;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
            QTabWidget::pane {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #e5e7eb;
                color: #111827;
                border: 1px solid #d1d5db;
                border-bottom: none;
                padding: 6px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #111827;
                font-weight: 600;
            }
            QTabBar::tab:!selected {
                color: #374151;
            }
            QTableWidget, QTableView {
                background: #ffffff;
                alternate-background-color: #f8fafc;
                color: #111827;
                gridline-color: #d1d5db;
                border: 1px solid #d1d5db;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
            QTableWidget::item, QTableView::item {
                background: transparent;
                color: #111827;
                padding: 6px;
            }
            QTableWidget::item:selected, QTableView::item:selected {
                background: #2563eb;
                color: #ffffff;
            }
            QHeaderView::section {
                background: #e5e7eb;
                color: #111827;
                border: 0;
                border-right: 1px solid #d1d5db;
                border-bottom: 1px solid #d1d5db;
                padding: 6px;
                font-weight: 600;
            }
            QPlainTextEdit {
                background: #111827;
                color: #f9fafb;
                border: 1px solid #374151;
                border-radius: 4px;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
                font-family: Menlo, Monaco, Consolas, monospace;
            }
            QScrollBar:vertical {
                background: #f3f4f6;
                width: 12px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #9ca3af;
                border-radius: 6px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6b7280;
            }
            """
        )

    def _safe_slot(self, callback, *args):
        if self._shutdown_complete:
            return None
        try:
            return callback(*args)
        except Exception as exc:
            callback_name = getattr(callback, "__name__", repr(callback))
            log_exception(f"Qt slot failed: {callback_name}", exc)
            try:
                QMessageBox.critical(self, tr("transcription_error"), str(exc))
            except Exception:
                pass
            return None

    def refresh_models(self):
        preferred_path = self.selected_model.path if self.selected_model else self.app_settings.selected_model_path
        self.models = scan_model_dirs(
            self.app_settings.model_dirs,
            self.app_settings.imported_model_paths,
            download_model_dir=self.app_settings.download_model_dir,
        )
        self.selected_model = choose_default_model(self.models, preferred_path)
        if self.selected_model:
            self.app_settings.selected_model_path = self.selected_model.path
            self.app_settings.selected_model_name = self.selected_model.name
            save_app_settings(self.app_settings)
        self._populate_model_combo()
        self._update_model_labels()
        self._set_status(self.controller.state.value)
        self._append_log(f"{tr('refresh_models')}: {len(self.models)} model(s).")

    def open_model_manager(self):
        crash_log("open Model Manager")
        dialog = ModelManagerDialog(self.app_settings, self.selected_model, self)
        self.model_manager_dialog = dialog
        dialog.log_message.connect(self._handle_model_manager_log)
        dialog.model_selected.connect(self._set_selected_model)
        dialog.models_changed.connect(self._reload_models_from_settings)
        try:
            dialog.exec()
        finally:
            crash_log("close Model Manager")
            try:
                dialog.log_message.disconnect(self._handle_model_manager_log)
            except Exception:
                pass
            try:
                dialog.model_selected.disconnect(self._set_selected_model)
            except Exception:
                pass
            try:
                dialog.models_changed.disconnect(self._reload_models_from_settings)
            except Exception:
                pass
            if self.model_manager_dialog is dialog:
                self.model_manager_dialog = None
        self._reload_models_from_settings()

    def _handle_model_manager_log(self, message, level="INFO"):
        self._append_log(message, level=level)

    def _reload_models_from_settings(self):
        self.models = scan_model_dirs(
            self.app_settings.model_dirs,
            self.app_settings.imported_model_paths,
            download_model_dir=self.app_settings.download_model_dir,
        )
        self.selected_model = choose_default_model(
            self.models,
            self.app_settings.selected_model_path,
        )
        self._populate_model_combo()
        self._update_model_labels()
        self._set_status(self.controller.state.value)

    def _populate_model_combo(self):
        if not hasattr(self, "model_combo"):
            return
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        if not self.models:
            self.model_combo.addItem(tr("no_model_selected"), "")
        else:
            for model in self.models:
                self.model_combo.addItem(model.display_label, str(model.path))
            if self.selected_model:
                for index, model in enumerate(self.models):
                    if model.path.resolve() == self.selected_model.path.resolve():
                        self.model_combo.setCurrentIndex(index)
                        break
        self.model_combo.blockSignals(False)

    def _on_model_combo_changed(self, index):
        if index < 0 or index >= len(self.models):
            return
        model = self.models[index]
        if not model.is_available:
            self._append_log(f"Model is not available: {model.display_label}", level="WARNING")
            self._set_status(self.controller.state.value)
            return
        self._set_selected_model(model)

    def _set_selected_model(self, model):
        self.selected_model = model
        self.app_settings.selected_model_path = model.path
        self.app_settings.selected_model_name = model.name
        save_app_settings(self.app_settings)
        self._populate_model_combo()
        self._update_model_labels()
        self._set_status(self.controller.state.value)

    def _selected_model_name(self):
        return self.selected_model.name if self.selected_model else tr("no_model_selected")

    def _has_startable_model(self):
        return bool(self.selected_model and self.selected_model.is_available)

    def _update_model_labels(self):
        name = self._selected_model_name()
        if hasattr(self, "model_label"):
            self.model_label.setText(name)
        if hasattr(self, "session_model_label"):
            self.session_model_label.setText(name)
        if hasattr(self, "model_current_label"):
            if self.selected_model:
                self.model_current_label.setText(self.selected_model.display_label)
                self.model_current_label.setToolTip(str(self.selected_model.path))
            else:
                self.model_current_label.setText(tr("no_model_selected"))
                self.model_current_label.setToolTip("")

    def start_recording(self):
        crash_log("start recording requested")
        if not self._has_startable_model():
            self._show_error("Cannot start transcription: no model selected.")
            return
        beam_size = int(self.beam_combo.currentData())
        original_language_label = self.language_combo.currentData()
        self.app_settings.default_beam_size = beam_size
        save_app_settings(self.app_settings)
        self._append_log(tr("starting_session"))
        try:
            session_dir = self.controller.start(
                beam_size=beam_size,
                original_language_label=original_language_label,
                selected_model_path=self.selected_model.path,
                selected_model_name=self.selected_model.name,
            )
        except Exception as exc:
            self._show_error(str(exc))
            return

        self.current_output_dir = Path(session_dir)
        self.current_clean_path = self.current_output_dir / "clean.txt"
        self.session_started_at = time.time()
        self.session_start_label.setText(time.strftime("%Y-%m-%d %H:%M:%S"))
        self.output_folder_label.setText(str(self.current_output_dir))
        self.output_folder_label.setToolTip(str(self.current_output_dir))
        self.beam_status_label.setText(str(beam_size))
        self.session_beam_label.setText(str(beam_size))
        self._update_model_labels()
        self.language_status_label.setText(original_language_label)
        self.session_language_label.setText(original_language_label)
        self.open_folder_button.setEnabled(True)
        self.export_clean_button.setEnabled(True)
        crash_log(f"start recording completed: session_dir={session_dir}")

    def stop_recording(self):
        crash_log("stop recording requested")
        if self._stop_thread and self._stop_thread.is_alive():
            crash_log("stop recording ignored: stop thread already running")
            return
        self._set_status(EngineState.STOPPING.value)
        self._append_log(tr("stopping_session"))
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self._stop_thread = threading.Thread(
            target=self._stop_controller,
            name="ui-stop-controller",
            daemon=False,
        )
        self._stop_thread.start()

    def _stop_controller(self):
        crash_log("_stop_controller entered")
        try:
            self.controller.stop()
        except Exception as exc:
            log_exception("_stop_controller failed", exc)
            self.bridge.event_received.emit({"type": "error", "message": str(exc)})
        finally:
            crash_log("_stop_controller completed")

    def handle_event(self, event):
        event_type = event.get("type")

        if event_type == "state":
            self._set_status(event.get("state", EngineState.IDLE.value))
            message = event.get("message")
            if message:
                self._append_log(message, level="ERROR")
        elif event_type == "session":
            self.current_output_dir = Path(event["session_dir"])
            self.current_clean_path = Path(event["clean_path"])
            self.output_folder_label.setText(str(self.current_output_dir))
            self.output_folder_label.setToolTip(str(self.current_output_dir))
            config = event.get("config", {})
            original_language_label = config.get("original_language_label")
            if original_language_label:
                self.language_status_label.setText(original_language_label)
                self.session_language_label.setText(original_language_label)
            model_name = config.get("model") or config.get("model_display")
            if model_name:
                self.model_label.setText(model_name)
                self.session_model_label.setText(model_name)
        elif event_type == "recording":
            self._set_status(EngineState.RECORDING.value)
        elif event_type == "queue":
            self.queue_size = event.get("queue_size", self.queue_size)
            self.queue_label.setText(str(self.queue_size))
        elif event_type == "raw_lines":
            lines = event.get("lines", [])
            self.raw_table.append_lines(lines)
            self.raw_count = event.get("raw_count", self.raw_count + len(lines))
            self.raw_lines_label.setText(str(self.raw_count))
        elif event_type == "clean_lines":
            lines = event.get("lines", [])
            self.clean_table.append_lines(lines)
            self.clean_count = event.get("clean_count", self.clean_count + len(lines))
            self.clean_lines_label.setText(str(self.clean_count))
        elif event_type == "log":
            self._append_log(event.get("message", ""), level=event.get("level", "INFO"))
        elif event_type == "error":
            self._append_log(event.get("message", ""), level="ERROR")
            self._show_error(event.get("message", tr("unknown_error")))
        elif event_type == "stopped":
            self._append_log(event.get("message", tr("stop_complete")))

        if "queue_size" in event:
            self.queue_size = event["queue_size"]
            self.queue_label.setText(str(self.queue_size))

    def _set_status(self, status):
        self.status_label.setText(display_status(status))
        is_idle = status == EngineState.IDLE.value
        is_starting = status == EngineState.STARTING.value
        is_recording = status == EngineState.RECORDING.value
        is_stopping = status == EngineState.STOPPING.value
        is_error = status == EngineState.ERROR.value

        self.start_button.setEnabled((is_idle or is_error) and self._has_startable_model())
        self.stop_button.setEnabled(is_starting or is_recording)
        self.beam_combo.setEnabled(is_idle or is_error)
        self.language_combo.setEnabled(is_idle or is_error)
        self.model_combo.setEnabled((is_idle or is_error) and bool(self.models))
        self.refresh_models_button.setEnabled(is_idle or is_error)
        self.manage_models_button.setEnabled(is_idle or is_error)

        if is_idle:
            self.session_started_at = None
        if is_stopping:
            self.stop_button.setEnabled(False)

    def _update_runtime_labels(self):
        if self.session_started_at:
            runtime = format_runtime(time.time() - self.session_started_at)
        else:
            runtime = "00:00:00"
        self.runtime_label.setText(runtime)
        self.session_runtime_label.setText(runtime)

    def _append_log(self, message, level="INFO"):
        if not message:
            return
        timestamp = time.strftime("%H:%M:%S")
        self.logs_text.appendPlainText(f"{timestamp} [{level}] {message}")
        self.logs_text.verticalScrollBar().setValue(
            self.logs_text.verticalScrollBar().maximum()
        )

    def _show_error(self, message):
        crash_log(f"show error: {message}")
        self._set_status(EngineState.ERROR.value)
        QMessageBox.critical(self, tr("transcription_error"), message)

    def open_output_folder(self):
        if self.current_output_dir and self.current_output_dir.exists():
            subprocess.run(["open", str(self.current_output_dir)], check=False)

    def reveal_clean_file(self):
        if self.current_clean_path and self.current_clean_path.exists():
            subprocess.run(["open", "-R", str(self.current_clean_path)], check=False)
        else:
            self.open_output_folder()

    def closeEvent(self, event):
        crash_log(f"closeEvent entered: controller_state={self.controller.state.value}")
        try:
            if self.controller.state in (EngineState.STARTING, EngineState.RECORDING):
                answer = QMessageBox.question(
                    self,
                    tr("stop_dialog_title"),
                    tr("stop_dialog_body"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    crash_log("closeEvent ignored by user")
                    event.ignore()
                    return

            self.safe_shutdown()
            event.accept()
            crash_log("closeEvent completed: accepted")
        except Exception as exc:
            log_exception("closeEvent failed", exc)
            event.ignore()

    def safe_shutdown(self):
        if self._shutdown_complete:
            crash_log("safe_shutdown skipped: already complete")
            return
        if self._shutdown_started:
            crash_log("safe_shutdown re-entered")
        self._shutdown_started = True
        crash_log(f"safe_shutdown entered: controller_state={self.controller.state.value}")

        if hasattr(self, "runtime_timer") and self.runtime_timer.isActive():
            self.runtime_timer.stop()
            crash_log("safe_shutdown: runtime timer stopped")

        dialog = self.model_manager_dialog
        if dialog is not None:
            crash_log("safe_shutdown: closing model manager dialog")
            try:
                dialog.reject()
            except Exception as exc:
                log_exception("safe_shutdown model manager close failed", exc)
            self.model_manager_dialog = None

        if self._stop_thread and self._stop_thread.is_alive():
            crash_log("safe_shutdown: waiting for active stop thread")
            self._stop_thread.join(timeout=300)
            if self._stop_thread.is_alive():
                crash_log("safe_shutdown: stop thread still alive after timeout")
        elif self.controller.state in (
            EngineState.STARTING,
            EngineState.RECORDING,
            EngineState.STOPPING,
            EngineState.ERROR,
        ) and self.controller.engine is not None:
            crash_log("safe_shutdown: stopping controller synchronously")
            self.controller.stop()

        try:
            self.bridge.event_received.disconnect()
            crash_log("safe_shutdown: bridge disconnected")
        except Exception:
            pass

        self._shutdown_complete = True
        crash_log("safe_shutdown completed")


def main():
    install_crash_logging()
    log_startup_environment()
    crash_log(f"crash_debug_log={CRASH_LOG_PATH}")
    app = QApplication(sys.argv)
    app.aboutToQuit.connect(lambda: crash_log("QApplication aboutToQuit"))
    window = None
    exit_code = 1
    try:
        window = MainWindow()
        app.aboutToQuit.connect(window.safe_shutdown)
        crash_log("open main window")
        window.show()
        exit_code = app.exec()
        crash_log(f"app.exec returned: {exit_code}")
    except Exception as exc:
        log_exception("main failed", exc)
        try:
            QMessageBox.critical(None, tr("transcription_error"), str(exc))
        except Exception:
            pass
        exit_code = 1
    finally:
        if window is not None:
            try:
                window.safe_shutdown()
            except Exception as exc:
                log_exception("final safe_shutdown failed", exc)
            window = None
        crash_log("before sys.exit")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
