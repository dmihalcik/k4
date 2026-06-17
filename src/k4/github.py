"""Thin wrappers around the `gh` CLI.

All GitHub access goes through ``_run`` (raw stdout) or ``_run_json`` (parsed).
Parsed results are returned as typed dataclasses so callers — and pyright — get
a stable shape instead of raw ``Any`` JSON.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any, cast

from k4 import K4Error

# Fields requested from `gh pr view` / `gh pr list`.
PR_JSON_FIELDS = (
    "number,title,url,state,isDraft,statusCheckRollup,"
    "reviewRequests,reviews,closingIssuesReferences,headRefName"
)


@dataclass
class Reviewer:
    name: str
    state: str  # APPROVED / CHANGES_REQUESTED / COMMENTED / PENDING


@dataclass
class LinkedIssue:
    number: int
    title: str


@dataclass
class PullRequest:
    number: int
    title: str
    url: str
    state: str
    is_draft: bool
    head: str
    ci: str  # "passing" / "running" / "failing" / "none"
    reviewers: list[Reviewer] = field(default_factory=lambda: [])
    linked_issues: list[LinkedIssue] = field(default_factory=lambda: [])


@dataclass
class Issue:
    number: int
    title: str
    labels: list[str]

    @property
    def is_bug(self) -> bool:
        return any(label.lower() == "bug" for label in self.labels)


@dataclass
class Repo:
    name_with_owner: str  # "org/repo"
    description: str = ""


def _run(args: list[str]) -> str:
    """Run ``gh <args>`` and return stdout. Raise K4Error on failure."""
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise K4Error("gh not found. Install with: brew install gh") from exc
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if "auth" in stderr.lower() or "logged" in stderr.lower():
            raise K4Error("GitHub CLI not authenticated. Run: gh auth login")
        raise K4Error(f"gh {' '.join(args)} failed:\n{stderr}")
    return proc.stdout


def _run_json(args: list[str]) -> Any:
    """Run ``gh <args>`` and parse stdout as JSON."""
    out = _run(args).strip()
    if not out:
        return None
    return json.loads(out)


def _obj(value: Any) -> dict[str, Any]:
    """Treat a JSON value as an object (None becomes empty)."""
    return cast("dict[str, Any]", value or {})


def _arr(value: Any) -> list[dict[str, Any]]:
    """Treat a JSON value as an array of objects (None becomes empty)."""
    return cast("list[dict[str, Any]]", value or [])


def _ci_status(rollup: Any) -> str:
    """Collapse a statusCheckRollup array into one of our status words."""
    checks = _arr(rollup)
    if not checks:
        return "none"
    states: list[str] = []
    for check in checks:
        # Checks expose `conclusion`+`status`; statuses expose `state`.
        if check.get("state"):
            states.append(str(check["state"]).upper())
        elif check.get("status") == "COMPLETED":
            states.append(str(check.get("conclusion", "")).upper())
        else:
            states.append("IN_PROGRESS")
    if any(s in ("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT") for s in states):
        return "failing"
    if any(s in ("IN_PROGRESS", "PENDING", "QUEUED", "") for s in states):
        return "running"
    return "passing"


def _parse_pr(data: dict[str, Any]) -> PullRequest:
    reviewers: list[Reviewer] = []
    # Latest review state per author from `reviews`.
    latest: dict[str, str] = {}
    for review in _arr(data.get("reviews")):
        author = _obj(review.get("author")).get("login")
        if author:
            latest[str(author)] = str(review.get("state", ""))
    for author, state in latest.items():
        reviewers.append(Reviewer(name=author, state=state))
    # Requested-but-not-yet-reviewed reviewers show as PENDING.
    for req in _arr(data.get("reviewRequests")):
        login = req.get("login")
        if login and login not in latest:
            reviewers.append(Reviewer(name=str(login), state="PENDING"))

    linked: list[LinkedIssue] = []
    for issue in _arr(data.get("closingIssuesReferences")):
        linked.append(LinkedIssue(number=int(issue["number"]), title=str(issue.get("title", ""))))

    return PullRequest(
        number=int(data["number"]),
        title=str(data["title"]),
        url=str(data["url"]),
        state=str(data["state"]),
        is_draft=bool(data.get("isDraft", False)),
        head=str(data.get("headRefName", "")),
        ci=_ci_status(data.get("statusCheckRollup")),
        reviewers=reviewers,
        linked_issues=linked,
    )


def pr_for_branch(branch: str) -> PullRequest | None:
    """Return the open PR whose head is ``branch`` in the current repo, if any."""
    data = _arr(_run_json(["pr", "list", "--head", branch, "--json", PR_JSON_FIELDS]))
    if not data:
        return None
    return _parse_pr(data[0])


def pr_view(number: int, repo: str | None = None) -> PullRequest | None:
    """Return PR ``number``, or None if it doesn't exist.

    ``repo`` is ``org/repo`` or None for the current repo.
    """
    args = ["pr", "view", str(number), "--json", PR_JSON_FIELDS]
    if repo:
        args += ["--repo", repo]
    try:
        data = _run_json(args)
    except K4Error:
        return None
    if not data:
        return None
    return _parse_pr(_obj(data))


def issue_view(number: int, repo: str | None = None) -> Issue:
    """Return issue ``number``. ``repo`` is ``org/repo`` or None for current repo."""
    args = ["issue", "view", str(number), "--json", "number,title,labels"]
    if repo:
        args += ["--repo", repo]
    data = _obj(_run_json(args))
    labels = [str(lbl.get("name", "")) for lbl in _arr(data.get("labels"))]
    return Issue(number=int(data["number"]), title=str(data["title"]), labels=labels)


def list_repos() -> list[Repo]:
    """Return personal + starred repos for completion (deduplicated)."""
    repos: dict[str, Repo] = {}
    owned = _run_json(["repo", "list", "--limit", "200", "--json", "nameWithOwner,description"])
    for r in _arr(owned):
        nwo = str(r["nameWithOwner"])
        repos[nwo] = Repo(nwo, str(r.get("description") or ""))
    # --jq emits newline-separated plain text, not JSON.
    starred = _run(["api", "user/starred?per_page=100", "--jq", ".[].full_name"])
    for nwo in starred.splitlines():
        nwo = nwo.strip()
        if nwo and nwo not in repos:
            repos[nwo] = Repo(nwo)
    return list(repos.values())


def list_open_prs() -> list[PullRequest]:
    """Return the user's open PRs across repos (for completion)."""
    data = _run_json(
        [
            "search",
            "prs",
            "--author",
            "@me",
            "--state",
            "open",
            "--json",
            "number,title,repository",
            "--limit",
            "100",
        ]
    )
    prs: list[PullRequest] = []
    for r in _arr(data):
        repo = _obj(r.get("repository")).get("nameWithOwner", "")
        prs.append(
            PullRequest(
                number=int(r["number"]),
                title=str(r["title"]),
                url="",
                state="OPEN",
                is_draft=False,
                head=str(repo),  # reuse head to carry repo for the picker label
                ci="none",
            )
        )
    return prs


def repo_default_branch(org_repo: str) -> str:
    """Return the default branch name of ``org/repo``."""
    data = _obj(_run_json(["repo", "view", org_repo, "--json", "defaultBranchRef"]))
    ref = _obj(data.get("defaultBranchRef"))
    return str(ref.get("name", "main"))


def repo_clone_url(org_repo: str) -> str:
    """Return the ssh clone URL for ``org/repo``."""
    data = _obj(_run_json(["repo", "view", org_repo, "--json", "sshUrl"]))
    return str(data["sshUrl"])


def create_draft_pr(title: str, body: str, head: str) -> str:
    """Create a draft PR from ``head`` and return its URL."""
    return _run(
        ["pr", "create", "--draft", "--title", title, "--body", body, "--head", head]
    ).strip()
