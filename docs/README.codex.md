# Science for Codex

Guide for using Science with OpenAI Codex via native skill discovery.

## Quick Install

Tell Codex:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/khughitt/science/refs/heads/main/codex-skills/INSTALL.codex.md
```

## Manual Installation

### Prerequisites

- OpenAI Codex CLI
- Git

### Steps

1. Clone the repo:

   ```bash
   git clone https://github.com/khughitt/science.git ~/.codex/science
   ```

2. Create the skills symlink:

   ```bash
   mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
   ln -s ~/.codex/science/codex-skills "${CODEX_HOME:-$HOME/.codex}/skills/science"
   ```

3. Restart Codex.

### Windows

Use a junction instead of a symlink:

```powershell
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { "$env:USERPROFILE\.codex" }
New-Item -ItemType Directory -Force -Path "$CodexHome\skills"
cmd /c mklink /J "$CodexHome\skills\science" "$env:USERPROFILE\.codex\science\codex-skills"
```

## What Is Installed

Codex discovers all generated `science-*` skills from `codex-skills/`.
Command skills are generated from the Claude command corpus in `commands/`.
Companion methodology skills are adapted from the canonical Science `skills/`
tree so command skills can invoke them through native Codex skill discovery.

See `codex-skills/INDEX.md` for the complete generated map.

Examples:

- `science-status`
- `science-research-topic`
- `science-search-literature`
- `science-add-hypothesis`
- `science-research-methodology`
- `science-scientific-writing`

## Regenerating Skills

If the Claude command docs change, regenerate the Codex skill tree:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --project science-tool python scripts/generate_codex_skills.py
```

## Verification

Run the generator tests:

```bash
cd ~/.codex/science/science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --project . pytest tests/test_codex_skills.py -q
```

## Updating

```bash
cd ~/.codex/science && git pull
```

If command docs changed, rerun the generator command above.
