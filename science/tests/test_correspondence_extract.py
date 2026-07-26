from science_tool.correspondence.extract import (
    Deliverable,
    Polarity,
    extract_deliverables,
    extract_task_refs,
)


def _declared(body: str) -> str:
    return f"## Deliverables\n\n{body}"


def _paths(body: str) -> list[str]:
    return [d.path for d in extract_deliverables(body)]


# --- the declared region (fb-2026-07-26-015) ---


def test_extracts_backticked_code_paths_from_the_declared_region():
    body = _declared("Add `src/foo/bar.py` and `tests/test_bar.py`.\n")
    assert _paths(body) == ["src/foo/bar.py", "tests/test_bar.py"]


def test_deduplicates_preserving_first_occurrence_order():
    body = _declared("`b/y.py` then `a/x.py` then `b/y.py` again\n")
    assert _paths(body) == ["b/y.py", "a/x.py"]


def test_extracts_supported_extensions_only():
    body = _declared("`a/b.py` `c/d.ts` `e/f.md` `g/h.yaml` `i/j.json` `k/l.png` `m/n.exe`\n")
    assert _paths(body) == ["a/b.py", "c/d.ts", "e/f.md", "g/h.yaml", "i/j.json"]


def test_a_plan_with_no_declared_region_declares_nothing():
    """0097-meta-model-v0-3-consolidation: an honest draft whose only paths were
    inputs cited under `### Task N` headings, adjudicated COMPLETE against them."""
    body = (
        "## Background\n\nSee `doc/architecture/spec.md`.\n\n"
        "### Task 1: extend it\n\nEdit `doc/architecture/spec.md` and `src/a.py`.\n"
    )
    assert extract_deliverables(body) == []


def test_a_declared_region_naming_no_path_declares_nothing():
    """0037-provenance-schema-integration-plan: it HAS `## Suggested deliverables`,
    and that section contains no paths -- the screen read its reading list instead."""
    body = (
        "## Recommended reading order\n\n`specs/design.md`\n`src/a.ts`\n\n"
        "## Suggested deliverables\n\nA migration note and a decision record.\n"
    )
    assert extract_deliverables(body) == []


def test_paths_outside_the_declared_region_are_not_deliverables():
    body = (
        "## Preconditions\n\nRead `src/precondition.py`.\n\n"
        "## Deliverables\n\n- `src/built.py`\n\n"
        "## Background\n\nCompare with `src/background.py`.\n"
    )
    assert _paths(body) == ["src/built.py"]


def test_a_subsection_of_the_declared_region_is_part_of_it():
    body = "## Deliverables\n\n### Phase 1\n\n`src/a.py`\n\n### Phase 2\n\n`src/b.py`\n\n## Risks\n\n`src/c.py`\n"
    assert _paths(body) == ["src/a.py", "src/b.py"]


def test_every_declared_region_contributes():
    body = "## Outputs\n\n`src/a.py`\n\n## Notes\n\n`src/z.py`\n\n## Required Output Artifacts\n\n`src/b.py`\n"
    assert _paths(body) == ["src/a.py", "src/b.py"]


def test_a_heading_that_merely_mentions_the_word_is_not_a_declaration():
    """Measured false friends from the corpus."""
    for heading in (
        "## Task 7: regenerate artifacts + final verification",
        "## What the output is and is not",
        "### Regenerated output (no manual edits)",
        "## Task 4: Define candidate schema and sidecar output format",
    ):
        assert extract_deliverables(f"{heading}\n\n`src/a.py`\n") == [], heading


def test_the_declaration_forms_the_corpus_actually_uses_are_admitted():
    for heading in (
        "## Deliverables",
        "## Suggested deliverables",
        "## Required Output Artifacts",
        "## Outputs",
        "## Workflow Outputs",
        "## t552 Deliverables",
        "## Shared Deliverables",
    ):
        assert _paths(f"{heading}\n\n`src/a.py`\n") == ["src/a.py"], heading


def test_ignores_bare_filenames_without_a_directory():
    """`foo.py` cannot be resolved to a location -- it is ambiguous, not absent."""
    assert extract_deliverables(_declared("see `foo.py` somewhere\n")) == []


def test_ignores_prose_in_backticks():
    assert extract_deliverables(_declared("the `status` field and `--apply` flag\n")) == []


# --- polarity (fb-2026-07-26-014) ---


def test_a_build_region_declares_create_polarity():
    assert extract_deliverables(_declared("`src/a.py`\n")) == [
        Deliverable(path="src/a.py", polarity=Polarity.CREATE)
    ]


def test_a_removal_region_declares_remove_polarity():
    body = "## Retirement targets\n\n`src/old.ts`\n"
    assert extract_deliverables(body) == [
        Deliverable(path="src/old.ts", polarity=Polarity.REMOVE)
    ]


def test_build_and_removal_regions_coexist():
    body = "## Deliverables\n\n`src/new.py`\n\n## Deliverables to remove\n\n`src/old.py`\n"
    assert extract_deliverables(body) == [
        Deliverable(path="src/new.py", polarity=Polarity.CREATE),
        Deliverable(path="src/old.py", polarity=Polarity.REMOVE),
    ]


def test_first_declaration_of_a_path_wins():
    body = "## Deliverables\n\n`src/a.py`\n\n## Removed artifacts\n\n`src/a.py`\n"
    assert extract_deliverables(body) == [
        Deliverable(path="src/a.py", polarity=Polarity.CREATE)
    ]


# --- task refs (unchanged) ---


def test_extracts_task_refs():
    assert extract_task_refs("closes `task:t254` and task:t007\n") == ["t254", "t007"]


def test_task_refs_deduplicated():
    assert extract_task_refs("task:t1 task:t1 task:t2\n") == ["t1", "t2"]


def test_no_task_refs_returns_empty():
    assert extract_task_refs("no tasks here\n") == []


def test_task_refs_are_read_from_the_whole_body():
    """Unlike deliverables, a task ref names an entity rather than making a claim
    about the tree, so it is not scoped to the declared region."""
    assert extract_task_refs("## Goal\n\nCloses task:t254.\n") == ["t254"]
