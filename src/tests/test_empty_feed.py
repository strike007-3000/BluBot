from unittest.mock import AsyncMock, MagicMock

import pytest

from src.curator import fetch_single_feed

EMPTY_RSS = b'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title></channel></rss>'


@pytest.mark.asyncio
@pytest.mark.parametrize("url,healthy,error", [
    ("https://arxiv.org/rss/cs.LG", True, None),
    ("https://example.com/feed", False, "Empty feed"),
])
async def test_empty_feed_is_healthy_only_for_arxiv(url, healthy, error):
    client = MagicMock(get=AsyncMock(return_value=MagicMock(status_code=200, content=EMPTY_RSS)))

    _, items, ok, err = await fetch_single_feed(client, url, None, __import__("datetime").datetime.now(__import__("datetime").timezone.utc), [], None)

    assert items == [] and ok is healthy and err == error
