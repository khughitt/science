from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from science_tool.boundary.config import BoundaryConfig, StorageClass


def _cfg(**kw):
    return BoundaryConfig.model_validate(kw)


def test_payload_root_parses():
    cfg = _cfg(roots=[{"path": "data/raw", "class": "payload"}])
    assert cfg.roots[0].storage_class is StorageClass.PAYLOAD
    assert cfg.roots[0].tracked == ()


def test_manifest_root_parses_tracked():
    cfg = _cfg(roots=[{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}])
    assert cfg.roots[0].tracked == ("datapackage.json",)


def test_manifest_requires_nonempty_tracked():
    # A manifest root tracking nothing IS a payload root. Two spellings of one
    # meaning is the ambiguity this design removes.
    with pytest.raises(ValidationError, match="tracked"):
        _cfg(roots=[{"path": "data/external", "class": "manifest", "tracked": []}])
    with pytest.raises(ValidationError, match="tracked"):
        _cfg(roots=[{"path": "data/external", "class": "manifest"}])


def test_tracked_rejected_on_payload():
    with pytest.raises(ValidationError, match="tracked"):
        _cfg(roots=[{"path": "data/raw", "class": "payload", "tracked": ["a.json"]}])


@pytest.mark.parametrize(
    "bad",
    ["/abs", "..", "a/../b", ".", "a/", "", "a\nb", "a\tb", "a*b", "a?b", "a[b]", "!a", "a\\"],
)
def test_root_path_grammar(bad):
    with pytest.raises(ValidationError):
        _cfg(roots=[{"path": bad, "class": "payload"}])


def test_duplicate_roots_rejected():
    with pytest.raises(ValidationError, match="duplicate"):
        _cfg(roots=[{"path": "data/raw", "class": "payload"}, {"path": "data/raw", "class": "payload"}])


def test_casefold_equivalent_roots_rejected():
    with pytest.raises(ValidationError, match="case-fold"):
        _cfg(
            roots=[
                {"path": "Data", "class": "payload"},
                {"path": "data", "class": "payload"},
            ]
        )


def test_nested_roots_rejected():
    # /data/ would stop git descending and silently disable the child's negations.
    with pytest.raises(ValidationError, match="nested"):
        _cfg(
            roots=[
                {"path": "data", "class": "payload"},
                {"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]},
            ]
        )


def test_casefold_ancestor_roots_rejected():
    with pytest.raises(ValidationError, match="case-fold"):
        _cfg(
            roots=[
                {"path": "Data", "class": "payload"},
                {
                    "path": "data/external",
                    "class": "manifest",
                    "tracked": ["datapackage.json"],
                },
            ]
        )


def test_casefold_ancestor_rejection_matches_real_git(tmp_path: Path):
    """With core.ignoreCase=true the payload parent prevents manifest traversal."""
    repo = tmp_path / "repo"
    descriptor = repo / "data/external/ds/datapackage.json"
    descriptor.parent.mkdir(parents=True)
    descriptor.write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "core.ignoreCase", "true"],
        check=True,
    )
    (repo / ".gitignore").write_text(
        "/Data/\n/data/external/**\n!/data/external/**/\n!/data/external/**/datapackage.json\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    staged = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")

    assert b"data/external/ds/datapackage.json" not in staged
    with pytest.raises(ValidationError, match="case-fold"):
        _cfg(
            roots=[
                {"path": "Data", "class": "payload"},
                {
                    "path": "data/external",
                    "class": "manifest",
                    "tracked": ["datapackage.json"],
                },
            ]
        )


def test_sibling_roots_allowed():
    cfg = _cfg(
        roots=[
            {"path": "data/raw", "class": "payload"},
            {"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]},
        ]
    )
    assert len(cfg.roots) == 2


@pytest.mark.parametrize(
    "bad",
    ["/abs", "..", "a/", "", "!x", "#x", "a\nb", "a\\", "a\\b", "[ab].json", "foo/**/bar.json", "a.json "],
)
def test_tracked_glob_grammar(bad):
    with pytest.raises(ValidationError):
        _cfg(roots=[{"path": "data/external", "class": "manifest", "tracked": [bad]}])


@pytest.mark.parametrize(
    "good",
    [
        "datapackage.json",
        "*.qa.json",
        "schemas/*.json",
        "données.json",
        "read me.json",
        " lead.json",
        "trail.json\u00a0",
    ],
)
def test_tracked_glob_admits_the_proven_subset(good):
    cfg = _cfg(roots=[{"path": "d", "class": "manifest", "tracked": [good]}])
    assert cfg.roots[0].tracked == (good,)


# --- the divergence oracle -------------------------------------------------
# The exclusions below are justified by git DISAGREEING with the checker. A
# comment asserting git's answer is not a regression test: if a future git
# changed its mind, or the claim was simply wrong, nothing would fail. So each
# case runs BOTH engines for real.


def _git_stages(tmp_path: Path, glob: str, rel: str) -> bool:
    """Does the GENERATED rule `!/root/**/<glob>` make `root/<rel>` stageable?

    Mirrors exactly what the generator emits, so this answers the only question
    that matters: would the emitted rule actually re-include the file?
    """
    repo = tmp_path / f"probe{_git_stages.counter}"
    _git_stages.counter += 1
    (repo / "root" / Path(rel).parent).mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    # Neutralise the developer's global excludes; they are not under test and
    # would otherwise make this pass or fail depending on whose machine it is.
    subprocess.run(["git", "-C", str(repo), "config", "core.excludesFile", str(repo / ".none")], check=True)
    (repo / ".gitignore").write_text(f"/root/**\n!/root/**/\n!/root/**/{glob}\n", encoding="utf-8")
    (repo / "root" / rel).write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    staged = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], check=True, capture_output=True).stdout.decode()
    return f"root/{rel}" in staged


