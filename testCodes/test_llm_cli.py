import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI = PROJECT_ROOT / "llm_postprocess.py"


def print_status(status, name, detail=""):
    suffix = f" - {detail}" if detail else ""
    print(f"{status}: {name}{suffix}")


def make_fake_secret():
    return "sk-" + ("d" * 24)


def make_session(tmp_path: Path, *, include_clean: bool = True):
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    files = {
        "raw.txt": "raw evidence should not change",
        "session.log": "session log",
        "config.json": '{"config": true}',
    }
    if include_clean:
        files["clean.txt"] = "[1s -> 2s] project instructions\n[2s -> 3s] review rubric"

    for name, content in files.items():
        (session_dir / name).write_text(content, encoding="utf-8")
    return session_dir, files


def run_cli(args):
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def read_all_outputs(llm_dir: Path):
    content = ""
    if not llm_dir.exists():
        return content
    for path in sorted(llm_dir.glob("*")):
        if path.is_file():
            content += path.read_text(encoding="utf-8")
    return content


def assert_evidence_unchanged(session_dir: Path, originals: dict[str, str]):
    for name, content in originals.items():
        assert (session_dir / name).read_text(encoding="utf-8") == content


def assert_no_structured_outputs(session_dir: Path):
    forbidden = [
        "summary.md",
        "summary.json",
        "sections.json",
        "key_terms.json",
        "action_items.json",
        "llm_errors.log",
        "readable_zh_final_state.json",
        "readable_zh_final.md",
        "readable_zh_final.html",
        "review_zh_final.md",
        "review_zh_final.html",
        "readable_zh_errors.log",
        "live_readable_zh_state.json",
        "live_readable_zh_revisions.jsonl",
        "live_readable_zh.md",
        "live_readable_zh.html",
        "live_review_zh.md",
        "live_review_zh.html",
        "live_readable_zh_errors.log",
    ]
    llm_dir = session_dir / "llm"
    assert not any((llm_dir / name).exists() for name in forbidden)


def assert_no_secret_or_prompt(result, session_dir: Path, secret: str | None = None):
    combined = f"{result.stdout}\n{result.stderr}"
    assert "Traceback" not in combined
    assert "Clean transcript chunk" not in combined
    assert "system_prompt" not in combined
    assert "user_prompt" not in combined
    assert "raw response" not in combined.lower()
    if secret:
        assert secret not in combined
        assert secret not in read_all_outputs(session_dir / "llm")


def test_cli_markdown_mock_success():
    with tempfile.TemporaryDirectory(prefix="llm_cli_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir))
        result = run_cli(["--session", str(session_dir), "--provider", "mock", "--task", "markdown"])

        assert result.returncode == 0, result.stderr
        assert "markdown: ok" in result.stdout
        assert (session_dir / "llm" / "readable_zh.md").exists()
        assert (session_dir / "llm" / "log.md").exists()
        assert_no_structured_outputs(session_dir)
        assert_evidence_unchanged(session_dir, originals)
        assert_no_secret_or_prompt(result, session_dir)

    print_status("PASS", "cli markdown mock success")


def test_cli_default_markdown_mock_success():
    with tempfile.TemporaryDirectory(prefix="llm_cli_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir))
        result = run_cli(["--session", str(session_dir), "--provider", "mock"])

        assert result.returncode == 0, result.stderr
        assert "Task: markdown" in result.stdout
        assert (session_dir / "llm" / "readable_zh.md").exists()
        assert (session_dir / "llm" / "log.md").exists()
        assert_no_structured_outputs(session_dir)
        assert_evidence_unchanged(session_dir, originals)

    print_status("PASS", "cli default markdown mock success")


def test_cli_rejects_missing_session():
    with tempfile.TemporaryDirectory(prefix="llm_cli_") as tmp_dir:
        missing = Path(tmp_dir) / "missing"
        result = run_cli(["--session", str(missing), "--provider", "mock"])

        assert result.returncode != 0
        assert "ERROR:" in result.stderr

    print_status("PASS", "cli rejects missing session")


def test_cli_rejects_missing_clean_transcript():
    with tempfile.TemporaryDirectory(prefix="llm_cli_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir), include_clean=False)
        result = run_cli(["--session", str(session_dir), "--provider", "mock"])

        assert result.returncode != 0
        assert "Missing clean transcript" in result.stderr
        assert not (session_dir / "llm" / "readable_zh.md").exists()
        assert (session_dir / "llm").exists() is False
        assert_evidence_unchanged(session_dir, originals)

    print_status("PASS", "cli rejects missing clean transcript")


def test_cli_rejects_non_mock_provider():
    with tempfile.TemporaryDirectory(prefix="llm_cli_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir))
        result = run_cli(["--session", str(session_dir), "--provider", "deepseek"])

        assert result.returncode != 0
        assert "only supports mock" in result.stderr
        assert not (session_dir / "llm").exists()
        assert_evidence_unchanged(session_dir, originals)

    print_status("PASS", "cli rejects non-mock provider")


def test_cli_provider_failure_sanitized():
    secret = make_fake_secret()
    with tempfile.TemporaryDirectory(prefix="llm_cli_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir))
        result = run_cli(
            [
                "--session",
                str(session_dir),
                "--provider",
                "mock",
                "--task",
                "markdown",
                "--mock-fail",
                f"provider failed with {secret}",
            ]
        )

        assert result.returncode != 0
        assert "[REDACTED]" in result.stderr
        assert not (session_dir / "llm" / "readable_zh.md").exists()
        assert (session_dir / "llm" / "log.md").exists()
        assert_no_secret_or_prompt(result, session_dir, secret=secret)
        assert_no_structured_outputs(session_dir)
        assert_evidence_unchanged(session_dir, originals)

    print_status("PASS", "cli provider failure sanitized")
    print_status("PASS", "cli does not print traceback prompt or raw response")


def test_cli_raw_clean_session_config_unchanged():
    with tempfile.TemporaryDirectory(prefix="llm_cli_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir))
        result = run_cli(["--session", str(session_dir), "--provider", "mock"])

        assert result.returncode == 0, result.stderr
        assert_evidence_unchanged(session_dir, originals)

    print_status("PASS", "cli raw clean session config unchanged")


def test_cli_no_real_api_call():
    with tempfile.TemporaryDirectory(prefix="llm_cli_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir))
        result = run_cli(["--session", str(session_dir), "--provider", "mock"])

        assert result.returncode == 0, result.stderr
        assert "Provider: mock" in result.stdout

    print_status("PASS", "cli no real API call")


def main():
    test_cli_markdown_mock_success()
    test_cli_default_markdown_mock_success()
    test_cli_rejects_missing_session()
    test_cli_rejects_missing_clean_transcript()
    test_cli_rejects_non_mock_provider()
    test_cli_provider_failure_sanitized()
    test_cli_raw_clean_session_config_unchanged()
    test_cli_no_real_api_call()


if __name__ == "__main__":
    main()
