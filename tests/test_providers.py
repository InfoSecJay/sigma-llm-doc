"""Tests for the LLM provider module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sigma_llm_doc.llm_provider import (
    _PROVIDERS,
    get_provider,
    GenerateResult,
    OpenAIProvider,
    ClaudeProvider,
    GeminiProvider,
)


def test_all_providers_registered():
    assert "openai" in _PROVIDERS
    assert "claude" in _PROVIDERS
    assert "gemini" in _PROVIDERS


def test_get_provider_unknown_raises():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_provider("nonexistent", api_key="test")


def test_openai_provider_constructor():
    provider = OpenAIProvider(api_key="test-key")
    assert provider.model == "gpt-4o-mini"
    assert provider.api_max_retries == 3


def test_claude_provider_constructor():
    provider = ClaudeProvider(api_key="test-key")
    assert provider.model == "claude-sonnet-4-5-20250929"
    assert provider.api_max_retries == 3


def test_gemini_provider_constructor():
    provider = GeminiProvider(api_key="test-key")
    assert provider.model == "gemini-2.5-flash"
    assert provider.api_max_retries == 3


def test_custom_model_and_retries():
    provider = OpenAIProvider(api_key="k", model="gpt-4o", api_max_retries=5)
    assert provider.model == "gpt-4o"
    assert provider.api_max_retries == 5


def test_generate_result_dataclass():
    r = GenerateResult(text="hello", input_tokens=100, output_tokens=50)
    assert r.text == "hello"
    assert r.input_tokens == 100
    assert r.output_tokens == 50


def test_generate_result_defaults():
    r = GenerateResult(text="hello")
    assert r.input_tokens == 0
    assert r.output_tokens == 0


@pytest.mark.asyncio
async def test_openai_generate_success():
    provider = OpenAIProvider(api_key="test")

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50

    mock_choice = MagicMock()
    mock_choice.message.content = "### Technical Context\nTest output"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    provider.client = MagicMock()
    provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = await provider.generate("prompt", "rule text")
    assert isinstance(result, GenerateResult)
    assert result.text == "### Technical Context\nTest output"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


@pytest.mark.asyncio
async def test_claude_generate_success():
    provider = ClaudeProvider(api_key="test")

    mock_usage = MagicMock()
    mock_usage.input_tokens = 200
    mock_usage.output_tokens = 80

    mock_content = MagicMock()
    mock_content.text = "### Technical Context\nClaude output"

    mock_message = MagicMock()
    mock_message.content = [mock_content]
    mock_message.usage = mock_usage

    provider.client = MagicMock()
    provider.client.messages.create = AsyncMock(return_value=mock_message)

    result = await provider.generate("prompt", "rule text")
    assert isinstance(result, GenerateResult)
    assert result.text == "### Technical Context\nClaude output"
    assert result.input_tokens == 200
    assert result.output_tokens == 80


@pytest.mark.asyncio
async def test_gemini_generate_success():
    provider = GeminiProvider(api_key="test")

    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 150
    mock_usage.candidates_token_count = 60

    mock_response = MagicMock()
    mock_response.text = "### Technical Context\nGemini output"
    mock_response.usage_metadata = mock_usage

    provider.client = MagicMock()
    provider.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    result = await provider.generate("prompt", "rule text")
    assert isinstance(result, GenerateResult)
    assert result.text == "### Technical Context\nGemini output"
    assert result.input_tokens == 150
    assert result.output_tokens == 60


@pytest.mark.asyncio
async def test_openai_retries_on_rate_limit():
    """Test that OpenAI provider retries on rate limit errors."""
    from openai import RateLimitError

    provider = OpenAIProvider(api_key="test", api_max_retries=2)

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 5

    mock_choice = MagicMock()
    mock_choice.message.content = "success"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    # First call raises rate limit, second succeeds
    mock_create = AsyncMock(
        side_effect=[
            RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            ),
            mock_response,
        ]
    )

    provider.client = MagicMock()
    provider.client.chat.completions.create = mock_create

    with patch("sigma_llm_doc.llm_provider.asyncio.sleep", new_callable=AsyncMock):
        result = await provider.generate("prompt", "rule")
        assert result.text == "success"
        assert mock_create.call_count == 2


def test_openai_base_url():
    provider = OpenAIProvider(api_key="test", base_url="https://custom.openai.example.com/v1")
    assert str(provider.client.base_url).startswith("https://custom.openai.example.com")


def test_claude_base_url():
    provider = ClaudeProvider(api_key="test", base_url="https://custom.anthropic.example.com")
    assert str(provider.client.base_url).startswith("https://custom.anthropic.example.com")


def test_gemini_vertexai_constructor():
    """Vertex AI mode should not require an api_key."""
    provider = GeminiProvider(vertexai=True, project="my-project", location="us-central1")
    assert provider.model == "gemini-2.5-flash"


def test_gemini_consumer_requires_api_key():
    """Consumer Gemini API should raise if no api_key and not vertexai."""
    with pytest.raises(ValueError, match="requires an api_key"):
        GeminiProvider()


def test_providers_accept_extra_kwargs():
    """Providers should silently ignore unknown kwargs (forward-compat)."""
    provider = OpenAIProvider(api_key="test", vertexai=True, gcp_project="ignored")
    assert provider.model == "gpt-4o-mini"

    provider = ClaudeProvider(api_key="test", vertexai=True, project="ignored")
    assert provider.model == "claude-sonnet-4-5-20250929"
