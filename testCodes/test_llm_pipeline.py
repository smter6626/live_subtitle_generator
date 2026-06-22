import json
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm.mock_provider import MockProvider  # noqa: E402
from llm.prompt_templates import build_section_summary_payload  # noqa: E402
from llm.provider_base import LLMProviderError  # noqa: E402
from llm.summary_pipeline import run_summary_pipeline  # noqa: E402
from llm.transcript_chunker import chunk_transcript, parse_clean_transcript  # noqa: E402


def print_status(status, name, detail=""):
    suffix = f" - {detail}" if detail else ""
    print(f"{status}: {name}{suffix}")


class RecordingSummaryProvider:
    provider_id = "recording"

    def __init__(self):
        self.calls = []

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_name: str):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "schema_name": schema_name,
            }
        )
        if schema_name == "phase1a_section_summary":
            return {
                "title": "阶段 1",
                "summary": "本段讨论课程项目要求。",
                "key_terms": [
                    {
                        "term": "evidence layer",
                        "explanation": "不可被 LLM 覆盖的证据层。",
                        "evidence": ["[1.00s -> 2.00s]"],
                    }
                ],
                "action_items": [
                    {
                        "text": "复习项目说明",
                        "due": "Friday",
                        "evidence": ["[2.00s -> 3.00s]"],
                    }
                ],
                "unclear_parts": [
                    {
                        "text": "first down first server",
                        "reason": "可能是 ASR 错误",
                        "possible_correction": "first come, first served",
                        "evidence": ["[3.00s -> 4.00s]"],
                    }
                ],
            }
        if schema_name == "phase1a_global_summary":
            return {
                "overview": "课程介绍了项目要求和复习重点。",
                "review_questions": ["为什么 clean.txt 不能被 LLM 覆盖？"],
                "key_terms": [],
                "action_items": [],
                "unclear_parts": [],
            }
        raise AssertionError(f"Unexpected schema: {schema_name}")

    def generate_text(self, *, system_prompt: str, user_prompt: str):
        raise AssertionError("Summary pipeline should use structured JSON in Step 7.")


class InvalidSchemaProvider:
    provider_id = "invalid_schema"

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_name: str):
        return {"summary": {"not": "a string"}}

    def generate_text(self, *, system_prompt: str, user_prompt: str):
        raise AssertionError("Unexpected text call.")


class SecretSuccessProvider:
    provider_id = "secret_success"

    def __init__(self, secret: str):
        self.secret = secret

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_name: str):
        if schema_name == "phase1a_section_summary":
            return {
                "title": "secret section",
                "summary": f"secret should be redacted {self.secret}",
                "key_terms": [self.secret],
                "action_items": [self.secret],
                "unclear_parts": [self.secret],
            }
        return {
            "overview": f"global secret {self.secret}",
            "review_questions": [self.secret],
            "key_terms": [],
            "action_items": [],
            "unclear_parts": [],
        }

    def generate_text(self, *, system_prompt: str, user_prompt: str):
        raise AssertionError("Unexpected text call.")


class SecretFailingProvider:
    provider_id = "secret_failure"

    def __init__(self, secret: str):
        self.secret = secret

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_name: str):
        raise LLMProviderError(f"provider failed with {self.secret}")

    def generate_text(self, *, system_prompt: str, user_prompt: str):
        raise AssertionError("Unexpected text call.")


def make_fake_secret():
    return "sk-" + ("c" * 24)


def make_session(tmp_path: Path, clean_text: str):
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    files = {
        "raw.txt": "raw evidence should not be read or changed",
        "clean.txt": clean_text,
        "session.log": "session log",
        "config.json": '{"beam_size": 5}',
    }
    for name, content in files.items():
        (session_dir / name).write_text(content, encoding="utf-8")
    return session_dir, files


def read_all_outputs(llm_dir: Path):
    content = ""
    for path in sorted(llm_dir.glob("*")):
        if path.is_file():
            content += path.read_text(encoding="utf-8")
    return content


def assert_evidence_unchanged(session_dir: Path, originals: dict[str, str]):
    for name, content in originals.items():
        assert (session_dir / name).read_text(encoding="utf-8") == content


def assert_no_phase1b_or_live_outputs(session_dir: Path):
    forbidden = [
        "readable_zh_final_state.json",
        "readable_zh_final.md",
        "readable_zh_final.html",
        "review_zh_final.md",
        "review_zh_final.html",
        "live_readable_zh_state.json",
        "live_readable_zh_revisions.jsonl",
        "live_readable_zh.md",
        "live_readable_zh.html",
        "live_review_zh.md",
        "live_review_zh.html",
    ]
    llm_dir = session_dir / "llm"
    assert not any((llm_dir / name).exists() for name in forbidden)


