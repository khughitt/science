"""A pre-registration freezes its vehicle by CONTENT, never by path.

The natural-systems t830 incident (fb-2026-07-11-024): pre-registration:0026
locked its vehicle as a path that was in `.gitignore`. The "frozen" vehicle was
an untracked build product whose content was a pure function of the working
tree, so re-running the registered pipeline regenerated it and destroyed the
registered export irrecoverably.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from science_tool.validate.checks.prereg_vehicles import check_prereg_vehicles
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A real git repository laid out like a Science project."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "science.yaml").write_text("name: f\nprofile: research\n", encoding="utf-8")
    (tmp_path / "entities" / "pre-registrations").mkdir(parents=True)
    return tmp_path


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_vehicle(root: Path, relative: str, content: str = "payload\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_prereg(
    root: Path,
    name: str = "0001-a.md",
    *,
    status: str = "committed",
    vehicles: str = "",
    body: str = "",
) -> None:
    frontmatter = ["---", "kind: pre-registration", f"status: {status}"]
    if vehicles:
        frontmatter.append(vehicles)
    frontmatter.append("---")
    text = "\n".join([*frontmatter, "", "## Hypotheses Under Test", body])
    root.joinpath("entities", "pre-registrations", name).write_text(text, encoding="utf-8")


def _rules(results: list[Result]) -> list[str]:
    return [result.rule or "" for result in results]


def _vehicle_block(path: str, digest: str) -> str:
    return f'vehicles:\n  - path: "{path}"\n    sha256: "{digest}"'


def test_gitignored_vehicle_is_an_error(project: Path) -> None:
    """The t830 incident itself: a vehicle under a gitignored build directory."""
    project.joinpath(".gitignore").write_text("pipeline/**/data/\n", encoding="utf-8")
    vehicle = _write_vehicle(project, "pipeline/graph-analysis/data/graph-export.json")
    _write_prereg(
        project,
        vehicles=_vehicle_block("pipeline/graph-analysis/data/graph-export.json", _sha256(vehicle)),
    )

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-gitignored"]
    assert results[0].severity.value == "error"
    assert "graph-export.json" in results[0].message
    assert results[0].path is not None and not results[0].path.is_absolute()


def test_gitignored_vehicle_under_data_is_still_an_error(project: Path) -> None:
    """`data/` is gitignored by design, which is exactly why it cannot freeze a vehicle.

    A vehicle living there must be declared as a content-addressed dataset
    entity; the payload directory alone confers no durability.
    """
    project.joinpath(".gitignore").write_text("data/\n", encoding="utf-8")
    vehicle = _write_vehicle(project, "data/graph-export.json")
    _write_prereg(project, vehicles=_vehicle_block("data/graph-export.json", _sha256(vehicle)))

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-gitignored"]


def test_committed_vehicle_with_matching_hash_passes(project: Path) -> None:
    vehicle = _write_vehicle(project, "inputs/graph-export.json")
    _git(project, "add", "inputs/graph-export.json")
    _git(project, "commit", "-qm", "add vehicle")
    _write_prereg(project, vehicles=_vehicle_block("inputs/graph-export.json", _sha256(vehicle)))

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_hash_drift_is_an_error(project: Path) -> None:
    """The registered content is gone even though the path still resolves."""
    vehicle = _write_vehicle(project, "inputs/graph-export.json", "244 models\n")
    _git(project, "add", "inputs/graph-export.json")
    _git(project, "commit", "-qm", "add vehicle")
    registered = _sha256(vehicle)
    vehicle.write_text("248 models\n", encoding="utf-8")
    _write_prereg(project, vehicles=_vehicle_block("inputs/graph-export.json", registered))

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-hash-drift"]
    assert registered[:12] in results[0].message


def test_untracked_vehicle_is_an_error(project: Path) -> None:
    """Not ignored, but never committed — still not durable."""
    vehicle = _write_vehicle(project, "inputs/graph-export.json")
    _write_prereg(project, vehicles=_vehicle_block("inputs/graph-export.json", _sha256(vehicle)))

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-untracked"]


def test_absent_vehicle_is_an_error(project: Path) -> None:
    _write_prereg(project, vehicles=_vehicle_block("inputs/gone.json", "0" * 64))

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-missing"]


def test_vehicle_without_sha256_is_an_error(project: Path) -> None:
    """A path alone is the defect: freezing by path is what failed."""
    _write_vehicle(project, "inputs/graph-export.json")
    _git(project, "add", "inputs/graph-export.json")
    _git(project, "commit", "-qm", "add vehicle")
    _write_prereg(project, vehicles='vehicles:\n  - path: "inputs/graph-export.json"')

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-uncontent-addressed"]


def test_committed_prereg_declaring_no_vehicle_warns(project: Path) -> None:
    """Grandfathered: WARN, so the existing corpus does not turn red retroactively."""
    _write_prereg(project)

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-undeclared"]
    assert results[0].severity.value == "warn"


def test_data_gated_prereg_declaring_no_vehicle_is_silent(project: Path) -> None:
    """Data-gated mode commits the decision rule before any vehicle is admissible."""
    _write_prereg(project, body="## Vehicle-Admissibility Gate (data-gated mode)\n")

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_uncommitted_prereg_declaring_no_vehicle_is_silent(project: Path) -> None:
    """The freeze obligation attaches at commit time, not while drafting."""
    _write_prereg(project, status="active")

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_vehicles_outside_a_git_repository_are_reported_unverifiable(tmp_path: Path) -> None:
    """Never claim a vehicle is frozen when durability could not be checked at all."""
    tmp_path.joinpath("science.yaml").write_text("name: f\nprofile: research\n", encoding="utf-8")
    tmp_path.joinpath("entities", "pre-registrations").mkdir(parents=True)
    _write_vehicle(tmp_path, "inputs/graph-export.json")
    _write_prereg(tmp_path, vehicles=_vehicle_block("inputs/graph-export.json", "0" * 64))

    results = list(check_prereg_vehicles(_ctx(tmp_path)))

    assert _rules(results) == ["prereg.vehicle-unverifiable"]


def test_durability_failures_gate_the_build_but_undeclared_does_not() -> None:
    """The four durability defects fail closed; the grandfathered WARN does not.

    Gating these is safe only because the corpus produces zero findings on them
    today — see the note in gates.py.
    """
    from science_tool.validate.gates import cumulative_rules

    gated = cumulative_rules("hygiene")
    assert "prereg.vehicle-gitignored" in gated
    assert "prereg.vehicle-untracked" in gated
    assert "prereg.vehicle-hash-drift" in gated
    assert "prereg.vehicle-missing" in gated
    assert "prereg.vehicle-uncontent-addressed" in gated
    assert "prereg.vehicle-undeclared" not in gated
    assert "prereg.vehicle-unverifiable" not in gated


def test_non_prereg_entities_are_ignored(project: Path) -> None:
    project.joinpath("entities", "pre-registrations", "README.md").write_text(
        "---\nkind: note\n---\n", encoding="utf-8"
    )

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_every_declared_vehicle_is_reported(project: Path) -> None:
    """One finding per vehicle — not one per document."""
    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    first = _write_vehicle(project, "build/a.json")
    second = _write_vehicle(project, "build/b.json")
    _write_prereg(
        project,
        vehicles=(
            f'vehicles:\n  - path: "build/a.json"\n    sha256: "{_sha256(first)}"\n'
            f'  - path: "build/b.json"\n    sha256: "{_sha256(second)}"'
        ),
    )

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-gitignored", "prereg.vehicle-gitignored"]
    assert "build/a.json" in results[0].message
    assert "build/b.json" in results[1].message
