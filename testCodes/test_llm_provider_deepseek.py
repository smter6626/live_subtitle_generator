import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm.deepseek_provider import DeepSeekProvider  # noqa: E402
from llm.openai_compatible_provider import HTTPJSONResponse  # noqa: E402
from llm.output_writer import append_error_log, ensure_llm_dir  # noqa: E402
from llm.provider_base import (  # noqa: E402
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMSchemaError,
    LLMTimeoutError,
    LLMMalformedResponseError,
    MissingAPIKeyError,
)


def print_status(status, name, detail=""):
    suffix = f" - {detail}" if detail else ""
    print(f"{status}: {name}{suffix}")


class FakeHTTPClient:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response or HTTPJSONResponse(
            status_code=200,
            json_body={"choices": [{"message": {"content": "fake text"}}]},
        )
        self.error = error
        self.calls = []

    def post_json(self, url, *, headers, payload, timeout):
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "payload": dict(payload),
                "timeout": timeout,
            }
        )
        if self.error:
            raise self.error
        return self.response


class NoNetworkHTTPClient:
    def post_json(self, url, *, headers, payload, timeout):
        raise AssertionError("HTTP client should not be called.")


class EnvVar:
    def __init__(self, name: str, value: str | None):
        self.name = name
        self.value = value
        self.original = None
        self.had_original = False

    def __enter__(self):
        self.had_original = self.name in os.environ
        self.original = os.environ.get(self.name)
        if self.value is None:
            os.environ.pop(self.name, None)
        else:
            os.environ[self.name] = self.value

    def __exit__(self, exc_type, exc, tb):
        if self.had_original:
            os.environ[self.name] = self.original
        else:
            os.environ.pop(self.name, None)


def make_fake_key():
    return "sk-" + ("e" * 24)


def make_text_response(text: str, status_code: int = 200):
    return HTTPJSONResponse(
        status_code=status_code,
        json_body={"choices": [{"message": {"content": text}}]},
    )


def assert_secret_not_in_exception(error: Exception, secret: str):
    assert secret not in str(error)
    assert ("Bear" + "er") not in str(error)


def test_deepseek_provider_requires_api_key():
    with EnvVar("DEEPSEEK_API_KEY", None):
        provider = DeepSeekProvider(http_client=NoNetworkHTTPClient())
        try:
            provider.generate_text(system_prompt="system", user_prompt="user")
        except MissingAPIKeyError:
            print_status("PASS", "deepseek provider requires api key")
            return
    raise AssertionError("Missing API key did not raise MissingAPIKeyError")


def test_deepseek_provider_builds_chat_completion_request():
    fake_key = make_fake_key()
    client = FakeHTTPClient(response=make_text_response("ok"))
    with EnvVar("DEEPSEEK_API_KEY", fake_key):
        provider = DeepSeekProvider(http_client=client)
        result = provider.generate_text(system_prompt="system prompt", user_prompt="user prompt")

    assert result == "ok"
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["headers"]["Authorization"] == ("Bear" + "er " + fake_key)
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["payload"]["model"] == "deepseek-chat"
    assert call["payload"]["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "user prompt"},
    ]
    assert call["payload"]["temperature"] == 0.2

    print_status("PASS", "deepseek provider builds chat completion request")


def test_deepseek_provider_text_success():
    fake_key = make_fake_key()
    client = FakeHTTPClient(response=make_text_response("hello"))
    with EnvVar("DEEPSEEK_API_KEY", fake_key):
        provider = DeepSeekProvider(http_client=client)
        result = provider.generate_text(system_prompt="system", user_prompt="user")

    assert result == "hello"
    assert fake_key not in result

    print_status("PASS", "deepseek provider text success")


def test_deepseek_provider_json_success():
    fake_key = make_fake_key()
    client = FakeHTTPClient(response=make_text_response('{"ok": true, "items": []}'))
    with EnvVar("DEEPSEEK_API_KEY", fake_key):
        provider = DeepSeekProvider(http_client=client)
        result = provider.generate_json(
            system_prompt="system",
            user_prompt="user",
            schema_name="unit_test",
        )

    assert result == {"ok": True, "items": []}
    assert client.calls[0]["payload"]["response_format"] == {"type": "json_object"}
    assert fake_key not in repr(result)

    print_status("PASS", "deepseek provider json success")


def test_deepseek_provider_malformed_json_response():
    fake_key = make_fake_key()
    client = FakeHTTPClient(
        response=HTTPJSONResponse(status_code=200, json_body=None, text_body="{not-json")
    )
    with EnvVar("DEEPSEEK_API_KEY", fake_key):
        provider = DeepSeekProvider(http_client=client)
        try:
            provider.generate_text(system_prompt="system", user_prompt="user")
        except LLMMalformedResponseError as exc:
            assert_secret_not_in_exception(exc, fake_key)
            print_status("PASS", "deepseek provider malformed json response")
            return
    raise AssertionError("malformed provider response did not raise LLMMalformedResponseError")


