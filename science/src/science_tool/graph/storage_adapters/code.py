from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from science_model.source_ref import SourceRef

from science_tool.code.classification import is_executable
from science_tool.code.git import last_content_change_date
from science_tool.code.metadata import parse_code_metadata
from science_tool.graph.storage_adapters.base import StorageAdapter

_CODE_SUFFIXES = {".py", ".R", ".r", ".sh", ".smk"}


class CodeAdapter(StorageAdapter):
    """Register code files under declared roots as `code-file` entities.

    A file with a `# science:code` block becomes a code-file entity whose
    `updated` is its last content-changing commit date. A file with no block
    returns a record with no `kind` and is skipped by the loader (it is a
    ghost, flagged in Plan B).
    """

    name = "code-file"

    def __init__(self, *, code_roots: tuple[Path, ...], repo_root: Path, excludes: tuple[str, ...] = ()) -> None:
        self._code_roots = tuple(code_roots)
        self._repo_root = repo_root
        self._excludes = tuple(excludes)

    def discover(self, project_root: Path) -> list[SourceRef]:
        refs: list[SourceRef] = []
        for root in self._code_roots:
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or not self._is_code_file(path):
                    continue
                rel = path.relative_to(project_root).as_posix()
                if any(fnmatch(rel, pattern) for pattern in self._excludes):
                    continue
                refs.append(SourceRef(adapter_name=self.name, path=rel))
        return refs

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        path = Path(ref.path)
        abs_path = path if path.is_absolute() else Path.cwd() / path
        text = abs_path.read_text(errors="replace")
        metadata = parse_code_metadata(text)
        if not metadata.valid:
            # absent OR invalid block -> no kind -> skipped by the loader.
            # Plan B distinguishes the two (ghost vs malformed) via metadata.error.
            return {"file_path": ref.path}
        fields = metadata.fields or {}
        local_id = self._local_id(ref.path)
        canonical_id = f"code-file:{local_id}"
        raw_task_ids = fields.get("task_ids")
        declared = fields.get("decision_bearing")
        return {
            "id": canonical_id,
            "canonical_id": canonical_id,
            "kind": "code-file",
            "title": local_id,
            "status": str(fields.get("status") or ""),
            "decision_bearing": declared if isinstance(declared, bool) else None,
            "executable": is_executable(ref.path, text),
            "task_ids": [str(t) for t in raw_task_ids] if isinstance(raw_task_ids, list) else [],
            "updated": last_content_change_date(ref.path, repo_root=self._repo_root),
            "content_preview": "",
            "file_path": ref.path,
        }

    def _is_code_file(self, path: Path) -> bool:
        return path.suffix in _CODE_SUFFIXES or path.name == "Snakefile"

    def _local_id(self, rel_path: str) -> str:
        # Declared roots are non-nested (enforced in paths._normalize_root_names),
        # so at most one root is a prefix of rel_path.
        for root in self._code_roots:
            root_rel = root.relative_to(self._repo_root).as_posix()
            if rel_path == root_rel:
                return Path(rel_path).name
            if rel_path.startswith(root_rel + "/"):
                return rel_path[len(root_rel) + 1 :]
        # Fallback: path is outside all declared roots; use it as-is.
        return rel_path
