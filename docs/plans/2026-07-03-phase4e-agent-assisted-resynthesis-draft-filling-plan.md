# Phase 4e Agent-Assisted Resynthesis Draft Filling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `resynthesis-draft-context` surface that expands an existing Half D resynthesis draft into a bounded, deterministic agent context packet.

**Architecture:** Keep Half D draft validation/apply unchanged. Add focused context-builder helpers to `proposition_resynthesis.py`, reuse live action resolution and live annotation indexing, then expose one flat CLI command that prints or writes JSON/markdown context. The context packet is guidance only; agents still edit the existing Half D draft schema and `validate-proposition-resynthesis` remains authoritative.

**Tech Stack:** Python 3.13, dataclasses-free dict payloads, Click, JSON, existing Phase 4e resynthesis/reconciliation helpers, pytest, ruff, pyright.

---

## File Structure

- Modify `science/src/science_tool/annotation/proposition_resynthesis.py`
  - Add context constants.
  - Add `build_resynthesis_context_packet`.
  - Add `resynthesis_context_to_markdown`.
  - Reuse `_live_action_for_draft`, `_current_action_annotations`, `_live_annotation_index`, `_resolve_paper_ref`, `find_entity`, `draft_to_json`, `RESYNTHESIS_DISPOSITIONS`, and `ALLOWED_REPLACEMENT_FRONTMATTER_KEYS`.
- Modify `science/src/science_tool/annotation/cli.py`
  - Add flat command `resynthesis-draft-context`.
  - Support `--format json|markdown`, `--output`, `--root`, and `--input`.
- Modify `science/tests/test_proposition_resynthesis.py`
  - Add unit tests for packet content, constraints, missing-hint failure, annotation-less hint exclusion, partial draft echoing, and markdown rendering.
- Modify `science/tests/test_proposition_reconciliation_cli.py`
  - Add CLI tests for JSON stdout, `--output`, markdown format, and malformed input errors.

Do not add an in-process LLM integration. Do not change the Half D draft schema, validator, apply code, graph materialization, belief aggregation, or archive behavior.

