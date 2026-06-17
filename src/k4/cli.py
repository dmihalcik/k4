"""k4 command-line entry point (Click)."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from k4 import K4Error, __version__, cache, display, github, jj, picker, workspace

COMPLETIONS_TTL = 60.0


def _err(msg: str) -> None:
    """Print a progress/status message to stderr (stdout is reserved for the path)."""
    click.echo(msg, err=True)


@click.group()
@click.version_option(__version__, prog_name="k4")
def cli() -> None:
    """Manage GitHub work with jj-vcs."""


@cli.command()
@click.argument("target", required=False)
def cd(target: str | None) -> None:
    """Resolve TARGET to a jj workspace and print its path.

    With no TARGET, launch an fzf picker over open PRs and your repos.
    """
    if not target:
        path = _interactive()
    else:
        resolved = workspace.resolve(target, Path.cwd())
        _err(f"Resolving {target} ...")
        path = workspace.materialize(resolved)
    click.echo(str(path))


def _interactive() -> Path:
    """Pick a PR or repo via fzf and return the workspace path."""
    prs = github.list_open_prs()
    repos = github.list_repos()

    choices: dict[str, tuple[str, str, int | None]] = {}
    lines: list[str] = []
    for pr in prs:
        # list_open_prs stows the repo's nameWithOwner in .head.
        label = f"PR    {pr.head}#{pr.number}  {pr.title}"
        choices[label] = ("pr", pr.head, pr.number)
        lines.append(label)
    for repo in repos:
        label = f"REPO  {repo.name_with_owner}"
        choices[label] = ("repo", repo.name_with_owner, None)
        lines.append(label)

    selection = picker.pick(lines)
    if selection is None:
        raise SystemExit(0)

    kind, nwo, num = choices[selection]
    org, repo_name = nwo.split("/", 1)
    if kind == "pr" and num is not None:
        pr = github.pr_view(num, repo=nwo)
        branch = pr.head if pr else None
        target: workspace.ResolvedTarget = workspace.BranchTarget(org, repo_name, branch)
    else:
        target = workspace.BranchTarget(org, repo_name, None)
    return workspace.materialize(target)


@cli.command(name=".")
def dot() -> None:
    """Show jj status combined with PR title, link, CI, and reviewers."""
    cwd = Path.cwd()
    status_text = jj.status(cwd=cwd)
    bookmark = jj.current_bookmark(cwd=cwd)
    pr = github.pr_for_branch(bookmark) if bookmark else None
    sys.stdout.write(display.render_status(status_text, pr, bookmark))


@cli.command()
@click.argument("prefix", required=False, default="")
def completions(prefix: str) -> None:
    """Print completion candidates (org/repo names) matching PREFIX."""
    repos: list[dict[str, str]] = cache.cached(
        "repos",
        COMPLETIONS_TTL,
        lambda: [{"nameWithOwner": r.name_with_owner} for r in github.list_repos()],
    )
    for r in repos:
        nwo = r["nameWithOwner"]
        if prefix in nwo:
            click.echo(nwo)


@cli.command(name="shell-init")
@click.argument("shell", type=click.Choice(["zsh", "bash"]))
def shell_init(shell: str) -> None:
    """Print the shell snippet to source (defines k4d + completion)."""
    click.echo(_ZSH_INIT if shell == "zsh" else _BASH_INIT)


_ZSH_INIT = """\
k4d() {
  local target
  target="$(command k4 cd "$@")" || return 1
  [[ -n "$target" ]] && cd "$target"
}
_k4d() {
  local -a cands
  cands=(${(f)"$(command k4 completions "${words[CURRENT]}" 2>/dev/null)"})
  compadd -- $cands
}
compdef _k4d k4d
"""

_BASH_INIT = """\
k4d() {
  local target
  target="$(command k4 cd "$@")" || return 1
  [[ -n "$target" ]] && cd "$target"
}
_k4d() {
  local cur="${COMP_WORDS[COMP_CWORD]}"
  COMPREPLY=( $(command k4 completions "$cur" 2>/dev/null) )
}
complete -F _k4d k4d
"""


def main() -> None:
    """Entry point. Catch K4Error and exit non-zero with a friendly message."""
    try:
        cli()
    except K4Error as exc:
        click.echo(f"k4: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
