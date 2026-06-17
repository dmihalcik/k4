"""Thin wrappers around the `jj` CLI.

Every function shells out via the single ``_run`` helper so tests can mock one
seam. Functions return parsed data (str / list / Path), never raw CompletedProcess.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from k4 import K4Error


def _run(args: list[str], cwd: Path | str | None = None) -> str:
    """Run ``jj <args>`` and return stdout. Raise K4Error on failure."""
    try:
        proc = subprocess.run(
            ["jj", *args],
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise K4Error("jj not found. Install with: brew install jj") from exc
    if proc.returncode != 0:
        raise K4Error(f"jj {' '.join(args)} failed:\n{proc.stderr.strip()}")
    return proc.stdout


def clone(url: str, dest: Path) -> None:
    """Clone ``url`` into ``dest`` as a jj+git repo."""
    _run(["git", "clone", url, str(dest)])


def workspace_add(repo_root: Path, name: str) -> Path:
    """Add a jj workspace ``name`` under ``repo_root`` and return its path."""
    path = repo_root / name
    _run(["workspace", "add", str(path)], cwd=repo_root)
    return path


def workspace_list(repo_root: Path) -> dict[str, str]:
    """Return a mapping of workspace name -> change id from ``jj workspace list``."""
    out = _run(["workspace", "list"], cwd=repo_root)
    result: dict[str, str] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        name, _, rest = line.partition(":")
        result[name.strip()] = rest.strip()
    return result


def bookmark_track(branch: str, remote: str = "origin") -> None:
    """Start tracking ``branch@remote`` as a local bookmark."""
    _run(["bookmark", "track", f"{branch}@{remote}"])


def bookmark_create(name: str, cwd: Path | str | None = None) -> None:
    """Create a local bookmark ``name`` pointing at the working-copy commit."""
    _run(["bookmark", "create", name, "-r", "@"], cwd=cwd)


def git_push(bookmark: str, cwd: Path | str | None = None) -> None:
    """Push ``bookmark`` to the git remote, creating it if needed."""
    _run(["git", "push", "--allow-new", "--bookmark", bookmark], cwd=cwd)


def new(revision: str, cwd: Path | str | None = None) -> None:
    """Create a new working-copy commit on top of ``revision``."""
    _run(["new", revision], cwd=cwd)


def git_fetch(cwd: Path | str | None = None) -> None:
    """Fetch from the git remote."""
    _run(["git", "fetch"], cwd=cwd)


def status(cwd: Path | str | None = None) -> str:
    """Return the raw text of ``jj status``."""
    return _run(["status"], cwd=cwd)


def current_bookmark(cwd: Path | str | None = None) -> str | None:
    """Return the nearest bookmark at or behind the working copy, if any.

    After ``jj new <branch>`` the working copy is an empty child of the branch,
    so the bookmark sits on an ancestor. ``latest(::@ & bookmarks())`` finds the
    closest ancestor that carries a bookmark.
    """
    out = _run(
        [
            "log",
            "-r",
            "latest(::@ & bookmarks())",
            "--no-graph",
            "-T",
            'bookmarks.join("\n")',
        ],
        cwd=cwd,
    ).strip()
    if not out:
        return None
    # Strip jj's markers like "name*" (ahead of remote) / "name@origin".
    first = out.splitlines()[0].strip()
    return first.split("@", 1)[0].rstrip("*") or None
