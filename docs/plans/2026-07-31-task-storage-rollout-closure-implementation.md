# Task-storage Rollout Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct bracket handling, overlay provenance, and revision-manifest source coverage in the shared toolkit; make workflow-run provenance durable; transactionally migrate all 13 registered legacy task stores without changing their task sets; close 15 local graphs; and refresh the 14 affected composites.

**Architecture:** The parser and overlay corrections are already public and remain immutable. A third toolkit prerequisite extends the revision manifest over the five omitted project-local loader surfaces and excludes the transient task lock. cBioPortal and post-acute-infection narrowly track the 16 workflow-run manifests their graphs consume while result payloads remain ignored. Every task-migration target, post-acute-infection, and multiple-myeloma pins the final public SHA. Cross-checkout graph parity compares named-graph quads excluding only `REVISION_URI`; same-checkout no-change rebuilds retain byte parity. Composite graphs are rebuilt only after all 15 local graphs are current, preserving peer named-graph context, authored peer lists, and default Commons behavior.

**Tech Stack:** Python 3.13, Click, Pydantic `Task`, PyYAML, RDFLib, uv, pytest, Ruff, Pyright, Git worktrees, jq, yq.

## Global Constraints

- Make authored and commit-bound changes only in `.worktrees/task-storage-rollout-closure`. The explicit Task 8C primary graph rebuild is a read-through diagnostic that may rewrite only the generated graph; preserve evidence and restore it as specified.
- Use `~/d/` paths in documentation and commands; do not write machine-specific absolute checkout roots into tracked files.
- Treat checked-in `uv.lock` files as authoritative and run `uv sync --frozen` in every worktree before invoking Science.
- The final toolkit prerequisite must be reachable from `origin/main` before any remaining consumer lock names it.
- Do not push any consumer repository. Local `main` merges are authorized; consumer remote publication is not.
- Do not change `~/.config/science/config.yaml`, any `science.yaml` peer list, or default Commons behavior. Never substitute `--no-commons` after a Commons failure.
- Every graph-diff capture, including baselines, must use `--output`; stdout is capped at 40 rows.
- Keep validation exit statuses and stderr. Exit 0 or 1 is admissible for strict validation; exit 2, a traceback, or a new unrelated finding delta stops the project.
- Map every newly activated finding family to a named pre-migration `validate.check-error`; any unexplained validation delta stops the project.
- A local graph must contain zero `schema:identifier` values matching an absolute `/.../overlays/...` path. Checking only for `.worktrees/` is insufficient.
- Cross-checkout graph comparisons use a sorted named-graph quad projection that excludes only the `graph_revision` subject. Do not use raw graph bytes across checkouts.
- cBioPortal and post-acute-infection must track every discovered `results/**/datapackage.json` while all non-manifest result payloads remain ignored.
- Relative overlay source URIs are project-local. Composite verification must preserve the peer project named graph as their qualifier; never certify them from a flattened union.
- The transactional migrator is the only task-store writer. Do not manually finish a partial migration, delete its journal, or copy task files between projects.
- No permanent rollout helper belongs in the toolkit or consumers. The two audit helpers in Task 3 live only under `/tmp/task-storage-rollout-closure/`.
- Do not run test suites concurrently in the toolkit worktree.
- Do not add compatibility modes, feature flags, new dependencies, or `Co-Authored-By` trailers.

## File and rollout map

Toolkit files changed by the prerequisite:

- `science/src/science_tool/tasks.py` — remove the unsupported closing-bracket title restriction at the two shared boundaries.
- `science/tests/test_tasks_dsl_roundtrip.py` — prove aggregate/ledger bracketed-title round trips.
- `science/tests/test_task_file_format.py` — prove a leading bracket survives YAML frontmatter rendering and parsing; retain multiline rejection.
- `science/tests/test_migrate_storage.py` — prove bracketed titles in done ledgers do not refuse migration.
- `science/tests/validate/test_checks_tasks.py` — replace the closing-bracket invalid-title fixture with a still-invalid whitespace title.
- `docs/plans/2026-07-26-context-budget-slice3-storage-design.md` — correct the two false claims about `]` ambiguity.
- `docs/audits/downstream-project-conventions/synthesis.md` — mark its aggregate-task convention as a dated historical observation.
- `skills/generated/science-command-preamble/references/docs/audits/downstream-project-conventions/synthesis.md` — regenerated mirror, never hand-edited independently.
- `science/src/science_tool/graph/materialize.py` — normalize absolute project-local overlay filenames to contained project-relative POSIX identifiers at emit time.
- `science/tests/test_graph_materialize.py` — prove relative overlay provenance and fail-early containment while retaining absolute loader state.
- `science/tests/test_graph_composite.py` — prove identical relative overlay source URIs remain distinct by peer named-graph context.
- `science/src/science_tool/graph/io.py` — include the five omitted project-local loader surfaces in the revision manifest and exclude `tasks/.tasks.lock` plus exact Marimo session JSON leaves.
- `science/src/science_tool/graph/storage_adapters/datapackage.py` — expose the existing entity-profile eligibility predicate for manifest discovery, if the implementation needs it; do not duplicate profile parsing.
- `science/tests/test_graph_io_revision_manifest.py` — prove complete source-family coverage, payload exclusion, task-lock exclusion, and workflow-manifest drift detection.
- `docs/plans/2026-07-31-task-storage-rollout-closure-design.md` — record the approved overlay-provenance amendment.
- `docs/plans/2026-07-31-task-storage-rollout-closure-implementation.md` — sequence the corrective release and staged repins.

Consumer migration matrix:

| Task | Project root | Active | Pin | Live docs | Composite |
|---:|---|---:|---|---|---|
| 4 | `~/d/cancer/data-sources/cbioportal` | 74 | parser, overlay, then final SHA | none | yes |
| 5 | `~/d/health/comparisons/pan-disease` | 58 | parser SHA; final in Task 9 | `AGENTS.md`, `README.md` | yes |
| 10 | `~/d/cancer/meta` | 11 | final SHA | none | yes |
| 11 | `~/d/cancer/mechanisms/evolution` | 31 | final SHA | `AGENTS.md` | yes |
| 12 | `~/d/cancer/conditions/pre-cancer` | 6 | final SHA | none | yes |
| 13 | `~/d/cancer/cancer-types/ovarian` | 0 | final SHA | `AGENTS.md` | yes |
| 14 | `~/d/cancer/cancer-types/head-and-neck` | 0 | final SHA | `AGENTS.md` | yes |
| 15 | `~/d/cancer/cancer-types/prostate` | 0 | final SHA | `AGENTS.md` | yes |
| 16 | `~/d/cancer/cancer-types/breast` | 0 | final SHA | `AGENTS.md` | yes |
| 17 | `~/d/cancer/therapeutics` | 2 | final SHA | `AGENTS.md` | no |
| 18 | `~/d/health/meta` | 32 | final SHA | `AGENTS.md` | yes |
| 19 | `~/d/health/processes/cycles` | 53 | final SHA | `AGENTS.md` | yes |
| 20 | `~/d/health/processes/immunity` | 5 | final SHA | `AGENTS.md` | yes |
| 21 | `~/d/health/processes/post-acute-infection` | already split | final SHA | `AGENTS.md` | yes |
| 22 | `~/d/cancer/cancer-types/multiple-myeloma` | already split | final SHA | none | yes |

Tasks 4 and 5 are complete migration commits on local `main`. Task 8's cBioPortal overlay correction is also complete at `2e7dd121`; Task 8C adds the final pin and durable workflow manifests. Task 9 has not started. Cancer/meta's Task 10 resumes its uncommitted migrated worktree after replacing the intermediate pin and tainted graph. Multiple-myeloma's historical `tasks/active.md` citations remain unchanged. `~/d/cancer/therapeutics` has no composite.

**Execution state and order:** Tasks 1-8 are complete, including publication of `36463540` and cBioPortal's local overlay commit. After independent review, stage only these two plan documents, run `git diff --cached --check`, and commit `docs: close graph source reproducibility gap` before Task 8A so its code commit starts from a clean branch. Then execute Tasks 8A-8C and Tasks 9-25 numerically. The completed Task 4-8 records remain as history and are not rerun.

---

### Task 1: Correct and publish-test the shared parser behavior

**Files:**
- Modify: `science/src/science_tool/tasks.py:170-205`
- Modify: `science/tests/test_tasks_dsl_roundtrip.py:54`
- Modify: `science/tests/test_task_file_format.py:252-270`
- Modify: `science/tests/test_migrate_storage.py:219-236`
- Modify: `science/tests/validate/test_checks_tasks.py:296-302`
- Modify: `docs/plans/2026-07-26-context-budget-slice3-storage-design.md:136-145,646-649`
- Modify: `docs/audits/downstream-project-conventions/synthesis.md:1-10`
- Regenerate: `skills/generated/science-command-preamble/references/docs/audits/downstream-project-conventions/synthesis.md`

**Interfaces:**
- Consumes: `_HEADER_RE = ^##\s+\[(tNNN)\]\s+(.+)$`, `render_task_file(Task) -> str`, and `plan_migration(Path, today=date) -> MigrationPlan`.
- Produces: every valid single-line `Task.title`, including `]`, is accepted by aggregate, split-frontmatter, create, edit, validation, and migration paths; aggregate titles pass through the shared validator after normalization, and existing newline/edge-whitespace rules remain.

- [ ] **Step 1: Replace the false bracket-rejection tests with acceptance regressions**

In `test_tasks_dsl_roundtrip.py`, replace `test_rejects_newline_in_title_via_header` with:

```python
@pytest.mark.parametrize(
    "title",
    ["F10 [Significant] result", "Evidence [UNVERIFIED]"],
)
def test_bracketed_title_roundtrips_through_ledger(title: str) -> None:
    task = Task(id="t014", title=title, status="done", created=date(2026, 3, 1))

    assert _roundtrip(task).title == title


def test_rejects_blank_title_via_header() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        _parse_task_block(["## [t015]    ", "- created: 2026-03-01", "", "x"])
```

In `test_task_file_format.py`, remove `"contains ] bracket"` from `test_rejects_non_single_line_title`, leaving the newline case, and add:

```python
def test_leading_bracket_title_roundtrips_through_frontmatter(tmp_path: Path) -> None:
    task = Task(
        id="t042",
        title="[UNVERIFIED] source classification",
        status="active",
        created=date(2026, 7, 20),
    )
    rendered = task_module.render_task_file(task)
    path = _write(tmp_path / "t042-unverified-source-classification.md", rendered)

    assert "title: '[UNVERIFIED] source classification'" in rendered
    assert task_module.parse_task_file(path) == task
```

Replace `test_plan_refuses_invalid_source_title` in `test_migrate_storage.py` with:

```python
def test_plan_accepts_bracketed_titles_in_done_ledgers(tmp_path: Path) -> None:
    migrate = _migrate_module()
    tasks_dir = tmp_path / "tasks"
    active = _task("t001", "Current work")
    completed = [
        _task("t072", "F10 [Significant] result", status="done", completed=TODAY),
        _task("t106", "Evidence [UNVERIFIED]", status="done", completed=TODAY),
    ]
    _write_legacy(tasks_dir, [active])
    done_dir = tasks_dir / "done"
    done_dir.mkdir()
    done_dir.joinpath("2026-07.md").write_text(
        "\n".join(render_task(task) for task in completed),
        encoding="utf-8",
    )

    plan = migrate.plan_migration(tasks_dir, today=TODAY)

    assert plan.refusals == []
    assert [entry.task.id for entry in plan.entries] == ["t001"]
```

In `test_checks_tasks.py`, change the `title: Bad]` invalid fixture to `title: " leading"` and retain its expected canonical title error.

- [ ] **Step 2: Run the focused tests and confirm the old predicates fail**

Run from `science/`:

