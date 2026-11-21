"""Fetch every RSS feed (plus replacement candidates) with two User-Agents and print a status table.

Read-only: posts nothing, writes no state. Run from GitHub Actions to see what its IPs can reach.
"""
import asyncio
import httpx
from src.config import SOURCE_REGISTRY

UAS = {
    "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "honest": "BluBot/3 (+https://github.com/strike007-3000/BluBot)",
}
CANDIDATES = [
    ("CANDIDATE The New Stack AI", "https://thenewstack.io/category/ai/feed/"),
    ("CANDIDATE Import AI", "https://importai.substack.com/feed"),
    ("CANDIDATE Understanding AI", "https://www.understandingai.org/feed"),
    ("CANDIDATE Exponential View", "https://www.exponentialview.co/feed"),
    ("CANDIDATE Unite.AI", "https://www.unite.ai/feed/"),
    ("CANDIDATE Lilian Weng", "https://lilianweng.github.io/index.xml"),
    ("CANDIDATE AI Now Institute", "https://ainowinstitute.org/feed"),
    ("CANDIDATE Platformer", "https://www.platformer.news/rss/"),
]


async def probe(client: httpx.AsyncClient, url: str, ua: str) -> str:
    try:
        r = await client.get(url, headers={"User-Agent": ua})
    except Exception as e:
        return type(e).__name__
    items = r.text.count("<item") + r.text.count("<entry")
    return f"{r.status_code}/{items}"


async def main() -> None:
    feeds = [(s["name"], s["url"]) for s in SOURCE_REGISTRY if s.get("kind", "rss") == "rss"] + CANDIDATES
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        async def row(name, url):
            return name, *[await probe(client, url, ua) for ua in UAS.values()]
        rows = await asyncio.gather(*[row(n, u) for n, u in feeds])
    print(f"{'feed':45} {'chrome':12} {'honest':12}  (status/items)")
    for name, chrome, honest in rows:
        flag = "" if chrome.startswith("200/") and honest.startswith("200/") else "  <-- check"
        print(f"{name[:45]:45} {chrome:12} {honest:12}{flag}")


if __name__ == "__main__":
    asyncio.run(main())
