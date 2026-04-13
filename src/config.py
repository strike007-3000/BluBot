import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Absolute Path Management
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEN_FILE_PATH = os.path.join(BASE_DIR, "seen_articles.json")
README_FILE_PATH = os.path.join(BASE_DIR, "README.md")

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_KEY")
BLUESKY_HANDLE = os.getenv("BSKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BSKY_APP_PASSWORD")
MASTODON_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")
MASTODON_BASE_URL = os.getenv("MASTODON_BASE_URL")
THREADS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.getenv("THREADS_USER_ID")

# Platform Constraints
GEMINI_MODEL_ID = "gemini-3.1-flash-lite-preview"
BLUESKY_LIMIT = 300
MASTODON_LIMIT = 500
THREADS_LIMIT = 500

# Configuration Constants
MAX_API_RETRIES = 3
BACKOFF_FACTOR = 3.0  # Increased from 2.0 per expert advice
JITTER_RANGE = 2.0

RSS_FEEDS = [
    "https://openai.com/news/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://deepmind.google/blog/rss.xml",
    "https://anthropic.com/news.rss",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",
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
    "Strategy": ["Enterprise", "ROI", "Budget", "Deployment", "Vendor", "Strategy"],
    "General": []
}

SECONDARY_TOPICS = [
    "Technical Debt in the Age of Co-Pilots",
    "The Economics of Model Distillation",
    "Becoming a T-Shaped AI Engineer",
    "Safe System-Level Prompt Injection Defense",
    "Agentic Autonomy vs. Human-in-the-Loop Design",
    "Sustainable AI: The Energy Cost of Inference",
    "Managing Cognitive Load when Coding with LLMs",
    "The Evolving Role of Junior Engineers",
    "From Prompt Engineering to Cognitive Architecture",
    "The Future of Multi-Modal Interaction",
    "Balancing Speed vs. Model Safety in Production",
    "The 'Small Language Model' Revolution",
    "AI Product Strategy: First-Mover vs. Fast-Follower",
    "Technical Documentation as a Model-Training Asset",
    "The Death of the 'Code Monkey' and the Rise of the Architect"
]

CURATOR_SYSTEM_INSTRUCTION = """
You are a 'Premium Tech Curator', an elite AI industry analyst. 
Your goal is to synthesize multiple technical news updates into a single, high-signal Bluesky post.
Focus on:
1. Product Shifts: Real software/hardware releases, not just rumors.
2. Hidden Gems: Technical nuances from research papers or engineering blogs.
3. Constructive Skepticism: Avoiding hype, focusing on utility.

Tone: Professional, concise, forward-looking. 
Constraints: No emojis. Stay under 300 characters. Use exactly 2 relevant hashtags.
"""

MENTOR_SYSTEM_INSTRUCTION = """
You are the 'Senior AI Mentor', a veteran technical leader and strategist.
Your goal is to provide deep, philosophical, or career-oriented wisdom about the AI industry.
Focus on:
1. Long-term Strategy: Avoiding flavor-of-the-week trends for sustainable engineering.
2. Technical Depth: Explaining *why* a concept matters for the architecture of tomorrow.
3. Professional Growth: Guiding other engineers and leaders through the AI shift.

Tone: Wise, authoritative, yet encouraging.
Constraints: No emojis. Stay under 300 characters. Use exactly 2 relevant hashtags.
"""

def validate_config():
    """Ensures all required environment variables are present and valid."""
    # Core essentials
    core_vars = ["BSKY_HANDLE", "BSKY_APP_PASSWORD", "GEMINI_KEY"]
    for v in core_vars:
        if not os.getenv(v):
            print(f"CRITICAL ERROR: Missing CORE variable: {v}")
            return False
            
    # Platform-specific "Fail Fast" validation
    # Mastodon
    if (MASTODON_TOKEN or MASTODON_BASE_URL) and not (MASTODON_TOKEN and MASTODON_BASE_URL):
        print("CRITICAL ERROR: Partial Mastodon configuration detected.")
        return False
        
    # Threads
    if (THREADS_TOKEN or THREADS_USER_ID) and not (THREADS_TOKEN and THREADS_USER_ID):
        print("CRITICAL ERROR: Partial Threads configuration detected.")
        return False
        
    return True
