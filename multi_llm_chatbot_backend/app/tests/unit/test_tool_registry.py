import asyncio
import unittest
from unittest.mock import AsyncMock

from app.tools import (
    get_tool_definitions,
    get_tool_executor,
    list_registered_tools,
    _REGISTRY,
)


KNOWN_TOOLS = {"get_current_datetime"}


class TestToolDiscovery(unittest.TestCase):
    def test_known_tools_are_discovered(self):
        registered = set(list_registered_tools())
        for name in KNOWN_TOOLS:
            self.assertIn(name, registered, f"Tool '{name}' was not discovered")

    def test_registry_entries_have_definition_and_executor(self):
        for name, entry in _REGISTRY.items():
            self.assertIn("definition", entry, f"'{name}' missing definition")
            self.assertIn("executor", entry, f"'{name}' missing executor")


class TestGetToolDefinitions(unittest.TestCase):
    def test_returns_all_when_no_filter(self):
        defs = get_tool_definitions()
        names = {d["function"]["name"] for d in defs}
        self.assertTrue(KNOWN_TOOLS.issubset(names))

    def test_filter_to_single_tool(self):
        defs = get_tool_definitions(enabled=["get_current_datetime"])
        self.assertEqual(len(defs), 1)
        self.assertEqual(defs[0]["function"]["name"], "get_current_datetime")


class TestGetToolExecutor(unittest.TestCase):
    def test_dispatch_unknown_tool_returns_error(self):
        dispatch = get_tool_executor()
        result = asyncio.run(dispatch(name="nonexistent"))
        self.assertIn("error", result)
