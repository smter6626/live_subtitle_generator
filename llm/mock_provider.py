from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, ClassVar

from llm.provider_base import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMSchemaError,
    LLMTimeoutError,
    LLMMalformedResponseError,
    MissingAPIKeyError,
)


MOCK_TEXT_RESPONSE = "Mock LLM text response."


def _default_json_response() -> dict[str, Any]:
    return {
        "provider_id": "mock",
        "summary": "Mock structured response.",
        "sections": [],
        "key_terms": [],
        "action_items": [],
    }


@dataclass(frozen=True)
class MockProvider:
    """Deterministic provider used by tests and offline pipeline development."""

    mode: str = "success"
    text_response: str = MOCK_TEXT_RESPONSE
    json_response: dict[str, Any] = field(default_factory=_default_json_response)

    provider_id: ClassVar[str] = "mock"
    VALID_MODES: ClassVar[set[str]] = {
        "success",
        "missing_api_key",
        "authentication",
        "rate_limit",
        "timeout",
        "provider_error",
        "invalid_json",
        "schema_error",
    }

    def __post_init__(self):
        if self.mode not in self.VALID_MODES:
            raise ValueError(f"Unknown mock provider mode: {self.mode}")

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> dict[str, Any]:
        """Return a copied fixed JSON response or raise the configured typed error."""

        self._raise_for_mode()
        response = deepcopy(self.json_response)
        response["schema_name"] = schema_name
        return response

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return a fixed text response or raise the configured typed error."""

        self._raise_for_mode()
        return self.text_response

    def _raise_for_mode(self):
        if self.mode == "success":
            return
        if self.mode == "missing_api_key":
            raise MissingAPIKeyError("Mock provider missing API key failure.")
        if self.mode == "authentication":
            raise LLMAuthenticationError("Mock provider authentication failure.")
        if self.mode == "rate_limit":
            raise LLMRateLimitError("Mock provider rate limit failure.")
        if self.mode == "timeout":
            raise LLMTimeoutError("Mock provider timeout failure.")
        if self.mode == "provider_error":
            raise LLMProviderError("Mock provider generic failure.")
        if self.mode == "invalid_json":
            raise LLMMalformedResponseError("Mock provider malformed response failure.")
        if self.mode == "schema_error":
            raise LLMSchemaError("Mock provider schema failure.")
        raise LLMProviderError(f"Unhandled mock provider mode: {self.mode}")
