from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

import pytest

from science_model.autonomous_runs import RunTier
from science_model.evidence_broker import (
    MAX_TARGET_CHARS,
    EvidenceSession,
    InlineInput,
    InstrumentIdentity,
    Outcome,
    SurfacePolicy,
)
from science_tool.autonomy.baseline import BaselineError
from science_tool.autonomy.extract import extract_change_set
from science_tool.autonomy.path_gate import evaluate
from science_tool.evidence_broker import session as session_module
from science_tool.evidence_broker.journal import create_journal, open_journal, read_journal
from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
from science_tool.evidence_broker.serve import MISS_MARKERS
from science_tool.evidence_broker.session import Session, SessionError

EXPECTED_BYTES = b"alpha\nbeta\n"
INSTRUMENT = InstrumentIdentity(ref="rubric.md", sha256="c" * 64, prompt_hash="d" * 64)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True
    ).stdout.decode().strip()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "private").mkdir(parents=True)
    (root / "a").mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "p@example.invalid"),
        ("config", "user.name", "P"),
    ):
        _git(root, *args)
    (root / "a.md").write_bytes(EXPECTED_BYTES)
    (root / "b.md").write_text("bravo\n", encoding="utf-8")
    (root / "copy-of-a.md").write_bytes(EXPECTED_BYTES)
    (root / "a" / "b").write_text("normalized\n", encoding="utf-8")
    (root / "private" / "x.md").write_text("secret\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")
    return root


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "control-plane" / "run-x"
    directory.mkdir(parents=True)
    return directory


@pytest.fixture
def session_model(project: Path, run_dir: Path) -> EvidenceSession:
    return EvidenceSession(
        session_id=run_dir.name,
        journal_path=run_dir / "journal.jsonl",
        commit=_git(project, "rev-parse", "HEAD"),
        budget=1,
        surface_policy=SurfacePolicy(notice="withheld"),
        instrument=INSTRUMENT,
        inline=(),
    )


@pytest.fixture
def session_at(project: Path, session_model: EvidenceSession):
    def build(
        *, budget: int, deny_prefixes: tuple[str, ...] = (), inline_count: int = 0
    ) -> Session:
        inline = tuple(
            InlineInput(target=f"seed{number}.md", sha256="f" * 64, lines=1)
            for number in range(inline_count)
        )
        model = session_model.model_copy(
            update={
                "budget": budget,
                "surface_policy": SurfacePolicy(
                    deny_prefixes=deny_prefixes, notice="withheld"
                ),
                "inline": inline,
            }
        )
        create_journal(model.journal_path, project_root=project, inline=inline)
        return Session(project, model)

    return build


@pytest.mark.parametrize(
    "evidence_request",
    [
        pytest.param(
            EvidenceRequest(op=EvidenceOp.READ, target="a" * (MAX_TARGET_CHARS + 1)),
            id="target",
        ),
        pytest.param(
            EvidenceRequest(
                op=EvidenceOp.SEARCH,
                target="pattern",
                pathspec="a" * (MAX_TARGET_CHARS + 1),
            ),
            id="pathspec",
        ),
    ],
)
def test_an_overlong_request_is_a_usage_error_before_git_or_spend(
    session_at, monkeypatch, evidence_request
) -> None:
    session = session_at(budget=3)

    def git_is_a_landmine(*_args, **_kwargs):
        raise AssertionError("an overlong requester-owned value must not reach git")

    monkeypatch.setattr(session_module, "_serve", git_is_a_landmine)
    with pytest.raises(SessionError, match="characters"):
        session.request(evidence_request)
    assert session.requests_used() == 0


def test_a_denial_spends_a_round(session_at) -> None:
    session = session_at(budget=3, deny_prefixes=("private",))
    receipt = session.request(EvidenceRequest(op=EvidenceOp.READ, target="private/x.md"))
    assert receipt.outcome is Outcome.REFUSED
    assert session.requests_used() == 1


def test_a_malformed_pattern_spends_a_round(session_at) -> None:
    session = session_at(budget=3)
    receipt = session.request(EvidenceRequest(op=EvidenceOp.SEARCH, target="a\0b"))
    assert receipt.outcome is Outcome.REFUSED
    assert session.requests_used() == 1


