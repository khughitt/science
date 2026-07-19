# Specs and Plans as First-Class Entities (S3a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `spec` a creatable, importable, supersedable, curation-visible core entity kind so design docs and implementation plans become first-class entities via the already-shipped `science entities import` engine.

**Architecture:** Four of the five tasks are declarative or documentation changes. Task 1 fleshes out the `spec` `EntityKind` descriptor and wires `spec → spec` supersession in `science-model` core (the only behavioral change). Tasks 2, 4 are guard tests that lock in the resulting behavior the shipped importer/rotation/materialize engines already provide once the descriptor exists. Task 3 removes a now-redundant validate-check constant. Task 5 documents the write-then-import interception in the AGENTS template and user guide. `spec` deliberately stays annotation-only in `_ANNOTATION_REF_PREFIXES` — turning on `spec:*` reference resolution and the id-remap migration is deferred to S3b and is out of scope here.

**Tech Stack:** Python `>=3.11`, Pydantic (science-model profiles), pytest, click, rdflib (graph materialization).

**Design doc:** `docs/plans/2026-07-18-specs-plans-as-entities-design.md`

## Global Constraints

Every task's requirements implicitly include this section.

- **Branch:** all work lands on `specs-plans-as-entities-s3a` (already created off local `main`; the design doc is already committed there as `32bd7acf`).
- **Never `git add science/uv.lock`.** It carries a Dropbox 0.3.0↔0.4.1 drift; each commit step lists exact paths — stage only those.
- **Test commands:** toolkit tests run from `science/` (`cd science && uv run --frozen pytest ...`); model tests run from `science/model/` (`cd science/model && uv run --frozen pytest ...`). Default pytest excludes the `snapshot` and `real_projects` markers.
- **No AI-attribution trailers** on commits (no `Co-Authored-By`, no "Generated with Claude Code").
- **In docs/code use `~/d/`**, never `/home/keith/d/` or `/mnt/ssd/Dropbox/`.
- Composition > inheritance; explicit > defensive; fail early / no silent fallbacks; no "legacy"/"compatibility" layers; no `Unified` prefix.
- **Do NOT grow `_KNOWN_HALF_WIRED`** in `science/model/tests/test_supersedable_gate.py`. `spec` becomes supersedable by *wiring the `spec → spec` endpoint pair*, not by adding it to the frozen debt allowlist.
- **Canonical `spec` descriptor values (exact):** `home="entities/specs"`, `strategy="numeric"`, `default_status="active"`, `statuses=["draft", "active", "complete", "superseded", "retired", "archived"]` (same lifecycle vocabulary as `plan`).
- **A created/imported `spec` id is `spec:0001-<slug>`** — the slug is part of the numeric local part (`LOCAL_PART_WIDTH == 4`), and the file lands at `entities/specs/0001-<slug>.md`.
- **S3a KEEPS `spec` in `_ANNOTATION_REF_PREFIXES`** (`science/src/science_tool/graph/sources.py`). Removing it (turning on `spec:*` metadata-reference resolution) plus the id-remap migration is S3b — explicitly NOT in this plan.
- `spec` has no packaged template and `template_ready` stays unset (parity with `plan`); `science entity create spec` uses the templateless frontmatter path.

---

### Task 1: Flesh out the `spec` kind and wire `spec → spec` supersession (science-model)

The four descriptor fields and the supersession wiring are one atomic change: the canonical `statuses` vocabulary includes `superseded`, which places `spec` in the supersedable gate's `declares` set (`test_every_supersedable_kind_can_author_the_CANONICAL_edge`). That gate then requires `spec` to be an admissible `sci:supersedes` endpoint, so the descriptor fields and the relation wiring must land together or the model suite goes red.

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py` (the `EntityKind(name="spec", …)` block at ~line 504; the `RelationKind(name="supersedes", …)` block at ~line 719)
- Create: `science/model/tests/test_spec_kind.py`
- Modify: `science/model/tests/test_supersedable_gate.py` (add two tests at end of file)
- Modify: `science/tests/test_kind_map_equivalence.py` (add `spec` entries to `FROZEN_MARKDOWN_POLICIES`, `FROZEN_DEFAULT_STATUS`, `FROZEN_STATUS_VALUES`)

**Interfaces:**
- Consumes: `science_model.profiles.core.CORE_PROFILE`; `science_model.relations.relation_allows_kinds`; `science_model.profiles.schema.RelationEndpointPair` (already imported in `core.py`).
- Produces: the `spec` `EntityKind` now exposes `home="entities/specs"`, `strategy="numeric"`, `default_status="active"`, and the six-status vocabulary; `relation_allows_kinds(supersedes, "spec", "spec")` is `True`. Downstream tasks rely on `resolve_path_policy("spec")` succeeding and on `_DEFAULT_STATUS["spec"] == "active"` (both derived from these descriptor fields in `science_tool.entities`).

**Why this task spans two packages:** the live `science_tool.entities` maps `_BUILTIN_MARKDOWN_POLICIES`, `_DEFAULT_STATUS`, and `_STATUS_VALUES` are all derived from `CORE_PROFILE`. `science/tests/test_kind_map_equivalence.py` freezes value-for-value copies of them and asserts equality, so adding the `spec` descriptor fields makes three of its tests go red unless the frozen copies get matching `spec` entries. The re-freeze is legitimate: that file's own guidance says re-freezing a golden is allowed precisely when the change it records is the point of the commit — and adding `spec` is the point here.

- [ ] **Step 1: Write the failing descriptor test**

Create `science/model/tests/test_spec_kind.py`:

```python
from __future__ import annotations

