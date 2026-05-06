"""Federation status rollup: meta umbrella plus per-child summary."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from science_tool.project_config import ChildEntry, ProjectConfig, ProjectRole, load_project_config, resolve_child_path


def render_federated_status(meta_root: Path) -> str:
    cfg = load_project_config(meta_root)
    if cfg.role != ProjectRole.META:
        raise ValueError(f"{meta_root} is role={cfg.role!r}; not a meta project")

    raw = cfg.model_dump()
    buf = StringIO()
    buf.write(f"# Federation: {cfg.id or meta_root.name}\n\n")
    buf.write(f"Research question: {raw.get('research_question', '(none)')}\n\n")
    buf.write(f"Children: {len(cfg.children)}\n\n")

    for child in cfg.children:
        buf.write(f"---\n\n## {child.id} ({child.role})\n\n")
        buf.write(_render_child_summary(child))
        buf.write("\n")

    buf.write("---\n\n## Meta scope\n\n")
    buf.write(_render_meta_scope(meta_root, cfg))
    return buf.getvalue()


def _render_child_summary(child: ChildEntry) -> str:
    child_root = resolve_child_path(child)
    if not (child_root / "science.yaml").is_file():
        return f"_missing_: declared path `{child_root}` has no science.yaml\n"

    try:
        child_cfg = load_project_config(child_root)
    except Exception as exc:  # noqa: BLE001
        return f"_failed to load_: {exc}\n"

    raw = child_cfg.model_dump()
    lines = [
        f"- name: {child_cfg.name}",
        f"- path: {child_root}",
        f"- research question: {raw.get('research_question', '(none)')}",
    ]
    question_count = _count_markdown(child_root / "doc" / "questions")
    hypothesis_count = _count_markdown(child_root / "specs" / "hypotheses") + _count_markdown(
        child_root / "doc" / "hypotheses"
    )
    if question_count:
        lines.append(f"- questions: {question_count}")
    if hypothesis_count:
        lines.append(f"- hypotheses: {hypothesis_count}")
    return "\n".join(lines) + "\n"


def _count_markdown(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for _ in path.glob("*.md"))


def _render_meta_scope(meta_root: Path, cfg: ProjectConfig) -> str:
    raw = cfg.model_dump()
    lines = [f"- name: {cfg.name}", f"- id: {cfg.id}"]
    questions_dir = meta_root / "doc" / "questions"
    if questions_dir.is_dir():
        lines.append(f"- foundational questions: {sum(1 for _ in questions_dir.glob('*.md'))}")
    if "tags" in raw:
        lines.append(f"- tags: {raw['tags']}")
    return "\n".join(lines) + "\n"
