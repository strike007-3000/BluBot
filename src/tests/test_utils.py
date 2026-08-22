import pytest
import ipaddress
from unittest.mock import AsyncMock, MagicMock
from src.utils import _is_public_ip, truncate_bytes, get_image_mime, compress_image, normalize_url

def test_is_public_ip_validation():
    """Verify that private and reserved IP addresses are correctly identified as non-public."""
    # Public IPs
    assert _is_public_ip("1.1.1.1") is True
    assert _is_public_ip("8.8.8.8") is True
    assert _is_public_ip("104.26.10.19") is True # Google
    
    # Private IPs (RFC 1918)
    assert _is_public_ip("10.0.0.1") is False
    assert _is_public_ip("172.16.0.1") is False
    assert _is_public_ip("192.168.1.1") is False
    
    # Loopback and Local
    assert _is_public_ip("127.0.0.1") is False
    assert _is_public_ip("::1") is False
    assert _is_public_ip("localhost") is False # Should return False via ValueError
    
    # Reserved/Special
    assert _is_public_ip("169.254.169.254") is False # AWS Metadata
    assert _is_public_ip("224.0.0.1") is False # Multicast

def test_truncate_bytes_unicode():
    """Verify that truncation doesn't break multi-byte unicode characters."""
    text = "Hello 🌍 focus" # 🌍 is 4 bytes in UTF-8
    # "Hello " is 6 bytes. 🌍 is 4 bytes. Total 10. " focus" is 6.
    
    # Truncate in the middle of the emoji
    # "Hello " (6) + part of emoji
    truncated = truncate_bytes(text, 8)
    assert truncated == "Hello "
    
    # Truncate after the emoji
    truncated = truncate_bytes(text, 10)
    assert truncated == "Hello 🌍"
    
    # Truncate within ASCII
    assert truncate_bytes("Hello World", 5) == "Hello"

def test_get_image_mime_detection():
    """Verify MIME type detection for different image headers."""
    # Mock some image bytes
    from PIL import Image
    import io
    
    # JPEG
    img = Image.new('RGB', (10, 10), color='red')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    assert get_image_mime(buf.getvalue()) == "image/jpeg"
    
    # PNG
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    assert get_image_mime(buf.getvalue()) == "image/png"

def test_compress_image_reduction():
    """Verify that compress_image actually reduces size if needed."""
    from PIL import Image
    import io
    
    # Create a large image
    img = Image.new('RGB', (1000, 1000), color='blue')
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=100)
    original_size = len(buf.getvalue())
    
    # Compress to something small (e.g. 50KB)
    compressed = compress_image(buf.getvalue(), max_size_kb=50)
    assert len(compressed) < original_size
    assert len(compressed) <= 50 * 1024

@pytest.mark.asyncio
async def test_ssrf_blocking_in_redirects(mock_httpx_client, mocker):
    """Verify that get_with_safe_redirects blocks redirects to private IPs."""
    from src.utils import get_with_safe_redirects
    
    # Mocking socket.getaddrinfo to return a private IP for "malicious.com"
    mock_resolve = mocker.patch("src.utils._resolve_public_ip_candidates")
    mock_resolve.return_value = None # This signals a private or unresolvable IP in our logic
    
    resp = await get_with_safe_redirects(mock_httpx_client, "http://malicious.com")
    assert resp is None
    
    # Test scheme downgrade
    mock_resolve.return_value = ["1.1.1.1"]
    mock_httpx_client.get = AsyncMock()
    mock_httpx_client.get.return_value = MagicMock(
        is_redirect=True,
        headers={"location": "http://unsafe.com"},
        status_code=301
    )
    
    # Starting with https
    resp = await get_with_safe_redirects(mock_httpx_client, "https://safe.com")
    assert resp is None # Should block downgrade to http

def test_normalize_url_scenarios():
    """Verify that normalize_url handles various edge cases correctly."""
    # 1. Protocol-relative
    assert normalize_url("//example.com/test") == "https://example.com/test"
    
    # 2. Relative resolving
    assert normalize_url("/img.jpg", base_url="https://site.com/blog") == "https://site.com/img.jpg"
    
    # 3. Tracking parameters
    url_with_tracking = "https://example.com/page?utm_source=twitter&ref=nudge&s=09&feature=share&id=123"
    normalized = normalize_url(url_with_tracking)
    assert "utm_source" not in normalized
    assert "ref" not in normalized
    assert "s=" not in normalized
    assert "feature=" not in normalized
    assert "id=123" in normalized
    
    # 4. Fragments and Casing
    assert normalize_url("HTTPS://Example.COM/Path/#frag") == "https://example.com/Path/"
    
    # 5. Null/Malformed
    assert normalize_url(None) == ""
    assert normalize_url("not-a-url") == "not-a-url"

