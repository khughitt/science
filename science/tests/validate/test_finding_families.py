from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest
from science_model.audit import (
    FindingRule,
    FindingSection,
    ProducerMetrics,
    finding_fingerprint,
)
from science_model.packages.schema import BENCHMARK_TASK_SUPPORT_FIELDS

from science_tool.annotation.verify import ISSUE_KINDS
from science_tool.findings.catalog import build_project_registry
from science_tool.findings.producers import validate_producer_result
from science_tool.run_fingerprint_policy import (
    RULE_AUTHORED_CAPTURABLE,
    RULE_INCOMPLETE,
)
from science_tool.validate.checks import (
    CANONICAL_CHECKS,
    CANONICAL_CHECK_MODULES,
    Check,
    CheckEntry,
    clear_checks_for_tests,
)
from science_tool.validate.checks.annotations import ANNOTATION_RULES
from science_tool.validate.checks.benchmark_metadata import SUPPORT_FIELD_RULES
from science_tool.validate.checks.correspondence_drift import (
    RULE_CORRESPONDENCE_DRIFT,
)
from science_tool.validate.checks.identity_context import (
    MOLECULAR_SPEC_RULES,
    TIER_DECLARATION_RULES,
)
from science_tool.validate.checks.manifest import RULES as MANIFEST_RULES
from science_tool.validate.checks.prose_lints import (
    RULE_ADVISORY,
    RULE_CONFIG,
    RULE_HIT,
)
from science_tool.validate.checks.relations import RELATION_RULES
from science_tool.validate.checks.status_vocabulary import (
    status_vocabulary_rules,
)
from science_tool.validate.checks.supersession import supersession_rules
from science_tool.validate.checks.workflow_runs import FINGERPRINT_RULES
from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import NumericVerificationMetrics, ValidationQualifiers
from science_tool.validate.gates import cumulative_rules
from science_tool.validate.observations import (
    ValidationMetricObservation,
    ValidationNotice,
    ValidationObservationBatch,
)
from science_tool.validate.result import Result, Severity
from science_tool.validate.runtime import VALIDATION_RUNTIME_PRODUCER


_STATIC_RULE_MIGRATIONS: tuple[tuple[str, str | None], ...] = (
    ("autonomous-runs", "autonomous-runs.check"),
    ("bias_audits", "bias-audits.check"),
    ("cross-references", "cross-references.check"),
    ("directory_structure", "directory-structure.check"),
    ("discussions", "discussions.check"),
    ("document_structure", "document-structure.check"),
    ("entity-conformance", "entity-conformance.check"),
    (
        "evidence.empirical.requires_dataset_usage",
        "evidence.empirical.requires-dataset-usage",
    ),
    ("gap_analysis", "gap-analysis.check"),
    ("graph", "graph.check"),
    ("hypotheses", "hypotheses.check"),
    ("hypothesis_comparisons", "hypothesis-comparisons.check"),
    ("id-prefixes", "id-prefixes.check"),
    ("forbidden-second-declaration", "identity.forbidden-second-declaration"),
    ("lens_views", "lens-views.check"),
    ("manifest", "manifest.check"),
    ("non-materializing-field", "materialization.non-materializing-field"),
    ("notes", "notes.check"),
    ("origins", "origins.check"),
    ("orphan-datapackage-owner", "dataset.orphan-datapackage-owner"),
    ("papers", None),
    ("prereg", "prereg.check"),
    ("project_readme", "project-readme.check"),
    ("proposition.claim_layer.canonical", "proposition.claim-layer.canonical"),
    ("references", "references.check"),
    ("registration", "registration.check"),
    ("research_scope", "research-scope.check"),
    ("tasks", "tasks.check"),
    ("tooling", "tooling.check"),
    ("unresolved_markers", "unresolved-markers.check"),
    ("validate.sidecar.legacy_removed", "validate.sidecar-removed"),
)


def _canonical_entries() -> tuple[CheckEntry, ...]:
    clear_checks_for_tests()
    for module_name in CANONICAL_CHECK_MODULES:
        importlib.reload(importlib.import_module(f"science_tool.validate.checks.{module_name}"))
    return tuple(CANONICAL_CHECKS)


