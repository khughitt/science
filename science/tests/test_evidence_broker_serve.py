from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from science_model.evidence_broker import SurfacePolicy

from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest, authorize
from science_tool.evidence_broker.serve import Outcome, ServeError, serve, verify_commit

OPEN = SurfacePolicy(notice="withheld")
CLOSED = SurfacePolicy(deny_prefixes=("private", "notes/a[b].md"), notice="withheld")
ZERO = "0" * 40


def _repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    (root / "private").mkdir(parents=True)
    (root / "privateer").mkdir()
    (root / "notes").mkdir()
    (root / "src").mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "p@example.invalid"),
        ("config", "user.name", "P"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    (root / "a.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    (root / "empty.txt").write_text("", encoding="utf-8")
    (root / "private" / "x.txt").write_text("secret\n", encoding="utf-8")
    (root / "privateer" / "p.txt").write_text("secret\n", encoding="utf-8")
    (root / "notes" / "a[b].md").write_text("secret\n", encoding="utf-8")
    (root / "notes" / "ab.md").write_text("secret\n", encoding="utf-8")
    # Every AGREEMENT row must be a REAL FILE WITH SEARCHABLE CONTENT, or the search half of
    # the table passes vacuously on the rows whose paths do not exist -- green while asserting
    # nothing. `src/main.py` and `privateer/x.txt` exist only for that.
    (root / "src" / "main.py").write_text("secret\n", encoding="utf-8")
    (root / "privateer" / "x.txt").write_text("secret\n", encoding="utf-8")
    # A directory whose NAME is git's own miss sentence, so a substring classifier reports
    # it absent. It is committed, so `cat-file -t` must answer `tree`.
    (root / "does not exist in").mkdir()
    (root / "does not exist in" / "f.txt").write_text("present\n", encoding="utf-8")
    # A file whose name contains a literal backslash, with NOTHING at `a/b`. The two
    # spellings therefore read different things, which is what makes the normalization
    # test below able to fail.
    (root / "a\\b").write_text("raw\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"], check=True, capture_output=True
    )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
    ).stdout.decode().strip()
    return root, commit


def _read(target: str) -> EvidenceRequest:
    return EvidenceRequest(op=EvidenceOp.READ, target=target)


def _search(pattern: str, pathspec: str | None = None) -> EvidenceRequest:
    return EvidenceRequest(op=EvidenceOp.SEARCH, target=pattern, pathspec=pathspec)


def test_read_serves_the_blob(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _read("a.txt"), OPEN)
    assert served.outcome is Outcome.SERVED
    assert served.payload == b"alpha\nbeta\n"


def test_an_empty_file_is_served_not_missed(tmp_path: Path):
    """"Shipped as a stub" is a different fact from "never shipped", and a reviewer that
    cannot tell them apart will report the wrong one."""
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _read("empty.txt"), OPEN)
    assert served.outcome is Outcome.SERVED
    assert served.payload == b""


def test_an_absent_path_is_a_defined_miss(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _read("nope.txt"), OPEN)
    assert served.outcome is Outcome.MISS_ABSENT
    assert served.payload  # the marker, so the hash covers the answer


def test_an_absent_path_that_exists_on_disk_is_the_same_miss(tmp_path: Path):
    """git spells this miss two ways depending on the working tree, which the actor owns.
    A classifier that knows only one turns an ordinary absent path into a halted run for
    exactly the paths the actor happened to create."""
    root, commit = _repo(tmp_path)
    (root / "later.txt").write_text("added after the commit\n", encoding="utf-8")
    served = serve(root, commit, _read("later.txt"), OPEN)
    assert served.outcome is Outcome.MISS_ABSENT


def test_read_refuses_a_directory(tmp_path: Path):
    """`git show <commit>:<dir>` answers this with a tree listing at exit 0. Served that
    way it would record FULL coverage over a directory listing, and a citation into it
    would correspond while resting on no file at all."""
    root, commit = _repo(tmp_path)
    # OPEN, deliberately: under CLOSED this path is refused by policy and the tree would
    # never be reached, so the test would pass without proving anything about `read`.
    #
    # `match=` distinguishes a TYPED refusal from an unclassifiable one -- without it this
    # test is satisfied by any `ServeError` at all, including the one a broken classifier
    # raises for a reason that has nothing to do with `cat-file -t` typing the path.
    with pytest.raises(ServeError, match="names a tree"):
        serve(root, commit, _read("private"), OPEN)


