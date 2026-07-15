# Graph Report - BlueSky  (2026-07-14)

## Corpus Check
- 41 files · ~32,743 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 468 nodes · 941 edges · 44 communities (27 shown, 17 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.71)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `79eb0c7c`
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
- [[_COMMUNITY_Mastodon post logic & smart text splitter|Mastodon post logic & smart text splitter]]
- [[_COMMUNITY_Dashboard telemetry status migration|Dashboard telemetry status migration]]
- [[_COMMUNITY_Image Compression utilities|Image Compression utilities]]
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
- [[_COMMUNITY_Issue 1 version 2 documentation|Issue 1 version 2 documentation]]
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
- [[_COMMUNITY_Community 58|Community 58]]

## God Nodes (most connected - your core abstractions)
1. `Settings` - 42 edges
2. `CurationResult` - 23 edges
3. `send_draft_for_approval()` - 23 edges
4. `SynthesisResult` - 22 edges
5. `📖 BluBot Elite Sage: The Complete Manual` - 22 edges
6. `media_strategy_stage()` - 21 edges
7. `synthesis_stage()` - 19 edges
8. `main()` - 19 edges
9. `curation_stage()` - 16 edges
10. `MediaAsset` - 16 edges

## Surprising Connections (you probably didn't know these)
- `test_article_matches_topic()` --calls--> `article_matches_topic()`  [EXTRACTED]
  src/tests/test_topic_grounding.py → bot.py
- `curation_stage()` --calls--> `fetch_news()`  [EXTRACTED]
  bot.py → src/curator.py
- `curation_stage()` --calls--> `get_temporal_context()`  [EXTRACTED]
  bot.py → src/curator.py
- `curation_stage()` --calls--> `VanguardManager`  [EXTRACTED]
  bot.py → src/feed_vanguard.py
- `curation_stage()` --references--> `CurationResult`  [EXTRACTED]
  bot.py → src/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Social Media Platform Targets** — sage_intelligence, the_weaver, interaction_engine [INFERRED 0.85]

## Communities (44 total, 17 thin omitted)

### Community 0 - "Core Curation & Broadcaster Logic"
Cohesion: 0.08
Nodes (22): 🧱 Architectural Guardrails, 🤝 Contributing to BluBot Elite, ⚖️ "Signal Verification" for AI-Assisted Code, 🚀 The PR Workflow, 🧠 The Sage Philosophy, 1. Automated Regression (CI-Ready), ⚙️1. Platform Credentials, 🤫2. Configure GitHub Secrets (+14 more)

### Community 1 - "Data Models & Pipeline Staging"
Cohesion: 0.06
Nodes (67): broadcast_stage(), interaction_stage(), Stage 2: AI Summarization and Persona Application., Stage 3: Multi-platform delivery., Handles social interactions (mentions/replies) with humanized engagement., synthesis_stage(), Client, Enum (+59 more)

### Community 2 - "Logger & Secret Redaction Engine"
Cohesion: 0.07
Nodes (28): Any, Synchronous implementation of STATUS.md update to be offloaded to thread., _update_status_dashboard_sync(), LogRecord, fetch_feed_headlines(), main(), Fetches first 5 headlines from a single RSS feed., _HumanFormatter (+20 more)

### Community 3 - "Global settings & config generation"
Cohesion: 0.10
Nodes (47): main(), media_strategy_stage(), persistence_stage(), Dedicated media decision stage (Step 1 & 2 & 3 & 4 & 5)., Stage 4: State Synchronization., Automatically update the STATUS.md dashboard without blocking the event loop., update_status_dashboard(), get_temporal_context() (+39 more)

### Community 4 - "Feed configuration and dry-run diagnostics"
Cohesion: 0.07
Nodes (38): main(), test_full_dry_run(), test_scoring(), get_version(), Legacy wrapper for the new Settings validation logic., Legacy wrapper for Gemini model self-discovery., validate_config(), validate_gemini_model_priority() (+30 more)

### Community 5 - "Feed Vanguard RSS audit resilience"
Cohesion: 0.15
Nodes (11): AsyncClient, Feed Vanguard, Three-Tier State Persistence, Performs a comprehensive feed audit and displays a health report., run_standalone_audit(), diagnostic(), Manages RSS feed health and identifies problematic sources for soft-disable., Helper to check a single feed's health. (+3 more)