def test_declared_status_and_inverse_ids_equal_active_kind_expansion() -> None:
    active = frozenset({"hypothesis", "workflow_run", "pre-registration", "pH"})
    assert {rule.id for rule in status_vocabulary_rules(active)} == {
        "hypothesis.status-vocabulary",
        "workflow-run.status-vocabulary",
        "pre-registration.status-vocabulary",
        "ph.status-vocabulary",
    }
    assert {rule.id for rule in supersession_rules(active)} == {
        "hypothesis.unbacked-inverse",
        "workflow-run.unbacked-inverse",
        "pre-registration.unbacked-inverse",
        "ph.unbacked-inverse",
    }


@pytest.mark.parametrize(
    "active",
    [
        frozenset({"workflow_run", "workflow-run"}),
        frozenset({"pH", "ph"}),
    ],
)
@pytest.mark.parametrize("factory", [status_vocabulary_rules, supersession_rules])
def test_kind_family_collision_fails_before_registry_construction(
    factory,
    active,
) -> None:
    with pytest.raises(ValueError, match="collide"):
        factory(active)


def test_sparse_family_emissions_are_declared_and_belong_to_active_registry() -> None:
    active = frozenset({"hypothesis", "interpretation"})
    declared_status = {rule.id for rule in status_vocabulary_rules(active)}
    declared_inverse = {rule.id for rule in supersession_rules(active)}
    sparse_status = {"hypothesis.status-vocabulary"}
    sparse_inverse = {"interpretation.unbacked-inverse"}
    assert sparse_status <= declared_status
    assert sparse_inverse <= declared_inverse
    assert {rule_id.rsplit(".", 1)[0] for rule_id in sparse_status} <= active
    assert {rule_id.rsplit(".", 1)[0] for rule_id in sparse_inverse} <= active


def test_annotation_suffixes_equal_issue_kinds() -> None:
    assert set(ANNOTATION_RULES) == set(ISSUE_KINDS)
    assert {rule.id.removeprefix("annotations.") for rule in ANNOTATION_RULES.values()} == set(ISSUE_KINDS)


def test_correspondence_and_hypothesis_gate_ids_remain_exact() -> None:
    assert RULE_CORRESPONDENCE_DRIFT.id == "plan.correspondence-drift"
    assert RULE_CORRESPONDENCE_DRIFT.identity_qualifiers == ("evidence_signature",)
    assert {rule for rule in cumulative_rules("hygiene") if rule.startswith("hypothesis.")} == {
        "hypothesis.status-vocabulary",
        "hypothesis.dangling-lineage",
        "hypothesis.unbacked-inverse",
    }


def test_prose_policy_rules_keep_distinct_visibility_and_metrics_only_coverage() -> None:
    assert RULE_HIT.default_visibility == "visible"
    assert RULE_CONFIG.default_visibility == "visible"
    assert RULE_ADVISORY.default_visibility == "hidden"
    assert set(NumericVerificationMetrics.model_fields) == {
        "verified",
        "unverifiable",
        "mismatch",
        "error",
    }
    assert all("numeric-verification.coverage" not in rule.id for rule in (RULE_HIT, RULE_CONFIG, RULE_ADVISORY))


def test_static_rule_migrations_are_complete_and_old_ids_are_absent() -> None:
    assert len(_STATIC_RULE_MIGRATIONS) == 31
    declared = {rule.id for entry in _canonical_entries() for rule in entry.producer.rules} | {
        rule.id for rule in VALIDATION_RUNTIME_PRODUCER.rules
    }
    assert {new for _, new in _STATIC_RULE_MIGRATIONS if new is not None} <= declared
    assert not ({old for old, _ in _STATIC_RULE_MIGRATIONS} & declared)
    rule_id_pattern = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
    assert all(rule_id_pattern.fullmatch(rule_id) for rule_id in declared)


def test_ordinary_identity_uses_semantic_keys_not_rendering_details(
    tmp_path: Path,
) -> None:
    rule = MANIFEST_RULES["manifest.check"]
    common = {
        "path": Path("science.yaml"),
        "rule": rule,
        "task": None,
        "qualifiers": {"key": ["required-field", "created"]},
    }
    findings = [
        Result(
            severity=severity,
            line=line,
            message=message,
            **common,
        ).to_finding(tmp_path)
        for severity, line, message in (
            (Severity.ERROR, 1, "first wording"),
            (Severity.WARN, 99, "second wording"),
        )
    ]
    assert findings[0].qualifiers["key"] == findings[1].qualifiers["key"]
    changed = Result(
        severity=Severity.ERROR,
        line=1,
        message="first wording",
        path=Path("science.yaml"),
        rule=rule,
        task=None,
        qualifiers={"key": ["required-field", "status"]},
    ).to_finding(tmp_path)
    assert changed.qualifiers["key"] != findings[0].qualifiers["key"]


