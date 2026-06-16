def build_section_summary_prompt(*, chunk_id: str, transcript_text: str) -> tuple[str, str]:
    """Return system/user prompts for a Phase 1A section summary."""

    raise NotImplementedError("Prompt templates are deferred to a later step.")


def build_global_summary_prompt(*, section_summaries: str) -> tuple[str, str]:
    """Return system/user prompts for a Phase 1A global summary."""

    raise NotImplementedError("Prompt templates are deferred to a later step.")


def build_readable_transcript_prompt(*, transcript_text: str) -> tuple[str, str]:
    """Return prompts for Phase 1B readable transcript structured output."""

    raise NotImplementedError("Prompt templates are deferred to a later step.")
