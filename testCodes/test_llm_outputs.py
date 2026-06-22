import json
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm.output_writer import (  # noqa: E402
    append_error_log,
    atomic_write_json,
    atomic_write_text,
    ensure_llm_dir,
    write_phase1a_outputs,
    write_phase1b_outputs,
)
from llm.provider_base import LLMSchemaError  # noqa: E402
from llm.renderer import (  # noqa: E402
    render_markdown_to_html,
    render_readable_markdown,
    render_review_markdown,
    render_summary_markdown,
)
from llm.state_schema import (  # noqa: E402
    ActionItem,
    AnnotationType,
    KeyTerm,
    ReadableSegment,
    ReadableTranscriptState,
    SectionSummary,
    SegmentAnnotation,
    SegmentStatus,
    SummaryState,
    UnclearPart,
)


def print_status(status, name, detail=""):
    suffix = f" - {detail}" if detail else ""
    print(f"{status}: {name}{suffix}")


def make_fake_secret():
    return "sk-" + ("a" * 24)


def make_session(tmp_path: Path):
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    files = {
        "raw.txt": "raw evidence",
        "clean.txt": "[1s -> 2s] clean evidence",
        "session.log": "session log",
        "config.json": '{"config": true}',
    }
    for name, content in files.items():
        (session_dir / name).write_text(content, encoding="utf-8")
    return session_dir, files


def make_summary_state(secret=""):
    return SummaryState(
        overview=f"课堂主线 {secret}".strip(),
        sections=(
            SectionSummary(
                section_id="section-1",
                title="阶段 1",
                summary="讨论项目要求 <script>alert(1)</script>",
                start=1.0,
                end=20.0,
                evidence=("[1.00s -> 20.00s]",),
            ),
        ),
        key_terms=(
            KeyTerm(term="LLM", explanation="大语言模型", evidence=("[2.00s -> 3.00s]",)),
        ),
        action_items=(
            ActionItem(text="复习 slides", due="Friday", evidence=("[4.00s -> 5.00s]",)),
        ),
        review_questions=("为什么 evidence layer 不可变？",),
        unclear_parts=(
            UnclearPart(
                text="first down first server",
                reason="可能是 ASR 错误",
                possible_correction="first come, first served",
                evidence=("[6.00s -> 7.00s]",),
            ),
        ),
    )


def make_readable_state(secret=""):
    return ReadableTranscriptState(
        revision=3,
        segments=(
            ReadableSegment(
                segment_id="seg-1",
                start=1.0,
                end=2.0,
                source_text=f"source <script>alert(1)</script> {secret}".strip(),
                text_zh=f"普通片段 <script>alert(1)</script> {secret}".strip(),
                evidence=("[1.00s -> 2.00s]",),
                status=SegmentStatus.EDITABLE,
            ),
            ReadableSegment(
                segment_id="seg-2",
                start=2.0,
                end=3.0,
                source_text="duplicate",
                text_zh="重复片段",
                annotations=(
                    SegmentAnnotation(AnnotationType.SUSPECTED_DUPLICATE, "重复片段"),
                ),
                evidence=("[2.00s -> 3.00s]",),
                status=SegmentStatus.EDITABLE,
            ),
            ReadableSegment(
                segment_id="seg-3",
                start=3.0,
                end=4.0,
                source_text="term",
                text_zh="Bayes",
                annotations=(SegmentAnnotation(AnnotationType.TERM, "Bayes"),),
                evidence=("[3.00s -> 4.00s]",),
                status=SegmentStatus.FROZEN,
            ),
            ReadableSegment(
                segment_id="seg-4",
                start=4.0,
                end=5.0,
                source_text="suspicious",
                text_zh="可能错",
                annotations=(SegmentAnnotation(AnnotationType.SUSPICIOUS, "可能错"),),
                evidence=("[4.00s -> 5.00s]",),
                status=SegmentStatus.EDITABLE,
            ),
            ReadableSegment(
                segment_id="seg-5",
                start=5.0,
                end=6.0,
                source_text="deadline",
                text_zh="deadline",
                annotations=(
                    SegmentAnnotation(
                        AnnotationType.HIGH_RISK_SUSPICIOUS,
                        "deadline <script>alert(1)</script>",
                    ),
                ),
                evidence=("[5.00s -> 6.00s]",),
                status=SegmentStatus.FROZEN,
            ),
        ),
    )


def read_all_outputs(llm_dir: Path):
    content = ""
    for path in sorted(llm_dir.glob("*")):
        if path.is_file():
            content += path.read_text(encoding="utf-8")
    return content