def test_nonpolicy_info_becomes_notice_but_policy_info_remains_finding() -> None:
    ordinary = validation_observation(
        severity=Severity.INFO,
        path=None,
        line=None,
        message="progress",
        rule=MANIFEST_RULES["manifest.check"],
        task=None,
        qualifiers={"key": ["progress"]},
    )
    policy = validation_observation(
        severity=Severity.INFO,
        path=None,
        line=None,
        message="configured",
        rule=RULE_CONFIG,
        task=None,
        qualifiers={},
    )
    advisory = validation_observation(
        severity=Severity.INFO,
        path=None,
        line=None,
        message="advisory",
        rule=RULE_ADVISORY,
        task=None,
        qualifiers={"check": "numeric-verification", "count": 1},
    )
    assert isinstance(ordinary, ValidationNotice)
    assert isinstance(policy, Result)
    assert isinstance(advisory, Result)


def test_registered_projection_never_reinvokes_raw_check(tmp_path: Path) -> None:
    from science_tool.validate import runner
    from science_tool.validate.context import ValidateContext

    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    section = FindingSection(
        id="test-raw-once",
        title="Test raw once",
        section_order=999,
    )
    rule = FindingRule(
        id="test.raw-once",
        severities=frozenset({"error"}),
        subject_types=frozenset({"project"}),
        qualifier_schema=ValidationQualifiers,
        identity_qualifiers=("key",),
        title="Test raw once",
        section=section.id,
        display_order=1,
    )
    calls = 0

    @Check(
        section=section,
        order=99_999,
        producer_id="validate.test.raw-once",
        rules=(rule,),
        metrics_schema=NumericVerificationMetrics,
    )
    def raw_observations(_ctx):
        nonlocal calls
        calls += 1
        yield Result(
            Severity.ERROR,
            None,
            None,
            "missing",
            rule,
            None,
            {"key": ["required-field", "name"]},
        )
        yield ValidationMetricObservation(
            metrics=ProducerMetrics.model_validate(
                {
                    "verified": 1,
                    "unverifiable": 2,
                    "mismatch": 3,
                    "error": 4,
                }
            )
        )
        yield ValidationNotice(path=None, line=None, message="progress")

    entry = next(item for item in CANONICAL_CHECKS if item.producer.producer_id == "validate.test.raw-once")
    try:
        ctx = ValidateContext.from_project_root(
            tmp_path,
            strict=False,
            verbose=False,
        )
        result, notices = runner._execute_check(
            entry,
            ctx,
            build_project_registry(tmp_path),
            tuple(entry.fn(ctx)),
        )
        assert calls == 1
        assert len(result.instrument.rows) == 1
        assert result.metrics.model_dump(mode="json") == {
            "verified": 1,
            "unverifiable": 2,
            "mismatch": 3,
            "error": 4,
        }
        assert [notice.message for notice in notices] == ["progress"]
    finally:
        CANONICAL_CHECKS.remove(entry)


def test_actual_evidence_emitter_has_no_same_subject_identity_collision(
    tmp_path: Path,
) -> None:
    from science_tool.validate.context import ValidateContext

    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    path = tmp_path / "entities" / "evidence-lines" / "el01.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nsource: paper:x\n---\n", encoding="utf-8")
    ctx = ValidateContext.from_project_root(
        tmp_path,
        strict=False,
        verbose=False,
    )
    entry = next(
        item
        for item in _canonical_entries()
        if item.producer.producer_id == "validate.evidence-lines.evidence-lines-unstanced"
    )

    observations = [item.to_finding(tmp_path) if isinstance(item, Result) else item for item in entry.fn(ctx)]
    batch = ValidationObservationBatch.from_observations(observations)
    result = validate_producer_result(
        build_project_registry(tmp_path),
        entry.producer.producer_id,
        entry.produce(batch),
    )

    assert len(result.instrument.rows) == 2
    assert {tuple(item.qualifiers["key"]) for item in result.instrument.rows} == {
        ("required-field", "stance"),
        ("required-field", "target"),
    }


