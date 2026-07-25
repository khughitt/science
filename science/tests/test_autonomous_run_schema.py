from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.sources import load_project_sources

RUN_ID = "run:2026-07-24-curation-sweep-a3f1"

# Both armed generations, and they resolve hypotheses through DIFFERENT mixin files:
# generation 2 -> mixin-hypothesis-1.0.json, generation 3 -> mixin-hypothesis-2.0.json.
ARMED_GENERATIONS = (2, 3)


def _write_project(root: Path, *, generation: int, extra: str = "") -> None:
    (root / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n"
        f"entity_schema_version: {generation}\n",
        encoding="utf-8",
    )
    hypotheses = root / "entities" / "hypotheses"
    hypotheses.mkdir(parents=True, exist_ok=True)
    # `created`/`updated` MUST be quoted. Unquoted, YAML yields `datetime.date`, the
    # string-typed subschema fails, and `unevaluatedProperties` then reports the field
    # as unexpected -- a confusing error with a simple cause. Verified against the loader.
    (hypotheses / "h01.md").write_text(
        "---\n"
        "id: hypothesis:h01\n"
        "kind: hypothesis\n"
        "title: Demo hypothesis\n"
        "status: active\n"
        'created: "2026-07-24"\n'
        'updated: "2026-07-24"\n'
        f"{extra}"
        "---\n\nBody.\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("generation", ARMED_GENERATIONS)
def test_pinned_hypothesis_accepts_autonomous_run(tmp_path: Path, generation: int) -> None:
    # `hypothesis` is the one project mixin validated strictly
    # (PROJECT_MIXIN_NAMES, entity_schema/profile.py:24), so an undeclared key here is a
    # hard load failure -- not a preserved extra as on every other kind.
    _write_project(tmp_path, generation=generation, extra=f"autonomous_run: {RUN_ID}\n")
    sources = load_project_sources(tmp_path)
    entity = next(e for e in sources.entities if e.canonical_id == "hypothesis:h01")
    assert entity.autonomous_run == RUN_ID


@pytest.mark.parametrize("generation", ARMED_GENERATIONS)
def test_pinned_hypothesis_without_the_field_still_loads(tmp_path: Path, generation: int) -> None:
    _write_project(tmp_path, generation=generation)
    sources = load_project_sources(tmp_path)
    assert sources.entities[0].autonomous_run is None
