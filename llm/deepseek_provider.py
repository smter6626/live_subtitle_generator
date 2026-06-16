from llm.llm_settings import LLMSettings
from llm.provider_base import LLMProvider


class DeepSeekProvider(LLMProvider):
    """DeepSeek provider adapter placeholder.

    HTTP integration is intentionally deferred until the provider implementation
    step. This skeleton does not read API keys or contact external services.
    """

    provider_id = "deepseek"

    def __init__(self, settings: LLMSettings | None = None):
        self.settings = settings or LLMSettings()

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_name: str):
        raise NotImplementedError("DeepSeek JSON generation is not implemented in Step 3.")

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError("DeepSeek text generation is not implemented in Step 3.")
