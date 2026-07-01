"""Tests for atomic, locked references.bib appends (`science bib add`)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
import pytest

from science_tool.bibliography import (
    add_bib_entry,
    load_bib_author_surnames,
    load_bib_keys,
)
from science_tool.cli import main

SMITH = """\
@article{Smith2024,
  title={A Test Paper},
  author={Smith, Jane},
  year={2024}
}"""

JONES = """\
@article{Jones2023,
  title={Another Paper},
  author={Jones, Bob},
  year={2023}
}"""

SMITH_REVISED = """\
@article{Smith2024,
  title={A Test Paper (revised)},
  author={Smith, Jane and Doe, John},
  journal={Nature},
  year={2024}
}"""


def test_add_to_missing_file_creates_with_header(tmp_path: Path) -> None:
    result = add_bib_entry(tmp_path, SMITH)
    bib = tmp_path / "papers" / "references.bib"
    assert bib.is_file()
    text = bib.read_text(encoding="utf-8")
    assert text.startswith("% references.bib")
    assert "@article{Smith2024," in text
    assert result.action == "added"
    assert result.key == "Smith2024"


def test_add_appends_to_existing(tmp_path: Path) -> None:
    add_bib_entry(tmp_path, SMITH)
    result = add_bib_entry(tmp_path, JONES)
    assert result.action == "added"
    assert load_bib_keys(tmp_path) == {"Smith2024", "Jones2023"}


def test_add_existing_key_is_idempotent_noop(tmp_path: Path) -> None:
    add_bib_entry(tmp_path, SMITH)
    bib = tmp_path / "papers" / "references.bib"
    before = bib.read_text(encoding="utf-8")

    result = add_bib_entry(tmp_path, SMITH_REVISED)  # same key, different body

    assert result.action == "exists"
    assert bib.read_text(encoding="utf-8") == before  # unchanged
    assert "revised" not in bib.read_text(encoding="utf-8")


def test_add_existing_key_with_replace_swaps_block(tmp_path: Path) -> None:
    add_bib_entry(tmp_path, SMITH)
    add_bib_entry(tmp_path, JONES)

    result = add_bib_entry(tmp_path, SMITH_REVISED, replace=True)

    bib = tmp_path / "papers" / "references.bib"
    text = bib.read_text(encoding="utf-8")
    assert result.action == "replaced"
    assert "A Test Paper (revised)" in text
    assert "A Test Paper}" not in text  # old body gone
    assert load_bib_keys(tmp_path) == {"Smith2024", "Jones2023"}  # Jones untouched
    # Only one Smith2024 block remains.
    assert text.count("@article{Smith2024,") == 1


def test_bib_add_accepts_format_json(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["bib", "add", "--project-root", str(tmp_path), "--entry", SMITH, "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == {
        "action": "added",
        "key": "Smith2024",
        "path": str(tmp_path / "papers" / "references.bib"),
    }


def test_add_rejects_entry_without_key(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="BibTeX key"):
        add_bib_entry(tmp_path, "this is not a bibtex entry")


def test_add_rejects_truncated_entry(tmp_path: Path) -> None:
    truncated = "@article{Broken2024,\n  title={Unterminated"
    with pytest.raises(ValueError, match="balanced|truncated|brace"):
        add_bib_entry(tmp_path, truncated)


def test_author_surnames_none_without_bib(tmp_path: Path) -> None:
    # No references.bib -> None, so bib-aware lints fall back to flag-all.
    assert load_bib_author_surnames(tmp_path) is None


def test_author_surnames_comma_format(tmp_path: Path) -> None:
    add_bib_entry(tmp_path, SMITH_REVISED)  # author={Smith, Jane and Doe, John}
    assert load_bib_author_surnames(tmp_path) == {"smith", "doe"}


def test_author_surnames_first_last_format(tmp_path: Path) -> None:
    entry = "@article{Levine2016,\n  author={Morgan E. Levine and Felix Day},\n  year={2016}\n}"
    add_bib_entry(tmp_path, entry)
    assert load_bib_author_surnames(tmp_path) == {"levine", "day"}


def _concurrent_add_worker(args: tuple[Path, int]) -> str:
    # Module-level so ProcessPoolExecutor can pickle it.
    from science_tool.bibliography import add_bib_entry as _add

    project_root, i = args
    entry = f"@article{{Author{i}_2024,\n  title={{Paper {i}}},\n  year={{2024}}\n}}"
    return _add(project_root, entry).key


def test_concurrent_add_no_lost_writes(tmp_path: Path) -> None:
    import concurrent.futures

    n = 8
    args = [(tmp_path, i) for i in range(n)]
    with concurrent.futures.ProcessPoolExecutor(max_workers=n) as ex:
        keys = list(ex.map(_concurrent_add_worker, args))

    assert len(set(keys)) == n
    assert load_bib_keys(tmp_path) == {f"Author{i}_2024" for i in range(n)}, (
        "concurrent appends lost entries from references.bib"
    )
