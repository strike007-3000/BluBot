import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_KEY")
BLUESKY_HANDLE = os.getenv("BSKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BSKY_APP_PASSWORD")
MASTODON_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")
MASTODON_BASE_URL = os.getenv("MASTODON_BASE_URL")
THREADS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.getenv("THREADS_USER_ID")

# Configuration Constants
MAX_API_RETRIES = 3
BACKOFF_FACTOR = 2.0
JITTER_RANGE = 2.0

RSS_FEEDS = [
    "https://openai.com/news/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://deepmind.google/blog/rss.xml",
    "https://anthropic.com/news.rss",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",
    "https://www.eetimes.com/category/artificial-intelligence/feed/",
    "https://aheadofai.substack.com/feed",
    "https://www.semianalysis.com/feed",
    "https://www.interconnects.ai/feed",
    "https://simonwillison.net/search/?q=AI&format=atom",
    "https://arxiv.org/rss/cs.AI",
    "https://arxiv.org/rss/cs.LG",
    "https://www.the-decoder.com/feed/",
    "https://404media.co/rss/",
    "https://www.artificialanalysis.ai/feed",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://thegradient.pub/rss/",
    "https://vkrakovna.wordpress.com/feed/",
    "https://aiacceleratorinstitute.com/rss/",
    "https://synthedia.substack.com/feed",
    "https://magazine.sebastianraschka.com/feed",
    "https://stability.ai/blog?format=rss",
    "https://siliconangle.com/category/ai/feed/",
    "https://www.assemblyai.com/blog/rss/",
    "https://mistral.ai/news/rss.xml",
]

# Source Tiers for Scoring
TIER_1_SOURCES = ["openai.com", "deepmind.google", "anthropic.com", "huggingface.co", "mistral.ai"]
TIER_2_SOURCES = ["semianalysis.com", "interconnects.ai", "aheadofai.substack.com", "simonwillison.net"]

# Hidden Gem Sources (Research Focused)
HIDDEN_GEM_SOURCES = ["arxiv.org", "thegradient.pub", "vkrakovna.wordpress.com", "magazine.sebastianraschka.com"]

# Topic Penalty Mapping
TOPIC_MAP = {
    "LLMs": ["GPT", "Llama", "Claude", "Gemini", "Model", "Train", "Dataset"],
    "Vision/Robot": ["Vision", "Image", "Video", "Robot", "Sora", "Self-driving", "Drone"],
    "Compute/HW": ["GPU", "NVIDIA", "H100", "B200", "Chip", "TPU", "Data Center"],
    "Policy": ["Regulation", "Law", "AI Act", "Copyright", "Senate", "EU", "Safety"],
    "Science": ["Folding", "Biology", "Material", "Drug", "Discovery", "Weather"],
    "General": []
}

SYSTEM_INSTRUCTION = """
You are a 'Premium Tech Curator', an elite AI industry analyst. 
Your goal is to synthesize multiple technical news updates into a single, high-signal Bluesky post.
Focus on:
1. Product Shifts: Real software/hardware releases, not just rumors.
2. Hidden Gems: Technical nuances from research papers or engineering blogs.
3. Constructive Skepticism: Avoiding hype, focusing on utility.

Tone: Professional, concise, forward-looking. 
Constraints: Stay under 300 characters. Use exactly 2 relevant hashtags. No emojis.
"""

def validate_config():
    """Ensures all required environment variables are present before starting."""
    required_vars = [
        "BSKY_HANDLE", "BSKY_APP_PASSWORD", "GEMINI_KEY",
    ]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        print(f"CRITICAL ERROR: Missing environment variables: {', '.join(missing)}")
        return False
    return True