def test_a_directory_named_like_the_miss_message_is_not_a_miss(tmp_path: Path):
    """MEASURED: `cat-file blob <c>:does not exist in` fails with
    `fatal: git cat-file <c>:does not exist in: bad file`, which CONTAINS git's miss
    sentence. A substring classifier serves a present directory as an absent path, and
    tells the reviewer a file is missing when it is there."""
    root, commit = _repo(tmp_path)
    # `match=` is load-bearing here too: without the `cat-file -t` step, `cat-file blob`
    # alone would ALSO raise `ServeError` for this directory (as `could not be classified`),
    # so an unmatched `pytest.raises` cannot tell a typed refusal from an unclassifiable one
    # -- it would pass whether or not the typing step ever ran.
    with pytest.raises(ServeError, match="names a tree"):
        serve(root, commit, _read("does not exist in"), OPEN)


def test_a_wellformed_miss_naming_a_different_path_is_not_a_miss(tmp_path: Path, monkeypatch):
    """Certifies the ANCHORED comparison in `_absent_sentences` against a fake, because behind
    the `cat-file -t` type check every git-produced failure this module can actually reach is
    already a genuine miss for the requested path -- live git offers no counterexample to point
    at. THE FAKE ANSWERS `rev-parse` TRUTHFULLY (so the call reaches the read classifier, as in
    `test_unrecognised_git_output_raises`) and then reports a well-formed miss sentence naming a
    DIFFERENT path than the one requested. Real code must raise, because the sentence's path and
    the request's path disagree; a classifier that matched `does not exist in` as a bare
    substring would call this a miss for `a.txt` on git's word about `other.txt`.
    """
    root, commit = _repo(tmp_path)
    import science_tool.evidence_broker.serve as serve_module

    real_run_git = serve_module.run_git

    def _fake(repo_root, *args, **kwargs):
        if args[0] == "rev-parse":
            return real_run_git(repo_root, *args, **kwargs)

        class _Strange:
            returncode = 128
            stdout = b""
            stderr = f"fatal: path 'other.txt' does not exist in '{commit}'\n".encode()

        return _Strange()

    monkeypatch.setattr(serve_module, "run_git", _fake)
    with pytest.raises(ServeError, match="could not be classified"):
        serve(root, commit, _read("a.txt"), OPEN)


def test_a_denied_read_makes_no_git_call_at_all(tmp_path: Path, monkeypatch):
    """Not merely "is refused": a withheld path must leave no trace in a process table or
    a timing difference, so `authorize` runs before `verify_commit` and before anything
    else. `run_git` is replaced with a landmine rather than observed after the fact."""
    root, commit = _repo(tmp_path)
    import science_tool.evidence_broker.serve as serve_module

    def _landmine(*args, **kwargs):
        raise AssertionError(f"a denied request reached git: {args}")

    monkeypatch.setattr(serve_module, "run_git", _landmine)
    served = serve(root, commit, _read("private/x.txt"), CLOSED)

    assert served.outcome is Outcome.REFUSED
    assert served.denial is not None
    assert served.payload == b""


def test_a_history_glob_cannot_walk_around_a_deny_prefix(tmp_path: Path):
    """MEASURED policy bypass: `priv*` is under no deny prefix as text, and as a bare
    pathspec git expands it onto `private/x.txt`. The literal pathspec is what keeps the
    authorized spelling and the searched spelling the same string."""
    root, commit = _repo(tmp_path)
    served = serve(root, commit, EvidenceRequest(op=EvidenceOp.HISTORY, target="priv*"), CLOSED)
    assert served.outcome is Outcome.MISS_NO_COMMITS


def test_a_search_pathspec_glob_cannot_walk_around_a_deny_prefix(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _search("secret", pathspec="priv*"), CLOSED)
    assert served.outcome is Outcome.MISS_NO_MATCH


FILE_DENY = SurfacePolicy(deny_prefixes=("private/x.txt",), notice="withheld")


