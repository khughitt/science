"""The synthesis output path must be RESOLVED, not composed.

`commands/big-picture.md` documented the target as `entities/synthesis/<hyp-id>.md`. But
mm30 and natural-systems both store synthesis as NUMBERED canonical entities
(`0022-epigenetic-commitment.md`), bound to their hypothesis by a `hypothesis:` frontmatter
field. Following the command literally would have created 29 NEW files beside the 15
existing ones -- duplicate synthesis entities for the same hypotheses, with the rollup
pointing at one set and the graph at the other (fb-2026-07-11-013, -002).

Both projects detected this by hand and built the hypothesis->file map themselves before
dispatching. The command already says these artifacts are identified "by `report_kind`, not
by filename" -- this resolver is that sentence, made true.
"""

from pathlib import Path

from science_tool.big_picture.synthesis_paths import resolve_synthesis_path


def _write_synthesis(directory: Path, filename: str, hypothesis: str, report_kind: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(
        f'---\nid: "synthesis:{filename[:-3]}"\nkind: synthesis\n'
        f'report_kind: "{report_kind}"\nhypothesis: "{hypothesis}"\n---\n\nBody.\n',
        encoding="utf-8",
    )
    return path


def test_resolves_to_an_existing_numbered_entity(tmp_path: Path) -> None:
    """The filename bears no relation to the hypothesis ID. Only the frontmatter does."""
    d = tmp_path / "entities" / "synthesis"
    expected = _write_synthesis(d, "0022-epigenetic-commitment.md", "hypothesis:0007-abc", "hypothesis-synthesis")

    assert resolve_synthesis_path(tmp_path, "hypothesis:0007-abc") == expected


def test_falls_back_when_no_prior_file_exists(tmp_path: Path) -> None:
    """Partial coverage is NORMAL -- mm30's prior run covered 15 of 29 hypotheses, so the
    resolver must handle 'this one has no synthesis yet' as an ordinary case, not an error.
    """
    (tmp_path / "entities" / "synthesis").mkdir(parents=True)

    resolved = resolve_synthesis_path(tmp_path, "hypothesis:0007-abc")

    assert resolved == tmp_path / "entities" / "synthesis" / "0007-abc.md"
    assert not resolved.exists()


def test_ignores_synthesis_entities_of_other_report_kinds(tmp_path: Path) -> None:
    """The rollup and the emergent-threads file also live in entities/synthesis/. Matching
    on `hypothesis:` alone would be enough today, but report_kind is the declared
    discriminator and must be honoured.
    """
    d = tmp_path / "entities" / "synthesis"
    _write_synthesis(d, "rollup.md", "hypothesis:0007-abc", "synthesis-rollup")

    resolved = resolve_synthesis_path(tmp_path, "hypothesis:0007-abc")

    assert resolved.name == "0007-abc.md"  # fell back; did not claim the rollup


def test_missing_synthesis_dir_falls_back(tmp_path: Path) -> None:
    """A project that has never run big-picture has no entities/synthesis/ at all."""
    resolved = resolve_synthesis_path(tmp_path, "hypothesis:0007-abc")
    assert resolved == tmp_path / "entities" / "synthesis" / "0007-abc.md"