def _write_multi_issue_fixture(
    root: Path,
    family: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (root / "science.yaml").write_text(
        "name: test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )
    if family == "evidence":
        path = root / "entities" / "evidence-lines" / "el01.md"
        path.parent.mkdir(parents=True)
        path.write_text("---\nsource: paper:x\n---\n", encoding="utf-8")
    elif family == "cross-references":
        path = root / "entities" / "reports" / "a.md"
        path.parent.mkdir(parents=True)
        path.write_text(
            "---\nid: report:a\nrelated: [missing:one, missing:two]\n---\n",
            encoding="utf-8",
        )
    elif family == "origins":
        path = root / "entities" / "findings" / "a.md"
        path.parent.mkdir(parents=True)
        path.write_text(
            "---\nid: finding:a\norigins:\n"
            "  - {type: literature, ref: 'cite:missing-one'}\n"
            "  - {type: literature, ref: 'cite:missing-two'}\n---\n",
            encoding="utf-8",
        )
    elif family == "unresolved-markers":
        path = root / "doc" / "note.md"
        path.parent.mkdir(parents=True)
        path.write_text("[UNVERIFIED]\n[MISSING_CITATION]\n", encoding="utf-8")
    elif family == "workflow-steps":
        methods = root / "entities" / "methods"
        methods.mkdir(parents=True)
        methods.joinpath("method.md").write_text(
            "---\nid: method:m\nkind: method\ntitle: M\nstochasticity: seedable\nseed_params: [a, b]\n---\n",
            encoding="utf-8",
        )
        steps = root / "entities" / "workflow-steps"
        steps.mkdir(parents=True)
        steps.joinpath("step.md").write_text(
            "---\nid: workflow-step:s\nkind: workflow-step\ntitle: S\nmethod: method:m\n---\n",
            encoding="utf-8",
        )
    elif family == "prose-lints":
        path = root / "doc" / "note.md"
        path.parent.mkdir(parents=True)
        path.write_text(
            "Smith 2020 reported this result.\nJones 2021 repeated it.\n",
            encoding="utf-8",
        )
    elif family == "lens-views":
        directory = root / "entities" / "questions"
        directory.mkdir(parents=True)
        for slug, lens in (("one", "mechanism"), ("two", "analogy")):
            directory.joinpath(f"{slug}.md").write_text(
                "---\n"
                f"id: question:{slug}\n"
                "kind: question\n"
                "origins:\n"
                f"  - {{type: assistant, ref: explore-ideas-{lens}}}\n"
                "---\n",
                encoding="utf-8",
            )
    elif family == "autonomous-runs":
        from science_tool.validate.checks import autonomous_runs

        (root / ".git").mkdir()
        monkeypatch.setattr(
            autonomous_runs,
            "_marked_commits",
            lambda _root: [
                ("a" * 40, "run:2026-07-28-missing-a"),
                ("b" * 40, "run:2026-07-28-missing-b"),
            ],
        )
        monkeypatch.setattr(
            autonomous_runs,
            "load_run_records",
            lambda _root: [],
        )
    elif family == "accepted-validation":
        (root / "science.yaml").write_text(
            "name: test\n"
            "health:\n"
            "  accepted_validation:\n"
            "    - rule: plan.correspondence-drift\n"
            "      path: entities/plans/one.md\n"
            "      reason: first\n"
            "    - rule: plan.correspondence-drift\n"
            "      path: entities/plans/two.md\n"
            "      reason: second\n",
            encoding="utf-8",
        )
    elif family == "directory-structure":
        (root / "AGENTS.md").write_text(
            "@core/legacy.md\n",
            encoding="utf-8",
        )
    elif family == "prereg-vehicles":
        (root / ".git").mkdir()
        directory = root / "entities" / "pre-registrations"
        directory.mkdir(parents=True)
        directory.joinpath("one.md").write_text(
            "---\nkind: pre-registration\nstatus: committed\nvehicles:\n  - {label: first}\n  - {label: second}\n---\n",
            encoding="utf-8",
        )
    elif family == "prereg-schedule":
        directory = root / "entities" / "pre-registrations"
        directory.mkdir(parents=True)
        directory.joinpath("one.md").write_text(
            "---\n"
            "kind: pre-registration\n"
            "status: committed\n"
            "---\n"
            "burn-in = 5. Apply thinning every 10 draws. Require ESS >= 400.\n"
            "## Cost Gate (execution geometry)\n"
            "| Field | Declaration | Rationale |\n"
            "|---|---|---|\n",
            encoding="utf-8",
        )
    elif family == "materialization":
        directory = root / "entities" / "interpretations"
        directory.mkdir(parents=True)
        directory.joinpath("one.md").write_text(
            "---\n"
            "id: interpretation:one\n"
            "kind: interpretation\n"
            "supersedes: interpretation:old\n"
            "amends: interpretation:draft\n"
            "---\n",
            encoding="utf-8",
        )
    elif family == "labnote-export":
        path = root / ".labnote" / "app_export" / "views.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            '{"views": [{"id": "one", "surface": "findings"}, {"id": "two", "surface": "findings"}]}\n',
            encoding="utf-8",
        )
    elif family == "dataset-taxonomy":
        directory = root / "entities" / "datasets"
        directory.mkdir(parents=True)
        directory.joinpath("one.md").write_text(
            "---\n"
            "id: dataset:one\n"
            "kind: dataset\n"
            "origin: external\n"
            "source_class: observational\n"
            "dataset_usage:\n"
            "  - {role: analyzed}\n"
            "  - {ref: paper:not-a-dataset, role: analyzed}\n"
            "---\n",
            encoding="utf-8",
        )
    elif family == "dataset-influence":
        from science_tool.validate.checks import dataset_influence

        directory = root / "entities" / "papers"
        directory.mkdir(parents=True)
        directory.joinpath("one.md").write_text(
            "---\n"
            "id: paper:one\n"
            "kind: paper\n"
            "dataset_usage:\n"
            "  - {ref: dataset:missing-a, role: analyzed}\n"
            "  - {ref: dataset:missing-b, role: analyzed}\n"
            "---\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            dataset_influence,
            "_dataset_ref_statuses",
            lambda _ctx, refs, _frontmatters: {ref: "missing" for ref in refs},
        )
    elif family == "identity-provenance":
        directory = root / "entities" / "datasets"
        directory.mkdir(parents=True)
        directory.joinpath("one.md").write_text(
            "---\n"
            "id: dataset:one\n"
            "kind: dataset\n"
            "identity_context:\n"
            "  assembly:\n"
            "    transform: {dataset: 'dataset:missing-a'}\n"
            "    proxy: {via: 'dataset:missing-b'}\n"
            "derivation: {transformations: []}\n"
            "---\n",
            encoding="utf-8",
        )
    elif family == "code-files":
        directory = root / "code"
        directory.mkdir()
        directory.joinpath("one.py").write_text(
            "# science:code\n"
            "# status: workflow-owned\n"
            "# task_ids: [missing-a, missing-b]\n"
            "# science:end\n"
            "print('ok')\n",
            encoding="utf-8",
        )
    elif family == "hypothesis-lineage":
        directory = root / "entities" / "hypotheses"
        directory.mkdir(parents=True)
        directory.joinpath("one.md").write_text(
            "---\n"
            "id: hypothesis:one\n"
            "kind: hypothesis\n"
            "title: One\n"
            "status: superseded\n"
            "created: '2026-07-28'\n"
            "updated: '2026-07-28'\n"
            "resynthesized_into:\n"
            "  - hypothesis:missing-a\n"
            "  - hypothesis:missing-b\n"
            "---\n",
            encoding="utf-8",
        )
    else:
        raise AssertionError(f"unknown fixture family {family}")


@pytest.mark.parametrize(
    ("family", "producer_id", "minimum_rows"),
    (
        (
            "evidence",
            "validate.evidence-lines.evidence-lines-unstanced",
            2,
        ),
        (
            "cross-references",
            "validate.cross-references.cross-references",
            2,
        ),
        ("origins", "validate.origins", 2),
        ("unresolved-markers", "validate.unresolved-markers", 2),
        ("workflow-steps", "validate.workflow-steps", 2),
        ("prose-lints", "validate.prose-lints", 1),
        ("lens-views", "validate.lens-views", 2),
        ("autonomous-runs", "validate.autonomous-runs", 2),
        (
            "accepted-validation",
            "validate.accepted-validation",
            2,
        ),
        ("directory-structure", "validate.directory-structure", 2),
        ("prereg-vehicles", "validate.prereg-vehicles", 2),
        ("prereg-schedule", "validate.prereg-schedule", 2),
        ("materialization", "validate.materialization", 2),
        ("labnote-export", "validate.labnote-export", 2),
        ("dataset-taxonomy", "validate.dataset-taxonomy", 2),
        ("dataset-influence", "validate.dataset-influence", 2),
        (
            "identity-provenance",
            "validate.identity-context.identity-provenance",
            4,
        ),
        ("code-files", "validate.code-files.code-files", 2),
        (
            "hypothesis-lineage",
            "validate.hypotheses.dangling-lineage",
            2,
        ),
    ),
)
def test_multi_issue_emitters_have_one_semantic_identity_per_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    family: str,
    producer_id: str,
    minimum_rows: int,
) -> None:
    from science_tool.validate import runner
    from science_tool.validate.context import ValidateContext

    entry = next(item for item in _canonical_entries() if item.producer.producer_id == producer_id)
    _write_multi_issue_fixture(tmp_path, family, monkeypatch)
    ctx = ValidateContext.from_project_root(
        tmp_path,
        strict=False,
        verbose=False,
    )
    registry = build_project_registry(tmp_path)
    result, _ = runner._execute_check(
        entry,
        ctx,
        registry,
        tuple(entry.fn(ctx)),
    )

    identities = [
        finding_fingerprint(
            rule_id=finding.rule_id,
            subject=finding.subject,
            identity_qualifiers=registry.rule(finding.rule_id).identity_subset(finding.qualifiers),
        )
        for finding in result.instrument.rows
    ]
    assert len(identities) >= minimum_rows
    assert len(identities) == len(set(identities))