def test_exhaustion_refuses_and_appends_nothing(session_at) -> None:
    session = session_at(budget=1)
    session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    receipt = session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert receipt.outcome is Outcome.REFUSED
    assert session.requests_used() == 1


def test_a_budget_allows_exactly_that_many_requests(session_at) -> None:
    session = session_at(budget=2)
    for _ in range(2):
        assert session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md")).path
    assert session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md")).path is None
    assert session.requests_used() == 2


def test_a_refusal_writes_no_served_file(session_at, run_dir: Path) -> None:
    session = session_at(budget=3, deny_prefixes=("private",))
    receipt = session.request(EvidenceRequest(op=EvidenceOp.READ, target="private/x.md"))
    assert receipt.path is None
    assert receipt.sha256 is None
    assert list((run_dir / "served").glob("*")) == []


def test_a_defined_miss_does_write_its_marker(session_at) -> None:
    session = session_at(budget=3)
    receipt = session.request(EvidenceRequest(op=EvidenceOp.READ, target="absent.md"))
    assert receipt.outcome is Outcome.MISS_ABSENT
    assert receipt.path is not None
    assert receipt.path.read_bytes() == MISS_MARKERS[Outcome.MISS_ABSENT]


def test_the_served_name_is_the_digest_of_the_bytes(session_at) -> None:
    session = session_at(budget=3)
    receipt = session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert receipt.path is not None
    assert receipt.path.name == hashlib.sha256(receipt.path.read_bytes()).hexdigest()


def test_two_requests_serving_identical_bytes_coincide(session_at) -> None:
    session = session_at(budget=3)
    first = session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    second = session.request(EvidenceRequest(op=EvidenceOp.READ, target="copy-of-a.md"))
    assert first.path == second.path
    assert session.requests_used() == 2


def test_seeding_leaves_requests_used_at_zero(session_at) -> None:
    assert session_at(budget=3, inline_count=4).requests_used() == 0


def test_the_authorized_spelling_is_journaled(session_at, project: Path) -> None:
    session = session_at(budget=3)
    session.request(EvidenceRequest(op=EvidenceOp.READ, target="a\\b"))
    with open_journal(session._session.journal_path, project_root=project) as handle:
        (entry,) = read_journal(handle)
    assert entry.target == "a/b"


@pytest.mark.parametrize(
    ("evidence_request", "outcome", "target", "pathspec"),
    [
        (EvidenceRequest(EvidenceOp.READ, "absent.md"), Outcome.MISS_ABSENT, "absent.md", None),
        (
            EvidenceRequest(EvidenceOp.SEARCH, "never-matches", "a\\b"),
            Outcome.MISS_NO_MATCH,
            "never-matches",
            "a/b",
        ),
        (
            EvidenceRequest(EvidenceOp.HISTORY, "absent.md"),
            Outcome.MISS_NO_COMMITS,
            "absent.md",
            None,
        ),
        (
            EvidenceRequest(EvidenceOp.READ, "private/x.md"),
            Outcome.REFUSED,
            "private/x.md",
            None,
        ),
    ],
)
def test_every_nonserved_outcome_keeps_its_target(
    session_at, project: Path, evidence_request, outcome, target, pathspec
) -> None:
    denied = ("private",) if outcome is Outcome.REFUSED else ()
    session = session_at(budget=3, deny_prefixes=denied)
    assert session.request(evidence_request).outcome is outcome
    with open_journal(session._session.journal_path, project_root=project) as handle:
        (entry,) = read_journal(handle)
    assert (entry.target, entry.pathspec) == (target, pathspec)


def test_a_journal_inside_the_project_cannot_construct_a_session(
    project: Path, session_model: EvidenceSession
) -> None:
    inside = session_model.model_copy(update={"journal_path": project / "runs" / "j.jsonl"})
    with pytest.raises(BaselineError, match="inside the project"):
        Session(project, inside)


def test_a_symlinked_journal_path_landing_in_the_project_is_refused(
    project: Path, tmp_path: Path, session_model: EvidenceSession
) -> None:
    (project / "runs").mkdir()
    link = tmp_path / "outside"
    link.symlink_to(project / "runs")
    linked = session_model.model_copy(update={"journal_path": link / "j.jsonl"})
    with pytest.raises(BaselineError, match="inside the project"):
        Session(project, linked)


