"""Tests for workspace resolution and the issue-branch flow."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from k4 import K4Error, workspace
from k4.github import PullRequest
from k4.workspace import BranchTarget, IssueTarget


def _pr(head: str) -> PullRequest:
    return PullRequest(
        number=1, title="t", url="u", state="OPEN", is_draft=True, head=head, ci="none"
    )


@pytest.fixture
def dev_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A cwd that looks like ~/dev/acme/myapp/branch."""
    monkeypatch.setattr(workspace, "DEV_ROOT", tmp_path)
    cwd = tmp_path / "acme" / "myapp" / "feature"
    cwd.mkdir(parents=True)
    return cwd


def test_resolve_org_repo_issue() -> None:
    t = workspace.resolve("acme/myapp#42", Path("/tmp"))
    assert t == IssueTarget("acme", "myapp", 42)


def test_resolve_org_repo_default_branch() -> None:
    t = workspace.resolve("acme/myapp", Path("/tmp"))
    assert t == BranchTarget("acme", "myapp", None)


def test_resolve_integer_as_pr(dev_repo: Path) -> None:
    with mock.patch.object(workspace.github, "pr_view", return_value=_pr("pr-branch")):
        t = workspace.resolve("123", dev_repo)
    assert t == BranchTarget("acme", "myapp", "pr-branch")


def test_resolve_integer_as_issue_when_no_pr(dev_repo: Path) -> None:
    with mock.patch.object(workspace.github, "pr_view", return_value=None):
        t = workspace.resolve("123", dev_repo)
    assert t == IssueTarget("acme", "myapp", 123)


def test_resolve_integer_without_context_errors(tmp_path: Path) -> None:
    with pytest.raises(K4Error, match="Specify repo"):
        workspace.resolve("123", tmp_path)


def test_resolve_bare_branch_in_repo(dev_repo: Path) -> None:
    t = workspace.resolve("my-branch", dev_repo)
    assert t == BranchTarget("acme", "myapp", "my-branch")


def test_resolve_bare_branch_without_context_errors(tmp_path: Path) -> None:
    with pytest.raises(K4Error, match="can't resolve branch"):
        workspace.resolve("my-branch", tmp_path)


def test_current_repo_outside_dev_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workspace, "DEV_ROOT", tmp_path / "dev")
    assert workspace.current_repo(tmp_path) is None


def test_slugify() -> None:
    assert workspace.slugify("Add Widget Support!") == "add-widget-support"
    assert workspace.slugify("  weird __ name  ") == "weird-name"
    assert workspace.slugify("???") == "issue"


def test_ensure_workspace_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workspace, "DEV_ROOT", tmp_path)
    repo_root = tmp_path / "acme" / "myapp"
    (repo_root / "main").mkdir(parents=True)  # repo + workspace already present
    with mock.patch.object(workspace.jj, "workspace_add") as add:
        path = workspace.ensure_workspace("acme", "myapp", "main")
    assert path == repo_root / "main"
    add.assert_not_called()


def test_ensure_workspace_creates_and_tracks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workspace, "DEV_ROOT", tmp_path)
    repo_root = tmp_path / "acme" / "myapp"
    repo_root.mkdir(parents=True)  # repo cloned, branch workspace missing

    def fake_add(root: Path, name: str) -> Path:
        (root / name).mkdir()
        return root / name

    with (
        mock.patch.object(workspace.jj, "git_fetch"),
        mock.patch.object(workspace.jj, "workspace_add", side_effect=fake_add),
        mock.patch.object(workspace.jj, "bookmark_track") as track,
        mock.patch.object(workspace.jj, "new") as new,
    ):
        path = workspace.ensure_workspace("acme", "myapp", "feature/x")

    assert path == repo_root / "feature-x"  # '/' flattened in dir name
    track.assert_called_once_with("feature/x")
    new.assert_called_once()
    assert "feature-x/" in (repo_root / ".gitignore").read_text()


def test_create_issue_branch_makes_draft_pr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workspace, "DEV_ROOT", tmp_path)
    repo_root = tmp_path / "acme" / "myapp"
    repo_root.mkdir(parents=True)

    from k4.github import Issue

    def fake_add(root: Path, name: str) -> Path:
        (root / name).mkdir()
        return root / name

    with (
        mock.patch.object(
            workspace.github,
            "issue_view",
            return_value=Issue(42, "Add Widget Support", []),
        ),
        mock.patch.object(workspace.github, "repo_default_branch", return_value="main"),
        mock.patch.object(workspace.jj, "git_fetch"),
        mock.patch.object(workspace.jj, "workspace_add", side_effect=fake_add),
        mock.patch.object(workspace.jj, "new"),
        mock.patch.object(workspace.jj, "bookmark_create"),
        mock.patch.object(workspace.jj, "git_push"),
        mock.patch.object(workspace.github, "create_draft_pr") as create_pr,
    ):
        path = workspace.create_issue_branch("acme", "myapp", 42)

    assert path == repo_root / "42-add-widget-support"
    _, kwargs = create_pr.call_args
    assert kwargs["body"] == "Implements #42\n\nCloses #42"
    assert kwargs["head"] == "42-add-widget-support"


def test_create_issue_branch_bug_uses_fixes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workspace, "DEV_ROOT", tmp_path)
    repo_root = tmp_path / "acme" / "myapp"
    repo_root.mkdir(parents=True)

    from k4.github import Issue

    def fake_add(root: Path, name: str) -> Path:
        (root / name).mkdir()
        return root / name

    with (
        mock.patch.object(
            workspace.github,
            "issue_view",
            return_value=Issue(7, "Crash on save", ["bug"]),
        ),
        mock.patch.object(workspace.github, "repo_default_branch", return_value="main"),
        mock.patch.object(workspace.jj, "git_fetch"),
        mock.patch.object(workspace.jj, "workspace_add", side_effect=fake_add),
        mock.patch.object(workspace.jj, "new"),
        mock.patch.object(workspace.jj, "bookmark_create"),
        mock.patch.object(workspace.jj, "git_push"),
        mock.patch.object(workspace.github, "create_draft_pr") as create_pr,
    ):
        workspace.create_issue_branch("acme", "myapp", 7)

    _, kwargs = create_pr.call_args
    assert kwargs["body"] == "Fixes #7"
