from __future__ import annotations

from science_tool.project_package.serialize import SOURCE_ROOTS


def test_runs_is_a_serialize_source_root() -> None:
    # Without this, a serialized project keeps entities whose `autonomous_run`
    # references nothing — the claims travel and the attestations do not.
    assert "runs" in SOURCE_ROOTS
