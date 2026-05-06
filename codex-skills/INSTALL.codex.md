# Installing Science for Codex

Enable Science skills in Codex via native skill discovery.

## Prerequisites

- Git

## Installation

1. Clone the Science repository:

   ```bash
   git clone https://github.com/khughitt/science.git ~/.codex/science
   ```

2. Create the skills symlink:

   ```bash
   mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
   ln -s ~/.codex/science/codex-skills "${CODEX_HOME:-$HOME/.codex}/skills/science"
   ```

   Windows (PowerShell):

   ```powershell
   $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { "$env:USERPROFILE\.codex" }
   New-Item -ItemType Directory -Force -Path "$CodexHome\skills"
   cmd /c mklink /J "$CodexHome\skills\science" "$env:USERPROFILE\.codex\science\codex-skills"
   ```

3. Restart Codex to discover the skills.

## Verify

```bash
ls -la "${CODEX_HOME:-$HOME/.codex}/skills/science"
```

You should see a symlink or junction pointing at the repo's `codex-skills/` directory.

`codex-skills/INDEX.md` lists the installed Science command skills and companion
methodology skills. Command skills reference the Codex-facing companion skills
`science-research-methodology` and `science-scientific-writing`.

## Update Generated Skills

If the repo's `commands/` docs change:

```bash
cd ~/.codex/science
UV_CACHE_DIR=/tmp/uv-cache uv run --project science python scripts/generate_codex_skills.py
```

## Uninstall

```bash
rm "${CODEX_HOME:-$HOME/.codex}/skills/science"
```

Optionally delete the clone:

```bash
rm -rf ~/.codex/science
```
