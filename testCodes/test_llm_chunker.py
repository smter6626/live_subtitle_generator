import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm.transcript_chunker import (  # noqa: E402
    TranscriptLine,
    chunk_transcript,
    parse_clean_transcript,
)


def print_status(status, name, detail=""):
    suffix = f" - {detail}" if detail else ""
    print(f"{status}: {name}{suffix}")


def test_transcript_line_parser():
    raw_line = "[12.34s -> 18.90s] transcript text"
    lines = parse_clean_transcript(raw_line)

    assert len(lines) == 1
    assert lines[0].text == "transcript text"
    assert lines[0].start == 12.34
    assert lines[0].end == 18.90
    assert lines[0].source_line == 0
    assert lines[0].raw_line == raw_line

    print_status("PASS", "transcript line parser")


def test_multiline_parser():
    text = "\n".join(
        [
            "[1s -> 2s] first",
            "[2.0s -> 3.50s] second",
            "plain fallback",
        ]
    )
    lines = parse_clean_transcript(text)

    assert [line.text for line in lines] == ["first", "second", "plain fallback"]
    assert [line.start for line in lines] == [1.0, 2.0, None]
    assert [line.end for line in lines] == [2.0, 3.5, None]

    print_status("PASS", "multiline transcript parser")


def test_parser_skips_empty_lines():
    lines = parse_clean_transcript("\n  \n[1s -> 2s] kept\n\t\nplain")

    assert [line.text for line in lines] == ["kept", "plain"]
    assert [line.source_line for line in lines] == [2, 4]

    print_status("PASS", "transcript parser skips empty lines")


def test_no_timestamp_fallback():
    lines = parse_clean_transcript("line without timestamp")

    assert lines == [
        TranscriptLine(
            text="line without timestamp",
            source_line=0,
            raw_line="line without timestamp",
        )
    ]

    print_status("PASS", "no timestamp fallback")


def test_malformed_timestamp_fallback():
    text = "\n".join(
        [
            "[abc -> 12.0s] broken",
            "[12.0s ->] broken",
        ]
    )
    lines = parse_clean_transcript(text)

    assert len(lines) == 2
    assert [line.text for line in lines] == [
        "[abc -> 12.0s] broken",
        "[12.0s ->] broken",
    ]
    assert all(line.start is None and line.end is None for line in lines)
    assert [line.raw_line for line in lines] == [
        "[abc -> 12.0s] broken",
        "[12.0s ->] broken",
    ]

    print_status("PASS", "malformed timestamp fallback")


def test_empty_transcript():
    assert parse_clean_transcript("") == []
    assert parse_clean_transcript("\n \t\n") == []
    assert chunk_transcript([]) == []

    print_status("PASS", "empty transcript")


def test_deterministic_chunking():
    lines = parse_clean_transcript(
        "\n".join(
            [
                "[0s -> 1s] alpha",
                "[1s -> 2s] beta",
                "[2s -> 3s] gamma",
            ]
        )
    )

    first = chunk_transcript(lines, max_chars=10)
    second = chunk_transcript(lines, max_chars=10)

    assert first == second
    assert [chunk.chunk_id for chunk in first] == ["chunk-0001", "chunk-0002"]

    print_status("PASS", "deterministic chunking")


def test_chunk_respects_max_chars():
    lines = parse_clean_transcript(
        "\n".join(
            [
                "[0s -> 1s] aaaaa",
                "[1s -> 2s] bbbbb",
                "[2s -> 3s] c",
            ]
        )
    )
    chunks = chunk_transcript(lines, max_chars=7)

    assert [chunk.text for chunk in chunks] == ["aaaaa", "bbbbb\nc"]
    assert all(len(chunk.text) <= 7 for chunk in chunks)

    print_status("PASS", "chunk respects max chars")


