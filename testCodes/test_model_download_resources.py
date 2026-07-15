import os
import stat
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import resource_paths  # noqa: E402
from model_manager import DOWNLOADABLE_MODELS, build_download_command  # noqa: E402


EXPECTED_MODELS = ("large-v3", "large-v3-turbo", "medium.en", "small.en", "base.en")
VENDORED_SCRIPT = PROJECT_ROOT / "vendor" / "whisper.cpp" / "download-ggml-model.sh"


def print_status(status, name):
    print(f"{status}: {name}")


def test_source_default_uses_vendored_script():
    assert resource_paths.vendored_download_script_path() == VENDORED_SCRIPT
    assert resource_paths.default_download_script_path() == VENDORED_SCRIPT
    assert "external/whisper.cpp" not in VENDORED_SCRIPT.as_posix()
    print_status("PASS", "source default uses vendored download script")


def test_vendored_script_exists_and_is_executable():
    assert VENDORED_SCRIPT.is_file()
    mode = VENDORED_SCRIPT.stat().st_mode
    assert stat.S_IMODE(mode) & 0o111 == 0o111
    assert os.access(VENDORED_SCRIPT, os.X_OK)
    print_status("PASS", "vendored download script exists and is executable")


def test_frozen_mode_prefers_bundled_script():
    with tempfile.TemporaryDirectory(prefix="bundled_download_script_") as tmp_dir:
        resource_root = Path(tmp_dir)
        bundled_script = resource_root / "bin" / "download-ggml-model.sh"
        bundled_script.parent.mkdir(parents=True)
        bundled_script.write_text("#!/bin/sh\n", encoding="utf-8")

        had_frozen = hasattr(sys, "frozen")
        old_frozen = getattr(sys, "frozen", None)
        had_meipass = hasattr(sys, "_MEIPASS")
        old_meipass = getattr(sys, "_MEIPASS", None)
        try:
            sys.frozen = True
            sys._MEIPASS = str(resource_root)
            assert resource_paths.default_download_script_path() == bundled_script
        finally:
            if had_frozen:
                sys.frozen = old_frozen
            else:
                delattr(sys, "frozen")
            if had_meipass:
                sys._MEIPASS = old_meipass
            else:
                delattr(sys, "_MEIPASS")

    print_status("PASS", "frozen mode prefers bundled download script")


def test_download_command_and_supported_models():
    assert DOWNLOADABLE_MODELS == EXPECTED_MODELS
    target_dir = Path("/tmp/classroom-transcriber-models")
    for model_name in EXPECTED_MODELS:
        assert build_download_command(model_name, target_dir=target_dir) == [
            "sh",
            str(VENDORED_SCRIPT),
            model_name,
            str(target_dir),
        ]
    print_status("PASS", "download command and supported model names")


def test_external_directory_is_not_required_for_default_path():
    with tempfile.TemporaryDirectory(prefix="fresh_clone_download_script_") as tmp_dir:
        fresh_root = Path(tmp_dir)
        vendored_script = fresh_root / "vendor" / "whisper.cpp" / "download-ggml-model.sh"
        vendored_script.parent.mkdir(parents=True)
        vendored_script.write_text("#!/bin/sh\n", encoding="utf-8")
        assert not (fresh_root / "external" / "whisper.cpp").exists()

        old_project_root = resource_paths.project_root
        try:
            resource_paths.project_root = lambda: fresh_root
            assert resource_paths.default_download_script_path() == vendored_script
            assert resource_paths.default_download_script_path().is_file()
        finally:
            resource_paths.project_root = old_project_root

    print_status("PASS", "fresh clone path does not require external whisper.cpp")


def main():
    test_source_default_uses_vendored_script()
    test_vendored_script_exists_and_is_executable()
    test_frozen_mode_prefers_bundled_script()
    test_download_command_and_supported_models()
    test_external_directory_is_not_required_for_default_path()


if __name__ == "__main__":
    main()
