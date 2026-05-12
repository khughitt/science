from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from science_model.source_ref import SourceRef

from science_tool.graph.storage_adapters.base import StorageAdapter


def _manifest_date(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return value.split("T", 1)[0]


class WorkflowRunAdapter(StorageAdapter):
    """Load workflow-run entities from results/**/datapackage.json manifests."""

    name = "workflow-run"

    def discover(self, project_root: Path) -> list[SourceRef]:
        refs: list[SourceRef] = []
        root = project_root / "results"
        if not root.is_dir():
            return refs
        for path in sorted(root.glob("**/datapackage.json")):
            rel_path = path.relative_to(project_root).as_posix()
            refs.append(SourceRef(adapter_name=self.name, path=rel_path))
        return refs

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        path = Path(ref.path)
        if not path.is_absolute():
            path = Path.cwd() / path
        manifest = json.loads(path.read_text(encoding="utf-8"))
        local_id = str(manifest.get("name") or path.parent.name)
        canonical_id = f"workflow-run:{local_id}"
        title = str(manifest.get("title") or local_id)
        return {
            "id": canonical_id,
            "canonical_id": canonical_id,
            "kind": "workflow-run",
            "title": title,
            "manifest_path": ref.path,
            "resources": manifest.get("resources", []),
            "created": _manifest_date(manifest.get("created")),
            "file_path": ref.path,
        }
