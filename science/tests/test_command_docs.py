from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

TOOL_MANIFEST_SNIPPET = """```toml
[project]
name = "<project-slug>-sciences"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = []
```"""

USER_GUIDE_DOC = "docs/" + "user-guide.md"
PROJECT_ORGANIZATION_DOC = "docs/" + "project-organization-profiles.md"
PROJECT_WORKING_MODEL_DOC = "docs/conventions/" + "project-working-model-" + "h00.md"
PROJECT_WORKING_MODEL_STEM = "project-working-model-" + "h00"
PROPOSITION_MODEL_DOC = "docs/" + "proposition-and-evidence-model.md"
CLAIM_MODEL_DOC = "docs/" + "claim-and-evidence-model.md"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _slice_between(text: str, start: str, end: str) -> str:
    if start not in text:
        raise AssertionError(f"missing start marker: {start}")
    if end not in text:
        raise AssertionError(f"missing end marker: {end}")
    return text.split(start, 1)[1].split(end, 1)[0]


def _norm(text: str) -> str:
    return " ".join(text.split())


def test_catalog_datasets_setup_is_layout_v3_aware() -> None:
    text = _read("commands/catalog-datasets.md")

    assert "entities/questions/" in text
    assert "entities/hypotheses/" in text
    assert "legacy specs/research-question.md only if it exists" in text
    assert "legacy specs/scope-boundaries.md only if it exists" in text
    assert "- `specs/research-question.md`" not in text
    assert "- `specs/scope-boundaries.md`" not in text


def test_catalog_datasets_connect_warns_about_legacy_metadata_backfill() -> None:
    text = _read("commands/catalog-datasets.md")

    assert "When connecting or backfilling legacy dataset entities" in text
    assert "do not add `origin: external` by itself" in text
    assert "set `license:` at the same time" in text
    assert "`unknown` is acceptable" in text
    assert "source_class: derived" in text
    assert "dataset_usage" in text
    assert "role: \"upstream\"" in text
    assert "role: \"training\"" in text


def test_catalog_datasets_documents_dataset_link_helper_and_deposit_landing_method() -> None:
    text = _read("commands/catalog-datasets.md")

    assert "science dataset reconcile-links --format json" in text
    assert "science dataset reconcile-links --fix" in text
    assert "science dataset link <dataset-ref> <question-or-hypothesis-ref>" in text
    assert "idempotent" in text
    assert "landing-confirmed" in text
    assert "deposit" in text
    assert "reject default `deposit` rows" not in text


def test_plan_pipeline_respects_project_plan_numbering_convention() -> None:
    text = _read("commands/plan-pipeline.md")

    assert "Do not blindly use `YYYY-MM-DD-<slug>` in projects whose `entities/plans/` use numeric `NNNN-` stems" in text
    assert "entities/plans/<NNNN>-<slug>.md" in text


def test_review_pipeline_runtime_stageability_allows_wp1_retrieval_probe_defer() -> None:
    text = _read("commands/review-pipeline.md")
    normalized = " ".join(text.split())

    assert "PASS-with-note" in text
    assert "WP1 is the staging step" in text
    assert "access.verified: true" in text
    assert "do not score absent runtime files as FAIL" in normalized


def test_find_datasets_setup_is_layout_v3_aware() -> None:
    text = _read("commands/find-datasets.md")

    assert "entities/questions/" in text
    assert "entities/hypotheses/" in text
    assert "entities/datasets/" in text
    assert "legacy specs/research-question.md only if it exists" in text
    assert "legacy specs/scope-boundaries.md only if it exists" in text
    assert "- `specs/research-question.md`" not in text
    assert "- `specs/scope-boundaries.md`" not in text


def test_find_datasets_routes_durable_records_through_dataset_lifecycle() -> None:
    text = _read("commands/find-datasets.md")

    assert "science datasets search" in text
    assert "science datasets metadata <source>:<id> --format json" in text
    assert "science datasets files <source>:<id> --format json" in text
    assert "science dataset add <slug>" in text
    assert "--level <public|registration|controlled|commercial|mixed>" in text
    add_example = _slice_between(
        text,
        "science dataset add <slug>",
        "science dataset verify-access <slug>",
    )
    assert "--license" not in add_example
    assert "science dataset verify-access <slug>" in text
    assert "--method <retrieved|credential-confirmed|landing-confirmed|metadata-confirmed>" in text
    assert '--source-url "<landing-page-or-download-url>"' in text
    assert "science dataset link <dataset-ref> <question-or-hypothesis-ref>" in text
    assert "science dataset prioritize" in text
    assert "Direct template authoring is a fallback" in text
    assert "For each `Use now` or `Evaluate next` dataset, create a dataset note" not in text
    assert "Update `science.yaml` data_sources section with new entries" not in text
    assert "--level <public|controlled|mixed>" not in text
    assert "--method <landing-confirmed|downloaded|manual-review>" not in text
    assert '--source "<landing-page-or-download-url>"' not in text
    assert "--date <YYYY-MM-DD>" not in text


def test_plan_pipeline_uses_current_dataset_verify_access_gate() -> None:
    text = _read("commands/plan-pipeline.md")

    assert "science dataset verify-access <slug>" in text
    assert "current `science dataset verify-access`" in text
    assert "future science dataset verify" not in text
    assert "future `science dataset verify`" not in text
    assert "(manual or future `science dataset verify`)" not in text


