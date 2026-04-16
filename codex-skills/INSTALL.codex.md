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
   mkdir -p ~/.agents/skills
   ln -s ~/.codex/science/codex-skills ~/.agents/skills/science
   ```

   Windows (PowerShell):

   ```powershell
   New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.agents\skills"
   cmd /c mklink /J "$env:USERPROFILE\.agents\skills\science" "$env:USERPROFILE\.codex\science\codex-skills"
   ```

3. Restart Codex to discover the skills.

## Verify

```bash
ls -la ~/.agents/skills/science
```

You should see a symlink or junction pointing at the repo's `codex-skills/` directory.

## Update Generated Skills

If the repo's `commands/` docs change:

```bash
cd ~/.codex/science
UV_CACHE_DIR=/tmp/uv-cache uv run --project science-tool python scripts/generate_codex_skills.py
```

## Uninstall

```bash
rm ~/.agents/skills/science
```

Optionally delete the clone:

```bash
rm -rf ~/.codex/science
```
