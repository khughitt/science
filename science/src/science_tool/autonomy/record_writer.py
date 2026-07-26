"""Write the finalized attestation to `runs/<slug>.md`.

`load_run_records` is this module's specification, not a downstream consumer: it
enforces whole-line delimiters, no duplicate or merge keys, flat `*.md` children, and
`slug == path.stem`. Anything this writer emits that the reader rejects is a defect
here.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from science_model.autonomous_runs import (
    RUN_ID_PREFIX,
    AutonomousRunRecord,
    validate_run_identity,
)
from science_model.frontmatter import render_frontmatter

from science_tool.graph.autonomous_runs import RUNS_DIRNAME


class RecordWriteError(ValueError):
    """The run record could not be written."""


def generate_run_id(started: date, agent: str, short_id: str) -> str:
    """Build a run id, refusing an agent or short id the model could never finalize."""
    validate_run_identity(agent=agent, short_id=short_id)
    return f"{RUN_ID_PREFIX}{started.isoformat()}-{agent}-{short_id}"


def record_path(project_root: Path, record: AutonomousRunRecord) -> Path:
    return project_root / RUNS_DIRNAME / f"{record.slug}.md"


def write_run_record(project_root: Path, record: AutonomousRunRecord) -> Path:
    """Serialize `record` and return the path written.

    `exclude_none` drops `basis_digest` when the disposition is `unwired` and
    `triggered_by` when it is absent -- design §2 says omitted, not blank. Every other
    field is required by the model, so none can be dropped by accident.

    THE ACTOR OWNS THIS DIRECTORY. Everything about the write is hostile-input handling:
    `runs/` may be a symlink it planted, and the record path may be a dangling symlink
    whose `exists()` is False. `O_CREAT | O_EXCL | O_NOFOLLOW` answers both in one
    syscall -- it refuses an existing file, refuses a symlink at the final component, and
    leaves no window between the check and the write. `load_run_records` refuses symlinks
    on read, so a followed link would also produce a record that can never be loaded.
    """
    runs_dir = project_root / RUNS_DIRNAME
    if runs_dir.is_symlink():
        raise RecordWriteError(
            f"{runs_dir} is a symlink; run records are written only into a real directory "
            "inside the project (load_run_records refuses to read a redirected runs/)"
        )
    path = record_path(project_root, record)

    payload = record.model_dump(mode="json", exclude_none=True)
    # sort_keys=False keeps the model's declaration order, which reads as the design's
    # table. default_flow_style=False keeps nested blocks (policy_identity, budget)
    # expanded, so a human reviewing an attestation sees one field per line.
    text = render_frontmatter(payload, "")
    try:
        runs_dir.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
    except FileExistsError as exc:
        # O_EXCL also fires on a symlink at the final component, which is why the message
        # names both readings rather than asserting the file already holds a record.
        raise RecordWriteError(
            f"{path} already exists or is a symlink; a run record is written once, never "
            "rewritten, and never through a link"
        ) from exc
    except OSError as exc:
        raise RecordWriteError(f"could not write run record to {path}: {exc}") from exc
    return path