def test_review_pipeline_uses_current_dataset_verify_access_gate() -> None:
    text = _read("commands/review-pipeline.md")

    assert "science dataset verify-access <slug>" in text
    assert "Access verification should be current" in text
    assert "science dataset verify " not in text
    assert "future science dataset verify" not in text
    assert "science dataset verify`" not in text


def test_task_command_docs_use_aspects_for_task_creation() -> None:
    for path in ("commands/tasks.md", "commands/review-tasks.md"):
        text = _read(path)

        assert "tasks add \"<title>\" --type" not in text
        assert "tasks add \"<title>\" --aspects=<aspect>" in text


def test_task_command_docs_allow_task_scoped_aspects_without_project_declaration() -> None:
    text = _read("commands/tasks.md")

    assert "Task-scoped aspects do not need to be declared in `science.yaml`" in text
    assert "project-wide aspect behavior" in text


def test_create_project_gitignore_excludes_transient_agent_artifacts() -> None:
    text = _read("commands/create-project.md")

    assert "entities/meta/*next-steps*.md" in text
    assert "doc/meta/next-steps-*.md" in text
    assert "doc/plans/*-plan-review.md" in text
    assert "docs/plans/*-plan-review.md" in text
    assert "unless explicitly promoted" in text


def test_plan_analysis_guides_blocker_tasks_to_reuse_task_scoped_aspects() -> None:
    text = _read("commands/plan-analysis.md")

    assert "Reuse task-scoped aspects" in text
    assert "do not mutate `science.yaml` solely to create blocker tasks" in text


def test_plan_analysis_discovers_prior_pre_registrations_in_legacy_doc_meta() -> None:
    text = _read("commands/plan-analysis.md")

    assert "Pre-registration discovery" in text
    assert "entities/pre-registrations/" in text
    assert "doc/meta/" in text
    assert "docs/meta/" in text
    assert "legacy `specs/` locations only if they exist" in text
    assert "do not assume absence just because `entities/pre-registrations/` is empty" in text


def test_plan_analysis_requires_per_input_data_profile() -> None:
    text = _read("commands/plan-analysis.md")

    assert "Per-Input Data Profile" in text
    assert "one row per input artifact or dataset" in text
    assert "encoding / file format" in text
    assert "row grain" in text
    assert "join cardinality" in text
    assert "missing-value sentinels" in text
    assert "provenance / source version" in text
    assert "checksum or immutable identifier" in text


def test_plan_analysis_preserves_locked_pre_registration_criteria() -> None:
    text = _read("commands/plan-analysis.md")

    assert "When a Pre-Registration Already Exists" in text
    assert "do **not** re-derive decision" in text
    assert "relitigating a committed criterion set here invites" in text
    assert "HARKing" in text
    assert "treat it as an amendment question rather than a" in text


def test_plan_pipeline_documents_mixed_access_public_slice_gate() -> None:
    text = _read("commands/plan-pipeline.md")

    assert "`access.level: mixed` with public-slice consumption" in text
    assert "PASS/DEFER only for the named public slice" in text
    assert "controlled or commercial siblings remain out of scope" in text
    assert "HALT if the plan would consume any restricted sibling" in text


def test_plan_pipeline_does_not_invent_validation_concepts() -> None:
    text = _read("commands/plan-pipeline.md")
    normalized = _norm(text)

    assert "Transformation `validated_by` refs should point to existing validation artifacts" in normalized
    assert "Leave `validated_by` blank or omit it when no validation artifact exists yet." in normalized
    assert "Do not use `concept:<check>` as a placeholder for a validation record that does not exist." in normalized
    assert 'validated_by: "<existing-validation-ref>"' in text
    assert 'validated_by: "concept:<check>"' not in text


def test_pre_register_documents_runnable_now_execution_readiness_gate() -> None:
    text = _read("commands/pre-register.md")

    assert "Execution-readiness gate" in text
    assert "runnable-now mode" in text
    assert "power floor, input QA, preprocessing checks, and required sensitivity checks" in text
    assert "gate verdict interpretability rather than data availability" in text


def test_pre_register_documents_multi_analysis_registry_for_mixed_modes() -> None:
    text = _read("commands/pre-register.md")

    assert "Analysis Registry" in text
    assert "one pre-registration covers multiple analyses" in text
    assert "mixed runnable/data-gated statuses" in text
    assert "Record each analysis's `mode` (`runnable-now` or `data-gated`)" in text
    assert "link each row to its readiness gate or vehicle-admissibility gate" in text


def test_pre_register_documents_in_run_no_peeking_calibration_gate() -> None:
    text = _read("commands/pre-register.md")

    assert "Calibration Gate" in text
    assert "in-run, no-peeking, marginal-derived threshold" in text
    assert "marginal distributions or eligibility counts only" in text
    assert "forbid outcome labels, effect estimates, group-contrast results" in text
    assert "not a data-gated pre-registration" in text


