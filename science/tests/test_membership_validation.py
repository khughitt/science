from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.propositions import (
    check_discusses_membership,
    check_relations_store_membership_roles,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _project(tmp_path: Path, discusses_yaml: str) -> ValidateContext:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    pdir = tmp_path / "entities" / "propositions"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "p1.md").write_text(
        "\n".join(
            [
                "---",
                'id: "proposition:p1"',
                'type: "proposition"',
                'title: "P1"',
                'status: "active"',
                "ontology_terms: []",
                "source_refs: []",
                "related: []",
                f"discusses: {discusses_yaml}",
                "---",
                "",
                "Body.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)


def _errors(ctx):
    return [r for r in check_discusses_membership(ctx) if r.severity == Severity.ERROR]


def test_valid_membership_has_no_errors(tmp_path: Path):
    ctx = _project(tmp_path, '[{frame: "hypothesis:h1", role: "rival"}]')
    assert _errors(ctx) == []


def test_bare_string_has_no_errors(tmp_path: Path):
    ctx = _project(tmp_path, '["hypothesis:h1"]')
    assert _errors(ctx) == []


def test_unknown_role_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '[{frame: "hypothesis:h1", role: "rebuttal"}]')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.role" for r in errs)


def test_missing_frame_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '[{role: "core"}]')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.frame" for r in errs)


def test_top_level_scalar_discusses_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '"hypothesis:h1"')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.shape" for r in errs)


def test_top_level_mapping_discusses_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '{frame: "hypothesis:h1", role: "core"}')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.shape" for r in errs)


def test_conflicting_duplicate_frame_is_error(tmp_path: Path):
    ctx = _project(
        tmp_path,
        '[{frame: "hypothesis:h1", role: "core"}, {frame: "hypothesis:h1", role: "rival"}]',
    )
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.duplicate" for r in errs)


def test_string_and_object_same_frame_conflict_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '["hypothesis:h1", {frame: "hypothesis:h1", role: "rival"}]')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.duplicate" for r in errs)


# ---------------------------------------------------------------------------
# Relations-store role validation (check_relations_store_membership_roles)
# ---------------------------------------------------------------------------


def _write_entity_file(path: Path, frontmatter_lines: list[str], body: str = "Body.") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["---", *frontmatter_lines, "---", "", body, ""]), encoding="utf-8")


def _write_minimal_project(tmp_path: Path) -> Path:
    """Write science.yaml and return the local sources dir for relations.yaml."""
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    local_sources = tmp_path / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True, exist_ok=True)
    return local_sources


def _write_hyp(tmp_path: Path, hid: str) -> None:
    _write_entity_file(
        tmp_path / "entities" / "hypotheses" / f"{hid}.md",
        [
            f'id: "hypothesis:{hid}"',
            'type: "hypothesis"',
            f'title: "{hid}"',
            'status: "proposed"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
        ],
    )


def _write_prop(tmp_path: Path, pid: str, discusses_yaml: str = "[]") -> None:
    _write_entity_file(
        tmp_path / "entities" / "propositions" / f"{pid}.md",
        [
            f'id: "proposition:{pid}"',
            'type: "proposition"',
            f'title: "{pid}"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            f"discusses: {discusses_yaml}",
        ],
    )


def _write_paper(tmp_path: Path, pid: str) -> None:
    """Write a paper entity via entities.yaml (papers are source-yaml-backed)."""
    entities_yaml = tmp_path / "knowledge" / "sources" / "local" / "entities.yaml"
    if not entities_yaml.exists():
        entities_yaml.parent.mkdir(parents=True, exist_ok=True)
        entities_yaml.write_text("entities:\n", encoding="utf-8")
    with entities_yaml.open("a", encoding="utf-8") as fh:
        fh.write(f"  - canonical_id: paper:{pid}\n")
        fh.write(f"    kind: paper\n")
        fh.write(f"    title: {pid}\n")


def _write_relations(local_sources: Path, lines: list[str]) -> None:
    (local_sources / "relations.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _relation_role_errors(ctx: ValidateContext) -> list:
    return [r for r in check_relations_store_membership_roles(ctx) if r.severity == Severity.ERROR]


def test_role_on_cito_supports_is_error(tmp_path: Path):
    """Rule 1: role set on a non-cito:discusses predicate → error."""
    local_sources = _write_minimal_project(tmp_path)
    _write_hyp(tmp_path, "h1")
    _write_prop(tmp_path, "p1")
    _write_relations(local_sources, [
        "relations:",
        "  - subject: proposition:p1",
        "    predicate: cito:supports",
        "    object: hypothesis:h1",
        "    role: background",
    ])
    ctx = ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)
    errs = _relation_role_errors(ctx)
    assert any(r.rule == "relation.role.non-discusses" for r in errs)