```bash
uv run --frozen pytest -q \
  tests/test_tasks_dsl_roundtrip.py::test_bracketed_title_roundtrips_through_ledger \
  tests/test_tasks_dsl_roundtrip.py::test_rejects_blank_title_via_header \
  tests/test_task_file_format.py::test_leading_bracket_title_roundtrips_through_frontmatter \
  tests/test_migrate_storage.py::test_plan_accepts_bracketed_titles_in_done_ledgers \
  tests/validate/test_checks_tasks.py
```

Expected: bracket acceptance fails on the `]` restriction, the blank aggregate-title test fails because no shared title validation runs there yet, and the replacement frontmatter whitespace fixture remains green.

- [ ] **Step 3: Remove the two unsupported predicates and correct the error text**

In `_parse_task_header`, replace the dedicated `]` branch with the shared validation call after title normalization:

```python
task_id, title = match.group(1), match.group(2).strip()
_validate_task_title(title)
return task_id, title
```

In `_validate_task_title`, remove only `or "]" in title` and change the message to:

```python
"task title must be non-empty, have no leading or trailing whitespace, and be single-line"
```

Do not change `_HEADER_RE`, `_ANY_TASK_HEADER_RE`, or the splitline-boundary checks.

- [ ] **Step 4: Correct the originating design and supersede the shipped audit claim**

At both cited locations in the 2026-07-26 storage design, state that newline boundaries are rejected but `]` is valid because `_HEADER_RE` consumes the bounded `[tNNN]` ID before capturing the title remainder.

After the audit metadata, add:

```markdown
> **Superseded note (2026-07-31):** This audit records the task layout observed
> on 2026-04-25. The current active-task store is `tasks/active/`, with one
> Markdown file per open task; `tasks/done/YYYY-MM.md` remains the closed-task
> ledger. Use `science tasks` rather than treating the aggregate `active.md`
> observations below as current operating guidance.
```

- [ ] **Step 5: Regenerate the shipped agent distributions**

Run from `science/`:

```bash
uv run --frozen science agents generate
```

Confirm the generated synthesis contains the same superseded note and no other generated file changed unexpectedly.

- [ ] **Step 6: Run focused parser, migration, validation, and generation tests**

Run from `science/`:

```bash
uv run --frozen pytest -q \
  tests/test_tasks_dsl_roundtrip.py \
  tests/test_task_file_format.py \
  tests/test_migrate_storage.py \
  tests/validate/test_checks_tasks.py \
  tests/test_agent_assets.py::test_committed_agent_distributions_match_generation
```

Expected: PASS, including all existing fail-closed migration tests and multiline-title cases.

- [ ] **Step 7: Lint the changed Python files and inspect the complete diff**

Run from `science/`:

```bash
uv run --frozen ruff check \
  src/science_tool/tasks.py \
  tests/test_tasks_dsl_roundtrip.py \
  tests/test_task_file_format.py \
  tests/test_migrate_storage.py \
  tests/validate/test_checks_tasks.py
git diff --check
git diff --stat
git diff
```

Expected: no lint or whitespace errors; the production change is only two predicate removals plus one message correction.

- [ ] **Step 8: Commit the atomic toolkit prerequisite**

```bash
git add \
  science/src/science_tool/tasks.py \
  science/tests/test_tasks_dsl_roundtrip.py \
  science/tests/test_task_file_format.py \
  science/tests/test_migrate_storage.py \
  science/tests/validate/test_checks_tasks.py \
  docs/plans/2026-07-26-context-budget-slice3-storage-design.md \
  docs/audits/downstream-project-conventions/synthesis.md \
  skills/generated/science-command-preamble/references/docs/audits/downstream-project-conventions/synthesis.md
git commit -m "fix(tasks): allow brackets in task titles"
```

### Task 2: Verify, merge, and publish the toolkit prerequisite

**Files:** None beyond Task 1.

**Interfaces:**
- Consumes: clean branch `task-storage-rollout-closure` with Task 1 committed.
- Produces: the already-published parser SHA stored at `/tmp/task-storage-rollout-closure/toolkit-sha.txt`; completed Tasks 4-5 consumed that exact revision. All remaining migrations consume the later corrective SHA from Task 7.

- [ ] **Step 1: Run the toolkit release gate**

Run serially from `science/` and allow the full suite roughly ten minutes:

```bash
uv run --frozen ruff check
uv run --frozen pyright
uv run --frozen pytest
```

Expected: all three pass. Do not publish after a scoped-only test run.

- [ ] **Step 2: Reconfirm clean ancestry immediately before merge**

```bash
git status --short
git fetch origin
git merge-base --is-ancestor origin/main task-storage-rollout-closure
test "$(git rev-list --count task-storage-rollout-closure..origin/main)" -eq 0
test "$(git rev-list --count origin/main..task-storage-rollout-closure)" -gt 0
```

Expected: clean worktree, origin has no commit absent from the rollout branch, and the branch has unpublished commits.

- [ ] **Step 3: Fast-forward local main and push it**

```bash
git -C ~/d/science status --short --branch
git -C ~/d/science merge --ff-only task-storage-rollout-closure
git -C ~/d/science push origin main
```

Expected: the primary checkout was clean on `main`, the merge is fast-forward only, and the push succeeds.

- [ ] **Step 4: Prove the exact SHA is publicly resolvable**

```bash
mkdir -p /tmp/task-storage-rollout-closure
git -C ~/d/science rev-parse HEAD | tee /tmp/task-storage-rollout-closure/toolkit-sha.txt
test "$(wc -c < /tmp/task-storage-rollout-closure/toolkit-sha.txt)" -eq 41
test "$(git -C ~/d/science rev-parse HEAD)" = "$(git -C ~/d/science ls-remote origin refs/heads/main | cut -f1)"
```

Expected: the local SHA, recorded SHA, and public `origin/main` SHA are identical.

### Task 3: Prepare temporary parity evidence tools

**Files:**
- Create temporarily: `/tmp/task-storage-rollout-closure/snapshot_tasks.py`
- Create temporarily: `/tmp/task-storage-rollout-closure/project_task_graph.py`
- Create evidence: `/tmp/task-storage-rollout-closure/registry.sha256`

**Interfaces:**
- Consumes: the installed `science_tool` and `science_model` packages in each consumer worktree.
- Produces: `snapshot_tasks.py PROJECT_ROOT OUTPUT_JSON`, whose output is a stable complete task structure plus done-ledger SHA-256 values; `project_task_graph.py GRAPH_TRIG OUTPUT_JSON`, whose output is the sorted task-subject domain triples excluding source provenance.

- [ ] **Step 1: Record the registry before any consumer mutation**

```bash
sha256sum ~/.config/science/config.yaml | tee /tmp/task-storage-rollout-closure/registry.sha256
```

- [ ] **Step 2: Create the task snapshot helper with the patch tool**

Create exactly:

```python
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from science_tool.tasks import parse_task_file, parse_tasks


root = Path(sys.argv[1])
output = Path(sys.argv[2])
tasks_dir = root / "tasks"
legacy = tasks_dir / "active.md"
split = tasks_dir / "active"

if legacy.is_file():
    active = parse_tasks(legacy)
elif split.is_dir():
    active = [parse_task_file(path) for path in sorted(split.glob("*.md"))]
else:
    active = []

done = []
for path in sorted((tasks_dir / "done").glob("*.md")):
    raw = path.read_bytes()
    done.append(
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "tasks": [task.model_dump(mode="json") for task in parse_tasks(path)],
        }
    )

payload = {
    "active": sorted(
        (task.model_dump(mode="json") for task in active),
        key=lambda row: row["id"],
    ),
    "done": done,
}
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
```

- [ ] **Step 3: Create the task-domain graph projection helper with the patch tool**

Create exactly:

```python
from __future__ import annotations

import json
import sys
from pathlib import Path

from rdflib import Dataset, Namespace, RDF


graph_path = Path(sys.argv[1])
output = Path(sys.argv[2])
science = Namespace("http://example.org/science/vocab/")
prov = Namespace("http://www.w3.org/ns/prov#")
dataset = Dataset()
dataset.parse(graph_path, format="trig")
task_subjects = {
    subject
    for subject, _, _, _ in dataset.quads((None, RDF.type, science.Task, None))
}
triples = sorted(
    (subject.n3(), predicate.n3(), obj.n3())
    for subject, predicate, obj, _ in dataset.quads((None, None, None, None))
    if subject in task_subjects and predicate != prov.wasDerivedFrom
)
output.write_text(json.dumps(triples, indent=2) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Smoke-test both helpers against the already-split toolkit meta project**

Run from `~/d/science/meta`:

```bash
uv run --frozen python /tmp/task-storage-rollout-closure/snapshot_tasks.py \
  . /tmp/task-storage-rollout-closure/science-meta-tasks.json
uv run --frozen python /tmp/task-storage-rollout-closure/project_task_graph.py \
  knowledge/graph.trig /tmp/task-storage-rollout-closure/science-meta-task-graph.json
jq -e '.active | type == "array"' /tmp/task-storage-rollout-closure/science-meta-tasks.json
jq -e 'type == "array"' /tmp/task-storage-rollout-closure/science-meta-task-graph.json
```

Expected: both helpers exit zero. Do not add either helper to Git.

### Task 6: Normalize project-local overlay provenance at graph emission

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py:330-385`
- Modify: `science/tests/test_graph_materialize.py:400-505`
- Modify: `science/tests/test_graph_composite.py:1-115`

**Interfaces:**
- Consumes: `ProjectSources.project_root: str`, `ProjectSources.commons_overlay_paths: dict[str, str]`, `_emit_phase(ProjectSources) -> EmitResult`, and composite peer named graphs `cancer://<project-id>`.
- Produces: `_relative_overlay_paths(sources: ProjectSources) -> dict[str, str]`; graph-emitted overlay paths are contained project-relative POSIX strings while `ProjectSources.commons_overlay_paths` remains absolute; duplicate relative overlay source URIs remain qualified by peer named graph.

- [ ] **Step 1: Write the failing graph-emission regressions**

In `test_materialize_with_commons_topic_emits_scope_and_dual_provenance`, retain the absolute Commons canonical identifier but replace the overlay expectation with:

```python
assert derived_source_identifiers == {
    str(commons_root / "topics" / "single-cell-foundation-models.md"),
    "overlays/topics/single-cell-foundation-models.md",
}
```

Add a focused containment test using the existing `ProjectSources`, `KnowledgeProfiles`, and `EntityRegistry` constructors:

```python
def test_relative_overlay_paths_rejects_path_outside_project_root(tmp_path: Path) -> None:
    from science_tool.graph.entity_registry import EntityRegistry
    from science_tool.graph.materialize import _relative_overlay_paths
    from science_tool.graph.sources import KnowledgeProfiles, ProjectSources

    project_root = tmp_path / "project"
    project_root.mkdir()
    sources = ProjectSources(
        project_name="demo",
        project_root=str(project_root),
        profiles=KnowledgeProfiles(),
        entities=[],
        registry=EntityRegistry.with_core_types(),
        commons_overlay_paths={"topic:x": str(tmp_path / "outside.md")},
    )

    with pytest.raises(ValueError, match="outside project root"):
        _relative_overlay_paths(sources)
```

- [ ] **Step 2: Run the focused tests and require the intended failures**

```bash
cd science
uv run --frozen pytest \
  tests/test_graph_materialize.py::test_materialize_with_commons_topic_emits_scope_and_dual_provenance \
  tests/test_graph_materialize.py::test_relative_overlay_paths_rejects_path_outside_project_root -q
```

Expected: the materialization assertion still sees an absolute overlay identifier and the helper import fails because it does not exist.

- [ ] **Step 3: Implement the single emission-boundary normalizer**

Add beside `_emit_phase`:

```python
def _relative_overlay_paths(sources: ProjectSources) -> dict[str, str]:
    project_root = Path(sources.project_root).resolve()
    relative: dict[str, str] = {}
    for canonical_id, raw_path in sources.commons_overlay_paths.items():
        overlay_path = Path(raw_path).resolve()
        try:
            path = overlay_path.relative_to(project_root)
        except ValueError as exc:
            raise ValueError(
                f"overlay path {overlay_path} is outside project root {project_root}"
            ) from exc
        relative[canonical_id] = path.as_posix()
    return relative
```

In `_emit_phase`, compute once before the entity loop and pass only the normalized mapping to `_add_entity`:

```python
overlay_paths = _relative_overlay_paths(sources)
for entity in sources.entities:
    _add_entity(
        entity=entity,
        knowledge=knowledge,
        provenance=provenance,
        overlay_paths=overlay_paths,
        reference_only_ids=reference_only_ids,
    )
```

Do not change `ProjectSources`, `SourceRef`, arbitration, `OverlayAdapter`, `_source_uri`, or `_add_entity`.

- [ ] **Step 4: Prove loader state remains absolute and graph state becomes relative**

```bash
cd science
uv run --frozen pytest \
  tests/test_graph_sources.py \
  tests/test_graph_commons_sources.py::test_load_project_sources_populates_overlay_paths \
  tests/test_graph_commons_mm30_canary.py::test_canary_overlay_and_inbound_ref_share_single_entity \
  tests/test_graph_materialize.py::test_materialize_with_commons_topic_emits_scope_and_dual_provenance \
  tests/test_graph_materialize.py::test_relative_overlay_paths_rejects_path_outside_project_root -q
```

Expected: PASS. The three source-loading assertions remain absolute; only persisted overlay provenance is relative.

- [ ] **Step 5: Pin the composite named-graph qualifier**

In `test_graph_composite.py`, import `Literal` and `SCHEMA_NS`, add the same source node to both peer local graphs, assemble, and assert two graph contexts:

```python
def test_composite_qualifies_same_overlay_source_uri_by_peer_graph(tmp_path: Path) -> None:
    host = tmp_path / "host"
    peer_a = tmp_path / "peer-a"
    peer_b = tmp_path / "peer-b"
    _write_project(host, "host", [("peer-a", peer_a), ("peer-b", peer_b)])
    _write_project(peer_a, "peer-a")
    _write_project(peer_b, "peer-b")
    _write_local_graph(host, "host")

    source = URIRef("http://example.org/project/source/overlays_papers_shared.md")
    identifier = Literal("overlays/papers/shared.md")
    for root, project_id in ((peer_a, "peer-a"), (peer_b, "peer-b")):
        _write_local_graph(root, project_id)
        path = root / "knowledge" / "graph.trig"
        dataset = _load_dataset(path)
        dataset.graph(URIRef(f"https://example.org/{project_id}/graph/provenance")).add(
            (source, SCHEMA_NS.identifier, identifier)
        )
        dataset.serialize(destination=path, format="trig")

    composite = _load_dataset(assemble_composite_graph(host))
    contexts = {
        str(graph)
        for _, _, _, graph in composite.quads((source, SCHEMA_NS.identifier, identifier, None))
    }

    assert contexts == {"cancer://peer-a", "cancer://peer-b"}
```

Run:

```bash
cd science
uv run --frozen pytest tests/test_graph_composite.py -q
```

Expected: PASS before and after the normalizer because this test pins the existing composite qualifier contract rather than changing assembly.

- [ ] **Step 6: Run focused lint, types, and tests**

```bash
cd science
uv run --frozen ruff check src/science_tool/graph/materialize.py \
  tests/test_graph_materialize.py tests/test_graph_composite.py
uv run --frozen pyright
uv run --frozen pytest tests/test_graph_materialize.py \
  tests/test_graph_sources.py tests/test_graph_commons_sources.py \
  tests/test_graph_commons_mm30_canary.py tests/test_graph_composite.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit the correction**

```bash
git add science/src/science_tool/graph/materialize.py \
  science/tests/test_graph_materialize.py science/tests/test_graph_composite.py
git diff --cached --check
git commit -m "fix(graph): stabilize overlay provenance"
```

### Task 7: Reconcile, release-test, and publish the corrective toolkit revision

**Files:** no new files; validates and publishes the Task 6 commit plus the approved design/plan commits.

**Interfaces:**
- Consumes: Task 6's reviewed commit, local toolkit `main`, and public `origin/main` at parser SHA `ba0b0cb0304aff03159ebc37c188839cfd4b1515`.
- Produces: `/tmp/task-storage-rollout-closure/corrective-toolkit-sha.txt`, a 40-character commit reachable from `origin/main` and containing both parser and overlay corrections.

- [ ] **Step 1: Reconfirm ancestry and inspect the clean merge**

```bash
git status --short
git -C ~/d/science status --short
git -C ~/d/science rev-list --left-right --count origin/main...main
git merge-tree "$(git merge-base HEAD main)" HEAD main > \
  /tmp/task-storage-rollout-closure/corrective-merge-tree.txt
! rg -n '^<<<<<<<|^=======$|^>>>>>>>' \
  /tmp/task-storage-rollout-closure/corrective-merge-tree.txt
```

Expected at final amendment review: clean worktrees and `0 28`, with local `main` at `f2fe585e`; if either branch advanced, fetch and repeat the overlap audit before rebasing.

- [ ] **Step 2: Rebase the unpublished rollout branch onto local main**

```bash
git rebase main
git status --short
```

Expected: clean rebase. Record the rewritten design/plan and Task 6 SHAs in the SDD ledger.

- [ ] **Step 3: Run the complete toolkit release gate**

```bash
cd science
uv run --frozen ruff check
uv run --frozen pyright
uv run --frozen pytest
```

Expected: all commands PASS. The pytest run is foreground with a long timeout and no concurrent suite.

- [ ] **Step 4: Fast-forward local main and publish**

```bash
git -C ~/d/science merge --ff-only task-storage-rollout-closure
git -C ~/d/science push origin main
git -C ~/d/science rev-parse HEAD | \
  tee /tmp/task-storage-rollout-closure/corrective-toolkit-sha.txt
test "$(tr -d '\n' < /tmp/task-storage-rollout-closure/corrective-toolkit-sha.txt | wc -c)" -eq 40
git -C ~/d/science ls-remote origin refs/heads/main | \
  tee /tmp/task-storage-rollout-closure/corrective-origin-main.txt
test "$(tr -d '\n' < \
  /tmp/task-storage-rollout-closure/corrective-toolkit-sha.txt)" = \
  "$(cut -f1 /tmp/task-storage-rollout-closure/corrective-origin-main.txt)"
```

This is the only new toolkit push; consumer pushes remain forbidden.

### Task 8: Correct cBioPortal's pin and overlay provenance

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `knowledge/graph.trig` under `~/d/cancer/data-sources/cbioportal`.

**Interfaces:**
- Consumes: local migration commit `cbe00b6238dc50fc4898b0b38413e305258a0ffc`, its retained rollout worktree/evidence, and `corrective-toolkit-sha.txt`.
- Produces: the completed `2e7dd121` local-main overlay commit with unchanged 74-task snapshot, zero worktree graph diff, no absolute overlay source identifier, and the primary/worktree failure evidence consumed by Task 8A.

- [ ] **Step 1: Reopen the retained clean worktree and capture the corrective baseline**

Require the primary and rollout branches both equal `cbe00b6238dc50fc4898b0b38413e305258a0ffc` and are clean. Run `uv sync --frozen`, capture complete strict validation as `validate-before-corrective.json`, capture `peers-before-corrective.json`, compare a fresh task snapshot byte-for-byte with Task 4's `tasks-after.json`, and require exactly six absolute overlay source identifiers in the baseline graph.

- [ ] **Step 2: Replace only the Science pin and lock**

Use the patch tool to replace the literal parser SHA with the exact value from `corrective-toolkit-sha.txt`, then run:

```bash
uv lock --upgrade-package science --upgrade-package science-model
git diff -- pyproject.toml uv.lock
uv sync --frozen
rg -n "$(tr -d '\n' < /tmp/task-storage-rollout-closure/corrective-toolkit-sha.txt)" \
  pyproject.toml uv.lock
```

Stop if any non-Science package or source moves.

- [ ] **Step 3: Rebuild and enforce stable provenance**

```bash
uv run --frozen science graph build --local-only
uv run --frozen science graph validate
uv run --frozen science graph diff --format json \
  --output /tmp/task-storage-rollout-closure/cbioportal/local-graph-diff-corrective.json
jq -e '.rows | length == 0' \
  /tmp/task-storage-rollout-closure/cbioportal/local-graph-diff-corrective.json
test "$(rg -o 'schema:identifier "/[^"]*/overlays/[^"]*"' \
  knowledge/graph.trig | wc -l)" -eq 0
```

Create `task-graph-corrective.json` and require it byte-identical to Task 4's `task-graph-after.json`.

- [ ] **Step 4: Require validation/topology parity**

Capture `validate-after-corrective.json` and require its sorted `.results` byte-identical to `validate-before-corrective.json`. Capture `peers-after-corrective.json`, require peer identity, and verify `science.yaml` remains byte-identical to its Task 4 checksum.

- [ ] **Step 5: Commit and fast-forward local main without pushing**

```bash
git diff --check
git add pyproject.toml uv.lock knowledge/graph.trig
git diff --cached --check
git commit -m "fix(graph): stabilize overlay provenance"
git rev-parse HEAD | tee \
  /tmp/task-storage-rollout-closure/cbioportal/local-commit.txt
git -C ~/d/cancer/data-sources/cbioportal merge --ff-only task-storage-rollout-closure
```

Record the corrective commit and confirm the existing remote ref is unchanged.

- [x] **Step 6: Run the real primary/worktree canary and stop on the discovered source delta**

After the fast-forward, the primary rebuild was not byte-identical. Investigation proved that revision mtimes differ by checkout and that 11 ignored workflow manifests add 99 non-revision quads only in primary. Preserve the primary generated-graph modification and evidence; do not force parity or clean it until Task 8C.

### Task 8A: Close revision-manifest source coverage in the toolkit

**Files:**
- Modify: `science/src/science_tool/graph/io.py`
- Modify only if needed to share its existing predicate: `science/src/science_tool/graph/storage_adapters/datapackage.py`
- Modify: `science/tests/test_graph_io_revision_manifest.py`
- Create temporarily: `/tmp/task-storage-rollout-closure/semantic_graph.py`

**Interfaces:**
- Consumes: accepted design/plan amendment and public toolkit `main` at `364635402fcb64c3483684a39b6692eac325688e`.
- Produces: one reviewed toolkit commit whose manifest covers the five omitted project-local loader surfaces without walking result payloads, plus a reusable semantic-quad evidence helper.

- [ ] **Step 1: Create the semantic graph projection helper**

Use the patch tool to create `/tmp/task-storage-rollout-closure/semantic_graph.py`. It accepts `GRAPH_TRIG OUTPUT_JSON`, parses an RDFLib `Dataset`, drops only quads whose subject equals `http://example.org/project/graph_revision`, retains the named-graph identifier, sorts `(subject, predicate, object, graph)` strings, and writes indented JSON. Smoke-test it against cBioPortal's primary and retained worktree graphs; record the expected pre-fix inequality caused by the 11 absent workflow runs.

- [ ] **Step 2: Write the failing source-family and exclusion tests**

In `test_graph_io_revision_manifest.py`, seed one project containing:

- `research/packages/example.md`;
- `papers/references.bib`;
- valid entity-profile datapackages under both `data/` and `results/`;
- `results/run/datapackage.json` plus a sibling payload;
- one canonical overlay under `overlays/papers/`;
- `tasks/.tasks.lock`; and
- two declared code roots with one `code_excludes` match, including
  `code/notebooks/__marimo__/session/state.py.json` plus ordinary durable code
  files in both roots.