def test_smart_truncate_edge_cases():
    from src.utils import smart_truncate
    # 1. Short input
    assert smart_truncate("short", 10) == "short"
    # 2. None or empty
    assert smart_truncate(None, 10) is None
    assert smart_truncate("", 10) == ""
    # 3. Exact length
    assert smart_truncate("1234567890", 10) == "1234567890"
    # 4. Long input with space backtracking
    assert smart_truncate("Hello World Testing", 15) == "Hello World..."
    # 5. Long input with no space (hard cut fallback)
    assert smart_truncate("HelloWorldTesting", 10) == "HelloWo..."

def test_smart_split_edge_cases():
    from src.utils import smart_split
    # 1. None or empty
    assert smart_split(None, 10) == []
    assert smart_split("", 10) == []
    # 2. Fits in one part
    assert smart_split("abc", 5) == ["abc"]
    # 3. Paragraph boundary split
    text_para = "Para1\n\nPara2"
    assert smart_split(text_para, 8) == ["Para1", "Para2"]
    # 4. Sentence boundary split
    text_sent = "Sentence one. Sentence two."
    assert smart_split(text_sent, 18) == ["Sentence one.", "Sentence two."]
    # 5. Word boundary split
    text_word = "Word1 Word2 Word3"
    assert smart_split(text_word, 12) == ["Word1 Word2", "Word3"]
    # 6. Max chunks limit
    text_long = "One. Two. Three. Four."
    assert smart_split(text_long, 6, max_chunks=2) == ["One.", "Two...."]

def test_seen_interactions_persistence(tmp_path):
    from src.utils import load_seen_interactions, save_seen_interactions
    import src.utils
    
    # Override the path for testing
    test_path = str(tmp_path / "test_interactions.json")
    original_path = src.utils.INTERACTIONS_STATE_PATH
    src.utils.INTERACTIONS_STATE_PATH = test_path
    try:
        # Load from non-existent file
        assert load_seen_interactions() == []
        
        # Save and load
        ids = ["id1", "id2", "id3"]
        save_seen_interactions(ids)
        assert load_seen_interactions() == ids
    finally:
        src.utils.INTERACTIONS_STATE_PATH = original_path

def test_sanitize_and_migrate_state_pureness():
    from src.utils import sanitize_and_migrate_state, LEGACY_DEFAULT_UPDATED_AT
    # 1. Empty input
    state = sanitize_and_migrate_state({})
    assert state["schema_version"] == 2
    assert state["revision"] == 1
    assert state["updated_at"] == LEGACY_DEFAULT_UPDATED_AT
    assert state["unsynced_gist"] is False
    assert state["links"] == []
    assert state["pending_stories"] == []

    # 2. Idempotence test
    state2 = sanitize_and_migrate_state(state)
    assert state2 == state

    # 3. Preserves existing valid updated_at
    custom_time = "2026-08-18T19:00:00Z"
    state3 = sanitize_and_migrate_state({"updated_at": custom_time, "revision": 5})
    assert state3["updated_at"] == custom_time
    assert state3["revision"] == 5

def test_pending_stories_uncertain_transition():
    from src.utils import filter_and_update_pending_stories
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    old_time = (now - timedelta(hours=25)).isoformat()
    recent_time = (now - timedelta(minutes=30)).isoformat()

    state = {
        "recent_stories": [{"url": "https://example.com/pub1"}],
        "pending_stories": [
            {"url": "https://example.com/pending-old", "created_at": old_time, "stage": "pending"},
            {"url": "https://example.com/pending-recent", "created_at": recent_time, "stage": "pending"}
        ]
    }

    seen_urls = filter_and_update_pending_stories(state, now_utc=now)

    # Verify old pending transitioned to uncertain
    assert state["pending_stories"][0]["stage"] == "uncertain"
    assert state["pending_stories"][1]["stage"] == "pending"

    # All URLs included in duplicate suppression set
    assert "https://example.com/pub1" in seen_urls
    assert "https://example.com/pending-old" in seen_urls
    assert "https://example.com/pending-recent" in seen_urls

