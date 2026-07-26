"""Layer 3 of design §5: the one-way perturbation alarm.

Perturb every ALLOWED field across a representative context. If a perturbation changes
the belief basis, this suite FAILS and the field must come off the allowlist.

The inverse is deliberately NOT asserted: observing no change never makes a field
writable (design §5 Layer 4 -- promotion requires human review of the materialization
path, and mutation results alone cannot authorize it). This asymmetry is what makes the
alarm sound despite perturbation being incomplete: a false negative can only ever leave
a field denied.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import Dataset

from science_tool.autonomy.policy import FIELD_ALLOWLIST, is_field_allowed
from science_tool.cli import main
from science_tool.graph.belief_basis import capture_basis, compare_bases
from science_tool.graph.io import PROJECT_NS

#: (kind, field, perturbed value as a RAW YAML FRAGMENT). One case per allowlist entry
#: -- `test_every_allowlisted_field_has_a_perturbation_case` is the ratchet that makes
#: an unalarmed allowlist entry impossible.
#:
#: The third element is spliced into the document verbatim, so its YAML type must match
#: the model's. `pmid` and `isbn` are `str` on the entity model, and unquoted `99999999`
#: parses as an int, which pydantic REJECTS -- so those values carry explicit quotes.
#: `year` and `duration_minutes` are `int | None` and must stay unquoted.
PERTURBATIONS: tuple[tuple[str, str, str], ...] = (
    ("paper", "venue", "Journal of Perturbation"),
    ("paper", "pmid", '"99999999"'),
    ("paper", "year", "1999"),
    ("paper", "url", "https://example.org/perturbed"),
    ("book", "publisher", "Perturbation Press"),
    ("book", "isbn", '"978-0-00-000000-0"'),
    ("book", "year", "1999"),
    ("book", "url", "https://example.org/perturbed-book"),
    ("talk", "venue", "Perturbation Symposium"),
    ("talk", "duration_minutes", "45"),
)

#: Where each perturbable kind's fixture entity lives, and its authored frontmatter.
_FIXTURE_ENTITIES: dict[str, tuple[str, str]] = {
    # `pmid` and `isbn` are quoted: unquoted digits parse as int and pydantic rejects
    # an int for a `str` field, so the fixture would fail to materialize at all.
    "paper": (
        "entities/papers/x.md",
        'id: paper:x\nkind: paper\ntitle: X\nvenue: Nature\npmid: "111"\nyear: 2020\nurl: https://example.org/x\n',
    ),
    "book": (
        "entities/books/b.md",
        'id: book:b\nkind: book\ntitle: B\npublisher: Old Press\nisbn: "978-1-11-111111-1"\nyear: 2019\nurl: https://example.org/b\n',
    ),
    "talk": (
        "entities/talks/t.md",
        "id: talk:t\nkind: talk\ntitle: T\nvenue: Old Venue\nduration_minutes: 30\n",
    ),
}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_project(root: Path) -> None:
    """A project with a real, non-empty belief basis plus one entity of every
    perturbable kind."""
    _write(root, "science.yaml", "name: perturbation-fixture\nknowledge_profiles:\n  local: local\n")
    _write(root, "entities/propositions/p1.md", "---\nid: proposition:p1\nkind: proposition\ntitle: P1\n---\n\nClaim.\n")
    _write(
        root,
        "entities/evidence-lines/e1.md",
        "---\n"
        "id: evidence-line:e1\n"
        "kind: evidence-line\n"
        "title: Evidence line\n"
        "stance: supports\n"
        "target: proposition:p1\n"
        "source: paper:x\n"
        "strength: strong\n"
        "belief_eligible: true\n"
        "---\n",
    )
    for rel, frontmatter in _FIXTURE_ENTITIES.values():
        _write(root, rel, f"---\n{frontmatter}---\n\nBody.\n")


def _build_and_capture(root: Path):
    result = CliRunner().invoke(main, ["graph", "build", "--project-root", str(root)])
    assert result.exit_code == 0, f"graph build failed:\n{result.output}"

    dataset = Dataset()
    dataset.parse(source=str(root / "knowledge" / "graph.trig"), format="trig")
    captured = capture_basis(
        dataset.graph(PROJECT_NS["graph/knowledge"]),
        dataset.graph(PROJECT_NS["graph/provenance"]),
    )
    assert captured.status != "unwired", f"fixture produced no basis: {captured.reason}"
    return captured.rows


def _perturb_field(root: Path, rel: str, field: str, value: str) -> None:
    text = (root / rel).read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith(f"{field}:"):
            lines[index] = f"{field}: {value}\n"
            break
    else:  # a field the fixture does not author is a fixture bug, not a passing case
        raise AssertionError(f"{rel} does not author {field!r}; the fixture cannot perturb it")
    (root / rel).write_text("".join(lines), encoding="utf-8")


@pytest.fixture
def seeded(tmp_path: Path):
    _seed_project(tmp_path)
    return tmp_path


def test_every_allowlisted_field_has_a_perturbation_case():
    """The ratchet: adding an allowlist entry without an alarm case fails HERE, before
    any promotion can happen."""
    covered = {(kind, field) for kind, field, _ in PERTURBATIONS}
    declared = {(kind, field) for kind, fields in FIELD_ALLOWLIST.items() for field in fields}
    assert covered == declared


def test_the_fixture_has_a_non_empty_basis(seeded: Path):
    """Certification: without a real evidence unit, every case below would pass
    vacuously."""
    rows = _build_and_capture(seeded)
    assert any(row.unit_keys for row in rows), "fixture yields no evidence units"


@pytest.mark.parametrize(("kind", "field", "value"), PERTURBATIONS, ids=lambda v: str(v))
def test_an_allowed_field_does_not_move_the_belief_basis(seeded: Path, kind: str, field: str, value: str):
    rel, _ = _FIXTURE_ENTITIES[kind]
    before = _build_and_capture(seeded)
    _perturb_field(seeded, rel, field, value)
    after = _build_and_capture(seeded)

    deltas = compare_bases(before, after)
    assert deltas == [], (
        f"{kind}.{field} moved the belief basis: {deltas}. Design §5 Layer 3: take it OFF "
        "FIELD_ALLOWLIST -- do not weaken this assertion."
    )


def test_the_alarm_fires_on_a_belief_bearing_field(seeded: Path):
    """Certification that the harness CAN fail. An evidence line's `strength` feeds
    `EvidenceUnit`, so perturbing it must move the basis. If this ever passes, every
    case above is meaningless."""
    before = _build_and_capture(seeded)
    _perturb_field(seeded, "entities/evidence-lines/e1.md", "strength", "weak")
    after = _build_and_capture(seeded)

    assert compare_bases(before, after) != []


def test_a_neutral_denied_field_stays_denied(seeded: Path):
    """Design §5 Layer 3, the one-way property. `methods_summary` moves nothing -- and
    that observation must NOT promote it. Overbreadth is an accepted, visible cost."""
    before = _build_and_capture(seeded)
    _write(
        seeded,
        "entities/papers/x.md",
        (seeded / "entities/papers/x.md").read_text(encoding="utf-8").replace(
            "venue: Nature\n", "venue: Nature\nmethods_summary: Rewritten by a run.\n"
        ),
    )
    after = _build_and_capture(seeded)

    assert compare_bases(before, after) == []
    assert is_field_allowed("paper", "methods_summary") is False