Assert that the five source families are represented by project-relative paths, the existing roots appear in `walked`, both declared code roots are covered, the configured code exclusion and sibling result payload are absent, both transient leaves are absent, and ordinary code files remain. Add a save/mutate/diff test proving that changing only the workflow-run manifest yields exactly that path as `hash_changed`. Run the new tests and require RED for the omitted families/current code-root/transient behavior, not fixture failure.

- [ ] **Step 3: Implement the minimum shared manifest repair**

Extend `build_input_manifest` with exact candidate scans for the five conventions in design §4.5. Replace the single `pp.code_dir` walk with all `pp.code_roots` and apply `pp.code_excludes` to code-root candidates, matching `CodeAdapter`. Reuse the existing markdown leaf policy and datapackage entity-profile predicate; if the latter is not independently callable, extract only that existing predicate and route `DatapackageAdapter.discover()` through it. Do not instantiate the full project loader, add a source registry, hash arbitrary files below `data/` or `results/`, or alter manifest schema 2. Add exactly `tasks/.tasks.lock` and `**/__marimo__/session/*.json` to `DEFAULT_REVISION_MANIFEST_EXCLUDES`.

- [ ] **Step 4: Run focused tests and static checks**

```bash
cd science
uv run --frozen pytest tests/test_graph_io_revision_manifest.py \
  tests/test_graph_cli.py tests/test_graph_materialize.py -q
uv run --frozen ruff check src/science_tool/graph/io.py \
  src/science_tool/graph/storage_adapters/datapackage.py \
  tests/test_graph_io_revision_manifest.py
uv run --frozen pyright
```

Expected: PASS. If `datapackage.py` was untouched, omit it from the Ruff path list and staged files.

- [ ] **Step 5: Mutate the workflow manifest test and prove the guard is live**

Temporarily remove the workflow-run candidate scan with the patch tool, rerun only the new workflow manifest tests, and require RED. Restore with the patch tool and require GREEN. Do not use copy/restore shell shortcuts.

- [ ] **Step 6: Review and commit the toolkit code**

Run the SDD spec-compliance and code-quality reviews against the exact diff. Fix all blockers, rerun Step 4, then stage only the code/tests and commit:

```bash
git add science/src/science_tool/graph/io.py \
  science/tests/test_graph_io_revision_manifest.py
git diff --cached --check
git commit -m "fix(graph): close revision manifest source coverage"
```

Add `science/src/science_tool/graph/storage_adapters/datapackage.py` only if Step 3 changed it.

### Task 8B: Release-test and publish the final toolkit prerequisite

**Files:** no new tracked files; validates and publishes the accepted amendment plus Task 8A.

**Interfaces:**
- Consumes: clean rollout branch with the reviewed docs and Task 8A code commit; public `origin/main` at `36463540` unless it advances.
- Produces: `/tmp/task-storage-rollout-closure/final-toolkit-sha.txt`, a 40-character commit reachable from `origin/main`.

- [ ] **Step 1: Reconfirm ancestry and overlap**

Require clean rollout and primary toolkit worktrees. Fetch, record `rev-list --left-right --count origin/main...main`, and inspect `merge-tree` for the rollout branch versus current local `main`. If either moved beyond `36463540`, rebase only after confirming no overlap with the manifest/doc files.

- [ ] **Step 2: Run the complete release gate**

```bash
cd science
uv run --frozen ruff check
uv run --frozen pyright
uv run --frozen pytest
```

Run the full suite alone with an explicit long timeout. Require PASS from all three commands.

- [ ] **Step 3: Fast-forward and publish**

```bash
git -C ~/d/science merge --ff-only task-storage-rollout-closure
git -C ~/d/science push origin main
git -C ~/d/science rev-parse HEAD | \
  tee /tmp/task-storage-rollout-closure/final-toolkit-sha.txt
test "$(tr -d '\n' < /tmp/task-storage-rollout-closure/final-toolkit-sha.txt | wc -c)" -eq 40
git -C ~/d/science ls-remote origin refs/heads/main | \
  tee /tmp/task-storage-rollout-closure/final-origin-main.txt
test "$(tr -d '\n' < /tmp/task-storage-rollout-closure/final-toolkit-sha.txt)" = \
  "$(cut -f1 /tmp/task-storage-rollout-closure/final-origin-main.txt)"
```

Consumer pushes remain forbidden.

### Task 8C: Make cBioPortal workflow provenance reproducible

**Files:** `.gitignore`, `pyproject.toml`, `uv.lock`, the 11 existing `results/**/datapackage.json` files, and `knowledge/graph.trig` under `~/d/cancer/data-sources/cbioportal`.

**Interfaces:**
- Consumes: clean retained rollout worktree at `2e7dd121fc82135ca17a5d3e636510ac9bc51c11`, final public toolkit SHA, and the primary checkout's one diagnostic `knowledge/graph.trig` modification.
- Produces: a local-main source-closure commit with 11 durable workflow-run manifests, ignored payloads, zero graph diff, and primary/worktree semantic parity.

- [ ] **Step 1: Preserve and verify the diagnostic primary state**

Use `git status --short --untracked-files=all` and require the primary checkout to contain exactly one modified `knowledge/graph.trig` and no other changes. Record its SHA-256, full status, semantic projection, and the previously measured `+99` non-revision workflow-run quad delta under cBioPortal's evidence directory. Require exactly 11 primary `results/**/datapackage.json` files and save their sorted relative-path/SHA-256 inventory.

- [ ] **Step 2: Admit only provenance manifests in the retained worktree**

Patch `.gitignore`, replacing `results/` with exactly:

```gitignore
results/**
!results/**/
!results/**/datapackage.json
!results/.gitkeep
```

Mechanically transfer the 11 audited JSON manifests from the primary checkout to the same relative paths in the rollout worktree, preserving bytes. Verify their path/hash inventory equals Step 1. Use `git check-ignore` to prove every manifest is visible while representative sibling payloads remain ignored. Require `git status` to show exactly `.gitignore` plus the 11 manifests before the pin moves.

- [ ] **Step 3: Pin the final prerequisite and relock only Science**

Replace `364635402fcb64c3483684a39b6692eac325688e` with the exact SHA from `final-toolkit-sha.txt`, run `uv lock --upgrade-package science --upgrade-package science-model`, require no unrelated package movement, run `uv sync --frozen`, and verify both installed Science packages resolve to the final SHA.

- [ ] **Step 4: Rebuild and certify closure**

Run local graph build/validate and complete graph diff; require zero rows. Require zero absolute overlay identifiers, exactly 11 workflow-run entities, unchanged task snapshot/task-domain projection, unchanged peers and `science.yaml`, and acceptable complete strict-validation parity. Compare the rebuilt worktree graph's semantic projection with the saved primary diagnostic projection and require byte-identical JSON.

- [ ] **Step 5: Commit the source closure**

Inspect the complete diff. Stage only `.gitignore`, the exact 11 manifests, `pyproject.toml`, `uv.lock`, and `knowledge/graph.trig`; run `git diff --cached --check`; obtain SDD spec/code reviews; and commit `fix(graph): make workflow provenance reproducible`. Do not push.

- [ ] **Step 6: Clean the known diagnostic artifact and fast-forward local main**

Reconfirm that the primary dirty graph's SHA-256 still equals Step 1 and no second path is dirty. The modification was created by this rollout and its evidence is preserved, so restore only `knowledge/graph.trig` to `HEAD`, require the primary clean, then fast-forward the rollout branch into local `main`.

- [ ] **Step 7: Run the real semantic parity canary**

From primary, synchronize and rebuild the local graph. Project both primary and retained-worktree graphs with `semantic_graph.py` and require identical JSON, zero absolute overlay identifiers, and 11 workflow-run entities in each. If the primary rebuild changes only revision metadata, preserve the diff evidence and restore only the generated graph to the committed artifact so primary ends clean. Any semantic delta stops the rollout.

### Task 9: Move pan-disease directly to the final prerequisite

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `knowledge/graph.trig` under `~/d/health/comparisons/pan-disease`.

**Interfaces:**
- Consumes: local migration commit `d15e64dfda60f7793f8d203e7df45c92a6535b85`, retained rollout evidence, and `final-toolkit-sha.txt`.
- Produces: a corrective local-main commit with unchanged 58-task snapshot, zero graph diff, stable relative overlay identifiers, validation identity, and no push.

- [ ] **Step 1: Capture the clean corrective baseline**

Require primary and rollout branches equal `d15e64dfda60f7793f8d203e7df45c92a6535b85`. Synchronize, capture complete strict validation/peers/config checks, require a fresh task snapshot byte-identical to Task 5's `tasks-after.json`, and require exactly 54 absolute overlay source identifiers in the baseline graph.

- [ ] **Step 2: Pin the final SHA and audit the Science-only relock**

Replace only the parser SHA with the exact final SHA, run `uv lock --upgrade-package science --upgrade-package science-model`, and apply the same dependency-diff, literal-SHA, installed-resolution, and `uv sync --frozen` gates as Task 8C.

- [ ] **Step 3: Rebuild and verify**

Run local graph build, graph validation, complete zero-row graph diff, absolute-overlay identifier rejection, task-domain projection parity against Task 5's `task-graph-after.json`, complete strict-validation result identity, peer identity, and `science.yaml` checksum identity.

- [ ] **Step 4: Commit and fast-forward locally**

```bash
git add pyproject.toml uv.lock knowledge/graph.trig
git diff --cached --check
git commit -m "fix(graph): stabilize overlay provenance"
git rev-parse HEAD | tee \
  /tmp/task-storage-rollout-closure/pan-disease/local-commit.txt
git -C ~/d/health/comparisons/pan-disease merge --ff-only task-storage-rollout-closure
```

Do not push. Retain the worktree for the health composite phase.

## Local migration protocol used historically by Tasks 4-5 and now by Tasks 10-20

Each task below supplies exact values for `PROJECT_ROOT`, `PROJECT_ID`, `EXPECTED_COUNT`, pin action, documentation files, and commit message. Execute this protocol inside that task; a failure stops that project before commit and before its local-main merge.

1. **Create the worktree.** With the task's exact `PROJECT_ROOT`, `PROJECT_ID`, and `EXPECTED_COUNT`, run:

   ```bash
   WORKTREE="$PROJECT_ROOT/.worktrees/task-storage-rollout-closure"
   EVIDENCE_DIR="/tmp/task-storage-rollout-closure/$PROJECT_ID"
   test "$(git -C "$PROJECT_ROOT" branch --show-current)" = main
   test -z "$(git -C "$PROJECT_ROOT" status --porcelain)"
   git -C "$PROJECT_ROOT" check-ignore -q .worktrees
   test ! -e "$WORKTREE"
   git -C "$PROJECT_ROOT" worktree add "$WORKTREE" -b task-storage-rollout-closure main
   mkdir -p "$EVIDENCE_DIR"
   if git -C "$PROJECT_ROOT" remote get-url origin >/dev/null 2>&1; then
     git -C "$PROJECT_ROOT" ls-remote origin refs/heads/main \
       | tee "$EVIDENCE_DIR/remote-main-before.txt"
   fi
   cd "$WORKTREE"
   ```

2. **Synchronize and pin the target toolkit.** Completed Tasks 4-5 used the parser SHA saved in their evidence. Tasks 10-20 run `uv sync --frozen`, capture current-pin validation with the status pattern below, then read and validate the final public SHA:

   ```bash
   TOOLKIT_SHA="$(tr -d '\n' < /tmp/task-storage-rollout-closure/final-toolkit-sha.txt)"
   test "${#TOOLKIT_SHA}" -eq 40
   git -C ~/d/science cat-file -e "$TOOLKIT_SHA^{commit}"
   ```

   Use the patch tool to add or replace the `science` uv source's `rev` with that exact literal SHA in `pyproject.toml`; do not use an environment variable in the TOML. Then run:

   ```bash
   uv lock --upgrade-package science --upgrade-package science-model
   git diff -- pyproject.toml uv.lock
   rg -n "$TOOLKIT_SHA" pyproject.toml uv.lock
   uv sync --frozen
   uv run --frozen science --version
   ```

   Stop if the lock diff moves an unrelated source or does not resolve both Science packages from the published commit.

