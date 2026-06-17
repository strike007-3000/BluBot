# Graph Report - BlueSky  (2026-06-16)

## Corpus Check
- 43 files · ~23,954 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 440 nodes · 698 edges · 58 communities (39 shown, 19 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 61 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `197d8ee8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Core Curation & Broadcaster Logic|Core Curation & Broadcaster Logic]]
- [[_COMMUNITY_Data Models & Pipeline Staging|Data Models & Pipeline Staging]]
- [[_COMMUNITY_Logger & Secret Redaction Engine|Logger & Secret Redaction Engine]]
- [[_COMMUNITY_Global settings & config generation|Global settings & config generation]]
- [[_COMMUNITY_Feed configuration and dry-run diagnostics|Feed configuration and dry-run diagnostics]]
- [[_COMMUNITY_Feed Vanguard RSS audit resilience|Feed Vanguard RSS audit resilience]]
- [[_COMMUNITY_Atomic file locking & state persistence|Atomic file locking & state persistence]]
- [[_COMMUNITY_Seen interactions & smart text truncation|Seen interactions & smart text truncation]]
- [[_COMMUNITY_Utils & SSRF prevention architecture|Utils & SSRF prevention architecture]]
- [[_COMMUNITY_Test mocks and conftest configurations|Test mocks and conftest configurations]]
- [[_COMMUNITY_SSRF redirect prevention & DNS validation|SSRF redirect prevention & DNS validation]]
- [[_COMMUNITY_Public IP validation|Public IP validation]]
- [[_COMMUNITY_Mastodon post logic & smart text splitter|Mastodon post logic & smart text splitter]]
- [[_COMMUNITY_Dashboard telemetry status migration|Dashboard telemetry status migration]]
- [[_COMMUNITY_Image Compression utilities|Image Compression utilities]]
- [[_COMMUNITY_Mime-type helpers|Mime-type helpers]]
- [[_COMMUNITY_URL normalization logic|URL normalization logic]]
- [[_COMMUNITY_Dependabot configuration|Dependabot configuration]]
- [[_COMMUNITY_Contributing guidelines|Contributing guidelines]]
- [[_COMMUNITY_PR description template|PR description template]]
- [[_COMMUNITY_Privacy policy documentation|Privacy policy documentation]]
- [[_COMMUNITY_Repository README dashboard|Repository README dashboard]]
- [[_COMMUNITY_Pip requirements configuration|Pip requirements configuration]]
- [[_COMMUNITY_Security reporting guidelines|Security reporting guidelines]]
- [[_COMMUNITY_Bot Telemetry status documentation|Bot Telemetry status documentation]]
- [[_COMMUNITY_Wiki manual blueprint|Wiki manual blueprint]]
- [[_COMMUNITY_Graphify rules configuration|Graphify rules configuration]]
- [[_COMMUNITY_Issue 1 documentation|Issue 1 documentation]]
- [[_COMMUNITY_Issue 1 version 2 documentation|Issue 1 version 2 documentation]]
- [[_COMMUNITY_Issue 2 documentation|Issue 2 documentation]]
- [[_COMMUNITY_Issue 7 documentation|Issue 7 documentation]]
- [[_COMMUNITY_Issue 8 documentation|Issue 8 documentation]]
- [[_COMMUNITY_Flux Nvidia model ID issue|Flux Nvidia model ID issue]]
- [[_COMMUNITY_CodeQL workflow pipeline|CodeQL workflow pipeline]]
- [[_COMMUNITY_Daily curation workflow pipeline|Daily curation workflow pipeline]]
- [[_COMMUNITY_Graphify pipeline workflow|Graphify pipeline workflow]]
- [[_COMMUNITY_Release workflow pipeline|Release workflow pipeline]]
- [[_COMMUNITY_Unit testing workflow pipeline|Unit testing workflow pipeline]]
- [[_COMMUNITY_Weekly configuration update pipeline|Weekly configuration update pipeline]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]

## God Nodes (most connected - your core abstractions)
1. `VanguardManager` - 21 edges
2. `📖 BluBot Elite Sage: The Complete Manual` - 18 edges
3. `InteractionNote` - 16 edges
4. `synthesis_stage()` - 15 edges
5. `SafeLogger` - 15 edges
6. `Article` - 14 edges
7. `CurationResult` - 14 edges
8. `Settings` - 14 edges
9. `InteractionResult` - 13 edges
10. `_SecretRedactionFilter` - 12 edges

## Surprising Connections (you probably didn't know these)
- `test_dashboard()` --calls--> `update_status_dashboard()`  [EXTRACTED]
  scratch/test_dashboard_migration.py → bot.py
- `curation_stage()` --calls--> `fetch_news()`  [EXTRACTED]
  bot.py → src/curator.py
- `AsyncClient` --uses--> `VanguardManager`  [INFERRED]
  bot.py → src/feed_vanguard.py
- `AsyncClient` --uses--> `Article`  [INFERRED]
  bot.py → src/models.py
- `AsyncClient` --uses--> `BroadcastResult`  [INFERRED]
  bot.py → src/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Social Media Platform Targets** — sage_intelligence, the_weaver, interaction_engine [INFERRED 0.85]

## Communities (58 total, 19 thin omitted)

### Community 0 - "Core Curation & Broadcaster Logic"
Cohesion: 0.12
Nodes (16): 1. Automated Regression (CI-Ready), ⚙️1. Platform Credentials, 🤫2. Configure GitHub Secrets, 2. Interactive Diagnostic (Developer Tool), 👨‍🔧 BluBot: Elite AI News Curator, Bluesky & Mastodon, 🤝 Community & Security, Google Gemini (+8 more)

### Community 1 - "Data Models & Pipeline Staging"
Cohesion: 0.08
Nodes (57): broadcast_stage(), curation_stage(), interaction_stage(), main(), persistence_stage(), Any, AsyncClient, Stage 2: AI Summarization and Persona Application. (+49 more)

### Community 2 - "Logger & Secret Redaction Engine"
Cohesion: 0.09
Nodes (18): LogRecord, _HumanFormatter, _JsonFormatter, Any, Redacts secrets from all log content.     Uses both keyword-based patterns and, Formats log records as clean, colorized text for terminal readability., Structured, security-hardened logger with secret redaction and JSON output., Formats log records as single-line JSON strings. (+10 more)

### Community 3 - "Global settings & config generation"
Cohesion: 0.09
Nodes (20): fetch_feed_headlines(), main(), Fetches first 5 headlines from a single RSS feed., Determines if the current execution was manually triggered (Persona logic)., Determines if scheduling rest locks should be ignored (Infrastructure logic)., Validates critical settings and returns True if valid., Centralized, typed configuration for BluBot., Settings (+12 more)

### Community 4 - "Feed configuration and dry-run diagnostics"
Cohesion: 0.11
Nodes (30): main(), test_full_dry_run(), test_scoring(), Legacy wrapper for Gemini model self-discovery., validate_gemini_model_priority(), calculate_relevance_score(), fetch_news(), fetch_single_feed() (+22 more)

### Community 5 - "Feed Vanguard RSS audit resilience"
Cohesion: 0.25
Nodes (5): diagnostic(), AsyncClient, Helper to check a single feed's health., Returns the list of feeds that are NOT currently blacklisted or have passed thei, Perform a full scan of all feeds and update the blacklist.

### Community 6 - "Atomic file locking & state persistence"
Cohesion: 0.16
Nodes (11): test_persistence_resilience(), FileLock, _load_gist_state(), load_seen_articles(), Cross-platform advisory file lock context manager., Helper to pull state from a private GitHub Gist., Helper to push state to a private GitHub Gist., 3-Tier Resilience: Local -> Backup -> Gist -> Default. (+3 more)

### Community 7 - "Seen interactions & smart text truncation"
Cohesion: 0.17
Nodes (15): Image Compression & RGB Defense, load_json_state(), load_seen_interactions(), load_session_string(), Helper to load JSON data from a file path., Helper to save state to a JSON file., Loads the list of social interaction IDs we've already responded to., Saves the list of social interaction IDs to persistent store. (+7 more)

### Community 8 - "Utils & SSRF prevention architecture"
Cohesion: 0.50
Nodes (4): get_image_mime(), Detects MIME type from image bytes for broadcaster fidelity., Verify MIME type detection for different image headers., test_get_image_mime_detection()

### Community 9 - "Test mocks and conftest configurations"
Cohesion: 0.22
Nodes (8): mock_bsky_client(), mock_genai_client(), mock_httpx_client(), Mock for httpx.AsyncClient., Mock for atproto.AsyncClient., Mock for google.genai.Client., Silence the SafeLogger during tests to keep output clean, unless we're testing t, silent_logger()

### Community 10 - "SSRF redirect prevention & DNS validation"
Cohesion: 0.33
Nodes (6): get_with_safe_redirects(), Temporarily constrains DNS resolution for one hostname to a prevalidated set., Fetches a URL while validating every hop in the redirect chain., _resolver_pinned_to_ips(), Verify that get_with_safe_redirects blocks redirects to private IPs., test_ssrf_blocking_in_redirects()

### Community 11 - "Public IP validation"
Cohesion: 0.33
Nodes (6): _is_public_ip(), Checks if an IP address is a routable public address., Resolves a hostname and returns only public IP candidates., _resolve_public_ip_candidates(), Verify that private and reserved IP addresses are correctly identified as non-pu, test_is_public_ip_validation()

### Community 12 - "Mastodon post logic & smart text splitter"
Cohesion: 0.25
Nodes (7): 1. Refactored JSON State Persistence, 2. Precompiled Regular Expressions, 3. Hardened Humanization & Short-Form Prompts, 4. Repository Cleanup, 🌟 Key Updates, PR Description: Refactored State Persistence & Hardened Humanization Prompts (v3.11.1) 🛠️✍️, 🧪 Verification & Testing

### Community 13 - "Dashboard telemetry status migration"
Cohesion: 0.10
Nodes (20): Automatically update the STATUS.md dashboard without blocking the event loop., update_status_dashboard(), Feed Vanguard, Three-Tier State Persistence, test_dashboard(), test_config_validation(), Performs a comprehensive feed audit and displays a health report., run_standalone_audit() (+12 more)

### Community 14 - "Image Compression utilities"
Cohesion: 0.21
Nodes (11): compress_image(), Losslessly then lossily compresses image to stay within platform limits (e.g., B, Unicode-aware byte-level truncation to prevent Bluesky index errors., Truncates text at word boundaries within the limit, appending a suffix., smart_truncate(), truncate_bytes(), Verify that truncation doesn't break multi-byte unicode characters., Verify that compress_image actually reduces size if needed. (+3 more)

### Community 15 - "Mime-type helpers"
Cohesion: 0.14
Nodes (18): Interaction Engine, Sage Intelligence v3, post_to_bluesky(), post_to_mastodon(), post_to_threads(), Posts to Mastodon with Conditional Multi-Post Threading (The Weaver)., Posts to Threads with Conditional Multi-Post Threading (The Weaver)., Posts to Bluesky with Conditional Multi-Post Threading (The Weaver). (+10 more)

### Community 16 - "URL normalization logic"
Cohesion: 0.50
Nodes (4): normalize_url(), Normalizes a URL by resolving protocol-relative links, stripping fragments,, Verify that normalize_url handles various edge cases correctly., test_normalize_url_scenarios()

### Community 25 - "Wiki manual blueprint"
Cohesion: 0.15
Nodes (12): 📖 BluBot Elite Sage: The Complete Manual, Hardening Features, 📊 Page 12: System Telemetry Dashboards, 🏠 Page 1: The Sage Philosophy, 🧠 Page 2: Breakthrough Scoring Engine v3, 🛡️ Page 3: Reliability & The Fortress (v3.9.0), 🛰️ Page 5: Source Intelligence, 💾 Page 8: 3-Tier State Resilience (v3.8.0) (+4 more)

### Community 27 - "Issue 1 documentation"
Cohesion: 0.40
Nodes (4): Description, Proposed Fix, Root Cause, Traceback

### Community 28 - "Issue 1 version 2 documentation"
Cohesion: 0.40
Nodes (4): Description, Proposed Fix, Root Cause, Traceback

### Community 29 - "Issue 2 documentation"
Cohesion: 0.50
Nodes (3): Actions Affected, Description, Proposed Fix

### Community 32 - "Flux Nvidia model ID issue"
Cohesion: 0.18
Nodes (10): Actual behavior, Bug: NVIDIA OpenAI-compatible fallback rejects shortened FLUX model id, Expected behavior, Impact, Labels (suggested), Reproduction (operational), Suggested fix (no code changes in this issue), Summary (+2 more)

### Community 42 - "Community 42"
Cohesion: 0.25
Nodes (8): Curation Feed Network (32 Validated Feeds), 📡 Page 13: Feed Vanguard Automation (v3.8.2), The Auditing Logic, The "Soft-Disable" Strategy, Tier 1: AI Lab Blogs, Tier 2: Elite Newsletters & Analysts, Tier 3: Research & Academic (Hidden Gems), Tier 4: Industry & Journalism

### Community 43 - "Community 43"
Cohesion: 0.25
Nodes (7): 1. Information We Collect, 2. How We Use Data, 3. Data Sharing and Third Parties, 4. Data Retention, 5. Revoking Access, 6. Contact & Support, Privacy Policy for BluBot

### Community 44 - "Community 44"
Cohesion: 0.29
Nodes (7): Configuration, Conversational Persona & Prompts, Core Architecture, Managing Feeds, Page 14: Interaction Engine (Mention Replies & Comments) (v3.11.0), Security & Anti-Spam, Token & Cost Optimization

### Community 45 - "Community 45"
Cohesion: 0.33
Nodes (5): 🧱 Architectural Guardrails, 🤝 Contributing to BluBot Elite, ⚖️ "Signal Verification" for AI-Assisted Code, 🚀 The PR Workflow, 🧠 The Sage Philosophy

### Community 46 - "Community 46"
Cohesion: 0.40
Nodes (5): Dependency Locking (pip-tools), Platform Synergy, Secret Redaction, Security & Supply Chain, SSRF Protection

### Community 47 - "Community 47"
Cohesion: 0.40
Nodes (4): Current Security Baseline (v3.6.7), Reporting a Vulnerability, 🛡️ Security Policy: BluBot Elite, Supported Versions

### Community 48 - "Community 48"
Cohesion: 0.50
Nodes (4): 1. Smart Split Logic, 2. Platform-Native Chaining, 3. Narrative Expansion, 🧵 Page 11: The Weaver (Multi-Post Threading)

### Community 49 - "Community 49"
Cohesion: 0.50
Nodes (4): 1. The Editorial Pulse (Stylistic Memory), 2. High-Resolution Temporal Intelligence, 3. Manual Intercept Mode, 🎭 Page 10: The Natural Vibe Engine (v3.7.0)

### Community 51 - "Community 51"
Cohesion: 0.67
Nodes (3): 1. Dynamic Keyword & Product Updates, 2. Friday Release Curation Focus, 📅 Page 16: Automated Config Updates & Friday Release Focus

### Community 52 - "Community 52"
Cohesion: 0.67
Nodes (3): Character Safety Buffers, Configuration, 🧶 Page 15: Precision Threading (The Weaver Cap)

### Community 53 - "Community 53"
Cohesion: 0.67
Nodes (3): Environment Secrets, Hardening & Event-Loop Optimization, ⚙️ Page 6: Technical Configuration (v3.11.0)

### Community 54 - "Community 54"
Cohesion: 0.67
Nodes (3): Execution, 🧪 Page 7: Local Testing & Interactive Diagnostics, 🎨 Sage Console (Logging)

### Community 55 - "Community 55"
Cohesion: 0.67
Nodes (3): 🧪 Page 9: Automated Quality Control (v3.6.5), Running Automated Tests, The Test Layers

## Knowledge Gaps
- **114 isolated node(s):** `Any`, `graphify`, `Workflow: graphify`, `🧠 The Sage Philosophy`, `🧱 Architectural Guardrails` (+109 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Global settings & config generation` to `Logger & Secret Redaction Engine`, `Dashboard telemetry status migration`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `VanguardManager` connect `Data Models & Pipeline Staging` to `Feed Vanguard RSS audit resilience`, `Dashboard telemetry status migration`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Why does `SafeLogger` connect `Logger & Secret Redaction Engine` to `Global settings & config generation`, `Feed configuration and dry-run diagnostics`, `Atomic file locking & state persistence`, `Seen interactions & smart text truncation`, `Dashboard telemetry status migration`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `VanguardManager` (e.g. with `Any` and `AsyncClient`) actually correct?**
  _`VanguardManager` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `InteractionNote` (e.g. with `Any` and `AsyncClient`) actually correct?**
  _`InteractionNote` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `SafeLogger` (e.g. with `Settings` and `FileLock`) actually correct?**
  _`SafeLogger` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Synchronous implementation of STATUS.md update to be offloaded to thread.`, `Automatically update the STATUS.md dashboard without blocking the event loop.`, `Stage 1: Fetch and Score Raw News.` to the rest of the system?**
  _213 weakly-connected nodes found - possible documentation gaps or missing edges._