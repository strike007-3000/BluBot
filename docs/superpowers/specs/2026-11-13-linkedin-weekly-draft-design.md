# LinkedIn Weekly Draft: Design

Status: revised after two design reviews (the reviewer would approve for implementation), awaiting owner approval. Nothing is built.

## Intent
Once a week, turn one of the past week's already-published Bluesky stories into a LinkedIn post draft for the owner's personal profile (Product Owner / AI practitioner voice, enterprise angle). The bot only drafts. The owner reviews in Telegram, adds bold and formatting, and pastes it into LinkedIn by hand.

Why: the owner already does this manually. The bot shortlists and drafts; the owner's context and opinion, which make posts perform, stay in the loop.

## Success criterion
Not "the bot can generate a post". The draft is good enough that the owner makes only minor personal edits. For the first few weeks, judge it on three things: did it pick an interesting story, were its claims accurate, and did its proposed take sound like something the owner would say. Bluesky engagement alone is not the measure.

## Goals
- Separate weekly GitHub Actions workflow, independent of the 3x/day pipeline.
- Shortlist of 3 candidates from the last 7 days of the `published_posts` ledger (see Candidate ranking).
- Owner taps one in Telegram, optionally adding personal take or context.
- Gemini drafts one post, 80-130 words, from the owner's writing instructions (below). Source URL on its own line.
- Claim-level verification against the fetched source, plus a lightweight number check.
- Draft delivered to Telegram only. LinkedIn publishing stays manual.