def test_role_to_topic_object_is_error(tmp_path: Path):
    """Rule 2: role on cito:discusses to a non-bundle (topic:) object → error."""
    local_sources = _write_minimal_project(tmp_path)
    _write_prop(tmp_path, "p1")
    # Write a topic entity
    _write_entity_file(
        tmp_path / "entities" / "topics" / "t1.md",
        [
            'id: "topic:t1"',
            'type: "topic"',
            'title: "t1"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
        ],
    )
    _write_relations(local_sources, [
        "relations:",
        "  - subject: proposition:p1",
        "    predicate: cito:discusses",
        "    object: topic:t1",
        "    role: background",
    ])
    ctx = ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)
    errs = _relation_role_errors(ctx)
    assert any(r.rule == "relation.role.non-membership" for r in errs)


def test_role_on_paper_to_hypothesis_is_error(tmp_path: Path):
    """Rule 2: role on cito:discusses where subject is paper (not proposition) → error."""
    local_sources = _write_minimal_project(tmp_path)
    _write_hyp(tmp_path, "h1")
    _write_paper(tmp_path, "doe2024")
    _write_relations(local_sources, [
        "relations:",
        "  - subject: paper:doe2024",
        "    predicate: cito:discusses",
        "    object: hypothesis:h1",
        "    role: background",
    ])
    ctx = ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)
    errs = _relation_role_errors(ctx)
    assert any(r.rule == "relation.role.non-membership" for r in errs)


def test_cross_surface_role_conflict_is_error(tmp_path: Path):
    """Rule 3: frontmatter says background, relations.yaml says core → error."""
    local_sources = _write_minimal_project(tmp_path)
    _write_hyp(tmp_path, "h1")
    # Frontmatter says background
    _write_prop(tmp_path, "p1", '[{frame: "hypothesis:h1", role: "background"}]')
    # relations.yaml says core
    _write_relations(local_sources, [
        "relations:",
        "  - subject: proposition:p1",
        "    predicate: cito:discusses",
        "    object: hypothesis:h1",
        "    role: core",
    ])
    ctx = ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)
    errs = _relation_role_errors(ctx)
    assert any(r.rule == "relation.role.cross-surface-conflict" for r in errs)


def test_no_role_in_relations_yaml_no_error(tmp_path: Path):
    """Relations.yaml with no role field should produce no role-validation errors."""
    local_sources = _write_minimal_project(tmp_path)
    _write_hyp(tmp_path, "h1")
    _write_prop(tmp_path, "p1")
    _write_relations(local_sources, [
        "relations:",
        "  - subject: proposition:p1",
        "    predicate: cito:discusses",
        "    object: hypothesis:h1",
    ])
    ctx = ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)
    errs = _relation_role_errors(ctx)
    assert errs == []


def test_matching_role_in_frontmatter_and_relations_no_error(tmp_path: Path):
    """Frontmatter and relations.yaml agreeing on role → no conflict error."""
    local_sources = _write_minimal_project(tmp_path)
    _write_hyp(tmp_path, "h1")
    _write_prop(tmp_path, "p1", '[{frame: "hypothesis:h1", role: "background"}]')
    _write_relations(local_sources, [
        "relations:",
        "  - subject: proposition:p1",
        "    predicate: cito:discusses",
        "    object: hypothesis:h1",
        "    role: background",
    ])
    ctx = ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)
    errs = _relation_role_errors(ctx)
    assert errs == []


# ---------------------------------------------------------------------------
# Rule-3 hardening: alias-based frame refs and unresolvable frame refs
# ---------------------------------------------------------------------------


def _write_hyp_with_alias(tmp_path: Path, hid: str, alias: str) -> None:
    """Write a hypothesis entity with one explicit alias."""
    _write_entity_file(
        tmp_path / "entities" / "hypotheses" / f"{hid}.md",
        [
            f'id: "hypothesis:{hid}"',
            'type: "hypothesis"',
            f'title: "{hid}"',
            'status: "proposed"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            f'aliases: ["{alias}"]',
        ],
    )


def test_alias_frame_ref_conflict_now_detected(tmp_path: Path):
    """Rule 3 (hardened): frontmatter uses an alias frame ref; old code silently skipped
    the pair because the alias was not in entity_index; new code canonicalizes it and
    correctly surfaces the conflict.

    Setup: hypothesis:h1 has alias "h-focal"; frontmatter says background via alias;
    relations.yaml says core via canonical id → conflict MUST be flagged.
    """
    local_sources = _write_minimal_project(tmp_path)
    _write_hyp_with_alias(tmp_path, "h1", "h-focal")
    # Frontmatter uses the ALIAS, not the canonical id.
    _write_prop(tmp_path, "p1", '[{frame: "h-focal", role: "background"}]')
    # relations.yaml uses the CANONICAL id with a conflicting role.
    _write_relations(local_sources, [
        "relations:",
        "  - subject: proposition:p1",
        "    predicate: cito:discusses",
        "    object: hypothesis:h1",
        "    role: core",
    ])
    ctx = ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)
    errs = _relation_role_errors(ctx)
    assert any(r.rule == "relation.role.cross-surface-conflict" for r in errs), (
        "Expected a cross-surface-conflict error but got: " + str([r.message for r in errs])
    )


