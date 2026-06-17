"""Rendering for ``k4 .`` — combines jj status with GitHub PR context."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from k4.github import PullRequest

_CI_LABEL = {
    "passing": "✅ CI passing",
    "running": "🔄 CI running",
    "failing": "❌ CI failed",
    "none": "",
}

_REVIEW_EMOJI = {
    "APPROVED": "✅",
    "CHANGES_REQUESTED": "🔴",
    "COMMENTED": "💬",
    "PENDING": "○",
}


def osc8(url: str, label: str) -> str:
    """Wrap ``label`` in an OSC 8 hyperlink escape pointing at ``url``."""
    return f"\033]8;;{url}\033\\{label}\033]8;;\033\\"


def render_status(jj_status: str, pr: PullRequest | None, bookmark: str | None) -> str:
    """Return the full ``k4 .`` output as a string (for testability)."""
    console = Console(force_terminal=True, highlight=False)
    with console.capture() as capture:
        header = Text()
        header.append("● ", style="bold green")
        header.append(bookmark or "(no bookmark)", style="bold")
        console.print(header)

        if pr is None:
            console.print(
                Text(
                    f"  No PR found for bookmark {bookmark!r}"
                    if bookmark
                    else "  No bookmark on the current change",
                    style="dim",
                )
            )
        else:
            console.print()
            title_line = Text("  📌  ")
            title_line.append(f"PR #{pr.number}: {pr.title}", style="bold cyan")
            console.print(title_line)
            console.print(Text(f"      {pr.url}", style="blue underline"))

            badges: list[str] = []
            badges.append("🟡 Draft" if pr.is_draft else "🟢 Open")
            if ci := _CI_LABEL.get(pr.ci, ""):
                badges.append(ci)
            if pr.reviewers:
                badges.append(f"👁 {len(pr.reviewers)} reviewers")
            for issue in pr.linked_issues:
                badges.append(f"🔗 closes #{issue.number}")
            console.print(Text("  " + "  ".join(badges)))

            if pr.reviewers:
                console.print()
                console.print(Text("  Reviewers:", style="bold"))
                for r in pr.reviewers:
                    emoji = _REVIEW_EMOJI.get(r.state, "○")
                    state = r.state.replace("_", " ").lower() or "pending"
                    console.print(Text(f"    {emoji}  {r.name:<12} {state}"))

        console.print(Text("─" * 55, style="dim"))
        console.print(jj_status.rstrip())

    output = capture.get()
    if pr is not None:
        # Make the printed URL an OSC 8 hyperlink (rich would escape a raw one).
        output = output.replace(pr.url, osc8(pr.url, pr.url), 1)
    return output
