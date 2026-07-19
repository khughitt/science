---
title: Specs and plans as first-class entities (S3a)
status: design
created: '2026-07-18'
---

# Specs and Plans as First-Class Entities (S3a)

**Program:** curation S1–S5. This is **S3**, narrowed to **S3a** (see Scope).
S1 (scope certification), S4 (correspondence-drift screen), and S2 (adaptive
rotation) are shipped and merged to local main.

**Goal.** New design docs and implementation plans become first-class Science
entities from creation — carrying a canonical id, frontmatter, and an
`entities/` home — via the already-shipped `science entities import` engine.
`spec` graduates from an annotation-only stub into a creatable, importable,
curation-visible correspondence kind.

## Context — most of S3 already ships

The decomposition framed S3 as three parts: (1) flesh out `spec`, (2) intercept
the superpowers `brainstorming`/`writing-plans` skills via the AGENTS.md
template, (3) `science entity import`. Grounding the work found that **part 3 is
already built, merged, and tested**:

- `science/src/science_tool/entity_import.py` — `plan_import` (read-only
  preview: proposes an id via `propose_number`, stamps frontmatter, rebases the
  document's own outbound links, plans the inbound reference rewrite, and
  validates the final entity through the same `_validate_prospective_write`
  boundary `create_entity` uses) and `apply_import` (transactional move with a
  full-tree snapshot, source-hash verification, reference rewrite, and a
  post-move inbound/outbound audit that rolls back on any failure).
- CLI: `science entities import SRC --kind K --save-plan p.json` (preview) then
  `science entities import --apply-plan p.json` (apply), in
  `entities_inventory_cli.py:269`. Two test files: `test_entity_import.py`,
  `test_entity_import_cli.py`.

**What the importer does and does not repoint.** It rewrites *structured*
references — frontmatter reference fields and Markdown links — from the old
identity to the new canonical id, and rebases the moved document's own relative
links. It deliberately leaves **plain prose and code-fence path mentions as
`ManualHit`s**: surfaced in the report, not auto-rewritten. So "repoint
references" is not "repoint every textual mention." The interception workflow
(Component 4) must require inspecting the manual-hit list before applying.

**Source placement.** `plan_import` computes `source.relative_to(project_root)`,
so the source **must live inside the project root** — it is not an arbitrary
path. The staging file the skills author is therefore a project-local file (the
saved `p.json` plan may live outside the tree; see Component 4).

What blocks importing a design doc today: `spec` is a bare `EntityKind` stub (no
`home`/`strategy`/`default_status`/`statuses`), so `resolve_path_policy("spec")`
raises `Unsupported source-authored entity kind: spec` and both `science entity
create spec` and `science entities import … --kind spec` fail.

## Scope — S3a (narrow) vs deferred S3b

`spec:` is currently an **annotation-only metadata-reference prefix**:
`graph/sources.py:806` lists it in `_ANNOTATION_REF_PREFIXES = frozenset({"meta",
"spec"})`, and `is_metadata_reference` is consulted **only in `_add_relations`**
(the ordinary metadata-pointer materialization loop in
`graph/materialize.py`) to skip individual edges. It does **not** gate entity
**node** materialization, and it does **not** gate authored typed relations —
`_add_authored_relation` resolves and admits `relations:` through
`admit_authored_relation` without ever calling `is_metadata_reference`.

That distinction is load-bearing and corrects an earlier over-broad reading:

- In **S3a**, a spec **entity materializes as a graph node** (it is a
  first-class entity file with an id), and a wired **`spec → spec`
  `sci:supersedes` edge materializes** (authored typed relation, not gated by
  the metadata filter).
- What stays suppressed until **S3b** is **ordinary `spec:` metadata-reference
  fields** (the pointer fields in `_add_relations`): those edges are skipped
  while `spec` remains in `_ANNOTATION_REF_PREFIXES`.

### Inventory (reproducible)

Method: on each project's `main` at the recorded SHA, over **git-tracked** files
only (untracked `.claude/worktrees/` copies are excluded — they inflated an
earlier count). Occurrences (every token) and files-with-a-token are counted by
separate commands:

```
# occurrences (every spec: token)
git -C <repo> grep -hI -oE 'spec:[A-Za-z0-9][A-Za-z0-9._/-]*' -- '*.md' '*.yaml' '*.yml' | wc -l
# files with at least one spec: token
git -C <repo> grep -lI 'spec:' -- '*.md' '*.yaml' '*.yml' | wc -l
```

| Project | SHA | files with a `spec:` token | occurrences | notes |
|---|---|---|---|---|
| natural-systems | `ee709872a` | 89 | 151 | date-slug **and** non-date ids (`spec:research-question`, `spec:scope-boundaries`, `spec:catalog-canonical-core`, `spec:health-coverage-scope`); a `kind: spec` entity at `entities/research-question.md` |
| cbioportal (`~/d/cancer/data-sources/cbioportal`) | `7b3a4de` | 11 | 13 | all `spec:research-question`; a `kind: spec` entity at `entities/research-question.md`, id `spec:research-question`, status active |
| multiple-myeloma | `54078d0a` | 10 | 12 | mostly date-slug; plus frontmatter `spec:` keys |

So **"every existing reference is a date-slug" is false** — semantic non-date
ids exist across projects, and there are pre-existing `kind: spec` entities in
the wild. Both cbioportal and the non-date ids are in **S3b's** migration scope.

**Ecosystem check — `~/d/science-commons` (`fe7d531`):** clean. 0 tracked files
with a `spec:` token, 0 occurrences, and no `entities/specs/` directory. AGENTS.md
names commons as a compatibility surface that must be checked when entity/source
formats change; S3a touches neither any commons file nor any `spec:` reference
there, so there is nothing to migrate. This is recorded to close that surface.

### S3a is zero-breakage — why

Making `spec:*` metadata-references resolve is a **global code constant**, not a
per-project switch, and imported specs get **numeric** ids (`spec:0001-slug`)
that would not match the existing date-slug/semantic references — so turning
resolution on is deferred. S3a instead leaves `spec` in
`_ANNOTATION_REF_PREFIXES` and only makes `spec` creatable/importable. It adds no
new findings to the surveyed projects because:

- **No project has an `entities/specs/` directory.** `entity_conformance`'s
  checks iterate `_entity_dirs`, which scans only existing `entities/<kind>/`
  directories; with no `entities/specs/` there is nothing to flag, and there is
  no reverse "a `kind: spec` file living outside its home" check.
- The pre-existing `kind: spec` files sit at the **research-question singleton
  path** (`entities/research-question.md`), which `_entity_dirs` skips
  (`strategy == "singleton"`). Their `spec:` id prefix still conforms under
  `id-prefixes`.
- `spec:*` references remain annotation-only, so existing pointers are
  untouched.

**S3b (deferred, separate design + migration):** remove `spec` from
`_ANNOTATION_REF_PREFIXES` (turn on ordinary metadata-reference resolution +
edges) **and** ship the id-remap migration that repoints existing `spec:`
references — date-slug **and** semantic (`spec:research-question`, etc.) — to
numeric ids, across natural-systems, cbioportal, and multiple-myeloma, and
reconciles the legacy `kind: spec` research-question entities. mm's
`entities/design/*` → `spec` re-import is likewise a project migration. None of
this is in S3a.

## Components

### Component 1 — flesh out the `spec` kind

`science/model/src/science_model/profiles/core.py`, the single
`EntityKind(name="spec", …)` (currently core.py:504). `entity_class`,
`curation_scope=CurationScope.CORRESPONDENCE`, `category`, `layer`, and
`description` stay; add four fields:

```python
EntityKind(
    name="spec",
    canonical_prefix="spec",
    layer="layer/core",
    description="A design or implementation specification.",
    entity_class=EntityClass.OPERATIONAL,
    curation_scope=CurationScope.CORRESPONDENCE,
    category=KindCategory.AUTHORED_CORE,
    home="entities/specs",
    strategy="numeric",
    default_status="active",
    # Same lifecycle vocabulary as `plan`: a spec's status IS a document
    # lifecycle (drafted before active, superseded when replaced). NOT a
    # claim of kind-certification — only `hypothesis` is kind-certified, and
    # the S4 drift screen remains plan-only.
    statuses=["draft", "active", "complete", "superseded", "retired", "archived"],
),
```