def test_summary_pipeline_reads_clean_transcript():
    clean_text = "[1s -> 2s] project instructions\n[2s -> 3s] review the rubric"
    with tempfile.TemporaryDirectory(prefix="llm_pipeline_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir), clean_text)
        provider = RecordingSummaryProvider()
        result = run_summary_pipeline(session_dir=session_dir, provider=provider, max_chars=100)

        assert result.success
        assert result.chunks_processed == 1
        assert provider.calls
        assert "project instructions" in provider.calls[0]["user_prompt"]
        assert "raw evidence" not in provider.calls[0]["user_prompt"]

    print_status("PASS", "summary pipeline reads clean transcript")


def test_summary_pipeline_writes_summary_outputs():
    clean_text = "[1s -> 2s] project instructions\n[2s -> 3s] review the rubric"
    with tempfile.TemporaryDirectory(prefix="llm_pipeline_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir), clean_text)
        result = run_summary_pipeline(
            session_dir=session_dir,
            provider=RecordingSummaryProvider(),
            max_chars=100,
        )

        assert result.success
        llm_dir = session_dir / "llm"
        expected = [
            "summary.md",
            "summary.json",
            "sections.json",
            "key_terms.json",
            "action_items.json",
        ]
        assert all((llm_dir / name).exists() for name in expected)
        summary_json = json.loads((llm_dir / "summary.json").read_text(encoding="utf-8"))
        assert summary_json["source"] == {"raw_used": False, "transcript": "clean.txt"}
        assert summary_json["overview"] == "课程介绍了项目要求和复习重点。"
        assert_evidence_unchanged(session_dir, originals)

    print_status("PASS", "summary pipeline writes summary outputs")
    print_status("PASS", "mock provider success path")


def test_prompt_payload_constraints():
    lines = parse_clean_transcript("[1s -> 2s] explain project deadline")
    chunk = chunk_transcript(lines, max_chars=100)[0]
    payload = build_section_summary_payload(chunk=chunk)
    combined = f"{payload.system_prompt}\n{payload.user_prompt}".lower()

    assert "chinese output" in combined or "output language: chinese" in combined
    assert "timestamp grounding" in combined
    assert "no hallucination" in combined
    assert "unclear" in combined
    assert "possible correction" in combined
    assert "do not overwrite clean.txt" in combined
    assert payload.metadata["chunk_id"] == "chunk-0001"
    assert payload.metadata["source_lines"] == [0]

    print_status("PASS", "prompt includes chinese output instruction")
    print_status("PASS", "prompt includes timestamp grounding instruction")
    print_status("PASS", "prompt includes no hallucination instruction")
    print_status("PASS", "prompt includes unclear possible correction instruction")


def test_provider_failure_isolated():
    clean_text = "[1s -> 2s] project instructions"
    with tempfile.TemporaryDirectory(prefix="llm_pipeline_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir), clean_text)
        result = run_summary_pipeline(
            session_dir=session_dir,
            provider=MockProvider(mode="provider_error"),
        )

        assert not result.success
        assert (session_dir / "llm" / "llm_errors.log").exists()
        assert not (session_dir / "llm" / "summary.md").exists()
        assert_evidence_unchanged(session_dir, originals)

    print_status("PASS", "provider failure isolated")


def test_schema_failure_isolated():
    clean_text = "[1s -> 2s] project instructions"
    with tempfile.TemporaryDirectory(prefix="llm_pipeline_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir), clean_text)
        result = run_summary_pipeline(session_dir=session_dir, provider=InvalidSchemaProvider())

        assert not result.success
        error_log = (session_dir / "llm" / "llm_errors.log").read_text(encoding="utf-8")
        assert "LLMSchemaError" in error_log
        assert not (session_dir / "llm" / "summary.md").exists()
        assert_evidence_unchanged(session_dir, originals)

    print_status("PASS", "schema failure isolated")


def test_raw_clean_session_config_unchanged():
    clean_text = "[1s -> 2s] project instructions"
    with tempfile.TemporaryDirectory(prefix="llm_pipeline_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir), clean_text)
        run_summary_pipeline(session_dir=session_dir, provider=RecordingSummaryProvider())
        assert_evidence_unchanged(session_dir, originals)

    print_status("PASS", "raw clean session config unchanged")


def test_api_key_not_written_success_and_failure():
    secret = make_fake_secret()
    clean_text = "[1s -> 2s] project instructions"
    with tempfile.TemporaryDirectory(prefix="llm_pipeline_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir), clean_text)
        success = run_summary_pipeline(session_dir=session_dir, provider=SecretSuccessProvider(secret))
        assert success.success
        output = read_all_outputs(session_dir / "llm")
        assert secret not in output

    with tempfile.TemporaryDirectory(prefix="llm_pipeline_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir), clean_text)
        failure = run_summary_pipeline(session_dir=session_dir, provider=SecretFailingProvider(secret))
        assert not failure.success
        output = read_all_outputs(session_dir / "llm")
        assert secret not in output

    print_status("PASS", "api key not written")


def test_no_phase1b_outputs():
    clean_text = "[1s -> 2s] project instructions"
    with tempfile.TemporaryDirectory(prefix="llm_pipeline_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir), clean_text)
        result = run_summary_pipeline(session_dir=session_dir, provider=RecordingSummaryProvider())

        assert result.success
        assert_no_phase1b_or_live_outputs(session_dir)

    print_status("PASS", "no phase1b outputs")


def test_no_live_sidecar_outputs():
    clean_text = "[1s -> 2s] project instructions"
    with tempfile.TemporaryDirectory(prefix="llm_pipeline_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir), clean_text)
        result = run_summary_pipeline(session_dir=session_dir, provider=RecordingSummaryProvider())

        assert result.success
        assert_no_phase1b_or_live_outputs(session_dir)

    print_status("PASS", "no live sidecar outputs")


def test_no_real_api_call():
    clean_text = "[1s -> 2s] project instructions"
    provider = RecordingSummaryProvider()
    with tempfile.TemporaryDirectory(prefix="llm_pipeline_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir), clean_text)
        result = run_summary_pipeline(session_dir=session_dir, provider=provider)

        assert result.success
        assert len(provider.calls) == 2

    print_status("PASS", "no real API call")


def main():
    test_summary_pipeline_reads_clean_transcript()
    test_summary_pipeline_writes_summary_outputs()
    test_prompt_payload_constraints()
    test_provider_failure_isolated()
    test_schema_failure_isolated()
    test_raw_clean_session_config_unchanged()
    test_api_key_not_written_success_and_failure()
    test_no_phase1b_outputs()
    test_no_live_sidecar_outputs()
    test_no_real_api_call()


if __name__ == "__main__":
    main()