## Task 1: Context Packet Builder

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_resynthesis.py`
- Test: `science/tests/test_proposition_resynthesis.py`

- [ ] **Step 1: Add failing context-packet content test**

Append this test to `science/tests/test_proposition_resynthesis.py` after `test_build_resynthesis_scaffold_emits_identity_context_and_empty_review_fields`:

```python
def test_build_resynthesis_context_packet_expands_scaffold_with_live_context(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(draft_to_json(
        build_resynthesis_scaffold(
            ctx["plan"],
            requested_action_id=ctx["action"].action_id,
            source_review=str(ctx["review_path"]),
            model="codex-gpt-5",
        )
    ))

    packet = build_resynthesis_context_packet(
        tmp_path,
        draft,
        draft_path="resynthesis-draft.json",
    )

    assert packet["schema_version"] == 1
    assert packet["source"] == "derived:proposition-resynthesis-context-v1"
    assert packet["draft_path"] == "resynthesis-draft.json"
    assert packet["action_id"] == ctx["action"].action_id
    assert packet["candidate_id"] == ctx["action"].candidate_id
    assert packet["judgment_id"] == ctx["action"].judgment_id
    assert packet["original_proposition"]["id"] == "proposition:broad"
    assert packet["original_proposition"]["title"] == "BES behaves like pooled meta-analysis"
    assert "Claim body." in packet["original_proposition"]["body"]
    assert packet["original_proposition"]["frontmatter"] == {
        "subject": None,
        "predicate": None,
        "object": None,
        "polarity": None,
        "claim_layer": None,
        "identification_strength": None,
        "source_refs": [
            "paper:A2020",
            "annotation:entities/papers/A2020.source#a1",
            "paper:B2021",
            "annotation:entities/papers/B2021.source#b1",
        ],
    }
    assert packet["review"] == {
        "decision": "factorization_needs_resynthesis",
        "confidence": "high",
        "rationale": "The broad proposition mixes distinct literature claims.",
    }
    assert packet["input_annotations"] == [
        {
            "annotation": "annotation:entities/papers/A2020.source#a1",
            "paper": "paper:A2020",
            "stance": "asserted",
            "section": "results",
            "exact": "a1",
            "subject": None,
            "object": None,
            "subject_concept": None,
            "object_concept": None,
            "current_promoted_to": "proposition:broad",
        },
        {
            "annotation": "annotation:entities/papers/B2021.source#b1",
            "paper": "paper:B2021",
            "stance": "negated",
            "section": "results",
            "exact": "b1",
            "subject": None,
            "object": None,
            "subject_concept": None,
            "object_concept": None,
            "current_promoted_to": "proposition:broad",
        },
    ]
    assert packet["draft_progress"] == {
        "disposition": "replace",
        "new_propositions": [],
        "annotation_assignments": [],
        "notes": "",
    }
    assert packet["constraints"]["required_assignment_annotations"] == [
        "annotation:entities/papers/A2020.source#a1",
        "annotation:entities/papers/B2021.source#b1",
    ]
    assert packet["output_contract"]["validate_with"] == (
        "science annotate validate-proposition-resynthesis --input resynthesis-draft.json"
    )
```

- [ ] **Step 2: Run the new test and confirm RED**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_resynthesis.py::test_build_resynthesis_context_packet_expands_scaffold_with_live_context -q
```

Expected: FAIL with `ImportError` or `AttributeError` because `build_resynthesis_context_packet` does not exist.

- [ ] **Step 3: Add context constants and selected-frontmatter helper**

In `science/src/science_tool/annotation/proposition_resynthesis.py`, after `RESYNTHESIS_SCHEMA_VERSION = 1`, add:

```python
RESYNTHESIS_CONTEXT_SCHEMA_VERSION = 1
RESYNTHESIS_CONTEXT_SOURCE = "derived:proposition-resynthesis-context-v1"
RESYNTHESIS_CONTEXT_FRONTMATTER_KEYS = (
    "subject",
    "predicate",
    "object",
    "polarity",
    "claim_layer",
    "identification_strength",
    "source_refs",
)
```

Then add this helper after `_jsonable`:

```python
def _selected_original_frontmatter(frontmatter: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: _jsonable(frontmatter.get(key))
        for key in RESYNTHESIS_CONTEXT_FRONTMATTER_KEYS
    }
```

- [ ] **Step 4: Add hint-index and context-row helpers**

In `science/src/science_tool/annotation/proposition_resynthesis.py`, after `_current_action_annotations`, add:

```python
def _observed_hint_index(action: ReconciliationAction) -> dict[str, Mapping[str, Any]]:
    raw_hints = action.inputs.get("observed_statement_hints", ())
    if isinstance(raw_hints, str) or not isinstance(raw_hints, Sequence):
        raise ResynthesisDraftError(f"{action.action_id} has malformed observed statement hints")

    by_annotation: dict[str, Mapping[str, Any]] = {}
    for hint in raw_hints:
        if not isinstance(hint, Mapping):
            raise ResynthesisDraftError(f"{action.action_id} has malformed observed statement hints")
        annotation = hint.get("annotation")
        if annotation is None:
            continue
        if not isinstance(annotation, str) or not annotation or annotation != annotation.strip():
            raise ResynthesisDraftError(f"{action.action_id} has malformed observed statement hints")
        if annotation in by_annotation:
            raise ResynthesisDraftError(f"{action.action_id} has duplicate observed hint for {annotation}")
        by_annotation[annotation] = hint
    return by_annotation
```

Then add:

```python
def _context_annotation_row(
    annotation_ref: str,
    hint: Mapping[str, Any],
    *,
    paper_ref: str,
    promoted_to: str | None,
) -> dict[str, Any]:
    return {
        "annotation": annotation_ref,
        "paper": paper_ref,
        "stance": hint.get("stance"),
        "section": hint.get("section"),
        "exact": hint.get("exact"),
        "subject": hint.get("subject"),
        "object": hint.get("object"),
        "subject_concept": hint.get("subject_concept"),
        "object_concept": hint.get("object_concept"),
        "current_promoted_to": promoted_to,
    }
```

Do not add `predicate` to the row. The current reconciliation hint model does not expose a statement predicate.

- [ ] **Step 5: Add `build_resynthesis_context_packet`**

In `science/src/science_tool/annotation/proposition_resynthesis.py`, import `EntityCommandError` and `find_entity` from `science_tool.entities`, then add this after `_context_annotation_row`:

```python
def build_resynthesis_context_packet(
    project_root: Path,
    draft: ResynthesisDraft,
    *,
    draft_path: str | None = None,
) -> dict[str, Any]:
    action = _live_action_for_draft(project_root, draft)
    current_annotations = _current_action_annotations(action)
    if draft.input_annotations != current_annotations:
        raise ResynthesisDraftError("input_annotations are stale")

    try:
        original_location = find_entity(project_root, draft.original_proposition)
    except (EntityCommandError, OSError) as exc:
        raise ResynthesisDraftError(str(exc)) from exc

    hints_by_annotation = _observed_hint_index(action)
    live_index = _live_annotation_index(project_root)
    input_rows: list[dict[str, Any]] = []
    for annotation_ref in current_annotations:
        hint = hints_by_annotation.get(annotation_ref)
        if hint is None:
            raise ResynthesisDraftError(f"{annotation_ref} has no observed statement hint")
        indexed = live_index.get(annotation_ref)
        if indexed is None:
            raise ResynthesisDraftError(f"{annotation_ref} resolves to no live sidecar annotation")
        sidecar_path, _sidecar, promoted_to = indexed
        paper_ref = _resolve_paper_ref(sidecar_path)
        if paper_ref is None:
            raise ResynthesisDraftError(f"{annotation_ref} resolves to no paper ref")
        input_rows.append(
            _context_annotation_row(
                annotation_ref,
                hint,
                paper_ref=paper_ref,
                promoted_to=promoted_to,
            )
        )

    draft_payload = draft_to_json(draft)
    return {
        "schema_version": RESYNTHESIS_CONTEXT_SCHEMA_VERSION,
        "source": RESYNTHESIS_CONTEXT_SOURCE,
        "draft_path": draft_path,
        "action_id": draft.action_id,
        "candidate_id": draft.candidate_id,
        "judgment_id": draft.judgment_id,
        "original_proposition": {
            "id": draft.original_proposition,
            "title": original_location.title,
            "body": original_location.body,
            "frontmatter": _selected_original_frontmatter(original_location.frontmatter),
        },
        "review": {
            "decision": action.decision,
            "confidence": action.confidence,
            "rationale": action.rationale,
        },
        "input_annotations": input_rows,
        "draft_progress": {
            "disposition": draft.disposition,
            "new_propositions": draft_payload["new_propositions"],
            "annotation_assignments": draft_payload["annotation_assignments"],
            "notes": draft.notes,
        },
        "constraints": {
            "allowed_dispositions": sorted(RESYNTHESIS_DISPOSITIONS),
            "required_assignment_annotations": list(current_annotations),
            "replacement_id_prefix": "proposition:",
            "replacement_id_policy": "canonical proposition local part; lowercase words joined by hyphens",
            "allowed_replacement_frontmatter_keys": sorted(ALLOWED_REPLACEMENT_FRONTMATTER_KEYS),
        },
        "output_contract": {
            "write": "a Half D proposition resynthesis draft JSON",
            "validate_with": f"science annotate validate-proposition-resynthesis --input {draft_path or '<draft>'}",
            "do_not_write": ["proposition files", "annotation sidecars", "archive rows"],
        },
    }
```

This function intentionally returns a plain JSON-ready `dict[str, Any]`. Do not add dataclasses unless implementation pressure proves they remove real complexity.

- [ ] **Step 6: Add original-proposition lookup regression test**

Append this test to `science/tests/test_proposition_resynthesis.py` after the Task 1 packet-content test:

```python
def test_resynthesis_context_finds_original_proposition_by_id_not_replacement_path(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    original_path = tmp_path / "entities" / "propositions" / "broad.md"
    relocated_path = tmp_path / "entities" / "propositions" / "legacy" / "broad-legacy-layout.md"
    relocated_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.rename(relocated_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    packet = build_resynthesis_context_packet(tmp_path, draft, draft_path="draft.json")

    assert packet["original_proposition"]["id"] == "proposition:broad"
    assert packet["original_proposition"]["title"] == "BES behaves like pooled meta-analysis"
    assert "Claim body." in packet["original_proposition"]["body"]
```

This regression must fail against any implementation that uses `_replacement_path(project_root, draft.original_proposition)` to locate the original. Existing propositions are found by id with `find_entity`; `_replacement_path` is only for authoring replacement ids.

- [ ] **Step 7: Run the new tests and verify GREEN**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_resynthesis.py::test_build_resynthesis_context_packet_expands_scaffold_with_live_context \
  science/tests/test_proposition_resynthesis.py::test_resynthesis_context_finds_original_proposition_by_id_not_replacement_path -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

Run:

```bash
rtk git add science/src/science_tool/annotation/proposition_resynthesis.py science/tests/test_proposition_resynthesis.py
rtk git commit -m "feat: build resynthesis draft context packet"
```

Expected: commit succeeds. Do not include `Co-Authored-By`.

## Task 2: Context Invariants And Partial Draft Echo

**Files:**
- Modify: `science/tests/test_proposition_resynthesis.py`
- Modify: `science/src/science_tool/annotation/proposition_resynthesis.py` only if tests expose a bug in Task 1 implementation

- [ ] **Step 1: Add constraints/no-timestamps/partial-progress test**

Append this test to `science/tests/test_proposition_resynthesis.py` after the Task 1 test:

```python
def test_resynthesis_context_derives_constraints_has_no_timestamps_and_echoes_progress(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        ALLOWED_REPLACEMENT_FRONTMATTER_KEYS,
        RESYNTHESIS_DISPOSITIONS,
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["notes"] = "Reviewer wants a conservative split."
    draft = parse_resynthesis_draft(payload)

    packet = build_resynthesis_context_packet(tmp_path, draft, draft_path="draft.json")
    encoded = json.dumps(packet, sort_keys=True)

    assert packet["constraints"]["allowed_dispositions"] == sorted(RESYNTHESIS_DISPOSITIONS)
    assert packet["constraints"]["allowed_replacement_frontmatter_keys"] == sorted(
        ALLOWED_REPLACEMENT_FRONTMATTER_KEYS
    )
    assert packet["draft_progress"]["disposition"] == "replace"
    assert packet["draft_progress"]["new_propositions"] == payload["new_propositions"]
    assert packet["draft_progress"]["annotation_assignments"] == payload["annotation_assignments"]
    assert packet["draft_progress"]["notes"] == "Reviewer wants a conservative split."
    assert "2026-07-03" not in encoded
    assert "created" not in packet["original_proposition"]["frontmatter"]
    assert "updated" not in packet["original_proposition"]["frontmatter"]
```

- [ ] **Step 2: Run the test and confirm result**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_resynthesis.py::test_resynthesis_context_derives_constraints_has_no_timestamps_and_echoes_progress -q
```

Expected: PASS.

- [ ] **Step 3: Add missing observed hint defensive-invariant test**

Append this test to `science/tests/test_proposition_resynthesis.py`:

```python
def test_resynthesis_context_rejects_missing_observed_hint_for_input_annotation(
    tmp_path: Path,
    monkeypatch,
):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    draft = parse_resynthesis_draft(payload)
    action = replace(
        ctx["action"],
        inputs={
            **ctx["action"].inputs,
            "observed_statement_hints": tuple(ctx["action"].inputs["observed_statement_hints"][:1]),
        },
    )
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=(str(ctx["review_path"]),), actions=(action,))
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)

    with pytest.raises(ResynthesisDraftError, match="has no observed statement hint"):
        build_resynthesis_context_packet(tmp_path, draft)
