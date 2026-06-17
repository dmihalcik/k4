"""Tests for the fzf picker integration."""

from __future__ import annotations

import subprocess
from unittest import mock

import pytest

from k4 import K4Error, picker


def _completed(stdout: str = "", code: int = 0):
    return subprocess.CompletedProcess(args=["fzf"], returncode=code, stdout=stdout)


def test_pick_returns_selection() -> None:
    with (
        mock.patch.object(picker.shutil, "which", return_value="/usr/bin/fzf"),
        mock.patch.object(subprocess, "run", return_value=_completed("chosen\n")) as run,
    ):
        result = picker.pick(["a", "chosen", "c"])
    assert result == "chosen"
    # candidates piped via stdin
    assert run.call_args.kwargs["input"] == "a\nchosen\nc"


def test_pick_cancelled_returns_none() -> None:
    with (
        mock.patch.object(picker.shutil, "which", return_value="/usr/bin/fzf"),
        mock.patch.object(subprocess, "run", return_value=_completed("", code=130)),
    ):
        assert picker.pick(["a", "b"]) is None


def test_pick_empty_candidates_returns_none() -> None:
    assert picker.pick([]) is None


def test_pick_missing_fzf_raises() -> None:
    with (
        mock.patch.object(picker.shutil, "which", return_value=None),
        pytest.raises(K4Error, match="brew install fzf"),
    ):
        picker.pick(["a"])
