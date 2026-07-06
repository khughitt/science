# Kernel Closure Phase 3a: Tier-2 + Tier-3 Writer Retirement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire 11 Tier-2 `graph add *` mutators + 3 Tier-3 writers (`import_snapshot`, `stamp_revision`, `migrate_addresses_direction`) so the source-declaration → `science graph build` path is the only durable writer, shrinking the durable-writer guard ledger from 18 to exactly the 4 deferred writers.

**Architecture:** The retired CLI subcommands stay (so users get actionable guidance) but their bodies `raise _retired_writer(...)`; the underlying Python functions are deleted and every re-export/import is pruned. Tests that assert **source-emitted** graph shapes migrate to author `entities/<kind>/*.md` (+ `relations.yaml` / inquiry `flow_edges`) and `materialize_graph`; tests that assert **mutator-only** graph shapes are deleted with a pointer to surviving coverage. This is NOT byte-identical — the source-built graph is deliberately smaller; the read-side audit (design §5.1) confirms no source-built consumer depends on any deleted predicate.

**Tech Stack:** Python 3, Click (CLI), rdflib (graph), pytest + `CliRunner`, Pydantic (`science_model`), `uv` (per-package). Design doc: [`2026-07-05-kernel-closure-phase3a-tier2-retirement-design.md`](2026-07-05-kernel-closure-phase3a-tier2-retirement-design.md).

## Global Constraints

- Run all `science`/CLI work from `science/` (`cd science && uv run --frozen …`); model work from `science/model/`. There is **no root `pyproject.toml`**.
- Worktree tests need `PYTHONPATH=src:model/src` prefixed (an editable `science_model` from `main` otherwise shadows worktree edits).
- Full validation gate for "green": `cd science && uv run --frozen pytest`, then `uv run ruff check`, then `uv run pyright`. Model tests: `cd science/model && uv run --frozen pytest`.
- Conventions: composition > inheritance; explicit > defensive; fail early (no silent fallbacks); no "legacy"/"compatibility" layers; no `Unified` prefix; no AI-attribution trailers on commits/PRs/comments; use `~/d/` (not absolute Dropbox paths) in docs/code.
- Retirement uses a hard, actionable `click.ClickException` — never a silent fallback or shim.
- **Disposition rule (design §5.1):** migrate an assertion iff the shape it asserts is source-emitted; delete an assertion over a mutator-only shape with a one-line pointer comment. Never weaken a migrated assertion; never fabricate a source form for a deleted one.
- The 4 **deferred** mutators — `add_article`, `add_falsification`, `add_story`, `add_paper_entity` — and their CLI commands stay untouched this phase; leave every test that uses them intact.
- Commit after each task. Do not push (local main is ahead of origin and this is a Dropbox-synced repo).

---

## File Structure

**Production code**
- `science/tests/graph/test_durable_write_boundary.py` — the guard; edit `EXPECTED_DEFERRED_WRITERS` (Task 1).
- `science/model/src/science_model/templates/{concept,observation,mechanism}.md` — new packaged templates (Task 2).
- `science/templates/{concept,observation,mechanism}.md` — byte-identical repo-root mirror (Task 2).
- `science/model/src/science_model/profiles/core.py` — mark 3 kinds `template_ready=True` (Task 2).
- `science/src/science_tool/cli.py` — add `_retired_writer` (Task 3); convert 14 command bodies + relax Click validation (Task 6); prune imports (Task 12).
- `science/src/science_tool/graph/store/mutations.py` — delete 11 functions + `_attach_edge_claims` + `_warn_on_relation_direction_mismatch` (Task 12).
- `science/src/science_tool/graph/store/snapshot.py` — delete `import_snapshot`, `stamp_revision` (Task 12).
- `science/src/science_tool/graph/__init__.py`, `science/src/science_tool/graph/store/__init__.py` — prune re-exports (Task 12).

**Tests**
- `science/tests/conftest.py` — add `build_entity_graph` helper (Task 4).
- CLI-invocation: `test_graph_cli.py` (Tasks 5, 6), `test_entities_cli.py`, `test_distill.py`, `test_membership_bridge.py` (Task 6).
- Direct-import: `test_causal.py` (Task 7), `test_graph_export.py` (Task 8), `test_paper_model.py` + `test_graph_materialize.py` (Task 9), `test_provenance_evidence.py` + `test_membership_bridge.py` + `test_inquiry.py` (Task 10), `test_meta_reference.py` + `test_layered_claim_migration.py` (Task 11).

**Docs/skills** (Task 13): `commands/{interpret-results,sketch-model,specify-model,plan-pipeline}.md`, `codex-skills/science-{interpret-results,sketch-model,specify-model,plan-pipeline}/SKILL.md`, `docs/conventions/cli-behavior.md`, `docs/user-guide/{cli-and-workflows,entities,epistemic-model,graph-and-derived-state}.md`.

---

## Task 1: Guard RED — name the retirement target

**Files:**
- Modify: `science/tests/graph/test_durable_write_boundary.py:48-69`

**Interfaces:**
- Produces: the frozen ledger `EXPECTED_DEFERRED_WRITERS = {4 deferred writers}`, which every later task's guard run checks against.

- [ ] **Step 1: Shrink the ledger to the 4 deferred writers**

Replace the `EXPECTED_DEFERRED_WRITERS` set body (lines 48-69) with exactly:

```python
EXPECTED_DEFERRED_WRITERS = {
    # Tier 2 — deferred to Phase 3b (no clean source-authoring file path).
    "graph/store/mutations.py:add_article",
    "graph/store/mutations.py:add_falsification",
    "graph/store/mutations.py:add_story",
    "graph/store/mutations.py:add_paper_entity",
}
```

Also update the module docstring's "Phase 1 … 18 deferred writers" framing to note the ledger now lists only the 4 Phase-3b-deferred writers and that Phase 3a is RED until Task 12 deletes the 14 retiring functions.

