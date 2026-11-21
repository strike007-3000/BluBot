# 📖 BluBot Manual

How BluBot curates, writes, reviews, publishes, persists, and is operated. Release history lives in [CHANGELOG.md](../CHANGELOG.md); this manual describes current behavior only.

**Contents**
1. [Overview](#1-overview)
2. [Sources](#2-sources)
3. [Curation & Scoring](#3-curation--scoring)
4. [Writing Engine](#4-writing-engine)
5. [Telegram Control](#5-telegram-control)
6. [Publishing](#6-publishing)
7. [Interaction Engine](#7-interaction-engine)
8. [State, Archive & Telemetry](#8-state-archive--telemetry)
9. [Reliability & Security](#9-reliability--security)
10. [Configuration](#10-configuration)
11. [Operations](#11-operations)

---

## 1. Overview

BluBot is an **impact-aware** AI news curator: it separates signal from noise by looking for **product shifts** (real code) and **technical gems** (research papers, deep engineering blogs), and explains the useful consequence in plain language instead of repeating headlines or writing promotional copy.

### Pipeline at a glance
```
Sources ─► Score & cluster ─► Pick lead story ─► Synthesize (Gemini, 3 platform drafts)
   ─► Media decision ─► Telegram review ─► Reserve story ─► Broadcast ─► Settle state ─► Archive
```
Each run is one story. Scheduled runs go through the full path; the breaking lane skips the Telegram review (see [Breaking-news lane](#breaking-news-lane)).

### Platform targets and limits
Drafts are generated for each platform in one request, then repaired to a safety-buffered maximum so pagination markers such as `(1/2)` never push a post over the API limit.

| Platform | Draft style | Target | API limit | Buffered max | Hashtags (default) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Bluesky | Direct, specific observation | 280 | 300 | 290 (limit − 10) | off (`ENABLE_HASHTAGS_BSKY`) |
| Mastodon | Technical overview with relevant hashtags | 450 | 500 | 485 (limit − 15) | on (`ENABLE_HASHTAGS_MASTODON`) |
| Threads | Conversational explanation; a question only when it follows naturally | 450 | 500 | 490 (limit − 10) | on (`ENABLE_HASHTAGS_THREADS`) |

---

## 2. Sources

The registry (`SOURCE_REGISTRY` in `src/config.py`) holds **51 RSS feeds plus 4 API sources** with stable IDs across 8 tiers. Each tier sets the base score a story starts with.

| Tier | Base | Sources |
| :--- | :--- | :--- |
| Research labs | +30 (Google AI +28; Google Research, Mistral +25) | OpenAI, DeepMind, Anthropic (community-maintained mirror; no official feed exists), Hugging Face Blog, Google AI Blog, Google Research, Mistral |
| Enterprise AI | +22–+27 | Microsoft Research, AWS ML Blog, NVIDIA Deep Learning (+27), Apple ML Research (+22) |
| Practitioner | +20 | Simon Willison, Interconnects, Latent Space, One Useful Thing, Maarten Grootendorst, Sebastian Raschka, Jack Clark |
| Open source | +18 (Claude Code releases +16) | Hugging Face Transformers, vLLM, Ollama, PyTorch, llama.cpp, Claude Code releases |
| Infrastructure / business | +15 | Together AI, ServeTheHome, Semiconductor Engineering, Sequoia Capital, CB Insights |
| Journalism | +12 | The Verge AI, Ars Technica AI, MIT Tech Review, IEEE Spectrum, The Decoder, Wired AI, VentureBeat AI, TechCrunch AI, 404 Media, Silicon Angle, The Sequence, MarktechPost, AI Accelerator Institute |
| Academic | +10 | arXiv cs.LG, BAIR Blog, ML Mastery |
| Policy & critical voices | +10 / +5 | AI Incident Database, EU AI Act Tracker (+10); AI Snake Oil, Gary Marcus, Algorithmic Bridge, Victoria Krakovna (+5) |

### API sources
API entries (`kind: api`) are scored and clustered like feed items but are never passed to Feed Vanguard or the RSS audit tooling.

| Source | Base | Rules |
| :--- | :--- | :--- |
| Hugging Face Trending | +18 | Public Hub models API; admits only models with a usable model-card excerpt |
| GitHub Fast-Rising Repositories | +16 | GitHub Search API for repos tagged `llm`, `generative-ai`, or `machine-learning`; ranked by star velocity (capped bonus); README excerpt via `Range: bytes=0-8191`; HTTPS `github.com` URLs only; 403/429 handled gracefully. `GITHUB_TOKEN` raises the rate limit |
| Hugging Face Daily Papers | +18 | Upvote-ranked; needs 10+ upvotes |
| Hacker News | +15 | Algolia search for LLM/AI queries; needs 50+ points |

### Feed Vanguard (RSS health)
Every run starts with a pre-flight scan (`VanguardManager._check_feed()`): fetch with a 15-second timeout, require HTTP `200`, then `feedparser.parse()`. A feed is unhealthy if it is empty or malformed with no entries. Failing feeds are soft-disabled with backoff instead of being deleted:

| Failure | Result |
| :--- | :--- |
| 1st | Warning only; feed stays active |
| 2nd / 3rd / 4th | Silenced 1 h / 12 h / 24 h |
| 5th and later | Silenced 48 h (maximum); `TERMINAL` flag from the 6th |

When the backoff expires the Vanguard retries; success restores the feed. State lives in the Gist file `feed_vanguard.json` (authoritative when configured) with a local cache `broken_feeds.json`; deleting a URL from the cache forces a recovery attempt on the next run. Run `python scripts/feed_audit.py` for a full health report.

---

## 3. Curation & Scoring

A story's score is its source tier plus the adjustments below (computed in `calculate_relevance_score`; every component is recorded in `_score_debug`).

| Component | Effect |
| :--- | :--- |
| High-signal keywords (e.g. *SOTA, agentic, world model, open weights*) | +12 |
| Momentum products (title contains a product in `MOMENTUM_PRODUCTS`, refreshed weekly) | +18 |
| Consensus synergy (≥2 distinct publisher domains cluster together) | +15 |
| Watchlist match (see below) | +3 to +8, capped at +8 |
| Topic diversity (topic already in `recent_topics`) | −12 |
| Category recurrence (category among the last 10 published; the latest repeat counts fully, the one before ½, then ⅓…) | −5 per weighted repeat |
| Time decay | −0.5 per hour since publication |

### Story clustering
1. **Normalization**: `normalize_headline()` strips publisher suffixes and stopwords, tokenizes, and extracts version numbers into a separate set.
2. **Matching**: headlines match pairwise (greedy) when both have ≥2 tokens, version sets do not conflict, and the Jaccard similarity of tokens plus versions is ≥0.25 with ≥2 shared items.
3. **Corroboration**: a cluster with ≥2 distinct publisher domains earns the synergy bonus.
4. **Lead selection**: highest score wins (ties: source base score, then publication time). Supporting source names and links attach to the lead.
5. **Selection integrity**: URLs are canonicalized (`normalize_url`) before clustering; the semantic-duplicate filter runs after clustering and before the final eight-article limit and lead-category policy, so fresh lower-ranked stories can refill the list. `/brief` keeps the full seven-day archive.

`_score_debug` also carries `cluster_size`, `cluster_lead`, `supporting_sources`, and `consensus_bonus_reason` (`domain_corroboration` or `none`).

### Watchlists
`/watch <topic>` adds a persistent topic (max 10, ≤100 characters, no URLs, no duplicates). Entries live in `seen_articles.json` under `watch_topics`:
```json
{"topic": "llama 4", "display_name": "Llama 4", "created": "2026-08-01T12:00:00+00:00", "keywords": ["llama"], "last_matched": null}
```
Matching uses word-boundary regex (so "ai" never matches "maintenance"): exact topic in title `+8`, keyword in title `+5`, keyword in summary `+3`; the best match across all watches is used and capped at `+8`.

### Full-article grounding
Synthesis receives only the **lead story** (title, source name, summary, and up to 6,000 characters of article body fetched with the SSRF-safe fetcher, falling back to the RSS summary) as a labeled untrusted JSON block. Any platform draft sharing no word (3+ characters) with the lead story is rejected and the next model is tried.

### Grounded briefings (`/brief <topic>`)
1. `fetch_news()` with `days_lookback=7` and no seen-link filter returns the full seven-day archive.
2. `article_matches_topic()` filters by the topic (same logic as `/topic`); matches are clustered.
3. Up to 15 articles go to Gemini for an executive summary, 3–5 key developments with `[Title](URL)` citations, and explicit consensus highlighting.
4. The briefing is delivered to Telegram with `smart_split()` at the 4,096-character message limit, with no chunk cap.

Topics over 100 characters or containing URLs are rejected (`brief_invalid`); no matches replies "No matching source items were found over the past 7 days." In dry-run mode Gemini is bypassed and a mock briefing listing the matches is returned.

---

## 4. Writing Engine

### Shared natural-writing policy
Every text path (daily synthesis, mentor fallback, Telegram remixing, interaction replies, `/brief`) reuses `NATURAL_WRITING_GUIDE`: supplied evidence, direct verbs, plain language, varied sentence rhythm. It rejects generic setup, unsupported importance claims, forced questions, binary "not X, but Y" contrasts, fake revelations, stacked fragments, and recap endings. `SOURCE_CONTENT_SAFETY` forbids following instructions embedded in RSS content, and summaries are capped by `FEED_SUMMARY_MAX_CHARS` (500).

### Angle and structure rotation
One consistent peer-like voice, rotating the analytical angle:
- **Angle pool**: mechanism and consequence, developer workflow, strategic consequence, concise explanation, concrete trade-off. `summarize_news` removes the previous angle (saved as `last_dialect`, a historical field name kept for state compatibility) before selecting.
- **Structure**: least-recently-used choice among strategic shift, practical workflow, risk/verification, and enterprise ROI.

### Sessions and manual runs
- **Sessions** follow actual execution time: Night Reflection (00–06 UTC), Morning Intelligence (06–11), Midday Briefing (11–15), Afternoon Deep Dive (15–19), Evening Synthesis (19–24).
- **Scheduled runs**: 06:17, 12:17, 18:17 UTC, Monday–Friday.
- **Manual intercept**: GitHub `workflow_dispatch` runs get an "(Intercept)" label and are treated as ad hoc; local runs and non-scheduled CI events bypass the weekend-rest window (push and pull-request events do not get the label).

### Model failover and routing
- **Priority chain**: `gemini-3.5-flash-lite` → `gemini-3.8-flash` → `gemini-4-hydrogen` → `gemini-3.7-flash` → `gemini-3.6-flash` → `gemini-2.5-flash-lite`, rotating immediately on 503, 429, 400, or 404.
- **Discovery**: the models available to the configured key are listed and only exact matches from the approved list are kept; if discovery fails the defaults stay available for runtime failover.
- **Task routing**: alt-text uses `gemini-3.5-flash-lite` then `gemini-2.5-flash-lite` (multimodal, with a neutral local fallback); visual prompts use `gemini-3.5-flash-lite`; `GEMINI_MODEL` handles interactive replies, on-demand topics, and `/brief`.
- **Output repair**: strips stray markdown, applies the platform hashtag policy, and shortens overlong output without splitting URLs. If synthesis fails or volume is low, a mentor fallback post is produced (except `/news`, which fails instead; see below).
- **Thinking**: `THINKING_BUDGET` (default 1,024) applies to Gemini 2.0/2.5 models and is bypassed for Gemma.

---

## 5. Telegram Control

The bot only processes updates from `TELEGRAM_USER_ID`. Telegram requests use 15 s connect / 30 s read / 60 s write timeouts for CI photo uploads.

### Approval queue
Before publishing, the bot sends the draft and image card to your chat as one authoritative preview (photo if media is present, else text) with these buttons:

| Button | Action |
| :--- | :--- |
| `🔵 Bluesky` `🧵 Threads` `🐘 Mastodon` | Switch the preview tab in place |
| `📋 Show All` / `📑 Show Tabs` | Toggle between one tab and all three drafts |
| `✨ Remix <platform>` / `✨ Remix All` | Reply with an instruction ("make it punchier"); Gemini rewrites the active tab (or all) with link-safe truncation |
| `🏷 Source tag: ON/OFF` | Shown only when the source has a verified account (see [Source tags](#source-tags)) |
| `✅ Approve` / `❌ Reject` | Publish / abort the run |
| `🔄 New Post (skip story)` | Marks the lead story as seen and re-runs for the next-best story (max 3 per run; hidden for `/topic` and `/news` drafts and on the last retry); Reject does not skip the story |
| `🎨 Regenerate Image` | New isometric prompt from the latest draft, fresh image from the provider chain, regenerated alt-text, preview media updated |

Other behavior:
- **Waiting**: the run polls up to `TELEGRAM_TIMEOUT_MINUTES` (default 5) using `time.monotonic()`, so system clock changes cannot skew the timeout.
- **Auto-post fallback**: scheduled runs post the draft if you do not respond. User-supplied topics never auto-post (see [Fail-closed approval](#fail-closed-approval)).
- **Manual editing**: reply to the draft with new text or send `/edit <new text>`; lengths are validated against the buffered limits (Bluesky 290, Mastodon 485, Threads 490) with a warning if the text will split or truncate. `/remix_all <instruction>` remixes every platform.
- **Safe truncation**: a deterministic URL policy never bisects a link. If a URL cannot fit a platform's budget it is omitted from the text and logged. Bluesky still shows the source as an external link card via `lead_link`; Mastodon and Threads publish text and media only, so an omitted link is not broadcast there.
- **Score receipt**: a separate message explains the pick (`📊 Score 63 (Source +30, Momentum +18, corroborated by 3 sources)`) with links to the lead and supporting articles, built from `_score_debug`.
- **Post-broadcast notifications**: three plain-text messages (Bluesky, Threads, Mastodon) report `✅ Published`, `❌ Failed (<error>)`, or `⚪ Not configured / not attempted`, the requested delivery mode, and the approved draft. A failure on one network never blocks the others or state settlement.
- **Threads media**: regenerating or changing the image creates a replacement `MediaAsset` with `public_url=None`, so Threads can never publish the originally crawled OpenGraph image after you approved a different one.

### Command reference
Commands are read when a run starts, from messages up to 15 minutes old (so send them shortly before a scheduled run, or trigger a manual run). The breaking lane never reads them.

| Command | Description |
| :--- | :--- |
| `/topic <keyword>` / `/curate <keyword>` | Curate and broadcast a post on a topic. Matching articles in the live feeds ground the post (original links and facts); with no match it falls back to raw synthesis |
| `/news <headline> [public url]` | Report a **confirmed** event. Skips feed matching and states your headline as fact using only the headline plus the URL's fetched title/description (no invented specs, numbers, dates, or quotes). The URL becomes the lead link and the ledger source is its host ("Manual news" if linkless). Not swallowed by the Friday roundup. Missing headline or non-public URL returns a usage hint |
| `/brief <keyword>` | 7-day executive briefing delivered to Telegram (see [Grounded briefings](#grounded-briefings-brief-topic)) |
| `/watch <topic>` / `/unwatch <topic>` / `/watches` | Add, remove (exact match, case-insensitive), or list watchlist topics |
| `/threads_refreshed [YYYY-MM-DD]` | Record the Threads token refresh date (see below) |
| `/edit <text>` | Replace the draft text during approval |
| `/remix_all <instruction>` | Remix all platform drafts during approval |
| `/skip` | Reply to a regeneration feedback prompt to use default settings |

### Fail-closed approval
`/topic`, `/curate`, and `/news` posts never auto-publish. If approval times out or errors, the bot warns you, posts nothing, and re-queues the request in `pending_topic.json` (`{topic, kind, timestamp}`) for the next run. `/news` synthesis also retries 3 times on Gemini errors such as 503; if it still fails it warns you, re-queues, and fails the run rather than substituting an unrelated mentor post. `pending_topic.json` is saved and restored with the Bluesky session cache so re-queued requests survive the ephemeral runner.

### Source tags
`src/tagging.py` holds `SOURCE_HANDLES`, a hand-verified map from source ID to account per platform. When the lead story's source is listed:
- The Bluesky and Mastodon drafts end with `cc @handle` (Mastodon uses `@user@instance`). Threads is never tagged.
- Tags are applied only on the approval path, so breaking-lane posts are never tagged. The `🏷 Source tag` button adds or removes the tag; the change is committed only after the preview updates successfully.
- A tag is skipped when it would push the draft past the buffered limit.
- Bluesky: each `@handle` resolves to a DID and becomes a real mention facet; if resolution fails it stays plain text and the post still goes out. Mastodon needs no extra handling.

To add a source, confirm the account really belongs to it (Bluesky: `app.bsky.actor.getProfile`; Mastodon: webfinger) and add its ID from `SOURCE_REGISTRY`.

### Threads token reminder
Threads long-lived tokens last 60 days. Send `/threads_refreshed [YYYY-MM-DD]` after each refresh (defaults to today; future dates are rejected). The date is stored in the Gist file `threads_token.json`, and unlike other commands the message may be up to 24 hours old. From 5 days before expiry, each scheduled run sends one Telegram reminder per day (`last_reminded` prevents repeats) until a new date is recorded. Nothing is sent until the first date exists, and the breaking lane never sends it. Refreshing is manual (`GET https://graph.threads.net/refresh_access_token?grant_type=th_refresh_token&access_token=<token>`), then update the secret.

---

## 6. Publishing

### Threading (the Weaver)
- **Smart split**: `smart_split` chunks at natural boundaries (paragraph `\n\n`, then sentence `. `, then spaces) and appends `(1/N)` markers.
- **Cap**: `MAX_THREAD_PARTS=2` (default). Longer text is truncated with `...` and relies on the linked article.
- **Chaining**: Bluesky uses depth-aware `root`/`parent` references; Mastodon uses `in_reply_to_id`; Threads publishes sequential containers with a `reply_to` link.
- **Rhythm**: randomized 10–30 s pauses between posts to avoid burst-spam detection.
- **Zero-duplicate ("catch & log")**: if a stage fails after publishing part of a thread, the exception is logged and state is persisted immediately with the post IDs already broadcast, so the next run does not post the same content again.

### Image and media pipeline
`IMAGE_PROVIDER` defaults to **Cloudflare Workers AI** (`@cf/black-forest-labs/flux-1-schnell`), then falls back to **Hugging Face**; `huggingface`, `nvidia`, and `imagen` can be selected explicitly, and Imagen never runs implicitly. One media decision produces a single canonical `MediaAsset` that platform adapters render: Bluesky uses an external link card (or an image embed for generated assets), Mastodon uploads image bytes (degrading to text on upload errors), and Threads uses public OpenGraph URLs only (generated assets without a public URL fall back to text).

```
              [Scrape Article URL]
                       │
          [og:image in metadata?]
           /                    \
      (found)                (not found)
         ▼                          ▼
  [Normalize URL]         [Gemini isometric prompt]
         ▼                          ▼
  [Filter generic logos]   [Cloudflare → Hugging Face]
         ▼                          ▼
  [Download original]       [Decode generated image]
         └────────────┬─────────────┘
                      ▼
           [RGB normalization]
                      ▼
           [Pillow optimizer ≤ 900 KB]
                      ▼
          [Broadcast to platforms]
```
1. **Validation**: OpenGraph candidates are checked for dimensions, size, aspect ratio, decodability, and known placeholder logos (`GENERIC_IMAGE_PATTERNS`); protocol-relative URLs are normalized.
2. **Generation**: Cloudflare prompts are capped at 2,048 characters and use FLUX's default parameters. Exhausting the chain returns no generated image.
3. **RGB normalization**: CMYK/grayscale sources (e.g. ArXiv thumbnails) are converted to RGB so they do not become black or white boxes.
4. **Compression**: JPEG at quality 85, then 80 down to 40 in steps of 10, in memory, until the file is ≤ 900 KB (`compress_image`).
5. **Alt text**: Gemini Vision writes screen-reader alt text under 100 characters for generated or attached images, broadcast to Mastodon and Threads.

### Hashtags
Per-platform toggles (see the table in [Overview](#platform-targets-and-limits)). Standalone hashtags are deleted and inline ones lose their `#` (`#AI` → `AI`).

### Breaking-news lane
`breaking_news.yml` runs daily at 09:47, 15:47, and 21:47 UTC with `BREAKING_ONLY=true`. It posts only when the top story scores ≥ 40 and is under 6 hours old, with a 3-hour cooldown after any post and at most one breaking post per rolling 24 hours (scheduled slots are unaffected). Otherwise it exits before synthesis (no Gemini calls, no Telegram prompt). A qualifying post skips Telegram approval (the final post is still pushed to Telegram) and is abandoned if synthesis picks a different lead than the one that qualified. The archive shows a Breaking badge and filter. Tunables: `BREAKING_MIN_SCORE`, `BREAKING_MAX_AGE_HOURS`, `BREAKING_COOLDOWN_HOURS`.

### Friday roundup
Scheduled Friday evening runs (18:17 UTC) publish a weekly digest instead of a single story (also `--roundup` / `FORCE_ROUNDUP=true`).
- **Stories**: ledger entries with `kind == "post"` in the current ISO week, ranked by live Bluesky engagement (likes + reposts + replies + quotes, fetched unauthenticated from the public AppView), falling back to recency; up to 5.
- **Format**: deterministic, no AI: `This week in AI (YYYY-Www)` then numbered `Title\nURL` paragraphs, up to 6 thread parts. Pre-broadcast verification confirms every selected URL survives platform chunking.
- **Decision**: roundup already reserved or published for the week → skip the run; 0 eligible stories → normal Friday post; 1–5 → publish the roundup.

### Bluesky source receipts
With `ENABLE_SOURCE_RECEIPTS_BSKY=true` (default `false`), a corroborated Bluesky post gets a best-effort reply listing up to two aligned source links. It runs only after the root post is durably settled and never affects broadcast success.

---

## 7. Interaction Engine

After broadcasting, `bot.py` handles mentions and replies:
1. **Polling**: Bluesky and Mastodon notifications (`mention`, `reply`) and recent Threads posts and replies, limited to the last 24 hours.
2. **Post context**: when a reply's `root_uri` matches a `thread_roots` entry in the ledger, that post's title, summary, and URL (first 500 characters) join the reply prompt so answers stay grounded; unmatched replies use the plain prompt.
3. **Selective engagement**: `MENTION_REPLY_PROB` (0.8) and `COMMENT_REPLY_PROB` (0.5), at most `INTERACTION_LIMIT` (5) interactions per run, a 10–30 s human-like delay, and notification IDs tracked in `seen_interactions.json` to prevent double replies.
4. **Generation**: `generate_interactive_reply` disables thinking and caps output at 100 tokens; 503 errors retry up to 3 times (2 s, 4 s backoff). `INTERACTIVE_REPLY_INSTRUCTION` adds reply rules to the shared writing policy: address what the person said (no persona intros, canned thanks, or forced lessons), give a relevant supported detail, no hashtags, emojis only for a specific technical concept, under 280 characters.
5. **Threading**: Bluesky keeps `root`/`parent` references; Mastodon chains by status ID.

Settings: `ENABLE_INTERACTIONS` (default `true`), `ENABLE_BSKY_COMMENT_REPLIES` (`true`), `ENABLE_MASTODON_COMMENT_REPLIES` (`false`), `ENABLE_THREADS_COMMENT_REPLIES` (`false`). `MENTION_REPLY_PROB`, `COMMENT_REPLY_PROB`, `INTERACTION_LIMIT`, and `AUTO_LIKE_INTERACTIONS` (default `true`) are constants in `src/config.py`, not environment variables.

---

## 8. State, Archive & Telemetry

### Persistence
State is stored in `seen_articles.json` (`schema_version: 2`, revision counter, `updated_at`). Recovery and write order:
1. **Remote Gist (when configured)** is the authoritative state, compared with local data by schema version, revision, and timestamp.
2. **Two-phase reservation**: a `pending_stories` reservation is written to Gist and local state before broadcasting (publication aborts if the Gist write fails) and becomes `published` on success.
3. **Local primary and backup**: atomic writes (`.tmp` → `seen_articles.json`) under an advisory `FileLock`, rotating the previous valid state to `.bak`. If the Gist write fails during settlement, local state is saved with `unsynced_gist: true`. A corrupted or missing primary falls back to `.bak`, then the Gist.
4. **Timestamps**: `source_published_at` (feed-supplied), `created_at` (reservation), and `published_at` (broadcast).
5. **Concurrent settlement**: the persistence lock merges publication entries, counters, and bounded topic/category/style histories so overlapping runs do not overwrite each other. Watch topics come from the remote state so deleted topics are not resurrected.

Separate Gist files hold `feed_vanguard.json` (feed health) and `threads_token.json` (refresh date); they stay out of the merged article state.

### Published-post ledger
Settlement appends to `published_posts` via `append_published_post()` (capped at 500 entries, never time-pruned): canonical URL, title, topic (default "General"), supporting links, `published_at`, per-platform roots (`posts.bluesky.uri`/`cid`/`receipt_uri`, `posts.mastodon.id`, `posts.threads.id`; only platforms that succeeded), and continuity fields (`entry_kind` "original" or "update", `story_fingerprint`, `parent_story_fingerprint`, `update_number`, `source_url`, `thread_roots`, `idempotency_key`). Legacy entries default safely to original stories. The separate `recent_stories` window (14 days) drives duplicate suppression.

### Story continuity
With `STORY_UPDATE_DETECTION_ENABLED=true`, new articles are matched against the last 72 hours of published stories using token overlap, explicit product versions, changed numeric facts, normalized status verbs, and material summary differences, yielding `CONFIDENT_UPDATE`, `POSSIBLE_MATCH`, or `NO_MATCH`. Only confirmed developments bypass semantic-duplicate filtering; publisher names or corroborating outlets alone count as syndicated coverage. Confident updates thread directly under the original root on Bluesky, Mastodon, and Threads, with link-preserving truncation (parents published before v3.37.0 get fingerprints and roots derived from legacy metadata).

### STATUS.md and engagement
Live telemetry (operational status, last run, session mode, current topic) is written to `STATUS.md`, not `README.md`, so runs never cause README rebase conflicts. The file is bootstrapped if missing, the topic is sanitized so it cannot break the table (whitespace collapsed, backslashes removed, `|` escaped, 120-character cap), and scheduled runs write it to the `automated/state` branch, from which `sync_status.yml` copies it to `main`. A 7-day engagement block (posts, likes, reposts, replies) is refreshed by `src/engagement.py` from public Bluesky data; reply counts exclude your own account, so multi-part threads do not inflate them (falls back to the raw `replyCount` if the thread lookup fails).

### Archive site
`scripts/build_archive.py` compiles the ledger into a static GitHub Pages site (`index.html`) and an RSS 2.0 feed (`feed.xml`, 50 items) at `https://strike007-3000.github.io/BluBot/`, built by `pages.yml` with no new secrets, paid APIs, databases, or runtime servers. Gist loading is fail-closed.
- **Source Trust Dashboard**: *Stories* (ledger entries, up to 500), *Sources* (distinct lead-source domains), *Corroborated* (eligible stories with ≥1 valid public supporting domain different from the lead, as a ratio and percentage; roundups excluded; "—" when none are eligible), *Receipts* (eligible corroborated Bluesky stories with a proof reply, `posts.bluesky.receipt_uri`), *Engagement* (7-day public Bluesky metrics, also limiting the "Most engaged" view; degrades cleanly if unavailable), plus top-5 source and category bars.
- **Timeline**: original stories link to their updates, with Update and Breaking badges.
- **Search and filter**: client-side text search; type (News, Repositories, Models, Roundups, Updates); trust status (Corroborated, Receipt available, Single-source); sorting. Vanilla JS, no frameworks or build step; all stories stay readable without JavaScript. Light/dark mode follows `prefers-color-scheme` and persists an explicit choice.
- **Historical fallbacks**: older entries fall back to the hostname for source, "General" for category, GitHub URLs → Repository, Hugging Face URLs → Model, and `kind == 'roundup'` → Roundup.

---

## 9. Reliability & Security

### Reliability
- **Non-blocking I/O**: persistence (`load_seen_articles`/`save_seen_articles`, interactions, session string), bio updates, status telemetry, and Feed Vanguard saves run in worker threads via `asyncio.to_thread`, so the event loop is never blocked.
- **Resilient RSS parsing**: raw bytes (`response.content`) with safe attribute lookups (`getattr(entry, 'link', None)`); invalid entries are skipped so one malformed feed cannot drop a source.
- **Decompression-bomb protection**: `Image.MAX_IMAGE_PIXELS` is capped at 10,000,000.
- **Structured logging**: `SafeLogger` emits JSON in CI (`LOG_FORMAT=json`) or colored text locally (`pretty`).
- **Bio management**: the profile shows an active day streak and the current topic (`AI signal, zero noise. Day 68. | Currently tracking: …`), trimmed to 250 characters (Bluesky allows 256, Mastodon 500).

### Security
- **SSRF protection**: the metadata scraper (`get_link_metadata`) validates the destination and **pins the connection to the validated IP** (original `Host` header and TLS server name, one connection per request), refusing local, private, and internal addresses.
- **Secret redaction**: `SafeLogger` masks secrets by keyword and by statistical entropy (JWTs, API tokens), in both log formats.

### Supply chain (`uv`)
`requirements.in` lists direct dependencies; `requirements.txt` is the generated Python 3.13 lockfile with SHA-256 hashes (`--generate-hashes`) so `pip` rejects mismatched packages. To update:
1. Edit `requirements.in`.
2. `uv pip compile requirements.in --python-version 3.13 --generate-hashes --no-annotate --output-file requirements.txt`
3. Commit both files.

### CI secrets and workflow hardening
- **Environment-scoped secrets**: all credentials are GitHub *environment* secrets in a `production` environment restricted to deployment branch `main`; repository-level secrets are not used. Otherwise anyone able to push a branch could run a `workflow_dispatch` workflow from it and exfiltrate every secret.
- **Every secret-reading job declares `environment: production`** (`post_pipeline`, `linkedin_weekly`, `weekly_config_update`, `sync_status`, the `pages` build job). `src/tests/test_workflow_environments.py` enforces this; `GITHUB_TOKEN` is exempt.
- **Pinned actions**: every `uses:` is a full commit SHA with a `# vN` comment (resolve a new pin with `gh api repos/<owner>/<repo>/commits/<tag> --jq .sha`).
- **No tokens in URLs**: `post_pipeline.yml` authenticates git with a masked `http.extraheader` via `GIT_CONFIG_*` env vars.
- **Least privilege**: `test.yml` has `contents: read`; the `pages.yml` build job has `contents: read` and `pages: read` (deploy keeps `pages: write` and `id-token: write`); `release.yml` passes values through `env:` rather than `${{ }}` inside `run:`.
- **Rotating secrets**: replace the value in the `production` environment, then revoke the old credential at its provider. `REPO_TOKEN` must be a fine-grained, single-repository token (Contents and Pull requests read/write) with an expiry date; an expired token silently breaks `weekly_config_update` and `sync_status`. If a secrets manager such as Infisical syncs into GitHub, target the `production` *environment*, not repository secrets.

---

## 10. Configuration

### Secrets and environment variables
Add secrets to the GitHub `production` environment (see [CI secrets](#ci-secrets-and-workflow-hardening)). Optional values have defaults.

| Variable | Description |
| :--- | :--- |
| `GEMINI_KEY` | Google AI Studio key (also used for model discovery) |
| `GEMINI_MODEL` | Model for replies, on-demand topics, and `/brief` (default `models/gemini-3.5-flash-lite`) |
| `THINKING_BUDGET` | Thinking budget for Gemini 2.0/2.5 (default 1024; bypassed for Gemma) |
| `BSKY_HANDLE`, `BSKY_APP_PASSWORD` | Bluesky account and app password |
| `MASTODON_ACCESS_TOKEN`, `MASTODON_BASE_URL` | Mastodon token and instance URL |
| `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID` | Threads long-lived token and user ID |
| `GIST_ID`, `GIST_TOKEN` | Private Gist for state (token needs `gist` scope) |
| `GITHUB_TOKEN` | Optional PAT or Actions token for higher GitHub REST limits (1,000 req/hr) when fetching fast-rising repositories |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | Workers AI image generation (default provider) |
| `HUGGINGFACE_API_KEY`, `HUGGINGFACE_IMAGE_MODEL` | Final image fallback and its model (default `stabilityai/stable-diffusion-3-medium-diffusers`) |
| `NVIDIA_KEY` | Optional NVIDIA image key and legacy Hugging Face token fallback |
| `IMAGE_PROVIDER` | `cloudflare` (default), `huggingface`, `nvidia`, or explicit-only `imagen` |
| `ENABLE_IMAGE_GEN` | Generated-image fallbacks (default `true`) |
| `ENABLE_BIO_MGMT` | Profile bio updates (default `true`) |
| `ENABLE_INTERACTIONS` | Mention/comment processing (default `true`) |
| `ENABLE_BSKY_COMMENT_REPLIES` / `ENABLE_MASTODON_COMMENT_REPLIES` / `ENABLE_THREADS_COMMENT_REPLIES` | Comment replies per platform (default `true` / `false` / `false`) |
| `ENABLE_HASHTAGS_BSKY` / `_MASTODON` / `_THREADS` | Hashtags per platform (default `false` / `true` / `true`) |
| `MAX_THREAD_PARTS` | Maximum posts per thread (default `2`) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID` | Optional Telegram bot token and your numeric user ID |
| `TELEGRAM_TIMEOUT_MINUTES` | Approval polling timeout (default `5`) |
| `ENABLE_TELEGRAM_APPROVAL` | Draft approval (default `true`; no effect without bot token and user ID) |
| `LINKEDIN_TELEGRAM_TIMEOUT_MINUTES` | Weekly LinkedIn draft Telegram budget (default `10`) |
| `LOG_FORMAT` | `pretty` locally, `json` in CI by default |
| `DRY_RUN` | Local use: skips all external posting and persistence and injects mock credentials |
| `REPO_TOKEN` | PAT used by `weekly_config_update.yml` and `sync_status.yml` so their PRs and syncs trigger required checks |

### Repository variables and tunables
| Variable | Description |
| :--- | :--- |
| `ENABLE_SOURCE_RECEIPTS_BSKY` | Bluesky corroboration receipts after durable settlement (default `false`) |
| `STORY_UPDATE_DETECTION_ENABLED` | Story continuity detection and threaded updates (default `false`) |
| `BREAKING_MIN_SCORE` / `BREAKING_MAX_AGE_HOURS` / `BREAKING_COOLDOWN_HOURS` | Breaking-lane thresholds (default `40` / `6` / `3`) |
| `FORCE_ROUNDUP` | Force the Friday roundup (also `bot.py --roundup`) |

The typed `Settings` singleton (`src/settings.py`) reads all of these; `DRY_RUN` injects mock credentials so synthesis can be checked with only AI keys.

---

## 11. Operations

### CI/CD workflows
| Workflow | Trigger | Purpose |
| :--- | :--- | :--- |
| `daily_post.yml` | Cron 06:17, 12:17, 18:17 UTC Mon–Fri; manual | Calls `post_pipeline.yml` (runs `bot.py`; commits `STATUS.md` to `automated/state`; dispatches `pages.yml` after a real post). Serialized by the `bsky-persistence-state` concurrency group |
| `breaking_news.yml` | Cron 09:47, 15:47, 21:47 UTC daily; manual | Calls `post_pipeline.yml` with `breaking_only: true`; same concurrency group |
| `post_pipeline.yml` | Called by the two above | Reusable pipeline holding secrets, cache, and state-commit logic |
| `linkedin_weekly.yml` | Cron Sunday 12:00 UTC; manual | Weekly LinkedIn draft (below); own `linkedin-weekly` concurrency group so a Telegram wait never blocks the daily state group |
| `sync_status.yml` | After a successful Daily AI News Post or Breaking News Post | Copies `STATUS.md` from `automated/state` to `main` via the GitHub Contents API (uses `REPO_TOKEN`) |
| `pages.yml` | Dispatched by `post_pipeline.yml` after a real post; manual | Builds and deploys the archive and RSS feed |
| `weekly_config_update.yml` | Cron Friday 02:00 UTC | Refreshes momentum products and keywords; opens/updates the `automated/config-update` PR |
| `test.yml` | Pull requests to `main` | `pytest src/tests/` on Python 3.13 |
| `codeql.yml` | Push/PR to `main`; cron Monday 02:30 UTC | CodeQL analysis |
| `release.yml` | `v*` tag push, or merged PR to `main` | Tags from `VERSION` if needed and creates a GitHub Release whose notes are the matching `CHANGELOG.md` entry |

Releases require a `CHANGELOG.md` entry whose line contains `v<VERSION>`.

### Weekly config update
`scripts/update_config_keywords.py` (run by `weekly_config_update.yml`) fetches recent headlines and asks Gemini for the top 10 momentum products and top 12 high-signal keywords. It also lists hosts cited by 2+ practitioner feeds (excluding registered sources and big platforms) as "Cited domains" in the PR body (`pr_body.md`); nothing is added automatically, and a human decides whether to register a feed. The workflow updates the `automated/config-update` branch with `REPO_TOKEN` (so required CI and CodeQL checks run) and refreshes an existing PR with `gh pr edit`.

### Weekly LinkedIn draft
`linkedin_weekly.py` shortlists three of the week's published stories in Telegram, drafts one LinkedIn post in the owner's voice with an optional personal take, verifies it against the source (rules, numbers, claims), and delivers it for manual posting. **Nothing is posted to LinkedIn.** It has one Telegram budget (`LINKEDIN_TELEGRAM_TIMEOUT_MINUTES`, default 10); a timeout auto-drafts the first story, labelled unreviewed. It is independent of the daily bot and the Friday roundup.

### Local diagnostics
```bash
python scripts/diagnostic.py                      # interactive menu
python scripts/diagnostic.py --mode engagement    # non-interactive; modes: scoring, dry-run, images, gist, gemini, drafts, hf, github, engagement, continuity
python scripts/check_tokens.py                    # credential checker
```
You can test the whole bot locally **without social credentials**: if `GEMINI_KEY` or `NVIDIA_KEY` is missing the script prompts for it, and `Settings.from_env()` injects mock values (for example `BSKY_HANDLE`) during dry runs. Option 2 (*Full Pipeline Dry Run*) shows a draft review of exactly what would post; option 6 (*Multi-Platform Drafting & Telegram State Simulation*) checks JSON parsing, writing-policy availability, platform limits, URL-safe repair, and Telegram preview rendering offline.

**Credential checker**: verifies secrets (for example after Infisical pushes them to GitHub) without posting. Menu: 1 Bluesky, 2 Threads, 3 Mastodon, 4 Gemini, 5 NVIDIA, 6 Telegram, 7 Gist, 8 Cloudflare, 9 Hugging Face, 10 Repo token (`REPO_TOKEN`: repo readable and push access). Secrets are typed hidden and Enter reuses the matching env var. Mastodon also checks the base URL and `write:statuses` scope; Threads checks the token matches `THREADS_USER_ID`; Telegram checks the bot can reach `TELEGRAM_USER_ID`.

### Automated tests
```bash
.venv/bin/python -m pytest src/tests/
```
The suite (not pinned to a count, since coverage changes independently of releases) covers repository hygiene, SSRF and redirect spoofing, scoring weights and `_score_debug`, secret redaction, story clustering, Telegram commands and approval flows (including tag toggling), topic grounding, dry-run bypasses, the media pipeline, state recovery, workflow environment guards, and platform failure handling. A conftest fixture redirects `STATUS.md` writes to a temp file so running tests never modifies the tracked file.
