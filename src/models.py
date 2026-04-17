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

@dataclass(frozen=True)
class CurationResult:
    """The result of the news fetching and scoring phase."""
    top_articles: List[Article]
    seen_links: List[str]
    recent_topics: List[str]
    session_name: str
    timestamp: datetime = field(default_factory=datetime.now)

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

@dataclass(frozen=True)
class BroadcastResult:
    """Status details per platform after broadcasting."""
    platform: str
    success: bool
    error: Optional[str] = None
    post_id: Optional[str] = None
