import asyncio
import json
from types import SimpleNamespace

from src import linkedin_draft as ld
from src.linkedin_prompts import (
    LINKEDIN_CONTENT_INSTRUCTIONS, LINKEDIN_EDITORIAL_INSTRUCTIONS, LINKEDIN_MY_TAKE_INSTRUCTIONS,
)

run = asyncio.run
ENTRY = {"title": "Big Paper", "url": "https://arxiv.org/abs/1", "posts": {"bluesky": "SECRETBSKYTEXT"}, "bluesky_uri": "at://x"}
GOOD = ("word " * 90).strip() + " #AI #Cloud #Open https://arxiv.org/abs/1"


def _resp(text, status=200, ctype="text/html"):
    return SimpleNamespace(status_code=status, text=text, headers={"content-type": ctype})


def _fetch(monkeypatch, resp):
    async def f(client, url, **kw):
        return resp
    monkeypatch.setattr(ld, "get_with_safe_redirects", f)


def _gemini(monkeypatch, outputs, prompts=None):
    it = iter(outputs)

    async def g(client, prompt, system, json_mode=False):
        if prompts is not None:
            prompts.append((prompt, json_mode))
        return next(it)
    monkeypatch.setattr(ld, "gemini_generate", g)


def test_prompts_are_verbatim():
    assert "No AI Slop – Mandatory Rules" in LINKEDIN_CONTENT_INSTRUCTIONS
    assert "Never invent a personal opinion" in LINKEDIN_MY_TAKE_INSTRUCTIONS
    assert "Cross-platform independence" in LINKEDIN_EDITORIAL_INSTRUCTIONS


def test_check_draft_rules_flags_bluesky_mention():
    assert any("Bluesky" in f for f in ld.check_draft_rules(GOOD + " seen on bsky"))


def test_check_draft_rules_flags_em_dash():
    assert any("em dash" in f for f in ld.check_draft_rules(GOOD + " a — b"))


def test_check_draft_rules_flags_word_count_out_of_range():
    assert any("Word count" in f for f in ld.check_draft_rules("short #a #b #c"))


def test_check_draft_rules_flags_hashtag_count():
    assert any("hashtags" in f for f in ld.check_draft_rules(GOOD + " #d #e"))


def test_check_draft_rules_accepts_valid_draft():
    assert ld.check_draft_rules(GOOD) == []


def test_fetch_source_text_arxiv_abstract(monkeypatch):
    html = "<html><title>Paper T</title><blockquote class='abstract'>Abstract:  We   test things.</blockquote><p>nav junk</p></html>"
    _fetch(monkeypatch, _resp(html))
    out = run(ld.fetch_source_text(None, "https://arxiv.org/abs/1"))
    assert "Paper T" in out and "We test things." in out and "junk" not in out


def test_fetch_source_text_returns_none_on_non_200(monkeypatch):
    _fetch(monkeypatch, _resp("x", status=404))
    assert run(ld.fetch_source_text(None, "https://a.com")) is None


def test_fetch_source_text_truncates(monkeypatch):
    _fetch(monkeypatch, _resp("<html><title>T</title><p>" + "a " * 9000 + "</p></html>"))
    assert len(run(ld.fetch_source_text(None, "https://a.com"))) <= ld.SOURCE_TEXT_MAX_CHARS


def test_generate_draft_prompt_includes_take_and_excludes_bluesky_fields(monkeypatch):
    prompts = []
    _gemini(monkeypatch, ["**hi**"], prompts)
    out = run(ld.generate_draft(None, ENTRY, "src body", "my take here", ["fix me"]))
    p = prompts[0][0]
    assert out == "hi"
    assert "my take here" in p and "src body" in p and "fix me" in p and "Big Paper" in p
    assert "SECRETBSKYTEXT" not in p and "at://x" not in p


def test_generate_draft_truncates_long_take(monkeypatch):
    prompts = []
    _gemini(monkeypatch, ["x"], prompts)
    run(ld.generate_draft(None, ENTRY, "s", "t" * 5000))
    assert "t" * 1000 in prompts[0][0] and "t" * 1001 not in prompts[0][0]


def test_unsupported_numbers_detects_missing_stat():
    assert ld.unsupported_numbers("It gained 27.7% and 40 points", "gained 40 points") == ["27.7%"]


def test_unsupported_numbers_ignores_hashtags_and_urls():
    assert ld.unsupported_numbers("See https://x.com/a/123 #GPT5 ok", "ok") == []


def _build(monkeypatch, drafts, claims, source="source text 40 points"):
    prompts = []

    async def fs(client, url):
        return source
    monkeypatch.setattr(ld, "fetch_source_text", fs)
    it = iter(drafts)

    async def gd(g, entry, src, take, fix_notes=()):
        prompts.append(list(fix_notes))
        return next(it)

    async def vc(g, d, s):
        return claims.pop(0)
    monkeypatch.setattr(ld, "generate_draft", gd)
    monkeypatch.setattr(ld, "verify_claims", vc)
    return prompts


def test_build_verified_draft_clean_first_try(monkeypatch):
    _build(monkeypatch, [GOOD], [[]])
    r = run(ld.build_verified_draft(None, None, ENTRY, None))
    assert r.verified and r.text == GOOD and r.error is None


def test_build_verified_draft_retries_with_fix_notes_then_passes(monkeypatch):
    bad = GOOD + " It rose 27.7%"
    notes = _build(monkeypatch, [bad, GOOD], [[], []])
    r = run(ld.build_verified_draft(None, None, ENTRY, None))
    assert r.verified and r.text == GOOD
    assert notes[0] == [] and any("27.7%" in n for n in notes[1])


def test_build_verified_draft_withholds_after_max_retries(monkeypatch):
    bad = GOOD + " 27.7%"
    notes = _build(monkeypatch, [bad] * 3, [[]] * 3)
    r = run(ld.build_verified_draft(None, None, ENTRY, None))
    assert r.text is None and r.error and len(notes) == 3


def test_build_verified_draft_unverified_when_source_missing(monkeypatch):
    _build(monkeypatch, [GOOD], [], source=None)
    r = run(ld.build_verified_draft(None, None, ENTRY, None))
    assert r.text == GOOD and not r.verified and "UNVERIFIED: source could not be fetched" in r.flags


def test_build_verified_draft_unverified_when_claim_check_fails(monkeypatch):
    _build(monkeypatch, [GOOD], [None])
    r = run(ld.build_verified_draft(None, None, ENTRY, None))
    assert r.text == GOOD and not r.verified and "UNVERIFIED: claim check unavailable" in r.flags


def test_misattributed_claim_is_caught(monkeypatch):
    notes = _build(monkeypatch, [GOOD, GOOD + " "], [["States a lab result as production cost"], []])
    r = run(ld.build_verified_draft(None, None, ENTRY, None))
    assert r.verified and "production cost" in notes[1][0]


def test_verify_claims_parses_json_and_none(monkeypatch):
    _gemini(monkeypatch, [json.dumps({"errors": ["bad"]}), "not json", None])
    assert run(ld.verify_claims(None, "d", "s")) == ["bad"]
    assert run(ld.verify_claims(None, "d", "s")) is None
    assert run(ld.verify_claims(None, "d", "s")) is None
