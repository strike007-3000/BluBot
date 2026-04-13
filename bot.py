import asyncio
import os
from datetime import datetime, timezone

# Modular Imports
from src.config import validate_config
from src.utils import load_seen_articles, save_seen_articles
from src.curator import (
    fetch_news, summarize_news, generate_mentor_insight, get_temporal_context
)
from src.broadcaster import post_to_bluesky, post_to_mastodon, post_to_threads

async def update_live_status(session_name):
    """Automatically update the README dashboard status."""
    try:
        readme_path = "README.md"
        if not os.path.exists(readme_path):
            return

        with open(readme_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        icon = "🚀" if "Morning" in session_name else "🔍"
        
        new_lines = []
        for line in lines:
            if "| **Broadcaster** |" in line:
                new_lines.append(f"| **Broadcaster** | Operational | {today} | {icon} {session_name} |\n")
            elif "| **Signal Strength** |" in line:
                new_lines.append(f"| **Signal Strength** | Elite (Parallel) | -- | -- |\n")
            else:
                new_lines.append(line)

        with open(readme_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print("Updated README Live Status Dashboard.", flush=True)
    except Exception as e:
        print(f"Failed to update README status: {e}", flush=True)

async def main():
    if not validate_config():
        return

    context = get_temporal_context()
    now = datetime.now(timezone.utc)

    # Weekend Skip logic
    if now.weekday() >= 5 and now.hour >= 12:
        print(f"Skipping scheduled post: It's {context['day']} afternoon. Bot is resting.", flush=True)
        return

    seen_data = load_seen_articles()
    news = await fetch_news(seen_data["links"], seen_data["recent_topics"])

    # 4-State Persona Matrix Decision
    summary, lead_link, topic = None, None, "General"
    session = context['session']
    news_count = len(news)
    
    if news_count > 3:
        # We have enough news for a synthesis
        # Morning => Curator, Afternoon => Senior Analyst (Mentor Mode)
        mode = "Mentor" if "Afternoon" in session else "Curator"
        summary, lead_link, topic = await summarize_news(news, context, mode=mode)
    else:
        # Insufficient news => Strategic Fallback
        # Morning => Strategist, Afternoon => Mentor
        mode_label = "Strategist" if "Morning" in session else "Mentor"
        print(f"Low news volume ({news_count}). Switching to {mode_label} Mode.", flush=True)
        summary, lead_link, topic = await generate_mentor_insight(context)

    if summary:
        print(f"Broadcasting in {topic} mode (Source: {lead_link or 'Fallback'})...", flush=True)
        await asyncio.gather(
            post_to_bluesky(summary, lead_link),
            post_to_mastodon(summary),
            post_to_threads(summary)
        )

        # Persistence
        if news:
            new_links = [item['link'] for item in news[:10]]
            seen_data["links"].extend(new_links)
        
        if topic and topic != "General":
            seen_data["recent_topics"].append(topic)
        save_seen_articles(seen_data)
        
        # Dashboard Update
        await update_live_status(f"{session} ({topic})")
    else:
        print("Quality validation failed or error occurred. Post aborted for safety.", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