3. **Capture the canonical baseline under the post-pin environment.** Run:

   ```bash
   uv run --frozen python /tmp/task-storage-rollout-closure/snapshot_tasks.py \
     . "$EVIDENCE_DIR/tasks-before.json"
   exit_code=0
   uv run --frozen science tasks migrate-storage --format json \
     --output "$EVIDENCE_DIR/migration-before.json" || exit_code=$?
   printf '%s\n' "$exit_code" | tee "$EVIDENCE_DIR/migration-before.exit"
   test "$exit_code" -le 1
   jq -e --argjson expected "$EXPECTED_COUNT" \
     '.meta.mode == "dry-run" and .meta.source_count == $expected and
      (.rows | length) == $expected and all(.rows[]; .status != "refusal")' \
     "$EVIDENCE_DIR/migration-before.json"
   test "$exit_code" -eq 0
   uv run --frozen science graph diff --format json \
     --output "$EVIDENCE_DIR/local-graph-diff-before.json"
   uv run --frozen python /tmp/task-storage-rollout-closure/project_task_graph.py \
     knowledge/graph.trig "$EVIDENCE_DIR/task-graph-before.json"
   uv run --frozen science peers list --format json \
     --output "$EVIDENCE_DIR/peers-before.json"
   sha256sum science.yaml | tee "$EVIDENCE_DIR/science-yaml-before.sha256"
   git status --short | tee "$EVIDENCE_DIR/git-status-before.txt"
   ```

   Capture strict validation with `--output validate-before.json`, stderr, and its exact 0/1 status using the status block below; reject exit 2 or `Traceback`.

4. **Apply only through the migrator.** Run:

   ```bash
   uv run --frozen science tasks migrate-storage --apply --format json \
     --output "$EVIDENCE_DIR/migration-applied.json"
   jq -e --argjson expected "$EXPECTED_COUNT" \
     '.meta.mode == "applied" and .meta.source_count == $expected and
      (.rows | length) == $expected' \
     "$EVIDENCE_DIR/migration-applied.json"
   uv run --frozen python /tmp/task-storage-rollout-closure/snapshot_tasks.py \
     . "$EVIDENCE_DIR/tasks-after.json"
   cmp "$EVIDENCE_DIR/tasks-before.json" "$EVIDENCE_DIR/tasks-after.json"
   test ! -e tasks/active.md
   test ! -e tasks/.science/task-storage-migration.journal
   uv run --frozen science tasks list --all --format json \
     --output "$EVIDENCE_DIR/tasks-list-after.json"
   if (( EXPECTED_COUNT == 0 )); then
     test ! -d tasks/active
   else
     test "$(find tasks/active -maxdepth 1 -type f -name '*.md' | wc -l)" -eq "$EXPECTED_COUNT"
   fi
   exit_code=0
   uv run --frozen science tasks migrate-storage --format json \
     --output "$EVIDENCE_DIR/migration-second-run.json" || exit_code=$?
   printf '%s\n' "$exit_code" | tee "$EVIDENCE_DIR/migration-second-run.exit"
   test "$exit_code" -eq 1
   ```

   When `EXPECTED_COUNT` is nonzero, require `tasks/active/` to contain exactly that many `*.md` files. When it is zero, require `tasks/active/` absent rather than manufacturing a placeholder. Capture a second dry-run with the status pattern below and require exit 1. For non-empty projects, its action rows must contain both `tasks/active/ is non-empty` and `tasks/active.md is absent`; for empty projects they must contain `tasks/active.md is absent; there is nothing to migrate`.
5. **Correct only live docs named by the task.** Say active tasks live under `tasks/active/`, one Markdown file per open task, and operators should use `science tasks`. Do not rewrite historical reports, done ledgers, or citations.
6. **Close the local graph.** Run:

   ```bash
   uv run --frozen science graph build --local-only
   uv run --frozen science graph validate
   uv run --frozen science graph diff --format json \
     --output "$EVIDENCE_DIR/local-graph-diff-after.json"
   jq -e '.rows | length == 0' "$EVIDENCE_DIR/local-graph-diff-after.json"
   test "$(rg -o 'schema:identifier "/[^"]*/overlays/[^"]*"' \
     knowledge/graph.trig | wc -l)" -eq 0
   uv run --frozen python /tmp/task-storage-rollout-closure/project_task_graph.py \
     knowledge/graph.trig "$EVIDENCE_DIR/task-graph-after.json"
   cmp "$EVIDENCE_DIR/task-graph-before.json" "$EVIDENCE_DIR/task-graph-after.json"
   ```

   Provenance paths may change; task-domain triples may not.

   If the final `cmp` fails, preserve both files and inspect the exact triple
   delta before doing anything else. When the pre-migration graph diff already
   reports task-source hashes as stale, create a disposable detached worktree
   at the project's recorded base commit, synchronize its pre-upgrade lock,
   rebuild its legacy-layout local graph, and write that projection to
   `task-graph-before-built.json`. Require that generated projection to be
   byte-identical to `task-graph-after.json`, and record why the committed
   baseline was stale. Any other task-domain delta stops the project.

7. **Compare validation and topology.** Capture post-build strict validation to `validate-after.json`, stderr, and exact 0/1 status. Reject `Traceback`, `resolver unavailable`, `predates the storage split`, or `falling back to deny-list only`. Then run:

   ```bash
   jq -S '.results | sort_by(.rule, .path, .line, .message, .severity, .task)' \
     "$EVIDENCE_DIR/validate-before.json" > "$EVIDENCE_DIR/validate-before-results.json"
   jq -S '.results | sort_by(.rule, .path, .line, .message, .severity, .task)' \
     "$EVIDENCE_DIR/validate-after.json" > "$EVIDENCE_DIR/validate-after-results.json"
   diff -u "$EVIDENCE_DIR/validate-before-results.json" \
     "$EVIDENCE_DIR/validate-after-results.json" > "$EVIDENCE_DIR/validate.delta" || test $? -eq 1
   uv run --frozen science peers list --format json \
     --output "$EVIDENCE_DIR/peers-after.json"
   cmp "$EVIDENCE_DIR/peers-before.json" "$EVIDENCE_DIR/peers-after.json"
   sha256sum -c "$EVIDENCE_DIR/science-yaml-before.sha256"
   ```

   Inspect `validate.delta`. Expected removals/additions are the task-storage
   state and graph-freshness messages. Map every newly reachable finding family
   to a named pre-migration `validate.check-error`; known storage-dependent
   examples include `short-form-ids` and `frontmatter-inline-gap`. Any family
   without that exact explanation stops the project.

8. **Commit and merge locally.** Inspect `git diff --check`, `git diff --stat`, and the full diff. Stage the complete intentional project transaction with `git add -A`, inspect `git diff --cached --check` and `git diff --cached`, commit with the task's exact message, record `git rev-parse HEAD | tee "$EVIDENCE_DIR/local-commit.txt"`, then run `git -C "$PROJECT_ROOT" merge --ff-only task-storage-rollout-closure`. Do not push. Keep every closure worktree through Task 25.

Use this status-capture shape whenever a command may legitimately exit 0 or 1:

```bash
exit_code=0
uv run --frozen science validate --all --strict --format json \
  --output "$EVIDENCE_DIR/validate-before.json" \
  2>"$EVIDENCE_DIR/validate-before.stderr" || exit_code=$?
printf '%s\n' "$exit_code" | tee "$EVIDENCE_DIR/validate-before.exit"
test "$exit_code" -le 1
! rg -n "Traceback" "$EVIDENCE_DIR/validate-before.stderr"
```

### Task 4: Migrate cBioPortal and prove the parser fix on the largest bracketed corpus

**Files:** `pyproject.toml`, `uv.lock`, `tasks/active.md`, `tasks/active/*.md`, `knowledge/graph.trig`, `knowledge/sources/local/manifest.yaml`, `knowledge/sources/local/mappings.yaml` under `~/d/cancer/data-sources/cbioportal`.

**Interfaces:** Consumes the public toolkit SHA and Local migration protocol. Produces 74 structurally identical split tasks and a current local graph on local `main`.

- [ ] **Step 1: Create cBioPortal's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/cancer/data-sources/cbioportal`, `PROJECT_ID=cbioportal`, and `EXPECTED_COUNT=74`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact public Task 2 SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the canonical task/validation/graph/peer baseline; explicitly prove all six historical bracketed done-ledger titles parse and the complete plan has 74 writes and zero refusals.**
- [ ] **Step 4: Apply the migrator and prove 74-task structural parity, done-ledger byte parity, split-store shape, no journal, successful listing, and the expected second-run refusal.**
- [ ] **Step 5: Make no live-doc edit because the audit found no current aggregate-path guidance in this project.**
- [ ] **Step 6: Rebuild and verify the local graph, including byte-identical task-domain projection and zero complete graph diff.**
- [ ] **Step 7: Review the complete validation delta and require unchanged peer output and `science.yaml`.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward cBioPortal's local `main`; do not push its existing origin.**

### Task 5: Migrate pan-disease and prove the second bracketed corpus

**Files:** `pyproject.toml`, `uv.lock`, `tasks/active.md`, `tasks/active/*.md`, `AGENTS.md`, `README.md`, and local graph artifacts under `~/d/health/comparisons/pan-disease`.

**Interfaces:** Consumes the public toolkit SHA and Local migration protocol. Produces 58 structurally identical split tasks and current live guidance/local graph.

- [ ] **Step 1: Create pan-disease's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/health/comparisons/pan-disease`, `PROJECT_ID=pan-disease`, and `EXPECTED_COUNT=58`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact public Task 2 SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the canonical baseline; prove the `[UNVERIFIED]` ledger title parses and the unbudgeted plan contains 58 writes and zero refusals.**
- [ ] **Step 4: Apply the migrator and prove 58-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Update `AGENTS.md` and both live `README.md` aggregate-path instructions to `tasks/active/` plus `science tasks`; leave historical records untouched.**
- [ ] **Step 6: Rebuild and verify the local graph, including task-domain projection parity and zero complete graph diff.**
- [ ] **Step 7: Review the complete validation delta and require unchanged peer output and `science.yaml`.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward pan-disease's local `main`; do not push.**

### Task 10: Resume and complete cancer/meta under the final toolkit

**Files:** `pyproject.toml`, `uv.lock`, task store, and local graph artifacts under `~/d/cancer/meta`.

**Interfaces:** Consumes the already-applied uncommitted 11-task migration, evidence under `/tmp/task-storage-rollout-closure/cancer-meta`, and the final public SHA. Produces the original 11 structurally identical split tasks plus a stable current local graph; it never reapplies or manually rewrites migration output.

- [ ] **Step 1: Verify and preserve the interrupted execution state**

Require clean primary `main` at `fdeeb70`, rollout branch based at that commit, and worktree changes limited to `pyproject.toml`, `uv.lock`, `tasks/active.md`, `tasks/active/*.md`, and `knowledge/graph.trig`. Require exactly 21 absolute overlay source identifiers in the tainted graph. Preserve every existing evidence file. Do not reset, recreate the worktree, or rerun `--apply`.

- [ ] **Step 2: Re-certify the completed migration gates**

Require `tasks-before.json == tasks-after.json`, exactly 11 split files, no aggregate or journal, successful `tasks-list-after.json`, second-run exit 1 with both required refusals, byte-identical peers, and a valid `science-yaml-before.sha256` check.