```

This is intentionally a plain fail-loud test. Do not build a separate diagnostic object for this path.

- [ ] **Step 4: Add annotation-less hint exclusion test**

Append this test to `science/tests/test_proposition_resynthesis.py`:

```python
def test_resynthesis_context_excludes_annotationless_hints_from_assignment_rows(
    tmp_path: Path,
    monkeypatch,
):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    draft = parse_resynthesis_draft(payload)
    annotationless_hint = {
        "paper": "paper:NoAnnotation2026",
        "stance": "asserted",
        "section": "discussion",
        "subject": "BES",
        "object": "unassignable claim text",
        "subject_concept": None,
        "object_concept": None,
        "exact": "This hint has no annotation ref.",
    }
    action = replace(
        ctx["action"],
        inputs={
            **ctx["action"].inputs,
            "observed_statement_hints": (
                *ctx["action"].inputs["observed_statement_hints"],
                annotationless_hint,
            ),
        },
    )
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=(str(ctx["review_path"]),), actions=(action,))
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)

    packet = build_resynthesis_context_packet(tmp_path, draft)

    assert [row["annotation"] for row in packet["input_annotations"]] == list(payload["input_annotations"])
    assert all(row.get("exact") != "This hint has no annotation ref." for row in packet["input_annotations"])
