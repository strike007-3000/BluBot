from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Any
from datetime import datetime

class MediaSource(str, Enum):
    OPENGRAPH = "opengraph"
    GENERATED = "generated"

@dataclass(frozen=True)
class MediaAsset:
    source: MediaSource
    image_bytes: Optional[bytes] = None
    public_url: Optional[str] = None
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    alt_text: Optional[str] = None
    attribution_url: Optional[str] = None

@dataclass(frozen=True)
class ImageValidationResult:
    valid: bool
    reason: Optional[str] = None
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    final_url: Optional[str] = None

@dataclass(frozen=True)
class Article:
    """Represents a single news item from an RSS feed."""
    title: str
    link: str
    summary: str
    published: str
    source: str
    score: Optional[int] = 0
    topic: Optional[str] = "General"
    _score_debug: Optional[Any] = None
    consensus_synergy: Optional[bool] = False
    source_url: Optional[str] = None
    source_id: Optional[str] = None
    cluster_id: Optional[str] = None
    supporting_sources: Optional[List[str]] = None
    supporting_links: Optional[List[str]] = None

@dataclass(frozen=True)
class CurationResult:
    """The result of the news fetching and scoring phase."""
    top_articles: List[Article]
    seen_links: List[str]
    recent_topics: List[str]
    last_dialect: Optional[str] = None
    session_name: str = "General Intelligence"
    timestamp: datetime = field(default_factory=datetime.now)
    recent_categories: List[str] = field(default_factory=list)
    recent_styles: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class PlatformDrafts:
    """Holds tailored draft content for each broadcast target."""
    bluesky: str
    threads: str
    mastodon: str

    @classmethod
    def from_single(cls, text: str) -> "PlatformDrafts":
        """Factory for legacy or fallback single-text posts."""
        safe_text = text or ""
        return cls(bluesky=safe_text, threads=safe_text, mastodon=safe_text)

    def get(self, platform: str, fallback: Optional[str] = None) -> str:
        key = platform.lower()
        if key == "bluesky":
            return self.bluesky or fallback or ""
        elif key == "threads":
            return self.threads or fallback or ""
        elif key == "mastodon":
            return self.mastodon or fallback or ""
        return fallback or ""

    def with_update(self, platform: str, new_text: str) -> "PlatformDrafts":
        """Returns a new immutable instance with the specified platform updated."""
        key = platform.lower()
        return PlatformDrafts(
            bluesky=new_text if key == "bluesky" else self.bluesky,
            threads=new_text if key == "threads" else self.threads,
            mastodon=new_text if key == "mastodon" else self.mastodon,
        )

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return self.bluesky == other
        if isinstance(other, PlatformDrafts):
            return (self.bluesky, self.threads, self.mastodon) == (other.bluesky, other.threads, other.mastodon)
        return False

    def __str__(self) -> str:
        return self.bluesky

@dataclass(frozen=True)
class SynthesisResult:
    """The result of the AI summarization and persona synthesis phase."""
    content: str
    lead_link: Optional[str]
    topic: str
    is_failover: bool = False
    media: Optional[MediaAsset] = None
    writing_style: Optional[str] = None
    drafts: Optional[PlatformDrafts] = None

    def get_platform_content(self, platform: str) -> str:
        """Retrieves platform-tailored content, falling back to .content."""
        if self.drafts:
            val = self.drafts.get(platform)
            if val and val.strip():
                return val
        return self.content

@dataclass(frozen=True)
class BroadcastResult:
    """Status details per platform after broadcasting."""
    platform: str
    success: bool
    error: Optional[str] = None
    post_id: Optional[str] = None

@dataclass(frozen=True)
class InteractionNote:
    """Metadata for a social mention or reply."""
    platform: str
    id: str
    author: str
    text: str
    timestamp: str
    uri: Optional[str] = None  # Bluesky specific
    cid: Optional[str] = None  # Bluesky specific
    root_uri: Optional[str] = None
    root_cid: Optional[str] = None

@dataclass(frozen=True)
class InteractionResult:
    """Tracking the result of an automated reply session."""
    processed_count: int
    replied_ids: List[str]
    errors: List[str]
