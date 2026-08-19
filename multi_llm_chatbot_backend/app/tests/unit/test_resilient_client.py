import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from app.llm.llm_client import ToolCallResult
from app.llm.resilient_client import ResilientLLMClient, _looks_like_failed_response


class TestResilientHelpers(unittest.TestCase):
    def test_failed_response_detection(self):
        self.assertTrue(_looks_like_failed_response(""))
        self.assertTrue(_looks_like_failed_response("I'm unable to connect to the AI service."))
        self.assertFalse(_looks_like_failed_response("Hello world"))


class TestResilientClient(unittest.TestCase):
    def test_primary_failure_uses_fallback(self):
        primary = MagicMock()
        primary.generate = AsyncMock(
            return_value="I'm unable to connect to the AI service. Please ensure the vLLM endpoint is available.",
        )
        fallback = MagicMock()
        fallback.generate = AsyncMock(return_value="fallback answer")

        client = ResilientLLMClient(primary, fallback, race_timeout_seconds=3.0)
        result = asyncio.run(
            client.generate("sys", [{"role": "user", "content": "hi"}], 0.5, 100),
        )
        self.assertEqual(result, "fallback answer")
        fallback.generate.assert_awaited_once()

    def test_race_uses_faster_fallback(self):
        async def slow_primary(*_a, **_k):
            await asyncio.sleep(5)
            return "primary"

        async def fast_fallback(*_a, **_k):
            return "fallback fast"

        primary = MagicMock()
        primary.generate = slow_primary
        fallback = MagicMock()
        fallback.generate = fast_fallback

        client = ResilientLLMClient(primary, fallback, race_timeout_seconds=0.05)
        result = asyncio.run(
            client.generate("sys", [{"role": "user", "content": "hi"}], 0.5, 100),
        )
        self.assertEqual(result, "fallback fast")

    def test_generate_stream_uses_primary_chunks(self):
        async def primary_stream(*_a, **_k):
            yield "A"
            yield "B"

        primary = MagicMock()
        primary.generate_stream = primary_stream
        fallback = MagicMock()
        fallback.generate_stream = AsyncMock()

        client = ResilientLLMClient(primary, fallback, race_timeout_seconds=3.0)

        async def collect():
            out = []
            async for chunk in client.generate_stream("sys", [{"role": "user", "content": "hi"}], 0.5, 100):
                out.append(chunk)
            return out

        self.assertEqual(asyncio.run(collect()), ["A", "B"])
        fallback.generate_stream.assert_not_called()

    def test_generate_stream_falls_back_on_primary_failure_text(self):
        async def primary_stream(*_a, **_k):
            yield "I'm unable to connect to the AI service."

        async def fallback_stream(*_a, **_k):
            yield "ok"

        primary = MagicMock()
        primary.generate_stream = primary_stream
        fallback = MagicMock()
        fallback.generate_stream = fallback_stream

        client = ResilientLLMClient(primary, fallback, race_timeout_seconds=3.0)

        async def collect():
            out = []
            async for chunk in client.generate_stream("sys", [{"role": "user", "content": "hi"}], 0.5, 100):
                out.append(chunk)
            return out

        self.assertEqual(asyncio.run(collect()), ["ok"])