def _repo_with_split_history(tmp_path: Path) -> tuple[Path, str, str]:
    """Two commits under ONE ancestor: one touching a denied file, one touching an allowed
    sibling. Returns `(root, allowed_commit, denied_commit)`; the denied one is HEAD.

    Both descendants live under `private/`, which is the whole point. A control that asked
    about a path OUTSIDE the ancestor cannot tell a precise exclusion from one that dropped
    the entire subtree -- both answer the same way -- so it would pass against the
    over-broad fix as readily as the correct one.
    """
    root = tmp_path / "split"
    (root / "private").mkdir(parents=True)
    for args in (
        ("init", "-q"),
        ("config", "user.email", "p@example.invalid"),
        ("config", "user.name", "P"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    def _commit(message: str) -> str:
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-q", "-m", message], check=True, capture_output=True
        )
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
        ).stdout.decode().strip()

    (root / "private" / "public.txt").write_text("allowed\n", encoding="utf-8")
    allowed = _commit("touch the allowed sibling")
    (root / "private" / "x.txt").write_text("secret\n", encoding="utf-8")
    denied = _commit("touch the denied descendant")
    return root, allowed, denied


def test_history_of_an_ancestor_does_not_report_a_denied_descendant(tmp_path: Path):
    """MEASURED: with deny prefix `private/x.txt`, the target `private` is beneath no
    prefix and authorizes -- `read` refuses it as a tree, but `log` selects paths
    RECURSIVELY, so `:(top,literal)private` reports every commit touching the denied file.

    Authorization answers "is this path denied". It cannot answer "does this path CONTAIN
    something denied", so `log` carries the exclusions exactly as `grep` does.
    """
    root, _allowed, denied = _repo_with_split_history(tmp_path)
    served = serve(
        root, denied, EvidenceRequest(op=EvidenceOp.HISTORY, target="private"), FILE_DENY
    )
    assert denied.encode() not in served.payload


def test_the_history_exclusions_withhold_only_the_denied_descendant(tmp_path: Path):
    """The control, and it must live INSIDE the ancestor. Dropping all of `private` would
    satisfy the test above just as well, so precision is what this asserts: the allowed
    sibling's commit is still reported, from the same query."""
    root, allowed, denied = _repo_with_split_history(tmp_path)
    served = serve(
        root, denied, EvidenceRequest(op=EvidenceOp.HISTORY, target="private"), FILE_DENY
    )
    assert served.outcome is Outcome.SERVED
    assert allowed.encode() in served.payload


def test_a_working_tree_symlink_does_not_redirect_or_deny_a_read(tmp_path: Path):
    """§7's policy bullet. The served surface is a blob read at a pinned commit, which
    never consults the working tree -- so replacing a committed file with a symlink must
    change nothing. A `resolve()`-based containment check would have denied this request,
    and would have bought no security doing so: there is no filesystem lookup to protect.
    """
    root, commit = _repo(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("not the committed bytes\n", encoding="utf-8")
    (root / "a.txt").unlink()
    (root / "a.txt").symlink_to(outside)

    served = serve(root, commit, _read("a.txt"), OPEN)

    assert served.outcome is Outcome.SERVED
    assert served.payload == b"alpha\nbeta\n"


def test_the_normalized_path_is_what_git_reads(tmp_path: Path):
    """`a\\b` normalizes to `a/b`, and the fixture commits a file at the FORMER and nothing
    at the latter. So the two spellings read different things, and the outcome says which
    one `serve` used: a request judged as `a/b` must miss, while a caller passing its own
    raw string would be served `raw\\n` -- authorizing one path and reading another.

    A gentler spelling such as `.//a.txt` proves nothing here: git resolves it to `a.txt`
    itself, so both the raw and the normalized form succeed and the test cannot fail.
    """
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _read("a\\b"), OPEN)
    assert served.outcome is Outcome.MISS_ABSENT
    assert served.payload != b"raw\n"


def test_the_normalized_path_is_what_history_walks(tmp_path: Path):
    """The HISTORY sibling of `test_the_normalized_path_is_what_git_reads`. `a\\b` normalizes
    to `a/b`, which has no history at all, while the raw spelling names a real committed file
    with one commit. A request judged as `a/b` must report no commits; a caller passing
    `request.target` straight through to `log` would instead report history for the committed
    `a\\b`.
    """
    root, commit = _repo(tmp_path)
    served = serve(root, commit, EvidenceRequest(op=EvidenceOp.HISTORY, target="a\\b"), OPEN)
    assert served.outcome is Outcome.MISS_NO_COMMITS


