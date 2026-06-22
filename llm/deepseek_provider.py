from llm.llm_settings import (
    DEFAULT_DEEPSEEK_ENDPOINT,
    DEFAULT_DEEPSEEK_MODEL,
    LLMSettings,
)
from llm.openai_compatible_provider import HTTPJSONClient, OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek OpenAI-compatible provider adapter."""

    provider_id = "deepseek"

    def __init__(
        self,
        settings: LLMSettings | None = None,
        *,
        api_key: str | None = None,
        endpoint: str | None = None,
        model: str | None = None,
        http_client: HTTPJSONClient | None = None,
    ):
        active_settings = settings or LLMSettings(provider=self.provider_id)
        super().__init__(
            active_settings,
            api_key=api_key,
            endpoint=endpoint or active_settings.endpoint or DEFAULT_DEEPSEEK_ENDPOINT,
            model=model or active_settings.model or DEFAULT_DEEPSEEK_MODEL,
            http_client=http_client,
        )
