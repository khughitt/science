from __future__ import annotations

import json
from datetime import date, datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from science_model.source_ref import SourceRef

from science_tool.graph.storage_adapters.base import StorageAdapter


def _manifest_date(value: Any, *, manifest_path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{manifest_path}: created must be an ISO date or datetime string")
    try:
        if "T" not in value:
            return date.fromisoformat(value).isoformat()
        datetime_value = f"{value[:-1]}+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(datetime_value)
    except ValueError as exc:
        raise ValueError(f"{manifest_path}: invalid created value {value!r}; expected ISO date or datetime") from exc
    return parsed.date().isoformat()


def _manifest_related(manifest: dict[str, Any]) -> list[str]:
    related: list[str] = []
    entity_refs = manifest.get("entities", {})
    if isinstance(entity_refs, dict):
        for ref_list in entity_refs.values():
            if isinstance(ref_list, list):
                related.extend(str(ref) for ref in ref_list)
    workflow = manifest.get("workflow", {})
    workflow_name = workflow.get("name") if isinstance(workflow, dict) else None
    if workflow_name:
        related.append(f"workflow:{workflow_name}")
    return related


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
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except JSONDecodeError as exc:
            raise ValueError(f"{ref.path}: invalid JSON in workflow-run manifest: {exc.msg}") from exc
        if not isinstance(manifest, dict):
            raise ValueError(f"{ref.path}: workflow-run manifest must be a JSON object")
        local_id = str(manifest.get("name") or path.parent.name)
        canonical_id = f"workflow-run:{local_id}"
        title = str(manifest.get("title") or local_id)
        return {
            "id": canonical_id,
            "canonical_id": canonical_id,
            "kind": "workflow-run",
            "title": title,
            "status": str(manifest.get("status") or "complete"),
            "manifest_path": ref.path,
            "resources": manifest.get("resources", []),
            "created": _manifest_date(manifest.get("created"), manifest_path=ref.path),
            "related": _manifest_related(manifest),
            "content_preview": str(manifest.get("description") or ""),
            "file_path": ref.path,
        }
