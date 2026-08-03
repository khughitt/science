from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.boundary.config import BoundaryConfig
from science_tool.boundary.generate import (
    MANAGED_BEGIN,
    MANAGED_END,
    ManagedBlockError,
    extract_managed_block,
    render_managed_block,
    splice_managed_block,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True).stdout


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def test_payload_root_is_anchored():
    cfg = BoundaryConfig.model_validate({"roots": [{"path": "data/raw", "class": "payload"}]})
    assert "/data/raw/" in render_managed_block(cfg)


def test_no_generated_pattern_is_unanchored():
    cfg = BoundaryConfig.model_validate(
        {
            "roots": [
                {"path": "pdfs", "class": "payload"},
                {"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]},
            ]
        }
    )
    for line in render_managed_block(cfg).splitlines():
        if not line or line.startswith("#"):
            continue
        body = line[1:] if line.startswith("!") else line
        assert body.startswith("/"), f"unanchored generated pattern: {line}"


def test_manifest_emits_descend_preserving_form():
    cfg = BoundaryConfig.model_validate(
        {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}
    )
    block = render_managed_block(cfg)
    assert "/data/external/**" in block
    assert "!/data/external/**/" in block
    assert "!/data/external/**/datapackage.json" in block
    # A bare anchored exclude would stop descent and disable the negations.
    assert "\n/data/external/\n" not in "\n" + block


def test_generation_is_deterministic():
    payload = {
        "roots": [
            {"path": "pdfs", "class": "payload"},
            {"path": "data/raw", "class": "payload"},
        ]
    }
    a = render_managed_block(BoundaryConfig.model_validate(payload))
    payload["roots"].reverse()
    b = render_managed_block(BoundaryConfig.model_validate(payload))
    assert a == b


def test_splice_appends_when_absent():
    out = splice_managed_block(".venv/\n", "X\n")
    assert out.startswith(".venv/\n")
    assert MANAGED_BEGIN in out and MANAGED_END in out


def test_splice_replaces_in_place_and_preserves_surroundings():
    original = splice_managed_block("head\n", "OLD\n")
    updated = splice_managed_block(original + "tail\n", "NEW\n")
    assert "OLD" not in updated
    assert "NEW" in updated
    assert updated.startswith("head\n")
    assert updated.rstrip().endswith("tail")


def test_splice_is_idempotent():
    once = splice_managed_block("head\n", "B\n")
    assert splice_managed_block(once, "B\n") == once


def test_extract_roundtrip():
    text = splice_managed_block("head\n", "B\n")
    assert extract_managed_block(text) == "B\n"
    assert extract_managed_block("no markers\n") is None


def test_marker_substrings_are_handwritten_text():
    """Marker words have no ownership meaning inside a physical line."""
    original = f"prefix {MANAGED_BEGIN}\n{MANAGED_END} suffix\n"

    assert extract_managed_block(original) is None
    assert splice_managed_block(original, "managed\n").startswith(original)


def test_markers_accept_only_a_terminal_cr_on_the_physical_line():
    crlf = f"{MANAGED_BEGIN}\r\nbody\r\n{MANAGED_END}\r\n"
    embedded_cr = f"{MANAGED_BEGIN}\rnot-a-marker\nbody\n{MANAGED_END}\rnot-a-marker\n"

    assert extract_managed_block(crlf) == "body\r\n"
    assert extract_managed_block(embedded_cr) is None


def test_extract_preserves_leading_blank_lines_and_exact_body_bytes():
    body = "\nraw-\udcff\r\n\n"
    text = f"prefix\n{MANAGED_BEGIN}\n{body}{MANAGED_END}\nsuffix\n"

    extracted = extract_managed_block(text)

    assert extracted == body
    assert extracted.encode("utf-8", "surrogateescape") == body.encode("utf-8", "surrogateescape")


def test_splice_preserves_prefix_and_suffix_bytes_including_blank_lines():
    prefix = "prefix-\udcff\r\n\n"
    suffix = "\n\nsuffix-\udcfe\r\n"
    original = f"{prefix}{MANAGED_BEGIN}\nold\r\n{MANAGED_END}\n{suffix}"

    updated = splice_managed_block(original, "new\n")

    assert updated.startswith(prefix)
    assert updated.endswith(suffix)
    assert updated.encode("utf-8", "surrogateescape").startswith(prefix.encode("utf-8", "surrogateescape"))
    assert updated.encode("utf-8", "surrogateescape").endswith(suffix.encode("utf-8", "surrogateescape"))


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        (f"handwritten before\n{MANAGED_BEGIN}\nhandwritten after\n", "unmatched BEGIN"),
        (f"handwritten before\n{MANAGED_END}\nhandwritten after\n", "unmatched END"),
        (f"handwritten before\n{MANAGED_END}\n{MANAGED_BEGIN}\nhandwritten after\n", "reversed"),
        (
            f"handwritten before\n{MANAGED_BEGIN}\nfirst\n{MANAGED_BEGIN}\n{MANAGED_END}\nhandwritten after\n",
            "duplicate BEGIN",
        ),
        (
            f"handwritten before\n{MANAGED_BEGIN}\n{MANAGED_END}\nsecond\n{MANAGED_END}\nhandwritten after\n",
            "duplicate END",
        ),
        (
            f"handwritten before\n{MANAGED_BEGIN}\none\n{MANAGED_END}\n"
            f"handwritten middle\n{MANAGED_BEGIN}\ntwo\n{MANAGED_END}\nhandwritten after\n",
            "multiple blocks",
        ),
    ],
)
def test_malformed_managed_markers_never_consume_handwritten_content(text: str, problem: str):
    """Neither reader nor writer may select a partial block from malformed text."""
    with pytest.raises(ManagedBlockError, match=problem):
        extract_managed_block(text)
    with pytest.raises(ManagedBlockError, match=problem):
        splice_managed_block(text, "replacement\n")


