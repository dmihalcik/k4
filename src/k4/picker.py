"""fzf integration for the interactive picker (``k4d`` with no args)."""

from __future__ import annotations

import shutil
import subprocess

from k4 import K4Error


def pick(candidates: list[str], prompt: str = "k4> ") -> str | None:
    """Pipe ``candidates`` through fzf; return the chosen line, or None if cancelled."""
    if not candidates:
        return None
    if shutil.which("fzf") is None:
        raise K4Error("fzf not found. Install with: brew install fzf")

    proc = subprocess.run(
        ["fzf", "--ansi", "--prompt", prompt, "--height", "40%", "--reverse"],
        input="\n".join(candidates),
        capture_output=True,
        text=True,
    )
    # fzf exits 130 when the user cancels (Esc / Ctrl-C).
    if proc.returncode == 130:
        return None
    if proc.returncode != 0:
        raise K4Error(f"fzf failed:\n{proc.stderr.strip()}")
    selection = proc.stdout.strip()
    return selection or None
