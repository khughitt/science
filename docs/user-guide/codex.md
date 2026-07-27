# Science for Codex

Use the common [coding-agent setup](coding-agents.md) to install Science's
shared generated skills. Codex discovers project skills from `.agents/skills`
and user skills from `~/.agents/skills`; Science uses those shared Agent Skills
roots rather than a Codex-specific skills directory. See the current
[Codex skill discovery documentation](https://learn.chatgpt.com/docs/build-skills).

## Use skills explicitly

Codex can select a Science skill by name when the task calls for it. For
example, ask it to load and follow `science-status` to orient on the current
research project, or `science-search-literature` for a literature search.
The installed packages use the `science-*` namespace.

Install or regenerate the distribution through the commands in
[Coding agents](coding-agents.md); that page also describes project versus user
scope, updates, collisions, and Windows links.
