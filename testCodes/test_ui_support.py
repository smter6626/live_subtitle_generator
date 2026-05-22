import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from settings import (  # noqa: E402
    HALLUCINATION_DENYLIST,
    MIN_MODEL_FILE_SIZE_BYTES,
    ORIGINAL_LANGUAGE_CHINESE,
    ORIGINAL_LANGUAGE_ENGLISH,
    ORIGINAL_LANGUAGE_MIXED,
    TranscriptionSettings,
    prompt_for_original_language_label,
    validate_runtime_paths,
    whisper_language_code_for_label,
)
from model_manager import (  # noqa: E402
    AppSettings,
    build_download_command,
    format_file_size,
    load_app_settings,
    parse_model_name,
    save_app_settings,
    scan_model_dirs,
)
import transcription_engine as transcription_engine_module  # noqa: E402
from stream_transcribe import (  # noqa: E402
    CAPTURE_RATE,
    build_whisper_cpp_command,
    render_safe_whisper_cpp_command,
)
from transcript_store import TranscriptStore, parse_transcript_line  # noqa: E402
from transcription_engine import (  # noqa: E402
    FINAL_PARTIAL_MIN_RMS,
    FINAL_PARTIAL_MIN_SECONDS,
    TranscriptionEngine,
    audio_rms,
    filter_clean_hallucinations,
)


def print_status(status, name, detail=""):
    suffix = f" - {detail}" if detail else ""
    print(f"{status}: {name}{suffix}")