- [ ] **Step 3: Replace the intermediate pin with the final SHA**

Use the patch tool to replace `ba0b0cb0304aff03159ebc37c188839cfd4b1515` with the exact `final-toolkit-sha.txt` value. Relock only Science packages, require no unrelated lock movement, synchronize, and verify both installed package revisions.

- [ ] **Step 4: Replace the tainted generated graph through a canonical rebuild**

```bash
uv run --frozen science graph build --local-only
uv run --frozen science graph validate
uv run --frozen science graph diff --format json \
  --output /tmp/task-storage-rollout-closure/cancer-meta/local-graph-diff-corrective.json
jq -e '.rows | length == 0' \
  /tmp/task-storage-rollout-closure/cancer-meta/local-graph-diff-corrective.json
test "$(rg -o 'schema:identifier "/[^"]*/overlays/[^"]*"' \
  knowledge/graph.trig | wc -l)" -eq 0
```

Create `task-graph-corrective.json` and require it byte-identical to the already-certified `task-graph-after.json`.

- [ ] **Step 5: Make no live-doc edit**

The initial audit found no current aggregate-path instruction. Leave historical docs untouched.

- [ ] **Step 6: Recheck validation and topology**

Capture complete strict validation as `validate-corrective.json`. Require its sorted results byte-identical to the existing post-migration `validate-after.json`; this pin changes provenance spelling, not validation semantics. Re-capture peers, require identity, and verify `science.yaml` checksum identity.

- [ ] **Step 7: Inspect the complete atomic diff**

Require the dependency diff restricted to the two Science packages, the 11-task split identical to migrator output, no absolute overlay identifier, and generated graph changes explained by task storage plus absolute-to-relative overlay provenance. Run unstaged and cached `diff --check`.

- [ ] **Step 8: Commit and fast-forward cancer/meta locally**

```bash
git add -A
git diff --cached --check
git commit -m "chore(science): migrate task storage"
git rev-parse HEAD | tee \
  /tmp/task-storage-rollout-closure/cancer-meta/local-commit.txt
git -C ~/d/cancer/meta merge --ff-only task-storage-rollout-closure
```

Do not push. Retain the worktree for Task 23.

### Task 11: Migrate evolution under the final toolkit

**Files:** task store, `AGENTS.md`, and local graph artifacts under `~/d/cancer/mechanisms/evolution`.

**Interfaces:** Consumes the final public SHA and Local migration protocol. Produces 31 structurally identical split tasks and a current local graph.

- [ ] **Step 1: Create evolution's clean worktree and synchronize its existing lock, using `PROJECT_ROOT=~/d/cancer/mechanisms/evolution`, `PROJECT_ID=evolution`, and `EXPECTED_COUNT=31`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact final public SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical task, 31-write dry-run, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove 31-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Update `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation, require peer/config identity, and prove the dependency diff is restricted to the two Science packages.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward evolution's local `main`; do not push.**

### Task 12: Migrate pre-cancer

**Files:** `pyproject.toml`, `uv.lock`, task store, and local graph artifacts under `~/d/cancer/conditions/pre-cancer`.

**Interfaces:** Consumes the final public SHA and Local migration protocol. Produces six structurally identical split tasks and a current local graph.

- [ ] **Step 1: Create pre-cancer's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/cancer/conditions/pre-cancer`, `PROJECT_ID=pre-cancer`, and `EXPECTED_COUNT=6`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact final public SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical task, six-write dry-run, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove six-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Make no live-doc edit because no current aggregate-path instruction was found.**
- [ ] **Step 6: Rebuild and verify the local graph, task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward pre-cancer's local `main`; do not push.**

### Task 13: Migrate the empty ovarian store

**Files:** `pyproject.toml`, `uv.lock`, `tasks/active.md`, `AGENTS.md`, and local graph artifacts under `~/d/cancer/cancer-types/ovarian`.

**Interfaces:** Consumes the final public SHA and Local migration protocol. Produces valid `EMPTY` task storage with no placeholder and a current local graph.

- [ ] **Step 1: Create ovarian's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/cancer/cancer-types/ovarian`, `PROJECT_ID=ovarian`, and `EXPECTED_COUNT=0`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact final public SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical zero-write dry-run, empty task snapshot, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove valid `EMPTY` storage, done-ledger parity, no aggregate, placeholder, or journal, zero-row listing, and the absent-source second-run refusal.**
- [ ] **Step 5: Update both live aggregate-path statements in `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, empty task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward ovarian's local `main`; do not push.**

### Task 14: Migrate the empty head-and-neck store

**Files:** `pyproject.toml`, `uv.lock`, `tasks/active.md`, `AGENTS.md`, and local graph artifacts under `~/d/cancer/cancer-types/head-and-neck`.

**Interfaces:** Consumes the final public SHA and Local migration protocol. Produces valid `EMPTY` task storage with no placeholder and a current local graph.

- [ ] **Step 1: Create head-and-neck's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/cancer/cancer-types/head-and-neck`, `PROJECT_ID=head-and-neck`, and `EXPECTED_COUNT=0`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact final public SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical zero-write dry-run, empty task snapshot, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove valid `EMPTY` storage, done-ledger parity, no aggregate, placeholder, or journal, zero-row listing, and absent-source refusal.**
- [ ] **Step 5: Update both live aggregate-path statements in `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, empty task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward head-and-neck's local `main`; do not push.**

### Task 15: Migrate the empty prostate store

**Files:** `pyproject.toml`, `uv.lock`, `tasks/active.md`, `AGENTS.md`, and local graph artifacts under `~/d/cancer/cancer-types/prostate`.

**Interfaces:** Consumes the final public SHA and Local migration protocol. Produces valid `EMPTY` task storage with no placeholder and a current local graph.

- [ ] **Step 1: Create prostate's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/cancer/cancer-types/prostate`, `PROJECT_ID=prostate`, and `EXPECTED_COUNT=0`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact final public SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical zero-write dry-run, empty task snapshot, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove valid `EMPTY` storage, done-ledger parity, no aggregate, placeholder, or journal, zero-row listing, and absent-source refusal.**
- [ ] **Step 5: Update both live aggregate-path statements in `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, empty task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward prostate's local `main`; do not push.**

### Task 16: Migrate the empty breast store

**Files:** `pyproject.toml`, `uv.lock`, `tasks/active.md`, `AGENTS.md`, and local graph artifacts under `~/d/cancer/cancer-types/breast`.

**Interfaces:** Consumes the final public SHA and Local migration protocol. Produces valid `EMPTY` task storage with no placeholder and a current local graph.

- [ ] **Step 1: Create breast's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/cancer/cancer-types/breast`, `PROJECT_ID=breast`, and `EXPECTED_COUNT=0`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact final public SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical zero-write dry-run, empty task snapshot, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove valid `EMPTY` storage, done-ledger parity, no aggregate, placeholder, or journal, zero-row listing, and absent-source refusal.**
- [ ] **Step 5: Update both live aggregate-path statements in `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, empty task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward breast's local `main`; do not push.**

### Task 17: Migrate therapeutics and close its stale environment

**Files:** task store, `AGENTS.md`, and local graph artifacts under `~/d/cancer/therapeutics`.

**Interfaces:** Consumes the final public SHA and Local migration protocol. Produces two structurally identical split tasks and a current local graph; no composite follows.

- [ ] **Step 1: Create therapeutics' clean worktree and run `uv sync --frozen` to replace its stale installed environment, using `PROJECT_ROOT=~/d/cancer/therapeutics`, `PROJECT_ID=therapeutics`, and `EXPECTED_COUNT=2`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact final public SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical task, two-write dry-run, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove two-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Update `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, task-domain parity, zero complete graph diff, and a dependency diff restricted to the two Science packages.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, fast-forward local `main`, do not push its origin, and retain the clean worktree through Task 25.**

### Task 18: Migrate health/meta under the final toolkit

**Files:** task store, `AGENTS.md`, and local graph artifacts under `~/d/health/meta`.

**Interfaces:** Consumes the final public SHA and Local migration protocol. Produces 32 structurally identical split tasks and a current local graph.

- [ ] **Step 1: Create health/meta's clean worktree and synchronize its existing lock, using `PROJECT_ROOT=~/d/health/meta`, `PROJECT_ID=health-meta`, and `EXPECTED_COUNT=32`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact final public SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical task, 32-write dry-run, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove 32-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Update both live aggregate-path statements in `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, task-domain parity, zero complete graph diff, and a dependency diff restricted to the two Science packages.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward health/meta's local `main`; do not push.**

### Task 19: Migrate cycles without rewriting its historical workflow README

**Files:** task store, `AGENTS.md`, and local graph artifacts under `~/d/health/processes/cycles`.

**Interfaces:** Consumes the final public SHA and Local migration protocol. Produces 53 structurally identical split tasks and a current local graph.

- [ ] **Step 1: Create cycles' clean worktree and synchronize its existing lock, using `PROJECT_ROOT=~/d/health/processes/cycles`, `PROJECT_ID=cycles`, and `EXPECTED_COUNT=53`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact final public SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical task, 53-write dry-run, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove 53-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Update `AGENTS.md`; leave the workflow README's dated aggregate-path record unchanged as history.**
- [ ] **Step 6: Rebuild and verify the local graph, task-domain parity, zero complete graph diff, and a dependency diff restricted to the two Science packages.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward cycles' local `main`; do not push its existing origin.**

### Task 20: Migrate immunity

**Files:** `pyproject.toml`, `uv.lock`, task store, `AGENTS.md`, and local graph artifacts under `~/d/health/processes/immunity`.

**Interfaces:** Consumes the final public SHA and Local migration protocol. Produces five structurally identical split tasks and a current local graph.

- [ ] **Step 1: Create immunity's clean worktree and synchronize its current lock, using `PROJECT_ROOT=~/d/health/processes/immunity`, `PROJECT_ID=immunity`, and `EXPECTED_COUNT=5`.**
- [ ] **Step 2: Capture current-pin validation, pin the exact final public SHA, relock only Science packages, synchronize, and verify the resolved SHA.**
- [ ] **Step 3: Capture the complete canonical task, five-write dry-run, validation, graph, and peer baseline.**
- [ ] **Step 4: Apply the migrator and prove five-task structural parity, done-ledger byte parity, split shape, no journal, listing success, and expected second-run refusal.**
- [ ] **Step 5: Update both live aggregate-path statements in `AGENTS.md` to the split-store/CLI guidance.**
- [ ] **Step 6: Rebuild and verify the local graph, task-domain parity, and zero complete graph diff.**
- [ ] **Step 7: Review validation activation and require peer/config identity.**
- [ ] **Step 8: Commit as `chore(science): migrate task storage`, review, and fast-forward immunity's local `main`; do not push.**

### Task 21: Close post-acute-infection without rerunning migration

**Files:** `.gitignore`, `pyproject.toml`, `uv.lock`, `AGENTS.md`, the five existing `results/**/datapackage.json` files, `knowledge/graph.trig`, `knowledge/sources/local/manifest.yaml`, and `knowledge/sources/local/mappings.yaml` under `~/d/health/processes/post-acute-infection`.

**Interfaces:** Consumes its already-split task store at local-main commit ancestry containing `67361ff` and the final public toolkit SHA. Produces unchanged split tasks, five durable workflow-run manifests with no checkout-local path, corrected live guidance, and a current local graph.

- [ ] **Step 1: Create and synchronize the isolated worktree**

