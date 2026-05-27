"""Tests for skip_memory gating in cron scheduler.

The cron scheduler used to hardcode skip_memory=True for all cron jobs,
preventing any cron job from doing memory lookups.  The fix resolves the
enabled toolsets into a variable first, then sets skip_memory=False only
when 'memory_search' appears in the resolved toolset list.  'memory_search'
is an explicit opt-in sentinel — it never appears in any platform-default
toolset list, so cron jobs with default or None toolsets always skip memory.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cron.scheduler import run_job


def _make_run_job_patches(tmp_path):
    """Common patches for run_job tests — mirrors the pattern in test_scheduler.py."""
    fake_db = MagicMock()
    return fake_db, [
        patch("cron.scheduler._hermes_home", tmp_path),
        patch("cron.scheduler._resolve_origin", return_value=None),
        patch("dotenv.load_dotenv"),
        patch("hermes_state.SessionDB", return_value=fake_db),
        patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            return_value={
                "api_key": "test-key",
                "base_url": "https://example.invalid/v1",
                "provider": "openrouter",
                "api_mode": "chat_completions",
            },
        ),
    ]


def _run_job_with_toolsets(enabled_toolsets, tmp_path):
    """Invoke run_job with a minimal job dict and given enabled_toolsets.

    Returns the kwargs captured from the AIAgent constructor call.
    """
    job = {
        "id": "test-job",
        "name": "test",
        "prompt": "say hi",
        "enabled_toolsets": enabled_toolsets,
    }

    fake_db, patches = _make_run_job_patches(tmp_path)
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patch("run_agent.AIAgent") as mock_agent_cls,
    ):
        mock_agent = MagicMock()
        mock_agent.run_conversation.return_value = {"final_response": "done"}
        mock_agent_cls.return_value = mock_agent
        run_job(job)

    assert mock_agent_cls.called, "AIAgent was never constructed"
    return mock_agent_cls.call_args.kwargs


def test_skip_memory_true_when_toolsets_none(tmp_path):
    """skip_memory must be True when enabled_toolsets is None (no explicit opt-in)."""
    kwargs = _run_job_with_toolsets(None, tmp_path)
    assert kwargs["skip_memory"] is True, (
        f"Expected skip_memory=True when toolsets=None; "
        f"got {kwargs['skip_memory']!r}"
    )


def test_skip_memory_true_when_memory_search_absent(tmp_path):
    """skip_memory must be True when memory_search is not in enabled_toolsets."""
    kwargs = _run_job_with_toolsets(["web_search", "code"], tmp_path)
    assert kwargs["skip_memory"] is True, (
        f"Expected skip_memory=True when memory_search not in toolsets; "
        f"got {kwargs['skip_memory']!r}"
    )


def test_skip_memory_false_when_memory_search_present(tmp_path):
    """skip_memory must be False when memory_search is explicitly in enabled_toolsets."""
    kwargs = _run_job_with_toolsets(["memory_search", "web_search"], tmp_path)
    assert kwargs["skip_memory"] is False, (
        f"Expected skip_memory=False when memory_search in toolsets; "
        f"got {kwargs['skip_memory']!r}"
    )
