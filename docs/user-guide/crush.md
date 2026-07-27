# Science for Crush

Use the common [coding-agent setup](coding-agents.md) to install Science's
generated skills. Crush discovers the shared project root `.agents/skills` and
the user root `~/.agents/skills`; see [Crush Agent Skills](https://github.com/charmbracelet/crush#agent-skills)
for its complete discovery order.

## Command palette

Science command-derived skills declare `user-invocable: true`, so Crush exposes
them in its command palette. Look for names such as `science-status` and
`science-search-literature` there, or ask Crush to use the named skill in a
conversation.

Methodology and support skills remain available for the command skills to
load, but do not appear in the palette. In particular, `science-statistics`
and `science-command-preamble` are not palette commands.

Install or regenerate the distribution through [Coding agents](coding-agents.md),
which covers scope, updates, collisions, and Windows links.
