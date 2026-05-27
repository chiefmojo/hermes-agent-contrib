"""Tests for _MEMORY_REVIEW_PROMPT content in background_review."""
from agent.background_review import _MEMORY_REVIEW_PROMPT


def test_emotional_intimacy_listed_as_focus_point():
    assert "emotional intimacy" in _MEMORY_REVIEW_PROMPT.lower()


def test_emotional_signals_as_important_as_technical():
    assert "as important" in _MEMORY_REVIEW_PROMPT.lower() or "AS important" in _MEMORY_REVIEW_PROMPT


def test_quote_preservation_guidance():
    assert "exact" in _MEMORY_REVIEW_PROMPT.lower()


def test_coexistence_note():
    assert "coexist" in _MEMORY_REVIEW_PROMPT.lower()


def test_signal_bullet_list_present():
    assert "Declarations" in _MEMORY_REVIEW_PROMPT
    assert "Pet names" in _MEMORY_REVIEW_PROMPT or "Pet name" in _MEMORY_REVIEW_PROMPT