from science_model.profiles.core import CORE_PROFILE


def _spec_kind():
    return next(k for k in CORE_PROFILE.entity_kinds if k.name == "spec")


def test_spec_kind_is_import_ready() -> None:
    spec = _spec_kind()
    assert spec.home == "entities/specs"
    assert spec.strategy == "numeric"
    assert spec.default_status == "active"
    assert spec.statuses == ["draft", "active", "complete", "superseded", "retired", "archived"]
```

- [ ] **Step 2: Run the descriptor test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_spec_kind.py -v`
Expected: FAIL — `spec.home` is `None` (the stub has no `home`/`strategy`/`default_status`/`statuses`).

- [ ] **Step 3: Write the failing supersedes-endpoint tests**

Append to `science/model/tests/test_supersedable_gate.py`:

```python
def test_spec_is_a_supersedes_ENDPOINT() -> None:
    # `spec` declares a `superseded` terminal (same lifecycle vocabulary as `plan`), so it must be an
    # admissible `sci:supersedes` endpoint or the derived gate above reports it newly half-wired.
    assert relation_allows_kinds(_supersedes(), "spec", "spec")


def test_supersedes_description_names_spec_replacement() -> None:
    # The descriptor prose is part of the contract: a reader of the relation must learn that spec
    # replacement is valid, not only that spec appears in the endpoint lists.
    assert "spec" in _supersedes().description.lower()
```

- [ ] **Step 4: Run the endpoint tests to verify they fail**

Run: `cd science/model && uv run --frozen pytest tests/test_supersedable_gate.py -v`
Expected: FAIL — `test_spec_is_a_supersedes_ENDPOINT` fails (`spec` not an allowed pair) and `test_supersedes_description_names_spec_replacement` fails (description does not mention spec). Note: `test_every_supersedable_kind_can_author_the_CANONICAL_edge` will ALSO fail once Step 5's descriptor edit adds `superseded` to `spec.statuses` without the wiring — Step 5 lands both halves together.

- [ ] **Step 5: Add the four descriptor fields to the `spec` `EntityKind`**

In `science/model/src/science_model/profiles/core.py`, replace the `spec` block (currently):

```python
        EntityKind(
            name="spec",
            canonical_prefix="spec",
            layer="layer/core",
            description="A design or implementation specification.",
            entity_class=EntityClass.OPERATIONAL,
            curation_scope=CurationScope.CORRESPONDENCE,
            category=KindCategory.AUTHORED_CORE,
        ),
```

with:

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
            # Same lifecycle vocabulary as `plan`: a spec's status IS a document lifecycle
            # (drafted before active, superseded when replaced). This is NOT a claim of
            # kind-certification -- only `hypothesis` is kind-certified, and the S4 drift
            # screen remains plan-only. `superseded` here requires the `spec -> spec`
            # `sci:supersedes` pair below, or the D4 supersedable gate goes red.
            statuses=["draft", "active", "complete", "superseded", "retired", "archived"],
        ),
```

- [ ] **Step 6: Wire the `spec → spec` supersedes endpoint**

In the same file, in the `RelationKind(name="supersedes", …)` block, add `"spec"` to both endpoint lists, add the pair, amend the description, and update the debt comment. Replace:

```python
            source_kinds=["workflow-run", "hypothesis", *_CONCLUSION_KINDS],
            target_kinds=["workflow-run", "hypothesis", *_CONCLUSION_KINDS],
            allowed_kind_pairs=[
                RelationEndpointPair(source_kind="workflow-run", target_kind="workflow-run"),
                RelationEndpointPair(source_kind="hypothesis", target_kind="hypothesis"),
                *_CONCLUSION_KIND_PAIRS,
            ],
            layer="layer/core",
            description=(
                "A newer entity replaces an older entity as canonical. Valid "
                "for workflow-run replacement, hypothesis replacement, and "
                "conclusion-level replacement."
            ),
```

with:

```python
            source_kinds=["workflow-run", "hypothesis", "spec", *_CONCLUSION_KINDS],
            target_kinds=["workflow-run", "hypothesis", "spec", *_CONCLUSION_KINDS],
            allowed_kind_pairs=[
                RelationEndpointPair(source_kind="workflow-run", target_kind="workflow-run"),
                RelationEndpointPair(source_kind="hypothesis", target_kind="hypothesis"),
                RelationEndpointPair(source_kind="spec", target_kind="spec"),
                *_CONCLUSION_KIND_PAIRS,
            ],
            layer="layer/core",
            description=(
                "A newer entity replaces an older entity as canonical. Valid "
                "for workflow-run replacement, hypothesis replacement, spec "
                "replacement, and conclusion-level replacement."
            ),
```

Also fix the stale `HYPOTHESIS ONLY` heading on that comment. It names only `hypothesis`, yet `workflow-run` is equally a fully wired, repairable endpoint in the same block -- the "ONLY" was already wrong before S3a and is more wrong once `spec` joins. Replace the heading line:

```python
            # HYPOTHESIS ONLY. Twelve other kinds are half-wired the same way (decision, inquiry,