- [ ] **Step 2: Run the guard — expect RED with exactly 14 unexpected sites**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/graph/test_durable_write_boundary.py -q`
Expected: FAIL. The `unexpected` assertion lists exactly these 14 (order-independent):
`add_concept, add_proposition, add_observation, add_evidence_edge, add_finding, add_interpretation, add_discussion, add_mechanism, add_hypothesis, add_question, add_edge` (in `graph/store/mutations.py`), `migrate_addresses_direction` (in `graph/store/mutations.py`), `import_snapshot, stamp_revision` (in `graph/store/snapshot.py`). `stale` must be empty.

- [ ] **Step 3: Commit**

```bash
git add science/tests/graph/test_durable_write_boundary.py
git commit -m "test(kernel-closure): guard RED — shrink deferred-writer ledger to 4 (Phase 3a)"
```

---

## Task 2: Forward-path templates + descriptor gate

Each retired `graph add X` must point to a real authoring path. `concept`, `observation`, `mechanism` are compiler-loadable but template-less; add packaged templates (what `Renderer._read_template` reads via `importlib.resources` when no `template_root` is given) + the byte-identical repo-root mirror, and mark the kinds `template_ready` so `MIGRATED_KINDS` (derived from `template_ready`) includes them.

**Files:**
- Create: `science/model/src/science_model/templates/concept.md`, `.../observation.md`, `.../mechanism.md`
- Create: `science/templates/concept.md`, `science/templates/observation.md`, `science/templates/mechanism.md` (byte-identical mirror)
- Modify: `science/model/src/science_model/profiles/core.py` (concept ~L312, observation ~L100, mechanism ~L206)
- Test: `science/tests/test_entities_cli.py` (add create tests), `science/tests/test_kind_map_equivalence.py` (gate already asserts `set(MIGRATED_KINDS) == FROZEN` — update its frozen set)

**Interfaces:**
- Produces: working `science entity create concept|observation|mechanism`, which Task 6's retirement messages point to.

- [ ] **Step 1: Write the failing create test**

In `science/tests/test_entities_cli.py`, add (mirroring the existing `test_entity_create_concept_writes_source` style):

```python
def test_entity_create_observation_and_mechanism_scaffold_from_packaged_template(tmp_path: Path) -> None:
    seed_project(tmp_path)
    runner = CliRunner()
    for kind in ("concept", "observation", "mechanism"):
        result = runner.invoke(main, ["entity", "create", kind, f"Demo {kind}"], obj={"project_root": tmp_path})
        assert result.exit_code == 0, result.output
        assert f"{kind}:" in result.output
```

- [ ] **Step 2: Run it — expect FAIL (packaged template not found)**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_entities_cli.py::test_entity_create_observation_and_mechanism_scaffold_from_packaged_template -q`
Expected: FAIL — `EntityTemplateError: Packaged template not found: science_model/templates/observation.md` (concept/observation/mechanism all currently template-less).

- [ ] **Step 3: Author the three packaged templates**

`science/model/src/science_model/templates/concept.md` (slug strategy — model on `proposition.md`; reference kind, statuses `active`/`deprecated`):

```markdown
---
id: "concept:{{slug}}"
kind: "concept"
title: "{{title}}"
status: "{{status}}"
related: []
source_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "concept" }
    title: { from: title }
    status: { from: status }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: definition, name: "Definition", required: true }
    - { key: notes, name: "Notes", required: false }
---

# {{title}}

## Definition

<!-- One or two sentences naming this concept as the project uses it. -->

## Notes

<!-- Optional: scope, synonyms, ontology cross-references (author ontology CURIEs via `ontology_terms:` for a sci:about bridge edge). -->
```

`science/model/src/science_model/templates/observation.md` (slug strategy; epistemic; statuses `active`/`superseded`/`retired`/`archived`):

```markdown
---
id: "observation:{{slug}}"
kind: "observation"
title: "{{title}}"
status: "{{status}}"
related: []
source_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "observation" }
    title: { from: title }
    status: { from: status }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: observation, name: "Observation", required: true }
    - { key: source, name: "Source", required: true }
---

# {{title}}

## Observation

<!-- The concrete empirical fact: metric, value, and conditions in prose. -->

## Source

<!-- Data from: data-package:<id> or dataset:<id> (authored via source_refs). -->
```

`science/model/src/science_model/templates/mechanism.md` (numeric strategy — model on `finding.md`; participants/propositions frontmatter are read by the compiler for `sci:hasParticipant`/`sci:hasProposition`):

```markdown
---
id: "mechanism:{{nn}}-{{slug}}"
kind: "mechanism"
title: "{{title}}"
status: "{{status}}"
participants: []
propositions: []
related: []
source_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    kind: { default: "mechanism" }
    title: { from: title }
    status: { from: status }
    participants: { default: [] }
    propositions: { default: [] }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: summary, name: "Summary", required: true }
    - { key: participants, name: "Participants", required: true }
    - { key: propositions, name: "Propositions", required: true }
---

# {{title}}

## Summary

<!-- The explanatory structure this mechanism names. -->

## Participants

<!-- List the typed entities (concepts, variables) this mechanism links, e.g.:
- concept:<id>
-->

## Propositions

<!-- List the proposition refs this mechanism explains, e.g.:
- proposition:<id>
-->
```

- [ ] **Step 4: Mirror to repo-root `templates/` byte-identically**

```bash
cd science
cp model/src/science_model/templates/concept.md templates/concept.md
cp model/src/science_model/templates/observation.md templates/observation.md
cp model/src/science_model/templates/mechanism.md templates/mechanism.md
# verify identical
for k in concept observation mechanism; do diff model/src/science_model/templates/$k.md templates/$k.md && echo "$k OK"; done
```

- [ ] **Step 5: Mark the three kinds `template_ready` in CORE_PROFILE**

In `science/model/src/science_model/profiles/core.py`, add `template_ready=True,` to the `EntityKind(name="concept", …)`, `EntityKind(name="observation", …)`, and `EntityKind(name="mechanism", …)` descriptors (place the line alongside `category=KindCategory.AUTHORED_CORE,`, matching how `finding`/`interpretation`/`theme` set it).

- [ ] **Step 6: Update the MIGRATED_KINDS equivalence gate**

`MIGRATED_KINDS` is derived from `template_ready`, so `tests/test_kind_map_equivalence.py`'s frozen expectation now needs the 3 new members. Add `"concept"`, `"observation"`, `"mechanism"` to that test's `FROZEN_MIGRATED_KINDS` set (the test asserts `set(MIGRATED_KINDS) == FROZEN_…`).