def test_path_checks():
    settings = TranscriptionSettings(
        whisper_cpp_cli=Path("/missing/whisper-cli"),
        whisper_cpp_model=Path("/missing/ggml-large-v3.bin"),
    )
    errors = validate_runtime_paths(settings)
    assert any("whisper-cli not found" in error for error in errors)
    assert any("selected model not found" in error for error in errors)

    with tempfile.TemporaryDirectory(prefix="ui_paths_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        cli = tmp_path / "whisper-cli"
        model = tmp_path / "ggml-large-v3.bin"
        cli.write_text("#!/bin/sh\n", encoding="utf-8")
        make_model_placeholder(model)
        os.chmod(cli, 0o755)

        ok_settings = TranscriptionSettings(
            whisper_cpp_cli=cli,
            whisper_cpp_model=model,
            output_root=tmp_path / "outputs",
        )
        assert validate_runtime_paths(ok_settings) == []

    print_status("PASS", "runtime path checks")


def make_model_placeholder(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as model_file:
        model_file.truncate(MIN_MODEL_FILE_SIZE_BYTES + 1)


def test_timestamp_parser():
    parsed = parse_transcript_line("[12.34s -> 18.90s] hello")
    assert parsed["time"] == "00:12"
    assert parsed["text"] == "hello"
    assert parsed["range"] == "12.34s -> 18.90s"
    print_status("PASS", "timestamp line parser")


def test_config_write():
    with tempfile.TemporaryDirectory(prefix="ui_config_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        cli = tmp_path / "whisper-cli"
        model = tmp_path / "ggml-large-v3.bin"
        cli.write_text("#!/bin/sh\n", encoding="utf-8")
        make_model_placeholder(model)

        settings = TranscriptionSettings(
            beam_size=6,
            whisper_cpp_cli=cli,
            whisper_cpp_model=model,
            output_root=tmp_path / "outputs",
            original_language_label=ORIGINAL_LANGUAGE_CHINESE,
        )
        store = TranscriptStore(settings.output_root, session_id="session")
        store.write_config(settings.to_config())
        store.close()

        config = json.loads((store.session_dir / "config.json").read_text(encoding="utf-8"))
        assert config["backend"] == "whisper_cpp"
        assert config["model"] == "large-v3"
        assert config["model_path"] == str(model)
        assert config["selected_model_path"] == str(model)
        assert config["beam_size"] == 6
        assert config["block_seconds"] == 10
        assert config["overlap_seconds"] == 3
        assert config["capture_rate"] == 48000
        assert config["transcribe_rate"] == 16000
        assert config["original_language_label"] == "Chinese"
        assert config["whisper_language_code"] == "zh"
        assert config["task"] == "transcribe"
        assert config["prompt_used"] == ""
        assert prompt_for_original_language_label(ORIGINAL_LANGUAGE_CHINESE) == ""
        assert config["hallucination_filter"]["mode"] == "clean_only"
        assert config["hallucination_filter"]["denylist"] == list(HALLUCINATION_DENYLIST)

    print_status("PASS", "config json write")


def test_model_scan_and_parser():
    with tempfile.TemporaryDirectory(prefix="ui_models_") as tmp_dir:
        model_dir = Path(tmp_dir) / "models"
        large = model_dir / "ggml-large-v3.bin"
        custom = model_dir / "ggml-my-classroom.bin"
        make_model_placeholder(large)
        make_model_placeholder(custom)

        models = scan_model_dirs([model_dir])
        names = [model.name for model in models]
        assert "large-v3" in names
        assert "Custom Model" in names
        assert parse_model_name("ggml-large-v3.bin") == "large-v3"
        assert parse_model_name("ggml-large-v3-turbo.bin") == "large-v3-turbo"
        assert parse_model_name("ggml-medium.en.bin") == "medium.en"

    print_status("PASS", "model scan and parser")


def test_file_size_formatter():
    assert format_file_size(0) == "0 B"
    assert format_file_size(1024) == "1.0 KB"
    assert format_file_size(1024 * 1024) == "1.0 MB"
    assert format_file_size(3 * 1024 * 1024 * 1024) == "3.0 GB"
    print_status("PASS", "file size formatter")


def test_app_settings_save_load():
    with tempfile.TemporaryDirectory(prefix="ui_app_settings_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        model_dir = tmp_path / "models"
        selected_model = model_dir / "ggml-large-v3.bin"
        make_model_placeholder(selected_model)
        settings_path = tmp_path / "config" / "settings.json"

        app_settings = AppSettings(
            whisper_cpp_cli=tmp_path / "whisper-cli",
            selected_model_path=selected_model,
            selected_model_name="large-v3",
            default_beam_size=5,
            model_dirs=[model_dir],
            imported_model_paths=[],
        )
        save_app_settings(app_settings, settings_path=settings_path)
        loaded = load_app_settings(settings_path=settings_path)

        assert loaded.selected_model_path.resolve() == selected_model.resolve()
        assert loaded.selected_model_name == "large-v3"
        assert loaded.default_beam_size == 5
        assert loaded.model_dirs == [model_dir]

    print_status("PASS", "app settings save/load")


def test_selected_model_missing_check():
    settings = TranscriptionSettings(whisper_cpp_model="")
    errors = validate_runtime_paths(settings)
    assert any("no model selected" in error for error in errors)
    print_status("PASS", "selected model missing check")


def test_download_command_builder():
    command = build_download_command("large-v3")
    assert command[0] == "sh"
    assert command[-2] == "large-v3"
    assert command[-1]
    try:
        build_download_command("not-a-model")
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported download model should fail")
    print_status("PASS", "download command builder")


def test_language_mapping():
    assert whisper_language_code_for_label(ORIGINAL_LANGUAGE_ENGLISH) == "en"
    assert whisper_language_code_for_label(ORIGINAL_LANGUAGE_CHINESE) == "zh"
    assert whisper_language_code_for_label(ORIGINAL_LANGUAGE_MIXED) == "auto"
    print_status("PASS", "original language mapping")


def test_whisper_cpp_command_language_args():
    cases = [
        (ORIGINAL_LANGUAGE_ENGLISH, "en", ""),
        (ORIGINAL_LANGUAGE_CHINESE, "zh", ""),
        (ORIGINAL_LANGUAGE_MIXED, "auto", ""),
    ]
    for label, expected_code, expected_prompt in cases:
        cmd = build_whisper_cpp_command(
            cli_path="/tmp/whisper-cli",
            model_path="/tmp/ggml-large-v3.bin",
            wav_path="/tmp/chunk.wav",
            language_code=whisper_language_code_for_label(label),
            beam_size=5,
            task="transcribe",
            initial_prompt=prompt_for_original_language_label(label),
        )
        assert "-l" in cmd
        assert cmd[cmd.index("-l") + 1] == expected_code
        assert "--prompt" not in cmd
        assert "-tr" not in cmd
        assert "--translate" not in cmd

        safe_command = render_safe_whisper_cpp_command(cmd)
        assert "<chunk.wav>" in safe_command
        assert expected_code in safe_command
        assert "--prompt" not in safe_command

    ignored_prompt_cmd = build_whisper_cpp_command(
        cli_path="/tmp/whisper-cli",
        model_path="/tmp/ggml-large-v3.bin",
        wav_path="/tmp/chunk.wav",
        language_code="zh",
        beam_size=5,
        task="transcribe",
        initial_prompt="should not be passed to whisper-cli",
    )
    assert "--prompt" not in ignored_prompt_cmd

    try:
        build_whisper_cpp_command(
            cli_path="/tmp/whisper-cli",
            model_path="/tmp/ggml-large-v3.bin",
            wav_path="/tmp/chunk.wav",
            language_code="zh",
            beam_size=5,
            extra_args="-tr",
            task="transcribe",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("translate flag should be rejected")

    print_status("PASS", "whisper.cpp language CLI args")


def test_clean_hallucination_filter():
    lines = [
        "[1.00s -> 2.00s] 今天我们讨论函数。",
        "[2.00s -> 3.00s] 中文字幕由 Amara.org 社群提供",
        "[3.00s -> 4.00s] 请订阅我的频道。",
        "[4.00s -> 5.00s] 请不吝点赞 订阅 转发 打赏支持明镜与点点栏目",
    ]
    kept_lines, filtered = filter_clean_hallucinations(lines)
    assert kept_lines == ["[1.00s -> 2.00s] 今天我们讨论函数。"]
    assert len(filtered) == 3
    assert any("Amara.org" in item["line"] for item in filtered)
    assert any("请订阅我的频道" in item["line"] for item in filtered)
    assert any("点赞 订阅 转发" in item["line"] for item in filtered)
    print_status("PASS", "clean hallucination filter")


def test_transcript_store_append():
    with tempfile.TemporaryDirectory(prefix="ui_store_") as tmp_dir:
        store = TranscriptStore(Path(tmp_dir), session_id="session")
        raw_lines = [
            "[0.00s -> 1.00s] first raw",
            "[1.00s -> 2.00s] second raw",
        ]
        clean_lines = ["[0.00s -> 1.00s] first clean"]
        store.append_raw(raw_lines)
        store.append_clean(clean_lines)
        store.log("hello")
        store.close()

        assert store.raw_path.read_text(encoding="utf-8").splitlines() == raw_lines
        assert store.clean_path.read_text(encoding="utf-8").splitlines() == clean_lines
        assert "hello" in store.log_path.read_text(encoding="utf-8")
        assert store.raw_lines == 2
        assert store.clean_lines == 1

    print_status("PASS", "transcript store append")


def test_final_partial_chunk_submit_preserves_queue():
    with tempfile.TemporaryDirectory(prefix="ui_final_partial_") as tmp_dir:
        settings = TranscriptionSettings(output_root=Path(tmp_dir) / "outputs")
        store = TranscriptStore(settings.output_root, session_id="session")
        engine = TranscriptionEngine(settings, store)

        existing_task = (
            np.zeros(int(10 * CAPTURE_RATE), dtype=np.float32),
            7.0,
            17.0,
        )
        engine.task_queue.put(existing_task)
        engine.total_audio_seconds = 18.5
        engine.last_chunk_start = 7.0
        engine.audio_buffer.extend(
            np.full(int(engine.total_audio_seconds * CAPTURE_RATE), 0.01, dtype=np.float32).tolist()
        )

        submitted = engine._submit_final_partial_chunk()
        assert submitted is True
        assert engine.task_queue.qsize() == 2

        first_task = engine.task_queue.get_nowait()
        second_task = engine.task_queue.get_nowait()
        assert first_task is existing_task
        final_audio, final_start, final_end = second_task
        assert final_start == 14.0
        assert final_end == engine.total_audio_seconds
        assert 0 < len(final_audio) < int(10 * CAPTURE_RATE)
        assert len(final_audio) >= int(FINAL_PARTIAL_MIN_SECONDS * CAPTURE_RATE)
        assert audio_rms(final_audio) >= FINAL_PARTIAL_MIN_RMS
        store.close()

    print_status("PASS", "final partial submit preserves queue")


def test_final_partial_low_rms_skipped():
    with tempfile.TemporaryDirectory(prefix="ui_final_partial_silence_") as tmp_dir:
        settings = TranscriptionSettings(output_root=Path(tmp_dir) / "outputs")
        store = TranscriptStore(settings.output_root, session_id="session")
        engine = TranscriptionEngine(settings, store)

        engine.total_audio_seconds = 4.0
        engine.last_chunk_start = None
        engine.audio_buffer.extend(
            np.zeros(int(engine.total_audio_seconds * CAPTURE_RATE), dtype=np.float32).tolist()
        )

        submitted = engine._submit_final_partial_chunk()
        assert submitted is False
        assert engine.task_queue.qsize() == 0
        store.close()

    print_status("PASS", "final partial low-rms skip")


def test_stop_does_not_clear_existing_queue():
    with tempfile.TemporaryDirectory(prefix="ui_stop_queue_") as tmp_dir:
        settings = TranscriptionSettings(output_root=Path(tmp_dir) / "outputs")
        store = TranscriptStore(settings.output_root, session_id="session")
        engine = TranscriptionEngine(settings, store)

        existing_task = (
            np.zeros(int(10 * CAPTURE_RATE), dtype=np.float32),
            0.0,
            10.0,
        )
        engine.task_queue.put(existing_task)
        engine.total_audio_seconds = 12.5
        engine.last_chunk_start = 0.0
        engine.audio_buffer.extend(
            np.full(int(engine.total_audio_seconds * CAPTURE_RATE), 0.01, dtype=np.float32).tolist()
        )

        engine.stop()
        assert engine.task_queue.qsize() == 3
        assert engine.task_queue.get_nowait() is existing_task
        final_task = engine.task_queue.get_nowait()
        assert final_task is not None
        assert engine.task_queue.get_nowait() is None

    print_status("PASS", "stop does not clear existing queue")


def test_worker_processes_short_final_chunk():
    class FakeWhisperCppBackend:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def transcribe_chunk(self, audio_16k, chunk_start_time):
            assert len(audio_16k) < int(10 * 16000)
            duration = len(audio_16k) / 16000
            return [f"[{chunk_start_time:.2f}s -> {chunk_start_time + duration:.2f}s] short final"]

    with tempfile.TemporaryDirectory(prefix="ui_short_worker_") as tmp_dir:
        settings = TranscriptionSettings(output_root=Path(tmp_dir) / "outputs")
        store = TranscriptStore(settings.output_root, session_id="session")
        engine = TranscriptionEngine(settings, store)

        old_backend = transcription_engine_module.WhisperCppBackend
        transcription_engine_module.WhisperCppBackend = FakeWhisperCppBackend
        try:
            engine.task_queue.put((
                np.zeros(int(3 * CAPTURE_RATE), dtype=np.float32),
                20.0,
                23.0,
            ))
            engine.task_queue.put(None)
            engine._worker_loop()
        finally:
            transcription_engine_module.WhisperCppBackend = old_backend
            store.close()

        raw_text = store.raw_path.read_text(encoding="utf-8")
        clean_text = store.clean_path.read_text(encoding="utf-8")
        assert "short final" in raw_text
        assert "short final" in clean_text

    print_status("PASS", "worker processes short final chunk")


def main():
    tests = [
        test_path_checks,
        test_timestamp_parser,
        test_config_write,
        test_model_scan_and_parser,
        test_file_size_formatter,
        test_app_settings_save_load,
        test_selected_model_missing_check,
        test_download_command_builder,
        test_language_mapping,
        test_whisper_cpp_command_language_args,
        test_clean_hallucination_filter,
        test_transcript_store_append,
        test_final_partial_chunk_submit_preserves_queue,
        test_final_partial_low_rms_skipped,
        test_stop_does_not_clear_existing_queue,
        test_worker_processes_short_final_chunk,
    ]
    for test in tests:
        test()


if __name__ == "__main__":
    main()
