# Graph Report - BlueSky  (2026-07-14)

## Corpus Check
- 40 files · ~30,604 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 446 nodes · 819 edges · 51 communities (35 shown, 16 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.71)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4f45d179`
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
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Test mocks and conftest configurations|Test mocks and conftest configurations]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Mastodon post logic & smart text splitter|Mastodon post logic & smart text splitter]]
- [[_COMMUNITY_Dashboard telemetry status migration|Dashboard telemetry status migration]]
- [[_COMMUNITY_Image Compression utilities|Image Compression utilities]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
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
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Issue 1 version 2 documentation|Issue 1 version 2 documentation]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_CodeQL workflow pipeline|CodeQL workflow pipeline]]
- [[_COMMUNITY_Graphify pipeline workflow|Graphify pipeline workflow]]
- [[_COMMUNITY_Release workflow pipeline|Release workflow pipeline]]
- [[_COMMUNITY_Unit testing workflow pipeline|Unit testing workflow pipeline]]
- [[_COMMUNITY_Weekly configuration update pipeline|Weekly configuration update pipeline]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 58|Community 58]]

## God Nodes (most connected - your core abstractions)
1. `Settings` - 32 edges
2. `📖 BluBot Elite Sage: The Complete Manual` - 22 edges
3. `send_draft_for_approval()` - 20 edges
4. `synthesis_stage()` - 19 edges
5. `main()` - 17 edges
6. `curation_stage()` - 16 edges
7. `VanguardManager` - 15 edges
8. `SafeLogger` - 15 edges
9. `CurationResult` - 15 edges
10. `broadcast_stage()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `test_article_matches_topic()` --calls--> `article_matches_topic()`  [EXTRACTED]
  src/tests/test_topic_grounding.py → bot.py
- `curation_stage()` --calls--> `fetch_news()`  [EXTRACTED]
  bot.py → src/curator.py
- `curation_stage()` --calls--> `VanguardManager`  [EXTRACTED]
  bot.py → src/feed_vanguard.py
- `synthesis_stage()` --calls--> `generate_image_alt_text()`  [EXTRACTED]
  bot.py → src/curator.py
- `synthesis_stage()` --calls--> `generate_mentor_insight()`  [EXTRACTED]
  bot.py → src/curator.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Social Media Platform Targets** — sage_intelligence, the_weaver, interaction_engine [INFERRED 0.85]

## Communities (51 total, 16 thin omitted)

### Community 0 - "Core Curation & Broadcaster Logic"
Cohesion: 0.08
Nodes (22): 🧱 Architectural Guardrails, 🤝 Contributing to BluBot Elite, ⚖️ "Signal Verification" for AI-Assisted Code, 🚀 The PR Workflow, 🧠 The Sage Philosophy, 1. Automated Regression (CI-Ready), ⚙️1. Platform Credentials, 🤫2. Configure GitHub Secrets (+14 more)

### Community 1 - "Data Models & Pipeline Staging"
Cohesion: 0.06
Nodes (76): article_matches_topic(), broadcast_stage(), curation_stage(), interaction_stage(), main(), persistence_stage(), Stage 1: Fetch and Score Raw News., Stage 2: AI Summarization and Persona Application. (+68 more)

### Community 2 - "Logger & Secret Redaction Engine"
Cohesion: 0.10
Nodes (18): Any, LogRecord, _HumanFormatter, _JsonFormatter, Redacts secrets from all log content.     Uses both keyword-based patterns and, Formats log records as clean, colorized text for terminal readability., Structured, security-hardened logger with secret redaction and JSON output., Formats log records as single-line JSON strings. (+10 more)

### Community 3 - "Global settings & config generation"
Cohesion: 0.09
Nodes (31): generate_image_alt_text(), generate_visual_prompt(), Generates screen-reader-friendly alt text for the generated image using Gemini V, Determines if the current execution was manually triggered (Persona logic)., Determines if scheduling rest locks should be ignored (Infrastructure logic)., Centralized, typed configuration for BluBot., Settings, Validates text length against platform limits and returns a warning or info stri (+23 more)

### Community 4 - "Feed configuration and dry-run diagnostics"
Cohesion: 0.06
Nodes (47): main(), test_full_dry_run(), test_scoring(), get_version(), Legacy wrapper for the new Settings validation logic., Legacy wrapper for Gemini model self-discovery., validate_config(), validate_gemini_model_priority() (+39 more)

### Community 5 - "Feed Vanguard RSS audit resilience"
Cohesion: 0.16
Nodes (11): AsyncClient, Feed Vanguard, Three-Tier State Persistence, Performs a comprehensive feed audit and displays a health report., run_standalone_audit(), diagnostic(), Manages RSS feed health and identifies problematic sources for soft-disable., Helper to check a single feed's health. (+3 more)

