import argparse
import os
import sys
import tempfile
import wave

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from stream_transcribe import (  # noqa: E402
    FasterWhisperBackend,
    TRANSCRIBE_RATE,
    WhisperCppBackend,
    build_whisper_cpp_command,
    parse_whisper_cpp_output,
    render_safe_whisper_cpp_command,
    write_pcm16_wav,
)


def print_status(status, name, detail=""):
    suffix = f" - {detail}" if detail else ""
    print(f"{status}: {name}{suffix}")


def short_silence(seconds=0.5):
    return np.zeros(int(TRANSCRIBE_RATE * seconds), dtype=np.float32)


def check_parser():
    sample_output = """
whisper_model_load: loading model
[00:00:01.000 --> 00:00:02.500]  hello world
"""
    lines = parse_whisper_cpp_output(sample_output, chunk_start_time=123.0)
    expected = ["[124.00s -> 125.50s] hello world"]
    if lines != expected:
        print_status("FAIL", "whisper.cpp output parser", f"expected {expected!r}, got {lines!r}")
        return False
    print_status("PASS", "whisper.cpp output parser")
    return True


def check_wav_writer():
    with tempfile.TemporaryDirectory(prefix="backend_test_") as tmp_dir:
        wav_path = os.path.join(tmp_dir, "chunk.wav")
        write_pcm16_wav(wav_path, short_silence(), TRANSCRIBE_RATE)
        with wave.open(wav_path, "rb") as wav_file:
            valid = (
                wav_file.getnchannels() == 1
                and wav_file.getsampwidth() == 2
                and wav_file.getframerate() == TRANSCRIBE_RATE
            )
    if not valid:
        print_status("FAIL", "16k mono pcm16 wav writer")
        return False
    print_status("PASS", "16k mono pcm16 wav writer")
    return True


def check_whisper_cpp_command_builder():
    cases = [
        ("en", ""),
        ("zh", ""),
        ("auto", ""),
    ]
    for language_code, prompt in cases:
        cmd = build_whisper_cpp_command(
            cli_path="/tmp/whisper-cli",
            model_path="/tmp/model.bin",
            wav_path="/tmp/chunk.wav",
            language_code=language_code,
            beam_size=5,
            task="transcribe",
            initial_prompt=prompt,
        )
        if cmd[cmd.index("-l") + 1] != language_code:
            print_status("FAIL", "whisper.cpp command builder", f"bad language for {language_code}")
            return False
        if "--prompt" in cmd:
            print_status("FAIL", "whisper.cpp command builder", "unexpected prompt")
            return False
        if "-tr" in cmd or "--translate" in cmd:
            print_status("FAIL", "whisper.cpp command builder", "translate flag present")
            return False
        safe_command = render_safe_whisper_cpp_command(cmd)
        if "<chunk.wav>" not in safe_command:
            print_status("FAIL", "whisper.cpp command builder", "safe command did not simplify wav path")
            return False
        if "--prompt" in safe_command:
            print_status("FAIL", "whisper.cpp command builder", "safe command includes prompt")
            return False

    ignored_prompt_cmd = build_whisper_cpp_command(
        cli_path="/tmp/whisper-cli",
        model_path="/tmp/model.bin",
        wav_path="/tmp/chunk.wav",
        language_code="zh",
        beam_size=5,
        task="transcribe",
        initial_prompt="should not be passed",
    )
    if "--prompt" in ignored_prompt_cmd:
        print_status("FAIL", "whisper.cpp command builder", "initial_prompt was not ignored")
        return False

    try:
        build_whisper_cpp_command(
            cli_path="/tmp/whisper-cli",
            model_path="/tmp/model.bin",
            wav_path="/tmp/chunk.wav",
            language_code="zh",
            beam_size=5,
            extra_args="--translate",
            task="transcribe",
        )
    except ValueError:
        print_status("PASS", "whisper.cpp command builder")
        return True

    print_status("FAIL", "whisper.cpp command builder", "translate flag was not rejected")
    return False


def check_faster_whisper_import():
    ok, message = FasterWhisperBackend.availability()
    print_status("PASS" if ok else "FAIL", "faster-whisper availability", message)
    return ok


def check_faster_whisper_smoke():
    try:
        backend = FasterWhisperBackend()
        lines = backend.transcribe_chunk(short_silence(), chunk_start_time=123.0)
    except Exception as exc:
        print_status("FAIL", "faster-whisper smoke", str(exc))
        return False

    if not isinstance(lines, list):
        print_status("FAIL", "faster-whisper smoke", f"expected list, got {type(lines)}")
        return False
    print_status("PASS", "faster-whisper smoke", f"returned {len(lines)} line(s)")
    return True


def check_whisper_cpp():
    try:
        backend = WhisperCppBackend()
    except Exception as exc:
        print_status("SKIP", "whisper.cpp availability", str(exc))
        return True

    ok, message = backend.availability()
    if not ok:
        print_status("SKIP", "whisper.cpp availability", message)
        return True

    print_status("PASS", "whisper.cpp availability", message)
    try:
        lines = backend.transcribe_chunk(short_silence(), chunk_start_time=123.0)
    except Exception as exc:
        print_status("FAIL", "whisper.cpp smoke", str(exc))
        return False

    if not isinstance(lines, list):
        print_status("FAIL", "whisper.cpp smoke", f"expected list, got {type(lines)}")
        return False
    print_status("PASS", "whisper.cpp smoke", f"returned {len(lines)} line(s)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Backend interface smoke checks.")
    parser.add_argument(
        "--skip-faster-smoke",
        action="store_true",
        help="Only check faster-whisper import; skip model loading.",
    )
    args = parser.parse_args()

    checks = [
        check_parser(),
        check_wav_writer(),
        check_whisper_cpp_command_builder(),
        check_faster_whisper_import(),
    ]
    if args.skip_faster_smoke:
        print_status("SKIP", "faster-whisper smoke", "requested by --skip-faster-smoke")
    else:
        checks.append(check_faster_whisper_smoke())

    checks.append(check_whisper_cpp())

    if not all(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
