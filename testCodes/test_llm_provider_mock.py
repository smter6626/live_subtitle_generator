import os
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm.mock_provider import MOCK_TEXT_RESPONSE, MockProvider  # noqa: E402
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


def test_mock_provider_text_success():
    provider = MockProvider()
    result = provider.generate_text(system_prompt="system", user_prompt="user")

    assert result == MOCK_TEXT_RESPONSE

    print_status("PASS", "mock provider text success")


def test_mock_provider_json_success():
    provider = MockProvider()
    result = provider.generate_json(
        system_prompt="system",
        user_prompt="user",
        schema_name="summary",
    )

    assert result["provider_id"] == "mock"
    assert result["schema_name"] == "summary"
    assert result["summary"] == "Mock structured response."

    print_status("PASS", "mock provider json success")


def test_mock_provider_deterministic():
    provider = MockProvider()
    first_text = provider.generate_text(system_prompt="a", user_prompt="b")
    second_text = provider.generate_text(system_prompt="a", user_prompt="b")
    first_json = provider.generate_json(system_prompt="a", user_prompt="b", schema_name="s")
    second_json = provider.generate_json(system_prompt="a", user_prompt="b", schema_name="s")

    assert first_text == second_text
    assert first_json == second_json
    assert first_json is not second_json

    print_status("PASS", "mock provider deterministic")


def test_mock_provider_failure_injection():
    cases = [
        ("missing_api_key", MissingAPIKeyError),
        ("authentication", LLMAuthenticationError),
        ("rate_limit", LLMRateLimitError),
        ("timeout", LLMTimeoutError),
        ("provider_error", LLMProviderError),
        ("invalid_json", LLMMalformedResponseError),
        ("schema_error", LLMSchemaError),
    ]

    for mode, expected_error in cases:
        provider = MockProvider(mode=mode)
        try:
            provider.generate_json(system_prompt="system", user_prompt="user", schema_name="s")
        except expected_error:
            continue
        raise AssertionError(f"mode {mode!r} did not raise {expected_error.__name__}")

    print_status("PASS", "mock provider failure injection")


def test_provider_errors_are_typed():
    typed_errors = [
        MissingAPIKeyError,
        LLMAuthenticationError,
        LLMRateLimitError,
        LLMTimeoutError,
        LLMMalformedResponseError,
        LLMSchemaError,
    ]

    assert all(issubclass(error_type, LLMProviderError) for error_type in typed_errors)

    print_status("PASS", "provider errors are typed")


def test_mock_provider_does_not_require_api_key():
    sentinel = object()
    original = os.environ.pop("DEEPSEEK_API_KEY", sentinel)
    try:
        provider = MockProvider()
        assert provider.generate_text(system_prompt="system", user_prompt="user")
    finally:
        if original is not sentinel:
            os.environ["DEEPSEEK_API_KEY"] = original

    print_status("PASS", "mock provider does not require api key")


def test_no_real_api_call():
    provider = MockProvider()
    assert provider.generate_text(system_prompt="system", user_prompt="user") == MOCK_TEXT_RESPONSE
    assert provider.generate_json(system_prompt="system", user_prompt="user", schema_name="s")

    print_status("PASS", "no real API call")


def test_mock_provider_does_not_write_files():
    old_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="mock_provider_no_files_") as tmp_dir:
        os.chdir(tmp_dir)
        try:
            provider = MockProvider()
            provider.generate_text(system_prompt="system", user_prompt="user")
            provider.generate_json(system_prompt="system", user_prompt="user", schema_name="s")
            assert list(Path(tmp_dir).iterdir()) == []
        finally:
            os.chdir(old_cwd)

    print_status("PASS", "mock provider does not write files")


def test_api_key_not_written():
    secret = "test-secret-value"
    os.environ["DEEPSEEK_API_KEY"] = secret
    try:
        provider = MockProvider()
        text_result = provider.generate_text(system_prompt="system", user_prompt="user")
        json_result = provider.generate_json(
            system_prompt="system",
            user_prompt="user",
            schema_name="s",
        )
    finally:
        os.environ.pop("DEEPSEEK_API_KEY", None)

    assert secret not in text_result
    assert secret not in repr(json_result)

    print_status("PASS", "api key not written")


def main():
    test_mock_provider_text_success()
    test_mock_provider_json_success()
    test_mock_provider_deterministic()
    test_mock_provider_failure_injection()
    test_provider_errors_are_typed()
    test_mock_provider_does_not_require_api_key()
    test_no_real_api_call()
    test_mock_provider_does_not_write_files()
    test_api_key_not_written()


if __name__ == "__main__":
    main()