def test_gist_reconciliation_and_fallback(tmp_path, mocker):
    import src.utils
    from src.utils import load_seen_articles, save_seen_articles
    from src.settings import settings

    test_file = str(tmp_path / "seen_articles.json")
    mocker.patch.object(src.utils, "SEEN_FILE_PATH", test_file)
    object.__setattr__(settings, "gist_id", "test_gist_id")
    object.__setattr__(settings, "gist_token", "test_token")
    object.__setattr__(settings, "is_dry_run", False)

    # Mock Gist return lower revision than local
    mocker.patch("src.utils._load_gist_state", return_value={
        "schema_version": 2, "revision": 2, "updated_at": "2026-08-18T10:00:00Z",
        "links": ["https://example.com/gist-only"]
    })

    # Save local state with revision 5
    src.utils.save_json_state(test_file, {
        "schema_version": 2, "revision": 5, "updated_at": "2026-08-18T12:00:00Z",
        "links": ["https://example.com/local-only"]
    })

    loaded = load_seen_articles()
    assert loaded["revision"] == 5
    assert "https://example.com/local-only" in loaded["links"]

    # Test Gist save failure handling during reservation
    mocker.patch("src.utils._save_gist_state", return_value=False)
    res_ok, _ = save_seen_articles({"revision": 5, "pending_stories": []}, is_reservation=True)
    assert res_ok is False

def test_gist_success_local_write_failure_returns_false(mocker, tmp_path):
    """Verify that if Gist write succeeds but local atomic write fails, save_seen_articles returns False."""
    import src.utils
    from src.utils import save_seen_articles
    from src.settings import settings

    object.__setattr__(settings, "is_dry_run", False)
    object.__setattr__(settings, "gist_id", "test_id")
    object.__setattr__(settings, "gist_token", "test_token")

    mocker.patch("src.utils._save_gist_state", return_value=True)
    mocker.patch("src.utils.save_json_state", side_effect=IOError("Disk write error"))

    ok, state = save_seen_articles({"revision": 5, "pending_stories": []}, is_reservation=False)
    assert ok is False
    assert state["revision"] == 6

def test_dry_run_makes_no_state_writes(mocker):
    """Verify that dry-run returns True immediately without making Gist or local disk writes."""
    import src.utils
    from src.utils import save_seen_articles
    from src.settings import settings

    object.__setattr__(settings, "is_dry_run", True)
    mock_gist = mocker.patch("src.utils._save_gist_state")
    mock_local = mocker.patch("src.utils.save_json_state")

    data = {"revision": 5, "pending_stories": []}
    ok, state = save_seen_articles(data, is_reservation=True)
    assert ok is True
    assert state == data
    mock_gist.assert_not_called()
    mock_local.assert_not_called()

def test_compute_story_fingerprint_normalizes_headlines():
    """Verify fingerprinting strips publisher suffixes, prices, and stopwords while preserving version tokens."""
    from src.utils import compute_story_fingerprint

    t1 = "Anthropic Releases Claude 3.7 Sonnet for $0.75/1M Tokens - TechCrunch"
    fp1 = compute_story_fingerprint(t1)
    assert "techcrunch" not in fp1
    assert "0.75" not in fp1
    assert "v3.7" in fp1
    assert "anthropic" in fp1
    assert "sonnet" in fp1

def test_story_fingerprint_version_boundary_enforcement():
    """Verify version boundary check: v3.6 vs v3.7 returns False, v3.7 vs v3.7 returns True."""
    from src.utils import compute_story_fingerprint, are_story_fingerprints_similar

    fp_36 = compute_story_fingerprint("Anthropic Launches Claude 3.6 Sonnet - VentureBeat")
    fp_37 = compute_story_fingerprint("Anthropic Releases Claude 3.7 Sonnet - TechCrunch")
    fp_37_alt = compute_story_fingerprint("Anthropic Announces New Claude 3.7 Sonnet Model - Wired")

    # Version mismatch (3.6 vs 3.7) -> False
    assert are_story_fingerprints_similar(fp_36, fp_37) is False

    # Version match (3.7 vs 3.7) with token overlap -> True
    assert are_story_fingerprints_similar(fp_37, fp_37_alt) is True

def test_is_story_semantic_duplicate():
    """Verify is_story_semantic_duplicate detects semantic duplicates in recent_stories and pending_stories."""
    from src.utils import is_story_semantic_duplicate, compute_story_fingerprint

    state = {
        "recent_stories": [
            {
                "url": "https://example.com/claude37",
                "title": "Anthropic Releases Claude 3.7 Sonnet",
                "fingerprint": compute_story_fingerprint("Anthropic Releases Claude 3.7 Sonnet")
            }
        ],
        "pending_stories": []
    }

    assert is_story_semantic_duplicate("Anthropic Announces New Claude 3.7 Sonnet Model", state) is True
    assert is_story_semantic_duplicate("OpenAI Launches GPT-4.5 Turbo", state) is False

