from pathlib import Path

from science_tool.validate.runner import run


def test_legacy_sidecar_finding_is_owned_by_runtime_producer(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    (tmp_path / "validate.local.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    result = run(tmp_path, strict=False, verbose=False)
    runtime = result.producer_results["validate.runtime"]
    assert "validate.sidecar-removed" in [
        item.rule_id for item in runtime.instrument.rows
    ]
