"""Templates must agree with their kind descriptor (task:t087).

For `id:`, the `template_ready=True` kinds are excluded: Renderer builds the id from
`_template.frontmatter`, so their literal `id:` line really is illustration.

`status:` is NOT excluded, for any kind. The "it's only illustration" argument was
tried and it failed in the wild: `templates/pre-registration.md` carried
`status: "committed"` while the pre-registration descriptor declared only
active|amended|superseded|retired. Agents copy the literal line, and
`commands/pre-register.md` independently prescribes `status: "committed"` on sign-off,
so 40 pre-registrations across five projects were authored with a status their own kind
forbade. Nothing noticed until a status check shipped and errored on all of them.

A status line an author can read is a status the kind must declare, whatever the
Renderer would have emitted (fb-2026-07-11-005 follow-on).
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


def _templates_with_a_literal_status(
) -> list[tuple[Path, str]]:
    """Every template hardcoding a real status value, `template_ready` or not.

    `status: "{{status}}"` is a substitution slot, not a status -- Renderer fills it from
    the kind's own vocabulary, so it cannot be out of vocabulary and is skipped. A
    template that bypasses the slot and hardcodes a word is making a claim about the
    vocabulary, and that claim gets checked.
    """
    found = []
    for path in sorted(TEMPLATES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        kind = _frontmatter_value(text, "kind")
        descriptor = _KINDS.get(kind or "")
        if descriptor is None or not descriptor.statuses:
            continue
        status = _frontmatter_value(text, "status")
        if status is None or status.startswith("{{"):
            continue
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


@pytest.mark.parametrize(
    "path,kind", _templates_with_a_literal_status(), ids=lambda v: getattr(v, "name", v)
)
def test_template_status_is_declared_by_the_kind(path: Path, kind: str) -> None:
    """A status an author can read off a template is a status the kind must declare.

    No `template_ready` exemption: see the module docstring. `pre-registration` is
    precisely the kind that exemption was hiding.
    """
    declared = _frontmatter_value(path.read_text(encoding="utf-8"), "status")
    statuses = _KINDS[kind].statuses
    assert declared in statuses, f"{path.name}: status {declared!r} not in {list(statuses)}"
