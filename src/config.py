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
    "https://bair.berkeley.edu/blog/feed.xml",
    "https://ai.stanford.edu/blog/feed.xml",
    "https://blogs.nvidia.com/blog/category/deep-learning/feed/",
    "https://ai.meta.com/blog/rss/",
    "https://www.microsoft.com/en-us/research/blog/feed/",
    "https://cohere.com/blog/rss.xml",
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
BASE_HIDDEN_GEM = 25
BASE_TIER_2 = 15
SIGNAL_BOOST = 12
MOMENTUM_BOOST = 18
SYNERGY_BONUS = 15
DIVERSITY_PENALTY = 25
MAX_TOPIC_RECURRENCE = 3

TIER_1_SOURCES = ["openai.com", "deepmind.google", "anthropic.com", "huggingface.co", "mistral.ai"]
TIER_2_SOURCES = ["semianalysis.com", "interconnects.ai", "aheadofai.substack.com", "simonwillison.net"]
HIDDEN_GEM_SOURCES = ["arxiv.org", "thegradient.pub", "vkrakovna.wordpress.com", "magazine.sebastianraschka.com", "bair.berkeley.edu", "ai.stanford.edu", "blogs.nvidia.com"]

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

CURATOR_SYSTEM_INSTRUCTION = "Synthesize technical news concisely as a Technical Expert curator."
MENTOR_SYSTEM_INSTRUCTION = "Share technical insights as a Veteran Mentor."
SAGE_DESIGNER_INSTRUCTION = "Design professional minimalist isometric AI visual prompts."

def validate_config():
    """Ensures all required environment variables are present and valid."""
    is_dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    
    # Core essentials
    core_vars = ["BSKY_HANDLE", "BSKY_APP_PASSWORD", "GEMINI_KEY"]
    if os.getenv("IMAGE_PROVIDER", "nvidia") == "nvidia":
        core_vars.append("NVIDIA_KEY")
        
    for v in core_vars:
        current_val = os.getenv(v)
        if not current_val:
            if is_dry_run and v not in ["GEMINI_KEY", "NVIDIA_KEY"]:
                # Injects "mock_value" into os.environ[v]
                if not os.environ.get(v):
                    os.environ[v] = "mock_value"
                SafeLogger.info(f"DRY_RUN: Missing {v}, using mock credentials.")
            elif is_dry_run and v in ["GEMINI_KEY", "NVIDIA_KEY"]:
                # These are required for dry-run AI testing
                pass
            else:
                SafeLogger.error(f"Missing CORE variable: {v}")
                return False
            
    # Platform-specific checks
    if (not os.getenv("MASTODON_ACCESS_TOKEN") or not os.getenv("MASTODON_BASE_URL")) and (os.getenv("MASTODON_ACCESS_TOKEN") or os.getenv("MASTODON_BASE_URL")):
        if not is_dry_run:
            SafeLogger.error("Partial Mastodon configuration detected.")
            return False

    if (not os.getenv("THREADS_ACCESS_TOKEN") or not os.getenv("THREADS_USER_ID")) and (os.getenv("THREADS_ACCESS_TOKEN") or os.getenv("THREADS_USER_ID")):
        if not is_dry_run:
            SafeLogger.error("Partial Threads configuration detected.")
            return False
            
    if not validate_gemini_model_priority():
        return False

    return True

def _model_variants(model_id):
    normalized = model_id.strip()
    without_prefix = normalized.replace("models/", "", 1)
    with_prefix = f"models/{without_prefix}"
    return {normalized, without_prefix, with_prefix}

def validate_gemini_model_priority():
    global GEMINI_MODEL_PRIORITY, GEMINI_MODEL_ID
    try:
        from google import genai
        api_key = os.getenv("GEMINI_KEY") or GEMINI_API_KEY
        if os.getenv("CI") == "true":
            return True
        if not api_key:
            return False
        client = genai.Client(api_key=api_key)
        listed_models = list(client.models.list())
        
        supported_by_name = {}
        for model in listed_models:
            actions = getattr(model, "supported_actions", None) or getattr(model, "supported_generation_methods", None) or []
            if "generateContent" in actions:
                supported_by_name[model.name] = model.name
                supported_by_name[model.name.replace("models/", "", 1)] = model.name

        valid_models = []
        for configured_model in GEMINI_MODEL_PRIORITY:
            for variant in _model_variants(configured_model):
                if variant in supported_by_name:
                    valid_models.append(supported_by_name[variant])
                    break
        
        valid_models = list(dict.fromkeys(valid_models))
        if valid_models:
            GEMINI_MODEL_PRIORITY[:] = valid_models
            GEMINI_MODEL_ID = GEMINI_MODEL_PRIORITY[0]
            SafeLogger.info(f"Validated Gemini model priority: {GEMINI_MODEL_PRIORITY}")
            return True
        return False
    except Exception as e:
        SafeLogger.error(f"Gemini validation error: {e}")
        return False
