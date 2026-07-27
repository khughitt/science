# Science for OpenCode

Use the common [coding-agent setup](coding-agents.md) to install Science's
generated skills. OpenCode discovers project skills from `.agents/skills` and
user skills from `~/.agents/skills`; see the [OpenCode skills documentation](https://opencode.ai/docs/skills/)
for its complete discovery order.

## Skills and commands

OpenCode loads the installed `science-*` skills as needed. Its Science command
adapters are installed separately alongside the shared skills:

| Scope | Command directory |
|---|---|
| Project | `.opencode/commands/` |
| User | `~/.config/opencode/commands/` |

The adapters provide namespaced slash commands such as `/science-status` and
`/science-search-literature`. They pass the command's `$ARGUMENTS` through to
the corresponding skill, so use normal command arguments after the slash
command.

## Permissions

OpenCode's permission policy controls whether the agent may load a skill. For
example, a project can allow Science skills in `opencode.json`:

```json
{
  "permission": {
    "skill": {
      "science-*": "allow"
    }
  }
}
```

Use `ask` instead of `allow` when each skill load should require approval. See
the [OpenCode commands documentation](https://opencode.ai/docs/commands/) for
command behavior and the [OpenCode permissions documentation](https://opencode.ai/docs/permissions/)
for policy details.

Install or regenerate the distribution through [Coding agents](coding-agents.md),
which covers scope, updates, collisions, and Windows links.