def test_pre_register_loads_real_artifacts_before_locking_thresholds() -> None:
    text = _read("commands/pre-register.md")

    assert "Feasibility Against Real Input Artifacts" in text
    assert "Before locking any threshold in § 3" in text
    assert "load the actual input artifacts" in text
    assert "Support-set size" in text
    assert "Universe alignment" in text
    assert "underpowered or that the wrong arm was slated as confirmatory" in text
    assert "re-scope, swap which arm is confirmatory/exploratory" in text
    assert "caught pre-data because the artifacts" in text
    assert "were loaded before the criteria were locked" in text


def test_pre_register_rederives_every_referenced_count_from_artifacts() -> None:
    text = _read("commands/pre-register.md")

    assert "Count ledger" in text
    assert "every numeric count referenced anywhere in the pre-registration" in text
    assert "denominators, subgroup counts, exclusion counts, missingness counts" in text
    assert "supporting counts in prose, tables, or caveats" in text
    assert "Do not only verify the headline arm" in text
    assert "re-derived from the loaded artifact" in text


def test_specify_model_documents_proxy_directness_vocabulary() -> None:
    text = _read("commands/specify-model.md")

    assert "`proxy_directness:` must be one of `direct`, `indirect`, or `derived`" in text
    assert "Do not write `proxy`; graph build rejects it." in text
    assert "`indirect` for a measured proxy of the target construct" in text
    assert "`derived` for a computed or model-derived proxy" in text


def test_specify_model_routes_hypotheses_to_durable_proposition_bundles() -> None:
    text = _read("commands/specify-model.md")

    assert "**Hypothesis / epistemic entity with no DAG yet**" in text
    assert "decompose the hypothesis into durable `proposition:` entities" in text
    assert "link each proposition back to the hypothesis with `related: [\"hypothesis:<id>\"]`" in text
    assert "add the proposition refs to the hypothesis's Proposition Bundle" in text
    assert "Do not leave the decomposition only as prose inside the hypothesis file." in text


def test_graph_docs_explain_local_only_build_for_composite_noise_control() -> None:
    user_guide = _read("docs/user-guide/graph-and-derived-state.md")
    federation = _read("docs/federation.md")

    for text in (user_guide, federation):
        assert "science graph build --local-only" in text
        assert "leaves `knowledge/composite.trig` untouched" in text


def test_pipeline_audit_process_documents_clean_base_qa_checkpoint_pattern() -> None:
    text = _read("docs/process/pipeline-audit-and-refactor.md")

    expected_strings = (
        "Clean-base QA checkpoint pattern",
        "prepared gene-by-sample matrices",
        "mapped gene-set universes",
        "matrix sample/audit consistency",
        "unique feature IDs",
        "finite values",
        "no all-NA rows",
        "feature-count agreement with the transform audit",
        "gene-set size-filter compliance",
        "complete theme/annotation coverage",
        "release/hash metadata",
    )
    for expected in expected_strings:
        assert expected in text


def test_pipeline_audit_process_uses_layout_v3_dataset_owner_paths() -> None:
    text = _read("docs/process/pipeline-audit-and-refactor.md")

    assert "entities/datasets/*.md" in text
    assert "entities/datasets/<slug>.md" in text
    assert "doc/datasets/data-*.md" not in text
    assert "doc/datasets/data-<slug>.md" not in text
    assert "mixin-dataset-1.0` fields" not in text


def test_pipeline_audit_process_documents_result_bundle_validation_modes() -> None:
    text = _read("docs/process/pipeline-audit-and-refactor.md")

    expected_strings = (
        "Result-bundle QA and wiring verification",
        "`qa_all`",
        "direct result-QA smoke checks",
        "existing ignored outputs",
        "dry-run DAG checks",
        "expensive stale downstream recomputation",
        "full recomputation",
        "intentional pipeline refresh",
    )
    for expected in expected_strings:
        assert expected in text


def test_pipeline_audit_process_documents_derived_artifact_freshness_checks() -> None:
    text = _read("docs/process/pipeline-audit-and-refactor.md")

    expected_strings = (
        "Derived-artifact freshness checks",
        "deterministic artifacts committed for review",
        "authored input",
        "regenerates into memory or a temp file",
        "diffs against the checked-in artifact",
        "raw-data QA",
        "downstream result-bundle QA",
    )
    for expected in expected_strings:
        assert expected in text


