from typing import Any, Protocol


class LLMError(Exception):
    """Base exception for LLM sidecar failures."""


class LLMProviderError(LLMError):
    """Raised when a provider call fails."""


class LLMConfigurationError(LLMProviderError):
    """Raised when provider configuration is missing or invalid."""


class MissingAPIKeyError(LLMConfigurationError):
    """Raised when the configured provider needs an API key but none is available."""


class LLMAuthenticationError(LLMProviderError):
    """Raised when provider credentials are rejected."""


class LLMRateLimitError(LLMProviderError):
    """Raised when a provider rate limit is hit."""


class LLMTimeoutError(LLMProviderError):
    """Raised when a provider call times out."""


class ProviderTimeoutError(LLMTimeoutError):
    """Raised when a provider request times out."""


class LLMMalformedResponseError(LLMProviderError):
    """Raised when a provider response is not parseable."""


class ProviderResponseError(LLMMalformedResponseError):
    """Raised when a provider response cannot be used."""


class LLMInvalidResponseError(LLMProviderError):
    """Raised when a parsed provider response is invalid for the requested use."""


class LLMSchemaError(LLMInvalidResponseError):
    """Raised when structured provider output fails schema expectations."""


class SchemaValidationError(LLMSchemaError):
    """Raised when structured LLM output does not match the expected schema."""


class RendererError(LLMError):
    """Raised when a derived Markdown/HTML view cannot be rendered."""


class PipelineError(LLMError):
    """Raised when an LLM pipeline step fails."""


class LLMProvider(Protocol):
    """Minimal interface implemented by mock and API-backed LLM providers."""

    provider_id: str

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> dict[str, Any]:
        """Return parsed structured output for the requested schema."""

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return text output for prompts that do not require structured JSON."""
