import html
import re
from typing import Any

from llm.output_writer import sanitize_text
from llm.provider_base import RendererError
from llm.state_schema import (
    AnnotationType,
    ReadableTranscriptState,
    SummaryState,
    validate_readable_state,
    validate_summary_state,
)


_CONTROLLED_HIGH_RISK_RE = re.compile(
    r"<u><strong>\[高风险可疑\] (?P<text>.*?)</strong></u>"
)


def render_summary_markdown(summary_state: SummaryState | dict[str, Any]) -> str:
    """Render a Phase 1A summary state into deterministic Markdown."""

    data = validate_summary_state(summary_state)
    lines: list[str] = ["# 课堂总结", "", "## 整体概述", ""]
    lines.append(_safe_markdown_text(data["overview"]))

    lines.extend(["", "## Timeline Sections", ""])
    for section in data["sections"]:
        prefix = _time_range(section.get("start"), section.get("end"))
        lines.append(
            f"- {prefix} **{_safe_markdown_text(section['title'])}**: "
            f"{_safe_markdown_text(section['summary'])}"
        )

    lines.extend(["", "## Key Terms", ""])
    for term in data["key_terms"]:
        lines.append(
            f"- *{_safe_markdown_text(term['term'])}*: "
            f"{_safe_markdown_text(term['explanation'])}"
        )

    lines.extend(["", "## Action Items", ""])
    for item in data["action_items"]:
        detail = _safe_markdown_text(item["text"])
        if item.get("due"):
            detail = f"{detail} (due: {_safe_markdown_text(item['due'])})"
        lines.append(f"- {detail}")

    lines.extend(["", "## Review Questions", ""])
    for question in data["review_questions"]:
        lines.append(f"- {_safe_markdown_text(question)}")

    lines.extend(["", "## Unclear / Possible ASR Errors", ""])
    for unclear in data["unclear_parts"]:
        reason = _safe_markdown_text(unclear.get("reason", ""))
        correction = unclear.get("possible_correction")
        suffix = f" Possible correction: {_safe_markdown_text(correction)}" if correction else ""
        lines.append(f"- **[可疑] {_safe_markdown_text(unclear['text'])}** {reason}{suffix}".rstrip())

    return "\n".join(lines).rstrip() + "\n"


def render_readable_markdown(state: ReadableTranscriptState | dict[str, Any]) -> str:
    """Render the clean readable Phase 1B view."""

    data = validate_readable_state(state)
    lines = ["# 中文阅读稿", ""]
    for segment in data["segments"]:
        lines.append(f"- {_time_range(segment.get('start'), segment.get('end'))} {_render_segment_text(segment)}")
    return "\n".join(lines).rstrip() + "\n"


