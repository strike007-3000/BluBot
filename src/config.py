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
PENDING_TOPIC_FILE_PATH = os.path.join(BASE_DIR, "pending_topic.json")

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
# Platform Constraints
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "huggingface")
POLLINATIONS_API_URL = "https://gen.pollinations.ai/image/"
HF_IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"
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
IMAGEN_MODEL = "models/imagen-3.0-generate-002"
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

# --- SOURCE REGISTRY WITH STABLE IDs (Refined v3.8.0) ---
SOURCE_REGISTRY = [
    # Category list: research_lab, enterprise, practitioner, open_source, infrastructure, business, journalism, academic, critical
    # Quality list: official, community, academic, journalism, opinion
    
    # === Tier 1: AI Research Labs (base 30) ===
    {"id": "openai_news",         "name": "OpenAI News",         "url": "https://openai.com/news/rss.xml",                                    "category": "research_lab",   "quality": "official",   "base_score": 30},
    {"id": "deepmind_blog",       "name": "DeepMind Blog",       "url": "https://deepmind.google/blog/rss.xml",                               "category": "research_lab",   "quality": "official",   "base_score": 30},
    {"id": "huggingface_blog",    "name": "HuggingFace Blog",    "url": "https://huggingface.co/blog/feed.xml",                               "category": "research_lab",   "quality": "official",   "base_score": 30},

    # === Tier 2: Enterprise AI Blogs (base 25-27) ===
    {"id": "microsoft_research",  "name": "Microsoft Research",  "url": "https://www.microsoft.com/en-us/research/blog/feed/",                "category": "enterprise",     "quality": "official",   "base_score": 25},
    {"id": "aws_ml_blog",         "name": "AWS ML Blog",         "url": "https://aws.amazon.com/blogs/machine-learning/feed/",                "category": "enterprise",     "quality": "official",   "base_score": 25},
    {"id": "nvidia_dl_blog",      "name": "NVIDIA Deep Learning","url": "https://blogs.nvidia.com/blog/category/deep-learning/feed/",         "category": "enterprise",     "quality": "official",   "base_score": 27},

    # === Tier 3: Practitioner / Developer Ecosystem (base 20) ===
    {"id": "simon_willison",      "name": "Simon Willison",      "url": "https://simonwillison.net/atom/everything/",                         "category": "practitioner",   "quality": "opinion",    "base_score": 20},
    {"id": "interconnects_ai",    "name": "Interconnects.ai",    "url": "https://www.interconnects.ai/feed",                                  "category": "practitioner",   "quality": "opinion",    "base_score": 20},
    {"id": "latent_space",        "name": "Latent Space",        "url": "https://www.latent.space/feed",                                      "category": "practitioner",   "quality": "community",  "base_score": 20},
    {"id": "one_useful_thing",    "name": "One Useful Thing",    "url": "https://www.oneusefulthing.org/feed",                                 "category": "practitioner",   "quality": "opinion",    "base_score": 20},
    {"id": "maarten_grootendorst","name": "Maarten Grootendorst","url": "https://newsletter.maartengrootendorst.com/feed",                    "category": "practitioner",   "quality": "opinion",    "base_score": 20},
    {"id": "sebastian_raschka",   "name": "Sebastian Raschka",   "url": "https://magazine.sebastianraschka.com/feed",                         "category": "practitioner",   "quality": "opinion",    "base_score": 20},
    {"id": "jack_clark",          "name": "Jack Clark",          "url": "https://jack-clark.net/feed/",                                       "category": "practitioner",   "quality": "opinion",    "base_score": 20},

    # === Tier 4: Open-Source Ecosystem (base 18) ===
    # None currently active; PyTorch 403s, others 404. Relies on Tiers 1-3 practitioners for OS.

    # === Tier 5: Infrastructure / Business Analysis (base 15) ===
    {"id": "semianalysis",        "name": "SemiAnalysis",        "url": "https://semianalysis.com/feed/",                                     "category": "infrastructure", "quality": "opinion",    "base_score": 15},
    {"id": "together_ai",         "name": "Together AI Blog",    "url": "https://www.together.ai/blog/rss.xml",                               "category": "infrastructure", "quality": "official",   "base_score": 15},
    {"id": "sequoia_cap",         "name": "Sequoia Capital",     "url": "https://www.sequoiacap.com/feed/",                                   "category": "business",       "quality": "opinion",    "base_score": 15},
    {"id": "cb_insights_ai",      "name": "CB Insights AI",      "url": "https://www.cbinsights.com/research/feed/",                          "category": "business",       "quality": "journalism", "base_score": 15},

    # === Tier 6: Journalism / Industry / General (base 12) ===
    {"id": "the_verge_ai",        "name": "The Verge AI",        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",  "category": "journalism",     "quality": "journalism", "base_score": 12},
    {"id": "mit_tech_review",     "name": "MIT Tech Review AI",  "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/","category": "journalism",   "quality": "journalism", "base_score": 12},
    {"id": "ieee_spectrum",       "name": "IEEE Spectrum AI",    "url": "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",  "category": "journalism",     "quality": "journalism", "base_score": 12},
    {"id": "the_decoder",         "name": "The Decoder",         "url": "https://www.the-decoder.com/feed/",                                  "category": "journalism",     "quality": "journalism", "base_score": 12},
    {"id": "wired_ai",            "name": "Wired AI",            "url": "https://www.wired.com/feed/tag/ai/latest/rss",                       "category": "journalism",     "quality": "journalism", "base_score": 12},
    {"id": "venturebeat_ai",      "name": "VentureBeat AI",      "url": "https://venturebeat.com/category/ai/feed/",                          "category": "journalism",     "quality": "journalism", "base_score": 12},
    {"id": "techcrunch_ai",       "name": "TechCrunch AI",       "url": "https://techcrunch.com/category/artificial-intelligence/feed/",      "category": "journalism",     "quality": "journalism", "base_score": 12},
    {"id": "four_hundred_four",   "name": "404 Media",           "url": "https://404media.co/rss/",                                           "category": "journalism",     "quality": "journalism", "base_score": 12},
    {"id": "silicon_angle",       "name": "Silicon Angle AI",    "url": "https://siliconangle.com/category/ai/feed/",                         "category": "journalism",     "quality": "journalism", "base_score": 12},
    {"id": "the_sequence",        "name": "The Sequence",        "url": "https://thesequence.substack.com/feed",                              "category": "journalism",     "quality": "journalism", "base_score": 12},
    {"id": "marktechpost",        "name": "MarktechPost",        "url": "https://www.marktechpost.com/feed/",                                  "category": "journalism",     "quality": "journalism", "base_score": 12},
    {"id": "ai_accelerator_inst", "name": "AI Accelerator Inst", "url": "https://aiacceleratorinstitute.com/rss/",                            "category": "journalism",     "quality": "journalism", "base_score": 12},

    # === Tier 7: Academic (base 10) ===
    {"id": "arxiv_cslg",          "name": "arXiv CS.LG",         "url": "https://arxiv.org/rss/cs.LG",                                        "category": "academic",       "quality": "academic",   "base_score": 10},
    {"id": "the_gradient",        "name": "The Gradient",        "url": "https://thegradient.pub/rss/",                                       "category": "academic",       "quality": "academic",   "base_score": 10},
    {"id": "bair_blog",           "name": "BAIR Blog",           "url": "https://bair.berkeley.edu/blog/feed.xml",                             "category": "academic",       "quality": "academic",   "base_score": 10},
    {"id": "ml_mastery",          "name": "ML Mastery",          "url": "https://machinelearningmastery.com/feed/",                            "category": "academic",       "quality": "academic",   "base_score": 10},

    # === Tier 8: Critical / Balancing Voices (base 5 — supporting context only) ===
    {"id": "ai_snake_oil",        "name": "AI Snake Oil",        "url": "https://www.aisnakeoil.com/feed",                                     "category": "critical",       "quality": "opinion",    "base_score": 5},
    {"id": "gary_marcus",         "name": "Gary Marcus",         "url": "https://garymarcus.substack.com/feed",                               "category": "critical",       "quality": "opinion",    "base_score": 5},
    {"id": "algorithmic_bridge",  "name": "Algorithmic Bridge",  "url": "https://thealgorithmicbridge.substack.com/feed",                      "category": "critical",       "quality": "opinion",    "base_score": 5},
    {"id": "vkrakovna",           "name": "Victoria Krakovna",   "url": "https://vkrakovna.wordpress.com/feed/",                              "category": "critical",       "quality": "opinion",    "base_score": 5},
]

# Derive flat RSS_FEEDS for backward compatibility
RSS_FEEDS = [s["url"] for s in SOURCE_REGISTRY]

# Lookups mapped by Source ID
FEED_SCORE_MAP = {s["id"]: s["base_score"] for s in SOURCE_REGISTRY}
FEED_CATEGORY_MAP = {s["id"]: s["category"] for s in SOURCE_REGISTRY}
URL_TO_ID = {s["url"]: s["id"] for s in SOURCE_REGISTRY}
ID_TO_NAME = {s["id"]: s["name"] for s in SOURCE_REGISTRY}

# --- Category Recurrence Penalty Constants ---
CATEGORY_RECURRENCE_PENALTY_STEP = 5

# --- Deprecated scoring constants retained for one release to simplify rollback ---
BASE_TIER_1 = 30
BASE_HIDDEN_GEM = 15
BASE_TIER_2 = 15

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

# Weighting Matrix (retained/updated)
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

CURATOR_SYSTEM_INSTRUCTION = """Synthesize technical news into an elite, human-authored social media post or short thread.

CRITICAL FORMAT REQUIREMENT:
* Determine if the story can be effectively communicated in a single high-signal post (1 paragraph), or if it genuinely requires a second post (exactly 2 paragraphs separated by a double newline '\\n\\n') to introduce a distinct perspective.
* PREFER A SINGLE POST BY DEFAULT. Generate a second paragraph ONLY when it introduces a distinct operational, strategic, technical, governance, or business perspective that would otherwise overcrowd the first post. Never split content simply to maintain a fixed format.
* Keep the length of each paragraph strictly under 280 characters to fit platform limits.
* Do NOT include any structural prefixes, labels, or templates (such as "Strategic Contrast:", "Practical Enterprise Implication:", "BODY:", "TOPIC:", "1/", "Part 1:", etc.) in the text of the posts. Start the text directly and naturally.

POST STRUCTURE:
1. First Paragraph (Always Present):
   - Start immediately with a distinctive, sharp observation about the news (no boilerplate openings).
   - Explain why it matters.
   - Include exactly one concrete technical fact (e.g. parameter count, RAM gigabytes, benchmark metrics, latency milliseconds, or specific hardware constraints) to anchor the authority of the post.
2. Second Paragraph (Optional - Thread Post):
   - Only output if a second post is genuinely needed to prevent overcrowding.
   - Introduce a net-new perspective (operational logistics, security/jailbreaks, scaling economics, governance, or product integration).
   - Do NOT restate or summarize the first post.

ANTI-PATTERNS (DO NOT USE):
* Generic openings like "AI is transforming...", "The future of...", or "In today's rapidly evolving...".
* Structural template prefixes like "Practical Enterprise Implication:" or "Strategic Contrast:".
* Hype words like "game-changing", "revolutionary", "frontier", or "systemic intelligence".
* Repeating the exact same "not X, but Y" structure in every post.

STYLE:
* Write like a thoughtful human engineer/architect, not a corporate press release.
* Use short, punchy sentences.
* Factuality: Do not invent events or state unverified rumors as established facts. If speculative, frame it hypothetically.
* Always append 1-2 relevant technical hashtags at the very end of the final paragraph of your response (e.g. #LLMs #EdgeAI) for discoverability.
"""

MENTOR_SYSTEM_INSTRUCTION = """Share technical insights as a Veteran Mentor. 
STRICTLY limit your output to a single post under 280 characters, presenting the core lesson with zero fluff."""
SAGE_DESIGNER_INSTRUCTION = """Design professional minimalist isometric AI visual prompts for conceptual editorial illustrations.
Do NOT generate prompts for: fake screenshots, fake dashboards, benchmark graphs, UI mockups, fabricated charts, company logos, copied branding, or text-heavy graphics.
Instead, focus on prompts depicting: clean isometric style, enterprise AI, networking, inference, agents, semiconductors, automation, orchestration, cloud infrastructure, or modern technology illustration.
The visual should support the concept and avoid any text, labels, or numbers."""

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
    "ANALYTICAL": "ANALYST: Explain why the news matters. Avoid hype, strip buzzwords, and connect technology to business impact.",
    "PRACTICAL": "PRACTICAL: Focus on developer utility, operational use, and what changes in real workflows.",
    "SAGE": "SAGE: Strategic, executive-facing, reflective, and written in simple language.",
    "CONCISE": "CONCISE: Short, sharp, high-signal, using minimal words.",
    "PHILOSOPHICAL": "PHILOSOPHICAL: Explore the deeper impact or ethical tension without becoming abstract or academic."
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

# --- Writing-Style Rotation Constants ---
ALL_STYLES = ["STRATEGIC_CONTRAST", "PRACTICAL_WORKFLOW", "RISK_VERIFICATION", "ENTERPRISE_ROI", "QUESTION_FIRST"]

WRITING_STYLES = {
    "STRATEGIC_CONTRAST": "Theme: Contrast the old assumptions / paradigm with the new reality of this story. Do NOT output 'STRATEGIC CONTRAST:' as a prefix.",
    "PRACTICAL_WORKFLOW": "Theme: Focus heavily on what changes immediately for developer setup, engineering workflows, or day-to-day operations. Do NOT output 'PRACTICAL WORKFLOW:' as a prefix.",
    "RISK_VERIFICATION": "Theme: Focus on the risk, failure modes, safety questions, compliance, or verification challenges of this news. Do NOT output 'RISK VERIFICATION:' as a prefix.",
    "ENTERPRISE_ROI": "Theme: Focus on commercial viability, business cost, ROI trade-offs, and what changes for enterprise vendors or deployment. Do NOT output 'ENTERPRISE ROI:' as a prefix.",
    "QUESTION_FIRST": "Theme: Start the first paragraph with a direct, provocative question about the core topic, then spend the rest of the paragraph answering it. Do NOT output 'QUESTION FIRST:' as a prefix."
}

STYLE_COMPATIBILITY = {
    "research_lab": ["STRATEGIC_CONTRAST", "QUESTION_FIRST", "RISK_VERIFICATION"],
    "enterprise": ["ENTERPRISE_ROI", "STRATEGIC_CONTRAST", "PRACTICAL_WORKFLOW"],
    "practitioner": ["PRACTICAL_WORKFLOW", "QUESTION_FIRST"],
    "open_source": ["PRACTICAL_WORKFLOW", "STRATEGIC_CONTRAST"],
    "infrastructure": ["ENTERPRISE_ROI", "STRATEGIC_CONTRAST"],
    "business": ["ENTERPRISE_ROI", "STRATEGIC_CONTRAST"],
    "journalism": ["STRATEGIC_CONTRAST", "QUESTION_FIRST", "RISK_VERIFICATION"],
    "academic": ["STRATEGIC_CONTRAST", "RISK_VERIFICATION", "QUESTION_FIRST"],
    "critical": ["RISK_VERIFICATION", "STRATEGIC_CONTRAST"]
}
