# Installing Science Skills in OpenCode

Science ships methodology skills and slash-commands that can be exposed to
[OpenCode](https://opencode.ai) as native skills and commands.

## Discovery paths

OpenCode discovers skills and commands from these locations:

**Skills:**
1. `~/.config/opencode/skills/` (global)
2. `~/.agents/skills/` (global, shared with Crush)
3. `~/.claude/skills/` (global, shared with Claude Code)
4. `.opencode/skills/` (project-local)
5. `.agents/skills/` (project-local, shared with Crush)
6. `.claude/skills/` (project-local, shared with Claude Code)

**Commands:**
1. `~/.config/opencode/commands/` (global)
2. `.opencode/commands/` (project-local)

Each skill is a directory containing a `SKILL.md` file. Commands are `.md`
files with YAML frontmatter.

## Quick start (global)

Generate and install globally:

```bash
# From the science toolkit repo root
cd science

# Generate skills
uv run science agents generate --agent opencode --output-dir ~/.config/opencode/skills

# Generate commands
uv run science agents generate --agent opencode --format command --output-dir ~/.config/opencode/commands
```

Or use the install command for methodology skills:

```bash
uv run science agents install --agent opencode --project-dir ~
```

## Quick start (project-local)

Generate for a specific project:

```bash
# From your Science-managed project
science agents generate --agent opencode --output-dir .opencode/skills
science agents generate --agent opencode --format command --output-dir .opencode/commands
```

Or symlink methodology skills:

```bash
science agents install --agent opencode
```

This creates `.opencode/skills/science-*/` symlinks pointing to the toolkit's
`skills/` directory.

## Invocation

### Skills

Skills are loaded on-demand via the `skill` tool. The agent sees available
skills listed in the tool description:

```xml
<available_skills>
  <skill>
    <name>science-status</name>
    <description>Show a curated project orientation...</description>
  </skill>
</available_skills>
```

The agent loads a skill by calling:

```
skill({ name: "science-status" })
```

### Commands

Commands are invoked directly with `/`:

```
/status
/health
/tasks
/add-hypothesis
```

OpenCode substitutes `$ARGUMENTS` in the command template with user input.

## What gets installed

### Skills

**Command skills** (generated from `commands/*.md`):
- `science-status` — project orientation
- `science-health` — health triage
- `science-tasks` — task management
- `science-add-hypothesis` — hypothesis authoring
- ... (39 commands total)

**Methodology skills** (symlinked from `skills/*`):
- `science-statistics` — statistical modeling
- `science-epistemics` — proposition/evidence schema
- `science-study-design` — rigor and pre-registration
- ... (12 methodology routers)

### Commands

Generated as `.md` files with YAML frontmatter:

- `status.md` — `/status` command
- `health.md` — `/health` command
- `tasks.md` — `/tasks` command
- ... (39 commands total)

Each command file contains the full prompt template with `$ARGUMENTS`
substitution support.

## Permissions

Configure skill access in `opencode.json`:

```json
{
  "permission": {
    "skill": {
      "*": "allow",
      "science-*": "allow",
      "science-experimental-*": "ask"
    }
  }
}
```

- `allow` — skill loads immediately
- `deny` — skill hidden from agent
- `ask` — user prompted for approval

## Updating

Regenerate when the Science toolkit updates:

```bash
# Re-generate skills
uv run science agents generate --agent opencode

# Re-generate commands
uv run science agents generate --agent opencode --format command

# Or re-symlink methodology skills
uv run science agents install --agent opencode
```

## Troubleshooting

**Skills don't appear:**
- Check the skill directory contains `SKILL.md` (all caps)
- Verify frontmatter has `name:` and `description:` fields
- The `name` field must match the directory name
- Restart OpenCode to reload skill discovery

**Commands don't work:**
- Verify the `.md` file has YAML frontmatter with `description:`
- Check for syntax errors in `$ARGUMENTS` substitution
- Commands override built-ins with the same name

**Symlinks broken:**
- Ensure the Science toolkit repo path hasn't moved
- Re-run `science agents install --agent opencode` to refresh links