def test_the_normalized_path_is_what_search_is_restricted_to(tmp_path: Path):
    """The SEARCH sibling. `a\\b` normalizes to `a/b`, which does not exist, so a search
    restricted to that pathspec must miss even though `raw` -- the pattern -- IS the literal
    content of the committed `a\\b`. A caller passing `request.pathspec` straight through would
    instead search the real file and find it.
    """
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _search("raw", pathspec="a\\b"), OPEN)
    assert served.outcome is Outcome.MISS_NO_MATCH


def test_search_hits_carry_commit_path_and_line(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _search("alpha"), OPEN)
    assert served.outcome is Outcome.SERVED
    assert served.payload == f"{commit}:a.txt".encode() + b"\x001\x00alpha\n"


def test_a_search_with_no_matches_is_a_defined_miss(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _search("zzzznope"), OPEN)
    assert served.outcome is Outcome.MISS_NO_MATCH


def test_a_malformed_pattern_is_refused_not_raised(tmp_path: Path):
    """The requester's own input, carrying no repository fact. Raising would halt an
    honest run over a typo."""
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _search("a["), OPEN)
    assert served.outcome is Outcome.REFUSED
    assert served.denial is not None
    assert served.denial.reason == "pattern-malformed"


def test_search_carries_the_policy_exclusions_even_with_no_pathspec(tmp_path: Path):
    """Search never names a path, so denying a directory to `read` while grep returns
    hits from inside it denies nothing."""
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _search("secret"), CLOSED)
    assert served.outcome is Outcome.SERVED
    assert b"private/x.txt" not in served.payload
    assert b"notes/a[b].md" not in served.payload
    assert b"privateer/p.txt" in served.payload
    assert b"notes/ab.md" in served.payload