`strategy="numeric"` is required: the importer mints ids through
`propose_number`, which only supports numeric kinds. `default_status="active"`
matches `plan`. This one change makes `spec` creatable and importable and —
because the curation scope is already correspondence — folds it into the S1
boundary and the S2 rotation corpus. `template_ready` is deliberately **not**
set (parity with `plan`; no `templates/spec.md`).

### Component 2 — wire `spec → spec` supersession

Same file, the `supersedes` `RelationKind` (core.py:720). Adding `superseded` to
spec's statuses places `spec` in the supersedable gate's `declares` set
(`model/tests/test_supersedable_gate.py:63`), which then requires spec to be an
admissible `sci:supersedes` endpoint. Per the owner ruling, do **not** grow the
`_KNOWN_HALF_WIRED` debt allowlist — wire the pair:

- add `"spec"` to `source_kinds` and `target_kinds`;
- add `RelationEndpointPair(source_kind="spec", target_kind="spec")` to
  `allowed_kind_pairs`;
- amend the relation **description** string to mention spec replacement (today
  it lists workflow-run / hypothesis / conclusion replacement); and update the
  debt comment to record `spec` as fully wired, not deferred debt.

Because `_add_authored_relation` does not consult `is_metadata_reference`, a
wired `spec → spec` supersedes edge **materializes in S3a** — this is real graph
participation, verified by test (below), not merely a model-level admission.

### Component 3 — id-prefix policy cleanup

`science/src/science_tool/validate/checks/id_prefixes.py:108`. The
`_EXTRA_PREFIX_KINDS = ("concept", "dataset", "spec")` fallback and its comment
are already stale: `concept` and `dataset` **do** carry policy homes/strategies
today and are already in `markdown_entity_kinds()` (verified at runtime — the
comment claiming they are "absent from `_BUILTIN_MARKDOWN_POLICIES`" is wrong).
Once `spec` gains `home`/`strategy` (Component 1), it too enters
`markdown_entity_kinds()`, and **every** member of `_EXTRA_PREFIX_KINDS` is
redundant. So remove the constant entirely rather than trimming it, and derive
`prefix_rules()` solely from the policy table:

```python
def prefix_rules() -> dict[str, str]:
    kinds = set(markdown_entity_kinds())
    kinds -= {"research-question", "claim-registry"}  # singletons
    return {kind: f"{kind}:" for kind in sorted(kinds)}
```

Coverage is unchanged: `concept`, `dataset`, and `spec` all stay in
`prefix_rules()` via the policy table. Delete
`test_prefix_rules_retain_nonpolicy_kinds`
(`science/tests/validate/test_checks_id_prefixes.py:154`) — with no
`_EXTRA_PREFIX_KINDS` there is no non-policy set left to retain, and its whole
premise (a kind covered *only* by the fallback) no longer exists.
`test_prefix_rules_cover_every_markdown_kind` (line 143) becomes the sole
authority guard: it already asserts every `markdown_entity_kinds()` member
(now including `spec`) has a prefix rule.

### Component 4 — AGENTS-template interception

`templates/agents-md.md` (shipped to adopters); explained in
`docs/user-guide/entities.md` under "Source Entity CLI." Add a section stating
the project preference the superpowers skills' documented "user-preferences
override the default save location" hook picks up. The `brainstorming` skill
mandates *writing and committing* the design doc; the interception must
**explicitly override that commit timing**:

1. Author the design doc / plan as a **project-local staging file** (no
   frontmatter). This staging file is **not committed**.
2. Preview: `science entities import <staging-file> --kind spec` (or `plan`),
   saving the plan to a path **outside the project tree** (a stale `p.json`
   holds paths and is itself a scannable ref artifact). **Inspect the manual-hit
   list** — plain prose/code mentions of the old path are not auto-repointed.
3. Apply: `science entities import --apply-plan <plan>`, then delete the plan
   file.
4. **Commit the canonical entity** (`entities/{specs,plans}/NNNN-slug.md`), not
   the staging file. The staging file is gone (moved) after apply.

