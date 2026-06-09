# tests/validate/test_aggregate_retired_gate.py
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.validate.checks.aggregate_retired import check_aggregate_retired_at_v3
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _ctx(root: Path, layout_version: int, terms: list[dict]) -> ValidateContext:
    (root / "science.yaml").write_text(
        f"name: demo\nprofile: research\nprofiles: {{local: local}}\nlayout_version: {layout_version}\n",
        encoding="utf-8",
    )
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    (src / "terms.yaml").write_text(yaml.safe_dump({"terms": terms}), encoding="utf-8")
    # Real constructor: ValidateContext.from_project_root(root, *, strict, verbose)
    # — the dataclass __init__ requires many fields, so use the factory.
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def test_v3_residual_aggregate_row_is_error(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, 3, [{"id": "question:open-thing", "title": "Open Thing"}])
    results = list(check_aggregate_retired_at_v3(ctx))
    assert results, "expected an ERROR for a residual aggregate row at v3"
    assert all(r.severity is Severity.ERROR for r in results)
    assert any("question:open-thing" in (r.message or "") for r in results)


def test_v2_residual_aggregate_row_is_silent(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, 2, [{"id": "question:open-thing", "title": "Open Thing"}])
    assert list(check_aggregate_retired_at_v3(ctx)) == []


def test_v3_no_aggregate_rows_is_clean(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n", encoding="utf-8"
    )
    (tmp_path / "knowledge" / "sources" / "local").mkdir(parents=True)
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    assert list(check_aggregate_retired_at_v3(ctx)) == []


def test_v3_single_type_aggregate_stays_clean(tmp_path: Path) -> None:
    # A single-type aggregate (doc/<plural>/<plural>.yaml is a bare LIST of rows) is
    # ALSO discovered by AggregateAdapter and marked deprecated, but 4c only retires
    # multi-type (entities.yaml/terms.yaml) rows -- so the v3 gate must NOT flag it.
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n", encoding="utf-8"
    )
    (tmp_path / "knowledge" / "sources" / "local").mkdir(parents=True)
    topics_dir = tmp_path / "doc" / "topics"
    topics_dir.mkdir(parents=True)
    (topics_dir / "topics.yaml").write_text(
        yaml.safe_dump([{"id": "topic:legacy-thing", "title": "Legacy Thing"}]), encoding="utf-8"
    )
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    assert list(check_aggregate_retired_at_v3(ctx)) == []
