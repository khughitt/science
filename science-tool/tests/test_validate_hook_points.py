"""Hook dispatch points exist in the canonical and fire in the documented order."""

from importlib import resources
from pathlib import Path


def _canonical_path() -> Path:
    files = resources.files("science_tool.project_artifacts")
    with resources.as_file(files / "data" / "validate.sh") as p:
        return Path(p)


def test_canonical_dispatches_pre_validation_once() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    assert text.count('dispatch_hook "pre_validation"') == 1, (
        "expected exactly one pre_validation dispatch site in the canonical"
    )


def test_canonical_dispatches_extra_checks_once() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    assert text.count('dispatch_hook "extra_checks"') == 1, (
        "expected exactly one extra_checks dispatch site in the canonical"
    )


def test_canonical_traps_post_validation_on_exit() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    assert "trap 'dispatch_hook post_validation' EXIT" in text, "expected EXIT trap dispatching post_validation"


def test_pre_validation_fires_before_section_1() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    pre_pos = text.find('dispatch_hook "pre_validation"')
    sec1_pos = text.find("# ─── 1. Project manifest")
    assert pre_pos > 0 and sec1_pos > 0, "missing markers"
    assert pre_pos < sec1_pos, "pre_validation must dispatch before section 1"


def test_extra_checks_fires_before_summary() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    extra_pos = text.find('dispatch_hook "extra_checks"')
    summary_pos = text.find("# ─── Summary")
    assert extra_pos > 0 and summary_pos > 0, "missing markers"
    assert extra_pos < summary_pos, "extra_checks must dispatch before the summary"


def test_post_validation_trap_set_after_sidecar_source() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    sidecar_pos = text.find('source "validate.local.sh"')
    trap_pos = text.find("trap 'dispatch_hook post_validation' EXIT")
    assert sidecar_pos > 0 and trap_pos > 0, "missing markers"
    assert trap_pos > sidecar_pos, "EXIT trap must be set AFTER sidecar source so registered hooks are visible"