State explicitly that this template change reaches only newly scaffolded/imported
projects — **existing adopters need a manual AGENTS.md update**. The toolkit repo
itself is untouched (no `entities/`; keeps loose `docs/plans/`).

## Data flow (write-then-import)

Unchanged from the shipped engine: skill authors a loose project-local staging
doc → `plan_import` previews read-only (proposes numeric id, renders + validates
the final entity, plans the structured-ref rewrite, lists manual hits) → operator
inspects manual hits → `apply_import` moves the file to
`entities/specs/NNNN-slug.md`, stamps frontmatter, repoints structured refs, runs
the post-move audit, and rolls back on any failure.

## Error handling

All existing. `plan_import` refuses a source that already has frontmatter, a
source outside the project root, an unknown or non-numeric kind, and a `--status`
outside the kind's vocabulary; `apply` verifies the source hash and rolls back on
any post-move audit failure. The only new surface is that `spec` is a valid
`--kind`.

## Testing

- **Model** (`science/model/tests/`): the `spec` `EntityKind` exposes the four
  new fields; `relation_allows_kinds(supersedes, "spec", "spec")` is True (new
  `test_spec_is_a_supersedes_ENDPOINT`); the supersedable gate shows no
  newly-half-wired kinds with spec present; the `supersedes` description mentions
  spec replacement.
- **Toolkit** (`science/tests/`): `science entity create spec` writes under
  `entities/specs/`; `plan_import(…, kind="spec")` yields dest
  `entities/specs/0001-<slug>.md`, `status="active"`, and id
  **`spec:0001-<slug>`** (the slug is part of `local_part` and therefore of the
  canonical id; `LOCAL_PART_WIDTH == 4`); a CLI `--save-plan` → `--apply-plan`
  round-trip lands the file and repoints a *structured* referrer while surfacing
  a *prose* mention as a manual hit; a created/imported spec appears in S2's
  `eligible_corpus`; and **`review_entity` actually stamps `review_state` on an
  imported spec** (the full curation loop, not just rotation selection).
- **Graph** (materialization): with `spec` annotation-only, (a) a spec entity
  materializes as a graph **node**; (b) an ordinary `spec:` metadata reference is
  **skipped** (no edge); (c) an authored **`spec → spec` supersedes edge
  materializes**. These three replace the earlier vague "no check assumes
  policy-kind ⇒ refs materialized" guard with concrete assertions.
- **id-prefixes**: `test_prefix_rules_cover_every_markdown_kind` now covers spec
  (via the policy table) and becomes the sole authority guard;
  `test_prefix_rules_retain_nonpolicy_kinds` is deleted along with
  `_EXTRA_PREFIX_KINDS`.
- **Interception**: a direct `test_command_docs.py` assertion that the AGENTS
  template / user-guide documents the staging-not-committed → preview → inspect
  manual hits → apply → commit-the-entity sequence (the existing structural
  template/marker test does not protect this new behavior).
- **Guard**: full suite green; update any kind-enumerating snapshot the new
  fields shift; `templates/agents-md.md` still passes its structural/marker test.

## Out of scope / follow-ups

- **S3b** — remove `spec` from `_ANNOTATION_REF_PREFIXES` (ordinary
  metadata-reference resolution + edges) **plus** the id-remap migration
  repointing existing date-slug **and** semantic `spec:` references to numeric
  ids across natural-systems, cbioportal, and multiple-myeloma, and reconciling
  the legacy `kind: spec` research-question entities. Its own design + migration.
- **mm `design` → `spec`** — mm re-imports `entities/design/*` as spec entities.
- No spec template / `template_ready` (parity with `plan`).
- No changes to the import engine.

## Risks

Low for S3a. Components 1–3 are declarative changes to `science-model` core plus
one validate-check constant, each guarded by an existing ratchet test, and the
surveyed projects take **zero new findings** (no `entities/specs/` dirs; legacy
`kind: spec` files sit at skipped singleton paths; `spec:*` refs stay
annotation-only). Component 4 is template + docs prose with a new command-doc
test. The blast radius of turning on `spec:*` reference resolution — and the
existing semantic/date-slug references and legacy spec entities it must migrate —
is entirely deferred behind the explicit S3b follow-up.