- [ ] **Step 7: Run the create test + gate + model suite — expect PASS**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_entities_cli.py::test_entity_create_observation_and_mechanism_scaffold_from_packaged_template tests/test_kind_map_equivalence.py -q`
Then: `cd science/model && uv run --frozen pytest -q`
Expected: PASS (templates render; reconciliation/equivalence gate green).

- [ ] **Step 8: Commit**

```bash
git add science/model/src/science_model/templates science/templates science/model/src/science_model/profiles/core.py science/tests/test_entities_cli.py science/tests/test_kind_map_equivalence.py
git commit -m "feat(entities): add concept/observation/mechanism create templates (Phase 3a forward paths)"
```

---

## Task 3: Generic `_retired_writer` helper

**Files:**
- Modify: `science/src/science_tool/cli.py` (near the existing `_retired_mutator`, ~L3013)
- Test: `science/tests/test_graph_cli.py`

**Interfaces:**
- Produces: `_retired_writer(command: str, forward_path: str) -> click.ClickException` — used by every retired command body in Task 6.

- [ ] **Step 1: Write the failing helper test**

Add to `science/tests/test_graph_cli.py`:

```python
def test_retired_writer_message_names_command_and_forward_path() -> None:
    from science_tool.cli import _retired_writer

    exc = _retired_writer("graph add concept", "Run `science entity create concept <title>`")
    msg = str(exc)
    assert "graph add concept is retired" in msg
    assert "science entity create concept" in msg
    assert "science graph build" in msg
```

- [ ] **Step 2: Run it — expect FAIL (import error)**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_graph_cli.py::test_retired_writer_message_names_command_and_forward_path -q`
Expected: FAIL — `ImportError: cannot import name '_retired_writer'`.

- [ ] **Step 3: Add the helper**

