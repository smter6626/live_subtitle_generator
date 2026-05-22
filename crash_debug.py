import atexit
import os
import sys
import time
import traceback
from pathlib import Path


APP_NAME = "ClassroomTranscriber"
CRASH_LOG_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / APP_NAME
    / "logs"
    / "crash_debug.log"
)

_installed = False


def log(message: str):
    try:
        CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(CRASH_LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(f"{timestamp} {message}\n")
            log_file.flush()
    except Exception:
        pass


def log_exception(context: str, exc: BaseException | None = None):
    log(f"{context}: exception")
    if exc is not None:
        log(f"{context}: {type(exc).__name__}: {exc}")
    try:
        CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CRASH_LOG_PATH, "a", encoding="utf-8") as log_file:
            traceback.print_exc(file=log_file)
            log_file.flush()
    except Exception:
        pass


def install():
    global _installed
    if _installed:
        return
    _installed = True

    original_excepthook = sys.excepthook

    def excepthook(exc_type, exc_value, exc_traceback):
        try:
            CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CRASH_LOG_PATH, "a", encoding="utf-8") as log_file:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                log_file.write(f"{timestamp} uncaught Python exception\n")
                traceback.print_exception(exc_type, exc_value, exc_traceback, file=log_file)
                log_file.flush()
        except Exception:
            pass
        original_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = excepthook
    atexit.register(lambda: log("atexit reached"))


def log_startup_environment():
    log("app start")
    log(f"frozen={getattr(sys, 'frozen', False)}")
    log(f"sys.executable={sys.executable}")
    log(f"cwd={os.getcwd()}")
    log(f"python={sys.version.replace(chr(10), ' ')}")

    try:
        import PySide6
        from PySide6.QtCore import qVersion

        log(f"PySide6={PySide6.__version__}")
        log(f"Qt={qVersion()}")
    except Exception as exc:
        log(f"PySide6 version unavailable: {exc}")

    try:
        from resource_paths import (
            resource_root,
            writable_config_dir,
            writable_models_dir,
            writable_outputs_dir,
            default_whisper_cli_path,
        )

        log(f"resource_root={resource_root()}")
        log(f"config_dir={writable_config_dir()}")
        log(f"models_dir={writable_models_dir()}")
        log(f"outputs_dir={writable_outputs_dir()}")
        log(f"default_whisper_cli={default_whisper_cli_path()}")
    except Exception as exc:
        log(f"resource path logging failed: {exc}")
