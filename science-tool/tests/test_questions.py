"""Tests for atomic question-file reservation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.questions import Reservation, reserve_question, slugify


# --- slugify ------------------------------------------------------------------


class TestSlugify:
    def test_basic_kebab_case(self) -> None:
        assert slugify("Hello World") == "hello-world"

    def test_collapses_repeated_separators(self) -> None:
        assert slugify("foo  --  bar") == "foo-bar"

    def test_strips_leading_trailing_separators(self) -> None:
        assert slugify("--foo bar--") == "foo-bar"

    def test_drops_punctuation(self) -> None:
        assert slugify("Why does X behave?? 2.0") == "why-does-x-behave-2-0"

    def test_truncates_to_max_length(self) -> None:
        long = "a" * 80
        assert slugify(long, max_length=10) == "a" * 10

    def test_truncation_strips_trailing_separator(self) -> None:
        # If the cap lands on a hyphen, drop it.
        result = slugify("abcdefghij-extra", max_length=11)
        assert result == "abcdefghij"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            slugify("")

    def test_rejects_pure_punctuation(self) -> None:
        with pytest.raises(ValueError):
            slugify("!!!")


# --- reserve_question ---------------------------------------------------------


def _read_frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


class TestReserveQuestion:
    def test_first_reservation_in_empty_dir(self, tmp_path: Path) -> None:
        result = reserve_question(tmp_path, "first thing")
        assert isinstance(result, Reservation)
        assert result.number == 1
        assert result.padded == "01"
        assert result.slug == "first-thing"
        assert result.id == "question:01-first-thing"
        assert result.path == tmp_path / "q01-first-thing.md"
        assert result.path.is_file()

    def test_increments_past_existing_files(self, tmp_path: Path) -> None:
        (tmp_path / "q01-foo.md").write_text("# foo\n")
        (tmp_path / "q02-bar.md").write_text("# bar\n")
        result = reserve_question(tmp_path, "baz")
        assert result.number == 3
        assert result.padded == "03"

    def test_gap_tolerant_uses_max_plus_one(self, tmp_path: Path) -> None:
        """Retired numbers stay retired so historical references don't shift."""
        (tmp_path / "q01-foo.md").write_text("# foo\n")
        (tmp_path / "q05-baz.md").write_text("# baz\n")
        result = reserve_question(tmp_path, "qux")
        assert result.number == 6  # max+1, not gap-fill at 02

    def test_padding_inferred_from_widest_existing(self, tmp_path: Path) -> None:
        (tmp_path / "q001-foo.md").write_text("# foo\n")
        result = reserve_question(tmp_path, "bar")
        assert result.padded == "002"
        assert result.path.name == "q002-bar.md"

    def test_collision_retries_until_free(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pre-create the path the first attempt would pick; reserve must bump and retry."""
        (tmp_path / "q03-other.md").write_text("# other\n")
        # Pre-create the slot the next-attempt scan would target after seeing q03 (i.e. q04)
        # — but with a different slug, so the destination filename differs and O_EXCL passes.
        # To force a true collision we need the SAME filename to exist already; so we
        # simulate that by pre-creating exactly the path reserve would attempt first.
        from science_tool import questions as q_mod

        original_scan = q_mod._scan_existing
        calls = {"n": 0}

        def fake_scan(d: Path) -> tuple[int, int]:
            # First call returns max=3 (so reserve tries q04). After reserve writes q04
            # we still need the second attempt to see something different — so we
            # simulate a competing process by pre-creating q04 *before* reserve writes,
            # forcing the EEXIST branch on its first try.
            calls["n"] += 1
            if calls["n"] == 1:
                # Plant the conflict before reserve's open() runs.
                (tmp_path / "q04-target.md").write_text("# competitor\n")
                return 3, 2
            return original_scan(d)

        monkeypatch.setattr(q_mod, "_scan_existing", fake_scan)
        result = reserve_question(tmp_path, "target")
        assert result.number == 5  # bumped past the planted collision
        assert result.path.name == "q05-target.md"
        assert calls["n"] >= 2  # retry occurred

    def test_frontmatter_filled(self, tmp_path: Path) -> None:
        result = reserve_question(
            tmp_path,
            "metadata test",
            title="Does X drive Y?",
            related=["question:01-prior", "hypothesis:h1"],
            ontology_terms=["GO:0006915", "process/apoptosis"],
            source_refs=["doi:10.1234/foo", "Smith2024"],
            datasets=["geo:GSE123456"],
        )
        fm = _read_frontmatter(result.path)
        assert fm["id"] == result.id
        assert fm["type"] == "question"
        assert fm["title"] == "Does X drive Y?"
        assert fm["status"] == "active"
        assert fm["related"] == ["question:01-prior", "hypothesis:h1"]
        assert fm["ontology_terms"] == ["GO:0006915", "process/apoptosis"]
        assert fm["source_refs"] == ["doi:10.1234/foo", "Smith2024"]
        assert fm["datasets"] == ["geo:GSE123456"]
        assert fm["created"] == fm["updated"]  # both stamped with today

    def test_title_substitutes_into_body(self, tmp_path: Path) -> None:
        result = reserve_question(tmp_path, "x", title="Why does X happen?")
        body = result.path.read_text(encoding="utf-8").split("\n---\n", 1)[1]
        assert "# Why does X happen?" in body

    def test_no_title_keeps_placeholder(self, tmp_path: Path) -> None:
        result = reserve_question(tmp_path, "x")
        body = result.path.read_text(encoding="utf-8").split("\n---\n", 1)[1]
        assert "# <Question>" in body

    def test_custom_template_body(self, tmp_path: Path) -> None:
        result = reserve_question(tmp_path, "x", title="T", template_body="# {title}\n\nCustom\n")
        body = result.path.read_text(encoding="utf-8").split("\n---\n", 1)[1]
        assert body.strip() == "# T\n\nCustom"

    def test_missing_dir_is_created(self, tmp_path: Path) -> None:
        nested = tmp_path / "doc" / "questions"
        assert not nested.exists()
        reserve_question(nested, "first")
        assert nested.is_dir()

    def test_unrelated_files_ignored_in_scan(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("readme\n")
        (tmp_path / "q-not-numbered.md").write_text("# no number\n")
        (tmp_path / "Q07-uppercase.md").write_text("# wrong case\n")
        result = reserve_question(tmp_path, "x")
        assert result.number == 1  # nothing matched the pattern