def test_a_truncated_file_at_the_digest_name_is_replaced(session_at, run_dir: Path) -> None:
    session = session_at(budget=3)
    digest = hashlib.sha256(EXPECTED_BYTES).hexdigest()
    (run_dir / "served").mkdir()
    (run_dir / "served" / digest).write_bytes(EXPECTED_BYTES[:3])
    receipt = session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert receipt.path is not None
    assert receipt.path.read_bytes() == EXPECTED_BYTES


def test_a_planted_leaf_symlink_is_replaced_not_written_through(
    session_at, project: Path, run_dir: Path
) -> None:
    session = session_at(budget=3)
    victim = project / "victim.txt"
    victim.write_text("original\n", encoding="utf-8")
    digest = hashlib.sha256(EXPECTED_BYTES).hexdigest()
    (run_dir / "served").mkdir()
    (run_dir / "served" / digest).symlink_to(victim)
    session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert victim.read_text(encoding="utf-8") == "original\n"
    assert not (run_dir / "served" / digest).is_symlink()


def test_a_planted_directory_symlink_is_refused(
    session_at, project: Path, run_dir: Path
) -> None:
    session = session_at(budget=3)
    (run_dir / "served").symlink_to(project, target_is_directory=True)
    with pytest.raises(OSError):
        session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert list(project.glob("*.partial")) == []
    assert session.requests_used() == 0


def test_an_ancestor_swapped_inside_the_critical_section_is_not_followed(
    session_at, project: Path, tmp_path: Path, monkeypatch
) -> None:
    session = session_at(budget=3)
    project_served = project / "run-x" / "served"
    project_served.mkdir(parents=True)
    control_plane = tmp_path / "control-plane"
    inner = session_module._serve

    def swap_then_serve(*args, **kwargs):
        control_plane.rename(tmp_path / "control-plane-moved")
        control_plane.symlink_to(project, target_is_directory=True)
        return inner(*args, **kwargs)

    monkeypatch.setattr(session_module, "_serve", swap_then_serve)
    with pytest.raises(SessionError, match="delivery path"):
        session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert list(project_served.iterdir()) == []
    moved = tmp_path / "control-plane-moved" / "run-x" / "journal.jsonl"
    assert moved.read_text(encoding="utf-8") == ""


def _raising_oserror(*_args: object, **_kwargs: object) -> Path:
    raise OSError("disk full")


def test_a_failed_served_write_records_nothing(session_at, monkeypatch) -> None:
    session = session_at(budget=3)
    monkeypatch.setattr(Session, "_write_served", _raising_oserror)
    with pytest.raises(OSError):
        session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert session.requests_used() == 0


def test_the_served_bytes_leave_the_tree_untouched(session_at, project: Path) -> None:
    base = _git(project, "rev-parse", "HEAD")
    session = session_at(budget=5)
    for target in ("a.md", "b.md", "copy-of-a.md"):
        session.request(EvidenceRequest(op=EvidenceOp.READ, target=target))
    change_set = extract_change_set(project, base, _git(project, "rev-parse", "HEAD"))
    assert evaluate(change_set, tier=RunTier.REPORT_ONLY, report_path=None).denials == ()
    assert change_set.changes == ()


def _calls_journal_lock(expression: ast.expr) -> bool:
    return (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == "journal_lock"
    )


def test_serving_happens_only_inside_request_s_locked_critical_section() -> None:
    tree = ast.parse(Path(session_module.__file__).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_serve"
    ]
    assert len(calls) == 1
    (klass,) = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Session"]
    (method,) = [
        node for node in klass.body if isinstance(node, ast.FunctionDef) and node.name == "request"
    ]
    locked = [
        node
        for node in ast.walk(method)
        if isinstance(node, ast.With)
        and any(_calls_journal_lock(item.context_expr) for item in node.items)
    ]
    (block,) = locked
    inside = list(ast.walk(block))
    assert calls[0] in inside
    for name in ("read_journal", "count_requests", "_serve", "append_request"):
        assert any(
            isinstance(node, ast.Call)
            and name in (getattr(node.func, "id", None), getattr(node.func, "attr", None))
            for node in inside
        ), f"{name} is outside the locked critical section"
    assert any(isinstance(node, ast.Compare) for node in inside)