In `science/src/science_tool/cli.py`, directly after the existing `_retired_mutator` (keep `_retired_mutator` for Phase 1's inquiry commands):

```python
def _retired_writer(command: str, forward_path: str) -> click.ClickException:
    return click.ClickException(
        f"{command} is retired. {forward_path}, then run `science graph build`."
    )
```

- [ ] **Step 4: Run it — expect PASS**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_graph_cli.py::test_retired_writer_message_names_command_and_forward_path -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_graph_cli.py
git commit -m "feat(cli): add generic _retired_writer error helper (Phase 3a)"
```

---

## Task 4: Shared `build_entity_graph` test helper

**Files:**
- Modify: `science/tests/conftest.py` (add after `build_inquiry_graph`, ~L95)

**Interfaces:**
- Consumes: `tests/_fixtures/entity_helpers.write_markdown_entity`, `science_tool.graph.materialize.materialize_graph`.
- Produces: `build_entity_graph(project_root: Path, entities: list[dict], relations: list[dict] | None = None) -> Path` returning the compiled `knowledge/graph.trig` path. Each `entities` item is `{"kind": str, "id": str, "frontmatter": dict, "body": str}`; each `relations` item is a `SourceRelation`-shaped dict written to `knowledge/sources/<local>/relations.yaml`.

- [ ] **Step 1: Write the failing helper test**

Add to `science/tests/conftest.py`-adjacent `tests/test_conftest_helpers.py` (create it):

```python
from pathlib import Path

from rdflib import Dataset, URIRef

from conftest import build_entity_graph
from science_tool.graph.store import _load_dataset


def test_build_entity_graph_emits_authored_concept(tmp_path: Path) -> None:
    graph_path = build_entity_graph(
        tmp_path,
        entities=[{"kind": "concept", "id": "drug", "frontmatter": {"title": "Drug"}, "body": "## Definition\n\nA drug."}],
    )
    ds = _load_dataset(graph_path)
    subjects = {str(s) for s in ds.subjects()}
    assert any(s.endswith("concept/drug") for s in subjects)
```

- [ ] **Step 2: Run it — expect FAIL (import error)**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_conftest_helpers.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_entity_graph'`.

- [ ] **Step 3: Implement `build_entity_graph` in `tests/conftest.py`**

```python
def build_entity_graph(
    project_root: Path,
    entities: list[dict],
    relations: list[dict] | None = None,
):
    """Author entity markdown (+ optional relations.yaml) and materialize.

    The general-entity sibling of ``build_inquiry_graph``: it takes the SAME
    source path a user takes (`entities/<kind>/<id>.md` + `relations.yaml`) and
    runs the compiler, returning the compiled ``knowledge/graph.trig`` path.
    Each ``entities`` item: {kind, id, frontmatter(dict, sans id/kind), body}.
    Each ``relations`` item: a SourceRelation-shaped dict
    {subject, predicate, object, graph_layer?}.
    """
    import yaml

    from _fixtures.entity_helpers import seed_project, write_markdown_entity
    from science_model.profiles.core import CORE_PROFILE
    from science_tool.graph.materialize import materialize_graph

    if not (project_root / "science.yaml").exists():
        seed_project(project_root)
    homes = {ek.name: ek.home for ek in CORE_PROFILE.entity_kinds}
    for ent in entities:
        kind = ent["kind"]
        home = homes[kind]
        fm = {"id": f"{kind}:{ent['id']}", "kind": kind, **ent.get("frontmatter", {})}
        write_markdown_entity(project_root, f"{home}/{ent['id']}.md", fm, ent.get("body", ""))
    if relations:
        rel_dir = project_root / "knowledge" / "sources" / "relations"
        rel_dir.mkdir(parents=True, exist_ok=True)
        (rel_dir / "relations.yaml").write_text(yaml.safe_dump({"relations": relations}), encoding="utf-8")
    return materialize_graph(project_root)
```

(If `write_markdown_entity`/`seed_project` signatures differ from `(root, rel_path, frontmatter, body)` / `(root)`, adapt to the actual signatures in `tests/_fixtures/entity_helpers.py` — do not change the fixture.)

- [ ] **Step 4: Run it — expect PASS**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_conftest_helpers.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/tests/conftest.py science/tests/test_conftest_helpers.py
git commit -m "test(conftest): add build_entity_graph source-authoring helper (Phase 3a)"
```

---

## Task 5: Migrate `test_graph_cli.py` "setup-only" tests to authored source

The ~30 `test_graph_cli` tests that use `graph add *` **only to seed state** for query/summary/validate/coverage/gaps/uncertainty/dashboard/neighborhood/question-summary surfaces (which STAY). Migrate their setup to authored source **before** the bodies are retired (Task 6), so they no longer invoke `graph add *`. Do this while `graph add *` still works, so each converted test stays green.

**Files:**
- Modify: `science/tests/test_graph_cli.py` (setup-only tests + helpers `_setup_evidence_graph`, `_setup_claim_backed_hypothesis_evidence_graph`)

**Interfaces:**
- Consumes: `build_entity_graph` (Task 4), `build_inquiry_graph` (existing), `entity create` CLI.

- [ ] **Step 1: Enumerate and convert setup per the audit**

For each setup-only test (full list in design §8 / the audit inventory), replace `graph add *` seed calls with authored source, keeping the query/summary command and its assertion:
- `graph add concept X` → author `concepts/x.md` (via `build_entity_graph` or `entity create concept`).
- `graph add hypothesis`/`question`/`proposition` → author the entity `.md`; `--related`/`--maturity`/structured S-P-O that are mutator-only are dropped from setup (they were not what the query test asserts).
- `graph add evidence` / evidence setup → author `evidence-lines/*.md` (`stance`/`strength`/`independence`).
- `graph add edge <a> <p> <b> --graph <layer>` (structural adjacency, e.g. `cito:discusses`, `sci:addresses`, `sci:measuredBy`, `skos:broader`) → a `relations.yaml` entry with `graph_layer`.
- Causal edges → `relations.yaml` at `graph_layer: graph/causal`.

Worked example — `test_graph_neighborhood_query_supports_json_format` (setup `graph add edge concept/brca1 skos:broader concept/tp53`):

```python
def test_graph_neighborhood_query_supports_json_format(tmp_path: Path) -> None:
    build_entity_graph(
        tmp_path,
        entities=[
            {"kind": "concept", "id": "brca1", "frontmatter": {"title": "BRCA1"}},
            {"kind": "concept", "id": "tp53", "frontmatter": {"title": "TP53"}},
        ],
        relations=[{"subject": "concept:brca1", "predicate": "skos:broader", "object": "concept:tp53", "graph_layer": "graph/knowledge"}],
    )
    runner = CliRunner()
    result = runner.invoke(main, ["graph", "neighborhood", "BRCA1", "--format", "json", "--path", str(tmp_path / "knowledge/graph.trig")], obj={"project_root": tmp_path})
    assert result.exit_code == 0
    rows = json.loads(result.output)["rows"]
    assert any(r["predicate"].endswith("broader") for r in rows)
```

- [ ] **Step 2: Drop assertions over mutator-only query columns (delete-with-pointer)**

For `test_graph_dashboard_summary_reports_explicit_evidence_semantics`, `…_pre_registration_links`, `…_interaction_terms`, `…_cross_hypothesis_bridges` — the asserted columns read the **mutator-only proposition payload** (§5.1), which no source path produces. Delete these tests (or the specific column assertions) with a comment:

```python
# Removed in kernel-closure Phase 3a: statistical/bridge/interaction/pre-registration
# dashboard columns are populated only by the retired `graph add proposition` payload
# (design §5.1 shape group #9); they are empty for source-built projects. The
# dashboard-summary *shape* stays covered by the migrated evidence-mix test above.
```

Keep the bridge *membership* (`cito:discusses`) coverage where it is source-emitted — author `proposition` frontmatter `discusses:` / `bridge_between` instead.

- [ ] **Step 3: Run the migrated file — expect PASS (bodies still live)**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_graph_cli.py -q`
Expected: PASS. (The `graph add *` unit-under-test tests are still present and green here — they are handled in Task 6.)

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_graph_cli.py
git commit -m "test(graph-cli): migrate setup-only tests to authored source (Phase 3a)"
```

---

## Task 6: Retire the 14 CLI bodies + dispose CLI-invocation tests

Convert every retired command body to `raise _retired_writer(...)`, relax obsolete Click validation so the message always surfaces, and update the remaining CLI-invocation tests. The Python functions still exist (guard stays RED) — this task retires the **surface**.

**Files:**
- Modify: `science/src/science_tool/cli.py` — the 11 `graph_add.command` bodies (~L2365-2887, retiring ones only) + `graph_import` (~L2308), `graph_stamp_revision` (~L1800), `graph_migrate_addresses` (~L1658)
- Modify: `science/tests/test_graph_cli.py`, `science/tests/test_entities_cli.py`, `science/tests/test_distill.py`, `science/tests/test_membership_bridge.py`

**Interfaces:**
- Consumes: `_retired_writer` (Task 3).

- [ ] **Step 1: Convert the 11 retiring `graph add` bodies**

For each retiring subcommand, replace the body with a single `raise`. Keep the `@graph_add.command(...)` decorator and function signature, but **strip obsolete validation** so the raise is always reached: drop `required=True`, `type=click.Choice(...)`, and any `@click.argument` requiredness that would preempt the body (make arguments `required=False`). Forward paths:

| command | `_retired_writer(command, forward_path)` |
|---|---|
| `graph add concept` | `"graph add concept"`, `"Run \`science entity create concept <title>\` (or edit entities/concepts/<slug>.md)"` |
| `graph add proposition` | `"graph add proposition"`, `"Run \`science propositions create <title>\`"` |
| `graph add observation` | `"graph add observation"`, `"Run \`science entity create observation <title>\`"` |
| `graph add evidence` | `"graph add evidence"`, `"Run \`science evidence-lines create --target <ref> --stance <supports|disputes>\`"` |
| `graph add finding` | `"graph add finding"`, `"Run \`science entity create finding <title>\`"` |
| `graph add interpretation` | `"graph add interpretation"`, `"Run \`science interpretations create <title>\`"` |
| `graph add discussion` | `"graph add discussion"`, `"Run \`science discussions create <title>\`"` |
| `graph add mechanism` | `"graph add mechanism"`, `"Run \`science entity create mechanism <title>\`"` |
| `graph add hypothesis` | `"graph add hypothesis"`, `"Run \`science hypotheses create <title>\`"` |
| `graph add question` | `"graph add question"`, `"Run \`science questions create <title>\`"` |
| `graph add edge` | `"graph add edge"`, `"Author the relation in \`relations.yaml\` (or \`relations:\` frontmatter) with the target graph_layer; claim-cited edges use inquiry flow_edges"` |

Example (concept) — the whole body becomes:

```python
def graph_add_concept(  # signature unchanged; options may lose Choice/required
    label: str | None = None,
    ...,
) -> None:
    """[RETIRED] Author concepts as source; see `science entity create concept`."""
    raise _retired_writer(
        "graph add concept",
        "Run `science entity create concept <title>` (or edit entities/concepts/<slug>.md)",
    )
```

- [ ] **Step 2: Convert the 3 Tier-3 command bodies + relax their validation**

- `graph_import` (`cli.py:2308`): change `@click.argument("snapshot_path", type=click.Path(exists=True, path_type=Path))` → `@click.argument("snapshot_path", required=False, type=click.Path(path_type=Path))` and body → `raise _retired_writer("graph import", "Raw-triple import is retired; author the source records and run")` (its forward path is just `science graph build`, so the message reads "… run `science graph build`.").
- `graph_stamp_revision` (`cli.py:1800`): body → `raise _retired_writer("graph stamp-revision", "The compiler stamps revisions; run")`.
- `graph_migrate_addresses` (`cli.py:1658`): body → `raise _retired_writer("graph migrate-addresses", "Address direction is canonical at build; run")`.

- [ ] **Step 3: Update CLI-invocation tests**

- `test_entities_cli.py` — the 5 ephemerality/tip tests (`test_graph_add_question_mentions_entity_create`, `…_proposition/observation/finding/evidence_warns_about_ephemerality`): assert the retirement message + non-zero exit instead of the old warning text, e.g.:

```python
def test_graph_add_question_is_retired(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["graph", "add", "question", "q01", "--text", "x", "--source", "paper:a"], obj={"project_root": tmp_path})
    assert result.exit_code != 0
    assert "graph add question is retired" in result.output
    assert "science questions create" in result.output
```

- `test_graph_cli.py` — **delete** the ~35 unit-under-test tests that assert mutator-only triples (`test_graph_add_concept_writes_expected_triples`, `…_with_note/_definition/_property_*`, `…_relation_claim_writes_claim_types…`, `…_add_claim_*`, `…_add_edge_*` semantics/warns, `…_add_question_creates_entity…`/`…_with_maturity…`, `…_add_mechanism_*`, `test_graph_migrate_addresses_flips_…`, `test_graph_stamp_revision_updates_…`) with a class/module-level pointer comment:

```python
# Removed in kernel-closure Phase 3a: these asserted graph state written by the
# retired `graph add *` / `graph import` / `graph stamp-revision` /
# `graph migrate-addresses` writers. Source-authored equivalents (node shape,
# causal edges, evidence lines, cito:discusses bridges) are covered by
# test_graph_materialize / test_causal / test_graph_export. Mutator-only shapes
# (design §5.1) have no source form and are intentionally gone.
```

Keep exactly one retirement-message assertion per retired command family (concept/edge/proposition/mechanism/import/stamp-revision/migrate-addresses) so the retired surface stays guarded, e.g.:

```python
def test_graph_add_edge_is_retired(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["graph", "add", "edge", "concept/a", "skos:broader", "concept/b"], obj={"project_root": tmp_path})
    assert result.exit_code != 0
    assert "graph add edge is retired" in result.output


def test_graph_import_is_retired_regardless_of_missing_path(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["graph", "import", "does-not-exist.ttl"], obj={"project_root": tmp_path})
    assert result.exit_code != 0
    assert "graph import is retired" in result.output  # not a Click path-exists error
```

Leave the 3 DEFERRED tests (`test_graph_add_paper_claim_hypothesis_records_provenance` [uses `graph add article`], `test_graph_add_story_warns_…`, `test_graph_add_paper_warns_…`) untouched.

- `test_distill.py` — the 3 `test_graph_import_*` tests become one `test_graph_import_is_retired` message assertion (distill has no live dependency on `import_snapshot`; the distill unit/CLI tests are untouched).
- `test_membership_bridge.py::TestBridgeRoleCli::test_bridge_role_background_via_cli` — reseed via `entity create` / authored proposition (`bridge_between` + `bridge_role: background`) + `graph build`, then assert the `BundleMembership` role; or delete it with a pointer to the migrated `TestBridgeBetweenMembership` (Task 10).

- [ ] **Step 4: Run the CLI suites — expect PASS**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_graph_cli.py tests/test_entities_cli.py tests/test_distill.py tests/test_membership_bridge.py -q`
Expected: PASS. Guard still RED (functions not yet deleted) — do not run it as a gate here.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_graph_cli.py science/tests/test_entities_cli.py science/tests/test_distill.py science/tests/test_membership_bridge.py
git commit -m "feat(cli): retire 14 graph-writer command surfaces via _retired_writer (Phase 3a)"
```

---

## Task 7: Migrate `test_causal.py`

Biggest direct-import migration. Concepts → authored `concepts/*.md`; `scic:causes`/`confounds` edges → `relations.yaml` (`graph/causal`); claim-cited edges (`TestEdgeProvenance`, export-provenance) → inquiry `flow_edges` with `claim_refs` referencing authored propositions.

**Files:**
- Modify: `science/tests/test_causal.py`

**Interfaces:**
- Consumes: `build_entity_graph`, `build_inquiry_graph` (already used in-file via `_build_compiled_inquiry_graph`).

- [ ] **Step 1: Replace concept + hypothesis + plain-edge setup**

Class helpers (`_setup_causal_inquiry`, `_build_simple_dag`, `_build_identifiable_dag`): author the X/Y/Z concepts and the hypothesis as source, and author the `scic:causes`/`confounds` edges via `relations.yaml` at `graph_layer: graph/causal`. Example for a causes edge pair:

```python
build_entity_graph(
    tmp_path,
    entities=[
        {"kind": "concept", "id": "x", "frontmatter": {"title": "X"}},
        {"kind": "concept", "id": "y", "frontmatter": {"title": "Y"}},
        {"kind": "concept", "id": "z", "frontmatter": {"title": "Z"}},
        {"kind": "hypothesis", "id": "h01", "frontmatter": {"title": "Test hypothesis"}},
    ],
    relations=[
        {"subject": "concept:x", "predicate": "scic:causes", "object": "concept:y", "graph_layer": "graph/causal"},
        {"subject": "concept:z", "predicate": "scic:causes", "object": "concept:y", "graph_layer": "graph/causal"},
    ],
)
```

Then build the causal inquiry via the existing `_build_compiled_inquiry_graph` (boundary roles / treatment / outcome unchanged). `validate_inquiry` acyclicity/confounders/identifiability assertions are **kept** (those checks read the `graph/causal` edges, which are now source-authored).

- [ ] **Step 2: Re-express claim-cited edges as inquiry `flow_edges`**

For `TestEdgeProvenance` and the export-provenance tests, author the proposition as source and cite it from an inquiry flow edge instead of `add_edge(..., claim_refs=[...])`:

```python
build_entity_graph(tmp_path, entities=[
    {"kind": "concept", "id": "drug", "frontmatter": {"title": "Drug"}},
    {"kind": "concept", "id": "recovery", "frontmatter": {"title": "Recovery"}},
    {"kind": "proposition", "id": "drug_causes_recovery", "frontmatter": {"title": "Drug causes recovery"}, "body": "## Claim\n\nDrug causes recovery."},
])
build_inquiry_graph(graph_path, slug="prov-dag", profile="causal", normalize_slug=True,
    treatment="concept:drug", outcome="concept:recovery",
    flow_edges=[{"subject": "concept:drug", "predicate": "causes", "object": "concept:recovery", "claim_refs": ["proposition:drug_causes_recovery"]}])
```

Assertions that survive (source-emitted): edge exists, `claims` non-empty with `text`/`sources`, `confidence` (author `confidence:` on the proposition), support/dispute counts.

- [ ] **Step 3: Delete mutator-only payload/observability assertions (delete-with-pointer)**

Delete the assertions/tests that read **mutator-only** shapes (§5.1): `subject_observability`/`object_observability` and the latent/confounds-as-latent expectations (concept `sci:observability`); `compositional_status`/`platform_pattern`/`dataset_effects`/`evidence_lines`/`statistical_support`/`mechanistic_support`/`replication_scope`/`claim_status`/`pre_registrations`/`interaction_terms`/`bridge_between` on edge claims; and the pgmpy/chirho **comment** assertions that echo them (`test_export_pgmpy_includes_phase1_claim_metadata_comments`, `…_explicit_evidence_semantics_comments`, `…_pre_registration_comments`, `…_interaction_comments`, `…_bridge_comments`, `test_enriched_edges_include_*` for those fields, `test_export_pgmpy_includes_confounds_as_latent_edges`, `…_todo_section`/`…_todo_latent_variables` observability TODOs). Leave one pointer comment on the class:

```python
# Removed in kernel-closure Phase 3a: proposition-provenance payload and concept
# observability are mutator-only shapes (design §5.1 groups #4, #9) with no source
# form; source-built causal export omits these comments/latent hints by design.
```

Keep the structural export tests (`test_export_pgmpy_generates_valid_script`, `…_contains_edge_tuples`, `…_topological_order`, `…_reads_compiled_patch_inquiry_edges`, provenance-comment `# Generated from inquiry:` / `# Treatment:` / `# Revision:`).

- [ ] **Step 4: Leave `add_falsification` tests intact (deferred)**

`test_enriched_edges_include_linked_falsifications` and `test_export_pgmpy_includes_falsification_comments` use the DEFERRED `add_falsification` — leave them calling it (the function and its `store` import stay until 3b). If they also depend on a now-deleted `add_proposition`/`add_edge` for setup, re-author just that setup via source per Steps 1-2 while keeping the `add_falsification` call.

- [ ] **Step 5: Run the file — expect PASS**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_causal.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/tests/test_causal.py
git commit -m "test(causal): migrate to authored source; drop mutator-only claim payload (Phase 3a)"
```

---

## Task 8: Migrate `test_graph_export.py`

**Files:**
- Modify: `science/tests/test_graph_export.py`

- [ ] **Step 1: Rebuild the shared `graph_path` fixture from source**

Replace the fixture's `add_concept`/`add_hypothesis`/`add_edge`/`add_proposition` seeding with: authored `concepts/{drug,recovery,kras}.md` + `hypothesis/{h1,h2}.md` + `proposition/drug_causes_recovery_evidence.md`; the `scic:causes` causal edge via `relations.yaml` (`graph/causal`); and the claim-backed causal edge via an inquiry `flow_edge` with `claim_refs`. Keep the two `build_inquiry_graph` calls (test_dag, dangling_dag) as-is.

- [ ] **Step 2: Keep source-emitted assertions; delete payload-overlay ones**

Keep: base nodes/edges/layers, `edge.graph_layer == "graph/causal"`, causal-overlay `kind == "causes"`/`confounds`, mechanism-node test (`add_mechanism` → author `mechanisms/*.md`), missing-referent warnings. Delete-with-pointer the evidence-overlay tests reading the mutator-only payload (`test_export_graph_payload_includes_evidence_overlay_for_claim_backed_edge` asserting `bridge_between`/`statistical_support`/`pre_registrations`). Tests that build via raw TrIG / `_load_dataset` / `_build_dataset_from_sources` are already source-path — leave them.

- [ ] **Step 3: Run + commit**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_graph_export.py -q` (expect PASS)
```bash
git add science/tests/test_graph_export.py
git commit -m "test(graph-export): rebuild fixture from source; drop payload overlay asserts (Phase 3a)"
```

---

## Task 9: Migrate `test_paper_model.py` + `test_graph_materialize.py`

**Files:**
- Modify: `science/tests/test_paper_model.py`, `science/tests/test_graph_materialize.py`

- [ ] **Step 1: `test_paper_model.py` — migrate node/composition, delete mutator-only**

Author `hypothesis`/`observation`/`proposition`/`finding`/`interpretation` as source. `sci:contains`/`sci:groundedBy` are **mutator-only** (§5.1) — delete those assertions with a pointer to `test_graph_materialize::test_materialize_graph_emits_mechanism_participants_and_propositions` (source-emitted composition). `test_add_finding_invalid_confidence` tested mutator validation → move to `FindingEntity` schema construction if a validator exists there, else delete-with-pointer. Leave `test_add_story*`, `test_add_paper_entity*`, and the deferred branches of `test_full_composition_chain` intact (they use DEFERRED mutators); re-author only the retiring-mutator setup inside `test_full_composition_chain`.

- [ ] **Step 2: `test_graph_materialize.py` — delete the one mutator test**

`test_source_authored_hypothesis_and_graph_added_hypothesis_do_not_double_count` exists to prove a `graph add hypothesis` write doesn't double-count vs source; post-retirement that path is gone. Delete it with:

```python
# Removed in kernel-closure Phase 3a: `graph add hypothesis` is retired, so the
# source-vs-mutator double-count scenario no longer exists. Source-authored
# hypothesis emission stays covered by the surrounding materialize tests.
```

All other tests in this file are already source→build — untouched.

- [ ] **Step 3: Run + commit**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_paper_model.py tests/test_graph_materialize.py -q` (expect PASS)
```bash
git add science/tests/test_paper_model.py science/tests/test_graph_materialize.py
git commit -m "test(paper-model,materialize): migrate/prune retired-mutator tests (Phase 3a)"
```

---

## Task 10: Migrate `test_provenance_evidence.py` + `test_membership_bridge.py` + `test_inquiry.py`

**Files:**
- Modify: `science/tests/test_provenance_evidence.py`, `science/tests/test_membership_bridge.py`, `science/tests/test_inquiry.py`

- [ ] **Step 1: `test_provenance_evidence.py` — author evidence-lines**

The fixture and 3 tests assert `evidenceIndependence` presence/absence and invalid-independence rejection. Author an `evidence-lines/<id>.md` with `target`, `stance`, `strength`, `independence` (all source-emitted). Note the edge subject is the evidence-line node (not the source entity) — adjust the triple lookup accordingly. The invalid-independence case moves from the mutator's `ClickException` to `EvidenceLineEntity` construction / `materialize` rejection (assert `pytest.raises` on the authored invalid value).

- [ ] **Step 2: `test_membership_bridge.py::TestBridgeBetweenMembership` — author proposition with bridge**

The 3 tests assert `cito:discusses` + `BundleMembership` + `membershipRole` + provenance `bridgeBetween` — all source-emitted via a proposition authoring `discusses:`/`bridge_between`. Replace `add_hypothesis`/`add_proposition` with authored `hypothesis/0001-foo.md` + `proposition/bridge-prop-01.md` (frontmatter `bridge_between: [hypothesis:0001-foo]`, `bridge_role: core`), then `materialize`. Keep all three assertions.

- [ ] **Step 3: `test_inquiry.py` — author the concept seed**

`test_get_inquiry_materialized_does_not_leak_knowledge_edges` seeds one `add_concept("unrelated_concept")`. Replace with `build_entity_graph(..., entities=[{"kind": "concept", "id": "unrelated_concept", "frontmatter": {"title": "Unrelated"}}])` merged into the inquiry graph, keeping the `result["edges"] == []` assertion.

- [ ] **Step 4: Run + commit**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_provenance_evidence.py tests/test_membership_bridge.py tests/test_inquiry.py -q` (expect PASS)
```bash
git add science/tests/test_provenance_evidence.py science/tests/test_membership_bridge.py science/tests/test_inquiry.py
git commit -m "test(evidence,bridge,inquiry): migrate to authored source (Phase 3a)"
```

---

## Task 11: Migrate `test_meta_reference.py` + `test_layered_claim_migration.py`

**Files:**
- Modify: `science/tests/test_meta_reference.py`, `science/tests/test_layered_claim_migration.py`

- [ ] **Step 1: `test_meta_reference.py` — meta-rejection via source**

`TestMetaRefsInAddEdge` (2 tests, `add_edge` with a `meta:` subject/object) and `TestMetaRefsInAddQuestion` (`add_hypothesis` + `add_question` with a `meta:` in `related`) assert meta-refs are rejected/skipped. The file already proves the source-build analogue in `TestMetaRefsInInquiryFlowEdge` (meta subject/object → `PatchMembershipError` at build) and `TestMetaRefsInMaterialize`/`…BlockedByAndSourceRefs` (`related`/`blocked_by`/`source_refs` meta not materialized). Re-express the `add_edge` cases as a `relations.yaml` entry with a `meta:` endpoint and assert the compiler rejects/skips it; re-express the `add_question` case as authored `question` frontmatter `related: [hypothesis:h1, meta:phase3b]` + `materialize`, asserting no `skos:related` to `meta`. If the compiler's meta-handling is already fully covered by the existing source tests, delete the mutator variants with a pointer to those classes instead.

- [ ] **Step 2: `test_layered_claim_migration.py` — reasoning metadata + validator retarget**

`test_export_graph_payload_includes_layered_claim_metadata_for_claim_backed_edge`: the layered-claim bundle (`claim_layer`/`identification_strength`/`proxy_directness`/`supports_scope`/`independence_group`/`evidence_role`/`measurement_model`/`rival_model_packet`) is **source-emitted** (`_add_reasoning_metadata`). Migrate: author `concepts/{drug,recovery}.md` + a `proposition/drug_claim.md` carrying those frontmatter fields, a `relations.yaml` `scic:causes` causal edge, and an inquiry `flow_edge` with `claim_refs=["proposition:drug_claim"]`; keep the bundle assertions.
`test_add_proposition_validates_raw_reasoning_metadata_dicts`: this tested the **entity model** validator (incomplete `measurement_model`/`rival_model_packet` dicts). Re-target it at `PropositionEntity(...)` construction — assert `pydantic.ValidationError` on the incomplete dict — since the validator now lives on the schema, not the mutator. (All other tests in this file are already source-path — untouched.)

- [ ] **Step 3: Run + commit**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_meta_reference.py tests/test_layered_claim_migration.py -q` (expect PASS)
```bash
git add science/tests/test_meta_reference.py science/tests/test_layered_claim_migration.py
git commit -m "test(meta-ref,layered-claim): migrate to authored source; retarget model validator (Phase 3a)"
```

---

## Task 12: Delete the writers + prune re-exports → guard GREEN

Now that no test imports the retiring functions, delete them and prune every export. This is the change that turns the guard GREEN.

**Files:**
- Modify: `science/src/science_tool/graph/store/mutations.py` (delete 11 `add_*` + `_attach_edge_claims` + `_warn_on_relation_direction_mismatch` + `migrate_addresses_direction`)
- Modify: `science/src/science_tool/graph/store/snapshot.py` (delete `import_snapshot`, `stamp_revision`)
- Modify: `science/src/science_tool/graph/store/__init__.py` (imports L71-93), `science/src/science_tool/graph/__init__.py` (imports L16-42, `__all__` L59-85), `science/src/science_tool/cli.py` (imports L64-100, local import L1674)

**Interfaces:**
- Consumes: nothing new. Produces: the retired names no longer exist anywhere.

- [ ] **Step 1: Delete the function definitions**

In `mutations.py` delete: `add_concept`, `add_proposition`, `add_observation`, `add_evidence_edge`, `add_finding`, `add_interpretation`, `add_discussion`, `add_mechanism`, `add_hypothesis`, `add_question`, `add_edge`, `migrate_addresses_direction`, and the two now-dead `add_edge`-local helpers `_warn_on_relation_direction_mismatch` and `_attach_edge_claims` (both are only called from inside `add_edge`; confirmed no compiler/authored-relation caller). Keep the DEFERRED `add_article`, `add_falsification`, `add_story`, `add_paper_entity`. In `snapshot.py` delete `import_snapshot` and `stamp_revision`.

- [ ] **Step 2: Prune re-exports and imports**

- `graph/store/__init__.py` (L71-93): remove `_attach_edge_claims`, `_warn_on_relation_direction_mismatch`, `add_concept`, `add_discussion`, `add_edge`, `add_evidence_edge`, `add_finding`, `add_hypothesis`, `add_interpretation`, `add_mechanism`, `add_observation`, `add_proposition`, `add_question`, `migrate_addresses_direction` from the `.mutations` import; keep `add_article`, `add_falsification`, `add_paper_entity`, `add_story`. Change `from .snapshot import import_snapshot, stamp_revision` to remove both names (delete the line if nothing else is imported from `.snapshot`).
- `graph/__init__.py`: remove `add_concept`, `add_discussion`, `add_edge`, `add_evidence_edge`, `add_finding`, `add_hypothesis`, `add_interpretation`, `add_observation`, `add_proposition`, `add_question`, `import_snapshot`, `stamp_revision` from both the `from science_tool.graph.store import (...)` block **and** the `__all__` list. Keep `add_article`, `add_paper_entity`, `add_story` (and `add_falsification` if present).
- `cli.py`: remove `add_concept`, `add_discussion`, `add_edge`, `add_evidence_edge`, `add_finding`, `add_hypothesis`, `add_interpretation`, `add_mechanism`, `add_observation`, `add_proposition`, `add_question`, `import_snapshot`, `stamp_revision` from the top-level `from science_tool.graph.store import (...)` block (L64-100); keep `add_article`, `add_falsification`, `add_paper_entity`, `add_story`. Delete the local `from science_tool.graph.store import migrate_addresses_direction` at ~L1674.

- [ ] **Step 3: Let ruff find any stragglers**

Run: `cd science && PYTHONPATH=src:model/src uv run ruff check`
Fix every `F401` (unused import) / `F821` (undefined name) it reports — e.g. now-unused `_parse_dataset_effects`/`_parse_evidence_lines`/`_parse_interaction_terms`/`PropositionEvidenceLine`/`MembershipRole` imports/helpers that only fed the deleted `add_proposition_cmd`. Delete genuinely-dead helpers; do not silence with `# noqa`.

- [ ] **Step 4: Guard GREEN + full suite**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/graph/test_durable_write_boundary.py -q`
Expected: PASS — `actual == EXPECTED_DEFERRED_WRITERS == {add_article, add_falsification, add_story, add_paper_entity}`.
Then: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest -q` (expect full suite green).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/store/mutations.py science/src/science_tool/graph/store/snapshot.py science/src/science_tool/graph/store/__init__.py science/src/science_tool/graph/__init__.py science/src/science_tool/cli.py
git commit -m "refactor(kernel-closure): delete 14 retired graph writers + prune exports — guard GREEN (Phase 3a)"
```

---

## Task 13: Docs / skills sweep + final gate

`test_command_docs` / `test_codex_skills` enforce doc guidance; repoint the live surfaces that still instruct `graph add *` / `graph import` / `graph stamp-revision` / `graph migrate-addresses` to source authoring, and run the full gate.

**Files:**
- Modify: `commands/{interpret-results,sketch-model,specify-model,plan-pipeline}.md`, `codex-skills/science-{interpret-results,sketch-model,specify-model,plan-pipeline}/SKILL.md`, `docs/conventions/cli-behavior.md`, `docs/user-guide/{cli-and-workflows,entities,epistemic-model,graph-and-derived-state}.md`
- (Do NOT touch `docs/plans/historical/**`, `docs/audits/**`, or the design/plan docs — those are historical record.)

- [ ] **Step 1: Repoint each live surface**

Replace `science graph add <kind> …` instructions with the durable path (`science entity create <kind>` / `science <kind>s create` / edit `entities/<kind>/*.md` / `relations:` + `science graph build`). Replace `science graph import` / `graph stamp-revision` / `graph migrate-addresses` mentions with the build-from-source guidance. Regenerate committed codex skills if they are generated (`generate_codex_skills`) so committed == generated.

- [ ] **Step 2: Run doc guards + full gate**

Run: `cd science && PYTHONPATH=src:model/src uv run --frozen pytest tests/test_command_docs.py tests/test_codex_skills.py -q` (expect PASS)
Then the full gate:
```bash
cd science && PYTHONPATH=src:model/src uv run --frozen pytest -q
cd science && PYTHONPATH=src:model/src uv run ruff check
cd science && PYTHONPATH=src:model/src uv run pyright
cd science/model && uv run --frozen pytest -q
```
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add commands codex-skills docs
git commit -m "docs(kernel-closure): repoint graph-writer guidance to source authoring (Phase 3a)"
```

---

## Self-Review Notes (coverage against the design)

- Guard RED→GREEN: Task 1 (RED) → Task 12 (GREEN). ✓ (§10)
- Generic `_retired_writer` + relaxed Click validation: Tasks 3, 6. ✓ (§6.1, §6.2)
- Forward-path templates (packaged + mirror + reconciliation gate): Task 2. ✓ (§7)
- Function deletion + dead helpers + re-export prune: Task 12. ✓ (§6.3, §6.4)
- Test disposition = migrate source-emitted / delete mutator-only-with-pointer: Tasks 5-11 apply the §5.1 table. ✓ (§8)
- Deferred mutators (article/falsification/story/paper) untouched: Global Constraints + Tasks 6, 7, 9. ✓ (§3)
- Docs/skills sweep: Task 13. ✓ (§9)
- No "byte-identical" claim; success = no source-built consumer regression: reflected in Task 12 gate + this plan's Architecture. ✓ (§2, §11)
- External-importer preflight (§6.5): the product surface is the `science` CLI, not the package; Task 12 Step 3 (ruff) plus the full suite catch any internal consumer. If a `~/d/science-commons` / `meta/` grep for the 14 names is desired before Task 12, run it as a pre-check — expected clean.
