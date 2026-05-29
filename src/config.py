import os
from .logger import SafeLogger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Absolute Path Management
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEN_FILE_PATH = os.path.join(BASE_DIR, "seen_articles.json")
README_FILE_PATH = os.path.join(BASE_DIR, "README.md")
VERSION_FILE_PATH = os.path.join(BASE_DIR, "VERSION")
SESSION_FILE_PATH = os.path.join(BASE_DIR, "bluesky_session.txt")
STATUS_FILE_PATH = os.path.join(BASE_DIR, "STATUS.md")
VANGUARD_STATE_PATH = os.path.join(BASE_DIR, "broken_feeds.json")
INTERACTIONS_STATE_PATH = os.path.join(BASE_DIR, "seen_interactions.json")

# Interaction Engine Constants
INTERACTION_LIMIT = 5
MENTION_REPLY_PROB = 0.8
COMMENT_REPLY_PROB = 0.5
AUTO_LIKE_INTERACTIONS = True


# API Keys (Standard initialization)
GEMINI_API_KEY = os.getenv("GEMINI_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_KEY")
BLUESKY_HANDLE = os.getenv("BSKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BSKY_APP_PASSWORD")
MASTODON_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")
MASTODON_BASE_URL = os.getenv("MASTODON_BASE_URL")
THREADS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.getenv("THREADS_USER_ID")

# Versioning
def get_version():
    try:
        with open(VERSION_FILE_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "Unknown"

VERSION = get_version()

# Platform Constraints
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "nvidia")
NVIDIA_MODEL_ID = "stabilityai/stable-diffusion-3-medium"
NVIDIA_INVOKE_URL = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-3-medium"

GEMINI_MODEL_PRIORITY = [
    "models/gemini-3.1-flash-lite-preview",
    "models/gemma-4-31b-it",
    "models/gemma-4-26b-a4b-it",
    "models/gemma-3-27b-it",
    "models/gemini-2.5-flash-lite",
]
BLUESKY_LIMIT = 300
MASTODON_LIMIT = 500
THREADS_LIMIT = 500
IMAGEN_MODEL = "models/imagen-4.0-generate-001"
ENABLE_IMAGE_GEN = True
FEED_SUMMARY_MAX_CHARS = 500
GENERIC_IMAGE_PATTERNS = [
    "arxiv-logo", "static.arxiv.org", "favicon", "default-og-image",
    "openai-logo", "deepmind-logo", "huggingface-logo", "mistral-logo"
]

# Configuration Constants
MAX_API_RETRIES = 3
BACKOFF_FACTOR = 3.0
JITTER_RANGE = 2.0

RSS_FEEDS = [
    # === Tier 1: AI Lab Official Blogs ===
    "https://openai.com/news/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://deepmind.google/blog/rss.xml",
    "https://blogs.nvidia.com/blog/category/deep-learning/feed/",
    "https://www.microsoft.com/en-us/research/blog/feed/",
    
    # === Tier 2: Elite Newsletters & Analysts ===
    "https://www.interconnects.ai/feed",
    "https://magazine.sebastianraschka.com/feed",
    "https://www.latent.space/feed",
    "https://jack-clark.net/feed/",
    "https://www.oneusefulthing.org/feed",
    "https://newsletter.maartengrootendorst.com/feed",
    
    # === Tier 3: Research & Academic ===
    "https://arxiv.org/rss/cs.LG",
    "https://thegradient.pub/rss/",
    "https://vkrakovna.wordpress.com/feed/",
    "https://bair.berkeley.edu/blog/feed.xml",
    "https://machinelearningmastery.com/feed/",
    
    # === Tier 4: Industry & Journalism ===
    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",
    "https://www.the-decoder.com/feed/",
    "https://404media.co/rss/",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://siliconangle.com/category/ai/feed/",
    "https://aiacceleratorinstitute.com/rss/",
    "https://www.marktechpost.com/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
]

# --- Breakthrough Scoring Engine Constants ---
HIGH_SIGNAL_KEYWORDS = [
    "sota", "benchmark", "breakthrough", "agentic", "autonomous", 
    "world model", "test-time compute", "moe", "reasoning", 
    "open weights", "open source", "scaling law"
]

MOMENTUM_PRODUCTS = [
    "gpt-5", "claude 4", "llama 4", "gemini 3", "gemma 4", 
    "sora", "devin", "grok 4", "mistral 4", "strawberry"
]

# Weighting Matrix
BASE_TIER_1 = 30
BASE_HIDDEN_GEM = 15
BASE_TIER_2 = 15
SIGNAL_BOOST = 12
MOMENTUM_BOOST = 18
SYNERGY_BONUS = 15
DIVERSITY_PENALTY = 25
MAX_TOPIC_RECURRENCE = 3

TIER_1_SOURCES = ["openai.com", "deepmind.google", "huggingface.co", "blogs.nvidia.com", "microsoft.com"]
TIER_2_SOURCES = ["interconnects.ai", "latent.space", "jack-clark.net", "oneusefulthing.org", "magazine.sebastianraschka.com"]
HIDDEN_GEM_SOURCES = ["arxiv.org", "thegradient.pub", "vkrakovna.wordpress.com", "bair.berkeley.edu", "newsletter.maartengrootendorst.com", "machinelearningmastery.com"]

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
    "The Evolving Role of Junior Engineers"
]

