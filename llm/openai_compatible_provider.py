from llm.llm_settings import LLMSettings
from llm.provider_base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible provider adapter placeholder."""

    provider_id = "openai_compatible"

    def __init__(self, settings: LLMSettings | None = None):
        self.settings = settings or LLMSettings(provider=self.provider_id)

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_name: str):
        raise NotImplementedError(
            "OpenAI-compatible JSON generation is not implemented in Step 3."
        )

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError(
            "OpenAI-compatible text generation is not implemented in Step 3."
        )
