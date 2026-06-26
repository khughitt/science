"""Tests for the `verify_access` writer (backs `science dataset verify-access`).

Covers the coupled origin/license/access edit, the verified and exception
branches, idempotent re-review, and the path-independent license rule.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from science_model.frontmatter import parse_frontmatter
from science_tool.dataset_prioritize import readiness_for, readiness_weight
from science_tool.datasets_catalog import verify_access
from science_tool.entities import EntityCommandError
from science_tool.validate.checks.dataset_metadata import evaluate_dataset_metadata

DATE = date(2026, 6, 24)
DATE2 = date(2026, 7, 1)


def _write(root: Path, slug: str, fm: dict, body: str = "# Body\n\nlegacy entity.\n") -> Path:
    dest = root / "entities" / "datasets" / f"{slug}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
    dest.write_text(f"---\n{front}---\n\n{body}", encoding="utf-8")
    return dest


def _legacy(root: Path, slug: str = "foo", **overrides) -> Path:
    """A legacy dataset entity: source_class but no origin/license/access/tier."""
    fm = {
        "id": f"dataset:{slug}",
        "type": "dataset",
        "title": slug.title(),
        "status": "candidate",
        "source_class": "observational",
        "created": "2026-01-01",
        "updated": "2026-01-01",
    }
    fm.update(overrides)
    return _write(root, slug, fm)


def _read(dest: Path) -> tuple[dict, str]:
    parsed = parse_frontmatter(dest)
    assert parsed is not None
    return parsed


def test_verify_access_backfills_all_coupled_fields(tmp_path: Path) -> None:
    _legacy(tmp_path)
    verify_access(
        tmp_path, "foo",
        level="public", method="retrieved", license_="CC0-1.0",
        note="landing page public", today=DATE,
    )
    fm, body = _read(tmp_path / "entities" / "datasets" / "foo.md")
    assert fm["origin"] == "external"
    assert fm["dataset_class"] == "deposit"
    assert fm["license"] == "CC0-1.0"
    access = fm["access"]
    assert access["level"] == "public"
    assert access["availability"] == "available"
    assert access["verified"] is True
    assert access["verification_method"] == "retrieved"
    assert access["last_reviewed"] == DATE.isoformat()
    assert access["verified_by"] == "agent (verify-access)"
    assert "## Access verification log" in body
    assert "2026-06-24" in body
    assert "landing page public" in body


def test_verify_access_preserves_existing_dataset_class(tmp_path: Path) -> None:
    _legacy(
        tmp_path,
        dataset_class="reference",
        license="MIT",
        access={"level": "public", "verified": False, "source_url": "https://example.org/foo"},
    )

    verify_access(tmp_path, "foo", level="public", method="landing-confirmed", today=DATE)

    fm, _body = _read(tmp_path / "entities" / "datasets" / "foo.md")
    assert fm["dataset_class"] == "reference"


def test_verify_access_sets_dataset_class_when_requested(tmp_path: Path) -> None:
    _legacy(tmp_path, license="MIT")

    verify_access(
        tmp_path,
        "foo",
        dataset_class="reference",
        level="public",
        method="landing-confirmed",
        source_url="https://example.org/foo",
        today=DATE,
    )

    fm, _body = _read(tmp_path / "entities" / "datasets" / "foo.md")
    assert fm["dataset_class"] == "reference"
    assert fm["access"]["source_url"] == "https://example.org/foo"


def test_verify_access_rejects_method_class_mismatch(tmp_path: Path) -> None:
    _legacy(tmp_path, license="MIT")

    with pytest.raises(EntityCommandError, match="retrieved"):
        verify_access(
            tmp_path,
            "foo",
            dataset_class="reference",
            method="retrieved",
            source_url="https://example.org/foo",
            today=DATE,
        )

    with pytest.raises(EntityCommandError, match="landing-confirmed"):
        verify_access(tmp_path, "foo", dataset_class="deposit", method="landing-confirmed", today=DATE)


def test_verify_access_reference_requires_source_url(tmp_path: Path) -> None:
    _legacy(tmp_path, license="MIT")

    with pytest.raises(EntityCommandError, match="source-url"):
        verify_access(tmp_path, "foo", dataset_class="reference", method="landing-confirmed", today=DATE)


def test_verify_access_yields_available_readiness(tmp_path: Path) -> None:
    _legacy(tmp_path)
    _id, _dest, state, weight, _warnings = verify_access(
        tmp_path, "foo", level="public", method="retrieved", license_="CC0-1.0", today=DATE,
    )
    assert state == "available"
    assert weight == 1.0
    fm, _ = _read(tmp_path / "entities" / "datasets" / "foo.md")
    assert readiness_for(fm).state == "available"
    assert readiness_weight(fm)[0] == 1.0


def test_verify_access_clean_under_dataset_metadata_check(tmp_path: Path) -> None:
    _legacy(tmp_path)
    verify_access(
        tmp_path, "foo", level="public", method="retrieved",
        license_="CC0-1.0", tier="use-now", today=DATE,
    )
    fm, _ = _read(tmp_path / "entities" / "datasets" / "foo.md")
    rules = {r.rule for r in evaluate_dataset_metadata([fm])}
    assert "dataset.license-missing" not in rules
    assert "dataset.tier-unrecognized" not in rules


def test_verify_access_idempotent_rereview(tmp_path: Path) -> None:
    _legacy(tmp_path)
    verify_access(tmp_path, "foo", level="public", method="retrieved",
                  license_="CC0-1.0", note="first", today=DATE)
    verify_access(tmp_path, "foo", method="retrieved", note="second", today=DATE2)
    fm, body = _read(tmp_path / "entities" / "datasets" / "foo.md")
    assert fm["access"]["last_reviewed"] == DATE2.isoformat()
    assert fm["access"]["verified"] is True
    assert fm["license"] == "CC0-1.0"  # preserved, no --license on 2nd call
    assert body.count("Access verification log") == 1  # one section
    assert "first" in body and "second" in body  # two log lines


def test_verify_access_preserves_existing_license_without_flag(tmp_path: Path) -> None:
    _legacy(tmp_path, license="MIT")
    verify_access(tmp_path, "foo", level="public", method="retrieved", today=DATE)
    fm, _ = _read(tmp_path / "entities" / "datasets" / "foo.md")
    assert fm["license"] == "MIT"


def test_verify_access_requires_license_when_none_known(tmp_path: Path) -> None:
    _legacy(tmp_path)
    with pytest.raises(EntityCommandError, match="--license"):
        verify_access(tmp_path, "foo", level="public", method="retrieved", today=DATE)


def test_verify_access_exception_requires_license_when_none_known(tmp_path: Path) -> None:
    # Path-independent: the exception branch still lands origin: external.
    _legacy(tmp_path)
    with pytest.raises(EntityCommandError, match="--license"):
        verify_access(tmp_path, "foo", exception="scope-reduced", rationale="defer", today=DATE)


def test_verify_access_exception_branch(tmp_path: Path) -> None:
    _legacy(tmp_path)
    _id, _dest, state, _weight, _warnings = verify_access(
        tmp_path, "foo", exception="scope-reduced", license_="unknown",
        rationale="defer", followup_task="task:t1", today=DATE,
    )
    fm, _ = _read(tmp_path / "entities" / "datasets" / "foo.md")
    exc = fm["access"]["exception"]
    assert exc["mode"] == "scope-reduced"
    assert exc["decision_date"] == DATE.isoformat()
    assert exc["followup_task"] == "task:t1"
    assert fm["access"]["verified"] is False
    assert state == "consumable-via-scope-reduced"


def test_verify_access_exception_clears_existing_verified(tmp_path: Path) -> None:
    _legacy(tmp_path)
    verify_access(tmp_path, "foo", level="public", method="retrieved",
                  license_="CC0-1.0", today=DATE)
    # Now convert to an exception decision — verified must clear.
    verify_access(tmp_path, "foo", exception="scope-reduced", rationale="defer", today=DATE2)
    fm, _ = _read(tmp_path / "entities" / "datasets" / "foo.md")
    assert fm["access"]["verified"] is False
    assert fm["access"]["exception"]["mode"] == "scope-reduced"
    # Conversely, the verified path clears a prior exception mode.
    verify_access(tmp_path, "foo", method="retrieved", today=DATE2)
    fm, _ = _read(tmp_path / "entities" / "datasets" / "foo.md")
    assert fm["access"]["verified"] is True
    assert fm["access"]["exception"]["mode"] == ""


def test_verify_access_refuses_derived(tmp_path: Path) -> None:
    _legacy(
        tmp_path, "der",
        origin="derived",
        source_class="derived",
        derived_kind="aggregate",
        derivation={"kind": "member_of", "parent_dataset": "dataset:p", "member_key": "k"},
    )
    with pytest.raises(EntityCommandError, match="register-run"):
        verify_access(tmp_path, "der", method="retrieved", license_="CC0-1.0", today=DATE)


def test_verify_access_unknown_slug(tmp_path: Path) -> None:
    (tmp_path / "entities" / "datasets").mkdir(parents=True)
    with pytest.raises(EntityCommandError):
        verify_access(tmp_path, "nope", method="retrieved", license_="CC0-1.0", today=DATE)
