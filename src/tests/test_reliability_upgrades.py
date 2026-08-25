import pytest
import os
import io
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from google.genai import errors
from src.curator import summarize_news, generate_mentor_insight, generate_image_alt_text, fetch_single_feed, fetch_news
from src.settings import settings

@pytest.fixture(autouse=True)
def configure_test_settings():
    orig_dry_run = settings.is_dry_run
    orig_key = settings.gemini_key
    object.__setattr__(settings, "is_dry_run", False)
    object.__setattr__(settings, "gemini_key", "test-key")
    yield
    object.__setattr__(settings, "is_dry_run", orig_dry_run)
    object.__setattr__(settings, "gemini_key", orig_key)

@pytest.mark.asyncio
async def test_synthesis_failover_on_503(monkeypatch):
    """Verify synthesis immediately rotates on 503 without sleep or second attempt."""
    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()

    # First model raises 503 APIError, second model succeeds
    err_503 = errors.APIError(503, "Service Unavailable")

    success_resp = MagicMock()
    success_resp.text = "TOPIC: Agents\nBODY: Breakthrough autonomous agents have been developed by research teams to streamline enterprise workflows."

    mock_client.aio.models.generate_content = AsyncMock(side_effect=[err_503, success_resp])
    monkeypatch.setattr("google.genai.Client", lambda api_key: mock_client)

    news_items = [{"title": "Agent Breakthrough", "summary": "Details on autonomous agents", "link": "https://example.com/1", "source": "Tech", "source_id": "tech"}]
    context = {"day": "Monday", "session": "Morning Intelligence"}

    summary, link, topic, is_failover, dialect = await summarize_news(news_items, context)

    assert is_failover is True
    assert topic == "Agents"
    assert "Breakthrough autonomous agents" in summary
    assert mock_client.aio.models.generate_content.call_count == 2

@pytest.mark.asyncio
async def test_synthesis_auth_error_halts_rotation(monkeypatch):
    """Verify 401/403 halts model rotation immediately."""
    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()

    err_401 = errors.APIError(401, "Unauthenticated")
    mock_client.aio.models.generate_content = AsyncMock(side_effect=err_401)
    monkeypatch.setattr("google.genai.Client", lambda api_key: mock_client)

    news_items = [{"title": "Test", "summary": "Test summary", "link": "https://example.com/1", "source": "Tech", "source_id": "tech"}]
    context = {"day": "Monday", "session": "Morning Intelligence"}

    summary, link, topic, is_failover, dialect = await summarize_news(news_items, context)
    assert summary is None
    # Only called once on the first model, rotation halted
    assert mock_client.aio.models.generate_content.call_count == 1

@pytest.mark.asyncio
async def test_synthesis_unexpected_exception_rotates(monkeypatch):
    """Verify an unexpected non-APIError rotates to the next model safely."""
    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()

    err_unexpected = RuntimeError("Unexpected internal transport error")
    success_resp = MagicMock()
    success_resp.text = "TOPIC: Compute/HW\nBODY: New GPU cluster deployed with record bandwidth and extreme power efficiency across modern datacenters."

    mock_client.aio.models.generate_content = AsyncMock(side_effect=[err_unexpected, success_resp])
    monkeypatch.setattr("google.genai.Client", lambda api_key: mock_client)

    news_items = [{"title": "GPU Cluster", "summary": "Datacenter upgrades", "link": "https://example.com/gpu", "source": "HW", "source_id": "hw"}]
    context = {"day": "Monday", "session": "Morning Intelligence"}

    summary, link, topic, is_failover, dialect = await summarize_news(news_items, context)
    assert is_failover is True
    assert topic == "Compute/HW"
    assert "New GPU cluster deployed" in summary
    assert mock_client.aio.models.generate_content.call_count == 2