def test_accepted_validation_coalesces_equivalent_severity_spellings_at_registered_boundary(
    tmp_path: Path,
) -> None:
    from science_tool.validate import runner
    from science_tool.validate.context import ValidateContext

    (tmp_path / "science.yaml").write_text(
        "name: test\n"
        "health:\n"
        "  accepted_validation:\n"
        "    - rule: plan.correspondence-drift\n"
        "      severity: warn\n"
        "      path: entities/plans/one.md\n"
        "      reason: first spelling\n"
        "    - rule: plan.correspondence-drift\n"
        "      severity: warning\n"
        "      path: entities/plans/one.md\n"
        "      reason: equivalent spelling\n",
        encoding="utf-8",
    )
    entry = next(item for item in _canonical_entries() if item.producer.producer_id == "validate.accepted-validation")
    ctx = ValidateContext.from_project_root(
        tmp_path,
        strict=False,
        verbose=False,
    )
    result, _ = runner._execute_check(
        entry,
        ctx,
        build_project_registry(tmp_path),
        tuple(entry.fn(ctx)),
    )

    assert len(result.instrument.rows) == 1


def test_finite_dispatch_maps_equal_their_authorities() -> None:
    assert set(SUPPORT_FIELD_RULES) == {
        field for field in BENCHMARK_TASK_SUPPORT_FIELDS if field in {"evidence", "notes"}
    }
    assert set(TIER_DECLARATION_RULES) == {
        "assembly",
        "gene",
        "protein",
        "variant",
    }
    assert set(MOLECULAR_SPEC_RULES) == {
        (tier, outcome)
        for tier in ("gene", "protein")
        for outcome in (
            "malformed",
            "namespace-unsupported",
            "declared-unresolved",
            "registry-unavailable",
            "registry-invalid",
        )
    }
    assert set(RELATION_RULES) == {
        "unknown-subject",
        "unknown-object",
        "unknown-predicate",
        "unsupported-graph-layer",
        "external-target",
        "self-referential",
        "illegal-kind-pair",
        "membership-role",
        "cycle",
    }
    assert set(FINGERPRINT_RULES) == {
        RULE_INCOMPLETE,
        RULE_AUTHORED_CAPTURABLE,
    }


def test_result_rule_arguments_are_never_string_literals_or_fstrings() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src" / "science_tool"
    paths = [
        *sorted(source_root.joinpath("validate", "checks").glob("*.py")),
        source_root / "validate" / "runner.py",
        source_root / "validate" / "runtime.py",
    ]
    violations: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            name = call.func.id if isinstance(call.func, ast.Name) else None
            if name not in {"Result", "validation_observation"}:
                continue
            candidates = [keyword.value for keyword in call.keywords if keyword.arg == "rule"]
            if name == "Result" and len(call.args) >= 5:
                candidates.append(call.args[4])
            if any(isinstance(value, ast.Constant | ast.JoinedStr) for value in candidates):
                violations.append(f"{path.relative_to(source_root)}:{call.lineno}")
    assert violations == []