def test_deepseek_provider_invalid_json_contract():
    fake_key = make_fake_key()
    cases = [
        make_text_response("[]"),
        HTTPJSONResponse(status_code=200, json_body={"choices": []}),
    ]

    for response in cases:
        client = FakeHTTPClient(response=response)
        with EnvVar("DEEPSEEK_API_KEY", fake_key):
            provider = DeepSeekProvider(http_client=client)
            try:
                provider.generate_json(
                    system_prompt="system",
                    user_prompt="user",
                    schema_name="unit_test",
                )
            except LLMSchemaError as exc:
                assert_secret_not_in_exception(exc, fake_key)
                continue
        raise AssertionError("invalid provider JSON contract did not raise LLMSchemaError")

    print_status("PASS", "deepseek provider invalid json contract")


def test_deepseek_provider_authentication_error():
    fake_key = make_fake_key()
    for status_code in [401, 403]:
        client = FakeHTTPClient(response=HTTPJSONResponse(status_code=status_code, json_body={}))
        with EnvVar("DEEPSEEK_API_KEY", fake_key):
            provider = DeepSeekProvider(http_client=client)
            try:
                provider.generate_text(system_prompt="system", user_prompt="user")
            except LLMAuthenticationError as exc:
                assert_secret_not_in_exception(exc, fake_key)
                continue
        raise AssertionError(f"status {status_code} did not raise authentication error")

    print_status("PASS", "deepseek provider authentication error")


def test_deepseek_provider_rate_limit_error():
    fake_key = make_fake_key()
    client = FakeHTTPClient(response=HTTPJSONResponse(status_code=429, json_body={}))
    with EnvVar("DEEPSEEK_API_KEY", fake_key):
        provider = DeepSeekProvider(http_client=client)
        try:
            provider.generate_text(system_prompt="system", user_prompt="user")
        except LLMRateLimitError as exc:
            assert_secret_not_in_exception(exc, fake_key)
            print_status("PASS", "deepseek provider rate limit error")
            return
    raise AssertionError("429 did not raise rate limit error")


def test_deepseek_provider_timeout_error():
    fake_key = make_fake_key()
    client = FakeHTTPClient(error=TimeoutError("timed out with hidden details"))
    with EnvVar("DEEPSEEK_API_KEY", fake_key):
        provider = DeepSeekProvider(http_client=client)
        try:
            provider.generate_text(system_prompt="system", user_prompt="user")
        except LLMTimeoutError as exc:
            assert_secret_not_in_exception(exc, fake_key)
            print_status("PASS", "deepseek provider timeout error")
            return
    raise AssertionError("timeout did not raise LLMTimeoutError")


def test_deepseek_provider_http_error():
    fake_key = make_fake_key()
    client = FakeHTTPClient(response=HTTPJSONResponse(status_code=500, json_body={}))
    with EnvVar("DEEPSEEK_API_KEY", fake_key):
        provider = DeepSeekProvider(http_client=client)
        try:
            provider.generate_text(system_prompt="system", user_prompt="user")
        except LLMProviderError as exc:
            assert_secret_not_in_exception(exc, fake_key)
            assert "500" in str(exc)
            print_status("PASS", "deepseek provider http provider error")
            return
    raise AssertionError("500 did not raise provider error")


def test_deepseek_provider_secret_not_leaked():
    fake_key = make_fake_key()
    stdout = io.StringIO()
    stderr = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="deepseek_secret_") as tmp_dir:
        session_dir = Path(tmp_dir) / "session"
        session_dir.mkdir()
        paths = ensure_llm_dir(session_dir)
        with EnvVar("DEEPSEEK_API_KEY", fake_key):
            provider = DeepSeekProvider(
                http_client=FakeHTTPClient(
                    response=HTTPJSONResponse(status_code=500, json_body={"error": fake_key})
                )
            )
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    provider.generate_text(system_prompt="system", user_prompt="user")
                except LLMProviderError as exc:
                    append_error_log(
                        paths.llm_errors_log,
                        category=exc.__class__.__name__,
                        message=str(exc),
                        details=f"hidden {fake_key}",
                        llm_dir=paths.llm_dir,
                    )

        combined = stdout.getvalue() + stderr.getvalue()
        log_text = paths.llm_errors_log.read_text(encoding="utf-8")
        assert fake_key not in combined
        assert fake_key not in log_text

    print_status("PASS", "deepseek provider secret not leaked")


def test_deepseek_provider_no_real_network():
    fake_key = make_fake_key()
    client = FakeHTTPClient(response=make_text_response("offline"))
    with EnvVar("DEEPSEEK_API_KEY", fake_key):
        provider = DeepSeekProvider(http_client=client)
        result = provider.generate_text(system_prompt="system", user_prompt="user")

    assert result == "offline"
    assert len(client.calls) == 1

    print_status("PASS", "deepseek provider no real network")


def main():
    test_deepseek_provider_requires_api_key()
    test_deepseek_provider_builds_chat_completion_request()
    test_deepseek_provider_text_success()
    test_deepseek_provider_json_success()
    test_deepseek_provider_malformed_json_response()
    test_deepseek_provider_invalid_json_contract()
    test_deepseek_provider_authentication_error()
    test_deepseek_provider_rate_limit_error()
    test_deepseek_provider_timeout_error()
    test_deepseek_provider_http_error()
    test_deepseek_provider_secret_not_leaked()
    test_deepseek_provider_no_real_network()


if __name__ == "__main__":
    main()
