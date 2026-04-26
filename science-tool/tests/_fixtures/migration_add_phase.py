"""Test-only migration step: ensure phase: line in specs/*.md."""

from pathlib import Path


def check(project_root: Path) -> bool:
    """True if migration is unnecessary (all spec files have phase:)."""
    for f in (project_root / "specs").glob("*.md"):
        if "phase:" not in f.read_text(encoding="utf-8"):
            return False
    return True


def apply(project_root: Path) -> dict:
    """Add `phase: active` to every spec file missing it. Return undo info."""
    touched: list[str] = []
    for f in (project_root / "specs").glob("*.md"):
        text = f.read_text(encoding="utf-8")
        if "phase:" not in text:
            f.write_text(text.replace("---\n", "---\nphase: active\n", 1), encoding="utf-8")
            touched.append(str(f.relative_to(project_root)))
    return {"touched": touched}


def unapply(project_root: Path, applied: dict) -> None:
    """Reverse what apply() did."""
    for rel in applied["touched"]:
        f = project_root / rel
        text = f.read_text(encoding="utf-8")
        f.write_text(text.replace("phase: active\n", "", 1), encoding="utf-8")