```

with wording that names both already-wired endpoints explicitly:

```python
            # WORKFLOW-RUN AND HYPOTHESIS are fully wired here (each a repairable endpoint); `spec`
            # joins them via the line below. Twelve other kinds are half-wired the same way (decision, inquiry,
```

Leave the twelve-kind list on the following comment lines as-is (those remain frozen debt); `spec` was never in it and is now a fully wired endpoint (`spec → spec`), so no edit to the twelve-kind list is required. Then add one line directly above `source_kinds` to record the new pair:

```python
            # `spec` is fully wired here (spec -> spec) as part of S3a -- it is NOT frozen debt.
            source_kinds=["workflow-run", "hypothesis", "spec", *_CONCLUSION_KINDS],
```

- [ ] **Step 7: Run the full model suite to verify green**

Run: `cd science/model && uv run --frozen pytest`
Expected: PASS — `test_spec_kind.py` passes, both new supersedable-gate tests pass, and `test_every_supersedable_kind_can_author_the_CANONICAL_edge` stays green (`spec` is in `declares` AND allowed, so it is not in `broken`).

- [ ] **Step 8: Add the `spec` entries to the frozen tool-map golden**

In `science/tests/test_kind_map_equivalence.py`, add a `spec` entry to each of the three frozen dicts so the live `CORE_PROFILE`-derived maps still equal them. Add to `FROZEN_MARKDOWN_POLICIES` (e.g. directly after the `"plan"` entry):

```python
    "spec": EntityPathPolicy(Path("entities/specs"), "numeric"),
```

Add to `FROZEN_DEFAULT_STATUS` (e.g. after the `"plan"` entry):

```python
    "spec": "active",
```

Add to `FROZEN_STATUS_VALUES` (e.g. after the `"plan"` entry) — the same vocabulary as `plan`/`report`:

```python
    "spec": frozenset({"draft", "active", "complete", "superseded", "retired", "archived"}),
```

`FROZEN_KIND_CLASSES` already contains `"spec": "operational"` (the kind's `entity_class` was always `OPERATIONAL`), and `FROZEN_MIGRATED_KINDS` correctly omits `spec` (no packaged template) — leave both unchanged.

- [ ] **Step 9: Run the frozen-map equivalence test to verify green**

Run: `cd science && uv run --frozen pytest tests/test_kind_map_equivalence.py -v`
Expected: PASS — `test_markdown_policies_equal_prior_literal`, `test_default_status_equals_prior_literal`, and `test_status_values_equal_prior_literal` all green with the new `spec` entries.

- [ ] **Step 10: Commit**

```bash
cd ~/d/science
git add science/model/src/science_model/profiles/core.py \
        science/model/tests/test_spec_kind.py \
        science/model/tests/test_supersedable_gate.py \
        science/tests/test_kind_map_equivalence.py