```bash
PROJECT_ROOT=~/d/health/processes/post-acute-infection
WORKTREE="$PROJECT_ROOT/.worktrees/task-storage-rollout-closure"
EVIDENCE_DIR=/tmp/task-storage-rollout-closure/post-acute-infection
git -C "$PROJECT_ROOT" status --short --branch
git -C "$PROJECT_ROOT" check-ignore -q .worktrees
git -C "$PROJECT_ROOT" merge-base --is-ancestor 67361ff main
git -C "$PROJECT_ROOT" worktree add "$WORKTREE" -b task-storage-rollout-closure main
mkdir -p "$EVIDENCE_DIR"
git -C "$PROJECT_ROOT" ls-remote origin refs/heads/main \
  | tee "$EVIDENCE_DIR/remote-main-before.txt"
cd "$WORKTREE"
uv sync --frozen
```

Expected: clean `main`, the migration commit is already an ancestor, and no migrator command is run.

- [ ] **Step 2: Capture task, validation, graph, and topology baselines**

Use the Task 3 helpers and the protocol's complete `--output` captures. Record `tasks-before.json`, `task-graph-before.json`, `validate-before.json` plus status/stderr, `local-graph-diff-before.json`, `peers-before.json`, and the `science.yaml` digest. From primary, require exactly five `results/**/datapackage.json` files and save their sorted relative-path/SHA-256 inventory.

- [ ] **Step 3: Admit only the five provenance manifests**

Patch `.gitignore`, replacing `results/*` and its current exception with exactly:

```gitignore
results/**
!results/**/
!results/**/datapackage.json
!results/.gitkeep
```

Mechanically transfer the five audited JSON manifests from primary to the same relative paths in the worktree, preserving bytes, then use the patch tool to change the t116 manifest's checkout-local source path to `code/workflows/t116-power-bias-floor/config.yaml`. Require the other four manifest hashes unchanged, all five visible to Git, `.gitkeep` visible, and representative result payloads still ignored. Reject any remaining checkout-root, home-directory, or `.worktrees/` value across the five manifests.

- [ ] **Step 4: Pin the final toolkit and relock only Science**

Patch the Science source to the exact value from `final-toolkit-sha.txt`, relock only `science` and `science-model`, require no unrelated package movement, run `uv sync --frozen`, and verify both installed revisions.

- [ ] **Step 5: Correct the live guide and rebuild only the local graph**

Patch `AGENTS.md` to describe `tasks/active/` and `science tasks`, then run:

```bash
uv run --frozen science graph build --local-only
uv run --frozen science graph validate
uv run --frozen science graph diff --format json \
  --output "$EVIDENCE_DIR/local-graph-diff-after.json"
jq -e '.rows | length == 0' "$EVIDENCE_DIR/local-graph-diff-after.json"
test "$(rg -o 'schema:identifier "/[^"]*/overlays/[^"]*"' \
  knowledge/graph.trig | wc -l)" -eq 0
```

- [ ] **Step 6: Prove closure parity**

Recreate task and task-domain graph snapshots and require both byte-identical to baseline. Require exactly five workflow-run entities, all five manifest paths in the stored revision manifest, zero graph-diff rows, identical peer output and `science.yaml` digest, no migration journal, no `tasks/active.md`, successful task listing, and post-validation without traceback or storage fallback. Review validation deltas under the same rules as the Local migration protocol.

- [ ] **Step 7: Commit and merge locally**

```bash
git add .gitignore pyproject.toml uv.lock AGENTS.md results \
  knowledge/graph.trig \
  knowledge/sources/local/manifest.yaml knowledge/sources/local/mappings.yaml
git diff --cached --check
git diff --cached
git commit -m "chore(science): close task storage rollout"
git rev-parse HEAD | tee "$EVIDENCE_DIR/local-commit.txt"
git -C "$PROJECT_ROOT" merge --ff-only task-storage-rollout-closure
```

Do not push its existing origin. Keep the worktree for the health composite phase.

### Task 22: Correct multiple-myeloma's pin and local overlay provenance

**Files:** `pyproject.toml`, `uv.lock`, and `knowledge/graph.trig` under `~/d/cancer/cancer-types/multiple-myeloma`.

**Interfaces:** Consumes its already-split task store and the final public SHA. Produces unchanged tasks and topology, a zero-diff local graph with relative overlay identifiers, and a retained worktree for Task 23. It does not run the task migrator or edit historical task-path citations.

- [ ] **Step 1: Create the clean corrective worktree and capture baselines**

At `~/d/cancer/cancer-types/multiple-myeloma`, require clean `main`, ignored `.worktrees`, and no existing rollout branch/worktree. Create `.worktrees/task-storage-rollout-closure`, run `uv sync --frozen`, and create `/tmp/task-storage-rollout-closure/multiple-myeloma`. Capture:

- the canonical task snapshot and task-domain graph projection with the Task 3 helpers;
- complete strict validation plus exit status and stderr;
- complete local graph diff via `--output`;
- peer-list JSON and the `science.yaml` digest; and
- the current pin, `pyproject.toml`, `uv.lock`, and `knowledge/graph.trig` checksums.

Require successful task listing, no aggregate task file or migration journal, and exactly 51 absolute overlay source identifiers in the existing local graph. Do not run `science tasks migrate-storage`.

- [ ] **Step 2: Pin the final SHA and audit the Science-only relock**

The current dependency has no `rev` key. Use the patch tool to add `rev = "<final SHA>"` to the existing `science = { git = ..., subdirectory = "science" }` source using the exact value in `/tmp/task-storage-rollout-closure/final-toolkit-sha.txt`; do not replace a nonexistent revision. Run `uv lock --upgrade-package science --upgrade-package science-model`, inspect the full dependency diff, require no unrelated package movement, run `uv sync --frozen`, and verify both installed package revisions equal the final SHA.

- [ ] **Step 3: Rebuild and certify the local graph**

```bash
uv run --frozen science graph build --local-only
uv run --frozen science graph validate
uv run --frozen science graph diff --format json \
  --output /tmp/task-storage-rollout-closure/multiple-myeloma/local-graph-diff-after.json
jq -e '.rows | length == 0' \
  /tmp/task-storage-rollout-closure/multiple-myeloma/local-graph-diff-after.json
test "$(rg -o 'schema:identifier "/[^"]*/overlays/[^"]*"' \
  knowledge/graph.trig | wc -l)" -eq 0
```

Recreate the task snapshot and task-domain graph projection and require both byte-identical to baseline. Require peer-list and `science.yaml` identity. Capture post-pin complete validation; any delta must be explained by the inherited toolkit revision and must not contain a traceback, storage fallback, or graph error.

- [ ] **Step 4: Commit and fast-forward locally**

Inspect the full and cached diffs. Require changes limited to the Science pin/lock and generated local graph, with graph changes explained by absolute-to-relative overlay provenance. Then run:

```bash
git add pyproject.toml uv.lock knowledge/graph.trig
git diff --cached --check
git commit -m "fix(graph): stabilize overlay provenance"
git rev-parse HEAD | tee \
  /tmp/task-storage-rollout-closure/multiple-myeloma/local-commit.txt
git -C ~/d/cancer/cancer-types/multiple-myeloma \
  merge --ff-only task-storage-rollout-closure
```

Do not push. Keep the clean worktree for Task 23.

## Composite refresh protocol used by Tasks 23-24

For each listed project's `.worktrees/task-storage-rollout-closure`, set that project's existing `EVIDENCE_DIR` and run:

```bash
sha256sum knowledge/graph.trig | tee "$EVIDENCE_DIR/local-graph-before-composite.sha256"
test "$(rg -o 'schema:identifier "/[^"]*/overlays/[^"]*"' \
  knowledge/graph.trig | wc -l)" -eq 0
uv run --frozen science peers list --format json \
  --output "$EVIDENCE_DIR/peers-composite-before.json"
uv run --frozen science graph build
sha256sum -c "$EVIDENCE_DIR/local-graph-before-composite.sha256"
uv run --frozen science peers list --format json \
  --output "$EVIDENCE_DIR/peers-composite-after.json"
cmp "$EVIDENCE_DIR/peers-composite-before.json" \
  "$EVIDENCE_DIR/peers-composite-after.json"
uv run --frozen science graph validate --path knowledge/composite.trig
test "$(rg -o 'schema:identifier "/[^"]*/overlays/[^"]*"' \
  knowledge/composite.trig | wc -l)" -eq 0
uv run --frozen science graph diff --path knowledge/composite.trig --format json \
  --output "$EVIDENCE_DIR/composite-graph-diff-after.json"
jq -e '.rows | length == 0' "$EVIDENCE_DIR/composite-graph-diff-after.json"
```

Any Commons resolution failure, local graph byte delta, peer delta, validation failure, or nonzero diff stops that project. Do not retry with `--no-commons`. Inspect `git status --short`: if `knowledge/composite.trig` changed, stage only that file, run `git diff --cached --check`, inspect the staged diff, commit `chore(science): refresh composite graph`, and record `git rev-parse HEAD | tee "$EVIDENCE_DIR/composite-commit.txt"`. If it did not change, make no commit and record `git rev-parse HEAD | tee "$EVIDENCE_DIR/composite-unchanged-at.txt"`. Fast-forward the rollout branch into the repository's local `main`; do not push.

### Task 23: Refresh all affected cancer composites

**Files:** `knowledge/composite.trig` in cancer/meta, multiple-myeloma, evolution, pre-cancer, cBioPortal, ovarian, head-and-neck, prostate, and breast.

**Interfaces:** Consumes every cancer local migration or corrective commit already merged to its local `main`; consumes the existing authored `peers:` lists and default Commons resolution. Produces validated, zero-diff composites without changing any local graph bytes. Task 6's unit test is the contract that same-named relative overlay sources remain qualified by peer named graph.

- [ ] **Step 1: Reuse multiple-myeloma's retained corrective worktree**

Require multiple-myeloma's Task 22 commit to be the tip of both local `main` and its clean retained rollout worktree. Run `uv sync --frozen`; do not create a second worktree or branch.

- [ ] **Step 2: Refresh each cancer composite from its retained worktree**

Process exactly these roots, one at a time:

```text
~/d/cancer/meta
~/d/cancer/cancer-types/multiple-myeloma
~/d/cancer/mechanisms/evolution
~/d/cancer/conditions/pre-cancer
~/d/cancer/data-sources/cbioportal
~/d/cancer/cancer-types/ovarian
~/d/cancer/cancer-types/head-and-neck
~/d/cancer/cancer-types/prostate
~/d/cancer/cancer-types/breast
```

Execute the Composite refresh protocol for each project in that order. Stop at the affected project on any failed gate.

- [ ] **Step 3: Commit only changed composites and merge each branch locally**

For each root, inspect `git status --short`. The Composite refresh protocol commits only a changed `knowledge/composite.trig` with:

```bash
git add knowledge/composite.trig
git diff --cached --check
git commit -m "chore(science): refresh composite graph"
```

If it did not change, make no commit. In either case, merge the rollout branch into that repository's local `main` with `--ff-only`. Do not push cBioPortal or any other consumer.

### Task 24: Refresh all affected health composites

**Files:** `knowledge/composite.trig` in health/meta, pan-disease, cycles, immunity, and post-acute-infection.

**Interfaces:** Consumes all health local commits already merged to local `main`, authored peer lists, and default Commons resolution. Produces validated, zero-diff composites without local graph changes.

- [ ] **Step 1: Process exactly the five retained health worktrees**

```text
~/d/health/meta
~/d/health/comparisons/pan-disease
~/d/health/processes/cycles
~/d/health/processes/immunity
~/d/health/processes/post-acute-infection
```

Execute the Composite refresh protocol for each project in that order using its existing evidence directory. Stop on Commons failure, local graph change, peer change, invalid graph, or nonzero diff; never use `--no-commons`.

- [ ] **Step 2: Commit only changed composites and merge locally**

For each root, commit only a changed `knowledge/composite.trig` with `chore(science): refresh composite graph`, make no empty commit, and fast-forward the local rollout branch into local `main`. Do not push cycles, post-acute-infection, or any other consumer.