def test_history_serves_commits(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(root, commit, EvidenceRequest(op=EvidenceOp.HISTORY, target="a.txt"), OPEN)
    assert served.outcome is Outcome.SERVED
    assert served.payload.startswith(commit.encode())


def test_history_with_no_commits_is_a_defined_miss(tmp_path: Path):
    root, commit = _repo(tmp_path)
    served = serve(
        root, commit, EvidenceRequest(op=EvidenceOp.HISTORY, target="nope.txt"), OPEN
    )
    assert served.outcome is Outcome.MISS_NO_COMMITS


def test_a_wellformed_nonexistent_commit_halts_rather_than_answering(tmp_path: Path):
    """THE regression test. `0`*40 makes git emit the MISS message, so an implementation
    that classifies before verifying answers "absent at commit" for a bogus revision --
    and passes a test written with a malformed ref instead."""
    root, _commit = _repo(tmp_path)
    with pytest.raises(ServeError):
        verify_commit(root, ZERO)
    with pytest.raises(ServeError):
        serve(root, ZERO, _read("a.txt"), OPEN)


def test_unrecognised_git_output_raises(tmp_path: Path, monkeypatch):
    """Anything git reports that is not a defined miss halts the run. A broker that
    guessed would turn an instrument failure into evidence.

    THE EARLIER FAKE FAILED EVERY CALL, so `verify_commit` raised and the read
    classifier was never reached -- the test passed without exercising the code it
    names. This one answers the verification truthfully and only then goes strange.
    """
    root, commit = _repo(tmp_path)
    import science_tool.evidence_broker.serve as serve_module

    real_run_git = serve_module.run_git
    calls: list[tuple] = []

    def _fake(repo_root, *args, **kwargs):
        calls.append(args)
        if args[0] == "rev-parse":
            return real_run_git(repo_root, *args, **kwargs)

        class _Strange:
            returncode = 128
            stdout = b""
            stderr = b"fatal: something nobody has seen before\n"

        return _Strange()

    monkeypatch.setattr(serve_module, "run_git", _fake)
    with pytest.raises(ServeError, match="could not be classified"):
        serve(root, commit, _read("a.txt"), OPEN)

    # The verification really did run, so the raise came from the read classifier.
    assert calls[0][0] == "rev-parse"
    assert len(calls) > 1


def test_unrecognised_search_output_raises(tmp_path: Path, monkeypatch):
    """The SEARCH sibling of `test_unrecognised_git_output_raises`. A `grep` failure that does
    not carry the argv-rejection prefix must halt rather than be reported as a retryable
    refusal -- the pattern classifier is as narrow as the read classifier is, and needs the
    same proof that it does not swallow an unfamiliar failure as a defined outcome.
    """
    root, commit = _repo(tmp_path)
    import science_tool.evidence_broker.serve as serve_module

    real_run_git = serve_module.run_git
    calls: list[tuple] = []

    def _fake(repo_root, *args, **kwargs):
        calls.append(args)
        if args[0] == "rev-parse":
            return real_run_git(repo_root, *args, **kwargs)

        class _Strange:
            returncode = 128
            stdout = b""
            stderr = b"fatal: something nobody has seen before\n"

        return _Strange()

    monkeypatch.setattr(serve_module, "run_git", _fake)
    with pytest.raises(ServeError, match="could not be classified"):
        serve(root, commit, _search("alpha"), OPEN)

    assert calls[0][0] == "rev-parse"
    assert len(calls) > 1


def test_a_wellformed_malformed_pattern_naming_a_different_pattern_is_not_a_refusal(
    tmp_path: Path, monkeypatch
):
    """The SEARCH sibling of `test_a_wellformed_miss_naming_a_different_path_is_not_a_miss`.
    Certifies the ANCHORED prefix in `_malformed_pattern_prefix` against a fake, for the same
    reason that one needed a fake: live git never hands this module a malformed-pattern
    diagnostic naming any pattern OTHER than the one just sent, so there is no reachable
    counterexample to point real git at.

    THE FAKE ANSWERS `rev-parse` TRUTHFULLY (so the call reaches the search classifier) and
    then reports a well-formed malformed-pattern diagnostic naming a DIFFERENT pattern than
    the one requested: the request sends `alpha`, but stderr complains about `other-pattern`.
    Real code must raise `ServeError`, because git is not actually refusing the pattern this
    request sent. An unanchored classifier that merely checked for `-e option` or `Invalid
    regular expression` anywhere in stderr would call this a REFUSAL of `alpha` and hand back
    a denial for a request that was never malformed -- which is exactly the failure mode
    `_absent_sentences`' anchoring exists to prevent on the `read` side.
    """
    root, commit = _repo(tmp_path)
    import science_tool.evidence_broker.serve as serve_module

    real_run_git = serve_module.run_git

    def _fake(repo_root, *args, **kwargs):
        if args[0] == "rev-parse":
            return real_run_git(repo_root, *args, **kwargs)

        class _Strange:
            returncode = 128
            stdout = b""
            stderr = b"fatal: -e option, 'other-pattern': Invalid regular expression\n"

        return _Strange()

    monkeypatch.setattr(serve_module, "run_git", _fake)
    with pytest.raises(ServeError, match="could not be classified"):
        serve(root, commit, _search("alpha"), OPEN)


def _sabotage_the_object_store(root: Path) -> None:
    """Make git warn on stderr before every verdict, through a channel `-c` cannot reach.

    `.git/objects/info/alternates` is untracked, actor-writable, and has NO config key, so
    `run_git`'s `-c` hardening does not touch it. MEASURED, git 2.55: with a nonexistent path
    written there, `cat-file -t` for an absent path answers

        error: unable to normalize alternate object path: /nonexistent/objects
        fatal: path 'nope.txt' does not exist in '<commit>'

    and `grep` with a bad pattern gets the same warning above its own diagnostic. The repository
    still resolves every object it needs -- this is a warning, not a broken store -- so the
    honest answer is still available and only the classifier's view of stderr changed.
    """
    alternates = root / ".git" / "objects" / "info" / "alternates"
    alternates.parent.mkdir(parents=True, exist_ok=True)
    alternates.write_text("/nonexistent/objects\n", encoding="utf-8")


def test_an_absent_path_is_still_a_miss_under_an_actor_written_stderr_warning(tmp_path: Path):
    """A comparison against the WHOLE of stderr lets the actor convert every defined miss into
    a halted run: two lines match neither absent sentence, `_serve_read` raises, and §5.1's
    "frequently the decisive finding" -- an absent path -- becomes unrecordable at the audited
    repository's discretion. Anchoring on the verdict LINE keeps the whole-sentence comparison
    while letting git warn.
    """
    root, commit = _repo(tmp_path)
    _sabotage_the_object_store(root)
    served = serve(root, commit, _read("nope.txt"), OPEN)
    assert served.outcome is Outcome.MISS_ABSENT


def test_a_malformed_pattern_is_still_a_refusal_under_an_actor_written_stderr_warning(
    tmp_path: Path,
):
    """The SEARCH half of the same lever: the `startswith` anchor is defeated by anything
    printed above git's verdict, turning a retryable refusal into a halt."""
    root, commit = _repo(tmp_path)
    _sabotage_the_object_store(root)
    served = serve(root, commit, _search("a["), OPEN)
    assert served.outcome is Outcome.REFUSED
    assert served.denial is not None
    assert served.denial.reason == "pattern-malformed"
    # The notice goes to a BLINDED requester. The warning names a filesystem path the actor
    # chose; the verdict line echoes only the pattern the requester itself sent.
    assert served.denial.notice == "fatal: -e option, 'a[': Invalid regular expression"
    assert "alternate" not in served.denial.notice


# THE AGREEMENT TABLE. Two mechanisms for one policy is how a policy comes to be half enforced,
# so the READ denial and the SEARCH exclusion are asserted against ONE set of inputs rather than
# each against its own expectations. Both halves below are parametrized over this tuple, which
# is the point: a table consumed by one mechanism is not an agreement table, it is that
# mechanism's own expectations with a misleading name.
#
# Every path here is a real file in `_repo` with `secret` as its content, so no row can pass the
# search half vacuously. `private` is the exception BY CONSTRUCTION -- it is the deny prefix
# itself and is a directory, so the search half reads it as "nothing at or beneath this path is
# served", which is the only reading a directory admits and is not vacuous.
AGREEMENT: tuple[tuple[str, bool], ...] = (
    ("private/x.txt", True),
    ("private", True),
    ("privateer/x.txt", False),
    ("notes/a[b].md", True),
    ("notes/ab.md", False),
    ("src/main.py", False),
)


@pytest.mark.parametrize("path,denied", AGREEMENT)
def test_read_denial_matches_the_table(path: str, denied: bool):
    assert (authorize(_read(path), CLOSED).denial is not None) is denied


def _searched_paths(payload: bytes, commit: str) -> set[str]:
    """The paths `grep` reported. `-z` records are `<commit>:<path>\\0<line-number>\\0<line>`,
    one per line, and the record prefix is asserted rather than assumed -- a payload this helper
    could not parse would otherwise be reported as an empty result set, which reads as "denied"
    for every row and makes the table pass on a broken search.
    """
    prefix = f"{commit}:".encode()
    paths: set[str] = set()
    for record in payload.split(b"\n"):
        if not record:
            continue
        assert record.startswith(prefix), f"unparsed grep record: {record!r}"
        paths.add(record[len(prefix) :].split(b"\x00")[0].decode("utf-8"))
    return paths


@pytest.mark.parametrize("path,denied", AGREEMENT)
def test_search_exclusion_matches_the_table(tmp_path: Path, path: str, denied: bool):
    """The half that was missing. `authorize` and `exclude_pathspecs` are independent
    implementations of one policy, and the one that was never checked against the table is the
    one that can drift: the exclusion's PATHSPEC MAGIC decides what git matches, and a change
    there is invisible to a table only `read` consumes.

    MEASURED, git 2.55, by mutation: rewriting `literal` to `glob` in `exclude_pathspecs` fails
    the `notes/ab.md` row here while all six rows of `test_read_denial_matches_the_table` stay
    green -- `glob` leaves `[b]` a character class, so the exclusion for `notes/a[b].md` also
    withholds a sibling the policy never denied and `read` serves without objection. That is the
    divergence, in the over-excluding direction.

    NOT EVERY EXCLUSION MUTATION IS BEHAVIOURAL, and the table should not be credited with more
    than it has. Also measured against this fixture: dropping `top`, and adding `icase`, change
    NOTHING -- `run_git` passes `-C <repo_root>`, so the pathspecs are already rooted and `top`
    is inert, and the fixture holds no case-variant paths for `icase` to reach. Those two
    spellings are pinned by `test_exclusions_are_top_literal_and_exclude`, textually, which is
    the only way a no-op spelling CAN be pinned.
    """
    root, commit = _repo(tmp_path)
    served = serve(root, commit, _search("secret"), CLOSED)
    assert served.outcome is Outcome.SERVED
    reported = _searched_paths(served.payload, commit)
    beneath = {seen for seen in reported if seen == path or seen.startswith(f"{path}/")}
    if denied:
        assert not beneath, f"`read` denies {path!r}; `search` served {sorted(beneath)}"
    else:
        assert path in reported, f"`read` allows {path!r}; `search` withheld it"
