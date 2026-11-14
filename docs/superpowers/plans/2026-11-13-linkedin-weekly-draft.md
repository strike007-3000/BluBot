# LinkedIn Weekly Draft Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A weekly, separate workflow that shortlists three of this week's published stories in Telegram, drafts one LinkedIn post in the owner's voice after the owner picks a story and optionally adds a take, verifies it against the source, and delivers it to Telegram for manual posting.

**Architecture:** A root entry script `linkedin_weekly.py` reuses the existing weekly ledger helpers and Bluesky engagement fetch, ranks candidates deterministically, asks Gemini once for enterprise angles, then runs one blocking Telegram session (the same polling pattern as `send_draft_for_approval`, held open for the whole run). Draft generation fetches the original source, generates, then checks rules, numbers and claims, retrying up to twice. Nothing is ever posted to LinkedIn.

**Tech Stack:** Python 3.13, `google-genai`, `python-telegram-bot`, `httpx`, `BeautifulSoup`, pytest (existing `src/tests/`), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-13-linkedin-weekly-draft-design.md`. Verbatim prompt text: `docs/superpowers/specs/2026-11-13-linkedin-prompts-source.md`.

## Global Constraints
- LinkedIn publishing stays manual: no LinkedIn API, no tokens. "Done" only marks the draft reviewed.
- Draft length 80-130 words excluding hashtags and URL; 3-4 hashtags; no em dashes, no emojis.
- The draft must never mention Bluesky or contain a `bsky` link. The drafter receives only the article title, URL, fetched source text and the owner's take, never the Bluesky post text or URI.
- Gemini only (rotate `GEMINI_MODEL_PRIORITY` from `src/config.py`); no new provider, no new dependency.
- At most 2 automatic regeneration retries on verification failure (`MAX_RETRIES = 2`).
- Shortlist size `SHORTLIST_SIZE = 3`, pre-rank pool `PRERANK_TOP_N = 8`; owner take capped at `TAKE_MAX_CHARS = 1000`; fetched source text capped at `SOURCE_TEXT_MAX_CHARS = 6000`.
- State week key is the ISO week string (e.g. `2026-W46`) from this feature's own `current_iso_week` in `src/linkedin_select.py`. Do not import from `bot.py`; the Friday roundup and this feature stay independent and share only `src/engagement.py` and `src/utils.py`.
- One total session deadline of `linkedin_telegram_timeout_minutes` (default 10) measured from the shortlist message, not per stage. Whatever stage is waiting when it expires follows the rules below. The week's draft must never be lost to a timeout: no reply at the shortlist stage auto-drafts the first candidate with no take; no reply at the take prompt proceeds as Skip; no reply at draft review leaves the delivered draft in the chat. Auto-drafts are labelled "Auto-selected, not reviewed" and write no week marker.
- Follow existing patterns: `SafeLogger`, `settings`, owner-only Telegram callbacks, tests under `src/tests/`.
- Do not touch README.md, CHANGELOG.md, VERSION or release docs (the owner has uncommitted edits stashed there).

## Review Focus
1. Ledger entry lacks `category`, a Bluesky URI, or the engagement fetch returns `{}`: still ranks and shortlists (engagement 0).
2. Gemini returns invalid JSON or fails for the angle call: shortlist still shows the top 3 with angle "No angle available".
3. Fewer than 3 eligible stories (1 or 2): shortlist shows what exists; 0: no Telegram message, clean exit.
4. Owner take contains HTML or is very long: HTML-escaped in Telegram messages, truncated to `TAKE_MAX_CHARS` before prompting.
5. Source is a PDF, non-200, or unreachable: draft is generated from title only and clearly marked UNVERIFIED, claim check skipped; never silent.
6. A callback or text reply from a non-owner, or from a different message, is ignored.

---

### Task 1: Week marker, setting and Gemini helper

**Files:**
- Create: `src/linkedin_llm.py`, `src/linkedin_select.py` (marker helpers only in this task)
- Modify: `src/settings.py` (add `linkedin_telegram_timeout_minutes: int = 10`, env `LINKEDIN_TELEGRAM_TIMEOUT_MINUTES`, loaded in `from_env` next to `telegram_timeout_minutes`), `src/utils.py` (`sanitize_and_migrate_state` must preserve a `linkedin_weeks: dict` key)
- Test: `src/tests/test_linkedin_select.py`

**Interfaces:**
- Produces: `linkedin_weeks` state key shape `{iso_week: {"status": "done", "url": str, "at": iso8601}}`
- Produces (`src/linkedin_select.py`): `is_week_done(state: dict, iso_week: str) -> bool`, `mark_week_done(state: dict, iso_week: str, url: str) -> dict` (returns the mutated state)
- Produces (`src/linkedin_llm.py`): `async def gemini_generate(genai_client, prompt: str, system_instruction: str, json_mode: bool = False) -> Optional[str]`; rotates `GEMINI_MODEL_PRIORITY` using the same temperature, `supports_thinking` and `normalize_gemini_model_id` handling as `remix_platform_draft` in `src/curator.py`; returns stripped text, or `None` if every model fails or returns empty.

- [ ] **Step 1: Write failing tests** in `test_linkedin_select.py`: `test_is_week_done_false_for_empty_state`, `test_mark_week_done_then_is_week_done_true`, `test_marker_survives_sanitize_round_trip` (call `sanitize_and_migrate_state` on a state containing `linkedin_weeks` and assert the key is unchanged), `test_gemini_generate_returns_none_when_all_models_fail` (fake client whose `aio.models.generate_content` raises), `test_gemini_generate_rotates_to_next_model` (first raises, second returns `"ok"`).
- [ ] **Step 2: Run** `pytest src/tests/test_linkedin_select.py -v`; expect FAIL (modules missing).
- [ ] **Step 3: Implement** the helpers above, the setting, and the `sanitize_and_migrate_state` passthrough for `linkedin_weeks` (non-dict value becomes `{}`).
- [ ] **Step 4: Run** the same command plus `pytest src/tests/test_utils.py src/tests/test_settings.py -q`; expect all PASS.
- [ ] **Step 5: Commit** `feat(linkedin): week marker, setting and gemini helper`.

### Task 2: Candidate selection

**Files:**
- Modify: `src/linkedin_select.py`
- Test: `src/tests/test_linkedin_select.py`

**Interfaces:**
- Consumes: `bluesky_uri(entry)` from `src/engagement.py`; `gemini_generate` (Task 1)
- Produces: `@dataclass(frozen=True) class Candidate: entry: dict; angle: str; engagement: int`
- Produces: `current_iso_week(now: Optional[datetime] = None) -> str` (`YYYY-Www`, UTC) and `eligible_this_week(state: dict, iso_week: str) -> List[dict]`: `published_posts` entries whose `published_at` falls in that ISO week, `kind != "roundup"`, with a valid public `url` (`is_valid_public_http_url` from `scripts/build_archive.py`), title whitespace-collapsed and cut to 120 chars. Tests: `test_eligible_this_week_excludes_roundup_entries`, `test_eligible_this_week_excludes_other_weeks`, `test_eligible_this_week_excludes_invalid_urls`, `test_current_iso_week_format`.
- Produces: `engagement_total(entry: dict, metrics: Dict[str, Dict[str, int]]) -> int` (likes+reposts+replies+quotes, 0 when no metrics)
- Produces: `prerank(entries: List[dict], metrics: Dict[str, Dict[str, int]]) -> List[dict]`: score = `engagement_total` + category boost (`research_lab`, `enterprise`, `academic`, `open_source` = 3; `practitioner` = 2; others 0); sorted descending, ties by newer `published_at`; returns at most `PRERANK_TOP_N`.
- Produces: `async def rate_candidates(genai_client, entries: List[dict], metrics) -> List[Candidate]`: one `gemini_generate(json_mode=True)` call over the pre-ranked entries (title, topic, summary only; never Bluesky text) returning `[{"index": int, "angle": str, "relevant": bool}]`; keep relevant ones in pre-rank order up to `SHORTLIST_SIZE`; on invalid JSON, failure, or no relevant result, fall back to the first `SHORTLIST_SIZE` entries with angle `"No angle available"`.

- [ ] **Step 1: Write failing tests:** `test_prerank_orders_by_engagement_plus_category_boost`, `test_prerank_caps_at_eight`, `test_engagement_total_zero_without_metrics`, `test_rate_candidates_keeps_relevant_and_angles` (fake Gemini JSON marking index 1 not relevant), `test_rate_candidates_falls_back_on_invalid_json`, `test_rate_candidates_falls_back_when_gemini_fails`, `test_rate_candidates_with_two_entries_returns_two`, `test_rate_candidates_prompt_excludes_bluesky_text` (entries carrying a `posts.bluesky` text field; assert the captured prompt does not contain it).
- [ ] **Step 2: Run** `pytest src/tests/test_linkedin_select.py -v`; expect new tests FAIL.
- [ ] **Step 3: Implement** the three functions and dataclass in `src/linkedin_select.py`.
- [ ] **Step 4: Run** the same command; expect PASS.
- [ ] **Step 5: Commit** `feat(linkedin): candidate pre-ranking and angle rating`.

### Task 3: Source fetch and draft generation

**Files:**
- Create: `src/linkedin_prompts.py`, `src/linkedin_draft.py`
- Test: `src/tests/test_linkedin_draft.py`

**Interfaces:**
- Consumes: `get_with_safe_redirects` from `src/utils.py` (SSRF-safe fetch used by `get_link_metadata`); `gemini_generate` (Task 1)
- Produces (`src/linkedin_prompts.py`): constants `LINKEDIN_CONTENT_INSTRUCTIONS`, `LINKEDIN_MY_TAKE_INSTRUCTIONS`, `LINKEDIN_EDITORIAL_INSTRUCTIONS`, copied verbatim from the prompts source file, and `LINKEDIN_SYSTEM_INSTRUCTION` = the three joined by blank lines.
- Produces: `async def fetch_source_text(client, url: str) -> Optional[str]`: `None` on non-200, non-HTML, or error. For arXiv abstract pages return the title plus the `blockquote.abstract` text; otherwise title, `og:description`/meta description and visible `<p>` text, whitespace-collapsed and cut to `SOURCE_TEXT_MAX_CHARS`.
- Produces: `check_draft_rules(draft: str) -> List[str]` returning rule failures: contains `bluesky` or `bsky` (case-insensitive), em dash present, word count outside 80-130 (excluding hashtags and URLs), hashtag count outside 3-4.
- Produces: `async def generate_draft(genai_client, entry: dict, source_text: Optional[str], take: Optional[str], fix_notes: Sequence[str] = ()) -> Optional[str]`: prompt contains only the title, URL, source text (or a note that it is unavailable), the take (truncated to `TAKE_MAX_CHARS`, labelled as the owner's input) and fix notes; uses `LINKEDIN_SYSTEM_INSTRUCTION`; output markdown-stripped.

- [ ] **Step 1: Write failing tests:** `test_prompts_are_verbatim` (each constant contains a known sentinel from its block: `"No AI Slop – Mandatory Rules"`, `"Never invent a personal opinion"`, `"Cross-platform independence"`), `test_check_draft_rules_flags_bluesky_mention`, `..._flags_em_dash`, `..._flags_word_count_out_of_range`, `..._flags_hashtag_count`, `test_check_draft_rules_accepts_valid_draft`, `test_fetch_source_text_arxiv_abstract` (fake client serving an arXiv-style page), `test_fetch_source_text_returns_none_on_non_200`, `test_fetch_source_text_truncates`, `test_generate_draft_prompt_includes_take_and_excludes_bluesky_fields`, `test_generate_draft_truncates_long_take`.
- [ ] **Step 2: Run** `pytest src/tests/test_linkedin_draft.py -v`; expect FAIL.
- [ ] **Step 3: Implement** the prompts module and the four functions.
- [ ] **Step 4: Run** the same command; expect PASS.
- [ ] **Step 5: Commit** `feat(linkedin): source fetch, prompts and draft generation`.

### Task 4: Verification and retry loop

**Files:**
- Modify: `src/linkedin_draft.py`
- Test: `src/tests/test_linkedin_draft.py`

**Interfaces:**
- Consumes: `check_draft_rules`, `generate_draft`, `fetch_source_text` (Task 3)
- Produces: `@dataclass(frozen=True) class DraftResult: text: Optional[str]; verified: bool; flags: Tuple[str, ...]; error: Optional[str]`
- Produces: `unsupported_numbers(draft: str, source_text: str) -> List[str]`: numbers (with optional `%`) in the draft, excluding hashtags and URLs, that do not appear in the source text.
- Produces: `async def verify_claims(genai_client, draft: str, source_text: str) -> Optional[List[str]]`: Gemini JSON pass returning material errors (statistic misattribution, baseline or measurement changed, experimental finding stated as general or production fact, unsupported names, organizations or capabilities); `[]` means none; `None` means the check could not run.
- Produces: `async def build_verified_draft(genai_client, client, entry: dict, take: Optional[str]) -> DraftResult`: fetch source; if source is `None`, generate once, check rules only, return `verified=False` with flag `"UNVERIFIED: source could not be fetched"`. Otherwise loop up to `1 + MAX_RETRIES` attempts: generate, collect rule failures + `unsupported_numbers` + `verify_claims` errors, pass them as `fix_notes` to the next attempt. First clean attempt returns `verified=True`. If errors remain after the last attempt, return `text=None` with `error` describing them (never a warning attached to a bad draft). If `verify_claims` returns `None`, keep the draft with `verified=False` and flag `"UNVERIFIED: claim check unavailable"`.

- [ ] **Step 1: Write failing tests:** `test_unsupported_numbers_detects_missing_stat`, `test_unsupported_numbers_ignores_hashtags_and_urls`, `test_build_verified_draft_clean_first_try`, `test_build_verified_draft_retries_with_fix_notes_then_passes` (first draft invents "27.7%", second is clean; assert the second prompt contains the fix note), `test_build_verified_draft_withholds_after_max_retries` (still failing after 3 attempts gives `text is None` and an `error`), `test_build_verified_draft_unverified_when_source_missing`, `test_build_verified_draft_unverified_when_claim_check_fails`, `test_misattributed_claim_is_caught` (numbers match but `verify_claims` fake reports a production-cost misstatement; draft is regenerated).
- [ ] **Step 2: Run** `pytest src/tests/test_linkedin_draft.py -v`; expect new tests FAIL.
- [ ] **Step 3: Implement** the dataclass and three functions.
- [ ] **Step 4: Run** the same command; expect PASS.
- [ ] **Step 5: Commit** `feat(linkedin): claim verification and bounded retry`.

### Task 5: Telegram session

**Files:**
- Create: `src/linkedin_telegram.py`
- Test: `src/tests/test_linkedin_telegram.py` (follow the `_make_bot` mocking style in `src/tests/test_telegram_gateway.py`)

**Interfaces:**
- Consumes: `_make_bot` from `src/telegram_gateway.py`; `Candidate` (Task 2); `DraftResult` (Task 4)
- Produces: `@dataclass(frozen=True) class SessionResult: candidate: Candidate; draft: str; reviewed: bool`
- Produces: `async def run_linkedin_session(candidates: List[Candidate], iso_week: str, make_draft: Callable[[Candidate, Optional[str]], Awaitable[DraftResult]]) -> Optional[SessionResult]`: `reviewed=True` when the owner taps Done; `reviewed=False` for an auto-draft after a timeout (see Global Constraints); `None` on Cancel, or when an auto-draft's `DraftResult.text` is `None`. The deadline is one `time.monotonic()` budget of `settings.linkedin_telegram_timeout_minutes` for the whole session; draft generation after the deadline (auto-draft) is allowed to finish.
- Flow: (1) shortlist message with title, `Enterprise angle: ...`, engagement per candidate and buttons `li:pick:<idx>:<iso_week>` plus `li:cancel:<iso_week>`; (2) after a pick, a prompt message "Add personal context, or Skip" with a Skip button; the take is the owner's text reply to that prompt message only (reply-to message id match), truncated to `TAKE_MAX_CHARS`; (3) call `make_draft`, send the draft HTML-escaped with Done / Regenerate / Cancel (UNVERIFIED flags shown above the draft); a `DraftResult` with `text is None` shows the error with Retry / Cancel; (4) Regenerate and Retry call `make_draft` again with the same candidate and take. Callbacks from non-owners, with another message id, or another week are ignored (answered as stale). Done sends "Marked reviewed. Post it to LinkedIn manually." and publishes nothing.

- [ ] **Step 1: Write failing tests:** `test_pick_skip_done_returns_candidate_and_draft`, `test_reply_take_reaches_make_draft`, `test_unrelated_text_message_is_not_taken_as_take`, `test_regenerate_keeps_story_and_take` (assert `make_draft` called twice with identical args), `test_cancel_returns_none`, `test_shortlist_timeout_autodrafts_first_candidate_unreviewed` (result `reviewed=False`, message labelled "Auto-selected, not reviewed", no buttons), `test_take_prompt_timeout_proceeds_without_take`, `test_review_timeout_leaves_draft_delivered`, `test_autodraft_failure_returns_none_and_sends_error`, `test_non_owner_callback_ignored`, `test_stale_week_callback_ignored`, `test_error_result_offers_retry_and_cancel`, `test_take_html_is_escaped_and_truncated`, `test_zero_candidates_sends_nothing`.
- [ ] **Step 2: Run** `pytest src/tests/test_linkedin_telegram.py -v`; expect FAIL.
- [ ] **Step 3: Implement** `run_linkedin_session` using the existing polling loop shape (`get_updates` with offset, 1-second long poll, `time.monotonic` deadline, ownership check against `settings.telegram_user_id`).
- [ ] **Step 4: Run** the same command; expect PASS.
- [ ] **Step 5: Commit** `feat(linkedin): sequential telegram session`.

### Task 6: Entry point, workflow and acceptance tests

**Files:**
- Create: `linkedin_weekly.py` (root), `.github/workflows/linkedin_weekly.yml`
- Test: `src/tests/test_linkedin_weekly.py`

**Interfaces:**
- Consumes: `current_iso_week`, `eligible_this_week` (Task 2); `load_seen_articles`, `save_seen_articles` from `src/utils.py`; `fetch_bluesky_metrics` from `src/engagement.py`; Tasks 1-5.
- Produces: `async def run(client, genai_client, now: Optional[datetime] = None) -> str` returning one of `"done"`, `"auto_drafted"`, `"skipped_done"`, `"no_stories"`, `"cancelled"`, `"telegram_disabled"`; and `main()` wiring `httpx.AsyncClient` and `genai.Client(api_key=settings.gemini_key)`, run with `asyncio.run`.
- Behavior: if Telegram token or user id is missing return `"telegram_disabled"`; if `is_week_done` return `"skipped_done"` before any Telegram message; no eligible stories returns `"no_stories"`; otherwise fetch metrics, `prerank`, `rate_candidates`, `run_linkedin_session` with `make_draft` bound to `build_verified_draft`; on a reviewed result call `mark_week_done` then `save_seen_articles` (return `"done"`); an unreviewed auto-draft returns `"auto_drafted"` and writes no marker; Cancel leaves no marker so a manual rerun can retry.
- Workflow: cron `0 9 * * 0` (Sunday 09:00 UTC, my default, owner may change the hour; the owner posts on Monday). The daily cron is Monday-Friday only, so no daily run polls the same Telegram bot, and a delayed Friday run plus the Friday roundup are already in the ledger. Sunday is still in the same ISO week plus `workflow_dispatch`; its own `concurrency` group `linkedin-weekly` (not `bsky-persistence-state`, so a 30-minute wait cannot displace queued daily runs); env limited to `GEMINI_KEY`, `GIST_ID`, `GIST_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID`, `ENABLE_TELEGRAM_APPROVAL`, `LINKEDIN_TELEGRAM_TIMEOUT_MINUTES`; step `python linkedin_weekly.py`. Confirm `Settings.from_env` loads with only this env subset.

- [ ] **Step 1: Write failing acceptance tests** using fakes for Telegram, Gemini and HTTP: `test_normal_run_three_candidates_one_verified_draft` (criterion 1), `test_take_is_reflected_in_draft_prompt` (2), `test_unsupported_statistic_is_corrected_or_withheld` (3), `test_rerun_after_done_sends_no_second_shortlist` (4), `test_regenerate_keeps_story_and_take_and_publishes_nothing` (5, also assert no broadcaster function is called), `test_draft_never_mentions_bluesky` (6), `test_no_stories_sends_nothing`, `test_cancel_does_not_write_marker`, `test_done_writes_marker_once`, `test_timeout_autodraft_returns_auto_drafted_and_writes_no_marker`.
- [ ] **Step 2: Run** `pytest src/tests/test_linkedin_weekly.py -v`; expect FAIL.
- [ ] **Step 3: Implement** `run` and `main` in `linkedin_weekly.py`, and the workflow file.
- [ ] **Step 4: Run** `pytest src/tests -q`; expect the whole suite PASS, then run `python -c "import linkedin_weekly"` and expect no error.
- [ ] **Step 5: Commit** `feat(linkedin): weekly entry point and workflow`.

## Out of scope
LinkedIn API or auto-posting, engagement analysis of LinkedIn posts, multiple competing drafts, new feeds or scoring dimensions, README/CHANGELOG edits (owner's stashed release-docs work), enabling the cron before the owner has run one `workflow_dispatch` successfully.
