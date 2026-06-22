import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from llm.llm_settings import LLMSettings
from llm.provider_base import (
    LLMAuthenticationError,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMSchemaError,
    LLMTimeoutError,
    LLMMalformedResponseError,
    MissingAPIKeyError,
)


DEFAULT_OPENAI_COMPATIBLE_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEFAULT_OPENAI_COMPATIBLE_MODEL = "deepseek-chat"
DEFAULT_TEMPERATURE = 0.2


@dataclass(frozen=True)
class HTTPJSONResponse:
    """Minimal response object returned by provider HTTP clients."""

    status_code: int
    json_body: dict[str, Any] | None = None
    text_body: str = ""


class HTTPJSONClient(Protocol):
    """Small injectable transport used to keep provider tests offline."""

    def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> HTTPJSONResponse:
        """POST JSON and return a parsed JSON response."""


class UrllibHTTPJSONClient:
    """stdlib JSON client for manual provider smoke tests."""

    def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> HTTPJSONResponse:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text_body = response.read().decode("utf-8")
                return HTTPJSONResponse(
                    status_code=response.status,
                    json_body=_parse_json_body(text_body),
                    text_body=text_body,
                )
        except urllib.error.HTTPError as exc:
            text_body = exc.read().decode("utf-8", errors="replace")
            return HTTPJSONResponse(
                status_code=exc.code,
                json_body=_parse_json_body_or_none(text_body),
                text_body=text_body,
            )
        except TimeoutError as exc:
            raise LLMTimeoutError("Provider request timed out.") from exc
        except OSError as exc:
            raise LLMProviderError("Provider request failed.") from exc


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible chat completions provider."""

    provider_id = "openai_compatible"

    def __init__(
        self,
        settings: LLMSettings | None = None,
        *,
        api_key: str | None = None,
        endpoint: str | None = None,
        model: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        http_client: HTTPJSONClient | None = None,
    ):
        self.settings = settings or LLMSettings(provider=self.provider_id)
        self.endpoint = endpoint or self.settings.endpoint or DEFAULT_OPENAI_COMPATIBLE_ENDPOINT
        self.model = model or self.settings.model or DEFAULT_OPENAI_COMPATIBLE_MODEL
        self.temperature = temperature
        self.http_client = http_client or UrllibHTTPJSONClient()
        self._api_key = api_key

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> dict[str, Any]:
        """Generate structured JSON through an OpenAI-compatible endpoint."""

        content = self._chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=True,
        )
        if isinstance(content, dict):
            return dict(content)
        if not isinstance(content, str):
            raise LLMSchemaError(f"{schema_name} response content must be a JSON object.")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMMalformedResponseError("Provider returned malformed JSON content.") from exc

        if not isinstance(parsed, dict):
            raise LLMSchemaError(f"{schema_name} response must be a JSON object.")
        return parsed

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        """Generate text through an OpenAI-compatible endpoint."""

        content = self._chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=False,
        )
        if not isinstance(content, str):
            raise LLMSchemaError("Provider text response content must be a string.")
        return content

    def _chat_completion(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
    ) -> str | dict[str, Any]:
        api_key = self._require_api_key()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = self.http_client.post_json(
                self.endpoint,
                headers=headers,
                payload=payload,
                timeout=self.settings.timeout_seconds,
            )
        except LLMTimeoutError:
            raise
        except TimeoutError as exc:
            raise LLMTimeoutError("Provider request timed out.") from exc
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError("Provider request failed.") from exc

        return self._extract_message_content(response)

    def _require_api_key(self) -> str:
        api_key = self._api_key or self.settings.read_api_key()
        if not api_key:
            raise MissingAPIKeyError(
                f"Missing API key in environment variable {self.settings.api_key_env_var}."
            )
        return api_key

    def _extract_message_content(self, response: HTTPJSONResponse | dict[str, Any]) -> str | dict[str, Any]:
        status_code, body = _normalize_response(response)
        if status_code in {401, 403}:
            raise LLMAuthenticationError("Provider authentication failed.")
        if status_code == 429:
            raise LLMRateLimitError("Provider rate limit exceeded.")
        if status_code >= 400:
            raise LLMProviderError(f"Provider HTTP error: {status_code}.")

        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMSchemaError("Provider response missing choices.")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise LLMSchemaError("Provider choice must be a mapping.")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise LLMSchemaError("Provider choice missing message.")
        content = message.get("content")
        if not isinstance(content, (str, dict)):
            raise LLMSchemaError("Provider message content must be a string or JSON object.")
        return content


def _normalize_response(response: HTTPJSONResponse | dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if isinstance(response, dict):
        return 200, response
    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int):
        raise LLMSchemaError("HTTP response status_code must be an integer.")
    body = getattr(response, "json_body", None)
    if body is None:
        text_body = getattr(response, "text_body", "")
        if not isinstance(text_body, str):
            raise LLMMalformedResponseError("Provider response body must be text.")
        body = _parse_json_body(text_body)
    if not isinstance(body, dict):
        raise LLMSchemaError("Provider response JSON body must be an object.")
    return status_code, body


def _parse_json_body(text_body: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text_body)
    except json.JSONDecodeError as exc:
        raise LLMMalformedResponseError("Provider returned malformed JSON body.") from exc
    if not isinstance(parsed, dict):
        raise LLMSchemaError("Provider response JSON body must be an object.")
    return parsed


def _parse_json_body_or_none(text_body: str) -> dict[str, Any] | None:
    try:
        return _parse_json_body(text_body)
    except (LLMMalformedResponseError, LLMSchemaError):
        return None