@pytest.mark.parametrize(
    ("path", "expected_strings"),
    [
        (
            "commands/add-hypothesis.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                "${CLAUDE_PLUGIN_ROOT}/docs/user-guide/epistemic-model.md",
                ".ai/templates/hypothesis.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/hypothesis.md",
            ),
        ),
        (
            "commands/bias-audit.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                ".ai/templates/bias-audit.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/bias-audit.md",
            ),
        ),
        (
            "commands/compare-hypotheses.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                "${CLAUDE_PLUGIN_ROOT}/docs/user-guide/epistemic-model.md",
                ".ai/templates/comparison.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/comparison.md",
            ),
        ),
        (
            "commands/discuss.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                ".ai/templates/discussion.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/discussion.md",
                ".ai/templates/question.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/question.md",
            ),
        ),
        (
            "commands/find-datasets.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                "${CLAUDE_PLUGIN_ROOT}/skills/data/SKILL.md",
                "${CLAUDE_PLUGIN_ROOT}/skills/data/frictionless.md",
                ".ai/templates/dataset.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/dataset.md",
            ),
        ),
        (
            "commands/interpret-results.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                "${CLAUDE_PLUGIN_ROOT}/docs/user-guide/epistemic-model.md",
                "${CLAUDE_PLUGIN_ROOT}/docs/user-guide/evidence-lines.md",
                ".ai/templates/interpretation.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/interpretation.md",
            ),
        ),
        (
            "commands/next-steps.md",
            ("${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",),
        ),
        (
            "commands/pre-register.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                ".ai/templates/pre-registration.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/pre-registration.md",
            ),
        ),
        (
            "commands/research-papers.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                ".ai/templates/paper.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/paper.md",
                ".ai/templates/question.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/question.md",
            ),
        ),
        (
            "commands/research-topic.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                ".ai/templates/background-topic.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/background-topic.md",
                ".ai/templates/question.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/question.md",
            ),
        ),
        (
            "commands/search-literature.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                "${CLAUDE_PLUGIN_ROOT}/skills/data/sources/openalex.md",
                "${CLAUDE_PLUGIN_ROOT}/skills/data/sources/pubmed.md",
                ".ai/templates/paper.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/paper.md",
            ),
        ),
        (
            "commands/status.md",
            ("${CLAUDE_PLUGIN_ROOT}/docs/user-guide/epistemic-model.md",),
        ),
    ],
)
def test_command_docs_use_explicit_framework_resolution(
    path: str,
    expected_strings: tuple[str, ...],
) -> None:
    text = _read(path)
    for expected in expected_strings:
        assert expected in text


def test_data_skill_routes_new_sources_through_dataset_entity_lifecycle() -> None:
    text = _read("skills/data/SKILL.md")

    assert "science dataset add <slug>" in text
    assert "--level <public|registration|controlled|commercial|mixed>" in text
    add_example = _slice_between(
        text,
        "science dataset add <slug>",
        "science dataset verify-access <slug>",
    )
    assert "--license" not in add_example
    assert "science dataset verify-access <slug>" in text
    assert "--method <retrieved|credential-confirmed|landing-confirmed|metadata-confirmed>" in text
    assert '--source-url "<landing-page-or-download-url>"' in text
    assert "science dataset link <dataset-ref> <question-or-hypothesis-ref>" in text
    assert "Manual template authoring is a fallback" in text
    assert "entities/datasets/<slug>.md" in text
    assert "entities/datasets/<source-name>.md" not in text
    assert "runtime datapackage descriptors" in text
    assert "--level <public|controlled|mixed>" not in text
    assert "--method <landing-confirmed|downloaded|manual-review>" not in text
    assert '--source "<landing-page-or-download-url>"' not in text
    assert "--date <YYYY-MM-DD>" not in text


def test_frictionless_skill_distinguishes_datapackages_from_dataset_entities() -> None:
    text = _read("skills/data/frictionless.md")

    boundary = _slice_between(
        text,
        "## Boundary With Dataset Entities",
        "## Creating a Data Package",
    )

    assert "runtime/package descriptor" in boundary
    assert "not the local dataset entity lifecycle" in boundary
    assert "Use `science dataset add <slug>`" in boundary
    assert "science dataset verify-access <slug>" in boundary
    assert "science datasets validate --path data/raw/" in boundary


def test_command_docs_do_not_reference_retired_user_docs() -> None:
    retired = (
        USER_GUIDE_DOC,
        PROJECT_ORGANIZATION_DOC,
        PROJECT_WORKING_MODEL_DOC,
        PROJECT_WORKING_MODEL_STEM,
        PROPOSITION_MODEL_DOC,
        CLAIM_MODEL_DOC,
    )
    offenders: list[str] = []
    for path in (ROOT / "commands").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in retired):
            offenders.append(path.relative_to(ROOT).as_posix())

    assert not offenders


def test_plan_analysis_command_defines_methodology_readiness_workflow() -> None:
    text = _read("commands/plan-analysis.md")

    expected_strings = (
        "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
        "${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md",
        "entities/plans/<NNNN>-<slug>-analysis-plan.md",
        'type: "plan"',
        'plan_kind: "analysis-plan"',
        "skills_loaded:",
        "Readiness Decision",
        "ready-with-caveats",
        "science feedback add",
        '--target "command:plan-analysis"',
    )
    for expected in expected_strings:
        assert expected in text


def test_plan_analysis_command_covers_pressure_scenarios() -> None:
    text = _read("commands/plan-analysis.md")

    expected_strings = (
        "MM30 scRNA pseudobulk / entropy analysis",
        "cBioPortal targeted-panel mutation frequency or dN/dS analysis",
        "Natural-systems annotation/curation agreement analysis",
        "Protein-landscape heldout benchmark or embedding-manifold analysis",
        "data-expression-scrna-qa",
        "data-genomics-somatic-mutation-qa",
        "research-annotation-curation-qa",
        "data-protein-sequence-structure-qa",
    )
    for expected in expected_strings:
        assert expected in text


