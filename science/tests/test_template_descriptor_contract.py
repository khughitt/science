"""Hand-copied templates must agree with their kind descriptor (task:t087).

`template_ready=True` kinds are rendered by Renderer from their `_template`
block, so their literal `id:`/`status:` lines are illustration and are excluded.
For `template_ready=False` kinds the literal lines are what an author copies,
so a wrong prefix or an undeclared status becomes a wrong entity file.
"""

import re
from pathlib import Path

import pytest
from science_model.profiles.core import CORE_PROFILE

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
_KINDS = {ek.name: ek for ek in CORE_PROFILE.entity_kinds}


def _frontmatter_value(text: str, key: str) -> str | None:
    match = re.search(rf'^{key}:\s*"?([^"\n#]+?)"?\s*(?:#.*)?$', text, re.MULTILINE)
    return match.group(1) if match else None


def _hand_copied_templates() -> list[tuple[Path, str]]:
    found = []
    for path in sorted(TEMPLATES_DIR.glob("*.md")):
        kind = _frontmatter_value(path.read_text(encoding="utf-8"), "kind")
        descriptor = _KINDS.get(kind or "")
        if descriptor is not None and not descriptor.template_ready:
            found.append((path, kind))
    return found


def test_survey_found_the_expected_hand_copied_templates() -> None:
    """Pins the sample size, so a template that stops declaring `kind` is noticed."""
    assert len(_hand_copied_templates()) == 10


@pytest.mark.parametrize("path,kind", _hand_copied_templates(), ids=lambda v: getattr(v, "name", v))
def test_template_id_uses_the_canonical_prefix(path: Path, kind: str) -> None:
    declared = _frontmatter_value(path.read_text(encoding="utf-8"), "id")
    prefix = _KINDS[kind].canonical_prefix
    assert declared is not None, f"{path.name} declares no id:"
    assert declared.startswith(f"{prefix}:"), f"{path.name}: id {declared!r} does not start with {prefix!r}:"


@pytest.mark.parametrize("path,kind", _hand_copied_templates(), ids=lambda v: getattr(v, "name", v))
def test_template_status_is_declared_by_the_kind(path: Path, kind: str) -> None:
    declared = _frontmatter_value(path.read_text(encoding="utf-8"), "status")
    statuses = _KINDS[kind].statuses
    if declared is None or not statuses:
        pytest.skip(f"{path.name}: no status line, or kind declares no status vocabulary")
    assert declared in statuses, f"{path.name}: status {declared!r} not in {list(statuses)}"