```

- [ ] **Step 5: Add non-null subject/object hint preservation test**

Append this test to `science/tests/test_proposition_resynthesis.py`:

```python
def test_resynthesis_context_preserves_subject_object_hint_fields(tmp_path: Path, monkeypatch):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    draft = parse_resynthesis_draft(payload)
    hints = tuple(
        {
            **hint,
            "subject": "BES",
            "object": "meta-analysis behavior",
            "subject_concept": "concept:bes",
            "object_concept": "concept:meta-analysis",
        }
        if hint.get("annotation") == "annotation:entities/papers/A2020.source#a1"
        else hint
        for hint in ctx["action"].inputs["observed_statement_hints"]
    )
    action = replace(ctx["action"], inputs={**ctx["action"].inputs, "observed_statement_hints": hints})
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=(str(ctx["review_path"]),), actions=(action,))
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)

    packet = build_resynthesis_context_packet(tmp_path, draft)
    row = packet["input_annotations"][0]

    assert row["annotation"] == "annotation:entities/papers/A2020.source#a1"
    assert row["subject"] == "BES"
    assert row["object"] == "meta-analysis behavior"
    assert row["subject_concept"] == "concept:bes"
    assert row["object_concept"] == "concept:meta-analysis"
```

- [ ] **Step 6: Run the invariant tests and verify GREEN**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_resynthesis.py::test_resynthesis_context_derives_constraints_has_no_timestamps_and_echoes_progress \
  science/tests/test_proposition_resynthesis.py::test_resynthesis_context_rejects_missing_observed_hint_for_input_annotation \
  science/tests/test_proposition_resynthesis.py::test_resynthesis_context_excludes_annotationless_hints_from_assignment_rows \
  science/tests/test_proposition_resynthesis.py::test_resynthesis_context_preserves_subject_object_hint_fields -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
rtk git add science/src/science_tool/annotation/proposition_resynthesis.py science/tests/test_proposition_resynthesis.py
rtk git commit -m "test: pin resynthesis context invariants"
```

