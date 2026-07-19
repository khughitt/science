# science/tests/skills_lint/test_templates.py
from pathlib import Path

import pytest

from science_tool.skills_lint.lint import check_skills

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "skills" / "meta" / "templates"
META = REPO / "skills" / "meta"

# Approved heading lists — the CONTRACT, encoded here, NOT derived from the files.
EXPECTED_HEADINGS = {
    "measurement-qa": ["Sources & ingestion/construction", "Pre-flight checklist", "QA metrics",
                       "Common failure modes", "Halt-On Conditions", "Minimum output package",
                       "Success test", "Companion Skills"],
    "method-guide": ["Applicability / non-applicability", "Estimand & assumptions", "Model/procedure choices",
                     "Fitting / execution", "Diagnostics", "Failure modes", "Outputs & reporting",
                     "Success test", "Companion Skills"],
    "analysis-discipline": ["Triggering condition", "Required reasoning / check / precommitment",
                            "Decision rule or reasoning criteria",
                            "Outcomes (pass / fail / indeterminate, or branch/threshold)",
                            "Halt / escalation", "Required evidence & artifacts", "Permitted reporting language",
                            "Success test", "Companion Skills"],
    "normative-reference": ["Scope", "Vocabulary / schema / enums", "Invariants", "Conformance rules",
                            "Examples", "Versioning / migration", "Invalid cases",
                            "Success test", "Companion Skills"],
    "tool-guide": ["Setup & version assumptions", "Command / API surface", "Failure handling",
                   "Rate limits (where relevant)", "Verification / smoke-test",
                   "Success test", "Companion Skills"],
    "practice-guide": ["When to apply", "Workflow steps", "Judgment rules", "Quality criteria",
                       "Common pitfalls", "Outputs", "Success test", "Companion Skills"],
}
ROUTER_HEADINGS = ["Routing trigger", "Scope boundary", "Leaves", "Decision / compose order",
                   "Parent & neighbors", "Success test", "Companion Skills"]
CANONICAL_HEADINGS = {
    "SKILL.md": ROUTER_HEADINGS,
    "skill-taxonomy.md": [
        "Scope", "Vocabulary / schema / enums", "Invariants", "Conformance rules",
        "Examples", "Versioning / migration", "Invalid cases", "Success test",
        "Companion Skills",
    ],
    "skill-authoring.md": [
        "When to apply", "Workflow steps", "Judgment rules", "Quality criteria",
        "Common pitfalls", "Outputs", "Success test", "Companion Skills",
    ],
}


def _headings(text: str) -> list[str]:
    return [ln[3:].strip() for ln in text.splitlines() if ln.startswith("## ")]


@pytest.mark.parametrize("archetype", sorted(EXPECTED_HEADINGS))
def test_template_headings_match_contract(archetype: str) -> None:
    text = (TEMPLATES / f"{archetype}.md").read_text(encoding="utf-8")
    assert _headings(text) == EXPECTED_HEADINGS[archetype]


def test_router_template_headings_match_contract() -> None:
    text = (TEMPLATES / "router.md").read_text(encoding="utf-8")
    assert _headings(text) == ROUTER_HEADINGS


def _is_subsequence(required: list[str], actual: list[str]) -> bool:
    remaining = iter(actual)
    return all(any(candidate == heading for candidate in remaining) for heading in required)


@pytest.mark.parametrize("filename", sorted(CANONICAL_HEADINGS))
def test_canonical_meta_skills_dogfood_declared_contract(filename: str) -> None:
    headings = _headings((META / filename).read_text(encoding="utf-8"))
    assert _is_subsequence(CANONICAL_HEADINGS[filename], headings)


def test_extension_requests_activate_and_route_to_authoring_doctrine() -> None:
    router = (META / "SKILL.md").read_text(encoding="utf-8")
    frontmatter, body = router.split("\n---\n", maxsplit=1)
    routing_surface, leaves = body.split("## Leaves", maxsplit=1)

    assert "extending" in frontmatter.lower()
    assert "extending" in routing_surface.lower()
    assert "extending" in leaves.lower()


def _body_of(template_text: str) -> str:
    """Return everything after the template's own frontmatter block."""
    end = template_text.find("\n---\n", 3)
    assert end != -1, "template has no closing frontmatter delimiter"
    return template_text[end + len("\n---\n"):]


@pytest.mark.parametrize("archetype", sorted(EXPECTED_HEADINGS))
def test_instance_from_template_passes_full_linter(archetype: str, tmp_path: Path) -> None:
    """Instantiate a leaf from the ACTUAL template file: keep its real body,
    swap only the placeholder frontmatter for a valid block, and prove FULL
    check_skills conformance (not a hand-picked subset of checks)."""
    body = _body_of((TEMPLATES / f"{archetype}.md").read_text(encoding="utf-8"))
    leaf_rel = f"{archetype}-example.md"
    (tmp_path / leaf_rel).write_text(
        f"---\nname: example-{archetype}\ndescription: Use when testing {archetype}.\n"
        f"archetype: {archetype}\nprovenance: internal\n---\n{body}",
        encoding="utf-8",
    )
    (tmp_path / "INDEX.md").write_text(
        "---\nname: idx\ndescription: index\n---\n\n"
        f"# Index\n\n- [`{leaf_rel}`]({leaf_rel})\n\n## Companion Skills\n\n- none\n",
        encoding="utf-8",
    )
    issues = [i for i in check_skills(tmp_path) if i.path.as_posix() == leaf_rel]
    assert issues == [], [i.to_json() for i in issues]
