from __future__ import annotations

import hashlib
import signal
import subprocess
from pathlib import Path

import pytest
from science_model.audit import LocationEvidence, Span, TextEvidence
from science_model.evidence_broker import (
    REPLAY_PROTOCOL_VERSION,
    EvidenceExposure,
    ExposureEntry,
    InlineInput,
    InstrumentIdentity,
    Outcome,
    SurfacePolicy,
)

import science_tool.evidence_broker.correspondence as correspondence_module
from science_tool.evidence_broker.correspondence import (
    Absent,
    Full,
    Lines,
    PathOnly,
    _corresponds,
    _line_count,
    _merge_coverage,
    check_correspondence,
)
from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
from science_tool.evidence_broker.serve import ServeError, serve


OPEN = SurfacePolicy(notice="withheld")
INSTRUMENT = InstrumentIdentity(ref="rubric.md", sha256="c" * 64, prompt_hash="d" * 64)


def _repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "p@example.invalid"),
        ("config", "user.name", "P"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    (root / "a.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    (root / "cr.txt").write_bytes(b"left\rright\n")
    (root / "empty.txt").write_bytes(b"")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"],
        check=True,
        capture_output=True,
    )
    (root / "head.txt").write_text("second commit\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "head"],
        check=True,
        capture_output=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
    ).stdout.decode().strip()
    return root, commit


def _entry(root: Path, commit: str, request: EvidenceRequest, policy=OPEN) -> ExposureEntry:
    replayed = serve(root, commit, request, policy)
    return ExposureEntry(
        op=request.op.value,
        target=replayed.target,
        pathspec=replayed.pathspec,
        commit=commit,
        sha256=hashlib.sha256(replayed.payload).hexdigest(),
        outcome=replayed.outcome,
    )


def _exposure(commit: str, entries=(), *, inline=(), protocol=REPLAY_PROTOCOL_VERSION, policy=OPEN):
    return EvidenceExposure(
        commit=commit,
        budget=10,
        requests_used=len([entry for entry in entries if entry.op != "inline"]),
        instrument=INSTRUMENT,
        surface_policy=policy,
        inline=inline,
        replay_protocol=protocol,
        entries=entries,
    )


@pytest.mark.parametrize(
    "left,right,expected",
    [
        (Full(8), Full(5), Full(5)),
        (Full(8), Lines(frozenset({9})), Full(8)),
        (Full(8), PathOnly(), Full(8)),
        (Full(8), Absent(), Full(8)),
        (Lines(frozenset({1})), Lines(frozenset({3})), Lines(frozenset({1, 3}))),
        (Lines(frozenset({1})), PathOnly(), Lines(frozenset({1}))),
        (PathOnly(), PathOnly(), PathOnly()),
        (PathOnly(), Absent(), Absent()),
        (Absent(), Absent(), Absent()),
    ],
)
def test_merge_coverage_is_total_over_reachable_pairs(left, right, expected) -> None:
    assert _merge_coverage(left, right) == expected
    assert _merge_coverage(right, left) == expected


def test_lines_and_absent_is_rejected_as_unreachable() -> None:
    with pytest.raises(ValueError, match="both matched and absent"):
        _merge_coverage(Lines(frozenset({1})), Absent())


@pytest.mark.parametrize(
    "payload,expected",
    [(b"", 0), (b"a\n", 1), (b"a", 1), (b"a\nb", 2), (b"a\rb\n", 1)],
)
def test_line_count_uses_lf_only(payload: bytes, expected: int) -> None:
    assert _line_count(payload) == expected


def test_full_bounds_lines_but_allows_a_pointer() -> None:
    assert _corresponds(LocationEvidence(path="a", line=2), Full(2))
    assert not _corresponds(LocationEvidence(path="a", line=3), Full(2))
    assert _corresponds(LocationEvidence(path="a", pointer="heading"), Full(0))


def test_full_span_matching_is_bounded() -> None:
    def _timeout(_signum, _frame):
        raise TimeoutError("FULL span matching iterated an authored-unbounded range")

    citation = LocationEvidence(path="a", span=Span(start_line=1, end_line=10**18))
    previous = signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(1)
    try:
        assert not _corresponds(citation, Full(10**18 - 1))
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def test_lines_requires_every_line_of_a_span_and_forbids_a_pointer() -> None:
    coverage = Lines(frozenset({2, 3, 4}))
    assert _corresponds(LocationEvidence(path="a", span=Span(start_line=2, end_line=4)), coverage)
    endpoints_only = Lines(frozenset({2, 4}))
    assert not _corresponds(LocationEvidence(path="a", span=Span(start_line=2, end_line=4)), endpoints_only)
    assert not _corresponds(LocationEvidence(path="a", pointer="heading"), coverage)


@pytest.mark.parametrize("coverage", [PathOnly(), Absent()])
def test_path_only_coverages_accept_only_a_bare_path(coverage) -> None:
    assert _corresponds(LocationEvidence(path="a"), coverage)
    assert not _corresponds(LocationEvidence(path="a", line=1), coverage)
    assert not _corresponds(LocationEvidence(path="a", pointer="heading"), coverage)


def test_no_exposure_is_unwired_without_touching_git(tmp_path: Path) -> None:
    result = check_correspondence((), None, repo=tmp_path / "not-a-repository")
    assert (result.status, result.code) == ("unwired", "NO_EXPOSURE")


def test_protocol_mismatch_precedes_every_git_call(tmp_path: Path) -> None:
    exposure = _exposure("a" * 40, protocol=REPLAY_PROTOCOL_VERSION - 1)
    result = check_correspondence((), exposure, repo=tmp_path / "not-a-repository")
    assert (result.status, result.code) == ("unwired", "REPLAY_PROTOCOL_MISMATCH")


def test_an_absent_commit_is_unwired(tmp_path: Path) -> None:
    root, _commit = _repo(tmp_path)
    result = check_correspondence((), _exposure("a" * 40), repo=root)
    assert (result.status, result.code) == ("unwired", "EXPOSURE_UNREACHABLE")


def test_a_replay_mismatch_is_violated(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    forged = entry.model_copy(update={"sha256": "0" * 64})
    result = check_correspondence((), _exposure(commit, (forged,)), repo=root)
    assert (result.status, result.code) == ("violated", "EXPOSURE_UNREPRODUCIBLE")


def test_an_unserved_citation_is_violated(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    result = check_correspondence(
        (LocationEvidence(path="a.txt", line=1),), _exposure(commit), repo=root
    )
    assert (result.status, result.code) == ("violated", "CITATION_UNSERVED")


def test_a_served_citation_is_verified(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    result = check_correspondence(
        (LocationEvidence(path="a.txt", line=2),), _exposure(commit, (entry,)), repo=root
    )
    assert result.status == "verified"
    assert result.code is None


def test_a_refusal_contributes_no_coverage(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    closed = SurfacePolicy(deny_prefixes=("a.txt",), notice="withheld")
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"), closed)
    result = check_correspondence(
        (LocationEvidence(path="a.txt"),),
        _exposure(commit, (entry,), policy=closed),
        repo=root,
    )
    assert (result.status, result.code) == ("violated", "CITATION_UNSERVED")


def test_an_empty_file_is_full_zero_coverage(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "empty.txt"))
    exposure = _exposure(commit, (entry,))
    assert check_correspondence((LocationEvidence(path="empty.txt"),), exposure, repo=root).status == "verified"
    assert check_correspondence(
        (LocationEvidence(path="empty.txt", line=1),), exposure, repo=root
    ).code == "CITATION_UNSERVED"


def test_a_read_miss_covers_only_the_bare_path(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "absent.txt"))
    exposure = _exposure(commit, (entry,))
    assert check_correspondence((LocationEvidence(path="absent.txt"),), exposure, repo=root).status == "verified"
    assert check_correspondence(
        (LocationEvidence(path="absent.txt", line=1),), exposure, repo=root
    ).code == "CITATION_UNSERVED"


def test_search_exposes_only_hit_lines_and_unites_two_searches(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    first = _entry(root, commit, EvidenceRequest(EvidenceOp.SEARCH, "alpha"))
    last = _entry(root, commit, EvidenceRequest(EvidenceOp.SEARCH, "gamma"))
    exposure = _exposure(commit, (first, last))
    result = check_correspondence(
        (LocationEvidence(path="a.txt", line=1), LocationEvidence(path="a.txt", line=3)),
        exposure,
        repo=root,
    )
    assert result.status == "verified"
    assert check_correspondence(
        (LocationEvidence(path="a.txt", line=2),), exposure, repo=root
    ).code == "CITATION_UNSERVED"


def test_a_search_miss_contributes_no_coverage(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.SEARCH, "not-present"))
    result = check_correspondence(
        (LocationEvidence(path="a.txt"),), _exposure(commit, (entry,)), repo=root
    )
    assert result.code == "CITATION_UNSERVED"


def test_history_covers_a_bare_path_but_not_a_line(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.HISTORY, "a.txt"))
    exposure = _exposure(commit, (entry,))
    assert check_correspondence((LocationEvidence(path="a.txt"),), exposure, repo=root).status == "verified"
    assert check_correspondence(
        (LocationEvidence(path="a.txt", line=1),), exposure, repo=root
    ).code == "CITATION_UNSERVED"


def test_empty_history_contributes_no_coverage(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.HISTORY, "absent.txt"))
    result = check_correspondence(
        (LocationEvidence(path="absent.txt"),), _exposure(commit, (entry,)), repo=root
    )
    assert result.code == "CITATION_UNSERVED"


def test_a_read_supersedes_search_lines(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    read = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    search = _entry(root, commit, EvidenceRequest(EvidenceOp.SEARCH, "alpha"))
    result = check_correspondence(
        (LocationEvidence(path="a.txt", line=3),),
        _exposure(commit, (read, search)),
        repo=root,
    )
    assert result.status == "verified"


def test_read_line_count_is_lf_only(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "cr.txt"))
    result = check_correspondence(
        (LocationEvidence(path="cr.txt", line=2),), _exposure(commit, (entry,)), repo=root
    )
    assert result.code == "CITATION_UNSERVED"


def _inline(commit: str, *, target: str = "prompt.md", digest: str = "e" * 64):
    # Overrides alter only the entry; the fixed manifest makes each disagreement deliberate.
    manifest = InlineInput(target="prompt.md", sha256="e" * 64, lines=2)
    entry = ExposureEntry(
        op="inline",
        target=target,
        commit=commit,
        sha256=digest,
        outcome=Outcome.SERVED,
    )
    return manifest, entry


def test_inline_coverage_uses_the_sealed_line_count(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    manifest, entry = _inline(commit)
    result = check_correspondence(
        (LocationEvidence(path="prompt.md", line=2),),
        _exposure(commit, (entry,), inline=(manifest,)),
        repo=root,
    )
    assert result.status == "verified"


def test_inline_and_read_full_coverage_takes_the_smaller_count(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    manifest = InlineInput(target="a.txt", sha256="e" * 64, lines=4)
    inline_entry = ExposureEntry(
        op="inline",
        target="a.txt",
        commit=commit,
        sha256=manifest.sha256,
        outcome=Outcome.SERVED,
    )
    read_entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    result = check_correspondence(
        (LocationEvidence(path="a.txt", line=4),),
        _exposure(commit, (inline_entry, read_entry), inline=(manifest,)),
        repo=root,
    )
    assert result.code == "CITATION_UNSERVED"


@pytest.mark.parametrize(
    "target,digest",
    [("other.md", "e" * 64), ("prompt.md", "f" * 64)],
)
def test_inline_disagreement_is_unreproducible(
    tmp_path: Path, target: str, digest: str
) -> None:
    root, commit = _repo(tmp_path)
    manifest, entry = _inline(commit, target=target, digest=digest)
    result = check_correspondence(
        (LocationEvidence(path=target),),
        _exposure(commit, (entry,), inline=(manifest,)),
        repo=root,
    )
    assert (result.status, result.code) == ("violated", "EXPOSURE_UNREPRODUCIBLE")


def test_inline_manifest_item_without_an_entry_is_unreproducible(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    manifest, _entry = _inline(commit)
    result = check_correspondence((), _exposure(commit, inline=(manifest,)), repo=root)
    assert (result.status, result.code) == ("violated", "EXPOSURE_UNREPRODUCIBLE")


def test_two_inline_entries_against_one_manifest_item_are_unreproducible(
    tmp_path: Path,
) -> None:
    root, commit = _repo(tmp_path)
    manifest, entry = _inline(commit)
    result = check_correspondence(
        (), _exposure(commit, (entry, entry), inline=(manifest,)), repo=root
    )
    assert (result.status, result.code) == ("violated", "EXPOSURE_UNREPRODUCIBLE")


def test_identical_inline_duplicates_are_reproducible(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    manifest, entry = _inline(commit)
    result = check_correspondence(
        (), _exposure(commit, (entry, entry), inline=(manifest, manifest)), repo=root
    )
    assert result.status == "verified"


def test_contradictory_inline_line_counts_are_unreproducible(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    manifest, entry = _inline(commit)
    contradictory = manifest.model_copy(update={"lines": manifest.lines + 1})
    result = check_correspondence(
        (),
        _exposure(commit, (entry, entry), inline=(manifest, contradictory)),
        repo=root,
    )
    assert (result.status, result.code) == ("violated", "EXPOSURE_UNREPRODUCIBLE")


def test_outcome_is_replayed_beside_the_digest(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    closed = SurfacePolicy(deny_prefixes=("a.txt",), notice="withheld")
    refused = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"), closed)
    relabelled = refused.model_copy(update={"outcome": Outcome.SERVED})
    result = check_correspondence(
        (), _exposure(commit, (relabelled,), policy=closed), repo=root
    )
    assert (result.status, result.code) == ("violated", "EXPOSURE_UNREPRODUCIBLE")


def test_a_narrowed_policy_is_unreproducible_not_silently_uncovered(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    served_open = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"), OPEN)
    narrowed = SurfacePolicy(deny_prefixes=("a.txt",), notice="withheld")
    result = check_correspondence(
        (), _exposure(commit, (served_open,), policy=narrowed), repo=root
    )
    assert (result.status, result.code) == ("violated", "EXPOSURE_UNREPRODUCIBLE")


def test_replay_integrity_precedes_citations(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    forged = entry.model_copy(update={"sha256": "0" * 64})
    result = check_correspondence(
        (LocationEvidence(path="never-served.txt"),),
        _exposure(commit, (forged,)),
        repo=root,
    )
    assert result.code == "EXPOSURE_UNREPRODUCIBLE"


def test_text_only_and_empty_evidence_are_vacuously_verified(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    for evidence in ((), (TextEvidence(text="prose belongs in the note"),)):
        result = check_correspondence(evidence, _exposure(commit), repo=root)
        assert result.status == "verified"
        assert result.reason


def test_verify_commit_rejects_a_present_noncommit_oid(tmp_path: Path) -> None:
    root, _commit = _repo(tmp_path)
    tree_oid = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
    ).stdout.decode().strip()
    entry = ExposureEntry(
        op="read",
        target="a.txt",
        commit=tree_oid,
        sha256="0" * 64,
        outcome=Outcome.SERVED,
    )
    result = check_correspondence((), _exposure(tree_oid, (entry,)), repo=root)
    assert (result.status, result.code) == ("unwired", "EXPOSURE_UNREACHABLE")


def test_a_serve_error_after_environment_checks_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))

    def fail(*args, **kwargs):
        raise ServeError("runtime format changed")

    monkeypatch.setattr(correspondence_module, "serve", fail)
    with pytest.raises(ServeError, match="runtime format changed"):
        check_correspondence((), _exposure(commit, (entry,)), repo=root)


def test_identical_requests_replay_once_within_one_exposure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    real_serve = correspondence_module.serve
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_serve(*args, **kwargs)

    monkeypatch.setattr(correspondence_module, "serve", counted)
    result = check_correspondence((), _exposure(commit, (entry, entry)), repo=root)
    assert result.status == "verified"
    assert calls == 1


def test_replay_cache_does_not_cross_exposures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.READ, "a.txt"))
    real_serve = correspondence_module.serve
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_serve(*args, **kwargs)

    monkeypatch.setattr(correspondence_module, "serve", counted)
    check_correspondence((), _exposure(commit, (entry,), policy=OPEN), repo=root)
    check_correspondence(
        (),
        _exposure(commit, (entry,), policy=SurfacePolicy(notice="a different sealed policy")),
        repo=root,
    )
    assert calls == 2


def test_a_shallow_replay_repository_is_unwired(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    entry = _entry(root, commit, EvidenceRequest(EvidenceOp.HISTORY, "a.txt"))
    clone = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", root.as_uri(), str(clone)],
        check=True,
        capture_output=True,
    )
    result = check_correspondence((), _exposure(commit, (entry,)), repo=clone)
    assert (result.status, result.code) == ("unwired", "EXPOSURE_UNREACHABLE")