def test_llm_output_directory_created():
    with tempfile.TemporaryDirectory(prefix="llm_outputs_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir))
        paths = ensure_llm_dir(session_dir)
        assert paths.llm_dir.exists()
        assert paths.llm_dir.is_dir()

    print_status("PASS", "llm output directory created")


def test_atomic_text_write():
    with tempfile.TemporaryDirectory(prefix="llm_outputs_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir))
        paths = ensure_llm_dir(session_dir)
        atomic_write_text(paths.summary_md, "hello", llm_dir=paths.llm_dir)
        atomic_write_text(paths.summary_md, "goodbye", llm_dir=paths.llm_dir)
        assert paths.summary_md.read_text(encoding="utf-8") == "goodbye"

    print_status("PASS", "atomic text write")


def test_atomic_json_write():
    with tempfile.TemporaryDirectory(prefix="llm_outputs_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir))
        paths = ensure_llm_dir(session_dir)
        atomic_write_json(paths.summary_json, {"b": 2, "a": 1}, llm_dir=paths.llm_dir)
        data = json.loads(paths.summary_json.read_text(encoding="utf-8"))
        assert data == {"a": 1, "b": 2}

    print_status("PASS", "atomic json write")


def test_writer_rejects_non_llm_path():
    with tempfile.TemporaryDirectory(prefix="llm_outputs_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir))
        paths = ensure_llm_dir(session_dir)
        try:
            atomic_write_text(session_dir / "clean.txt", "bad write", llm_dir=paths.llm_dir)
        except ValueError:
            pass
        else:
            raise AssertionError("writer accepted an output path outside session_dir/llm")
        assert (session_dir / "clean.txt").read_text(encoding="utf-8") == originals["clean.txt"]

    print_status("PASS", "writer rejects non-llm path")


def test_summary_outputs_written():
    with tempfile.TemporaryDirectory(prefix="llm_outputs_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir))
        summary_state = make_summary_state()
        summary_md = render_summary_markdown(summary_state)
        paths = write_phase1a_outputs(session_dir, summary_state, summary_md)

        assert paths.summary_md.exists()
        assert paths.summary_json.exists()
        assert paths.sections_json.exists()
        assert paths.key_terms_json.exists()
        assert paths.action_items_json.exists()
        assert json.loads(paths.summary_json.read_text(encoding="utf-8"))["source"] == {
            "raw_used": False,
            "transcript": "clean.txt",
        }

    print_status("PASS", "summary json outputs written")
    print_status("PASS", "summary markdown rendered")


def test_readable_outputs_written():
    with tempfile.TemporaryDirectory(prefix="llm_outputs_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir))
        state = make_readable_state()
        readable_md = render_readable_markdown(state)
        review_md = render_review_markdown(state)
        readable_html = render_markdown_to_html(readable_md)
        review_html = render_markdown_to_html(review_md)
        paths = write_phase1b_outputs(
            session_dir,
            state,
            readable_markdown=readable_md,
            readable_html=readable_html,
            review_markdown=review_md,
            review_html=review_html,
        )

        assert paths.readable_state_json.exists()
        assert paths.readable_md.exists()
        assert paths.readable_html.exists()
        assert paths.review_md.exists()
        assert paths.review_html.exists()

    print_status("PASS", "readable state written")
    print_status("PASS", "readable markdown rendered")
    print_status("PASS", "readable html rendered")
    print_status("PASS", "review markdown rendered")
    print_status("PASS", "review html rendered")


def test_html_escaping():
    state = make_readable_state()
    markdown = render_readable_markdown(state)
    html = render_markdown_to_html(markdown)

    assert "<script>" not in html
    assert "&lt;script&gt;" in html or "&amp;lt;script&amp;gt;" in html

    print_status("PASS", "html escaping")


def test_annotation_rendering():
    markdown = render_readable_markdown(make_readable_state())

    assert "~~重复片段~~" in markdown
    assert "*Bayes*" in markdown
    assert "**[可疑] 可能错**" in markdown
    assert "<u><strong>[高风险可疑] deadline &lt;script&gt;alert(1)&lt;/script&gt;</strong></u>" in markdown

    print_status("PASS", "annotation rendering")


def test_renderer_deterministic():
    state = make_readable_state()
    first = render_readable_markdown(state)
    second = render_readable_markdown(state)
    assert first == second
    assert render_markdown_to_html(first) == render_markdown_to_html(second)

    print_status("PASS", "renderer deterministic")


def test_schema_validation_failure():
    try:
        render_readable_markdown({"schema_version": 1, "revision": 1, "source": {}, "segments": []})
    except LLMSchemaError:
        print_status("PASS", "schema validation failure")
        return
    raise AssertionError("invalid readable state did not raise LLMSchemaError")


def test_renderer_failure_preserves_previous_valid_output():
    with tempfile.TemporaryDirectory(prefix="llm_outputs_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir))
        paths = ensure_llm_dir(session_dir)
        atomic_write_text(paths.readable_md, "previous valid output", llm_dir=paths.llm_dir)
        before = paths.readable_md.read_text(encoding="utf-8")
        try:
            render_readable_markdown({"schema_version": 1, "revision": 1, "source": {}, "segments": []})
        except LLMSchemaError:
            pass
        assert paths.readable_md.read_text(encoding="utf-8") == before

    print_status("PASS", "renderer failure preserves previous valid output")


def test_raw_clean_session_config_unchanged():
    with tempfile.TemporaryDirectory(prefix="llm_outputs_") as tmp_dir:
        session_dir, originals = make_session(Path(tmp_dir))
        summary_state = make_summary_state()
        write_phase1a_outputs(session_dir, summary_state, render_summary_markdown(summary_state))
        state = make_readable_state()
        write_phase1b_outputs(
            session_dir,
            state,
            readable_markdown=render_readable_markdown(state),
            readable_html=render_markdown_to_html(render_readable_markdown(state)),
            review_markdown=render_review_markdown(state),
            review_html=render_markdown_to_html(render_review_markdown(state)),
        )

        for name, content in originals.items():
            assert (session_dir / name).read_text(encoding="utf-8") == content

    print_status("PASS", "raw clean session config unchanged")


def test_api_key_not_written():
    fake_secret = make_fake_secret()
    bearer = ("Bear" + "er") + f" {fake_secret}"
    auth_header = ("Author" + "ization") + f": {fake_secret}"
    env_secret = f"DEEPSEEK_API_KEY={fake_secret}"

    with tempfile.TemporaryDirectory(prefix="llm_outputs_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir))
        summary_state = make_summary_state(secret=fake_secret)
        summary_md = render_summary_markdown(summary_state)
        paths = write_phase1a_outputs(session_dir, summary_state, summary_md)
        state = make_readable_state(secret=f"{fake_secret} {bearer} {auth_header}")
        write_phase1b_outputs(
            session_dir,
            state,
            readable_markdown=render_readable_markdown(state),
            readable_html=render_markdown_to_html(render_readable_markdown(state)),
            review_markdown=render_review_markdown(state),
            review_html=render_markdown_to_html(render_review_markdown(state)),
        )
        append_error_log(
            paths.llm_errors_log,
            category="provider",
            message=f"failed {bearer}",
            details=f"{auth_header} {env_secret}",
            llm_dir=paths.llm_dir,
        )

        output = read_all_outputs(paths.llm_dir)
        assert fake_secret not in output
        assert bearer not in output
        assert auth_header not in output
        assert env_secret not in output

    print_status("PASS", "api key not written")


def test_no_live_sidecar_files():
    with tempfile.TemporaryDirectory(prefix="llm_outputs_") as tmp_dir:
        session_dir, _ = make_session(Path(tmp_dir))
        state = make_readable_state()
        write_phase1b_outputs(
            session_dir,
            state,
            readable_markdown=render_readable_markdown(state),
            readable_html=render_markdown_to_html(render_readable_markdown(state)),
            review_markdown=render_review_markdown(state),
            review_html=render_markdown_to_html(render_review_markdown(state)),
        )
        llm_dir = session_dir / "llm"
        forbidden = [
            "live_readable_zh_state.json",
            "live_readable_zh_revisions.jsonl",
            "live_readable_zh.md",
            "live_readable_zh.html",
            "live_review_zh.md",
            "live_review_zh.html",
        ]
        assert not any((llm_dir / name).exists() for name in forbidden)

    print_status("PASS", "no live sidecar files")


def main():
    test_llm_output_directory_created()
    test_atomic_text_write()
    test_atomic_json_write()
    test_writer_rejects_non_llm_path()
    test_summary_outputs_written()
    test_readable_outputs_written()
    test_html_escaping()
    test_annotation_rendering()
    test_renderer_deterministic()
    test_schema_validation_failure()
    test_renderer_failure_preserves_previous_valid_output()
    test_raw_clean_session_config_unchanged()
    test_api_key_not_written()
    test_no_live_sidecar_files()


if __name__ == "__main__":
    main()