def render_review_markdown(state: ReadableTranscriptState | dict[str, Any]) -> str:
    """Render the audit/review Phase 1B view."""

    data = validate_readable_state(state)
    lines = ["# 中文审计稿", ""]
    for segment in data["segments"]:
        lines.append(f"## {_safe_markdown_text(segment['segment_id'])} {_time_range(segment.get('start'), segment.get('end'))}")
        lines.append("")
        lines.append(f"- Status: `{_safe_markdown_text(segment['status'])}`")
        lines.append(f"- 中文: {_render_segment_text(segment)}")
        lines.append(f"- Source: {_safe_markdown_text(segment['source_text'])}")
        if segment["evidence"]:
            lines.append(f"- Evidence: {', '.join(_safe_markdown_text(item) for item in segment['evidence'])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_markdown_to_html(markdown_text: str) -> str:
    """Render a small deterministic Markdown subset to standalone HTML."""

    try:
        body_lines: list[str] = []
        in_list = False
        for raw_line in markdown_text.splitlines():
            line = raw_line.rstrip()
            if not line:
                if in_list:
                    body_lines.append("</ul>")
                    in_list = False
                continue

            if line.startswith("# "):
                if in_list:
                    body_lines.append("</ul>")
                    in_list = False
                body_lines.append(f"<h1>{_inline_markdown_to_html(line[2:])}</h1>")
            elif line.startswith("## "):
                if in_list:
                    body_lines.append("</ul>")
                    in_list = False
                body_lines.append(f"<h2>{_inline_markdown_to_html(line[3:])}</h2>")
            elif line.startswith("- "):
                if not in_list:
                    body_lines.append("<ul>")
                    in_list = True
                body_lines.append(f"<li>{_inline_markdown_to_html(line[2:])}</li>")
            else:
                if in_list:
                    body_lines.append("</ul>")
                    in_list = False
                body_lines.append(f"<p>{_inline_markdown_to_html(line)}</p>")

        if in_list:
            body_lines.append("</ul>")

        body = "\n".join(body_lines)
        return (
            "<!doctype html>\n"
            '<html><head><meta charset="utf-8"></head><body>\n'
            f"{body}\n"
            "</body></html>\n"
        )
    except Exception as exc:
        raise RendererError(str(exc)) from exc


def render_markdown(state: ReadableTranscriptState, *, review: bool = False) -> str:
    """Backward-compatible readable transcript Markdown renderer."""

    if review:
        return render_review_markdown(state)
    return render_readable_markdown(state)


def render_html(state: ReadableTranscriptState, *, review: bool = False) -> str:
    """Backward-compatible readable transcript HTML renderer."""

    return render_markdown_to_html(render_markdown(state, review=review))


def _render_segment_text(segment: dict[str, Any]) -> str:
    text = _safe_markdown_text(segment["text_zh"])
    annotations = segment.get("annotations", [])
    if not annotations:
        return text

    annotation = _highest_priority_annotation(annotations)
    annotation_type = annotation.get("annotation_type", annotation.get("type"))
    annotation_text = _safe_markdown_text(annotation.get("text") or segment["text_zh"])

    if annotation_type in {AnnotationType.DUPLICATE.value, AnnotationType.SUSPECTED_DUPLICATE.value, AnnotationType.DELETION.value}:
        return f"~~{annotation_text}~~"
    if annotation_type in {AnnotationType.TERM.value, AnnotationType.UNCERTAIN_TRANSLATION.value}:
        return f"*{annotation_text}*"
    if annotation_type in {AnnotationType.UNCLEAR.value, AnnotationType.SUSPICIOUS.value}:
        return f"**[可疑] {annotation_text}**"
    if annotation_type in {AnnotationType.HIGH_RISK_UNCLEAR.value, AnnotationType.HIGH_RISK_SUSPICIOUS.value}:
        return f"<u><strong>[高风险可疑] {annotation_text}</strong></u>"
    return text


def _highest_priority_annotation(annotations: list[dict[str, Any]]) -> dict[str, Any]:
    priority = {
        AnnotationType.HIGH_RISK_UNCLEAR.value: 0,
        AnnotationType.HIGH_RISK_SUSPICIOUS.value: 0,
        AnnotationType.UNCLEAR.value: 1,
        AnnotationType.SUSPICIOUS.value: 1,
        AnnotationType.DUPLICATE.value: 2,
        AnnotationType.SUSPECTED_DUPLICATE.value: 2,
        AnnotationType.DELETION.value: 2,
        AnnotationType.TERM.value: 3,
        AnnotationType.UNCERTAIN_TRANSLATION.value: 3,
    }
    return sorted(
        annotations,
        key=lambda item: (priority.get(item.get("annotation_type", item.get("type")), 99), str(item)),
    )[0]


def _safe_markdown_text(value: Any) -> str:
    return html.escape(sanitize_text("" if value is None else str(value)), quote=False)


def _time_range(start: float | None, end: float | None) -> str:
    if start is None and end is None:
        return "[--]"
    start_text = "--" if start is None else f"{start:.2f}s"
    end_text = "--" if end is None else f"{end:.2f}s"
    return f"[{start_text} -> {end_text}]"


def _inline_markdown_to_html(text: str) -> str:
    protected: list[str] = []

    def protect_controlled(match: re.Match) -> str:
        safe_inner = html.escape(match.group("text"), quote=False)
        protected.append(f"<u><strong>[高风险可疑] {safe_inner}</strong></u>")
        return f"@@CONTROLLED_{len(protected) - 1}@@"

    text_with_placeholders = _CONTROLLED_HIGH_RISK_RE.sub(protect_controlled, text)
    rendered = html.escape(text_with_placeholders, quote=False)
    rendered = re.sub(r"~~(.+?)~~", r"<del>\1</del>", rendered)
    rendered = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", rendered)

    for index, controlled_html in enumerate(protected):
        rendered = rendered.replace(f"@@CONTROLLED_{index}@@", controlled_html)
    return rendered