def test_chunk_respects_max_duration():
    lines = parse_clean_transcript(
        "\n".join(
            [
                "[0s -> 3s] alpha",
                "[3s -> 5s] beta",
                "[5s -> 9s] gamma",
            ]
        )
    )
    chunks = chunk_transcript(lines, max_chars=100, max_seconds=5)

    assert [chunk.text for chunk in chunks] == ["alpha\nbeta", "gamma"]
    assert [(chunk.start, chunk.end) for chunk in chunks] == [(0.0, 5.0), (5.0, 9.0)]

    print_status("PASS", "chunk respects max duration")


def test_long_single_line_can_exceed_max_chars():
    lines = parse_clean_transcript("x" * 20)
    chunks = chunk_transcript(lines, max_chars=5)

    assert len(chunks) == 1
    assert chunks[0].text == "x" * 20

    print_status("PASS", "long single line can exceed max chars")


def test_no_timestamp_lines_included_in_chunks():
    lines = parse_clean_transcript("first fallback\nsecond fallback")
    chunks = chunk_transcript(lines, max_chars=100)

    assert len(chunks) == 1
    assert chunks[0].text == "first fallback\nsecond fallback"
    assert chunks[0].start is None
    assert chunks[0].end is None

    print_status("PASS", "no timestamp lines included in chunks")


def test_chunk_preserves_source_line_indexes():
    lines = parse_clean_transcript("\n[1s -> 2s] first\nfallback\n\n[2s -> 3s] second")
    chunks = chunk_transcript(lines, max_chars=100)

    assert [line.source_line for line in chunks[0].lines] == [1, 2, 4]
    assert chunks[0].source_lines == (1, 2, 4)

    print_status("PASS", "chunk preserves source line indexes")


def test_chunk_start_end_from_timestamped_lines():
    lines = parse_clean_transcript("preface\n[10s -> 12s] main\nuntimed\n[12s -> 15s] end")
    chunks = chunk_transcript(lines, max_chars=100)

    assert chunks[0].start == 10.0
    assert chunks[0].end == 15.0

    print_status("PASS", "chunk start/end derived from timestamped lines")


def test_transcript_parser_preserves_raw_line():
    raw_lines = [
        "[1s -> 2s] timestamped",
        "fallback",
        "[broken -> 3s] malformed",
    ]
    lines = parse_clean_transcript("\n".join(raw_lines))

    assert [line.raw_line for line in lines] == raw_lines

    print_status("PASS", "transcript parser preserves raw line")


def test_inverted_timestamp_falls_back_to_text_only_line():
    raw_line = "[20s -> 10s] wrong order"
    lines = parse_clean_transcript(raw_line)

    assert len(lines) == 1
    assert lines[0].text == raw_line
    assert lines[0].start is None
    assert lines[0].end is None
    assert lines[0].source_line == 0
    assert lines[0].raw_line == raw_line

    print_status("PASS", "inverted timestamp falls back to text-only line")


def test_parser_and_chunker_do_not_modify_inputs():
    text = "[1s -> 2s] original\nfallback"
    original_text = text[:]
    lines = parse_clean_transcript(text)
    original_lines = tuple(lines)

    chunk_transcript(lines, max_chars=100)

    assert text == original_text
    assert tuple(lines) == original_lines

    print_status("PASS", "parser/chunker do not modify inputs")


def main():
    test_transcript_line_parser()
    test_multiline_parser()
    test_parser_skips_empty_lines()
    test_no_timestamp_fallback()
    test_malformed_timestamp_fallback()
    test_empty_transcript()
    test_deterministic_chunking()
    test_chunk_respects_max_chars()
    test_chunk_respects_max_duration()
    test_long_single_line_can_exceed_max_chars()
    test_no_timestamp_lines_included_in_chunks()
    test_chunk_preserves_source_line_indexes()
    test_chunk_start_end_from_timestamped_lines()
    test_transcript_parser_preserves_raw_line()
    test_inverted_timestamp_falls_back_to_text_only_line()
    test_parser_and_chunker_do_not_modify_inputs()


if __name__ == "__main__":
    main()
