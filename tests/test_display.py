"""Tests for k4 . rendering."""

from __future__ import annotations

from k4 import display
from k4.github import LinkedIssue, PullRequest, Reviewer


def test_osc8_wraps_url() -> None:
    seq = display.osc8("https://example.com", "label")
    assert seq == "\033]8;;https://example.com\033\\label\033]8;;\033\\"


def _pr() -> PullRequest:
    return PullRequest(
        number=123,
        title="Add widget support",
        url="https://github.com/acme/myapp/pull/123",
        state="OPEN",
        is_draft=True,
        head="feature",
        ci="passing",
        reviewers=[
            Reviewer("alice", "APPROVED"),
            Reviewer("bob", "PENDING"),
        ],
        linked_issues=[LinkedIssue(42, "the issue")],
    )


def test_render_includes_pr_details_and_hyperlink() -> None:
    out = display.render_status("M file.py", _pr(), "feature")
    assert "PR #123: Add widget support" in out
    assert "🟡 Draft" in out
    assert "✅ CI passing" in out
    assert "🔗 closes #42" in out
    assert "alice" in out and "bob" in out
    # OSC 8 hyperlink for the URL present.
    assert "\033]8;;https://github.com/acme/myapp/pull/123" in out
    # jj status passed through.
    assert "M file.py" in out


def test_render_no_pr_fallback() -> None:
    out = display.render_status("M file.py", None, "feature")
    assert "No PR found for bookmark 'feature'" in out
    assert "M file.py" in out


def test_render_no_bookmark() -> None:
    out = display.render_status("clean", None, None)
    assert "No bookmark" in out