def test_unresolvable_frame_ref_is_loud_error(tmp_path: Path):
    """Rule 3 (hardened): a discusses frame ref that cannot be resolved to any known
    entity must now surface as a loud error (relation.role.unresolved-frame) rather than
    silently skipping — the old code called entity_index.get(frame_ref) and continued on
    None, masking the bad ref.
    """
    local_sources = _write_minimal_project(tmp_path)
    _write_hyp(tmp_path, "h1")
    # Frontmatter references a frame that does NOT exist in the project.
    _write_prop(tmp_path, "p1", '[{frame: "hypothesis:nonexistent", role: "background"}]')
    # relations.yaml has a valid role entry (triggering rule-3 path).
    _write_relations(local_sources, [
        "relations:",
        "  - subject: proposition:p1",
        "    predicate: cito:discusses",
        "    object: hypothesis:h1",
        "    role: core",
    ])
    ctx = ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)
    errs = _relation_role_errors(ctx)
    assert any(r.rule == "relation.role.unresolved-frame" for r in errs), (
        "Expected an unresolved-frame error but got: " + str([r.message for r in errs])
    )


# ---------------------------------------------------------------------------
# Rule-3 hardening: unlabeled relations.yaml edge treated as implicit core
# ---------------------------------------------------------------------------


def test_frontmatter_background_vs_unlabeled_relations_conflict_is_error(tmp_path: Path):
    """Rule 3 (unlabeled-core fix): frontmatter labels (p1, h1) as 'background'; a
    role-less relations.yaml cito:discusses edge materializes to the same membership node
    as implicit 'core' — the two conflicting literals on one node must be caught here.

    Before the fix, the `if relation.role is None: continue` guard skipped the role-less
    edge entirely, so no conflict was detected.
    """
    local_sources = _write_minimal_project(tmp_path)
    _write_hyp(tmp_path, "h1")
    # Frontmatter explicitly labels this pair as 'background'.
    _write_prop(tmp_path, "p1", '[{frame: "hypothesis:h1", role: "background"}]')
    # relations.yaml has the SAME edge but with NO role → implicit core.
    _write_relations(local_sources, [
        "relations:",
        "  - subject: proposition:p1",
        "    predicate: cito:discusses",
        "    object: hypothesis:h1",
    ])
    ctx = ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)
    errs = _relation_role_errors(ctx)
    assert any(r.rule == "relation.role.cross-surface-conflict" for r in errs), (
        "Expected a cross-surface-conflict error (frontmatter=background vs implicit core) "
        "but got: " + str([r.message for r in errs])
    )


def test_frontmatter_core_vs_unlabeled_relations_no_error(tmp_path: Path):
    """Rule 3 (unlabeled-core fix): when frontmatter says 'core' and relations.yaml has the
    same edge with NO role (also implicit core), there is no conflict → no error.
    """
    local_sources = _write_minimal_project(tmp_path)
    _write_hyp(tmp_path, "h1")
    # Frontmatter explicitly labels this pair as 'core' (same as the implicit default).
    _write_prop(tmp_path, "p1", '[{frame: "hypothesis:h1", role: "core"}]')
    # relations.yaml has the SAME edge with NO role → implicit core → no conflict.
    _write_relations(local_sources, [
        "relations:",
        "  - subject: proposition:p1",
        "    predicate: cito:discusses",
        "    object: hypothesis:h1",
    ])
    ctx = ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)
    errs = _relation_role_errors(ctx)
    assert not any(r.rule == "relation.role.cross-surface-conflict" for r in errs), (
        "Expected no conflict error but got: " + str([r.message for r in errs])
    )


def test_no_frontmatter_membership_unlabeled_relations_no_error(tmp_path: Path):
    """Rule 3 (unlabeled-core fix): a role-less relations.yaml edge with NO frontmatter
    membership for that pair must NOT trigger a conflict error (there is only one surface).
    """
    local_sources = _write_minimal_project(tmp_path)
    _write_hyp(tmp_path, "h1")
    # Proposition has no discusses at all.
    _write_prop(tmp_path, "p1")
    # relations.yaml has a role-less cito:discusses edge.
    _write_relations(local_sources, [
        "relations:",
        "  - subject: proposition:p1",
        "    predicate: cito:discusses",
        "    object: hypothesis:h1",
    ])
    ctx = ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)
    errs = _relation_role_errors(ctx)
    assert errs == [], (
        "Expected no errors for single-surface role-less edge but got: "
        + str([r.message for r in errs])
    )