Expected: commit succeeds. If no production code changed in this task, the same commit still records the new regression coverage.

## Task 3: Markdown Rendering

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_resynthesis.py`
- Test: `science/tests/test_proposition_resynthesis.py`

- [ ] **Step 1: Add failing markdown rendering test**

Append this test to `science/tests/test_proposition_resynthesis.py`:

```python
def test_resynthesis_context_markdown_renders_same_packet_as_json_block(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
        resynthesis_context_to_markdown,
    )

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    packet = build_resynthesis_context_packet(tmp_path, draft, draft_path="draft.json")

    rendered = resynthesis_context_to_markdown(packet)

    assert rendered.startswith("# Proposition Resynthesis Draft Context\n")
    assert "## Instructions" in rendered
    assert "Do not edit proposition files or annotation sidecars directly." in rendered
    assert "## Context JSON" in rendered
    json_block = rendered.split("```json\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(json_block) == packet
```

- [ ] **Step 2: Run the markdown test and confirm RED**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_resynthesis.py::test_resynthesis_context_markdown_renders_same_packet_as_json_block -q
```

Expected: FAIL with `ImportError` or `AttributeError` because `resynthesis_context_to_markdown` does not exist.

- [ ] **Step 3: Add markdown renderer**

In `science/src/science_tool/annotation/proposition_resynthesis.py`, after `build_resynthesis_context_packet`, add:

```python
def resynthesis_context_to_markdown(packet: Mapping[str, Any]) -> str:
    json_text = json.dumps(packet, indent=2, sort_keys=True)
    return (
        "# Proposition Resynthesis Draft Context\n\n"
        "## Instructions\n\n"
        "- Use this packet to fill a Half D proposition resynthesis draft JSON.\n"
        "- Preserve action identity fields from the draft.\n"
        "- Assign every required input annotation exactly once.\n"
        "- Do not edit proposition files or annotation sidecars directly.\n"
        "- Validate the filled draft with `science annotate validate-proposition-resynthesis`.\n\n"
        "## Context JSON\n\n"
        "```json\n"
        f"{json_text}\n"
        "```\n"
    )
```

This renderer deliberately embeds the exact JSON packet. Do not add markdown-only facts.

- [ ] **Step 4: Run the markdown test and verify GREEN**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_resynthesis.py::test_resynthesis_context_markdown_renders_same_packet_as_json_block -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
rtk git add science/src/science_tool/annotation/proposition_resynthesis.py science/tests/test_proposition_resynthesis.py
rtk git commit -m "feat: render resynthesis context markdown"
```

Expected: commit succeeds.

## Task 4: CLI Command

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Test: `science/tests/test_proposition_reconciliation_cli.py`