### Community 6 - "Atomic file locking & state persistence"
Cohesion: 0.15
Nodes (10): fetch_feed_headlines(), main(), Fetches first 5 headlines from a single RSS feed., generate_interactive_reply(), Generates an AI reply for a social mention, maintaining the Sage persona., Validates critical settings and returns True if valid., load_session_string(), Saves the BlueSky session string to a private file. (+2 more)

### Community 7 - "Seen interactions & smart text truncation"
Cohesion: 0.24
Nodes (10): compress_image(), Losslessly then lossily compresses image to stay within platform limits (e.g., B, Truncates text at word boundaries within the limit, appending a suffix., Splits text into chunks within the limit, prioritizing paragraph and sentence bo, smart_split(), smart_truncate(), Verify that compress_image actually reduces size if needed., test_compress_image_reduction() (+2 more)

### Community 8 - "Community 8"
Cohesion: 0.22
Nodes (6): FileLock, _load_gist_state(), load_seen_articles(), Cross-platform advisory file lock context manager., Helper to pull state from a private GitHub Gist., 3-Tier Resilience: Local -> Backup -> Gist -> Default.

### Community 9 - "Test mocks and conftest configurations"
Cohesion: 0.22
Nodes (8): mock_bsky_client(), mock_genai_client(), mock_httpx_client(), Mock for httpx.AsyncClient., Mock for atproto.AsyncClient., Mock for google.genai.Client., Silence the SafeLogger during tests to keep output clean, unless we're testing t, silent_logger()

### Community 10 - "Community 10"
Cohesion: 0.38
Nodes (7): load_json_state(), load_seen_interactions(), Helper to load JSON data from a file path., Loads the list of social interaction IDs we've already responded to., Saves the list of social interaction IDs to persistent store., save_seen_interactions(), test_seen_interactions_persistence()

### Community 11 - "Community 11"
Cohesion: 0.33
Nodes (6): get_with_safe_redirects(), Temporarily constrains DNS resolution for one hostname to a prevalidated set., Fetches a URL while validating every hop in the redirect chain., _resolver_pinned_to_ips(), Verify that get_with_safe_redirects blocks redirects to private IPs., test_ssrf_blocking_in_redirects()

### Community 12 - "Mastodon post logic & smart text splitter"
Cohesion: 0.20
Nodes (9): 1. What was Deleted or Simplified, 2. Why the Simpler Version is Safe, 3. Verification & Tests Run, Changes, 🛠️ Compliance with `AGENTS.md` Rules, 🧠 Curation Diversity & Writing-Style Rotation, 📡 Curation Engine & Registry Refinement, 📄 PR v3.13.5: Curation Engine v4 (Stable ID Registry, Category Rotation, and Telegram Overrides) (+1 more)

### Community 14 - "Image Compression utilities"
Cohesion: 0.22
Nodes (8): Image Compression & RGB Defense, Helper to push state to a private GitHub Gist., Helper to save state to a JSON file., 3-Tier Persistence: Atomic Write -> Backup Commit -> Remote Sync., _save_gist_state(), save_json_state(), save_seen_articles(), SSRF Prevention

### Community 15 - "Community 15"
Cohesion: 0.33
Nodes (6): _is_public_ip(), Checks if an IP address is a routable public address., Resolves a hostname and returns only public IP candidates., _resolve_public_ip_candidates(), Verify that private and reserved IP addresses are correctly identified as non-pu, test_is_public_ip_validation()

### Community 16 - "Community 16"
Cohesion: 0.50
Nodes (4): get_image_mime(), Detects MIME type from image bytes for broadcaster fidelity., Verify MIME type detection for different image headers., test_get_image_mime_detection()

### Community 25 - "Wiki manual blueprint"
Cohesion: 0.13
Nodes (15): 📖 BluBot Elite Sage: The Complete Manual, Hardening Features, 📊 Page 12: System Telemetry Dashboards, 🚀 Page 18: Threads Media Propagation Hardening (v3.13.1), 🚀 Page 19: Telegram Approval Queue Timeout Calibration (v3.13.2), 🏠 Page 1: The Sage Philosophy, 🚀 Page 20: Monotonic Time Tracking for Telegram Approval Timeout (v3.13.3), 🧠 Page 2: Breakthrough Scoring Engine v3 (+7 more)

### Community 27 - "Community 27"
Cohesion: 0.50
Nodes (4): normalize_url(), Normalizes a URL by resolving protocol-relative links, stripping fragments,, Verify that normalize_url handles various edge cases correctly., test_normalize_url_scenarios()

### Community 28 - "Issue 1 version 2 documentation"
Cohesion: 0.50
Nodes (4): 1. Interactive Telegram Gateway & Approval Queue, 2. Screen Reader Multimodal Alt-Text, 3. Cultural Hashtag Alignment, 🚀 Page 17: Interactive Telegram Control, Alt Text, and Hashtag Management (v3.13.0)

### Community 29 - "Community 29"
Cohesion: 0.50
Nodes (4): Unicode-aware byte-level truncation to prevent Bluesky index errors., truncate_bytes(), Verify that truncation doesn't break multi-byte unicode characters., test_truncate_bytes_unicode()

### Community 42 - "Community 42"
Cohesion: 0.25
Nodes (8): Curation Feed Network (32 Validated Feeds), 📡 Page 13: Feed Vanguard Automation, The Auditing Logic, The "Soft-Disable" Strategy, Tier 1: AI Lab Blogs, Tier 2: Elite Newsletters & Analysts, Tier 3: Research & Academic (Hidden Gems), Tier 4: Industry & Journalism

### Community 43 - "Community 43"
Cohesion: 0.25
Nodes (7): 1. Information We Collect, 2. How We Use Data, 3. Data Sharing and Third Parties, 4. Data Retention, 5. Revoking Access, 6. Contact & Support, Privacy Policy for BluBot

### Community 44 - "Community 44"
Cohesion: 0.29
Nodes (7): Configuration, Conversational Persona & Prompts, Core Architecture, Managing Feeds, Page 14: Interaction Engine (Mention Replies & Comments), Security & Anti-Spam, Token & Cost Optimization

### Community 46 - "Community 46"
Cohesion: 0.40
Nodes (5): Dependency Locking (pip-tools), Platform Synergy, Secret Redaction, Security & Supply Chain, SSRF Protection

### Community 47 - "Community 47"
Cohesion: 0.40
Nodes (4): Current Security Baseline (v3.13.3), Reporting a Vulnerability, 🛡️ Security Policy: BluBot Elite, Supported Versions

### Community 48 - "Community 48"
Cohesion: 0.50
Nodes (4): 1. Smart Split Logic, 2. Platform-Native Chaining, 3. Narrative Expansion, 🧵 Page 11: The Weaver (Multi-Post Threading)

### Community 49 - "Community 49"
Cohesion: 0.50
Nodes (4): 1. The Editorial Pulse (Stylistic Memory), 2. High-Resolution Temporal Intelligence, 3. Manual Intercept Mode, 🎭 Page 10: The Natural Vibe Engine

### Community 51 - "Community 51"
Cohesion: 0.67
Nodes (3): 1. Dynamic Keyword & Product Updates, 2. Friday Release Curation Focus, 📅 Page 16: Automated Config Updates & Friday Release Focus

### Community 52 - "Community 52"
Cohesion: 0.67
Nodes (3): Character Safety Buffers, Configuration, 🧶 Page 15: Precision Threading (The Weaver Cap)

### Community 53 - "Community 53"
Cohesion: 0.67
Nodes (3): Environment Secrets, Hardening & Event-Loop Optimization, ⚙️ Page 6: Technical Configuration

### Community 54 - "Community 54"
Cohesion: 0.67
Nodes (3): Execution, 🧪 Page 7: Local Testing & Interactive Diagnostics, 🎨 Sage Console (Logging)

### Community 55 - "Community 55"
Cohesion: 0.67
Nodes (3): 🧪 Page 9: Automated Quality Control, Running Automated Tests, The Test Layers

## Knowledge Gaps
- **96 isolated node(s):** `graphify`, `Workflow: graphify`, `Ponytail-style development rules`, `🧠 The Sage Philosophy`, `🧱 Architectural Guardrails` (+91 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Global settings & config generation` to `Data Models & Pipeline Staging`, `Logger & Secret Redaction Engine`, `Feed configuration and dry-run diagnostics`, `Atomic file locking & state persistence`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Why does `📖 BluBot Elite Sage: The Complete Manual` connect `Wiki manual blueprint` to `Core Curation & Broadcaster Logic`, `Community 42`, `Community 44`, `Dashboard telemetry status migration`, `Community 46`, `Community 48`, `Community 49`, `Community 51`, `Community 52`, `Community 53`, `Community 54`, `Community 55`, `Issue 1 version 2 documentation`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Why does `SafeLogger` connect `Logger & Secret Redaction Engine` to `Data Models & Pipeline Staging`, `Global settings & config generation`, `Feed configuration and dry-run diagnostics`, `Atomic file locking & state persistence`, `Community 8`, `Image Compression utilities`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **What connects `Synchronous implementation of STATUS.md update to be offloaded to thread.`, `Automatically update the STATUS.md dashboard without blocking the event loop.`, `Stage 1: Fetch and Score Raw News.` to the rest of the system?**
  _205 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Core Curation & Broadcaster Logic` be split into smaller, more focused modules?**
  _Cohesion score 0.07692307692307693 - nodes in this community are weakly interconnected._
- **Should `Data Models & Pipeline Staging` be split into smaller, more focused modules?**
  _Cohesion score 0.05742296918767507 - nodes in this community are weakly interconnected._
- **Should `Logger & Secret Redaction Engine` be split into smaller, more focused modules?**
  _Cohesion score 0.1010752688172043 - nodes in this community are weakly interconnected._