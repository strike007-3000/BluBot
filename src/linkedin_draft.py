"""Source fetch, draft generation and verification for the LinkedIn weekly draft."""
import json
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from bs4 import BeautifulSoup

from src.curator import strip_markdown
from src.linkedin_llm import gemini_generate
from src.linkedin_prompts import LINKEDIN_SYSTEM_INSTRUCTION
from src.logger import SafeLogger
from src.utils import get_with_safe_redirects

TAKE_MAX_CHARS = 1000
SOURCE_TEXT_MAX_CHARS = 6000
MAX_RETRIES = 2

_URL_RE = re.compile(r"https?://\S+")
_HASHTAG_RE = re.compile(r"#\w+")
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*%?")


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


async def fetch_source_text(client, url: str) -> Optional[str]:
    try:
        resp = await get_with_safe_redirects(client, url, timeout=10)
        if not resp or resp.status_code != 200:
            return None
        if "html" not in resp.headers.get("content-type", "").lower():
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.get_text() if soup.title else ""
        abstract = soup.select_one("blockquote.abstract")
        if abstract:
            parts = [title, abstract.get_text()]
        else:
            meta = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
            parts = [title, meta.get("content", "") if meta else ""] + [p.get_text() for p in soup.find_all("p")]
        text = _collapse(" ".join(parts))[:SOURCE_TEXT_MAX_CHARS]
        return text or None
    except Exception as e:
        SafeLogger.warn(f"LinkedIn source fetch failed for {url}: {e}")
        return None


def check_draft_rules(draft: str) -> List[str]:
    failures = []
    low = draft.lower()
    if "bluesky" in low or "bsky" in low:
        failures.append("Mentions Bluesky; remove any reference to it.")
    if "—" in draft:
        failures.append("Contains an em dash; rewrite without it.")
    body = _HASHTAG_RE.sub(" ", _URL_RE.sub(" ", draft))
    words = len(body.split())
    if not 80 <= words <= 130:
        failures.append(f"Word count is {words}; it must be 80-130 words excluding hashtags and URL.")
    tags = len(_HASHTAG_RE.findall(draft))
    if not 3 <= tags <= 4:
        failures.append(f"Has {tags} hashtags; it must have 3-4.")
    return failures


async def generate_draft(genai_client, entry: dict, source_text: Optional[str], take: Optional[str],
                         fix_notes: Sequence[str] = ()) -> Optional[str]:
    lines = [f"Article title: {entry.get('title', '')}", f"Article URL: {entry.get('url', '')}"]
    if source_text:
        lines.append(f"Source text (fetched from the original article):\n{source_text}")
    else:
        lines.append("Source text: unavailable. Rely only on the title and avoid specific figures.")
    if take:
        lines.append(f"Owner's personal input (preserve its meaning, do not exaggerate):\n{take[:TAKE_MAX_CHARS]}")
    if fix_notes:
        lines.append("Fix these problems from the previous attempt:\n" + "\n".join(f"- {n}" for n in fix_notes))
    lines.append("Write the LinkedIn post now. Return only the post followed by the source URL.")
    text = await gemini_generate(genai_client, "\n\n".join(lines), LINKEDIN_SYSTEM_INSTRUCTION)
    return strip_markdown(text) if text else None


@dataclass(frozen=True)
class DraftResult:
    text: Optional[str]
    verified: bool
    flags: Tuple[str, ...] = ()
    error: Optional[str] = None


def unsupported_numbers(draft: str, source_text: str) -> List[str]:
    body = _HASHTAG_RE.sub(" ", _URL_RE.sub(" ", draft))
    bad = []
    for n in _NUM_RE.findall(body):
        bare = n.rstrip("%")
        if not re.search(r"(?<![\d.,])" + re.escape(bare) + r"(?![\d])", source_text) and n not in bad:
            bad.append(n)
    return bad


async def verify_claims(genai_client, draft: str, source_text: str) -> Optional[List[str]]:
    prompt = (
        "Compare the LinkedIn draft with the source text. List only material errors: statistic misattribution, "
        "a baseline or measurement changed, an experimental finding stated as general or production fact, "
        "or names, organizations or capabilities not supported by the source.\n"
        'Return JSON: {"errors": ["..."]} with an empty list if none.\n\n'
        f"SOURCE:\n{source_text}\n\nDRAFT:\n{draft}"
    )
    raw = await gemini_generate(genai_client, prompt, "You are a strict fact checker.", json_mode=True)
    if not raw:
        return None
    try:
        errors = json.loads(raw)["errors"]
        return [str(e) for e in errors] if isinstance(errors, list) else None
    except (ValueError, KeyError, TypeError):
        return None


async def build_verified_draft(genai_client, client, entry: dict, take: Optional[str]) -> DraftResult:
    source = await fetch_source_text(client, entry.get("url", ""))
    if source is None:
        text = await generate_draft(genai_client, entry, None, take)
        if not text:
            return DraftResult(None, False, (), "Draft generation failed.")
        flags = ["UNVERIFIED: source could not be fetched"] + check_draft_rules(text)
        return DraftResult(text, False, tuple(flags), None)

    notes: List[str] = []
    for _ in range(1 + MAX_RETRIES):
        text = await generate_draft(genai_client, entry, source, take, notes)
        if not text:
            notes = ["Draft generation failed."]
            continue
        errors = check_draft_rules(text)
        errors += [f"The number {n} does not appear in the source; remove or correct it." for n in unsupported_numbers(text, source)]
        claims = await verify_claims(genai_client, text, source)
        errors += claims or []
        if not errors:
            if claims is None:
                return DraftResult(text, False, ("UNVERIFIED: claim check unavailable",), None)
            return DraftResult(text, True, (), None)
        notes = errors
    return DraftResult(None, False, (), "Draft failed verification: " + "; ".join(notes))
