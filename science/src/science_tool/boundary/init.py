"""Propose a boundary declaration from an existing tree.

The ONLY place a heuristic touches the boundary. `classify()` is good at
suggesting and bad at enforcing, so its output here is a proposal a human reads
and edits -- never something written without review.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from science_tool.boundary.walk import iter_repo_files
from science_tool.data_policy import FileClass, classify
from science_tool.project_config import load_project_config, resolve_data_policy

_RECORD_NAMES = ("datapackage.json", "datapackage.yaml")
_CANDIDATE_TOPS = frozenset({"data", "pdfs", "results"})


def _walk_candidates(project_root: Path) -> list[Path]:
    """Every file under the candidate top-level directories, INCLUDING ignored ones.

    Deliberately NOT `visible_paths`: an adoption aid whose whole job is to
    discover already-ignored payload roots cannot use an oracle that excludes
    ignored files. A tree with a pre-existing `data/raw/*` rule would otherwise
    yield nothing to propose.
    """
    found: list[Path] = []
    for top in sorted(_CANDIDATE_TOPS):
        found.extend(Path(rel) for rel in iter_repo_files(project_root, project_root / top))
    return sorted(found)


def propose_declaration(project_root: Path) -> dict:
    """Return a `boundary:` mapping proposal. Never writes."""
    # NOTE: resolve_data_policy takes a ProjectConfig, not a path
    # (project_config.py:453). Deliberately NOT wrapped in a try/except: a
    # science.yaml that will not validate is a real error, and silently
    # substituting the default policy would make the proposal a guess derived
    # from a config the operator believes is in effect.
    policy = resolve_data_policy(load_project_config(project_root))

    payload_dirs: Counter[str] = Counter()
    manifest_dirs: Counter[str] = Counter()
    # Propose the descriptor names ACTUALLY FOUND, per root -- proposing
    # `datapackage.json` when discovery only ever saw `datapackage.yaml` would
    # emit a declaration that matches nothing.
    observed: dict[str, set[str]] = {}

    for path in _walk_candidates(project_root):
        try:
            size = (project_root / path).stat().st_size
        except OSError:
            # NOT the fail-open pattern removed elsewhere. This is a file that
            # vanished between the walk and the stat; skipping one candidate
            # weakens a suggestion, whereas swallowing an unreadable RULE SOURCE
            # would silently drop governance. Rule sources raise; races skip.
            continue
        top = "/".join(path.parts[:2]) if len(path.parts) > 2 else path.parts[0]
        if path.name in _RECORD_NAMES:
            manifest_dirs[top] += 1
            observed.setdefault(top, set()).add(path.name)
        elif classify(path, size, policy) is FileClass.PAYLOAD:
            payload_dirs[top] += 1

    roots: list[dict] = []
    for name in sorted(manifest_dirs):
        roots.append({"path": name, "class": "manifest", "tracked": sorted(observed[name])})
    for name in sorted(payload_dirs):
        if name in manifest_dirs:
            continue
        roots.append({"path": name, "class": "payload"})
    return {"roots": roots}
