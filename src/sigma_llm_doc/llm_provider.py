"""LLM abstraction layer with async provider implementations."""

import asyncio
import logging
from abc import ABC, abstractmethod

from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError, APIConnectionError

import anthropic
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

# Provider registry for extensibility
_PROVIDERS: dict[str, type["LLMProvider"]] = {}


def register_provider(name: str):
    """Decorator to register an LLM provider class."""
    def decorator(cls):
        _PROVIDERS[name] = cls
        return cls
    return decorator


def get_provider(name: str, **kwargs) -> "LLMProvider":
    """Instantiate a registered provider by name."""
    if name not in _PROVIDERS:
        available = ", ".join(_PROVIDERS.keys())
        raise ValueError(f"Unknown LLM provider '{name}'. Available: {available}")
    return _PROVIDERS[name](**kwargs)


class LLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, rule_text: str) -> str:
        """Generate an investigation guide for a Sigma rule.

        Args:
            prompt: The system/instruction prompt.
            rule_text: The full Sigma rule YAML text.

        Returns:
            The generated markdown investigation guide.
        """
        ...


@register_provider("openai")
class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider using the modern AsyncOpenAI SDK (>=1.0)."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", api_max_retries: int = 3):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.api_max_retries = api_max_retries

    async def generate(self, prompt: str, rule_text: str) -> str:
        """Call the OpenAI chat completions API with exponential backoff retry."""
        last_exception = None

        for attempt in range(1, self.api_max_retries + 1):
            try:
                logger.debug(
                    "OpenAI API call attempt %d/%d (model=%s)",
                    attempt, self.api_max_retries, self.model,
                )
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "user", "content": f"{prompt}\n\n{rule_text}"}
                    ],
                )
                content = response.choices[0].message.content
                if content is None:
                    content = ""
                return content.strip()

            except RateLimitError as e:
                last_exception = e
                wait = 2 ** attempt
                logger.warning(
                    "Rate limited (attempt %d/%d). Retrying in %ds...",
                    attempt, self.api_max_retries, wait,
                )
                await asyncio.sleep(wait)

            except (APITimeoutError, APIConnectionError) as e:
                last_exception = e
                wait = 2 ** attempt
                logger.warning(
                    "API connection/timeout error (attempt %d/%d): %s. Retrying in %ds...",
                    attempt, self.api_max_retries, e, wait,
                )
                await asyncio.sleep(wait)

            except APIError as e:
                last_exception = e
                if e.status_code and e.status_code >= 500:
                    wait = 2 ** attempt
                    logger.warning(
                        "API server error %s (attempt %d/%d). Retrying in %ds...",
                        e.status_code, attempt, self.api_max_retries, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error("Non-retryable API error: %s", e)
                    raise

        # All retries exhausted
        logger.error(
            "OpenAI API call failed after %d attempts: %s",
            self.api_max_retries, last_exception,
        )
        raise last_exception


@register_provider("claude")
class ClaudeProvider(LLMProvider):
    """Anthropic Claude LLM provider using the AsyncAnthropic SDK."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929", api_max_retries: int = 3):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.api_max_retries = api_max_retries

    async def generate(self, prompt: str, rule_text: str) -> str:
        """Call the Anthropic Messages API with exponential backoff retry."""
        last_exception = None

        for attempt in range(1, self.api_max_retries + 1):
            try:
                logger.debug(
                    "Claude API call attempt %d/%d (model=%s)",
                    attempt, self.api_max_retries, self.model,
                )
                message = await self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=[
                        {"role": "user", "content": f"{prompt}\n\n{rule_text}"}
                    ],
                )
                content = message.content[0].text if message.content else ""
                return content.strip()

            except anthropic.RateLimitError as e:
                last_exception = e
                wait = 2 ** attempt
                logger.warning(
                    "Rate limited (attempt %d/%d). Retrying in %ds...",
                    attempt, self.api_max_retries, wait,
                )
                await asyncio.sleep(wait)

            except (anthropic.APITimeoutError, anthropic.APIConnectionError) as e:
                last_exception = e
                wait = 2 ** attempt
                logger.warning(
                    "API connection/timeout error (attempt %d/%d): %s. Retrying in %ds...",
                    attempt, self.api_max_retries, e, wait,
                )
                await asyncio.sleep(wait)

            except anthropic.APIStatusError as e:
                last_exception = e
                if e.status_code >= 500:
                    wait = 2 ** attempt
                    logger.warning(
                        "API server error %s (attempt %d/%d). Retrying in %ds...",
                        e.status_code, attempt, self.api_max_retries, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error("Non-retryable API error: %s", e)
                    raise

        # All retries exhausted
        logger.error(
            "Claude API call failed after %d attempts: %s",
            self.api_max_retries, last_exception,
        )
        raise last_exception
