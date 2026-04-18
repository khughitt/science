from __future__ import annotations

from pathlib import Path

from science_tool.big_picture.validator import validate_synthesis_file

FIXTURE = Path(__file__).parent / "fixtures" / "big_picture" / "minimal_project"


def _write(tmp_path: Path, name: str, body: str) -> Path:
    f = tmp_path / name
    f.write_text(body)
    return f


def test_flags_nonexistent_interpretation_id(tmp_path: Path) -> None:
    synth = _write(
        tmp_path,
        "h1-alpha.md",
        """---
id: "synthesis:h1-alpha"
hypothesis: "hypothesis:h1-alpha"
provenance_coverage: "high"
---

## Arc

The investigation began with interpretation:i99-does-not-exist.
""",
    )
    issues = validate_synthesis_file(synth, project_root=FIXTURE)
    assert any(i.kind == "nonexistent_reference" and "i99-does-not-exist" in i.message for i in issues)


def test_passes_when_all_references_exist(tmp_path: Path) -> None:
    synth = _write(
        tmp_path,
        "h1-alpha.md",
        """---
id: "synthesis:h1-alpha"
hypothesis: "hypothesis:h1-alpha"
provenance_coverage: "high"
---

## Arc

The investigation built on interpretation:i01-h1-q03.
""",
    )
    issues = validate_synthesis_file(synth, project_root=FIXTURE)
    assert not any(i.kind == "nonexistent_reference" for i in issues)
