# k4

A personal CLI for managing GitHub work on top of [jj-vcs](https://github.com/jj-vcs/jj).

`k4` collapses the multi-step dance of moving between active branches/PRs across
repos (clone → workspace add → bookmark track → cd) into a single command, and
enriches your terminal with PR context.

## Install

Prerequisites: `jj`, `gh`, and (for the interactive picker) `fzf` on your `$PATH`.

### 1. Install the `k4` binary

`k4` isn't published to PyPI yet, so install it from your local checkout.
`--editable` tracks your working copy, so edits take effect without reinstalling:

```bash
git clone https://github.com/dmihalcik/k4 ~/dev/k4   # or your fork
uv tool install --editable ~/dev/k4
```

### 2. Make sure it's on your `$PATH`

`uv` installs tools into `~/.local/bin`. Add it to your `$PATH` if it isn't
already:

```bash
# zsh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc

# bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

(`uv tool update-shell` does this for you.)

### 3. Enable the `k4d` alias and tab completion

`k4 shell-init` prints a snippet that defines the `k4d` shell function (so `cd`
happens in your shell) and wires up tab completion. Source it from your rc file:

```bash
# zsh
echo 'eval "$(k4 shell-init zsh)"' >> ~/.zshrc

# bash
echo 'eval "$(k4 shell-init bash)"' >> ~/.bashrc
```

Reload your shell (or `source ~/.zshrc` / `source ~/.bashrc`) and you're set:

```bash
k4d                # fuzzy-pick a PR or repo
k4d org/repo       # jump to a repo's default branch
k4 .               # show status for the current workspace
```

## Commands

- `k4d` — fuzzy-pick an open PR or repo and `cd` into its jj workspace.
- `k4d <target>` — jump directly. Targets:
  - `org/repo` → default branch
  - `branch-name` → that branch in the current repo
  - `123` → PR #123 (in a workspace) or issue #123 → new branch + draft PR
  - `org/repo#123` → issue #123 in that repo → new branch + draft PR
- `k4 .` — show jj status combined with PR title, link, CI, and reviewers.

## Development

```bash
uv sync
uv run pytest
uv run pyright
uv run ruff check .
```
