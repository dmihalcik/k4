"""Tests for the jj wrappers."""

from __future__ import annotations

from unittest import mock

from k4 import jj


def test_current_bookmark_uses_nearest_ancestor_revset() -> None:
    with mock.patch.object(jj, "_run", return_value="main\n") as run:
        assert jj.current_bookmark() == "main"
    # The revset must look at ancestors, not just @ (jj new makes @ a child).
    args = run.call_args.args[0]
    assert "latest(::@ & bookmarks())" in args


def test_current_bookmark_strips_markers() -> None:
    with mock.patch.object(jj, "_run", return_value="feature*@origin\n"):
        assert jj.current_bookmark() == "feature"


def test_current_bookmark_none_when_empty() -> None:
    with mock.patch.object(jj, "_run", return_value="\n"):
        assert jj.current_bookmark() is None