git commit -m "feat(model): make spec a first-class supersedable kind"
```

---

### Task 2: Guard `spec` create / import / rotation / review (toolkit)

The importer, rotation, and review engines already ship. Task 1 unlocked them for `spec` by giving the kind a path policy and a non-`none` curation scope. This task adds guard tests that lock in that unlocked behavior — the concrete evidence for the design's zero-breakage claim. Each test in this task PASSES because Task 1 landed and FAILS if Task 1 is reverted (`resolve_path_policy("spec")` would raise). No `src/` change is expected.

**Files:**
- Create: `science/tests/test_spec_entity_s3a.py`

**Interfaces:**
- Consumes: `science_tool.entities.create_entity`; `science_tool.entity_import.plan_import` / `apply_import`; `science_tool.curate.rotation.eligible_corpus`; `science_tool.entity_review.review_entity`; the `science entities import` CLI via `science_tool.cli.main`.
- Produces: nothing new for later tasks (leaf guard task).

- [ ] **Step 1: Write the create + import guard tests**

Create `science/tests/test_spec_entity_s3a.py`:

```python
# science/tests/test_spec_entity_s3a.py
"""S3a guards: `spec` is creatable, importable, and enters the S2 curation loop.

Each test here would FAIL before the science-model descriptor change (Task 1):
`resolve_path_policy("spec")` raises `Unsupported source-authored entity kind: spec`
until the kind has a home/strategy. They lock in the zero-breakage claim.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.entities import create_entity
from science_tool.entity_import import apply_import, plan_import


def _project(root: Path) -> Path:
    # Create the project in a SUBDIRECTORY of tmp_path so callers can save the import
    # plan under tmp_path itself — i.e. OUTSIDE the project root, as the design requires.
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text(
        "name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8"
    )
    return root


def _loose(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_science_entity_create_spec_writes_under_entities_specs(tmp_path: Path) -> None:
    root = _project(tmp_path / "project")

    create_entity(root, "spec", "My Design Doc")

    dest = root / "entities" / "specs" / "0001-my-design-doc.md"
    assert dest.is_file()
    frontmatter, _body = _split(dest.read_text(encoding="utf-8"))
    assert frontmatter["id"] == "spec:0001-my-design-doc"
    assert frontmatter["kind"] == "spec"
    assert frontmatter["status"] == "active"


def test_plan_import_spec_proposes_numeric_id_and_home(tmp_path: Path) -> None:
    root = _project(tmp_path / "project")
    source = _loose(root, "docs/loose.md", "# My Spec\n\nbody\n")

    plan = plan_import(root, source, kind="spec")

    assert plan.entity_id == "spec:0001-my-spec"
    assert plan.dest_rel == "entities/specs/0001-my-spec.md"
    assert plan.status == "active"


def _split(text: str) -> tuple[dict, str]:
    assert text.startswith("---\n")
    _, fm, body = text.split("---\n", 2)
    return yaml.safe_load(fm), body
```

- [ ] **Step 2: Run the create + import guard tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_spec_entity_s3a.py -v`
Expected: PASS. (These assertions are non-vacuous by construction: before Task 1, `resolve_path_policy("spec")` raises `Unsupported source-authored entity kind: spec`, so both `create_entity` and `plan_import` would raise here.)

- [ ] **Step 3: Add the CLI round-trip test (exact link rewrite + manual hit asserted through the CLI JSON)**

Append to `science/tests/test_spec_entity_s3a.py`. This single test proves the whole public contract through the CLI: the preview reports the prose mention as a manual hit in its JSON, apply lands the spec and moves the source, and the structured markdown link is rewritten to the exact new relative path.

```python
def test_cli_import_spec_roundtrip_rewrites_link_and_reports_manual_hit(tmp_path: Path) -> None:
    import json

    from click.testing import CliRunner

    from science_tool.cli import main

    root = _project(tmp_path / "project")
    source = _loose(root, "docs/loose.md", "# My Spec\n\nbody\n")

    # A structured referrer: a markdown link to the loose doc gets repointed on apply.
    referrer = root / "entities" / "questions" / "0001-ref.md"
    referrer.parent.mkdir(parents=True, exist_ok=True)
    referrer.write_text(
        "---\nid: question:0001-ref\nkind: question\ntitle: Ref\nstatus: active\n"
        "related: []\nsource_refs: []\n---\n\nSee [design](../../docs/loose.md).\n",
        encoding="utf-8",
    )

    # A prose-only path mention: reported as a manual hit, never rewritten.
    (root / "notes.md").write_text("The design lives at docs/loose.md for now.\n", encoding="utf-8")

    plan_path = tmp_path / "p.json"  # OUTSIDE the project tree (tmp_path is root's parent)
    runner = CliRunner()

    preview = runner.invoke(
        main,
        ["entities", "import", str(source), "--kind", "spec",
         "--project-root", str(root), "--save-plan", str(plan_path)],
    )
    assert preview.exit_code == 0, preview.output

    # The preview JSON surfaces the prose mention as a manual hit.
    preview_payload = json.loads(preview.output)
    manual_files = {hit["rel_path"] for hit in preview_payload["ref_report"]["manual"]}
    assert "notes.md" in manual_files

    apply = runner.invoke(
        main,
        ["entities", "import", "--apply-plan", str(plan_path), "--project-root", str(root)],
    )
    assert apply.exit_code == 0, apply.output

    # The spec entity landed; the loose source is gone.
    assert (root / "entities" / "specs" / "0001-my-spec.md").is_file()
    assert not source.exists()

    # The structured markdown link was rewritten to the exact new relative path.
    assert "[design](../specs/0001-my-spec.md)" in referrer.read_text(encoding="utf-8")
    assert "docs/loose.md" not in referrer.read_text(encoding="utf-8")
```

`RewriteReport.manual` (serialized under `ref_report.manual` in the CLI JSON) is a
list of `ManualHit` objects with fields `rel_path`, `line`, `text`; `ref_report.hits`
(`RefHit`, field `surface`) is the list of repointed structured references.

- [ ] **Step 4: Run the round-trip test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_spec_entity_s3a.py::test_cli_import_spec_roundtrip_rewrites_link_and_reports_manual_hit -v`
Expected: PASS — the spec lands at `entities/specs/0001-my-spec.md`, the CLI preview JSON reports `notes.md` as a manual hit, and the markdown link is rewritten to `../specs/0001-my-spec.md`.

- [ ] **Step 5: Add the rotation + review curation-loop tests**

Append to `science/tests/test_spec_entity_s3a.py`:

```python
def test_created_spec_enters_eligible_corpus(tmp_path: Path) -> None:
    from science_tool.curate.rotation import eligible_corpus

    root = _project(tmp_path / "project")
    create_entity(root, "spec", "My Design Doc")

    ids = {e.id for e in eligible_corpus(root)}
    assert "spec:0001-my-design-doc" in ids


def test_review_entity_stamps_last_reviewed_on_an_imported_spec(tmp_path: Path) -> None:
    # The design requires exercising the curation loop on an IMPORTED spec, not only a
    # created one: import + apply first, then review the resulting entity id.
    from datetime import date

    from science_tool.entity_import import apply_import
    from science_tool.entity_review import review_entity

    root = _project(tmp_path / "project")
    source = _loose(root, "docs/loose.md", "# My Spec\n\nbody\n")
    plan = plan_import(root, source, kind="spec")
    apply_import(root, plan)

    path, changed = review_entity(
        root, plan.entity_id, note="Read; no change.", today=date(2026, 7, 18)
    )

    assert changed is True
    frontmatter, _body = _split(path.read_text(encoding="utf-8"))
    assert frontmatter["review_state"]["last_reviewed"] == "2026-07-18"
    assert frontmatter["review_state"]["last_review_note"] == "Read; no change."
```

- [ ] **Step 6: Run the full new test file to verify green**

Run: `cd science && uv run --frozen pytest tests/test_spec_entity_s3a.py -v`
Expected: PASS — all create/import/round-trip/rotation/review guards green.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science
git add science/tests/test_spec_entity_s3a.py
git commit -m "test(spec): guard create/import/rotation/review for spec entities"
```

---

### Task 3: Remove the redundant `_EXTRA_PREFIX_KINDS` fallback (toolkit)

Once `spec` has a policy (Task 1), it enters `markdown_entity_kinds()` alongside `concept` and `dataset` — which were already policy kinds despite the stale comment claiming otherwise. Every member of `_EXTRA_PREFIX_KINDS` is now redundant, so the constant is removed and `prefix_rules()` derives solely from the policy table. The all-policy-kinds test becomes the sole authority guard; the retain-nonpolicy test loses its premise and is deleted.

**Files:**
- Modify: `science/src/science_tool/validate/checks/id_prefixes.py` (remove `_EXTRA_PREFIX_KINDS` at ~line 102–114)
- Modify: `science/tests/validate/test_checks_id_prefixes.py` (delete `test_prefix_rules_retain_nonpolicy_kinds` at ~line 154–163)

**Interfaces:**
- Consumes: `science_tool.entities.markdown_entity_kinds`.
- Produces: `prefix_rules()` unchanged in output (still covers `concept`, `dataset`, `spec` via the policy table); `PREFIX_RULES` module constant unchanged in shape.

- [ ] **Step 1: Update the coverage test to prove spec is covered via the policy table**

Confirm `test_prefix_rules_cover_every_markdown_kind` already asserts every `markdown_entity_kinds()` member has a rule (it does). Add an explicit spec assertion so the intent is legible. In `science/tests/validate/test_checks_id_prefixes.py`, replace `test_prefix_rules_cover_every_markdown_kind` with:

```python
def test_prefix_rules_cover_every_markdown_kind() -> None:
    from science_tool.entities import markdown_entity_kinds
    from science_tool.validate.checks.id_prefixes import prefix_rules

    rules = prefix_rules()
    kinds = set(markdown_entity_kinds())
    assert "spec" in kinds, "spec must be a policy kind (needs a home/strategy)"
    for kind in kinds:
        if kind in {"research-question", "claim-registry"}:
            continue  # singletons validated elsewhere
        assert rules.get(kind) == f"{kind}:", f"{kind} missing/incorrect prefix rule"
```

- [ ] **Step 2: Run it to verify it passes (spec already in the policy table after Task 1)**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_id_prefixes.py::test_prefix_rules_cover_every_markdown_kind -v`
Expected: PASS — Task 1 put `spec` in `markdown_entity_kinds()`, and `prefix_rules()` still unions it in via the (soon-to-be-removed) `_EXTRA_PREFIX_KINDS` today, so this is green before and after the Step 3 removal.

- [ ] **Step 3: Delete the retain-nonpolicy test**

In `science/tests/validate/test_checks_id_prefixes.py`, delete the entire `test_prefix_rules_retain_nonpolicy_kinds` function:

```python
def test_prefix_rules_retain_nonpolicy_kinds() -> None:
    # Regression guard: deriving rules from the policy table must NOT drop
    # non-policy kinds the static PREFIX_RULES used to cover. `concept` and
    # `dataset` are not markdown entity kinds (absent from the policy table)
    # but still carry typed `concept:`/`dataset:` ids that need conformance.
    from science_tool.validate.checks.id_prefixes import prefix_rules

    rules = prefix_rules()
    for kind in ("concept", "dataset", "spec"):
        assert rules.get(kind) == f"{kind}:", f"{kind} prefix rule was dropped"
```

(Its premise — that `concept`/`dataset` are "absent from the policy table" — is false at runtime, and after Step 4 there is no non-policy fallback set for it to guard.)

- [ ] **Step 4: Remove `_EXTRA_PREFIX_KINDS` and derive `prefix_rules()` from the policy table only**

In `science/src/science_tool/validate/checks/id_prefixes.py`, replace the constant and `prefix_rules()`:

```python
# Reference/operational kinds NOT governed by the markdown policy table but
# still subject to id-prefix conformance. These must be every kind the static
# PREFIX_RULES covered that is absent from _BUILTIN_MARKDOWN_POLICIES -- today
# that is concept, dataset, and spec. (paper IS in the policy table, so it is
# intentionally NOT listed here.) Dropping any of these silently reduces
# validation coverage in repos with concept:/dataset:/spec: records.
_EXTRA_PREFIX_KINDS = ("concept", "dataset", "spec")


def prefix_rules() -> dict[str, str]:
    kinds = set(markdown_entity_kinds()) | set(_EXTRA_PREFIX_KINDS)
    kinds -= {"research-question", "claim-registry"}  # singletons
    return {kind: f"{kind}:" for kind in sorted(kinds)}
```

with:

```python
def prefix_rules() -> dict[str, str]:
    # Every id-prefixed kind is a markdown policy kind: concept, dataset, and (as of
    # S3a) spec all carry a home/strategy and appear in markdown_entity_kinds(). There
    # is no non-policy fallback set -- the policy table is the single authority.
    kinds = set(markdown_entity_kinds())
    kinds -= {"research-question", "claim-registry"}  # singletons
    return {kind: f"{kind}:" for kind in sorted(kinds)}
```

- [ ] **Step 5: Run the id-prefix check suite to verify green**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_id_prefixes.py -v`
Expected: PASS — coverage test green; retain test gone; no reference to `_EXTRA_PREFIX_KINDS` remains.

- [ ] **Step 6: Confirm no other importer of the removed constant**

Run: `cd science && rg -n "_EXTRA_PREFIX_KINDS" src/ tests/`
Expected: no matches.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/validate/checks/id_prefixes.py \
        science/tests/validate/test_checks_id_prefixes.py
git commit -m "refactor(validate): derive id-prefix rules from the policy table alone"
```

---

### Task 4: Graph-materialization guard for `spec` (toolkit)

Prove the design's corrected graph-boundary claim concretely: a `spec` entity materializes as a graph node, a wired `spec → spec` supersedes edge materializes (bypassing the annotation filter), and ordinary `spec:` metadata references stay annotation-only in S3a. Also refresh the now-stale `sources.py` comment that calls spec pointers "not first-class entities."

**Files:**
- Create: `science/tests/test_spec_materialization.py`
- Modify: `science/src/science_tool/graph/sources.py` (comment above `_ANNOTATION_REF_PREFIXES` at ~line 800–806, and the `is_metadata_reference` docstring at ~line 809 — comment-only; the frozenset itself does NOT change)

**Interfaces:**
- Consumes: the `build_entity_graph` conftest helper; `science_tool.graph.store` (`PROJECT_NS`, `SCI_NS`, `_graph_uri`, `_load_dataset`). The annotation-only behavior of `science_tool.graph.sources.is_metadata_reference` is exercised indirectly, through `_add_relations` at materialization — the test asserts edge absence, not the predicate directly.
- Produces: nothing new for later tasks (leaf guard task).

- [ ] **Step 1: Write the node + supersedes-edge materialization test**

Create `science/tests/test_spec_materialization.py`:

```python
# science/tests/test_spec_materialization.py
"""S3a graph guards: a spec materializes as a node and a wired spec->spec supersedes
edge materializes, while ordinary spec: metadata references stay annotation-only."""
from __future__ import annotations

import sys
from pathlib import Path

if "conftest" in sys.modules and not hasattr(sys.modules["conftest"], "build_entity_graph"):
    del sys.modules["conftest"]
from conftest import build_entity_graph
from rdflib.namespace import RDF

from science_tool.graph.store import PROJECT_NS, SCI_NS, _graph_uri, _load_dataset


def _spec_entity(local_part: str, title: str):
    frontmatter = {"title": title, "status": "active", "related": [], "source_refs": []}
    return {"kind": "spec", "id": local_part, "frontmatter": frontmatter, "body": f"{title}\n"}


def test_spec_entity_materializes_as_a_graph_node(tmp_path: Path) -> None:
    graph_path = build_entity_graph(tmp_path, [_spec_entity("0001-design", "Design")])

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    spec_uri = PROJECT_NS["spec/0001-design"]

    assert (spec_uri, RDF.type, SCI_NS.Spec) in knowledge


def test_spec_to_spec_supersedes_edge_materializes(tmp_path: Path) -> None:
    graph_path = build_entity_graph(
        tmp_path,
        [_spec_entity("0001-old", "Old"), _spec_entity("0002-new", "New")],
        relations=[
            {"subject": "spec:0002-new", "predicate": "sci:supersedes", "object": "spec:0001-old"}
        ],
    )

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    new_uri = PROJECT_NS["spec/0002-new"]
    old_uri = PROJECT_NS["spec/0001-old"]

    assert (new_uri, SCI_NS.supersedes, old_uri) in knowledge


def test_ordinary_spec_metadata_reference_produces_no_edge(tmp_path: Path) -> None:
    # S3a KEEPS spec in _ANNOTATION_REF_PREFIXES: a `spec:` pointer in an ordinary
    # metadata field (`related`) is skipped by `_add_relations` (via is_metadata_reference),
    # so NO edge from the referrer to the spec is materialized -- even though the spec
    # target exists as a node. Turning that resolution on is S3b.
    question = {
        "kind": "question",
        "id": "0001-ask",
        "frontmatter": {
            "title": "Ask",
            "status": "active",
            "related": ["spec:0001-design"],  # existing spec target, but annotation-only
            "source_refs": [],
        },
        "body": "Ask\n",
    }
    graph_path = build_entity_graph(
        tmp_path, [_spec_entity("0001-design", "Design"), question]
    )

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    question_uri = PROJECT_NS["question/0001-ask"]
    spec_uri = PROJECT_NS["spec/0001-design"]

    # The spec node exists on its own...
    assert (spec_uri, RDF.type, SCI_NS.Spec) in knowledge
    # ...but the metadata `related` pointer produced no edge to it (any predicate).
    assert list(knowledge.triples((question_uri, None, spec_uri))) == []
```

- [ ] **Step 2: Run the materialization tests to verify pass/fail state**

Run: `cd science && uv run --frozen pytest tests/test_spec_materialization.py -v`
Expected: `test_spec_entity_materializes_as_a_graph_node` PASS; `test_ordinary_spec_metadata_reference_produces_no_edge` PASS (the spec node exists, but the `related: ["spec:0001-design"]` pointer is skipped by `is_metadata_reference` in `_add_relations`, so no question→spec edge); `test_spec_to_spec_supersedes_edge_materializes` PASS (Task 1 wired the pair — without it, `admit_authored_relation` raises `ValueError` for a forbidden endpoint pair, which is the exact behavior the pair wiring fixes).

- [ ] **Step 3: Refresh the stale `sources.py` comment (comment-only)**

In `science/src/science_tool/graph/sources.py`, update the comment block above `_ANNOTATION_REF_PREFIXES` and the `is_metadata_reference` docstring so they no longer assert that `spec:` pointers are "not first-class entities" (false as of S3a). Replace:

```python
# Annotation-only reference namespaces: pointers an author keeps in source files
# (e.g. `meta:<phase>` process tags, `spec:<design-doc>` pointers to design
# documents that are not first-class entities) that are intentionally NOT
# materialized as KG edges and require no resolvable entity.
_ANNOTATION_REF_PREFIXES = frozenset({"meta", "spec"})


def is_metadata_reference(raw: str) -> bool:
    """Return True for annotation-only refs (`meta:*`, `spec:*`).

    These are intentional annotations preserved in source files but excluded
    from KG materialization (no entity required, no edge created). `spec:` joins
    `meta:` because design-spec pointers reference plain design documents, not
    first-class entities.