- [ ] **Step 1: Add failing JSON CLI stdout test**

Append this test to `science/tests/test_proposition_reconciliation_cli.py` after `test_scaffold_proposition_resynthesis_cli_writes_project_relative_source_review_for_relative_input`:

```python
def test_resynthesis_draft_context_cli_prints_json_packet(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    draft_path = tmp_path / "resynthesis-draft.json"
    draft_path.write_text(json.dumps(_draft_payload(ctx)), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "resynthesis-draft-context",
            "--root",
            str(tmp_path),
            "--input",
            str(draft_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["source"] == "derived:proposition-resynthesis-context-v1"
    assert payload["draft_path"] == "resynthesis-draft.json"
    assert payload["action_id"] == ctx["action"].action_id
    assert payload["original_proposition"]["id"] == "proposition:broad"
    assert [row["annotation"] for row in payload["input_annotations"]] == list(ctx["action"].inputs["annotations"])
```

- [ ] **Step 2: Run the CLI test and confirm RED**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_reconciliation_cli.py::test_resynthesis_draft_context_cli_prints_json_packet -q
```

Expected: FAIL because Click reports no such command `resynthesis-draft-context`.

- [ ] **Step 3: Add CLI command**

In `science/src/science_tool/annotation/cli.py`, insert this command after `scaffold_proposition_resynthesis_cmd` and before `validate_proposition_resynthesis_cmd`:

```python
@annotate_group.command("resynthesis-draft-context")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.option("--format", "fmt", type=click.Choice(("json", "markdown")), default="json")
def resynthesis_draft_context_cmd(
    input_path: Path,
    root: Path | None,
    output_path: Path | None,
    fmt: str,
) -> None:
    """Emit an agent context packet for a proposition resynthesis draft."""
    from science_tool.annotation.proposition_reconciliation import ReconciliationValidationError
    from science_tool.annotation.proposition_resynthesis import (
        ResynthesisDraftError,
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
        resynthesis_context_to_markdown,
    )

    project_root = (root or Path.cwd()).resolve()
    try:
        draft = parse_resynthesis_draft(_read_json_object_for_cli(input_path))
        draft_ref = _project_relative_or_absolute(project_root, input_path)
        packet = build_resynthesis_context_packet(
            project_root,
            draft,
            draft_path=draft_ref,
        )
        if fmt == "json":
            output_text = json.dumps(packet, indent=2, sort_keys=True) + "\n"
        else:
            output_text = resynthesis_context_to_markdown(packet)
    except (
        ResynthesisDraftError,
        ReconciliationValidationError,
        ValueError,
        OSError,
    ) as exc:
        raise click.ClickException(str(exc)) from exc

    if output_path is not None:
        try:
            output_path.write_text(output_text, encoding="utf-8")
        except OSError as exc:
            raise click.ClickException(str(exc)) from exc

    click.echo(output_text, nl=False)
```

This command intentionally prints to stdout even when `--output` is supplied, so callers can inspect exactly what was written.

- [ ] **Step 4: Run the JSON CLI test and verify GREEN**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_reconciliation_cli.py::test_resynthesis_draft_context_cli_prints_json_packet -q
```

Expected: PASS.

- [ ] **Step 5: Add output and markdown CLI tests**

Append these tests to `science/tests/test_proposition_reconciliation_cli.py`:

```python
def test_resynthesis_draft_context_cli_writes_output_and_keeps_stdout(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    draft_path = tmp_path / "resynthesis-draft.json"
    output_path = tmp_path / "resynthesis-context.json"
    draft_path.write_text(json.dumps(_draft_payload(ctx)), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "resynthesis-draft-context",
            "--root",
            str(tmp_path),
            "--input",
            str(draft_path),
            "--output",
            str(output_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    stdout_payload = json.loads(result.output)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    assert file_payload["draft_progress"]["new_propositions"] == _draft_payload(ctx)["new_propositions"]


def test_resynthesis_draft_context_cli_prints_markdown_packet(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    draft_path = tmp_path / "resynthesis-draft.json"
    draft_path.write_text(json.dumps(_draft_payload(ctx)), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "resynthesis-draft-context",
            "--root",
            str(tmp_path),
            "--input",
            str(draft_path),
            "--format",
            "markdown",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output.startswith("# Proposition Resynthesis Draft Context\n")
    assert "```json" in result.output
    assert "annotation:entities/papers/A2020.source#a1" in result.output
