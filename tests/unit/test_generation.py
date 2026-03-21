"""Unit tests for LLM generators."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ragcore.generation.base import GenerationResult
from ragcore.generation.openai_generator import OpenAIGenerator
from ragcore.generation.litellm_generator import LiteLLMGenerator


# ---------------------------------------------------------------------------
# OpenAIGenerator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openai_generator_complete_returns_result():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Hello world"
    mock_response.usage.total_tokens = 42

    with patch("ragcore.generation.openai_generator.AsyncOpenAI") as MockClient:
        MockClient.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
        gen = OpenAIGenerator(model="gpt-4o-mini", api_key="test")
        result = await gen.generate("Say hello", stream=False)

    assert isinstance(result, GenerationResult)
    assert result.text == "Hello world"
    assert result.tokens_used == 42


@pytest.mark.asyncio
async def test_openai_generator_missing_usage_returns_zero_tokens():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Hi"
    mock_response.usage = None

    with patch("ragcore.generation.openai_generator.AsyncOpenAI") as MockClient:
        MockClient.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
        gen = OpenAIGenerator(model="gpt-4o-mini", api_key="test")
        result = await gen.generate("Hi", stream=False)

    assert isinstance(result, GenerationResult)
    assert result.tokens_used == 0


@pytest.mark.asyncio
async def test_openai_generator_stream_returns_async_gen():
    with patch("ragcore.generation.openai_generator.AsyncOpenAI"):
        gen = OpenAIGenerator(model="gpt-4o-mini", api_key="test")
        result = await gen.generate("stream me", stream=True)

    # Should return an async generator, not a GenerationResult
    import inspect
    assert inspect.isasyncgen(result)


# ---------------------------------------------------------------------------
# LiteLLMGenerator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_litellm_generator_complete_returns_result():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "LiteLLM answer"
    mock_response.usage.total_tokens = 15

    with patch("ragcore.generation.litellm_generator.litellm.acompletion", new=AsyncMock(return_value=mock_response)):
        gen = LiteLLMGenerator(model="gpt-4o-mini")
        result = await gen.generate("Ask something", stream=False)

    assert isinstance(result, GenerationResult)
    assert result.text == "LiteLLM answer"
    assert result.tokens_used == 15


@pytest.mark.asyncio
async def test_litellm_generator_missing_usage_returns_zero_tokens():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Answer"
    mock_response.usage = None

    with patch("ragcore.generation.litellm_generator.litellm.acompletion", new=AsyncMock(return_value=mock_response)):
        gen = LiteLLMGenerator(model="gpt-4o-mini")
        result = await gen.generate("Q", stream=False)

    assert result.tokens_used == 0
