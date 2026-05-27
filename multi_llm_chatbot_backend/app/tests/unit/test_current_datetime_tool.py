import asyncio
import unittest
from unittest.mock import patch

from app.tools.current_datetime import TOOL_DEFINITION, execute


class TestCurrentDatetimeTool(unittest.TestCase):
    def test_tool_definition_shape(self):
        self.assertEqual(TOOL_DEFINITION["type"], "function")
        self.assertEqual(TOOL_DEFINITION["function"]["name"], "get_current_datetime")

    @patch("app.config.get_settings")
    def test_execute_returns_utc_and_local(self, mock_settings):
        mock_settings.return_value.tools.get_tool_config.return_value = {
            "default_timezone": "UTC",
        }
        result = asyncio.run(execute())
        self.assertIn("utc_iso", result)
        self.assertIn("local_iso", result)
        self.assertEqual(result["local_timezone"], "UTC")