```

with:

```python
# Annotation-only reference namespaces: pointer FIELDS an author keeps in source
# files (e.g. `meta:<phase>` process tags, `spec:<design-doc>` pointers) whose
# individual metadata-reference edges are intentionally NOT materialized and
# require no resolvable target. As of S3a `spec` is a first-class entity kind, so
# a spec FILE materializes as a node and an authored `spec -> spec` supersedes
# edge materializes; only ordinary `spec:` metadata-reference fields stay
# suppressed here. Removing `spec` (turning that resolution on) is S3b.
_ANNOTATION_REF_PREFIXES = frozenset({"meta", "spec"})


def is_metadata_reference(raw: str) -> bool:
    """Return True for annotation-only refs (`meta:*`, `spec:*`).

    These are intentional annotations preserved in source files but excluded from
    KG materialization at the metadata-reference edge level (no target required,
    no edge created). `spec:` stays here in S3a even though `spec` is now a
    first-class kind: its ordinary pointer fields remain annotation-only until
    S3b turns `spec:*` reference resolution on.
```

- [ ] **Step 4: Re-run the materialization tests and a sources smoke check**

Run: `cd science && uv run --frozen pytest tests/test_spec_materialization.py -v`
Expected: PASS (comment change is inert).
Run: `cd science && uv run --frozen pytest tests/graph -q`
Expected: PASS — no graph regression from the comment edit.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/tests/test_spec_materialization.py \
        science/src/science_tool/graph/sources.py
git commit -m "test(graph): guard spec node + spec->spec supersedes materialization"
```

---

### Task 5: AGENTS-template interception + user-guide docs + command-doc test (Component 4)

Document the write-then-import interception that overrides the superpowers `brainstorming`/`writing-plans` default of writing-and-committing a loose design doc: author into a project-local staging file (uncommitted), preview, inspect manual hits, apply, then commit the canonical entity. Add the interception section to the AGENTS template (reaches newly scaffolded/imported projects only) and to the user guide's "Source Entity CLI" section, and protect the new copy with a `test_command_docs.py` assertion.

**Files:**
- Modify: `templates/agents-md.md` (add a "Design docs and plans" section)
- Modify: `docs/user-guide/entities.md` (add an "Importing loose design docs and plans" subsection under "Source Entity CLI", after the wrapper table at ~line 107)
- Modify: `science/tests/test_command_docs.py` (add one test)

**Interfaces:**
- Consumes: `science_tool` test harness `_read(path)` helper in `test_command_docs.py` (reads repo-root-relative files).
- Produces: nothing for later tasks (final task).

- [ ] **Step 1: Write the failing command-doc test**

Append to `science/tests/test_command_docs.py`:

```python
def test_agents_template_and_guide_document_import_interception_in_sequence() -> None:
    # Both surfaces must carry the full write-then-import sequence IN ORDER:
    # save-plan preview -> inspect the manual-hit list -> apply-plan -> commit the
    # canonical entity. Order matters: it is the interception's whole contract.
    sequence = ["--save-plan", "manual-hit", "--apply-plan", "commit the canonical entity"]

    def _in_order(text: str, tokens: list[str], where: str) -> None:
        idx = -1
        for tok in tokens:
            nxt = text.find(tok, idx + 1)
            assert nxt > idx, f"{where}: token missing or out of order: {tok!r}"
            idx = nxt

    for path in ("templates/agents-md.md", "docs/user-guide/entities.md"):
        text = _read(path).lower()
        assert "science entities import" in text, path
        _in_order(text, sequence, path)

    # Surface-specific anchors.
    template = _read("templates/agents-md.md")
    assert "staging file" in template
    assert "not committed" in template
    assert "existing adopters" in _read("docs/user-guide/entities.md").lower()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_command_docs.py::test_agents_template_and_guide_document_import_interception_in_sequence -v`
Expected: FAIL — neither doc mentions the import interception yet.

- [ ] **Step 3: Add the interception section to the AGENTS template**

In `templates/agents-md.md`, add a new section immediately after the `## Task execution` section (before `## Known issues / nuances`):

```markdown
## Design docs and plans

Design docs and implementation plans are first-class `spec` / `plan` entities in
this project. When a brainstorming or planning skill would write a design doc or
plan, do NOT commit the loose file — import it so it gains a canonical id and an
`entities/` home:

1. Author the doc as a project-local **staging file** (e.g. `docs/_staging/x.md`,
   no frontmatter). This staging file is **not committed**.
2. Preview: `science entities import docs/_staging/x.md --kind spec --save-plan /tmp/p.json`
   (use `--kind plan` for implementation plans). **Inspect the manual-hit list** in
   the preview — plain prose/code path mentions are reported, not auto-repointed.
3. Apply: `science entities import --apply-plan /tmp/p.json`, then delete the plan file.
4. **Commit the canonical entity** at `entities/specs/NNNN-slug.md` (or
   `entities/plans/NNNN-slug.md`), not the staging file — the staging file is moved
   away by apply.

This overrides any skill default that writes and commits the loose design doc.
```

- [ ] **Step 4: Add the import subsection to the user guide**

In `docs/user-guide/entities.md`, add a new subsection under "Source Entity CLI", after the typed-wrappers table (before `### CLI Path And Identity Policy`). The block below is wrapped in a **four-backtick** outer fence so its inner ```` ```bash ```` fences render — paste the inner content (from `### Importing…` onward) into the guide:

````markdown
### Importing Loose Design Docs And Plans

`science entities import` turns a loose Markdown document into a canonical entity:
it proposes a numeric id, stamps frontmatter, relocates the file under the kind's
home, and repoints structured references (frontmatter reference fields and Markdown
links). Plain prose or code path mentions are reported separately and never rewritten.

Preview the import read-only and save the plan outside the project tree:

```bash
science entities import docs/_staging/my-design.md --kind spec --save-plan /tmp/p.json
```

**Inspect the manual-hit list** in the preview before applying — those prose/code path
mentions are not auto-repointed. Then apply the saved plan:

```bash
science entities import --apply-plan /tmp/p.json
```

Finally, **commit the canonical entity** at `entities/specs/NNNN-slug.md` (or
`entities/plans/NNNN-slug.md`), not the staging file. The source must live inside the
project root; the saved plan (`/tmp/p.json`) lives outside the project tree, since a
stale plan file is itself a scannable reference artifact. Use `--kind spec` for design
docs and `--kind plan` for implementation plans. This keeps design docs and plans
first-class: author a staging file, import it, then commit the canonical entity rather
than the loose file. Newly scaffolded or imported projects carry this in their
`AGENTS.md`; **existing adopters need a manual AGENTS.md update** to adopt it.
````

- [ ] **Step 5: Run the command-doc test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_command_docs.py::test_agents_template_and_guide_document_import_interception_in_sequence -v`
Expected: PASS.

- [ ] **Step 6: Run the full command-doc suite to confirm no regression**

Run: `cd science && uv run --frozen pytest tests/test_command_docs.py -q`
Expected: PASS — in particular `test_agents_template_recommends_nested_worktrees_and_local_overlay` and `test_active_tooling_docs_drop_relative_editable_workarounds` still pass (the new AGENTS section adds no retired tokens and no `--no-verify`).

- [ ] **Step 7: Commit**

```bash
cd ~/d/science
git add templates/agents-md.md docs/user-guide/entities.md science/tests/test_command_docs.py
git commit -m "docs(entities): document spec/plan write-then-import interception"
```

---

## Final Verification

After all tasks, run both suites and the linters:

```bash
cd ~/d/science/science && uv run --frozen pytest
cd ~/d/science/science/model && uv run --frozen pytest
cd ~/d/science/science && uv run ruff check && uv run pyright
```

Expected: all green. The working tree is **not** expected to be pristine: `science/uv.lock`
is intentionally left modified-but-unstaged (the Dropbox 0.3.0↔0.4.1 drift — never stage it),
and untracked scratch under `.worktrees/` belongs to other sessions. Confirm `git status`
shows the five S3a commits on `specs-plans-as-entities-s3a`, `science/uv.lock` as the only
modified tracked file, and nothing staged beyond those commits.

## Self-Review Notes (coverage against the design)

- Component 1 (flesh out `spec`) → Task 1 Steps 1–2, 5.
- Component 2 (wire `spec → spec` supersession, amend description, don't grow debt) → Task 1 Steps 3–4, 6; endpoint + description tests.
- Frozen tool-map goldens (`FROZEN_MARKDOWN_POLICIES`/`FROZEN_DEFAULT_STATUS`/`FROZEN_STATUS_VALUES`) updated for `spec` so the equivalence guard stays green → Task 1 Steps 8–9.
- Component 3 (remove `_EXTRA_PREFIX_KINDS`, delete retain test, coverage test as authority) → Task 3.
- Component 4 (AGENTS-template interception incl. commit-timing override; existing-adopters note; ordered-sequence command-doc test on both surfaces) → Task 5.
- Testing/Model (four fields, endpoint True, gate green, description mentions spec) → Task 1.
- Testing/Toolkit (create under `entities/specs/`, import id `spec:0001-<slug>`, CLI round-trip with exact link rewrite + manual hit asserted in the CLI JSON, `eligible_corpus`, `review_entity` stamps an **imported** spec) → Task 2.
- Testing/Graph (spec node materializes, spec→spec supersedes edge materializes, ordinary `spec:` metadata ref produces no edge) → Task 4.
- Zero-breakage: Tasks 2 and 4 are guard tests that pass only because Task 1 unlocked the shipped engines; `spec` stays in `_ANNOTATION_REF_PREFIXES` (Task 4 asserts it via edge absence). S3b (reference resolution + id-remap migration) is explicitly out of scope.