### Community 6 - "Atomic file locking & state persistence"
Cohesion: 0.15
Nodes (17): article_matches_topic(), curation_stage(), Stage 1: Fetch and Score Raw News., Returns True if all significant keywords from topic match (with inflections on w, Article, Represents a single news item from an RSS feed., Validates the new Interaction Engine note structure., Validates the interaction processing summary structure. (+9 more)

### Community 7 - "Seen interactions & smart text truncation"
Cohesion: 0.13
Nodes (14): Verify that validate() always returns True in dry run., Verify validate() fails when required production keys are missing., Verify validate() succeeds with valid parameters., Verify is_manual_run checks correct github event., Verify should_bypass_rest determines when rest is bypassed., Verify that Settings.from_env() reads correct defaults., Verify that settings correctly capture Telegram environment variables., test_settings_from_env_default() (+6 more)

### Community 9 - "Test mocks and conftest configurations"
Cohesion: 0.22
Nodes (8): mock_bsky_client(), mock_genai_client(), mock_httpx_client(), Mock for httpx.AsyncClient., Mock for atproto.AsyncClient., Mock for google.genai.Client., Silence the SafeLogger during tests to keep output clean, unless we're testing t, silent_logger()

### Community 12 - "Mastodon post logic & smart text splitter"
Cohesion: 0.20
Nodes (9): 1. What was Deleted or Simplified, 2. Why the Simpler Version is Safe, 3. Verification & Tests Run, Changes, 🛠️ Compliance with `AGENTS.md` Rules, 🧠 Curation Diversity & Writing-Style Rotation, 📡 Curation Engine & Registry Refinement, 📄 PR v3.13.5: Curation Engine v4 (Stable ID Registry, Category Rotation, and Telegram Overrides) (+1 more)

### Community 14 - "Image Compression utilities"
Cohesion: 0.06
Nodes (47): Image Compression & RGB Defense, compress_image(), FileLock, get_with_safe_redirects(), _is_public_ip(), load_json_state(), load_seen_interactions(), normalize_url() (+39 more)

### Community 25 - "Wiki manual blueprint"
Cohesion: 0.12
Nodes (16): 📖 BluBot Elite Sage: The Complete Manual, Hardening Features, 🚀 Page 18: Threads Media Propagation Hardening (v3.13.1), 🚀 Page 19: Telegram Approval Queue Timeout Calibration (v3.13.2), 🏠 Page 1: The Sage Philosophy, 🚀 Page 20: Monotonic Time Tracking for Telegram Approval Timeout (v3.13.3), 🧠 Page 2: Breakthrough Scoring Engine v3, 🛡️ Page 3: Reliability & The Fortress (+8 more)

### Community 28 - "Issue 1 version 2 documentation"
Cohesion: 0.50
Nodes (4): 1. Interactive Telegram Gateway & Approval Queue, 2. Screen Reader Multimodal Alt-Text, 3. Cultural Hashtag Alignment, 🚀 Page 17: Interactive Telegram Control, Alt Text, and Hashtag Management (v3.13.0)

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

## Knowledge Gaps
- **96 isolated node(s):** `graphify`, `Workflow: graphify`, `Ponytail-style development rules`, `🧠 The Sage Philosophy`, `🧱 Architectural Guardrails` (+91 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Global settings & config generation` to `Logger & Secret Redaction Engine`, `Feed configuration and dry-run diagnostics`, `Atomic file locking & state persistence`, `Seen interactions & smart text truncation`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `📖 BluBot Elite Sage: The Complete Manual` connect `Wiki manual blueprint` to `Core Curation & Broadcaster Logic`, `Community 8`, `Community 42`, `Community 44`, `Dashboard telemetry status migration`, `Community 46`, `Community 48`, `Community 49`, `Community 51`, `Community 52`, `Community 53`, `Community 54`, `Issue 1 version 2 documentation`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `SafeLogger` connect `Logger & Secret Redaction Engine` to `Data Models & Pipeline Staging`, `Global settings & config generation`, `Feed configuration and dry-run diagnostics`, `Image Compression utilities`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **What connects `Synchronous implementation of STATUS.md update to be offloaded to thread.`, `Automatically update the STATUS.md dashboard without blocking the event loop.`, `Stage 1: Fetch and Score Raw News.` to the rest of the system?**
  _206 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Core Curation & Broadcaster Logic` be split into smaller, more focused modules?**
  _Cohesion score 0.07692307692307693 - nodes in this community are weakly interconnected._
- **Should `Data Models & Pipeline Staging` be split into smaller, more focused modules?**
  _Cohesion score 0.062342342342342344 - nodes in this community are weakly interconnected._
- **Should `Logger & Secret Redaction Engine` be split into smaller, more focused modules?**
  _Cohesion score 0.06565656565656566 - nodes in this community are weakly interconnected._