```

- [ ] **Step 6: Run the new CLI tests and verify GREEN**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_reconciliation_cli.py::test_resynthesis_draft_context_cli_writes_output_and_keeps_stdout \
  science/tests/test_proposition_reconciliation_cli.py::test_resynthesis_draft_context_cli_prints_markdown_packet -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

Run:

```bash
rtk git add science/src/science_tool/annotation/cli.py science/tests/test_proposition_reconciliation_cli.py
rtk git commit -m "feat: expose resynthesis draft context CLI"
```

Expected: commit succeeds.

## Task 5: CLI Failure Cases And End-To-End Context Loop

**Files:**
- Modify: `science/tests/test_proposition_reconciliation_cli.py`
- Modify: `science/tests/test_proposition_resynthesis.py`
- Modify: production files only if tests reveal mismatches

- [ ] **Step 1: Add malformed JSON CLI error test**

Append this test to `science/tests/test_proposition_reconciliation_cli.py`:

```python
def test_resynthesis_draft_context_cli_includes_input_path_on_malformed_json(tmp_path: Path):
    _factorization_project(tmp_path)
    draft_path = tmp_path / "malformed-context-input.json"
    draft_path.write_text("{not json", encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "resynthesis-draft-context",
            "--root",
            str(tmp_path),
            "--input",
            str(draft_path),
        ],
    )

    assert result.exit_code != 0
    assert str(draft_path) in result.output
    assert "is not valid JSON" in result.output
```

- [ ] **Step 2: Run malformed JSON CLI test**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_reconciliation_cli.py::test_resynthesis_draft_context_cli_includes_input_path_on_malformed_json -q
```

Expected: PASS, because the new command should reuse `_read_json_object_for_cli`.

- [ ] **Step 3: Add stale input-annotation CLI error test**

Append this test to `science/tests/test_proposition_reconciliation_cli.py`:

```python
def test_resynthesis_draft_context_cli_reports_stale_input_annotations(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["input_annotations"] = payload["input_annotations"][:1]
    draft_path = tmp_path / "stale-resynthesis-draft.json"
    draft_path.write_text(json.dumps(payload), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "resynthesis-draft-context",
            "--root",
            str(tmp_path),
            "--input",
            str(draft_path),
        ],
    )

    assert result.exit_code != 0
    assert "input_annotations are stale" in result.output
```

