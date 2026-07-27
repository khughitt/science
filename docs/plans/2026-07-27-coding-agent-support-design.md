# Coding-Agent Support — Design

**Status:** Approved

**Date:** 2026-07-27

**Goal:** Ship one committed Agent Skills distribution that works across
Codex, Crush, and OpenCode; ship thin, committed OpenCode command adapters; and
move installation guidance and generated artifacts out of the repository root.

## Context

Science currently has two distinct agent-facing source corpora:

- `commands/*.md` contains Claude command definitions.
- `skills/` contains the canonical methodology-skill corpus and its registry.

The existing Codex integration converts command definitions and selected
methodology skills into a committed `codex-skills/` mirror. Commit `811f7cfa`
extends that generator with Crush and OpenCode modes and adds a new
`science agents` CLI group.

The extension establishes the right broad direction—reuse the command corpus
and expose standard `SKILL.md` packages—but the implementation is not ready to
merge. Agent-specific branching was added around logic that still assumes the
Codex layout and vocabulary, and the installation path does not preserve the
generated skills' contracts.

The relevant host contracts are:

- [Agent Skills specification](https://agentskills.io/specification)
- [Crush Agent Skills](https://github.com/charmbracelet/crush#agent-skills)
- [OpenCode Agent Skills](https://opencode.ai/docs/skills/)
- [OpenCode commands](https://opencode.ai/docs/commands/)
- [Codex skills](https://learn.chatgpt.com/docs/build-skills)

## Review Findings

The current branch has the following blocking problems.

### OpenCode command generation corrupts command semantics

`_build_command_text` applies the Codex-oriented rewrite that replaces
`$ARGUMENTS` with prose, despite OpenCode commands using `$ARGUMENTS` natively.
The generated command then says to follow a "Science Codex Command Preamble"
without embedding that preamble. The generated file is neither a faithful
OpenCode command template nor a self-contained Science workflow.

### Agent labels are presentation-only

The new `agent` argument changes the preamble heading, but the generated body
and index still contain Codex-specific wording. Crush and OpenCode outputs
therefore tell the host to load Codex skills and their indexes identify every
entry as a Codex skill.

### Crush palette support is documented but not generated

Crush requires `user-invocable: true` for a skill to appear in its command
palette. The generator's docstring and installation guide promise that
behavior, but generated command skills omit the field.

### Methodology installation violates the skill identity contract

The install command links `skills/statistics/` as a directory named
`science-statistics`, while its frontmatter still declares
`name: statistics`. It also links `skills/meta/` as `science-meta`, although
that router declares `name: skill-development`. Agent Skills and OpenCode
require the frontmatter name to match the parent directory.

### Installation and documentation disagree

The implementation installs Crush and OpenCode skills into `.agents/skills/`.
The agent-specific guides say that the command creates `.crush/skills/` or
`.opencode/skills/`. The shared `.agents/skills/` destination is supported by
both hosts, but the observable behavior and documentation must agree.

### Output-location overrides break toolkit references

Generated skills contain relative links back to canonical toolkit files.
Generating directly into `~/.config/crush/skills/` or
`~/.config/opencode/skills/`, as the new guides recommend, changes the
generated files' depth and makes those links point outside the toolkit.

### Root discovery and installation fail open

If repository discovery fails, `_resolve_repo_root` returns the current
directory. Generation then fails at an incidental file read, while
installation can report a successful zero-skill install. A relative
`--repo-root` also produces relative symlink targets that become broken when
created in another project.

### Installation deletes conflicting user content

Before creating a link, the current installer unconditionally unlinks a
destination symlink or recursively deletes a destination directory. A
pre-existing user-authored skill with the same name can therefore be destroyed
without confirmation. Collision refusal and preservation are blocking safety
requirements, not merely installation ergonomics.

### New behavior has no tests

The existing 62 Codex generator tests pass, but the branch adds no tests for
the new CLI, Crush frontmatter, OpenCode commands, installation, agent-specific
rewrites, or the new default directories.

## Decisions

| Fork | Decision |
|---|---|
| Generated artifacts | Commit them and verify exact fresh-generation equality. |
| Compatibility | Deliberate breaking path change; remove `codex-skills/` without a compatibility wrapper or symlink. |
| Skill variants | One shared generated Agent Skills tree for Codex, Crush, and OpenCode. |
| Methodology skills | Generate every canonical top-level router, with its resource subtree, plus a standalone scientific-writing skill. |
| Command support resources | Keep the command preamble prose inline; put its shared role prompts, aspects, and generated router index in one non-invocable `science-command-preamble` support skill. |
| OpenCode commands | Thin adapters that invoke the corresponding shared skill. |
| Canonical skill layout | Keep the existing authored corpus directly under `skills/`; it is already the base corpus. |
| Generated skill layout | `skills/generated/`. |
| Generated OpenCode command layout | `commands/opencode/`. |
| Installation | Symlink committed artifacts from a persistent toolkit checkout. |
| Collision policy | Idempotent for the same target; fail on every other collision. |
| Documentation | Canonical instructions in `docs/user-guide/`, with a compact README entry point. |
| Provenance notes | Remove conversion/adaptation notes from generated bodies. Source paths remain visible in the generated index. |

## Target Layout

```text
skills/
  INDEX.md                         # canonical authored-skill registry
  bio/
  data-management/
  ...
  generated/                       # committed, generated Agent Skills distribution
    INDEX.md
    science-add-hypothesis/
      SKILL.md
    science-command-preamble/       # non-invocable shared support resources
      SKILL.md
      references/
        role-prompts/
        aspects/
        methodology-index.md
    science-status/
      SKILL.md
    science-scientific-writing/
      SKILL.md
      references/
        ...
    science-skill-development/
      SKILL.md
      references/
        ...
    science-statistics/
      SKILL.md
      references/
        ...

commands/
  add-hypothesis.md                # canonical command source
  status.md
  ...
  opencode/                        # committed, generated thin adapters
    science-add-hypothesis.md
    science-status.md
    ...

docs/user-guide/
  coding-agents.md
  codex.md
  crush.md
  opencode.md
```

`skills/generated/` is a distribution mirror, not part of the canonical
methodology corpus. Canonical inventory and lint discovery must exclude that
subtree explicitly. Its own generated `INDEX.md` records source-to-output
mappings without adding registry rows to `skills/INDEX.md`.

Moving the canonical corpus to `skills/base/` was rejected. It would not
improve generation or installation, and it would force a broad rewrite of the
skill registry, companion links, doctrine, command instructions, inventories,
tests, and historical implementation assumptions.

## Generation

### Public generation surface

Replace the Codex-specific generator module/API and script with agent-neutral
names. The developer-facing command is:

```bash
cd science
uv run --frozen science agents generate
```

It regenerates both committed output roots. It does not accept `--agent`,
`--format`, or `--output-dir`; those options describe the superseded model in
which each host receives a separate tree. Python generator functions accept
explicit output roots so tests can generate into temporary directories.

The old `generate_codex_skills` wrapper and
`scripts/generate_codex_skills.py` are removed. No compatibility wrapper is
retained.

### Shared skill rendering

Every `commands/*.md` source produces:

```text
skills/generated/science-<command>/SKILL.md
```

Generated command skills:

- declare a `name` identical to the parent directory;
- preserve the canonical command description;
- include `user-invocable: true` for Crush's command palette;
- use the neutral heading `## Science Command Preamble`;
- embed the command preamble before the command body;
- include a numbered setup step that loads `science-command-preamble` for the
  role prompt and aspect definitions;
- name the generation-time-resolved role directly in that step, such as
  `research-assistant` or `discussant`;
- rewrite Claude-only invocation syntax to agent-neutral user-input language;
- refer to `science-*` companion skills without a Codex label;
- bundle every command-specific toolkit resource beneath the skill's own
  `references/` directory;
- rewrite every remaining path-based toolkit reference to that in-package
  resource;
- contain no relative path that escapes the generated skill package;
- omit "Converted from Claude command ..." and equivalent conversion notes.

Canonical command and skill frontmatter is parsed as YAML, must be a mapping,
and is validated before any generated-output mutation. Every command requires
a nonempty string `description`; every skill requires its validated Agent
Skills `name` plus a nonempty string `description`. Descriptions are limited to
1024 characters. Generated descriptions use deterministic JSON-compatible YAML
scalar serialization rather than manual quote escaping.

The shared `user-invocable` field is the one host extension in the common
tree. OpenCode documents that unknown skill-frontmatter fields are ignored;
Codex requires `name` and `description` and consumes Agent Skills packages.
Compatibility with all three current hosts is verified by the automated
format/link gates and the recorded host smoke checklist defined below.

Every canonical top-level router at `skills/*/SKILL.md` produces one generated
package named from the router's declared identity, not its source-directory
basename. For example, `skills/meta/SKILL.md` declares `skill-development` and
therefore produces `science-skill-development`, never `science-meta`. Each
package includes its local resource subtree recursively and preserves that
subtree's relative structure beneath `references/`. This includes nested
routers and resources such as `bio/{genomics,transcriptomics,proteomics}/`,
`literature/sources/`, and `meta/templates/`. Link rewriting handles
multi-segment relative paths; a flat `glob("*.md")` is insufficient. The one
reserved-filename exception is a nested canonical `SKILL.md`: it is emitted as
`router.md`, and every link or backticked path to it is rewritten accordingly.
Hosts may scan skill roots recursively, so each generated package must contain
exactly one discoverable `SKILL.md`, at the package root. Nested routers remain
resources of their owning top-level package and never create extra emitted
skill identities.

References that leave a methodology router's source subtree are rewritten to
load the corresponding generated `science-*` router instead of becoming
escape-links. The generated `science-writing` router is the deliberate
exception to ordinary local-subtree copying: it does not bundle
`writing/scientific-writing.md`. It delegates to the standalone
`science-scientific-writing` package, which is the sole emitted copy and the
target for every "load the scientific-writing skill" rewrite.

Cross-package rewriting is context-aware. The generator processes a whole
Markdown link before considering bare backticked paths, and substitutes a noun
phrase such as “the `science-study-design` skill” when the reference occurs in
running prose. It preserves or introduces imperative “Load ...” wording only
when rendering a complete load instruction. Replacements do not carry their
own duplicated article or `skill` suffix into the surrounding sentence.
Inline-code slash invocations are parsed through their closing backtick, so
arguments are retained as an explicit generated-skill input rather than left
outside an unmatched delimiter. Bare slash tokens are rewritten separately and
do not consume surrounding punctuation.

Generated methodology bodies omit "Adapted from canonical Science skill ..."
notes. The generated index remains the provenance map. Generation fails if two
sources resolve to the same generated identity, one canonical `skills/` source
is assigned two emitted owners, or a bundled resource link cannot be resolved.
The single-owner rule is deliberately scoped to canonical `skills/` sources.
Non-skill resources, such as documentation and templates, may be bundled by
multiple command packages when each command needs a self-contained copy.

### Command preamble support skill

The preamble prose remains embedded in every command-derived skill. This keeps
profile resolution, role selection, aspect selection, and the remaining
mandatory setup instructions directly in front of the model rather than making
them contingent on a second skill load.

The resources dereferenced by that prose have one emitted owner:
`science-command-preamble`. The support package contains both canonical role
prompt files, the aspect definitions, and a generated methodology-router
index. Its `SKILL.md` description states that Science command skills load it
for support resources and that it is not invoked directly. It omits
`user-invocable`.

Agent Skills packages have no parameter-passing contract. The generator
resolves each command's required role while rendering the command skill and
bakes that role name into the inline preamble. The support package supplies
the named file; the command does not pass a role value to another skill.

The support package's methodology index is generated from the canonical
top-level routers, but names their emitted `science-*` skill identities rather
than canonical repository paths. The inline preamble tells the model to load
the relevant generated router from this index. It never directs an installed
host toward `skills/INDEX.md` or an authored `skills/<path>` that is absent from
the installed distribution.

Command-body references that land under canonical `skills/` are likewise
rewritten as generated-skill loads instead of being copied. For example, the
commands that refer to `skills/study-design/estimator-certification.md` load
the owning `science-study-design` router. Literal template, documentation, and
other non-`skills/` fallbacks are bundled with each command that uses them,
preserving repository-relative structure under `references/`.

Every generated command skill therefore remains self-contained except for its
explicit sibling-skill dependencies: `science-command-preamble` and any
generated methodology router named by a rewritten canonical-skill reference.
No generated package depends on resolving `../../../` through a symlink into
the toolkit checkout. Generation fails if any command skill names a
sibling-skill dependency that is absent from the complete emitted package set.

Generation prunes stale generated skill directories and stale OpenCode command
files, while leaving only explicitly declared static files untouched. The
generated roots contain no hand-maintained installation documents.

### OpenCode command rendering

Every `commands/*.md` source also produces a namespaced adapter:

```text
commands/opencode/science-<command>.md
```

The adapter does not duplicate the source command body or preamble. It has the
source description and directs OpenCode to load and execute the corresponding
shared `science-*` skill with the native `$ARGUMENTS` value:

```markdown
---
description: Develop and refine a research hypothesis interactively.
---

Load and execute the `science-add-hypothesis` skill using this input:

$ARGUMENTS
```

The `science-` command namespace avoids collisions with OpenCode built-ins and
user-defined commands. A generated command without a corresponding generated
skill is an error.

## Installation

### Source and lifetime

Installation operates on the committed output trees in a persistent Science
toolkit checkout. It does not regenerate content in a consumer project and
does not pretend that a wheel-installed CLI contains the repository-level
command, skill, template, aspect, and documentation corpus.

Each generated package contains its path-based resources and has no escaping
relative references. Explicit sibling-skill dependencies are installed as one
complete set. The checkout must remain available after installation only
because it is the symlink target, not because skill instructions escape a
package to read unrelated checkout paths.

Repository discovery walks upward from the current directory for validated
toolkit sentinels. An explicit `--repo-root` is resolved to an absolute path
and validated by the same function. Failure raises a concise Click error before
creating any destination directory.

### CLI

```bash
science agents install --agent codex --scope project
science agents install --agent crush --scope user
science agents install --agent opencode --scope project
```

`--scope` accepts `project` or `user` and defaults to `project`.
`--project-dir` selects the project root for project scope and defaults to the
current directory.

All three hosts receive per-skill links from `skills/generated/science-*`,
including the required `science-command-preamble` support skill:

| Scope | Skill destination |
|---|---|
| project | `<project>/.agents/skills/science-*` |
| user | `~/.agents/skills/science-*` |

The shared user destination is intentional and is supported by each current
host:

| Host | Documented user discovery roots | Selected root |
|---|---|---|
| Codex | [`$HOME/.agents/skills`](https://learn.chatgpt.com/docs/build-skills) | `~/.agents/skills` |
| Crush | [`~/.agents/skills`, `~/.config/agents/skills`, and `~/.config/crush/skills`](https://github.com/charmbracelet/crush#agent-skills) | `~/.agents/skills` |
| OpenCode | [`~/.agents/skills`, `~/.config/opencode/skills`, and `~/.claude/skills`](https://opencode.ai/docs/skills/) | `~/.agents/skills` |

The existing `docs/user-guide/codex.md` instruction using
`${CODEX_HOME:-$HOME/.codex}/skills/` predates the current shared Agent Skills
discovery contract and is replaced as part of this change. Agent-specific user
roots remain valid alternatives, but the installer selects the one root shared
by all three hosts.

OpenCode additionally receives per-command links:

| Scope | Command destination |
|---|---|
| project | `<project>/.opencode/commands/science-*.md` |
| user | `~/.config/opencode/commands/science-*.md` |

The implementation resolves every source to an absolute path before creating
links. Correct existing links are left unchanged. A conflicting file,
directory, or link fails the install without deleting or overwriting user
content. The command reports installed, already-current, and failed items
explicitly. Installation preflight verifies that
`science-command-preamble` is in the complete link set for every host and
fails before creating destinations if it is missing.

Installation is symlink-only. The `--copy` mode is removed because copied
artifacts introduce a second update lifecycle and can remain stale after the
committed distribution changes. Windows guidance uses directory junctions or
equivalent supported links and keeps the same identity and collision rules.

Automatic uninstall and installed-link pruning are out of scope. The installer
never removes a destination, including a dangling or stale link. The user guide
documents how to remove Science-owned links manually; a future uninstall
command must establish ownership before deleting anything.

## Documentation

Delete the root and generated-tree installation documents:

```text
INSTALL.crush.md
INSTALL.opencode.md
MULTI_AGENT.md
codex-skills/INSTALL.codex.md
```

The user guide becomes the sole detailed installation source:

- `coding-agents.md` explains the common distribution, checkout lifetime,
  shared discovery path, generation, and update model.
- `codex.md` covers Codex invocation and project/user installation.
- `crush.md` covers the command palette and `user-invocable` behavior.
- `opencode.md` covers skill loading, namespaced slash commands, and
  permissions.

`docs/user-guide/index.md` and the documentation navigation register all four
pages. The root README gets a compact comparison/quick-install table for
Claude, Codex, Crush, and OpenCode and links to the detailed pages.

Active code, tests, and user documentation are updated from `codex-skills/` to
the new paths. Historical design and implementation plans remain historical
records and are not mass-rewritten.

Deleting `codex-skills/INSTALL.codex.md` intentionally breaks the published
`raw.githubusercontent.com/.../codex-skills/INSTALL.codex.md` bootstrap URL in
the current Codex guide. The README and user guide move to the new installation
commands in the same change; no redirect or compatibility file is retained.

## Error Handling

The generator and installer fail early for:

- an invalid or undiscoverable toolkit root;
- an unsupported agent or scope;
- malformed command or skill frontmatter;
- a generated skill name that does not match its directory;
- a missing command/skill one-to-one mapping;
- a command skill whose explicit sibling-skill dependency is absent;
- a generated install set without `science-command-preamble`;
- a destination collision;
- an output root inside the canonical source set when not equal to the declared
  committed output root.

There are no warning-and-fallback branches that silently change formats,
targets, or source roots.

## Verification

### Generator tests

- Every canonical command produces exactly one shared generated skill.
- Every canonical command produces exactly one OpenCode adapter.
- Every canonical top-level methodology router produces exactly one generated
  package named from its frontmatter identity.
- Methodology resource subtrees and their internal links are complete.
- The scientific-writing leaf is available as its own generated skill.
- The `science-command-preamble` support skill contains both role prompts, all
  aspect definitions, and the generated methodology-router index.
- The support skill omits `user-invocable`, and its description says it is
  loaded by Science command skills rather than invoked directly.
- Every command skill embeds the preamble prose and contains an explicit load
  of `science-command-preamble` naming its generation-time-resolved role.
- Every command skill's sibling-skill delegation targets exist.
- The support skill's router index maps every canonical top-level router to
  its generated `science-*` identity and contains no canonical repository path.
- Command packages do not copy canonical `skills/` resources; such references
  are rewritten to their owning generated methodology router.
- Every OpenCode adapter maps to an existing generated skill.
- Generated skill names match their parent directories.
- Generated command skills contain `user-invocable: true`.
- Generated methodology/router skills omit `user-invocable`.
- OpenCode adapters preserve `$ARGUMENTS`.
- Shared skill bodies and indexes contain no host-specific labels.
- Generated bodies contain no conversion or adaptation notes.
- Every path-based toolkit resource reference stays within its generated skill
  package; sibling-skill dependencies are explicit and resolve to generated
  packages.
- Every relative resource link resolves both from the committed generated path
  and through a per-skill installation symlink.
- Stale skill directories and stale OpenCode adapters are pruned.
- Committed output bytes equal fresh temporary generation.
- `science_tool.graph.skill_inventory.real_skill_paths` excludes the
  `skills/generated/` prefix before enforcing `skills/INDEX.md` coverage.
- `science_tool.skills_lint.discovery.iter_skill_files` excludes the
  `generated/` prefix centrally; this exclusion consequently governs both
  `check_skills`/`check_index_coverage` and the `sources.yaml` dependency views
  built by `skills_lint.cli.build_dependency_views`.
- The exclusions are prefix-based, so the nested
  `skills/generated/INDEX.md` and every generated resource are excluded.
- Canonical command discovery is explicitly non-recursive, excludes
  `commands/opencode/`, and has a guard test preventing generated adapters from
  entering command counts or command-documentation checks.

### Installer tests

- Project and user scopes select the documented destinations.
- Codex, Crush, and OpenCode all link the same shared generated skills.
- The complete installed skill set for every host contains
  `science-command-preamble`; preflight refuses an incomplete generated set
  before creating destinations.
- OpenCode additionally links its command adapters.
- Source links are absolute.
- Reinstalling correct links is idempotent.
- Conflicting files, directories, and unrelated symlinks are refused and
  preserved.
- A real destination directory and its contents survive a refused install
  byte-for-byte.
- Invalid toolkit roots fail before destination creation.
- Relative explicit toolkit roots are resolved before link creation.

### Host compatibility smoke checklist

Before completion, record the installed Codex, Crush, and OpenCode versions and
the result of this project-scoped fixture check:

1. Install the generated skills into a temporary Git project's
   `.agents/skills/`.
2. Confirm each host discovers `science-status`.
3. Confirm Codex can explicitly select the skill.
4. Confirm Crush exposes the command-derived skill in its palette and does not
   expose either `science-statistics` or `science-command-preamble` there.
5. Confirm OpenCode can load `science-status` through its skill tool and invoke
   `/science-status` through the installed thin adapter.
6. Ask each host to read at least one bundled reference through the loaded
   skill, confirming that no logical-versus-physical symlink behavior is
   required.

The user-scope destination is covered by official discovery contracts plus CLI
path-selection tests using an injected temporary user directory; the smoke
check does not mutate the real user skill directories.

### Gates

Run affected generator, inventory, command-documentation, and CLI tests first.
Then run:

```bash
cd science
uv run --frozen ruff check
uv run --frozen pyright
uv run --frozen pytest
```

Only the top-level implementation run executes the full suite; no concurrent
test suites run in the same worktree.

The generator implementation is renamed to
`science/src/science_tool/agent_assets.py`, its script to
`scripts/generate_agent_assets.py`, and its test module to
`science/tests/test_agent_assets.py`. The existing Codex test module is
rewritten for the new paths and neutral contracts rather than carried forward
under its old assertions.

## Alternatives Considered

### Three generated skill trees under `skills/`

`skills/generated/{codex,crush,opencode}/` makes host differences explicit,
but duplicates almost every generated byte and preserves the drift that caused
the current implementation's Codex labels and inconsistent rewrites. Rejected
because the three hosts share the Agent Skills format.

### Native hidden output directories

Committing `.agents/skills/` and `.opencode/commands/` would match discovery
paths directly. It would also make every generated Science command skill
automatically visible while working on this toolkit and would mix distributable
assets with local host configuration. Rejected in favor of explicit
distribution roots.

### Generate only during installation

Transient generation would keep mirrors out of Git but remove byte-for-byte
review of shipped artifacts, require repository-level assets to be available
inside installed wheels, and make updates depend on mutable local generation.
Rejected; the owner chose committed artifacts.

## Consequences

- One generated skill corpus is reviewed, tested, and installed across all
  three coding agents.
- Command preamble prose is intentionally duplicated in every command skill so
  its mandatory setup remains visible. The larger role-prompt, aspect, and
  router-index resource closure is emitted once in
  `science-command-preamble`, so changes to those resources do not rewrite
  every command package.
- OpenCode commands stay small and cannot drift from command-skill behavior.
- The repository root loses three installation documents and the
  `codex-skills/` directory, without gaining `crush-skills/` or
  `opencode-skills/`.
- Canonical methodology skills keep their current paths and inventory
  semantics.
- Existing Codex installation paths break intentionally and must be recreated
  from the new instructions.
- The old raw `INSTALL.codex.md` bootstrap URL stops working intentionally.
- Installed links depend on the toolkit checkout remaining at its installed
  path.
- Install does not prune or uninstall old links; removal remains an explicit
  manual operation.
- Host-format changes are centralized in one generator and its compatibility
  tests rather than spread across per-agent branches.
