import pytest
import ipaddress
from unittest.mock import AsyncMock, MagicMock
from src.utils import _is_public_ip, truncate_bytes, get_image_mime, compress_image

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
