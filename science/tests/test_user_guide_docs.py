from __future__ import annotations

import re
from pathlib import Path

from science_tool.cli import main as science_cli
from science_model.identity import EntityClass
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.schema import KindCategory

ROOT = Path(__file__).resolve().parents[2]
GUIDE_ROOT = ROOT / "docs" / "user-guide"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _slice_between(text: str, start: str, end: str) -> str:
    if start not in text:
        raise AssertionError(f"missing start marker: {start}")
    remainder = text.split(start, 1)[1]
    if end not in remainder:
        raise AssertionError(f"missing end marker after {start}: {end}")
    return remainder.split(end, 1)[0]


def _norm(text: str) -> str:
    return " ".join(text.split())


def _section_kinds(text: str, section: str) -> list[str]:
    pattern = re.compile(
        rf"<!-- entity-kinds:{section}:start -->\n(?P<body>.*?)\n<!-- entity-kinds:{section}:end -->",
        re.DOTALL,
    )
    match = pattern.search(text)
    assert match is not None, f"missing entity kind marker section: {section}"
    return re.findall(r"^- `([^`]+)` - ", match.group("body"), flags=re.MULTILINE)


def _core_kinds_by_class() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {
        "epistemic": [],
        "operational": [],
        "reference": [],
    }
    for kind in CORE_PROFILE.entity_kinds:
        if kind.category not in (KindCategory.AUTHORED_CORE, KindCategory.RESERVED):
            continue
        entity_class = kind.entity_class
        assert entity_class is not None, f"core kind {kind.name!r} has no entity_class"
        if entity_class is EntityClass.EPISTEMIC:
            grouped["epistemic"].append(kind.name)
        elif entity_class is EntityClass.OPERATIONAL:
            grouped["operational"].append(kind.name)
        elif entity_class is EntityClass.REFERENCE:
            grouped["reference"].append(kind.name)
        else:  # pragma: no cover - exhaustive for current EntityClass enum
            raise AssertionError(f"unhandled entity class: {entity_class}")
    return {key: sorted(value) for key, value in grouped.items()}


def test_entities_chapter_lists_core_kinds_by_entity_class() -> None:
    text = _read(GUIDE_ROOT / "entities.md")
    documented = {
        "epistemic": sorted(_section_kinds(text, "epistemic")),
        "operational": sorted(_section_kinds(text, "operational")),
        "reference": sorted(_section_kinds(text, "reference")),
    }

    assert documented == _core_kinds_by_class()


def test_user_guide_index_links_all_chapters() -> None:
    index = _read(GUIDE_ROOT / "index.md")
    expected = (
        "introduction.md",
        "science-model.md",
        "project-layout.md",
        "entities.md",
        "epistemic-model.md",
        "evidence-lines.md",
        "graph-and-derived-state.md",
        "health-and-validation.md",
        "agent-workflows.md",
        "cross-project-work.md",
    )
    for chapter in expected:
        assert (GUIDE_ROOT / chapter).exists()
        assert chapter in index


def test_cli_workflow_map_mentions_every_top_level_command() -> None:
    text = _read(GUIDE_ROOT / "cli-and-workflows.md")
    code_spans = re.findall(r"`([^`]+)`", text)
    documented_commands: set[str] = set()

    for span in code_spans:
        words = span.split()
        if not words:
            continue
        if words[0] == "science" and len(words) > 1:
            documented_commands.add(words[1])
        elif len(words) == 1:
            documented_commands.add(words[0])

    missing = sorted(set(science_cli.commands) - documented_commands)
    assert not missing, "Top-level commands missing from CLI workflow map: " + ", ".join(missing)


def test_deleted_user_docs_are_not_reintroduced() -> None:
    deleted = (
        ROOT / "docs" / ("user-guide" + ".md"),
        ROOT / "docs" / ("project-organization-profiles" + ".md"),
        ROOT / "docs" / "conventions" / ("project-working-model-" + "h00.md"),
        ROOT / "docs" / ("proposition-and-evidence-model" + ".md"),
        ROOT / "docs" / ("claim-and-evidence-model" + ".md"),
    )
    for path in deleted:
        assert not path.exists(), f"retired doc path should not exist: {path.relative_to(ROOT)}"


