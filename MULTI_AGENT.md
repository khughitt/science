# Multi-Agent Support

Science skills and commands are now available in three coding agents:

- **Crush** — see [INSTALL.crush.md](INSTALL.crush.md)
- **OpenCode** — see [INSTALL.opencode.md](INSTALL.opencode.md)
- **Codex** — see [codex-skills/](codex-skills/) (already integrated)

## Quick reference

```bash
# Generate skills for any agent
science agents generate --agent crush
science agents generate --agent opencode
science agents generate --agent opencode --format command  # OpenCode commands only

# Install methodology skills via symlink
science agents install --agent crush
science agents install --agent opencode
```

## What's included

- **40+ command skills** — generated from `commands/*.md` as SKILL.md files
- **12 methodology skills** — symlinked from `skills/*` (statistics, epistemics, study-design, etc.)
- **40+ OpenCode commands** — generated as `.md` files with YAML frontmatter

See [INSTALL.crush.md](INSTALL.crush.md) and [INSTALL.opencode.md](INSTALL.opencode.md) for detailed setup instructions.
