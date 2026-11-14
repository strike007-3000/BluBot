import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.linkedin_llm import gemini_generate
from src.linkedin_select import is_week_done, mark_week_done
from src.utils import sanitize_and_migrate_state


def _client(*behaviours):
    """Each behaviour is an Exception to raise or a str to return, consumed per call."""
    calls = iter(behaviours)

    async def gen(**kwargs):
        b = next(calls)
        if isinstance(b, Exception):
            raise b
        return SimpleNamespace(text=b)

    client = MagicMock()
    client.aio.models.generate_content = gen
    return client


def test_is_week_done_false_for_empty_state():
    assert is_week_done({}, "2026-W46") is False


def test_mark_week_done_then_is_week_done_true():
    state = mark_week_done({}, "2026-W46", "https://a.example/x")
    assert is_week_done(state, "2026-W46")
    assert not is_week_done(state, "2026-W47")


def test_marker_survives_sanitize_round_trip():
    state = mark_week_done({}, "2026-W46", "https://a.example/x")
    assert sanitize_and_migrate_state(state)["linkedin_weeks"] == state["linkedin_weeks"]
    assert sanitize_and_migrate_state({"linkedin_weeks": "bad"})["linkedin_weeks"] == {}


def test_gemini_generate_returns_none_when_all_models_fail():
    client = _client(*[RuntimeError("x")] * 20)
    assert asyncio.run(gemini_generate(client, "p", "s")) is None


def test_gemini_generate_rotates_to_next_model():
    client = _client(RuntimeError("x"), " ok ")
    assert asyncio.run(gemini_generate(client, "p", "s")) == "ok"
