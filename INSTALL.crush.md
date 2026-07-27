# Installing Science Skills in Crush

Science ships methodology skills and slash-commands that can be exposed to
[Crush](https://github.com/charmbracelet/crush) as native skills.

## Discovery paths

Crush discovers skills from these locations (in priority order):

1. `$CRUSH_SKILLS_DIR` (environment variable)
2. `~/.config/crush/skills/` (global)
3. `~/.agents/skills/` (global, shared with OpenCode)
4. `.crush/skills/` (project-local)
5. `.agents/skills/` (project-local, shared with OpenCode)

Each skill is a directory containing a `SKILL.md` file with YAML frontmatter.

## Quick start (global)

Generate and install skills globally:

```bash
# From the science toolkit repo root
cd science
uv run science agents generate --agent crush --output-dir ~/.config/crush/skills
```

Or use the install command to symlink methodology skills:

```bash
uv run science agents install --agent crush --project-dir ~
```

## Quick start (project-local)

Generate skills for a specific project:

```bash
# From your Science-managed project
science agents generate --agent crush --output-dir .crush/skills
```

Or symlink methodology skills:

```bash
science agents install --agent crush
```

This creates `.crush/skills/science-*/` symlinks pointing to the toolkit's
`skills/` directory.

## Invocation

Once installed, skills appear in Crush's command palette (Ctrl+P):

- `user:science-status` — global skills
- `project:science-status` — project-local skills

You can also invoke them by name in conversation:

```
Use the science-status skill to show me where we are.
```

## What gets installed

### Command skills

Generated from `commands/*.md` in the Science toolkit:

- `science-status` — project orientation
- `science-health` — health triage
- `science-tasks` — task management
- `science-add-hypothesis` — hypothesis authoring
- ... (39 commands total)

### Methodology skills

Symlinked from `skills/*` in the Science toolkit:

- `science-statistics` — statistical modeling
- `science-epistemics` — proposition/evidence schema
- `science-study-design` — rigor and pre-registration
- ... (12 methodology routers)

## Updating

Regenerate when the Science toolkit updates:

```bash
# Re-generate (overwrites existing)
uv run science agents generate --agent crush

# Or re-symlink (updates links)
uv run science agents install --agent crush
```

## Troubleshooting

**Skills don't appear in palette:**
- Check the skill directory contains `SKILL.md` (not `skill.md`)
- Verify frontmatter has `name:` and `description:` fields
- Restart Crush to reload skill discovery

**Symlinks broken:**
- Ensure the Science toolkit repo path hasn't moved
- Re-run `science agents install --agent crush` to refresh links