def test_recent_stories_14day_retention_and_500_entry_capping():
    """Verify filter_and_update_pending_stories prunes recent_stories > 14 days old and caps arrays to 500 entries."""
    from src.utils import filter_and_update_pending_stories
    from datetime import datetime, timezone, timedelta

    now = datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc)
    old_date = (now - timedelta(days=15)).isoformat()
    recent_date = (now - timedelta(days=2)).isoformat()

    state = {
        "recent_stories": [
            {"url": "https://example.com/old", "title": "Old Story", "published_at": old_date},
            {"url": "https://example.com/fresh", "title": "Fresh Story", "published_at": recent_date}
        ],
        "pending_stories": [],
        "links": [f"https://example.com/link{i}" for i in range(600)]
    }

    filter_and_update_pending_stories(state, now_utc=now)

    assert len(state["recent_stories"]) == 1
    assert state["recent_stories"][0]["url"] == "https://example.com/fresh"
    assert len(state["links"]) == 500

def test_missing_local_state_with_valid_gist(mocker):
    """Verify that when local file is missing, valid Gist state is loaded cleanly."""
    from src.utils import load_seen_articles
    from src.settings import settings

    object.__setattr__(settings, "gist_id", "test_id")
    object.__setattr__(settings, "gist_token", "test_token")

    mocker.patch("src.utils._load_gist_state", return_value={"schema_version": 2, "revision": 10, "links": []})
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("src.utils.save_json_state")
    mocker.patch("os.replace")

    state = load_seen_articles()
    assert state["revision"] == 10

def test_missing_local_state_without_gist(mocker):
    """Verify that when local file and Gist are missing/unconfigured, default schema-v2 state is initialized."""
    from src.utils import load_seen_articles
    from src.settings import settings

    object.__setattr__(settings, "gist_id", "")
    object.__setattr__(settings, "gist_token", "")

    mocker.patch("os.path.exists", return_value=False)

    state = load_seen_articles()
    assert state["schema_version"] == 2
    assert state["revision"] == 1

def test_configured_unavailable_gist_aborts_reservation(mocker):
    """Verify that when Gist is configured but save fails during reservation, save_seen_articles returns False."""
    from src.utils import save_seen_articles
    from src.settings import settings

    object.__setattr__(settings, "is_dry_run", False)
    object.__setattr__(settings, "gist_id", "test_id")
    object.__setattr__(settings, "gist_token", "test_token")

    mocker.patch("src.utils._save_gist_state", return_value=False)

    ok, state = save_seen_articles({"revision": 5, "pending_stories": []}, is_reservation=True)
    assert ok is False

def test_successful_gist_sync_clears_unsynced_gist(mocker, tmp_path):
    """Verify that when Gist save succeeds, unsynced_gist is explicitly set to False."""
    import src.utils
    from src.utils import save_seen_articles
    from src.settings import settings

    test_file = str(tmp_path / "seen_articles.json")
    mocker.patch.object(src.utils, "SEEN_FILE_PATH", test_file)

    object.__setattr__(settings, "is_dry_run", False)
    object.__setattr__(settings, "gist_id", "test_id")
    object.__setattr__(settings, "gist_token", "test_token")

    uploaded_state = {}
    def capture_gist_payload(_filename, payload):
        uploaded_state.update(payload)
        return True
    mocker.patch("src.utils._save_gist_state", side_effect=capture_gist_payload)

    input_state = {"revision": 5, "unsynced_gist": True, "pending_stories": []}
    ok, state = save_seen_articles(input_state, is_reservation=False)

    assert ok is True
    assert state["unsynced_gist"] is False
    assert state["revision"] == 6
    assert uploaded_state["unsynced_gist"] is False

def test_no_tracked_runtime_state_files():
    """Verify that seen_articles.json is not tracked in the git repository index."""
    import subprocess
    res = subprocess.run(["git", "ls-files", "seen_articles.json"], capture_output=True, text=True)
    assert res.stdout.strip() == ""

def test_v3code_workspace_metadata_is_ignored():
    """Local .v3code workspace metadata must not pollute Git status."""
    import subprocess
    res = subprocess.run(
        ["git", "check-ignore", ".v3code/workspace-id"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
