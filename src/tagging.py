"""Source-account tags for Bluesky and Mastodon drafts.

Applied only on the Telegram-approval path, where the user can toggle the tag off.
"""
from typing import Optional

from src.models import PlatformDrafts
from src.settings import settings

# Hand-verified accounts only. A missing platform means no tag on that platform.
SOURCE_HANDLES = {
    "anthropic_news": {"bluesky": "anthropic.com"},
    "simon_willison": {"bluesky": "simonwillison.net", "mastodon": "simon@simonwillison.net"},
    "interconnects_ai": {"bluesky": "natolambert.bsky.social"},
    "one_useful_thing": {"bluesky": "emollick.bsky.social"},
    "pytorch_releases": {"bluesky": "pytorch.org"},
    "microsoft_research": {"bluesky": "msftresearch.bsky.social"},
}
_PLATFORMS = ("bluesky", "mastodon")


def _suffix(platform: str, source_id: Optional[str]) -> Optional[str]:
    handle = SOURCE_HANDLES.get(source_id or "", {}).get(platform)
    return f"\n\ncc @{handle}" if handle else None


def _budget(platform: str) -> int:
    # Same safety buffers the broadcaster uses.
    return settings.bluesky_limit - 10 if platform == "bluesky" else settings.mastodon_limit - 15


def tag_state(drafts: PlatformDrafts, source_id: Optional[str]) -> Optional[bool]:
    """None: source has no tag. True/False: tag currently present/absent in the drafts."""
    pairs = [(p, _suffix(p, source_id)) for p in _PLATFORMS]
    pairs = [(p, s) for p, s in pairs if s]
    if not pairs:
        return None
    return any(drafts.get(p).endswith(s) for p, s in pairs)


def apply_tags(drafts: PlatformDrafts, source_id: Optional[str]) -> PlatformDrafts:
    for p in _PLATFORMS:
        s, text = _suffix(p, source_id), drafts.get(p)
        if s and not text.endswith(s) and len(text) + len(s) <= _budget(p):
            drafts = drafts.with_update(p, text + s)
    return drafts


def strip_tags(drafts: PlatformDrafts, source_id: Optional[str]) -> PlatformDrafts:
    for p in _PLATFORMS:
        s, text = _suffix(p, source_id), drafts.get(p)
        if s and text.endswith(s):
            drafts = drafts.with_update(p, text[: -len(s)])
    return drafts
