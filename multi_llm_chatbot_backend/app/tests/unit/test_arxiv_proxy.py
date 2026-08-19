import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.routes.phd_canvas import _parse_arxiv_feed


SAMPLE = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1006.1956v2</id>
    <title>A Semi-distributed Reputation Based Intrusion Detection System</title>
    <published>2010-06-10T06:03:44Z</published>
    <author><name>Jane Doe</name></author>
  </entry>
</feed>
"""


def test_parse_arxiv_feed_atom_ns():
    rows = _parse_arxiv_feed(SAMPLE)
    assert len(rows) == 1
    assert rows[0]["id"] == "1006.1956v2"
    assert "Intrusion Detection" in rows[0]["title"]
    assert rows[0]["authors"] == ["Jane Doe"]
    assert rows[0]["year"] == "2010"


def test_parse_arxiv_feed_empty():
    xml = """<?xml version='1.0'?><feed xmlns="http://www.w3.org/2005/Atom"></feed>"""
    assert _parse_arxiv_feed(xml) == []
