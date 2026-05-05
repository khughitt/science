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

## Project Installation

Use a project-local install when only one repository should see the Science
skills. Codex discovers repo-scoped skills from `.agents/skills/` directories
inside the project tree, so put the Science skill root there instead of under
`${CODEX_HOME:-$HOME/.codex}/skills`.

### Link an Existing Science Clone

If Science is already cloned somewhere on the machine:

```bash
cd <project-root>
mkdir -p .agents/skills
ln -s ~/.codex/science/codex-skills .agents/skills/science
```

Restart Codex from inside that project. The Science skills are available only
for that project tree.

### Vendor Science in the Project

If the project should carry its own Science checkout, keep the clone under
`.agents/` and link its generated Codex skills:

```bash
cd <project-root>
git clone https://github.com/khughitt/science.git .agents/science
mkdir -p .agents/skills
ln -s ../science/codex-skills .agents/skills/science
```

For a committed dependency, use a submodule instead of a plain clone:

```bash
cd <project-root>
git submodule add https://github.com/khughitt/science.git .agents/science
mkdir -p .agents/skills
ln -s ../science/codex-skills .agents/skills/science
```

### Windows

Use a junction inside the project:

```powershell
Set-Location <project-root>
New-Item -ItemType Directory -Force -Path ".agents\skills"
cmd /c mklink /J ".agents\skills\science" "$env:USERPROFILE\.codex\science\codex-skills"
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