### Task 25: Run the registry-wide closure audit and clean consumer worktrees

**Files:** Evidence only under `/tmp/task-storage-rollout-closure/`; no tracked mutation.

**Interfaces:** Consumes all local-main merges and evidence from Tasks 3-24. Produces the final completion report and leaves primary repositories clean with consumer changes unpublished.

- [ ] **Step 1: Prove the global registry was not edited**

```bash
sha256sum -c /tmp/task-storage-rollout-closure/registry.sha256
```

- [ ] **Step 2: Prove every present non-Commons registered project has retired the aggregate store**

Run:

```bash
yq -r '.projects[] | select(.role != "commons") | [.id, .path] | @tsv' \
  ~/.config/science/config.yaml |
while IFS=$'\t' read -r project_id project_root; do
  if [[ "$project_id" == obsproj ]]; then
    test ! -e "$project_root"
    printf 'skip %s: registered path is absent\n' "$project_id"
    continue
  fi
  test -d "$project_root"
  test ! -e "$project_root/tasks/active.md"
done
printf 'skip commons: role has no task queue\n'
```

Expected: the two skips are explicit; every present non-Commons project passes the absence assertion.

- [ ] **Step 3: Prove all 272 migrated active tasks survived structurally**

Run:

```bash
project_ids=(
  cbioportal pan-disease cancer-meta evolution pre-cancer ovarian head-and-neck
  prostate breast therapeutics health-meta cycles immunity
)
for project_id in $project_ids; do
  cmp "/tmp/task-storage-rollout-closure/$project_id/tasks-before.json" \
    "/tmp/task-storage-rollout-closure/$project_id/tasks-after.json"
done
jq -s -e 'map(.active | length) | add == 272' \
  /tmp/task-storage-rollout-closure/{cbioportal,pan-disease,cancer-meta,evolution,pre-cancer,ovarian,head-and-neck,prostate,breast,therapeutics,health-meta,cycles,immunity}/tasks-before.json
```

Also require no `tasks/.science/task-storage-migration.journal` in those 13 roots or post-acute-infection.

- [ ] **Step 4: Recheck every local and composite artifact from local main**

First require the exact final revision in all 15 closure targets:

```bash
final_sha="$(tr -d '\n' < \
  /tmp/task-storage-rollout-closure/final-toolkit-sha.txt)"
pin_roots=(
  ~/d/cancer/meta
  ~/d/cancer/mechanisms/evolution
  ~/d/cancer/conditions/pre-cancer
  ~/d/cancer/data-sources/cbioportal
  ~/d/cancer/cancer-types/ovarian
  ~/d/cancer/cancer-types/head-and-neck
  ~/d/cancer/cancer-types/prostate
  ~/d/cancer/cancer-types/breast
  ~/d/cancer/therapeutics
  ~/d/cancer/cancer-types/multiple-myeloma
  ~/d/health/meta
  ~/d/health/comparisons/pan-disease
  ~/d/health/processes/cycles
  ~/d/health/processes/immunity
  ~/d/health/processes/post-acute-infection
)
for project_root in $pin_roots; do
  rg -q "$final_sha" "$project_root/pyproject.toml"
  rg -q "$final_sha" "$project_root/uv.lock"
done
```

Then use this exact 15-project local target map:

```bash
closure_ids=(
  cancer-meta multiple-myeloma evolution pre-cancer cbioportal ovarian head-and-neck prostate breast
  therapeutics health-meta pan-disease cycles immunity post-acute-infection
)
closure_roots=(
  ~/d/cancer/meta
  ~/d/cancer/cancer-types/multiple-myeloma
  ~/d/cancer/mechanisms/evolution
  ~/d/cancer/conditions/pre-cancer
  ~/d/cancer/data-sources/cbioportal
  ~/d/cancer/cancer-types/ovarian
  ~/d/cancer/cancer-types/head-and-neck
  ~/d/cancer/cancer-types/prostate
  ~/d/cancer/cancer-types/breast
  ~/d/cancer/therapeutics
  ~/d/health/meta
  ~/d/health/comparisons/pan-disease
  ~/d/health/processes/cycles
  ~/d/health/processes/immunity
  ~/d/health/processes/post-acute-infection
)
for (( index = 1; index <= ${#closure_ids}; index++ )); do
  project_id="${closure_ids[$index]}"
  project_root="${closure_roots[$index]}"
  final_dir="/tmp/task-storage-rollout-closure/$project_id/final"
  mkdir -p "$final_dir"
  (
    cd "$project_root"
    uv run --frozen science graph validate
    uv run --frozen science graph diff --mode hash --format json \
      --output "$final_dir/local-graph-diff.json"
    test "$(rg -o 'schema:identifier "/[^"]*/overlays/[^"]*"' \
      knowledge/graph.trig | wc -l)" -eq 0
  )
jq -e '.rows | length == 0' "$final_dir/local-graph-diff.json"
done
```

`--mode hash` is deliberate in primary checkouts: revision mtimes are local to
the worktree that built the committed artifact. Each retained build worktree
already proved zero hybrid diff before commit.

Then run:

```bash
composite_ids=(
  cancer-meta multiple-myeloma evolution pre-cancer cbioportal ovarian head-and-neck
  prostate breast health-meta pan-disease cycles immunity post-acute-infection
)
composite_roots=(
  ~/d/cancer/meta
  ~/d/cancer/cancer-types/multiple-myeloma
  ~/d/cancer/mechanisms/evolution
  ~/d/cancer/conditions/pre-cancer
  ~/d/cancer/data-sources/cbioportal
  ~/d/cancer/cancer-types/ovarian
  ~/d/cancer/cancer-types/head-and-neck
  ~/d/cancer/cancer-types/prostate
  ~/d/cancer/cancer-types/breast
  ~/d/health/meta
  ~/d/health/comparisons/pan-disease
  ~/d/health/processes/cycles
  ~/d/health/processes/immunity
  ~/d/health/processes/post-acute-infection
)
for (( index = 1; index <= ${#composite_ids}; index++ )); do
  project_id="${composite_ids[$index]}"
  project_root="${composite_roots[$index]}"
  final_dir="/tmp/task-storage-rollout-closure/$project_id/final"
  mkdir -p "$final_dir"
  (
    cd "$project_root"
    uv run --frozen science graph validate --path knowledge/composite.trig
    test "$(rg -o 'schema:identifier "/[^"]*/overlays/[^"]*"' \
      knowledge/composite.trig | wc -l)" -eq 0
    uv run --frozen science graph diff --mode hash \
      --path knowledge/composite.trig --format json \
      --output "$final_dir/composite-graph-diff.json"
  )
  jq -e '.rows | length == 0' "$final_dir/composite-graph-diff.json"
done
test ! -e ~/d/cancer/therapeutics/knowledge/composite.trig
```

Do not create a therapeutics composite.

- [ ] **Step 5: Prove workflow provenance durability**

Require exactly 11 tracked `results/**/datapackage.json` files in cBioPortal
and five in post-acute-infection. Require no other tracked result payload except
each project's existing `.gitkeep`; require every sibling payload still ignored; reject
checkout-root, home-directory, and `.worktrees/` values across all 16 manifests.
Project both primary graphs with `semantic_graph.py` and require the saved Task
8C and Task 21 workflow-run counts.

- [ ] **Step 6: Recheck federation health without changing topology**

Using the exact `closure_ids` and `closure_roots` arrays from Step 4, run from every project root:

```bash
for (( index = 1; index <= ${#closure_ids}; index++ )); do
  project_id="${closure_ids[$index]}"
  project_root="${closure_roots[$index]}"
  final_dir="/tmp/task-storage-rollout-closure/$project_id/final"
  (
    cd "$project_root"
    uv run --frozen science peers check --format json
    uv run --frozen science peers list --format json --output "$final_dir/peers.json"
  )
  cmp "/tmp/task-storage-rollout-closure/$project_id/peers-before.json" \
    "$final_dir/peers.json"
done
```

Exit 0 and byte-identical peer lists are required.

- [ ] **Step 7: Recheck task and validation behavior**

Using the exact `closure_ids` and `closure_roots` arrays from Step 4, run for every entry:

```bash
for (( index = 1; index <= ${#closure_ids}; index++ )); do
  project_id="${closure_ids[$index]}"
  project_root="${closure_roots[$index]}"
  final_dir="/tmp/task-storage-rollout-closure/$project_id/final"
  (
    cd "$project_root"
    uv run --frozen science tasks list --all --format json \
      --output "$final_dir/tasks.json"
    exit_code=0
    uv run --frozen science validate --all --strict --format json \
      --output "$final_dir/validate.json" \
      2>"$final_dir/validate.stderr" || exit_code=$?
    printf '%s\n' "$exit_code" | tee "$final_dir/validate.exit"
    test "$exit_code" -le 1
  )
  ! rg -n "Traceback|resolver unavailable|predates the storage split|falling back to deny-list only" \
    "$final_dir/validate.stderr"
done
```

Extract and report any activated `short-form-ids` or `frontmatter-inline-gap` result; do not suppress it.

- [ ] **Step 8: Confirm local-main state and unpublished remotes**

For every touched repository, require the SHA in its `local-commit.txt` to be an ancestor of local `main`, include any later composite commit, and require an empty primary `git status --porcelain`. This works even though Task 17 already deleted therapeutics' merged branch. For the four repositories with remotes, compare the remote ref to its recorded pre-rollout value and report local ahead counts:

```bash
remote_ids=(cbioportal therapeutics cycles post-acute-infection)
remote_roots=(
  ~/d/cancer/data-sources/cbioportal
  ~/d/cancer/therapeutics
  ~/d/health/processes/cycles
  ~/d/health/processes/post-acute-infection
)
for (( index = 1; index <= ${#remote_ids}; index++ )); do
  project_id="${remote_ids[$index]}"
  project_root="${remote_roots[$index]}"
  git -C "$project_root" ls-remote origin refs/heads/main \
    > "/tmp/task-storage-rollout-closure/$project_id/remote-main-after.txt"
  cmp "/tmp/task-storage-rollout-closure/$project_id/remote-main-before.txt" \
    "/tmp/task-storage-rollout-closure/$project_id/remote-main-after.txt"
  git -C "$project_root" rev-list --left-right --count origin/main...main
done
```

An identical remote ref proves the rollout did not publish consumer commits.

- [ ] **Step 9: Remove only clean, merged consumer worktrees**

For all 15 closure roots, run:

```bash
cleanup_roots=($closure_roots)
for PROJECT_ROOT in $cleanup_roots; do
  WORKTREE="$PROJECT_ROOT/.worktrees/task-storage-rollout-closure"
  if [[ -d "$WORKTREE" ]]; then
    test -z "$(git -C "$WORKTREE" status --porcelain)"
    git -C "$PROJECT_ROOT" merge-base --is-ancestor task-storage-rollout-closure main
    git -C "$PROJECT_ROOT" worktree remove "$WORKTREE"
    git -C "$PROJECT_ROOT" branch -d task-storage-rollout-closure
  fi
done
```

Leave the toolkit worktree in place for final review and branch handoff.

- [ ] **Step 10: Write the completion report**

Report: public final toolkit SHA; exact final pins in all 15 closure targets; all consumer commit SHAs; 272/272 task parity; empty-store outcomes; 15 local and 14 composite zero-diff results; zero absolute overlay identifiers; 16 tracked workflow-run manifests with ignored payloads; primary/worktree semantic parity; cBioPortal 74 and pan-disease 58 no-refusal proofs; validation activations; unchanged registry and peer topology; Commons success; worktree cleanup; and which consumer mains remain unpublished. Also list the intentionally deferred `obsproj`, registry-parent, peer-symmetry, standalone-graph, workflow-manifest schema projection, and historical-citation follow-ups.
