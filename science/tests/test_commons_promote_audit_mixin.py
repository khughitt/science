"""Audit-log shape extension for mixin_extensions."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml
from science_model.entity_schema.profile import ProfileComponent

from science_tool.commons.promote import (
    PROMOTE_KIND_DATASET,
    PromoteResult,
    _render_audit_log_yaml,
)


def _empty_result(mixin_extensions: tuple[ProfileComponent, ...] = ()) -> PromoteResult:
    now = datetime.now(timezone.utc)
    return PromoteResult(
        op_id="op-test",
        started_at=now,
        finished_at=now,
        commons_commit=None,
        tags_created=[],
        decisions=[],
        failed_candidates=[],
        audit_log_path=None,
        status="ok",
        failure_stage=None,
        failure_detail=None,
        projects_touched=[],
        kind=PROMOTE_KIND_DATASET,
        mixin_extensions=mixin_extensions,
    )


def test_audit_log_omits_mixin_extensions_when_empty(tmp_path: Path) -> None:
    yaml_text = _render_audit_log_yaml(_empty_result(), tmp_path, invocation="x")
    parsed = yaml.safe_load(yaml_text)
    assert "mixin_extensions" not in parsed


def test_audit_log_emits_mixin_extensions_when_non_empty(tmp_path: Path) -> None:
    extensions = (
        ProfileComponent(name="bio.matrix", version="1.0"),
        ProfileComponent(name="bio.rnaseq", version="1.0"),
    )
    yaml_text = _render_audit_log_yaml(
        _empty_result(extensions), tmp_path, invocation="x"
    )
    parsed = yaml.safe_load(yaml_text)
    assert parsed["mixin_extensions"] == ["bio.matrix/1.0", "bio.rnaseq/1.0"]