@pytest.mark.asyncio
async def test_synthesis_topic_fallbacks(monkeypatch):
    """Verify structured topic validation and local topic derivation order."""
    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()

    monkeypatch.setattr("google.genai.Client", lambda api_key: mock_client)
    context = {"day": "Monday", "session": "Morning Intelligence"}

    # 1. Valid TOPIC and BODY
    resp1 = MagicMock(text="TOPIC: Ethics\nBODY: New guidelines established for responsible deployment of frontier AI models in enterprise systems.")
    mock_client.aio.models.generate_content = AsyncMock(return_value=resp1)
    news1 = [{"title": "Ethics Guidelines", "summary": "Policy framework", "link": "https://example.com/1", "source_id": "openai_news", "source": "OpenAI"}]
    s, l, t, f, _ = await summarize_news(news1, context)
    assert t == "Ethics"
    assert "New guidelines established" in s

    # 2. Empty TOPIC with valid BODY -> derives topic locally via TOPIC_MAP keyword (e.g. GPU in Compute/HW)
    resp2 = MagicMock(text="TOPIC:\nBODY: Major breakthrough in GPU accelerator systems published today by leading research labs.")
    mock_client.aio.models.generate_content = AsyncMock(return_value=resp2)
    news2 = [{"title": "GPU Architecture Breakthrough", "summary": "New GPU capabilities", "link": "https://example.com/2", "source_id": "openai_news", "source": "OpenAI"}]
    s, l, t, f, _ = await summarize_news(news2, context)
    assert t == "Compute/HW"
    assert "Major breakthrough in GPU" in s

    # 3. Valid TOPIC with empty/short BODY -> invalid, rotates to next model
    resp_short = MagicMock(text="TOPIC: Agents\nBODY: Too short.")
    resp_ok = MagicMock(text="TOPIC: Compute/HW\nBODY: Semiconductor advancements offer incredible speedups for deep learning workloads across the industry.")
    mock_client.aio.models.generate_content = AsyncMock(side_effect=[resp_short, resp_ok])
    news3 = [{"title": "Silicon Advancements", "summary": "Hardware compute update", "link": "https://example.com/3", "source_id": "semi", "source": "Semi"}]
    s, l, t, f, _ = await summarize_news(news3, context)
    assert f is True
    assert t == "Compute/HW"

    # 4. Plain valid text without markers -> derives topic via normalized category if no TOPIC_MAP keyword
    resp4 = MagicMock(text="A comprehensive overview of recently discovered phenomena in multimodal learning without standard structured markers.")
    mock_client.aio.models.generate_content = AsyncMock(return_value=resp4)
    news4 = [{"title": "Miscellaneous Update", "summary": "Summary without keywords", "link": "https://example.com/4", "source_id": "research_lab", "source": "Lab"}]
    # research_lab category is mapped to "Research Lab"
    with patch("src.config.FEED_CATEGORY_MAP", {"research_lab": "research_lab"}):
        s, l, t, f, _ = await summarize_news(news4, context)
        assert t == "Research Lab"
        assert "A comprehensive overview" in s

@pytest.mark.asyncio
async def test_alt_text_mime_and_neutral_fallback(monkeypatch):
    """Verify alt-text detects valid MIME, never sends unknown bytes as JPEG, and uses accurate local fallback."""
    from PIL import Image

    # 1. Valid PNG bytes -> sent with image/png
    img = Image.new("RGB", (300, 300), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()

    resp_ai = MagicMock(text="Minimalist diagram showing neural network nodes connected by blue light beams.")
    mock_client.aio.models.generate_content = AsyncMock(return_value=resp_ai)
    monkeypatch.setattr("google.genai.Client", lambda api_key: mock_client)

    alt = await generate_image_alt_text(
        png_bytes,
        prompt="Neural network nodes",
        article_title="Scaling Laws in Transformers",
        category="research_lab",
        topic="Open Source"
    )
    assert alt == "Minimalist diagram showing neural network nodes connected by blue light beams."
    mock_client.aio.models.generate_content.assert_called_once()

    # 2. Unknown/unsupported bytes -> not sent to Gemini, local fallback returned
    mock_client.aio.models.generate_content.reset_mock()
    garbage_bytes = b"not_an_image_random_binary_garbage_1234567890"
    alt_fallback = await generate_image_alt_text(
        garbage_bytes,
        prompt="Some prompt",
        article_title="Scaling Laws in Transformers",
        category="research_lab",
        topic="Open Source"
    )
    assert alt_fallback == "Image accompanying news about Scaling Laws in Transformers"
    mock_client.aio.models.generate_content.assert_not_called()

    # 3. Vision failure on valid image -> falls back to neutral category or technology wording
    mock_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("Vision API rate limit"))
    alt_err = await generate_image_alt_text(
        png_bytes,
        prompt="Some prompt",
        article_title="",
        category="research_lab",
        topic="General"
    )
    assert alt_err == "Image accompanying a research lab news post"

    # 4. Empty image bytes -> returns empty string
    alt_empty = await generate_image_alt_text(b"")
    assert alt_empty == ""

