"""Tests for the gh wrappers — JSON parsing and error handling."""

from __future__ import annotations

import json
import subprocess
from unittest import mock

import pytest

from k4 import K4Error, github


def _completed(stdout: str = "", stderr: str = "", code: int = 0):
    return subprocess.CompletedProcess(args=["gh"], returncode=code, stdout=stdout, stderr=stderr)


def test_parse_pr_collapses_reviews_and_ci() -> None:
    data = {
        "number": 12,
        "title": "Add widget",
        "url": "https://github.com/acme/myapp/pull/12",
        "state": "OPEN",
        "isDraft": True,
        "headRefName": "feature",
        "statusCheckRollup": [{"status": "COMPLETED", "conclusion": "SUCCESS"}],
        "reviews": [{"author": {"login": "alice"}, "state": "APPROVED"}],
        "reviewRequests": [{"login": "bob"}],
        "closingIssuesReferences": [{"number": 42, "title": "the issue"}],
    }
    with mock.patch.object(github, "_run_json", return_value=data):
        pr = github.pr_view(12)
    assert pr is not None
    assert pr.ci == "passing"
    assert pr.is_draft is True
    assert {r.name: r.state for r in pr.reviewers} == {
        "alice": "APPROVED",
        "bob": "PENDING",
    }
    assert pr.linked_issues[0].number == 42


def test_ci_status_failing_and_running() -> None:
    assert github._ci_status([{"status": "COMPLETED", "conclusion": "FAILURE"}]) == "failing"
    assert github._ci_status([{"status": "IN_PROGRESS"}]) == "running"
    assert github._ci_status([]) == "none"
    assert github._ci_status(None) == "none"


def test_pr_for_branch_none_when_empty() -> None:
    with mock.patch.object(github, "_run_json", return_value=[]):
        assert github.pr_for_branch("nope") is None


def test_issue_is_bug() -> None:
    data = {"number": 5, "title": "Boom", "labels": [{"name": "Bug"}]}
    with mock.patch.object(github, "_run_json", return_value=data):
        issue = github.issue_view(5)
    assert issue.is_bug is True


def test_auth_error_is_friendly() -> None:
    proc = _completed(stderr="You are not logged into any GitHub hosts", code=1)
    with (
        mock.patch.object(subprocess, "run", return_value=proc),
        pytest.raises(K4Error, match="gh auth login"),
    ):
        github._run(["pr", "list"])


def test_missing_gh_binary() -> None:
    with (
        mock.patch.object(subprocess, "run", side_effect=FileNotFoundError),
        pytest.raises(K4Error, match="brew install gh"),
    ):
        github._run(["pr", "list"])


def test_list_open_prs_carries_repo_in_head() -> None:
    data = [
        {"number": 3, "title": "x", "repository": {"nameWithOwner": "acme/myapp"}},
    ]
    with mock.patch.object(github, "_run_json", return_value=data):
        prs = github.list_open_prs()
    assert prs[0].head == "acme/myapp"


def test_run_json_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"a": 1}
    with mock.patch.object(github, "_run", return_value=json.dumps(payload)):
        assert github._run_json(["x"]) == payload


def test_list_repos_merges_owned_and_starred() -> None:
    owned = [{"nameWithOwner": "acme/myapp", "description": "mine"}]
    # `gh api ... --jq` returns newline-separated plain text, not JSON.
    starred_text = "acme/myapp\nother/cool-lib\n"
    with (
        mock.patch.object(github, "_run_json", return_value=owned),
        mock.patch.object(github, "_run", return_value=starred_text),
    ):
        repos = github.list_repos()
    names = [r.name_with_owner for r in repos]
    assert names == ["acme/myapp", "other/cool-lib"]  # deduped, owned first
