from __future__ import annotations

import json
from pathlib import Path

from science_tool.validate.checks.dataset_metadata import (
    _ALLOWED_CADENCES,
    _ALLOWED_TIERS,
    evaluate_dataset_metadata,
)
from science_tool.validate.result import Severity


def _load_checks_with_dataset_metadata_fresh() -> None:
    """Order-robust canonical registration for the wiring tests below.

    Other validate test modules clear ``CANONICAL_CHECKS`` and reload only subsets,
    so by the time these tests run the registry may lack ``dataset_metadata``. Drop
    the module from the import cache and run the REAL ``_load_canonical_checks``:
    that re-fires its ``@Check`` decorator regardless of prior test order while
    still proving the module is wired into the loader's tuple (a bare ``reload``
    would pass even if it were missing from the loader). Mirrors the reload idiom
    in ``test_runner.py``'s ``_register_real_canonical_checks``.
    """
    import sys

    import science_tool.validate.checks as checks

    checks.clear_checks_for_tests()
    sys.modules.pop("science_tool.validate.checks.dataset_metadata", None)
    checks._load_canonical_checks()


def _rules(datasets: list[dict]) -> list[tuple[Severity, str]]:
    return [(r.severity, r.rule) for r in evaluate_dataset_metadata(datasets)]


def _ds(**kw) -> dict:
    base = {"type": "dataset", "id": "dataset:x", "_path": "entities/datasets/x.md"}
    base.update(kw)
    return base


def test_external_missing_license_warns() -> None:
    assert (Severity.WARN, "dataset.license-missing") in _rules([_ds(origin="external")])


def test_derived_missing_license_is_exempt() -> None:
    rules = _rules([_ds(origin="derived")])
    assert (Severity.WARN, "dataset.license-missing") not in rules


def test_valid_license_passes_silently() -> None:
    assert _rules([_ds(origin="external", license="CC-BY-4.0")]) == []


def test_lgpl_or_later_license_passes_silently() -> None:
    assert _rules([_ds(origin="external", license="LGPL-3.0-or-later")]) == []


def test_sentinel_license_clears_missing_without_unrecognized() -> None:
    assert _rules([_ds(origin="external", license="unknown")]) == []


def test_unrecognized_license_warns() -> None:
    assert (Severity.WARN, "dataset.license-unrecognized") in _rules(
        [_ds(origin="external", license="cc-by-4.0")]
    )


def test_unrecognized_tier_warns() -> None:
    assert (Severity.WARN, "dataset.tier-unrecognized") in _rules(
        [_ds(origin="external", license="MIT", tier="use_now")]
    )


def test_versioned_releases_cadence_is_clean() -> None:
    rules = _rules([_ds(origin="external", license="MIT", update_cadence="versioned-releases")])
    assert (Severity.WARN, "dataset.cadence-unrecognized") not in rules


def test_unrecognized_cadence_warns() -> None:
    assert (Severity.WARN, "dataset.cadence-unrecognized") in _rules(
        [_ds(origin="external", license="MIT", update_cadence="hourly")]
    )


def test_absent_tier_and_cadence_not_flagged() -> None:
    rules = _rules([_ds(origin="external", license="MIT")])
    assert (Severity.WARN, "dataset.tier-unrecognized") not in rules
    assert (Severity.WARN, "dataset.cadence-unrecognized") not in rules


def test_non_dataset_rows_ignored() -> None:
    # evaluate_dataset_metadata yields an iterator — must materialize before comparing.
    assert list(evaluate_dataset_metadata([{"type": "paper", "id": "paper:x", "_path": "p.md"}])) == []


def test_non_string_license_is_unrecognized_not_crash() -> None:
    # license: 123 must not raise AttributeError on .strip(); treat as unrecognized.
    assert (Severity.WARN, "dataset.license-unrecognized") in _rules(
        [_ds(origin="external", license=123)]
    )


def test_non_string_tier_is_unrecognized_not_crash() -> None:
    # tier: [] must not raise TypeError on set membership; treat as unrecognized.
    assert (Severity.WARN, "dataset.tier-unrecognized") in _rules(
        [_ds(origin="external", license="MIT", tier=[])]
    )


def test_non_string_cadence_is_unrecognized_not_crash() -> None:
    assert (Severity.WARN, "dataset.cadence-unrecognized") in _rules(
        [_ds(origin="external", license="MIT", update_cadence=[1])]
    )


def test_module_is_registered() -> None:
    # The new module must be wired into _load_canonical_checks's tuple or it
    # silently never runs. Run the real loader (order-robust) and assert membership.
    from science_tool.validate.checks import CANONICAL_CHECKS

    _load_checks_with_dataset_metadata_fresh()
    assert any(entry.fn.__module__.endswith("dataset_metadata") for entry in CANONICAL_CHECKS)


def test_license_missing_surfaces_through_runner(tmp_path: Path) -> None:
    # End-to-end: the finding must appear in a real validate run, not just in
    # the pure core. Proves wiring (registration + raw-frontmatter discovery).
    from science_tool.validate.runner import run

    _load_checks_with_dataset_metadata_fresh()
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    ds_dir = tmp_path / "entities" / "datasets"
    ds_dir.mkdir(parents=True)
    (ds_dir / "x.md").write_text(
        '---\n'
        'id: "dataset:x"\n'
        'type: "dataset"\n'
        'title: "X"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'ontology_terms: []\n'
        '---\n\n# X\n',
        encoding="utf-8",
    )

    result = run(tmp_path, strict=False, verbose=False, enable_python_sidecar=False)

    assert any(r.rule == "dataset.license-missing" for r in result.results)


def _schema(name: str) -> dict:
    path = Path(__file__).resolve().parents[2] / "model/src/science_model/schemas" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_cadence_vocabulary_equals_schema_enum() -> None:
    # The check's cadence set must equal the authoritative schema enum (minus "")
    # so a value cannot pass the check yet fail schema validation, or vice versa.
    enum = set(_schema("science-pkg-entity-1.0.json")["properties"]["update_cadence"]["enum"]) - {""}
    assert _ALLOWED_CADENCES == enum


def test_tier_vocabulary_agrees_across_both_schema_surfaces() -> None:
    # tier must agree across the check and BOTH schema surfaces (legacy pkg-entity
    # and the mixin profile), per the spec's schema-sync requirement.
    pkg_tier = set(_schema("science-pkg-entity-1.0.json")["properties"]["tier"]["enum"])
    mixin_tier = set(_schema("mixin-dataset-1.0.json")["properties"]["tier"]["enum"])
    assert _ALLOWED_TIERS == pkg_tier == mixin_tier
