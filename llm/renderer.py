from llm.state_schema import ReadableTranscriptState


def render_markdown(state: ReadableTranscriptState, *, review: bool = False) -> str:
    """Render a readable transcript state to Markdown."""

    raise NotImplementedError("Markdown rendering is deferred to a later step.")


def render_html(state: ReadableTranscriptState, *, review: bool = False) -> str:
    """Render a readable transcript state to HTML."""

    raise NotImplementedError("HTML rendering is deferred to a later step.")