def test_plan_analysis_command_routes_proteomics_and_sensor_time_series() -> None:
    text = _read("commands/plan-analysis.md")
    index = _read("skills/INDEX.md")

    expected_strings = (
        "`data-proteomics-qa`: `skills/data/proteomics-qa.md`",
        "`statistics-time-series-and-longitudinal-models`: `skills/statistics/time-series-and-longitudinal-models.md`",
        "Proteomics, phosphoproteomics, mass spectrometry, peptide intensity, TMT, LFQ",
        "`data-proteomics-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration`",
        "Wearable, behavioral, actigraphy, EMA, symptom diary, sensor time series, sleep/activity rhythms, or cross-lag coupling",
        "`statistics-time-series-and-longitudinal-models`, `statistics-bias-vs-variance-decomposition`, `statistics-power-floor-acknowledgement`, and `statistics-sensitivity-arbitration`",
    )
    for expected in expected_strings[:2]:
        assert expected in index
    for expected in expected_strings[2:]:
        assert expected in text


def test_plan_analysis_command_routes_network_dyadic_permutation_designs() -> None:
    text = _read("commands/plan-analysis.md")

    expected_strings = (
        "Network/graph edges, dyadic data, edge prediction, node-label permutation, QAP/MRQAP",
        "`statistics-power-floor-acknowledgement`, `statistics-replicate-count-justification`, `statistics-sensitivity-arbitration`",
        "treat dyads as dependent observations",
    )
    for expected in expected_strings:
        assert expected in text

    assert "statistics-time-series-and-longitudinal-models` if present" not in text


def test_plan_analysis_is_integrated_with_neighbor_commands() -> None:
    expected_by_path = {
        "commands/plan-pipeline.md": (
            "/science:plan-analysis",
            "methodological readiness",
            "plan:<stem>",
        ),
        "commands/pre-register.md": (
            "plan:<stem>",
            "entities/plans/*-analysis-plan.md",
            "/science:plan-analysis",
        ),
        "commands/status.md": (
            "plan:<stem>",
            "/science:plan-analysis",
        ),
        "commands/next-steps.md": (
            "plan:<stem>",
            "entities/plans/*-analysis-plan.md",
            "/science:plan-analysis",
        ),
    }
    for path, expected_strings in expected_by_path.items():
        text = _read(path)
        for expected in expected_strings:
            assert expected in text


def test_next_steps_scans_done_files_for_each_month_in_recent_window() -> None:
    text = _read("commands/next-steps.md")

    assert "derive the recent-progress window first" in text
    assert "scan every `tasks/done/YYYY-MM.md` file whose month intersects that window" in text
    assert "Do not stop at the current month file" in text
    assert "treat those rows as recent progress, not status drift" in text


def test_needs_review_resolution_docs_cover_amendment_workflow() -> None:
    expected_by_path = {
        "commands/interpret-results.md": (
            "needs-review resolution",
            "sci:amends",
            "sci:supersedes",
            "sci:supersedesClaim",
            "entity review <target-ref>",
            "flagged entity",
            "status: superseded",
        ),
        "commands/next-steps.md": (
            "needs-review",
            "review prompt",
            "sci:amends",
            "sci:supersedes",
        ),
        "commands/status.md": (
            "needs-review",
            "review workflow",
            "sci:amends",
            "sci:supersedes",
        ),
        "commands/big-picture.md": (
            "sci:amends",
            "sci:supersedes",
            "prior_interpretations",
            "not the machine-readable chain",
        ),
        "templates/interpretation.md": (
            "relations:",
            "sci:amends",
            "sci:supersedes",
        ),
        "templates/interpretation-dev.md": (
            "relations:",
            "sci:amends",
            "sci:supersedes",
        ),
        "science/model/src/science_model/templates/interpretation.md": (
            "relations:",
            "sci:amends",
            "sci:supersedes",
        ),
        "science/model/src/science_model/templates/interpretation-dev.md": (
            "relations:",
            "sci:amends",
            "sci:supersedes",
        ),
    }
    for path, expected_strings in expected_by_path.items():
        text = _read(path)
        for expected in expected_strings:
            assert expected in text


@pytest.mark.parametrize(
    ("path", "expected_strings"),
    [
        (
            "commands/create-project.md",
            (
                TOOL_MANIFEST_SNIPPET,
                'uv add --dev --editable "$SCIENCE_TOOL_PATH"',
                "non-Python repos",
            ),
        ),
        (
            "commands/import-project.md",
            (
                TOOL_MANIFEST_SNIPPET,
                'uv add --dev --editable "$SCIENCE_TOOL_PATH"',
                "non-Python repos",
            ),
        ),
        (
            "references/project-structure.md",
            (
                TOOL_MANIFEST_SNIPPET,
                "tool-only manifest",
                "science",
            ),
        ),
        (
            "references/command-preamble.md",
            (
                "uv run science <command>",
                "project-local install",
                "uv add --dev --editable",
            ),
        ),
        (
            "README.md",
            (
                "pyproject.toml",
                "science",
                "project-local tooling",
            ),
        ),
    ],
)
def test_project_bootstrap_docs_cover_science_tool_install_contract(
    path: str,
    expected_strings: tuple[str, ...],
) -> None:
    text = _read(path)
    for expected in expected_strings:
        assert expected in text