- [ ] **Step 4: Run stale CLI test**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_reconciliation_cli.py::test_resynthesis_draft_context_cli_reports_stale_input_annotations -q
```

Expected: PASS.

- [ ] **Step 5: Add scaffold-context-validate end-to-end unit test**

Append this test to `science/tests/test_proposition_resynthesis.py`:

```python
def test_resynthesis_context_loop_supports_existing_validate_path(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
        validate_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    scaffold = draft_to_json(
        build_resynthesis_scaffold(
            ctx["plan"],
            requested_action_id=ctx["action"].action_id,
            source_review=str(ctx["review_path"]),
            model="codex-gpt-5",
        )
    )
    scaffold_draft = parse_resynthesis_draft(scaffold)
    packet = build_resynthesis_context_packet(tmp_path, scaffold_draft, draft_path="draft.scaffold.json")

    filled = dict(scaffold)
    filled["new_propositions"] = _draft_payload(ctx)["new_propositions"]
    filled["annotation_assignments"] = _draft_payload(ctx)["annotation_assignments"]
    filled["context"] = {
        **filled["context"],
        "resynthesis_context_source": packet["source"],
    }
    draft = parse_resynthesis_draft(filled)
    report = validate_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert report.status == "ok"
    assert report.replacement_propositions == 2
    assert report.moved_annotations == 2
```

This proves the context command does not create a new authoritative artifact. The filled output remains a normal Half D draft.

- [ ] **Step 6: Run Task 5 tests**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_reconciliation_cli.py::test_resynthesis_draft_context_cli_includes_input_path_on_malformed_json \
  science/tests/test_proposition_reconciliation_cli.py::test_resynthesis_draft_context_cli_reports_stale_input_annotations \
  science/tests/test_proposition_resynthesis.py::test_resynthesis_context_loop_supports_existing_validate_path -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

Run:

```bash
rtk git add science/tests/test_proposition_reconciliation_cli.py science/tests/test_proposition_resynthesis.py science/src/science_tool/annotation/proposition_resynthesis.py science/src/science_tool/annotation/cli.py
rtk git commit -m "test: cover resynthesis context CLI failures"
```

Expected: commit succeeds. If no production files changed in this task, Git will commit only tests.

## Task 6: Verification And Real-Corpus Smoke

**Files:**
- No required code changes.
- Optional: update `docs/plans/2026-07-02-phase4e-remaining-work-roadmap.md` only if the implementation also closes the roadmap item during execution. Do not mix roadmap cleanup into this plan unless the implementation branch owner asks for it.

- [ ] **Step 1: Run focused resynthesis tests**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_proposition_resynthesis.py \
  science/tests/test_proposition_resynthesis_apply.py \
  science/tests/test_proposition_reconciliation_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run ruff on touched files**

Run:

```bash
rtk uv run --frozen --project science ruff check \
  science/src/science_tool/annotation/proposition_resynthesis.py \
  science/src/science_tool/annotation/cli.py \
  science/tests/test_proposition_resynthesis.py \
  science/tests/test_proposition_reconciliation_cli.py
```

Expected: PASS.

- [ ] **Step 3: Run pyright on touched modules**

Run:

```bash
rtk uv run --frozen --project science pyright \
  science/src/science_tool/annotation/proposition_resynthesis.py \
  science/src/science_tool/annotation/cli.py
```

Expected: PASS.

- [ ] **Step 4: Run full science test suite**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests -q
```

Expected: PASS. Existing warnings are acceptable; new failures are not.

- [ ] **Step 5: Real-corpus smoke, if a ready review exists**

Look for an existing reviewed factorization input:

```bash
rtk rg -n '"factorization_needs_resynthesis"' results meta/results -g '*.json'
```

If no result exists, record: "real-corpus smoke skipped; no reviewed factorization resynthesis artifact found." If a review exists, choose the first matching JSON file and run the following in a worktree:

```bash
REVIEW_JSON=$(rtk rg -l '"factorization_needs_resynthesis"' results meta/results -g '*.json' | head -n 1)

rtk uv run --frozen --project science science annotate scaffold-proposition-resynthesis \
  --root . \
  --input "$REVIEW_JSON" \
  --output /tmp/science-resynthesis-draft.json \
  --format json

rtk uv run --frozen --project science science annotate resynthesis-draft-context \
  --root . \
  --input /tmp/science-resynthesis-draft.json \
  --output /tmp/science-resynthesis-context.json \
  --format json
```

Expected: either a valid context packet, or a clear stale-review/action error. A stale real-corpus review is not automatically a context-command bug; inspect before changing code.

- [ ] **Step 6: Commit verification notes only if files changed**

If verification required code/test fixes, commit them:

```bash
rtk git add science/src/science_tool/annotation/proposition_resynthesis.py science/src/science_tool/annotation/cli.py science/tests/test_proposition_resynthesis.py science/tests/test_proposition_reconciliation_cli.py
rtk git commit -m "fix: stabilize resynthesis context verification"
```

Expected: commit succeeds only when there are actual changes. If the worktree is clean, skip this commit.

## Acceptance Checklist

- [ ] `science annotate resynthesis-draft-context` exists as a flat annotate command.
- [ ] JSON output is deterministic, timestamp-free, and sorted by CLI serialization.
- [ ] Markdown output embeds the same JSON packet and adds no markdown-only facts.
- [ ] Packet expands draft `original_proposition` string into an object with id, title, body, and selected frontmatter.
- [ ] Packet joins per-annotation hint fields from `observed_statement_hints` by annotation ref.
- [ ] Packet uses live sidecar state only for `current_promoted_to` and paper-ref resolution.
- [ ] Annotation-less hints are excluded from `input_annotations`.
- [ ] Missing hint for an input annotation fails loud with a simple exception.
- [ ] `allowed_dispositions` and `allowed_replacement_frontmatter_keys` are derived from existing Half D constants.
- [ ] Partially filled draft progress is echoed under `draft_progress`.
- [ ] Existing `validate-proposition-resynthesis` and `apply-proposition-resynthesis` semantics are unchanged.
- [ ] No in-process LLM/provider integration is added.
- [ ] No proposition files, sidecars, graph files, belief state, or archive rows are written by the context command.

## Non-Goals

- Do not add a `--apply` flag.
- Do not change `RESYNTHESIS_SCHEMA_VERSION`.
- Do not add a new draft schema.
- Do not add claim-family clustering.
- Do not make context packets graph or belief inputs.
- Do not add compatibility aliases for command names.
