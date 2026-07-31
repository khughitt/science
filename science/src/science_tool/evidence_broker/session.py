"""The budget-enforcing session over policy, serving, and the append-only journal."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from science_model.evidence_broker import (
    MAX_TARGET_CHARS,
    EvidenceSession,
    ExposureEntry,
    Outcome,
)
from science_tool.autonomy.baseline import reject_baseline_inside_project
from science_tool.evidence_broker.journal import (
    JournalHandle,
    append_request,
    count_requests,
    journal_lock,
    open_journal,
    read_journal,
)
from science_tool.evidence_broker.policy import EvidenceRequest
from science_tool.evidence_broker.serve import serve as _serve
from science_tool.findings.paths import create_regular_file_at, replace_at, unlink_at

_BUDGET_NOTICE = "evidence budget exhausted for this run"


class SessionError(RuntimeError):
    """The session could not answer at all; a refusal is an answer."""


@dataclass(frozen=True)
class Receipt:
    """What the requester is told, never the served bytes themselves."""

    outcome: Outcome
    sha256: str | None = None
    path: Path | None = None
    notice: str | None = None


class Session:
    """One run's bounded evidence surface."""

    def __init__(self, repo_root: Path, session: EvidenceSession) -> None:
        self._repo_root = repo_root
        self._session = session
        self._run_dir = session.journal_path.parent
        self._served_dir = self._run_dir / "served"
        self._project_root = repo_root
        reject_baseline_inside_project(self._served_dir, repo_root)
        reject_baseline_inside_project(session.journal_path, repo_root)

    def requests_used(self) -> int:
        """Derive spend by counting journal request events."""
        with open_journal(
            self._session.journal_path, project_root=self._project_root
        ) as handle:
            return count_requests(read_journal(handle))

    def request(self, request: EvidenceRequest) -> Receipt:
        """Answer one request, refuse it, or halt without recording a false exposure."""
        for field, value in (("target", request.target), ("pathspec", request.pathspec)):
            if value is not None and len(value) > MAX_TARGET_CHARS:
                raise SessionError(
                    f"{field} is {len(value)} characters, over the {MAX_TARGET_CHARS} bound"
                )

        with journal_lock(
            self._session.journal_path, project_root=self._project_root
        ) as handle:
            if count_requests(read_journal(handle)) >= self._session.budget:
                return Receipt(outcome=Outcome.REFUSED, notice=_BUDGET_NOTICE)

            served = _serve(
                self._repo_root,
                self._session.commit,
                request,
                self._session.surface_policy,
            )
            digest = hashlib.sha256(served.payload).hexdigest()
            path: Path | None = None
            if served.outcome is not Outcome.REFUSED:
                path = self._write_served(handle, digest, served.payload)

            append_request(
                handle,
                ExposureEntry(
                    op=request.op.value,
                    target=served.target,
                    pathspec=served.pathspec,
                    commit=self._session.commit,
                    sha256=digest,
                    outcome=served.outcome,
                ),
            )

            if served.outcome is Outcome.REFUSED:
                return Receipt(
                    outcome=served.outcome,
                    notice=served.denial.notice if served.denial is not None else None,
                )
            return Receipt(outcome=served.outcome, sha256=digest, path=path)

    def _write_served(self, handle: JournalHandle, digest: str, payload: bytes) -> Path:
        """Atomically replace ``served/<sha256>`` through the captured run directory."""
        directory = self._open_served_dir(handle.dir_fd)
        try:
            temporary = f".{digest}.{os.getpid()}.partial"
            descriptor = create_regular_file_at(directory, temporary)
            try:
                with os.fdopen(descriptor, "wb") as destination:
                    destination.write(payload)
                replace_at(directory, temporary, digest)
                try:
                    receipt_directory = self._served_dir.stat()
                except OSError as exc:
                    raise SessionError(
                        "served bytes were written but their delivery path is no longer "
                        f"reachable: {exc}"
                    ) from exc
                if not os.path.samestat(os.fstat(directory), receipt_directory):
                    raise SessionError(
                        "served bytes were written but their delivery path now names another "
                        "directory"
                    )
            except BaseException:
                unlink_at(directory, temporary)
                raise
        finally:
            os.close(directory)
        return self._served_dir / digest

    def _open_served_dir(self, run_dir: int) -> int:
        """Open or create the real ``served`` child of an already-captured run directory."""
        try:
            os.mkdir("served", dir_fd=run_dir)
        except FileExistsError:
            pass
        return os.open(
            "served", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=run_dir
        )