_git_stages.counter = 0


def _matcher_stages(glob: str, rel: str) -> bool:
    from pathlib import PurePosixPath

    return PurePosixPath(rel).match(glob)


# (id, glob, path-under-root). Measured answers, reproduced against real git:
# every DIVERGENT row differs, every AGREEING row does not.
DIVERGENT = [
    pytest.param("foo/**/bar.json", "foo/bar.json", id="double-star"),
    pytest.param("?.json", "d/é.json", id="question-mark-is-one-byte-in-git"),
    pytest.param("trail.json ", "d/trail.json ", id="trailing-space-stripped-by-git"),
    pytest.param("foo//bar.json", "foo/bar.json", id="empty-segment"),
    pytest.param("foo/./bar.json", "foo/bar.json", id="dot-segment"),
    pytest.param("./a.json", "d/a.json", id="leading-dot-segment"),
]

AGREEING = [
    pytest.param(" lead.json", "d/ lead.json", id="leading-space"),
    pytest.param("trail.json\u00a0", "d/trail.json\u00a0", id="unicode-nbsp-is-literal"),
    pytest.param("[ab].json", "d/a.json", id="character-class"),
    pytest.param("datapackage.json", "d/datapackage.json", id="literal"),
    pytest.param("*.qa.json", "d/x.qa.json", id="star"),
    pytest.param("schemas/*.json", "d/schemas/x.json", id="multi-segment"),
    pytest.param("données.json", "d/données.json", id="non-ascii-literal"),
]


@pytest.mark.parametrize(("glob", "rel"), DIVERGENT)
def test_divergent_globs_really_diverge_and_are_rejected(tmp_path, glob, rel):
    """Runs BOTH engines. A comment asserting git's answer is not a regression
    test -- if git changed its mind, or the claim was simply wrong, nothing
    would fail. Each rejection must be earned by a measured disagreement."""
    assert _matcher_stages(glob, rel) != _git_stages(tmp_path, glob, rel), (
        f"{glob!r} vs {rel!r}: the engines AGREE, so this is not a divergence exclusion"
    )
    with pytest.raises(ValidationError):
        _cfg(roots=[{"path": "d", "class": "manifest", "tracked": [glob]}])


@pytest.mark.parametrize(("glob", "rel"), AGREEING)
def test_agreeing_globs_really_agree(tmp_path, glob, rel):
    """The other half of the contract. If one of these ever diverges, the
    grammar is admitting something unreachable-tracked cannot verify."""
    assert _matcher_stages(glob, rel) is True
    assert _git_stages(tmp_path, glob, rel) is True


def test_leading_whitespace_is_admitted():
    """An earlier draft rejected it as a divergence. It is not one -- git keeps
    leading whitespace and the matcher agrees -- so rejecting it was policy
    dressed as a technical constraint. Only TRAILING whitespace diverges."""
    cfg = _cfg(roots=[{"path": "d", "class": "manifest", "tracked": [" lead.json"]}])
    assert cfg.roots[0].tracked == (" lead.json",)


def test_character_class_is_rejected_as_a_probe_restriction():
    """`test_agreeing_globs_really_agree` proves both engines match it. It is
    excluded because probe generation cannot synthesise a witness filename for a
    class -- the plan must NOT claim git disagrees here."""
    with pytest.raises(ValidationError, match="probe witness"):
        _cfg(roots=[{"path": "d", "class": "manifest", "tracked": ["[ab].json"]}])


def test_duplicate_tracked_rejected():
    with pytest.raises(ValidationError, match="duplicate"):
        _cfg(roots=[{"path": "d", "class": "manifest", "tracked": ["a.json", "a.json"]}])


def test_allow_entry_shorthand_expands_to_root():
    cfg = _cfg(unmanaged_allow=[".venv/"])
    assert cfg.unmanaged_allow[0].source == ".gitignore"
    assert cfg.unmanaged_allow[0].pattern == ".venv/"


def test_allow_entry_explicit_source():
    cfg = _cfg(unmanaged_allow=[{"source": "inc/shiny/.gitignore", "pattern": "node_modules/"}])
    assert cfg.unmanaged_allow[0].source == "inc/shiny/.gitignore"


def test_allow_source_must_be_a_gitignore_file():
    with pytest.raises(ValidationError, match="gitignore"):
        _cfg(unmanaged_allow=[{"source": "inc/shiny/ignore.txt", "pattern": "x"}])


def test_duplicate_allow_pairs_rejected():
    with pytest.raises(ValidationError, match="duplicate"):
        _cfg(unmanaged_allow=[".venv/", {"source": ".gitignore", "pattern": ".venv/"}])


def test_allow_pattern_preserves_git_significant_whitespace():
    """Only an UNESCAPED trailing ASCII space is stripped by git. Leading
    whitespace, U+00A0, and an escaped trailing ASCII space are rule text and
    must remain representable by the exact-text allowlist."""
    cfg = _cfg(unmanaged_allow=[" .venv/", "archive\\ ", "archive\u00a0/"])
    assert [a.pattern for a in cfg.unmanaged_allow] == [" .venv/", "archive\\ ", "archive\u00a0/"]
    with pytest.raises(ValidationError, match="unescaped trailing ASCII space"):
        _cfg(unmanaged_allow=[".venv/ "])


def test_unknown_key_rejected():
    with pytest.raises(ValidationError):
        _cfg(roots=[{"path": "d", "class": "payload", "clazz": "x"}])