def test_manifest_descriptor_is_really_visible_to_git(tmp_path: Path):
    """Real git, not string comparison. The trap is that negations LOOK right."""
    repo = _repo(tmp_path)
    (repo / "data/external/ot/25.03").mkdir(parents=True)
    (repo / "data/external/ot/25.03/datapackage.json").write_text("{}\n")
    (repo / "data/external/ot/25.03/big.parquet").write_text("x\n")
    cfg = BoundaryConfig.model_validate(
        {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}
    )
    (repo / ".gitignore").write_text(splice_managed_block("", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    staged = _git(repo, "ls-files").split()
    assert "data/external/ot/25.03/datapackage.json" in staged
    assert "data/external/ot/25.03/big.parquet" not in staged


def test_payload_root_stages_nothing(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "data/raw").mkdir(parents=True)
    (repo / "data/raw/x.csv").write_text("a\n")
    cfg = BoundaryConfig.model_validate({"roots": [{"path": "data/raw", "class": "payload"}]})
    (repo / ".gitignore").write_text(splice_managed_block("", render_managed_block(cfg)))
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    assert "data/raw/x.csv" not in _git(repo, "ls-files").split()


def test_the_managed_block_ignores_the_ingestion_lock():
    """`locked_store` creates `doc/audits/cases/.ingest.lock` and deliberately never
    unlinks it -- making it ephemeral would reopen the check/use gap the directory
    descriptor closes. So it is permanent untracked residue in every project that has
    ever ingested, and nothing ignored it: the supervised run harness committed it.

    Derived from the two constants that already define the path, so there is no third
    spelling to drift.
    """
    from science_tool.findings.storage import CASES_DIRNAME, LOCK_NAME

    block = render_managed_block(BoundaryConfig())

    assert f"/{CASES_DIRNAME}/{LOCK_NAME}\n" in block


def test_the_lock_is_ignored_even_with_no_boundary_roots():
    """The lock is not root-derived. A project with no configured roots still ingests,
    so a block that only renders when `cfg.roots` is non-empty would miss exactly the
    projects most likely to hit this."""
    assert render_managed_block(BoundaryConfig(roots=())).strip() != ""


def test_the_lock_survives_a_manifest_root_that_overlaps_the_cases_directory(tmp_path: Path):
    """`.gitignore` is last-match-wins. Nothing in `boundary/config.py` reserves
    `doc/audits/cases`, so a manifest root declared there with a `tracked` glob that
    matches the lock (`*` here) legally emits `!/doc/audits/cases/**/*` -- a negation
    that would silently re-include the lock if the fixed line were emitted BEFORE the
    root-derived lines instead of after them.

    Checked against real git, not string containment: the lock line being present
    somewhere in the block proves nothing if a later line in the same block
    re-includes the file it names.
    """
    repo = _repo(tmp_path)
    (repo / "doc/audits/cases").mkdir(parents=True)
    (repo / "doc/audits/cases/.ingest.lock").write_text("")
    cfg = BoundaryConfig.model_validate(
        {"roots": [{"path": "doc/audits/cases", "class": "manifest", "tracked": ["*"]}]}
    )
    (repo / ".gitignore").write_text(splice_managed_block("", render_managed_block(cfg)))

    result = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "-q", "doc/audits/cases/.ingest.lock"]
    )

    assert result.returncode == 0, "the ingestion lock must stay ignored under an overlapping manifest root"
