"""Tests for atomic question-file reservation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.questions import _MAX_SLUG_LENGTH, Reservation, reserve_question, slugify

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

    def test_truncation_backs_up_to_word_boundary(self) -> None:
        # Slug is 53 chars; a hard 50-char cap lands inside the final token
        # ("...-dysregulation-express"). Back up to the token boundary instead.
        result = slugify("convergence reduction versus dysregulation expression")
        assert result == "convergence-reduction-versus-dysregulation"
        assert len(result) <= _MAX_SLUG_LENGTH
        assert not result.endswith("-")

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


def _questions_dir(project_root: Path) -> Path:
    return project_root / "entities" / "questions"


class TestReserveQuestion:
    def test_first_reservation_in_empty_dir(self, tmp_path: Path) -> None:
        result = reserve_question(tmp_path, "first thing")
        assert isinstance(result, Reservation)
        assert result.number == 1
        assert result.padded == "0001"
        assert result.slug == "first-thing"
        assert result.id == "question:0001-first-thing"
        assert result.path == _questions_dir(tmp_path) / "0001-first-thing.md"
        assert result.path.is_file()

    def test_increments_past_existing_files(self, tmp_path: Path) -> None:
        d = _questions_dir(tmp_path)
        d.mkdir(parents=True)
        (d / "0001-foo.md").write_text("# foo\n")
        (d / "0002-bar.md").write_text("# bar\n")
        result = reserve_question(tmp_path, "baz")
        assert result.number == 3
        assert result.padded == "0003"

    def test_gap_tolerant_uses_max_plus_one(self, tmp_path: Path) -> None:
        """Retired numbers stay retired so historical references don't shift."""
        d = _questions_dir(tmp_path)
        d.mkdir(parents=True)
        (d / "0001-foo.md").write_text("# foo\n")
        (d / "0005-baz.md").write_text("# baz\n")
        result = reserve_question(tmp_path, "qux")
        assert result.number == 6  # max+1, not gap-fill at 02

    def test_counts_legacy_prefixed_files(self, tmp_path: Path) -> None:
        """Legacy ``qNN``/``hNN`` style names still count in the next-number scan."""
        d = _questions_dir(tmp_path)
        d.mkdir(parents=True)
        (d / "q03-legacy.md").write_text("# legacy\n")
        result = reserve_question(tmp_path, "bar")
        assert result.number == 4
        assert result.path.name == "0004-bar.md"

    def test_questions_dir_override(self, tmp_path: Path) -> None:
        """The deprecated --questions-dir override writes to that dir verbatim."""
        override = tmp_path / "custom" / "qs"
        result = reserve_question(tmp_path, "first", questions_dir=override)
        assert result.path == override / "0001-first.md"
        assert result.path.is_file()
        # Nothing was written under the default entities/questions home.
        assert not _questions_dir(tmp_path).exists()

    def test_frontmatter_filled(self, tmp_path: Path) -> None:
        result = reserve_question(
            tmp_path,
            "metadata test",
            title="Does X drive Y?",
            related=["question:0001-prior", "hypothesis:h1"],
            ontology_terms=["GO:0006915", "process/apoptosis"],
            source_refs=["doi:10.1234/foo", "Smith2024"],
            datasets=["geo:GSE123456"],
        )
        fm = _read_frontmatter(result.path)
        assert fm["id"] == result.id
        assert fm["type"] == "question"
        assert fm["title"] == "Does X drive Y?"
        assert fm["status"] == "active"
        assert fm["related"] == ["question:0001-prior", "hypothesis:h1"]
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
        nested = _questions_dir(tmp_path)
        assert not nested.exists()
        reserve_question(tmp_path, "first")
        assert nested.is_dir()

    def test_counts_create_style_unprefixed_files(self, tmp_path: Path) -> None:
        """`science questions create` writes NNNN-slug.md (no prefix). reserve must
        count those when picking the next number, or it silently reissues a number
        that create already used."""
        d = _questions_dir(tmp_path)
        d.mkdir(parents=True)
        (d / "0002-foo.md").write_text("# foo\n")
        (d / "0003-bar.md").write_text("# bar\n")
        result = reserve_question(tmp_path, "baz")
        assert result.number == 4

    def test_counts_mixed_prefixed_and_unprefixed(self, tmp_path: Path) -> None:
        d = _questions_dir(tmp_path)
        d.mkdir(parents=True)
        (d / "q01-foo.md").write_text("# foo\n")  # legacy single-letter prefix
        (d / "0004-bar.md").write_text("# bar\n")  # higher number, canonical
        result = reserve_question(tmp_path, "baz")
        assert result.number == 5

    def test_unrelated_files_ignored_in_scan(self, tmp_path: Path) -> None:
        d = _questions_dir(tmp_path)
        d.mkdir(parents=True)
        (d / "README.md").write_text("readme\n")
        (d / "not-numbered.md").write_text("# no number\n")
        result = reserve_question(tmp_path, "x")
        assert result.number == 1  # nothing matched the numeric pattern


def test_question_reserve_writes_under_entities_questions(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "questions",
            "reserve",
            "--slug",
            "why-things",
            "--project-root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["id"] == "question:0001-why-things"
    assert payload["number"] == 1
    assert payload["padded"] == "0001"
    assert payload["slug"] == "why-things"
    assert payload["path"] == str(tmp_path / "entities" / "questions" / "0001-why-things.md")
    assert (tmp_path / "entities" / "questions" / "0001-why-things.md").is_file()