@pytest.mark.asyncio
async def test_fetch_single_feed_error_handling_and_zero_article_health(mock_httpx_client, mocker):
    """Verify single feed error classification and that a valid feed with 0 new articles is healthy."""
    now_utc = datetime.now(timezone.utc)

    # 1. Network exception (Timeout) -> returns (url, [], False, "Network error: ...")
    mock_httpx_client.get = mocker.AsyncMock(side_effect=Exception("Connection timed out"))
    url, items, is_healthy, err = await fetch_single_feed(mock_httpx_client, "https://timeout.com/feed", now_utc - timedelta(days=2), now_utc, [], [])
    assert is_healthy is False
    assert "Network error" in err
    assert items == []

    # 2. Non-200 HTTP response -> returns (url, [], False, "HTTP 404")
    mock_resp_404 = mocker.MagicMock(status_code=404)
    mock_httpx_client.get = mocker.AsyncMock(return_value=mock_resp_404)
    url, items, is_healthy, err = await fetch_single_feed(mock_httpx_client, "https://notfound.com/feed", now_utc - timedelta(days=2), now_utc, [], [])
    assert is_healthy is False
    assert err == "HTTP 404"
    assert items == []

    # 3. Valid feed with entries, but all entries older than recency cutoff -> HEALTHY with 0 items returned
    old_entry = mocker.MagicMock()
    old_entry.link = "https://old.com/article1"
    old_entry.title = "Old Article"
    old_entry.summary = "Old summary"
    old_dt = now_utc - timedelta(days=10) # 10 days old, cutoff is 2 days
    old_entry.published_parsed = old_dt.utctimetuple()

    mock_feed = mocker.MagicMock()
    mock_feed.entries = [old_entry]
    mock_feed.bozo = 0
    mock_feed.feed = mocker.MagicMock(title="Valid Feed")
    mocker.patch("feedparser.parse", return_value=mock_feed)

    mock_resp_200 = mocker.MagicMock(status_code=200, content=b"<rss>valid</rss>")
    mock_httpx_client.get = mocker.AsyncMock(return_value=mock_resp_200)

    url, items, is_healthy, err = await fetch_single_feed(mock_httpx_client, "https://validold.com/feed", now_utc - timedelta(days=2), now_utc, [], [])
    assert is_healthy is True
    assert err is None
    assert items == [] # 0 new items, but feed is healthy!

def test_curator_has_single_summarize_news_ast_definition():
    """Verify src/curator.py contains exactly one top-level summarize_news function definition."""
    import ast
    curator_path = os.path.join(os.path.dirname(__file__), "..", "curator.py")
    with open(curator_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=curator_path)

    top_level_summarize = [
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "summarize_news"
    ]
    assert len(top_level_summarize) == 1, f"Expected 1 summarize_news definition, found {len(top_level_summarize)}"

@pytest.mark.asyncio
async def test_gemini_config_temperature_conditional(monkeypatch):
    """Verify gemini-3.7-flash and gemini-3.6-flash omit temperature while 3.5-flash-lite includes temperature."""
    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()

    configs_passed = []
    async def mock_generate(model, contents, config=None):
        configs_passed.append((model, config))
        resp = MagicMock()
        resp.text = "TOPIC: Compute/HW\nBODY: Advanced semiconductor test body with sufficient length exceeding sixty characters."
        return resp

    mock_client.aio.models.generate_content = AsyncMock(side_effect=mock_generate)
    monkeypatch.setattr("google.genai.Client", lambda api_key: mock_client)

    news_items = [{"title": "Hardware News", "summary": "Chip update", "link": "https://example.com", "source": "HW", "source_id": "hw"}]
    context = {"day": "Monday", "session": "Morning Intelligence"}

    # Test 1: gemini-3.5-flash-lite (should retain temperature)
    with patch("src.curator.GEMINI_MODEL_PRIORITY", ["models/gemini-3.5-flash-lite"]):
        await summarize_news(news_items, context)
        assert len(configs_passed) == 1
        model, cfg = configs_passed[-1]
        assert model == "models/gemini-3.5-flash-lite"
        assert cfg.temperature == 0.7

    # Test 2: gemini-3.7-flash (should omit temperature)
    with patch("src.curator.GEMINI_MODEL_PRIORITY", ["models/gemini-3.7-flash"]):
        await summarize_news(news_items, context)
        assert len(configs_passed) == 2
        model, cfg = configs_passed[-1]
        assert model == "models/gemini-3.7-flash"
        assert cfg.temperature is None

    # Test 3: gemini-3.6-flash (should omit temperature)
    with patch("src.curator.GEMINI_MODEL_PRIORITY", ["models/gemini-3.6-flash"]):
        await summarize_news(news_items, context)
        assert len(configs_passed) == 3
        model, cfg = configs_passed[-1]
        assert model == "models/gemini-3.6-flash"
        assert cfg.temperature is None

    # Test 4: Mentor insight conditional temperature
    with patch("src.curator.GEMINI_MODEL_PRIORITY", ["models/gemini-3.7-flash"]):
        await generate_mentor_insight(context)
        assert len(configs_passed) == 4
        model, cfg = configs_passed[-1]
        assert model == "models/gemini-3.7-flash"
        assert cfg.temperature is None
