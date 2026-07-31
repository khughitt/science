from __future__ import annotations

import pytest
from science_model.evidence_broker import SurfacePolicy

from science_tool.evidence_broker.policy import (
    EvidenceOp,
    EvidenceRequest,
    authorize,
    exclude_pathspecs,
    literal_pathspec,
)

POLICY = SurfacePolicy(deny_prefixes=("private", "notes/a[b].md"), notice="withheld by policy")


def _read(target: str) -> EvidenceRequest:
    return EvidenceRequest(op=EvidenceOp.READ, target=target)


def test_a_path_under_a_deny_prefix_is_refused():
    auth = authorize(_read("private/x.txt"), POLICY)
    assert auth.denial is not None
    assert auth.denial.notice == "withheld by policy"
    assert auth.denial.reason == "path-denied"
    assert auth.path is None


def test_the_prefix_itself_is_refused():
    assert authorize(_read("private"), POLICY).denial is not None


def test_a_prefix_denies_on_component_boundaries_only():
    """`private` must deny `private/x` and must NOT deny `privateer/x`. A bare
    `startswith` would deny both, and would silently withhold an unrelated tree."""
    assert authorize(_read("privateer/x.txt"), POLICY).denial is None


def test_containment_is_checked_before_any_prefix():
    """A prefix check alone is walked around with `..`, so traversal is refused first
    and is refused as MALFORMED rather than as denied -- the two are different facts and
    a requester that cannot tell them apart cannot correct its own input."""
    auth = authorize(_read("private/../public/x.txt"), POLICY)
    assert auth.denial is not None
    assert auth.denial.reason == "path-malformed"


def test_an_absolute_path_is_refused_lexically():
    auth = authorize(_read("/etc/passwd"), POLICY)
    assert auth.denial is not None
    assert auth.denial.reason == "path-malformed"


def test_an_undenied_path_is_authorized():
    assert authorize(_read("src/main.py"), POLICY).denial is None


def test_the_authorized_path_is_the_normalized_one():
    """The value the caller must hand to git. `a\\b` normalizes to `a/b`, and a caller
    that passed its own raw string would authorize one path and read another -- git
    reads a file literally named `a\\b`, which no prefix was ever compared against."""
    auth = authorize(_read("./docs//a\\b"), POLICY)
    assert auth.denial is None
    assert auth.path == "docs/a/b"


def test_a_search_carries_no_path_so_only_its_pathspec_is_judged():
    """SEARCH's target is a PATTERN. Judging it as a path would refuse legitimate
    patterns for containing `/` or `..`, and would say nothing about what git reads."""
    assert authorize(EvidenceRequest(op=EvidenceOp.SEARCH, target="../secret"), POLICY).denial is None
    denied = EvidenceRequest(op=EvidenceOp.SEARCH, target="x", pathspec="private/x.txt")
    assert authorize(denied, POLICY).denial is not None


@pytest.mark.parametrize("pattern", ["a\0b", "\ud800"])
def test_a_pattern_that_cannot_cross_argv_is_refused_not_passed_to_git(pattern: str):
    """Measured: a NUL raises `ValueError` inside `subprocess` and a lone high surrogate
    raises `UnicodeEncodeError`, a `ValueError` subclass. `run_git` turns either into
    `GitError`, halting the run over input §6 calls retryable."""
    auth = authorize(EvidenceRequest(op=EvidenceOp.SEARCH, target=pattern), POLICY)
    assert auth.denial is not None
    assert auth.denial.reason == "pattern-malformed"


def test_an_empty_pattern_is_authorized():
    """An empty ERE is VALID and matches every line -- measured, exit 0 with every file
    listed. Refusing it would deny a real query on a guess about the requester's intent,
    and whether a pattern compiles is git's answer to give."""
    assert authorize(EvidenceRequest(op=EvidenceOp.SEARCH, target=""), POLICY).denial is None


def test_a_surrogateescape_byte_pattern_is_authorized():
    """`\\udcff` round-trips through `os.fsencode` to a byte and git accepts it. Judging
    with strict UTF-8 instead would refuse a pattern the instrument can actually run --
    a check that looks stricter and is simply wrong."""
    assert authorize(EvidenceRequest(op=EvidenceOp.SEARCH, target="\udcff"), POLICY).denial is None


def test_history_is_judged_as_a_path():
    auth = authorize(EvidenceRequest(op=EvidenceOp.HISTORY, target="private/x.txt"), POLICY)
    assert auth.denial is not None


def test_a_glob_target_is_authorized_but_must_reach_git_literally():
    """MEASURED policy bypass: `priv*` is not under any deny prefix as text, and as a
    bare pathspec git expands it onto `private/x.txt`. `literal_pathspec` is what makes
    the authorized spelling and the searched spelling the same string."""
    assert authorize(EvidenceRequest(op=EvidenceOp.HISTORY, target="priv*"), POLICY).denial is None
    assert literal_pathspec("priv*") == ":(top,literal)priv*"


def test_exclusions_are_top_literal_and_exclude():
    assert exclude_pathspecs(POLICY) == (
        ":(top,literal,exclude)private",
        ":(top,literal,exclude)notes/a[b].md",
    )


def test_an_empty_policy_excludes_nothing():
    assert exclude_pathspecs(SurfacePolicy(notice="n")) == ()


# THE AGREEMENT TABLE LIVES IN `test_evidence_broker_serve.py`. It used to sit here and drove
# only the READ half, while its comment claimed both -- so changing the search exclusion's
# pathspec magic could stop `private` from excluding while READ went on denying it, and the
# table stayed green through the divergence it was written to catch. The SEARCH half cannot be
# asserted without running git (a pure test would have to reimplement git's pathspec matching,
# which proves agreement with the reimplementation and nothing else), so the table moved to the
# module that has git rather than the search half being faked to keep it here.