@pytest.mark.parametrize("path", ["commands/create-project.md", "commands/import-project.md"])
def test_project_bootstrap_docs_ignore_managed_artifact_update_backups(path: str) -> None:
    text = _read(path)

    assert "*.pre-update*.bak" in text


def test_validate_cli_reference_documents_shim_contract() -> None:
    reference = _read("docs/conventions/validate.md")
    readme = _read("README.md")
    conventions_index = _read("docs/conventions/README.md")

    expected_reference_strings = (
        "# `science validate`",
        "## Synopsis",
        "science validate [--verbose] [--strict] [--all] [--format text|json] [--fail-on TIER] [--project-root PATH]",
        "## Flags",
        "--format text|json",
        "--project-root PATH",
        "## Exit Codes",
        "Warnings alone do not fail the command",
        "## Severity Model",
        "`--strict` enables strict advisory warnings; it does not promote `warn` results to `error`.",
        "## JSON Output Schema",
        '"summary": {"errors": 0, "warnings": 1, "infos": 0}',
        '"severity": "warn"',
        '"path": "doc/example.md"',
        '"line": 12',
        '"message": "example warning"',
        '"rule": "example.rule"',
        '"task": "task:t001"',
        "## Environment Variables",
        "NO_COLOR",
        "SCIENCE_VALIDATE_DISABLE_SIDECAR=1",
        "For `science validate`, disables both Python sidecar discovery and deprecated legacy `validate.local.sh` discovery.",
        "## Discovery",
        "`validate.sh` is the managed project artifact shim that delegates to `science validate`.",
        "`validate_local.py` is imported by default when it exists in the project root.",
        "Because `validate.sh` delegates to `science validate`, this environment variable affects validation reached through the shim as well.",
    )
    for expected in expected_reference_strings:
        assert expected in reference

    assert "[`science validate`](docs/conventions/validate.md)" in readme
    assert "Python sidecar hooks" in readme
    assert "experimental Python sidecars" not in readme
    assert "[`validate.md`](validate.md)" in conventions_index


@pytest.mark.parametrize(
    ("path", "legacy_strings"),
    [
        (
            "commands/add-hypothesis.md",
            (
                "Follow `references/command-preamble.md`",
                f"Read `{CLAIM_MODEL_DOC}`.",
            ),
        ),
        ("commands/bias-audit.md", ("Follow `references/command-preamble.md`",)),
        (
            "commands/compare-hypotheses.md",
            (
                "Follow `references/command-preamble.md`",
                f"Read `{CLAIM_MODEL_DOC}`.",
            ),
        ),
        ("commands/discuss.md", ("Follow `references/command-preamble.md`", "Read `templates/discussion.md`")),
        (
            "commands/find-datasets.md",
            (
                "Follow `references/command-preamble.md`",
                "Read `skills/data/SKILL.md` for data management conventions.",
                "If present, read `skills/data/frictionless.md` for Data Package guidance.",
            ),
        ),
        (
            "commands/interpret-results.md",
            (
                "Follow `references/command-preamble.md`",
                f"Read `{CLAIM_MODEL_DOC}`.",
            ),
        ),
        ("commands/next-steps.md", ("Follow `references/command-preamble.md`",)),
        (
            "commands/pre-register.md",
            ("Follow `references/command-preamble.md`", "Read `templates/pre-registration.md`"),
        ),
        ("commands/research-papers.md", ("Follow `references/command-preamble.md`", "Read `templates/paper.md`")),
        (
            "commands/research-topic.md",
            ("Follow `references/command-preamble.md`", "Read `templates/background-topic.md`"),
        ),
        (
            "commands/search-literature.md",
            (
                "Follow `references/command-preamble.md`",
                "Read `skills/data/sources/openalex.md`.",
                "Read `skills/data/sources/pubmed.md`.",
            ),
        ),
        ("commands/status.md", (f"If present, read `{CLAIM_MODEL_DOC}`.",)),
    ],
)
def test_command_docs_remove_project_local_framework_paths(path: str, legacy_strings: tuple[str, ...]) -> None:
    text = _read(path)
    for legacy in legacy_strings:
        assert legacy not in text


@pytest.mark.parametrize(
    ("path", "legacy_strings"),
    [
        (
            "README.md",
            (
                "claims and relation-claims are the main units of belief",
                CLAIM_MODEL_DOC,
            ),
        ),
        (
            "commands/interpret-results.md",
            (
                "claim-centric way",
                "`relation_claim`",
                "claim updates",
            ),
        ),
        (
            "commands/add-hypothesis.md",
            (
                "the concrete `claim` or `relation_claim` units that would actually be tested",
                "relation_claim`s",
                "claim bundle",
            ),
        ),
        (
            "commands/compare-hypotheses.md",
            (
                "Claim-Centric Evidence Inventory",
                "relation-claims",
                "claim bundle",
            ),
        ),
    ],
)
def test_command_docs_remove_claim_centric_terminology(
    path: str,
    legacy_strings: tuple[str, ...],
) -> None:
    text = _read(path)
    for legacy in legacy_strings:
        assert legacy not in text


