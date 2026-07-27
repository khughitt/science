# Coding Agents

Science supports Codex, Crush, and OpenCode with one generated Agent Skills
distribution. This page covers installation shared by all three hosts; use the
host pages for [Codex](codex.md), [Crush](crush.md), and [OpenCode](opencode.md)
behavior.

## Distribution

The authored sources are the top-level `skills/` tree and `commands/` files.
They are not installed directly. Science commits a generated distribution at
`skills/generated/`, where every `science-*` directory is a complete skill
package with a `SKILL.md`. The same tree is installed for Codex, Crush, and
OpenCode. OpenCode additionally receives its committed, generated command
adapters from `commands/opencode/`.

The shared user root is deliberate. Current host discovery documentation lists
`~/.agents/skills` for [Codex](https://learn.chatgpt.com/docs/build-skills),
[Crush](https://github.com/charmbracelet/crush#agent-skills), and
[OpenCode](https://opencode.ai/docs/skills/). Project installs use the
corresponding `.agents/skills` root.

## Install

Run the installer from a persistent Science checkout. It creates absolute
symlinks to each generated package, so deleting or moving that checkout breaks
the installation. A durable checkout such as `~/d/science` is suitable.

For a project installation, select the host and point `--project-dir` at the
project when it is not the current directory:

```bash
cd ~/d/science/science
uv run --frozen science agents install --agent codex --scope project --project-dir ~/d/my-research
uv run --frozen science agents install --agent crush --scope project --project-dir ~/d/my-research
uv run --frozen science agents install --agent opencode --scope project --project-dir ~/d/my-research
```

All three commands link skills into `<project>/.agents/skills/`. The OpenCode
command also links its adapters into `<project>/.opencode/commands/`.

For a user installation, use the same persistent checkout:

```bash
cd ~/d/science/science
uv run --frozen science agents install --agent codex --scope user
uv run --frozen science agents install --agent crush --scope user
uv run --frozen science agents install --agent opencode --scope user
```

All three user installs link skills into `~/.agents/skills/`. The OpenCode
user install also links its adapters into `~/.config/opencode/commands/`.

## Reinstall, update, and regenerate

Running the same install command again is idempotent: links that already have
the expected absolute target remain unchanged. Pulling a newer Science checkout
updates what those links point at. Regenerate committed artifacts after editing
their authored sources:

```bash
cd ~/d/science
cd science && uv run --frozen science agents generate
```

Then rerun the applicable install command. Generation updates the committed
`skills/generated/` distribution and `commands/opencode/` adapters together.

## Collisions, removal, and Windows

Installation never overwrites a file, directory, unrelated link, dangling
link, or stale link at a destination. It fails before changing destinations
and preserves the collision for you to inspect. There is no pruning or
uninstall command.

To remove an installation manually, remove only the known Science-owned
`science-*` symlinks in the selected skill directory and, for OpenCode, the
known Science-owned `science-*.md` symlinks in its selected command directory.
Do not remove an entry unless you have confirmed it is a Science link pointing
at the persistent checkout.

On Windows, use directory junctions or another supported symlink mechanism in
place of the Unix links. Keep the same package identity (`science-*`), target
the persistent checkout with absolute paths, and apply the same rule: inspect
and preserve every collision rather than overwriting it.

The former raw Codex bootstrap URL and old Codex-only skill path have been
intentionally removed. Use these installer commands instead.