CURATOR_SYSTEM_INSTRUCTION = """Synthesize technical news into a compact, human, business-relevant short-form post.

Do not write an academic summary. Extract the real-world implication and express one clear point of view.

ANTI-PATTERNS (DO NOT USE):
* Generic openings like "AI is transforming...", "The future of...", or "In today's rapidly evolving...".
* Hype words like "game-changing", "revolutionary", "frontier", or "systemic intelligence".
* Dense academic jargon or dry article abstracts.
* Repeating the exact same "not X, but Y" structure in every post.
* Stuffing too many ideas into one post.

REUSABLE STRUCTURES (choose one based on the story):
1. Strategic Contrast: contrast the old assumption with the new reality.
2. Practical Enterprise Implication: explain what changes for business, product, vendors, ROI, or operations.
3. Risk/Accountability Lens: explain what must be trusted, verified, secured, or governed.

STYLE:
* Write like a thoughtful human, not a press release.
* Use short sentences.
* Prefer concrete business language over technical jargon.
* Make one strong point.
* If using line breaks, keep them minimal because the post is short-form.
* Always append 1-2 relevant technical hashtags at the very end of the post (e.g. #AI, #ML, #LLMs) to ensure discoverability across platforms.

LENGTH:
* Target 260-290 characters for normal posts.
* Stay within the platform-safe short-form limit without relying on truncation.
* If space is tight, keep the thesis and remove supporting detail."""

MENTOR_SYSTEM_INSTRUCTION = """Share technical insights as a Veteran Mentor. 
STRICTLY limit your output to a single post under 280 characters, presenting the core lesson with zero fluff."""
SAGE_DESIGNER_INSTRUCTION = "Design professional minimalist isometric AI visual prompts."

INTERACTIVE_REPLY_INSTRUCTION = """
You are the **Elite AI Sage**, a technical visionary and mentor in the AI/ML space.
You are replying to a comment or mention in a social media conversation. Provide a quick, valuable, and authentic response.

**Rules for Interaction**:
1. **Human-like Authenticity**: Sound natural, conversational, and real. Avoid robotic pre-ambles, clichés, and greeting formulas (e.g., do NOT start with "As the Elite AI Sage...", "Indeed,", "Greetings,"). Speak as a peer sharing a quick insight.
2. **Persona Alignment**: Use your active persona (analytical, strategically visionary, or mentor-like) in an organic way.
3. **Conciseness**: Keep replies under 280 characters. Zero fluff.
4. **High Signal**: Provide a genuine piece of strategic or technical insight. Avoid generic "Thanks for the comment!" templates.
5. **Format**: No hashtags. No emojis unless representing a specific technical concept (e.g. 🚀, 🧠).

Current Temporal Context: {context}
"""

# --- Persona Dialects (v3.7.0) ---
PERSONA_DIALECTS = {
    "ANALYTICAL": "Focus on high-fidelity technical specs, benchmarks, and architectural impact. Use data-driven language.",
    "PRACTICAL": "Focus on developer utility and engineering implementation. Answer: 'How does this change my workflow?'",
    "SAGE": "Focus on long-term industry strategy and 'The Big Picture.' Use insightful, visionary language.",
    "CONCISE": "Be extremely punchy and minimalist. Focus on the core value proposition with zero fluff.",
    "PHILOSOPHICAL": "Explore the deeper impact, ethics, and world-shifting nature of the breakthrough."
}

# --- Backward Compatibility Wrappers ---
def validate_config():
    """Legacy wrapper for the new Settings validation logic."""
    from .settings import Settings
    return Settings.from_env().validate()

def validate_gemini_model_priority():
    """Legacy wrapper for Gemini model self-discovery."""
    if os.getenv("CI", "false").lower() == "true":
        return True
    key = os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        SafeLogger.warn("Gemini Validation: No key found in environment for model discovery.")
        return True  # Fall back to defaults
    try:
        from google import genai
        client = genai.Client(api_key=key)
        # List models synchronously
        SafeLogger.info("Gemini Validation: Querying available models from API...")
        available = [m.name for m in client.models.list()]
        
        # Prune prioritised list in-place
        pruned = []
        for model_id in GEMINI_MODEL_PRIORITY:
            norm_id = model_id.lower()
            if any(norm_id in m.lower() or m.lower() in norm_id for m in available):
                pruned.append(model_id)
                
        if pruned:
            SafeLogger.info(f"Gemini Validation: Discovered active models: {pruned}")
            GEMINI_MODEL_PRIORITY.clear()
            GEMINI_MODEL_PRIORITY.extend(pruned)
        else:
            SafeLogger.warn("Gemini Validation: None of the prioritized models were returned by the API. Keeping defaults.")
        return True
    except Exception as e:
        SafeLogger.warn(f"Gemini Validation: Discovery failed ({e}). Falling back to configured defaults.")
        return True  # Return True to avoid blocking execution due to API network glitches