## Non-goals
- No LinkedIn API, no auto-posting, no OAuth tokens (avoids the 60-day token expiry and the policy gray area; LinkedIn's primary policy pages could not be read, so treat its automation policy as unverified).
- No new feeds, no new scoring service, no second model provider (Groq rejected).
- No roundup posts; one story per post.
- No auto-learning from LinkedIn engagement.
- No extra Telegram controls beyond those listed, until a real need appears.

## Anti-goals
- A post that reads as vendor marketing or a paraphrased press release, or as an automated rewrite of a news summary.
- Invented facts, statistics, personal experiences or strong opinions.
- A forced enterprise angle where the connection is weak.

## Approaches considered
1. **Curate from the ledger (chosen).** Reuses vetted, deduplicated, already-posted stories and the existing engagement fetch. Limit: the pool is what the daily bot already posted.
2. **Fresh weekly curation with an enterprise-weighted score.** Rejected: only 3 feeds carry the `enterprise` category, and the owner's real sources are papers and open-source projects the bot already posts.
3. **A standalone LLM judge over a wide candidate set (possibly Groq).** Rejected: more moving parts than needed. A single Gemini call limited to the shortlist (below) covers what is needed.

## Design

### 1. Candidate ranking
Priority order: (1) enterprise relevance and potential for an interesting personal perspective, (2) source credibility and substance, (3) Bluesky engagement as a supporting signal.
- Deterministic pre-rank of the 7-day ledger using source quality / category (small research and open-source boost) and engagement from `src/engagement.py`. Keep the top ~8.
- One Gemini call over those ~8 returns, per candidate, a one-line "why this works for LinkedIn" enterprise angle and a relevance judgement. Candidates with a weak enterprise connection are dropped; keep the best 3.
- Note: this is a bounded call on the shortlist, not a scoring service; it is needed anyway to write the one-line explanations.
- Telegram shows each candidate with its enterprise angle and engagement counts.

### 2. Personal take hierarchy
1. Owner's Telegram input (opinion, experience, context): highest priority. Preserve it without exaggerating it into a stronger claim.
2. Established perspective: Product Owner, AI practitioner, enterprise adoption.
3. Fallback: Gemini proposes a measured professional interpretation grounded in the source. No invented experience or strong opinion.
If the enterprise connection is weak, choose another story instead of forcing one.

### 3. Verification
- Fetch the primary source (for a paper, the abstract). If retrieval fails, flag the draft as unverified. Never treat the earlier Bluesky summary as primary-source evidence.
- Claim-level check: a second Gemini pass compares the draft's claims with the source text and flags: statistic attribution, preserved baseline and measurement, experimental finding stated as a general claim, and unsupported names, organizations or product capabilities.
- Keep the automatic number check as a cheap first filter. It is not proof of accuracy (a matching number can still be mis-described).
- A material factual error (unsupported statistic, misattributed claim, finding stated as general fact) is corrected or the draft is regenerated before it is shown. A warning is never merely attached to a misleading post. Cap at 2 automatic retries (my call); if it still fails, withhold the unsupported claim or show a clear error with a retry option.
- Abstracts suffice for high-level claims but may lack benchmark methodology or limitations. The drafter omits unsupported details instead of inferring them.
- Remaining minor flags appear in Telegram outside the post.

### 4. Telegram experience (sequential)
1. Weekly shortlist: 3 stories with enterprise angle and engagement.
2. Owner selects a story.
3. Bot prompts: add personal context, or Skip. The next reply is bound to the selected candidate and week id, so an unrelated message is never read as a take.
4. Gemini drafts and verifies.
5. Telegram draft with Done, Regenerate, Cancel.
- Regenerate keeps the selected story and the personal take; only the draft changes.
- Done only marks the draft reviewed. Nothing is ever published to LinkedIn.

### 4b. Cross-platform independence
Bluesky is an internal discovery source only. The LinkedIn draft must never mention Bluesky, link to the Bluesky post, or refer to earlier publication. The source is the original article, paper or announcement (ledger `source_url` / `url`). The drafter is a fresh LinkedIn post for this audience and the owner's perspective. Safeguard: do not pass Bluesky post text or URI to the drafter at all; engagement counts are used only for ranking and the Telegram shortlist. Add a post-draft check that rejects drafts containing "Bluesky" or a bsky link.

### 5. Draft structure
No mandatory closing principle sentence (dropped from the earlier draft, to avoid a repetitive pattern). The ending emerges from the topic, per the owner's writing instructions (practical takeaway or genuine question, never forced).

### 6. Reliability
- One shortlist message per ISO week (idempotency key in existing state); reruns do not post duplicates.
- Callbacks carry the week id so a late tap resolves against the correct shortlist.
- If source retrieval or generation fails, Telegram shows a clear error with a retry option.
- Reuse the existing state mechanism; add a new store only if it cannot do this reliably.

## Drafter prompt, part 1: LinkedIn content instructions (owner-supplied)
Store as a dedicated prompt constant, using the owner's full text verbatim (do not compress). Summary: accuracy first (primary sources, attribute vendor and research claims, never invent facts or personal experience); plain, conversational, confident; no AI cliches, generic openings, "not X but Y" contrasts, dramatic setups, empty conclusions or repetitive "this highlights/underscores"; no emojis, bold, em dashes or bullet-heavy formatting; 80-130 words excluding hashtags and URL; specific opening; short mobile paragraphs; 3-4 hashtags; answer what happened, why it matters, what the owner thinks; silent self-review; output only the post with the source URL separate and important unverified claims flagged outside it.

## Drafter prompt, part 2: "Writing My Take" (owner-supplied)
Interpretation from a Product Owner / AI practitioner view on enterprise adoption (scalability, cost, customer value, security, governance, deployment, whichever is genuinely relevant). Add something beyond the announcement without inventing facts, experiences or strong opinions. Constructive, curious, generally pro-AI; acknowledge limits without needless skepticism. Natural phrasing; do not mechanically introduce opinions with "My take". Separate interpretation from fact ("could", "may", "I think"). With insufficient context, give a measured professional observation.

## Drafter prompt, part 3: Editorial perspective and originality (from review)
Treat the selected Bluesky post as a starting point, not as the final LinkedIn content. Identify the most interesting verified development and explain its practical significance. Add one thoughtful observation from a Product Owner and AI practitioner perspective. Prioritize the owner's optional Telegram input when provided; otherwise use a measured interpretation grounded in the source. Do not force an enterprise angle, invent personal experience or manufacture a strong opinion. Avoid predictable closing statements, generic AI commentary and repeated sentence structures. Every paragraph should contribute new information or perspective. The draft should feel like a knowledgeable professional sharing an interesting discovery, not an automated rewrite of a news summary.

My call: hedge predictions ("could", "may") but state established facts plainly, because the owner's best-performing posts are decisive.

## Acceptance criteria
The feature is complete only when each of these is demonstrated:
1. A normal weekly run produces three candidates and one verified draft.
2. A personal take entered in Telegram is reflected accurately in the draft, without being exaggerated.
3. An unsupported statistic is detected and corrected or explicitly withheld.
4. Re-running the weekly workflow does not create a duplicate shortlist message.
5. Regeneration retains the selected story and personal context, and publishes nothing.
6. (Added) The draft never mentions Bluesky or links to the Bluesky post.

Also not to be added at this stage: LinkedIn engagement analysis, multiple competing drafts, a separate editorial agent, more scoring dimensions.

## Known unknowns for the builder (not yet inspected)
- Whether ledger entries store Bluesky post text or only the URI (summary and source URL are stored).
- How the weekly workflow gets the same state and secrets as the daily one.
- The existing `roundup_stage` / `week` field in `bot.py` may overlap; read before writing new code.
- How the "tap a candidate, then optionally reply with a take" flow fits the existing Telegram gateway and callback handling.
- Overlap with a story the daily bot already posted is assumed fine (different audience); owner confirmation still pending.

## Risks
- Single-digit engagement counts make that signal noisy; it is only supporting.
- Two extra Gemini calls (shortlist angles, claim check) per week add free-tier usage and failure points; both fall back to showing flags or raw candidates, not to silent success.
- Claim-level checking by a model is a safeguard, not proof; the owner still reads the source.
