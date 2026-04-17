import pytest
from datetime import datetime, timezone
from src.models import (
    Article, CurationResult, SynthesisResult, BroadcastResult,
    InteractionNote, InteractionResult
)

def test_article_validation():
    """Validates the core Article dataclass."""
    article = Article(
        title="Test Build",
        summary="A summary of the breakthrough",
        link="https://openai.com/1",
        published=datetime.now(timezone.utc).isoformat(),
        source="OpenAI",
        score=10.5
    )
    assert article.title == "Test Build"
    assert article.score == 10.5

def test_interaction_note_structure():
    """Validates the new Interaction Engine note structure."""
    note = InteractionNote(
        platform="bluesky",
        id="at://did:123/app.bsky.feed.post/1",
        author="sage.bsky.social",
        text="Mention text",
        timestamp="2026-04-18T10:00:00Z",
        uri="at://did:123/app.bsky.feed.post/1",
        cid="cid123",
        root_uri="at://did:123/app.bsky.feed.post/0",
        root_cid="cid0"
    )
    assert note.platform == "bluesky"
    assert note.root_uri == "at://did:123/app.bsky.feed.post/0"

def test_interaction_result_aggregation():
    """Validates the interaction processing summary structure."""
    res = InteractionResult(
        processed_count=5,
        replied_ids=["id1", "id2"],
        errors=[]
    )
    assert len(res.replied_ids) == 2
    assert res.processed_count == 5

def test_curation_result_typing():
    """Ensures curation results maintain session and link tracking."""
    article = Article("Title", "Sum", "Link", "Date", "Src", 1.0)
    curation = CurationResult(
        top_articles=[article],
        seen_links=["Link"],
        recent_topics=["AI"],
        session_name="Morning Intelligence",
        last_dialect="Sage"
    )
    assert curation.session_name == "Morning Intelligence"
    assert "Link" in curation.seen_links
