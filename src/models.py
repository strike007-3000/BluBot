from dataclasses import dataclass, field
from typing import List, Optional, Any
from datetime import datetime

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
class SynthesisResult:
    """The result of the AI summarization and persona synthesis phase."""
    content: str
    lead_link: Optional[str]
    topic: str
    is_failover: bool = False
    visual_prompt: Optional[str] = None
    image_data: Optional[bytes] = None
    image_url: Optional[str] = None
    image_alt_text: Optional[str] = None
    writing_style: Optional[str] = None

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
