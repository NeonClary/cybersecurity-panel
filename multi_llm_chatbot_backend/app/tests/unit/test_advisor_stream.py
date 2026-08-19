import asyncio
import unittest

from app.core.advisor_stream import iter_parallel_advisor_events


class TestParallelAdvisorEvents(unittest.IsolatedAsyncioTestCase):
    async def test_start_order_follows_first_token_not_rank(self):
        async def stream_one(pid: str):
            if pid == "jerry_huaute":
                await asyncio.sleep(0.05)
                yield {"event": "delta", "text": "J"}
                yield {"event": "delta", "text": "erry"}
                yield {
                    "event": "done",
                    "result": {
                        "persona_id": pid,
                        "persona_name": "Jerry",
                        "response": "Jerry",
                    },
                }
                return
            yield {"event": "delta", "text": "T"}
            await asyncio.sleep(0.02)
            yield {"event": "delta", "text": "hreat"}
            yield {
                "event": "done",
                "result": {
                    "persona_id": pid,
                    "persona_name": "Threat",
                    "response": "Threat",
                },
            }

        names = {
            "jerry_huaute": {"persona_name": "Jerry"},
            "threat_modeler": {"persona_name": "Threat"},
        }
        events = []
        async for ev in iter_parallel_advisor_events(
            ["jerry_huaute", "threat_modeler"],
            stream_one,
            timeout_seconds=2.0,
            persona_meta=lambda pid: names[pid],
        ):
            events.append(ev)

        types = [e["type"] for e in events]
        self.assertEqual(types[0], "advisor_start")
        self.assertEqual(events[0]["data"]["persona_id"], "threat_modeler")
        start_ids = [e["data"]["persona_id"] for e in events if e["type"] == "advisor_start"]
        self.assertEqual(start_ids, ["threat_modeler", "jerry_huaute"])
        self.assertIn("advisor_delta", types)
        self.assertEqual(types.count("advisor_done"), 2)

    async def test_timeout_emits_start_and_done(self):
        async def stream_one(_pid: str):
            await asyncio.sleep(1)
            yield {"event": "delta", "text": "late"}

        events = []
        async for ev in iter_parallel_advisor_events(
            ["slow"],
            stream_one,
            timeout_seconds=0.05,
            persona_meta=lambda pid: {"persona_name": pid},
        ):
            events.append(ev)

        self.assertEqual([e["type"] for e in events], ["advisor_start", "advisor_done"])
        self.assertIn("too long", events[-1]["data"]["content"])
