"""Workspace path resolution and creation.

``resolve`` turns a user-typed target into a structured ``ResolvedTarget``
(implementing the input table from the design spec). ``ensure_workspace`` and
``create_issue_branch`` carry out the resulting filesystem + jj + gh actions and
return the path the shell should ``cd`` into.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from k4 import K4Error, github, jj

DEV_ROOT = Path.home() / "dev"


@dataclass
class BranchTarget:
    """Open the workspace for ``branch`` (or the default branch if None)."""

    org: str
    repo: str
    branch: str | None


@dataclass
class IssueTarget:
    """Create a branch + draft PR for ``issue`` in ``org/repo``."""

    org: str
    repo: str
    issue: int


ResolvedTarget = BranchTarget | IssueTarget

_ISSUE_RE = re.compile(r"^(?P<org>[\w.-]+)/(?P<repo>[\w.-]+)#(?P<num>\d+)$")
_REPO_RE = re.compile(r"^(?P<org>[\w.-]+)/(?P<repo>[\w.-]+)$")


def current_repo(cwd: Path) -> tuple[str, str] | None:
    """Derive ``(org, repo)`` from ``cwd`` if it lives under ``~/dev/<org>/<repo>``."""
    try:
        rel = cwd.resolve().relative_to(DEV_ROOT.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None


def resolve(target: str, cwd: Path) -> ResolvedTarget:
    """Resolve a user-typed target into a ResolvedTarget. May call gh."""
    target = target.strip()

    if m := _ISSUE_RE.match(target):
        return IssueTarget(m["org"], m["repo"], int(m["num"]))

    if target.isdigit():
        ctx = current_repo(cwd)
        if ctx is None:
            raise K4Error("Specify repo: k4 cd org/repo#123")
        org, repo = ctx
        pr = github.pr_view(int(target))
        if pr is not None:
            return BranchTarget(org, repo, pr.head)
        return IssueTarget(org, repo, int(target))

    if m := _REPO_RE.match(target):
        return BranchTarget(m["org"], m["repo"], None)

    # Bare word: a branch in the current repo.
    ctx = current_repo(cwd)
    if ctx is None:
        raise K4Error(f"Not in a repo workspace; can't resolve branch {target!r}")
    org, repo = ctx
    return BranchTarget(org, repo, target)


def slugify(text: str) -> str:
    """Lowercase, hyphenate, collapse repeats — for branch names."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "issue"


def _workspace_dirname(branch: str) -> str:
    """Map a branch name to a flat directory name (branch names may contain '/')."""
    return branch.replace("/", "-")


def _add_to_gitignore(repo_root: Path, entry: str) -> None:
    """Append ``entry/`` to the repo-root .gitignore if not already present."""
    gitignore = repo_root / ".gitignore"
    line = f"{entry}/"
    existing = gitignore.read_text().splitlines() if gitignore.exists() else []
    if line in existing:
        return
    with gitignore.open("a") as fh:
        if existing and existing[-1] != "":
            fh.write("\n")
        fh.write(line + "\n")


def _ensure_repo_root(org: str, repo: str) -> Path:
    """Return the repo root, cloning it on first use."""
    repo_root = DEV_ROOT / org / repo
    if not repo_root.exists():
        url = github.repo_clone_url(f"{org}/{repo}")
        repo_root.parent.mkdir(parents=True, exist_ok=True)
        jj.clone(url, repo_root)
    return repo_root


def materialize(target: ResolvedTarget) -> Path:
    """Carry out a resolved target and return the path to cd into."""
    if isinstance(target, IssueTarget):
        return create_issue_branch(target.org, target.repo, target.issue)
    branch = target.branch or github.repo_default_branch(f"{target.org}/{target.repo}")
    return ensure_workspace(target.org, target.repo, branch)


def ensure_workspace(org: str, repo: str, branch: str) -> Path:
    """Ensure a workspace tracking remote ``branch`` exists; return its path."""
    repo_root = _ensure_repo_root(org, repo)
    path = repo_root / _workspace_dirname(branch)
    if path.exists():
        return path

    jj.git_fetch(cwd=repo_root)
    jj.workspace_add(repo_root, _workspace_dirname(branch))
    jj.bookmark_track(branch)
    jj.new(branch, cwd=path)
    _add_to_gitignore(repo_root, _workspace_dirname(branch))
    return path


def create_issue_branch(org: str, repo: str, issue_number: int) -> Path:
    """Create a branch + draft PR for an issue; return the workspace path."""
    repo_root = _ensure_repo_root(org, repo)
    issue = github.issue_view(issue_number, repo=f"{org}/{repo}")

    branch = f"{issue_number}-{slugify(issue.title)}"[:60].rstrip("-")
    dirname = _workspace_dirname(branch)
    path = repo_root / dirname
    if path.exists():
        return path

    default = github.repo_default_branch(f"{org}/{repo}")
    jj.git_fetch(cwd=repo_root)
    jj.workspace_add(repo_root, dirname)
    jj.new(default, cwd=path)
    jj.bookmark_create(branch, cwd=path)
    jj.git_push(branch, cwd=path)

    verb = "Fixes" if issue.is_bug else "Implements"
    body = f"{verb} #{issue_number}"
    if not issue.is_bug:
        body += f"\n\nCloses #{issue_number}"
    github.create_draft_pr(title=f"WIP: {issue.title}", body=body, head=branch)

    _add_to_gitignore(repo_root, dirname)
    return path
