from __future__ import annotations

import re
from pathlib import Path

import pytest

from science_tool.agent_assets import (
    GenerationResult,
    command_to_skill_name,
    generate_agent_assets,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def generated(tmp_path: Path) -> GenerationResult:
    return generate_agent_assets(
        ROOT,
        tmp_path / "skills",
        tmp_path / "commands",
    )


@pytest.fixture
def skills_root(generated: GenerationResult) -> Path:
    return generated.skill_paths["science-status"].parent.parent


def _generate(tmp_path: Path) -> GenerationResult:
    return generate_agent_assets(
        ROOT,
        tmp_path / "skills",
        tmp_path / "commands",
    )


def _read_skill(skills_root: Path, name: str) -> str:
    return (skills_root / name / "SKILL.md").read_text(encoding="utf-8")


def _slice_between(text: str, start_marker: str, end_marker: str) -> str:
    assert start_marker in text
    assert end_marker in text
    return text.split(start_marker, 1)[1].split(end_marker, 1)[0]


def _norm(text: str) -> str:
    return " ".join(text.split())


def test_command_to_skill_name_uses_science_namespace() -> None:
    assert command_to_skill_name(Path("commands/status.md")) == "science-status"
    assert command_to_skill_name(Path("commands/research-topic.md")) == "science-research-topic"


def test_data_skills_document_configured_data_root() -> None:
    conventions = (ROOT / "skills/data-management/conventions.md").read_text(encoding="utf-8")
    snakemake = (ROOT / "skills/pipelines/snakemake.md").read_text(encoding="utf-8")
    for text in (conventions, snakemake):
        assert "SCIENCE_DATA_ROOT" in text
        assert "data.root" in text
        assert "Never commit files under the resolved data root" in text


def test_command_skills_are_neutral_invocable_and_inline_preamble(
    generated: GenerationResult,
) -> None:
    command_names = {command_to_skill_name(path) for path in sorted((ROOT / "commands").glob("*.md"))}
    for name in sorted(command_names):
        path = generated.skill_paths[name]
        text = path.read_text(encoding="utf-8")
        assert f"name: {name}" in text
        assert "user-invocable: true" in text
        assert "## Science Command Preamble" in text
        assert "Resolve project profile" in text
        assert "Converted from Claude command" not in text
        assert "Science Codex" not in text
        assert "Science Crush" not in text
        assert "Science OpenCode" not in text


def test_command_support_skill_is_non_invocable_and_resource_only(
    generated: GenerationResult,
) -> None:
    support = generated.skill_paths["science-command-preamble"].parent
    text = (support / "SKILL.md").read_text(encoding="utf-8")
    assert "name: science-command-preamble" in text
    assert "loaded by Science command skills" in text
    assert "not invoked directly" in text
    assert "user-invocable" not in text
    assert sorted(path.name for path in (support / "references" / "role-prompts").glob("*.md")) == [
        "discussant.md",
        "research-assistant.md",
    ]
    assert sorted(path.parent.name for path in (support / "references" / "aspects").glob("*/*.md")) == [
        "causal-modeling",
        "computational-analysis",
        "hypothesis-testing",
        "software-development",
    ]


@pytest.mark.parametrize(
    ("skill_name", "resource"),
    (
        ("science-health", "references/docs/user-guide/evidence-lines.md"),
        ("science-create-graph", "references/docs/process/entity-creation-cookbook.md"),
        ("science-research-topic", "references/templates/background-topic.md"),
        ("science-create-project", "references/references/project-structure.md"),
    ),
)
def test_command_resources_are_bundled_inside_their_package(
    generated: GenerationResult,
    skill_name: str,
    resource: str,
) -> None:
    skill_path = generated.skill_paths[skill_name]
    assert (skill_path.parent / resource).is_file()
    assert resource in skill_path.read_text(encoding="utf-8")


def test_command_markdown_links_do_not_escape_their_package(
    generated: GenerationResult,
) -> None:
    command_names = {command_to_skill_name(path) for path in sorted((ROOT / "commands").glob("*.md"))}
    for name in sorted(command_names):
        skill_path = generated.skill_paths[name]
        package_root = skill_path.parent.resolve()
        for markdown in sorted(package_root.rglob("*.md")):
            text = markdown.read_text(encoding="utf-8")
            for raw in re.findall(r"]\(([^)]+)\)", text):
                target = raw.split("#", 1)[0]
                if not target or target.startswith("/") or re.match(r"^[a-z]+:", target):
                    continue
                resolved = (markdown.parent / target).resolve()
                source = markdown.relative_to(package_root)
                assert resolved.is_relative_to(package_root), f"{name}/{source}: {raw}"
                assert resolved.exists(), f"{name}/{source}: {raw}"


@pytest.mark.parametrize(
    ("skill_name", "emitted_dependency", "canonical_reference"),
    (
        (
            "science-plan-analysis",
            "science-study-design",
            "skills/study-design/estimator-certification.md",
        ),
        (
            "science-find-datasets",
            "science-data-management",
            "skills/data-management/",
        ),
        (
            "science-search-literature",
            "science-literature",
            "skills/literature/",
        ),
    ),
)
def test_canonical_skill_references_become_emitted_sibling_skill_loads(
    generated: GenerationResult,
    skill_name: str,
    emitted_dependency: str,
    canonical_reference: str,
) -> None:
    skill_path = generated.skill_paths[skill_name]
    text = skill_path.read_text(encoding="utf-8")
    assert f"`{emitted_dependency}` skill" in text
    assert canonical_reference not in text
    assert not (skill_path.parent / "references" / "skills").exists()


def test_command_methodology_index_reference_is_package_local(
    generated: GenerationResult,
) -> None:
    text = generated.skill_paths["science-plan-analysis"].read_text(encoding="utf-8")
    assert "the `science-command-preamble` skill's `references/methodology-index.md`" in text
    assert "skills/INDEX.md" not in text


@pytest.mark.parametrize(
    ("command_name", "role"),
    (
        ("research-topic", "research-assistant"),
        ("discuss", "discussant"),
    ),
)
def test_command_role_is_resolved_during_generation(
    generated: GenerationResult,
    command_name: str,
    role: str,
) -> None:
    text = generated.skill_paths[f"science-{command_name}"].read_text(encoding="utf-8")
    expected = (
        "2. Load the `science-command-preamble` skill. Use its\n"
        f"   `references/role-prompts/{role}.md` role prompt and its aspect definitions."
    )
    assert expected in text
    assert "role argument" not in text
    assert "role parameter" not in text


def test_command_without_explicit_role_defaults_to_research_assistant(
    generated: GenerationResult,
) -> None:
    text = generated.skill_paths["science-health"].read_text(encoding="utf-8")
    assert (
        "2. Load the `science-command-preamble` skill. Use its\n"
        "   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions." in text
    )


def test_rejects_unsupported_explicit_command_role(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "commands").mkdir(parents=True)
    (repo_root / "skills").mkdir()
    (repo_root / "references").mkdir()
    (repo_root / "aspects").mkdir()
    (repo_root / "skills" / "INDEX.md").write_text("# Skills\n", encoding="utf-8")
    (repo_root / "references" / "command-preamble.md").write_text(
        (ROOT / "references" / "command-preamble.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (repo_root / "commands" / "invalid.md").write_text(
        "\n".join(
            (
                "---",
                "description: Invalid role",
                "---",
                "",
                "# Invalid",
                "",
                "Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `reviewer`).",
                "",
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported Science command role"):
        generate_agent_assets(
            repo_root,
            tmp_path / "skills-output",
            tmp_path / "commands-output",
        )


def test_rejects_invalid_toolkit_root_before_creating_output(tmp_path: Path) -> None:
    skills_output = tmp_path / "skills-output"
    commands_output = tmp_path / "commands-output"

    with pytest.raises(ValueError, match="not a Science toolkit root"):
        generate_agent_assets(tmp_path / "not-science", skills_output, commands_output)

    assert not skills_output.exists()
    assert not commands_output.exists()


def test_rejects_skills_output_inside_canonical_tree(tmp_path: Path) -> None:
    output = ROOT / "skills" / "accidental"
    assert not output.exists()

    with pytest.raises(ValueError, match="generated output inside canonical source tree"):
        generate_agent_assets(ROOT, output, tmp_path / "commands")

    assert not output.exists()


def test_rejects_commands_output_inside_canonical_tree(tmp_path: Path) -> None:
    output = ROOT / "commands" / "accidental"
    assert not output.exists()

    with pytest.raises(ValueError, match="generated output inside canonical source tree"):
        generate_agent_assets(ROOT, tmp_path / "skills", output)

    assert not output.exists()


def test_generate_agent_assets_rewrites_arguments_and_template_paths(
    generated: GenerationResult,
) -> None:
    topic_skill = generated.skill_paths["science-research-topic"]
    text = topic_skill.read_text(encoding="utf-8")

    assert "Write a structured background synthesis on the topic specified by the user." in text
    assert "templates/background-topic.md" in text
    assert ".ai/templates/background-topic.md" in text
    assert "science feedback add" in text
    assert "$ARGUMENTS" not in text


def test_generate_agent_assets_emits_all_commands_and_support(
    generated: GenerationResult,
    skills_root: Path,
) -> None:
    command_count = len(list((ROOT / "commands").glob("*.md")))
    assert len(generated.skill_paths) == command_count + 1
    assert len(list(skills_root.glob("science-*/SKILL.md"))) == command_count + 1
    assert generated.opencode_command_paths == {}


def test_add_theme_skill_uses_schema_driven_entity_creation(skills_root: Path) -> None:
    text = _norm(_read_skill(skills_root, "science-add-theme"))

    assert "Create first, then draft." in text
    assert "science entity sections theme --format json" in text
    assert "theme_kind" in text
    assert "theme_scope" in text
    assert "`science entity create theme` owns ID sequencing, frontmatter, file placement" in text


def test_plan_analysis_generated_skill_mentions_index_and_readiness(
    skills_root: Path,
) -> None:
    text = _read_skill(skills_root, "science-plan-analysis")

    expected_strings = (
        "name: science-plan-analysis",
        "references/methodology-index.md",
        "entities/plans/<NNNN>-<slug>-analysis-plan.md",
        "Readiness Decision",
        "science feedback add",
    )
    for expected in expected_strings:
        assert expected in text


def test_generated_plan_analysis_skill_routes_proteomics_and_sensor_time_series(tmp_path: Path) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-plan-analysis"].read_text(encoding="utf-8")

    expected_strings = (
        "Proteomics, phosphoproteomics, mass spectrometry, peptide intensity, TMT, LFQ",
        "`proteomics-qa`, `study-design-bias-vs-variance-decomposition`, `study-design-sensitivity-arbitration`",
        "Wearable, behavioral, actigraphy, EMA, symptom diary, sensor time series, sleep/activity rhythms, or cross-lag coupling",
        "`statistics-time-series-and-longitudinal-models`, `study-design-bias-vs-variance-decomposition`, `study-design-power-floor-acknowledgement`, and `study-design-sensitivity-arbitration`",
    )
    for expected in expected_strings:
        assert expected in text

    assert "statistics-time-series-and-longitudinal-models` if present" not in text


def test_generated_plan_analysis_skill_routes_network_dyadic_permutation_designs(tmp_path: Path) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-plan-analysis"].read_text(encoding="utf-8")

    expected_strings = (
        "Network/graph edges, dyadic data, edge prediction, node-label permutation, QAP/MRQAP",
        "`study-design-power-floor-acknowledgement`, `study-design-replicate-count-justification`, `study-design-sensitivity-arbitration`",
        "treat dyads as dependent observations",
    )
    for expected in expected_strings:
        assert expected in text


def test_catalog_datasets_generated_skill_is_layout_v3_aware(tmp_path: Path) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-catalog-datasets"].read_text(encoding="utf-8")

    assert "entities/questions/" in text
    assert "entities/hypotheses/" in text
    assert "Read project context from current entity roots" in text
    assert "legacy specs/research-question.md only if it exists" not in text
    assert "legacy specs/scope-boundaries.md only if it exists" not in text
    assert "Read `specs/research-question.md` for project context" not in text
    assert "- `specs/research-question.md`" not in text
    assert "- `specs/scope-boundaries.md`" not in text


def test_catalog_datasets_generated_skill_warns_about_metadata_completion(tmp_path: Path) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-catalog-datasets"].read_text(encoding="utf-8")
    normalized = _norm(text)

    assert "Metadata completion" in text
    assert "When connecting or backfilling legacy dataset entities" not in text
    assert "do not add `origin: external` by itself" in normalized
    assert "set `license:` at the same time" in normalized
    assert "`unknown` is acceptable" in text
    assert "source_class: derived" in text
    assert "dataset_usage" in text
    assert 'role: "upstream"' in text
    assert 'role: "training"' in text


def test_catalog_datasets_generated_skill_documents_dataset_link_helper(tmp_path: Path) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-catalog-datasets"].read_text(encoding="utf-8")

    assert "science dataset reconcile-links --format json" in text
    assert "science dataset reconcile-links --fix" in text
    assert "science dataset link <dataset-ref> <question-or-hypothesis-ref>" in text
    assert "idempotent" in text


def test_find_datasets_skill_routes_durable_records_through_dataset_lifecycle(
    skills_root: Path,
) -> None:
    text = _read_skill(skills_root, "science-find-datasets")

    assert "entities/questions/" in text
    assert "entities/hypotheses/" in text
    assert "legacy specs/research-question.md only if it exists" not in text
    assert "science datasets search" in text
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
    assert "If a needed field is not yet exposed by the CLI" in text
    assert "Direct template authoring is a fallback" not in text
    assert "For each `Use now` or `Evaluate next` dataset, create a dataset note" not in text
    assert "--level <public|controlled|mixed>" not in text
    assert "--method <landing-confirmed|downloaded|manual-review>" not in text
    assert '--source "<landing-page-or-download-url>"' not in text
    assert "--date <YYYY-MM-DD>" not in text


def test_plan_pipeline_skill_uses_current_dataset_verify_access_gate(
    skills_root: Path,
) -> None:
    text = _read_skill(skills_root, "science-plan-pipeline")

    assert "science dataset verify-access <slug>" in text
    assert "current `science dataset verify-access`" in text
    assert "future `science dataset verify`" not in text


def test_generated_plan_pipeline_respects_project_plan_numbering_convention(tmp_path: Path) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-plan-pipeline"].read_text(encoding="utf-8")

    assert (
        "Do not blindly use `YYYY-MM-DD-<slug>` in projects whose `entities/plans/` use numeric `NNNN-` stems" in text
    )
    assert "entities/plans/<NNNN>-<slug>.md" in text


def test_generated_plan_pipeline_keeps_core_decisions_out_of_related_refs(tmp_path: Path) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-plan-pipeline"].read_text(encoding="utf-8")
    normalized = _norm(text)

    assert "Core-log decisions are not graph refs" in text
    assert "`entities/decision/*.md`" in text
    assert (
        "Do not put `decision:<id>` in `related:` for a decision that only exists in `core/decisions.md`" in normalized
    )
    assert "it is not a resolvable entity kind" not in text


def test_generated_task_skills_use_aspects_for_task_creation(tmp_path: Path) -> None:
    generated = _generate(tmp_path).skill_paths
    for skill_name in ("science-tasks", "science-review-tasks"):
        text = generated[skill_name].read_text(encoding="utf-8")

        assert 'tasks add "<title>" --type' not in text
        assert 'tasks add "<title>" --aspects=<aspect>' in text


def test_generated_tasks_skill_allows_task_scoped_aspects_without_project_declaration(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-tasks"].read_text(encoding="utf-8")

    assert "Task-scoped aspects do not need to be declared in `science.yaml`" in text
    assert "project-wide aspect behavior" in text


def test_generated_plan_analysis_skill_reuses_task_scoped_aspects_for_blockers(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-plan-analysis"].read_text(encoding="utf-8")

    assert "Reuse task-scoped aspects" in text
    assert "do not mutate `science.yaml` solely to create blocker tasks" in text


def test_generated_plan_analysis_skill_discovers_legacy_doc_meta_pre_registrations(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-plan-analysis"].read_text(encoding="utf-8")

    assert "Pre-registration discovery" in text
    assert "entities/pre-registrations/" in text
    assert "doc/meta/" not in text
    assert "docs/meta/" not in text
    assert "legacy `specs/` locations only if they exist" not in text
    assert "do not assume absence just because no task mentions one" in text


def test_generated_plan_analysis_skill_requires_per_input_data_profile(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-plan-analysis"].read_text(encoding="utf-8")

    assert "Per-Input Data Profile" in text
    assert "one row per input artifact or dataset" in text
    assert "encoding / file format" in text
    assert "row grain" in text
    assert "join cardinality" in text
    assert "missing-value sentinels" in text
    assert "provenance / source version" in text
    assert "checksum or immutable identifier" in text


def test_generated_plan_analysis_skill_preserves_locked_pre_registration_criteria(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-plan-analysis"].read_text(encoding="utf-8")

    assert "When a Pre-Registration Already Exists" in text
    assert "do **not** re-derive decision" in text
    assert "relitigating a committed criterion set here invites" in text
    assert "HARKing" in text
    assert "treat it as an amendment question rather than a" in text


def test_generated_plan_pipeline_skill_documents_mixed_access_public_slice_gate(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-plan-pipeline"].read_text(encoding="utf-8")

    assert "`access.level: mixed` with public-slice consumption" in text
    assert "PASS/DEFER only for the named public slice" in text
    assert "controlled or commercial siblings remain out of scope" in text
    assert "HALT if the plan would consume any restricted sibling" in text


def test_generated_pre_register_skill_documents_runnable_now_gate(tmp_path: Path) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-pre-register"].read_text(encoding="utf-8")

    assert "Execution-readiness gate" in text
    assert "runnable-now mode" in text
    assert "power floor, input QA, preprocessing checks, and required sensitivity checks" in text
    assert "gate verdict interpretability rather than data availability" in text


def test_generated_pre_register_skill_documents_multi_analysis_registry(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-pre-register"].read_text(encoding="utf-8")

    assert "Analysis Registry" in text
    assert "one pre-registration covers multiple analyses" in text
    assert "mixed runnable/data-gated statuses" in text
    assert "Record each analysis's `mode` (`runnable-now` or `data-gated`)" in text
    assert "link each row to its readiness gate or vehicle-admissibility gate" in text


def test_generated_pre_register_skill_documents_in_run_calibration_gate(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-pre-register"].read_text(encoding="utf-8")

    assert "Calibration Gate" in text
    assert "in-run, no-peeking, marginal-derived threshold" in text
    assert "marginal distributions or eligibility counts only" in text
    assert "forbid outcome labels, effect estimates, group-contrast results" in text
    assert "not a data-gated pre-registration" in text


def test_generated_pre_register_skill_loads_real_artifacts_before_locking_thresholds(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-pre-register"].read_text(encoding="utf-8")

    assert "Feasibility Against Real Input Artifacts" in text
    assert "Before locking any threshold in § 3" in text
    assert "load the actual input artifacts" in text
    assert "Support-set size" in text
    assert "Universe alignment" in text
    assert "underpowered or that the wrong arm was slated as confirmatory" in text
    assert "re-scope, swap which arm is confirmatory/exploratory" in text
    assert "caught pre-data because the artifacts" in text
    assert "were loaded before the criteria were locked" in text


def test_generated_pre_register_skill_rederives_every_referenced_count_from_artifacts(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-pre-register"].read_text(encoding="utf-8")

    assert "Count ledger" in text
    assert "every numeric count referenced anywhere in the pre-registration" in text
    assert "denominators, subgroup counts, exclusion counts, missingness counts" in text
    assert "supporting counts in prose, tables, or caveats" in text
    assert "Do not only verify the headline arm" in text
    assert "re-derived from the loaded artifact" in text


def test_generated_pre_register_skill_documents_derivation_cohort_circularity(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-pre-register"].read_text(encoding="utf-8")
    normalized = _norm(text)

    assert "Derivation-cohort circularity" in text
    assert "training or validation cohort" in normalized
    assert "same scored signature, model, or threshold" in normalized
    assert "in-cohort predictive-vs-prognostic test circular" in normalized
    assert "treat it as exploratory or require an independent validation vehicle" in normalized


def test_generated_interpret_results_skill_clarifies_single_line_authoring_vs_touching(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-interpret-results"].read_text(encoding="utf-8")
    normalized = _norm(text)

    assert "Authoring a new single-line proposition" in text
    assert "Touching an existing proposition" in text
    assert "do not suppress `belief.fragile-single-line`" in normalized
    assert "newly fire only when this run made an existing proposition newly single-line" in normalized


def test_generated_specify_model_skill_documents_proxy_directness_vocabulary(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-specify-model"].read_text(encoding="utf-8")

    assert "`proxy_directness:` must be one of `direct`, `indirect`, or `derived`" in text
    assert "Do not write `proxy`; graph build rejects it." in text
    assert "`indirect` for a measured proxy of the target construct" in text
    assert "`derived` for a computed or model-derived proxy" in text


def test_generated_specify_model_skill_routes_hypotheses_to_proposition_bundles(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-specify-model"].read_text(encoding="utf-8")

    assert "**Hypothesis / epistemic entity with no DAG yet**" in text
    assert "decompose the hypothesis into durable `proposition:` entities" in text
    assert 'link each proposition back to the hypothesis with `related: ["hypothesis:<id>"]`' in text
    assert "add the proposition refs to the hypothesis's Proposition Bundle" in text
    assert "Do not leave the decomposition only as prose inside the hypothesis file." in text


def test_review_pipeline_generated_skill_uses_doc_reviews_for_reports(tmp_path: Path) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-review-pipeline"].read_text(encoding="utf-8")

    assert "doc/reviews/<stem>-pipeline-review.md" in text
    assert "entities/plans/<stem>-review.md" not in text


def test_review_pipeline_skill_documents_data_availability_tightening(tmp_path: Path) -> None:
    generated = _generate(tmp_path).skill_paths
    text = generated["science-review-pipeline"].read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert "locked pre-registration model" in text
    assert "covariates, adjustment variables, strata" in text
    assert "undeclared locked-model requirement" in normalized
    assert "Reference-class input deferral" in text
    assert "LD panels" in text
    assert "follow-on design or staging work package" in text
    assert "checksums or equivalent identity evidence" in text
    assert "does not apply to primary analytic datasets" in normalized


def test_explore_ideas_skill_documents_first_run_friction_guardrails(
    skills_root: Path,
) -> None:
    text = _read_skill(skills_root, "science-explore-ideas")
    normalized = _norm(text)

    assert "no `kind:`/entity frontmatter" in normalized
    assert "prose lint treats that directory as process-output space" in normalized
    assert (
        'Omit unknown identifier fields rather than writing empty placeholders such as `doi: ""` or `doi: null`'
        in normalized
    )
    assert (
        "anchors with no usable `ref`, `doi`, citekey, title, or `openalex_id` are ignored by the resolver"
        in normalized
    )


def test_explore_ideas_skill_documents_multi_lens_convergence_representation(
    skills_root: Path,
) -> None:
    text = _read_skill(skills_root, "science-explore-ideas")
    normalized = _norm(text)

    assert "Convergence and cluster detection" in text
    assert "Convergent lenses are not collapsed to" in text
    assert "one** block carrying multiple `lens_views`" in normalized
    assert "When two lenses independently converge on the **same idea**, emit **one block**" in text
    assert "not one per lens" in normalized
    assert "one `origin_plan.origins` entry per lens" in normalized
    assert "independent: true" in text
    assert "omits the top-level `lens`/`rationale` fields" in normalized


def test_science_health_mentions_identity_policy_triage(skills_root: Path) -> None:
    text = _read_skill(skills_root, "science-health")

    assert "docs/process/entity-creation-cookbook.md" in text
    assert "external-id requirement" in text
    assert "prose-only fallback" in text


def test_science_health_generated_skill_uses_semantic_triage_for_topic_refs(
    skills_root: Path,
) -> None:
    text = _read_skill(skills_root, "science-health")

    assert "**looks_like=semantic-triage**" in text
    assert "Do not create `topic:*` stubs as" in text
    assert "Create stub topic entity files" not in text
    assert "Creating topic stubs" not in text


def test_create_graph_points_to_cookbook_for_new_entities(skills_root: Path) -> None:
    text = _read_skill(skills_root, "science-create-graph")

    assert "docs/process/entity-creation-cookbook.md" in text
    assert "check shared kinds" in text
    assert "prefer the most specific registered kind" in text
    assert 'science entity create concept "<title>"' in text


def test_update_graph_mentions_fix_on_touch_for_non_canonical_entities(
    skills_root: Path,
) -> None:
    text = _read_skill(skills_root, "science-update-graph")

    assert "fix-on-touch" in text
    assert "non-canonical entity IDs" in text
    assert "rename/xref addition needed to move it toward canonical identity" in text


def test_sync_mentions_scope_and_collision_warnings(skills_root: Path) -> None:
    text = _read_skill(skills_root, "science-sync")

    assert "`scope: shared`" in text
    assert "`scope: project`" in text
    assert "primary_external_id collision" in text


def test_next_steps_skill_scans_done_files_for_each_month_in_recent_window(
    skills_root: Path,
) -> None:
    text = _read_skill(skills_root, "science-next-steps")

    assert "derive the recent-progress window first" in text
    assert "scan every `tasks/done/YYYY-MM.md` file whose month intersects that window" in text
    assert "Do not stop at the current month file" in text
    assert "treat those rows as recent progress, not status drift" in text


def test_task_inquiry_skills_reflect_command_boundaries(skills_root: Path) -> None:
    next_steps = _norm(_read_skill(skills_root, "science-next-steps"))
    sketch_model_raw = _read_skill(skills_root, "science-sketch-model")
    sketch_model = _norm(sketch_model_raw)
    specify_model = _norm(_read_skill(skills_root, "science-specify-model"))
    add_hypothesis = _norm(_read_skill(skills_root, "science-add-hypothesis"))

    assert "A next-steps run produces recommendations, not task records." in next_steps
    assert "Convert recommendations into `science tasks add ...` only after user acceptance." in next_steps
    assert "`science graph add concept` is retired" in sketch_model
    assert "use source-authored concept owners or project-local patch prose" in sketch_model
    assert (
        "If no supported durable source kind exists yet, describe the term in the inquiry patch prose" in sketch_model
    )
    assert "defer boundary roles or flow edges until a source owner is available" in sketch_model
    assert "Unknown markers may be used in sketch as temporary uncertainty markers" in sketch_model
    assert "resolve or justify them before moving out of sketch" in sketch_model
    assert "Use the patch source for inquiry-local assumptions and transformations" in sketch_model
    assert "the inquiry compiler mints those local nodes from the authored patch" in sketch_model
    assert "```bash\nscience graph add concept" not in sketch_model_raw
    assert "`science graph add concept` is retired." in specify_model
    assert "For inquiry-patch projects, record durable variable refs in `entities/patches/<slug>.md`." in specify_model
    assert "Create first, then draft." in add_hypothesis
    assert (
        "`science hypotheses create` owns ID sequencing, frontmatter, file placement, "
        "and prospective validation." in add_hypothesis
    )


def test_concept_ownership_skills_reflect_command_boundaries(
    skills_root: Path,
) -> None:
    sketch_model_raw = _read_skill(skills_root, "science-sketch-model")
    sketch_model = _norm(sketch_model_raw)
    specify_model = _norm(_read_skill(skills_root, "science-specify-model"))
    plan_pipeline_raw = _read_skill(skills_root, "science-plan-pipeline")
    plan_pipeline = _norm(plan_pipeline_raw)

    assert "Use the most specific registered source kind available before creating a local concept." in sketch_model
    assert "Use `science entity create concept" in sketch_model
    assert "when the model genuinely needs a reusable project-local concept" in sketch_model
    assert "Keep weak ideas in prose when they do not need graph refs yet." in sketch_model
    assert "```bash\nscience graph add concept" not in sketch_model_raw
    assert "Make sure those refs resolve through source records or entity owners" in specify_model
    assert (
        "Do not treat retired graph-writer output as an owner for variables, treatment/outcome refs, or unknowns."
        in specify_model
    )
    assert "Transformation `validated_by` refs should point to existing validation artifacts" in plan_pipeline
    assert "Do not use `concept:<check>` as a placeholder for a validation record that does not exist." in plan_pipeline
    assert 'validated_by: "<existing-validation-ref>"' in plan_pipeline_raw
    assert 'validated_by: "concept:<check>"' not in plan_pipeline_raw


def test_generated_concept_ownership_skills_reflect_command_boundaries(
    tmp_path: Path,
) -> None:
    generated = _generate(tmp_path).skill_paths
    sketch_model_raw = generated["science-sketch-model"].read_text(encoding="utf-8")
    sketch_model = _norm(sketch_model_raw)
    specify_model = _norm(generated["science-specify-model"].read_text(encoding="utf-8"))
    plan_pipeline_raw = generated["science-plan-pipeline"].read_text(encoding="utf-8")
    plan_pipeline = _norm(plan_pipeline_raw)

    assert "Use the most specific registered source kind available before creating a local concept." in sketch_model
    assert "Use `science entity create concept" in sketch_model
    assert "when the model genuinely needs a reusable project-local concept" in sketch_model
    assert "Keep weak ideas in prose when they do not need graph refs yet." in sketch_model
    assert "```bash\nscience graph add concept" not in sketch_model_raw
    assert "Make sure those refs resolve through source records or entity owners" in specify_model
    assert (
        "Do not treat retired graph-writer output as an owner for variables, treatment/outcome refs, or unknowns."
        in specify_model
    )
    assert "Transformation `validated_by` refs should point to existing validation artifacts" in plan_pipeline
    assert "Do not use `concept:<check>` as a placeholder for a validation record that does not exist." in plan_pipeline
    assert 'validated_by: "<existing-validation-ref>"' in plan_pipeline_raw
    assert 'validated_by: "concept:<check>"' not in plan_pipeline_raw


def test_concept_authoring_skills_use_entity_owners(skills_root: Path) -> None:
    create_graph = _norm(_read_skill(skills_root, "science-create-graph"))
    health = _norm(_read_skill(skills_root, "science-health"))

    assert (
        'Use `science entity create concept "<title>"` when a project-scoped concept needs a durable graph identity'
        in create_graph
    )
    assert 'create a concept entity with `science entity create concept "<title>"`' in health


def test_concept_authoring_generated_skills_use_entity_owners(tmp_path: Path) -> None:
    generated = _generate(tmp_path).skill_paths
    create_graph = _norm(generated["science-create-graph"].read_text(encoding="utf-8"))
    health = _norm(generated["science-health"].read_text(encoding="utf-8"))

    assert (
        'Use `science entity create concept "<title>"` when a project-scoped concept needs a durable graph identity'
        in create_graph
    )
    assert 'create a concept entity with `science entity create concept "<title>"`' in health


# ---------------------------------------------------------------------------
# Smoke tests: generated skills must not inject @core/*.md
# ---------------------------------------------------------------------------

# Phrases that appeared verbatim in the old (pre-Task-2/3) injection guidance.
# Presence of any of these means the generator picked up stale source content.
_INJECTION_PHRASES = (
    "include `@core/overview.md` and `@core/decisions.md` near the top",
    "include @core/overview.md and @core/decisions.md",
)

USER_GUIDE_DOC = "docs/" + "user-guide.md"
PROJECT_ORGANIZATION_DOC = "docs/" + "project-organization-profiles.md"
PROJECT_WORKING_MODEL_DOC = "docs/conventions/" + "project-working-model-" + "h00.md"
PROJECT_WORKING_MODEL_STEM = "project-working-model-" + "h00"
PROPOSITION_MODEL_DOC = "docs/" + "proposition-and-evidence-model.md"
CLAIM_MODEL_DOC = "docs/" + "claim-and-evidence-model.md"


def test_no_generated_skill_has_at_core_injection_guidance(
    skills_root: Path,
) -> None:
    """Generated skills must not instruct agents to insert @core/* includes.

    Prose references to @core/*.md that explain what to *remove* are fine.
    Only positive injection instructions (the old pattern) are forbidden.
    """
    offenders: list[str] = []
    for skill_md in skills_root.rglob("SKILL.md"):
        text = skill_md.read_text(encoding="utf-8")
        if any(phrase in text for phrase in _INJECTION_PHRASES):
            offenders.append(str(skill_md.relative_to(skills_root)))
    assert not offenders, (
        f"Generated command skills must not instruct agents to insert @core/*.md includes. Offenders: {offenders}"
    )


def test_no_generated_skill_references_retired_user_docs(
    skills_root: Path,
) -> None:
    retired = (
        USER_GUIDE_DOC,
        PROJECT_ORGANIZATION_DOC,
        PROJECT_WORKING_MODEL_DOC,
        PROJECT_WORKING_MODEL_STEM,
        PROPOSITION_MODEL_DOC,
        CLAIM_MODEL_DOC,
    )
    offenders: list[str] = []
    for skill_md in skills_root.rglob("SKILL.md"):
        text = skill_md.read_text(encoding="utf-8")
        if any(token in text for token in retired):
            offenders.append(str(skill_md.relative_to(skills_root)))

    assert not offenders, f"Generated command skills reference retired user-guide docs. Offenders: {offenders}"


def test_agents_md_template_has_no_at_core_includes() -> None:
    """The canonical AGENTS.md template must not contain @core/ include directives."""
    template = ROOT / "templates" / "agents-md.md"
    text = template.read_text(encoding="utf-8")
    assert "@core/overview.md" not in text
    assert "@core/decisions.md" not in text


def test_generated_command_skills_embed_cli_compatibility_gate(
    generated: GenerationResult,
) -> None:
    command_names = {command_to_skill_name(path) for path in sorted((ROOT / "commands").glob("*.md"))}
    for name in sorted(command_names):
        path = generated.skill_paths[name]
        text = path.read_text(encoding="utf-8")
        assert "SCIENCE_REQUIRED_VERSION=0.3.0" in text, name
        assert "uv run --frozen science --version" in text, name
        assert "UV_PROJECT=$MAIN" not in text, name
        assert "$MAIN/.venv/bin/science" not in text, name