def test_convention_docs_do_not_link_retired_user_docs() -> None:
    retired_refs = (
        "project-organization-profiles.md",
        "project-working-model-h00.md",
        "proposition-and-evidence-model.md",
        "claim-and-evidence-model.md",
    )
    offenders: list[str] = []
    for path in sorted((ROOT / "docs" / "conventions").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for retired in retired_refs:
            if retired in text:
                offenders.append(f"{path.relative_to(ROOT)} links retired {retired}")
    assert not offenders


def test_entities_chapter_documents_compositional_outputs_and_paper_split() -> None:
    text = _read(GUIDE_ROOT / "entities.md")
    normalized = " ".join(text.split())

    assert "## Compositional Research Outputs" in text
    assert "`finding`" in text
    assert "`story`" in text
    assert "The current loadable `paper` kind is an external literature note" in normalized
    assert "do not use `paper:<id>` for the project's own publication draft" in normalized


def test_entities_chapter_documents_reference_semantics_and_topic_deprecation() -> None:
    text = _read(GUIDE_ROOT / "entities.md")
    normalized = " ".join(text.split())

    assert "## Reference Semantics" in text
    assert "cross-kind slug fallback" in normalized
    assert "`terms.yaml` is for lightweight semantic rows" in normalized
    assert "Field-scoped `tag:*`" in text
    assert "`topic` remains registered for legacy projects and migration surfaces" in normalized
    assert "Do not create topic stubs to silence unresolved-reference checks." in normalized


def test_entities_documents_terms_add_for_lightweight_terms() -> None:
    normalized = _norm(_read(GUIDE_ROOT / "entities.md"))

    assert "`terms.yaml` is for lightweight semantic rows" in normalized
    assert 'Use `science terms add <id> --title "<title>"` for routine lightweight term creation' in normalized
    assert "The command writes to the configured local profile's `terms.yaml`" in normalized
    assert "Do not pass external ontology CURIEs as the term id; put them in `--ontology-term`." in normalized
    assert "Promote the row to a Markdown entity owner when it accumulates body prose" in normalized


def test_epistemic_model_documents_inquiry_ref_ownership_contract() -> None:
    text = _read(GUIDE_ROOT / "epistemic-model.md")
    section = _slice_between(
        text,
        "### Inquiry Ref Ownership Contract",
        "### Causal Inquiry Profiles",
    )
    normalized = _norm(section)

    assert "Inquiry fields use two ownership modes" in normalized
    assert "| Boundary refs | Existing source refs selected by the inquiry" in section
    assert "| Flow-edge endpoints | Existing source refs connected by the inquiry" in section
    assert "| Unknowns | Refs marked as `sci:Unknown`" in section
    assert "| Assumptions | Inquiry-local records in `inquiry.assumptions`" in section
    assert "| Transformations | Inquiry-local records in `inquiry.transformations`" in section
    assert "Unresolved endpoint refs are graph-build errors" in normalized
    assert (
        "Boundary refs, flow endpoints, causal treatment/outcome refs, and claim refs must already resolve"
        in normalized
    )
    assert "Unknown markers may remain in sketch" in normalized
    assert "non-sketch inquiries should resolve or justify them" in normalized
    assert "`science entity create concept" in normalized
    assert "`science graph add concept` is not durable inquiry authoring" in normalized


def test_epistemic_model_references_terms_add_for_lightweight_refs() -> None:
    normalized = _norm(_read(GUIDE_ROOT / "epistemic-model.md"))

    assert "source records or `science terms add` lightweight rows before the inquiry can be materialized" in normalized
    assert "Use `science terms add concept:" in normalized
    assert "`science entity create concept" in normalized


def test_entities_chapter_documents_source_authored_concepts() -> None:
    text = _read(GUIDE_ROOT / "entities.md")
    section = _slice_between(
        text,
        "### Source-Authored Concepts",
        "### Legacy Topic Triage",
    )
    normalized = _norm(section)

    assert "`terms.yaml` is the lightweight concept tier" in normalized
    assert "Use `science terms add concept:" in normalized
    assert "`science entity create concept" in normalized
    assert "`entities/concepts/<slug>.md`" in normalized
    assert "Use the most specific registered kind before creating a local concept" in normalized
    assert "`science graph add concept` writes derived graph state" in normalized
    assert "Do not use graph-added concepts as durable owners" in normalized