def test_command_docs_do_not_reference_legacy_relation_claim_commands() -> None:
    forbidden_strings = (
        "`relation_claim`",
        "relation_claim:",
        "relation-claim",
        "science graph add claim",
        "science graph add relation-claim",
        "graph claim surfaces",
        "Claim And Graph Uncertainty",
    )
    offenders: list[str] = []
    for path in sorted((ROOT / "commands").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for forbidden in forbidden_strings:
            if forbidden in text:
                offenders.append(f"{path.relative_to(ROOT)} contains {forbidden!r}")
    assert not offenders


def test_entity_creation_cookbook_covers_positive_and_negative_examples() -> None:
    text = _read("docs/process/entity-creation-cookbook.md")

    for expected in (
        "gene",
        "protein",
        "family",
        "complex",
        "disease",
        "drug",
        "cell type",
        "phenotype",
        "pathway",
        "histone mark",
        "mechanism",
        "prose-only note",
        "what not to create",
        "concept:high-proliferation-rate",
    ):
        assert expected in text


def test_health_command_uses_semantic_triage_for_legacy_topic_refs() -> None:
    text = _read("commands/health.md")

    assert "**looks_like=semantic-triage**" in text
    assert "Do not create `topic:*` stubs as" in text
    assert "Create stub topic entity files" not in text
    assert "Creating topic stubs" not in text
    assert "field-scoped `tag:` ref" in text


def test_tasks_command_documents_flat_ids_parent_and_namespace_refs() -> None:
    text = _read("commands/tasks.md")

    expected_strings = (
        "Task IDs are flat local identifiers in the form `tNNN`",
        "`parent: task:t001`",
        "`natural-systems:task:t335`",
        "Bare `t123` always means a local task",
        "`tasks/archive.md` is for historical task aliases",
    )
    for expected in expected_strings:
        assert expected in text


def test_federation_docs_document_canonical_entity_refs_and_artifact_addresses() -> None:
    text = _read("docs/federation.md")

    expected_strings = (
        "<project-id>:<kind>:<slug>",
        "`cbioportal:question:q014`",
        "`multiple-myeloma:hypothesis:h003`",
        "`cbioportal:topics/clonal-hematopoiesis-contamination` is an artifact address",
        "Two-part entity shorthand such as",
        "`cbioportal:q014`",
        "is legacy and non-canonical",
    )
    for expected in expected_strings:
        assert expected in text


def test_comparison_template_satisfies_validator_sections() -> None:
    """Both comparison template copies must carry every section the validator requires.

    Regression for fb-2026-06-02-002 / fb-2026-06-11-001: the template emitted
    'Current Assessment' while hypothesis_comparisons requires 'Current Verdict'.
    """
    from science_tool.validate.checks.hypothesis_comparisons import _SECTIONS

    for path in ("templates/comparison.md", "science/model/src/science_model/templates/comparison.md"):
        text = _read(path)
        for section in _SECTIONS:
            assert f"## {section}" in text, f"{path} missing required section: {section}"


def test_comparison_template_satisfies_discussion_schema_and_numeric_path() -> None:
    """Comparison docs are discussion entities, so the template must satisfy the
    discussion section schema and use the numeric discussion id/path shape."""
    from science_tool.validate.checks.discussions import _REQUIRED_SECTIONS

    for path in ("templates/comparison.md", "science/model/src/science_model/templates/comparison.md"):
        text = _read(path)
        assert 'id: "discussion:{{NNNN}}-{{slug}}"' in text
        assert 'id: "discussion:{{slug}}"' not in text
        for section in _REQUIRED_SECTIONS:
            assert section in text, f"{path} missing required discussion section: {section}"


def test_compare_hypotheses_command_uses_numeric_discussion_output() -> None:
    text = _read("commands/compare-hypotheses.md")

    assert "Save to `entities/discussions/<NNNN>-comparison-<slug>.md`" in text
    assert 'frontmatter `id: "discussion:<NNNN>-comparison-<slug>"`' in text
    assert "entities/discussions/comparison-<slug>.md" not in text


def test_bias_audit_templates_emit_report_not_task() -> None:
    for path in ("templates/bias-audit.md", "science/model/src/science_model/templates/bias-audit.md"):
        text = _read(path)
        assert 'id: "report:{{NNNN}}-bias-audit-{{slug}}"' in text
        assert 'type: "report"' in text
        assert 'id: "task:{{slug}}"' not in text
        assert 'type: "task"' not in text


def test_pre_registration_templates_include_runnable_now_execution_readiness_gate() -> None:
    for path in (
        "templates/pre-registration.md",
        "science/model/src/science_model/templates/pre-registration.md",
    ):
        text = _read(path)
        assert "Execution-Readiness Gate (runnable-now mode)" in text
        assert "Use in RUNNABLE-NOW mode" in text
        assert "power floor, input QA checks, preprocessing checks" in text
        assert "gate verdict interpretability rather than data availability" in text


def test_pre_registration_templates_include_multi_analysis_registry() -> None:
    for path in (
        "templates/pre-registration.md",
        "science/model/src/science_model/templates/pre-registration.md",
    ):
        text = _read(path)
        assert "Analysis Registry" in text
        assert "one pre-registration covers multiple analyses" in text
        assert "mixed runnable/data-gated statuses" in text
        assert "| Analysis ID | Commitment target | Mode | Status | Gate reference | Verdict policy |" in text
        assert "link to that analysis's Execution-Readiness Gate or Vehicle-Admissibility Gate" in text


def test_pre_registration_templates_include_calibration_gate() -> None:
    for path in (
        "templates/pre-registration.md",
        "science/model/src/science_model/templates/pre-registration.md",
    ):
        text = _read(path)
        assert "Calibration Gate (in-run no-peeking threshold)" in text
        assert "Use when a threshold will be derived inside the run" in text
        assert "marginal distributions or eligibility counts only" in text
        assert "forbid outcome labels, effect estimates, group-contrast results" in text
        assert "| Threshold | Allowed calibration inputs | Forbidden inputs | Lock point | Formula |" in text


def test_big_picture_synthesis_frontmatter_includes_profile_required_title() -> None:
    command = _read("commands/big-picture.md")
    assert (
        "Frontmatter: emit `type: synthesis` + `title: \"Synthesis: <hyp-id>\"` + "
        "`report_kind: hypothesis-synthesis`"
    ) in command
    assert (
        "Frontmatter: emit `type: synthesis` + `title: \"Emergent threads - <project name>\"` + "
        "`report_kind: emergent-threads`"
    ) in command
    assert 'title: "Project synthesis - <project name>"' in command

    for path in ("templates/synthesis.md", "science/model/src/science_model/templates/synthesis.md"):
        text = _read(path)
        assert 'title: "{{title}}"' in text


def test_bias_audit_commit_step_is_conditional() -> None:
    text = _read("commands/bias-audit.md")
    assert "Only commit if the user explicitly requested a commit or the session has commit approval." in text
    assert "Otherwise, report the changed files and leave the workspace uncommitted." in text
    assert 'Commit: `git add -A && git commit -m "doc: bias audit <slug>"`' not in text


def test_sketch_model_documents_existing_inquiry_upgrade() -> None:
    text = _read("commands/sketch-model.md")
    expected_strings = (
        "Existing Inquiry Upgrade",
        "entities/inquiries/<slug>.md",
        "preserve its existing slug and frontmatter",
        "Register the existing inquiry before adding graph nodes or edges",
    )
    for expected in expected_strings:
        assert expected in text


def test_next_steps_declares_recommendation_not_task_queue_boundary() -> None:
    text = _read("commands/next-steps.md")
    normalized = _norm(text)

    assert "A next-steps run produces recommendations, not task records." in normalized
    assert "Do not treat `<meta-home>` files as the durable task queue." in normalized
    assert (
        "Convert recommendations into `science tasks add ...` only after user acceptance."
        in normalized
    )
    assert "Accepted work belongs in `science tasks ...` and `tasks/active.md`." in normalized


def test_sketch_model_uses_source_first_inquiry_authoring() -> None:
    text = _read("commands/sketch-model.md")
    normalized = _norm(text)

    assert "Do not use `science graph add concept` as the durable authoring path." in normalized
    assert "Direct graph mutation writes to `knowledge/graph.trig`" in normalized
    assert "regenerated by `science graph build` from source files" in normalized
    assert "Do not use `science entity create concept` in this workflow" in normalized
    assert "Use a registered source kind, a lightweight `terms.yaml` row, or prose deferral" in normalized
    assert (
        "If no supported durable source kind exists yet, describe the term in the inquiry patch prose"
        in normalized
    )
    assert "boundary roles, flow edges, or unknown markers until a source owner is available" in normalized
    assert "Use the patch source for inquiry-local assumptions and transformations" in normalized
    assert "the inquiry compiler mints those local nodes from the authored patch" in normalized
    assert "```bash\nscience graph add concept" not in text
    assert "```bash\nscience entity create concept" not in text
    assert "science entity create concept " not in text


def test_specify_model_marks_direct_graph_concepts_as_non_durable() -> None:
    text = _read("commands/specify-model.md")
    normalized = _norm(text)

    assert (
        "For inquiry-patch projects, record durable variable refs in `entities/patches/<slug>.md`."
        in normalized
    )
    assert "Make sure those refs resolve through source records or lightweight term rows" in normalized
    assert "Direct `science graph add concept` writes are exploratory and non-durable." in normalized
    assert "They write to `knowledge/graph.trig`, which is regenerated from source files." in normalized
    assert "Do not treat graph-added concepts as owners for variables, treatment/outcome refs, or unknowns." in normalized


def test_add_hypothesis_keeps_cli_creation_before_template_body_editing() -> None:
    text = _read("commands/add-hypothesis.md")
    normalized = _norm(text)

    assert "Create first, then draft." in normalized
    assert (
        "`science hypotheses create` owns ID sequencing, frontmatter, file placement, "
        "and prospective validation."
        in normalized
    )
    assert "Use hypothesis templates only after creation, as body-writing references." in normalized
    assert "Do NOT pre-write the file or hand-pick the ID" in normalized


def test_critique_approach_documents_pre_dag_mode() -> None:
    text = _read("commands/critique-approach.md")
    expected_strings = (
        "Pre-DAG Critique Mode",
        "Markdown-only or sketch-stage inquiry",
        "Validation unavailable",
        "Do not claim formal adjustment-set review",
        "pre-DAG critique",
    )
    for expected in expected_strings:
        assert expected in text
