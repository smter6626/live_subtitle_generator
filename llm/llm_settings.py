import os
from dataclasses import dataclass


DEFAULT_PROVIDER = "deepseek"
DEFAULT_OUTPUT_LANGUAGE = "zh"
DEFAULT_API_KEY_ENV_VAR = "DEEPSEEK_API_KEY"
DEFAULT_DEEPSEEK_MODEL_ENV_VAR = "DEEPSEEK_MODEL"
DEFAULT_DEEPSEEK_ENDPOINT_ENV_VAR = "DEEPSEEK_ENDPOINT"


@dataclass(frozen=True)
class LLMSettings:
    """Non-secret LLM sidecar settings.

    The actual API key is intentionally not stored here. Phase 1 reads it only
    from the environment variable named by api_key_env_var.
    """

    provider: str = DEFAULT_PROVIDER
    output_language: str = DEFAULT_OUTPUT_LANGUAGE
    api_key_env_var: str = DEFAULT_API_KEY_ENV_VAR
    model: str | None = None
    endpoint: str | None = None
    timeout_seconds: float = 60.0
    max_retries: int = 1

    @classmethod
    def from_env(cls):
        """Build non-secret settings from environment variables."""

        model = os.environ.get(DEFAULT_DEEPSEEK_MODEL_ENV_VAR) or None
        endpoint = os.environ.get(DEFAULT_DEEPSEEK_ENDPOINT_ENV_VAR) or None
        return cls(model=model, endpoint=endpoint)
