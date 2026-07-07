from __future__ import annotations

from pathlib import Path

from science_tool.codex_skills import command_to_skill_name, generate_codex_skills

ROOT = Path(__file__).resolve().parents[2]


def _read_skill(name: str) -> str:
    return (ROOT / "codex-skills" / name / "SKILL.md").read_text(encoding="utf-8")


def _slice_between(text: str, start_marker: str, end_marker: str) -> str:
    assert start_marker in text
    assert end_marker in text
    return text.split(start_marker, 1)[1].split(end_marker, 1)[0]


def _norm(text: str) -> str:
    return " ".join(text.split())


def test_command_to_skill_name_uses_science_namespace() -> None:
    assert command_to_skill_name(Path("commands/status.md")) == "science-status"
    assert command_to_skill_name(Path("commands/research-topic.md")) == "science-research-topic"


def test_generate_codex_skills_rewrites_claude_specific_references(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    status_skill = generated["science-status"]
    text = status_skill.read_text(encoding="utf-8")

    assert "name: science-status" in text
    assert "Converted from Claude command `/science:status`." in text
    assert "## Science Codex Command Preamble" in text
    assert "science-sync" in text
    assert "/science:sync" not in text
    assert "${CLAUDE_PLUGIN_ROOT}" not in text
    assert "If the user explicitly asks to save the output or includes `--save`" in text
    assert "project-local install path: `uv run science <command>`" in text
    assert "`uv run --with <science-plugin-root>/science science <command>`" in text


def test_generate_codex_skills_rewrites_arguments_and_template_paths(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    topic_skill = generated["science-research-topic"]
    text = topic_skill.read_text(encoding="utf-8")

    assert "Write a structured background synthesis on the topic specified by the user." in text
    assert "Follow the Science Codex Command Preamble before executing this skill." in text
    assert "templates/background-topic.md" in text
    assert ".ai/templates/background-topic.md" in text
    assert "science feedback add" in text
    assert "$ARGUMENTS" not in text


def test_generate_codex_skills_emits_all_commands(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)

    command_count = len(list((ROOT / "commands").glob("*.md")))
    assert len(generated) == command_count + 2
    assert len(list(tmp_path.glob("science-*/SKILL.md"))) == command_count + 2


def test_generate_codex_skills_emits_companion_methodology_skills(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)

    research_skill = generated["science-research-methodology"].read_text(encoding="utf-8")
    writing_skill = generated["science-scientific-writing"].read_text(encoding="utf-8")

    assert "name: science-research-methodology" in research_skill
    assert "Adapted from canonical Science skill `skills/research/SKILL.md`." in research_skill
    assert "Core research methodology for scientific investigation." in research_skill
    assert '\\"research methodology.\\"' in research_skill
    assert "name: science-scientific-writing" in writing_skill
    assert "Adapted from canonical Science skill `skills/writing/SKILL.md`." in writing_skill
    assert "scientific-writing" in writing_skill
    assert "../science-research-methodology/SKILL.md" in writing_skill
    assert "../research/SKILL.md" not in writing_skill
    assert "../../skills/statistics/SKILL.md" in writing_skill
    assert "../statistics/SKILL.md" not in writing_skill


def test_generated_command_preamble_references_codex_companion_skills(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-research-papers"].read_text(encoding="utf-8")

    assert "Load the `science-research-methodology` and `science-scientific-writing` Codex skills." in text
    assert "If native skill loading is unavailable, use `codex-skills/INDEX.md`" in text
    assert "Load the `research-methodology` and `scientific-writing` skills." not in text


def test_generate_codex_skills_writes_index(tmp_path: Path) -> None:
    generate_codex_skills(ROOT, tmp_path)
    text = (tmp_path / "INDEX.md").read_text(encoding="utf-8")

    assert "# Science Codex Skills" in text
    assert (
        "| `research-methodology` | `science-research-methodology` | `science-research-methodology/SKILL.md` | `skills/research/SKILL.md` |"
        in text
    )
    assert (
        "| `scientific-writing` | `science-scientific-writing` | `science-scientific-writing/SKILL.md` | `skills/writing/SKILL.md` |"
        in text
    )
    assert "| `status` | `science-status` | `science-status/SKILL.md` | `commands/status.md` |" in text


def test_codex_install_docs_use_codex_home_skills() -> None:
    install_text = (ROOT / "codex-skills" / "INSTALL.codex.md").read_text(encoding="utf-8")
    readme_text = (ROOT / "docs" / "user-guide" / "codex.md").read_text(encoding="utf-8")

    for text in (install_text, readme_text):
        assert "${CODEX_HOME:-$HOME/.codex}/skills" in text
        assert "mkdir -p ~/.agents/skills" not in text


def test_plan_analysis_generated_skill_mentions_index_and_readiness() -> None:
    text = _read_skill("science-plan-analysis")

    expected_strings = (
        "name: science-plan-analysis",
        "skills/INDEX.md",
        "entities/plans/<NNNN>-<slug>-analysis-plan.md",
        "Readiness Decision",
        "science feedback add",
    )
    for expected in expected_strings:
        assert expected in text


def test_generated_plan_analysis_skill_routes_proteomics_and_sensor_time_series(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-plan-analysis"].read_text(encoding="utf-8")

    expected_strings = (
        "Proteomics, phosphoproteomics, mass spectrometry, peptide intensity, TMT, LFQ",
        "`data-proteomics-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration`",
        "Wearable, behavioral, actigraphy, EMA, symptom diary, sensor time series, sleep/activity rhythms, or cross-lag coupling",
        "`statistics-time-series-and-longitudinal-models`, `statistics-bias-vs-variance-decomposition`, `statistics-power-floor-acknowledgement`, and `statistics-sensitivity-arbitration`",
    )
    for expected in expected_strings:
        assert expected in text

    assert "statistics-time-series-and-longitudinal-models` if present" not in text


def test_generated_plan_analysis_skill_routes_network_dyadic_permutation_designs(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-plan-analysis"].read_text(encoding="utf-8")

    expected_strings = (
        "Network/graph edges, dyadic data, edge prediction, node-label permutation, QAP/MRQAP",
        "`statistics-power-floor-acknowledgement`, `statistics-replicate-count-justification`, `statistics-sensitivity-arbitration`",
        "treat dyads as dependent observations",
    )
    for expected in expected_strings:
        assert expected in text


def test_catalog_datasets_generated_skill_is_layout_v3_aware(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
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
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-catalog-datasets"].read_text(encoding="utf-8")
    normalized = _norm(text)

    assert "Metadata completion" in text
    assert "When connecting or backfilling legacy dataset entities" not in text
    assert "do not add `origin: external` by itself" in normalized
    assert "set `license:` at the same time" in normalized
    assert "`unknown` is acceptable" in text
    assert "source_class: derived" in text
    assert "dataset_usage" in text
    assert "role: \"upstream\"" in text
    assert "role: \"training\"" in text


def test_catalog_datasets_generated_skill_documents_dataset_link_helper(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-catalog-datasets"].read_text(encoding="utf-8")

    assert "science dataset reconcile-links --format json" in text
    assert "science dataset reconcile-links --fix" in text
    assert "science dataset link <dataset-ref> <question-or-hypothesis-ref>" in text
    assert "idempotent" in text


def test_committed_find_datasets_skill_routes_durable_records_through_dataset_lifecycle() -> None:
    text = _read_skill("science-find-datasets")

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
    assert "--source-url \"<landing-page-or-download-url>\"" in text
    assert "science dataset link <dataset-ref> <question-or-hypothesis-ref>" in text
    assert "If a needed field is not yet exposed by the CLI" in text
    assert "Direct template authoring is a fallback" not in text
    assert "For each `Use now` or `Evaluate next` dataset, create a dataset note" not in text
    assert "--level <public|controlled|mixed>" not in text
    assert "--method <landing-confirmed|downloaded|manual-review>" not in text
    assert "--source \"<landing-page-or-download-url>\"" not in text
    assert "--date <YYYY-MM-DD>" not in text


def test_committed_plan_pipeline_skill_uses_current_dataset_verify_access_gate() -> None:
    text = _read_skill("science-plan-pipeline")

    assert "science dataset verify-access <slug>" in text
    assert "current `science dataset verify-access`" in text
    assert "future `science dataset verify`" not in text


def test_generated_plan_pipeline_respects_project_plan_numbering_convention(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-plan-pipeline"].read_text(encoding="utf-8")

    assert "Do not blindly use `YYYY-MM-DD-<slug>` in projects whose `entities/plans/` use numeric `NNNN-` stems" in text
    assert "entities/plans/<NNNN>-<slug>.md" in text


def test_generated_task_skills_use_aspects_for_task_creation(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    for skill_name in ("science-tasks", "science-review-tasks"):
        text = generated[skill_name].read_text(encoding="utf-8")

        assert "tasks add \"<title>\" --type" not in text
        assert "tasks add \"<title>\" --aspects=<aspect>" in text


def test_generated_tasks_skill_allows_task_scoped_aspects_without_project_declaration(
    tmp_path: Path,
) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-tasks"].read_text(encoding="utf-8")

    assert "Task-scoped aspects do not need to be declared in `science.yaml`" in text
    assert "project-wide aspect behavior" in text


def test_generated_plan_analysis_skill_reuses_task_scoped_aspects_for_blockers(
    tmp_path: Path,
) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-plan-analysis"].read_text(encoding="utf-8")

    assert "Reuse task-scoped aspects" in text
    assert "do not mutate `science.yaml` solely to create blocker tasks" in text


def test_generated_plan_analysis_skill_discovers_legacy_doc_meta_pre_registrations(
    tmp_path: Path,
) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
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
    generated = generate_codex_skills(ROOT, tmp_path)
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
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-plan-analysis"].read_text(encoding="utf-8")

    assert "When a Pre-Registration Already Exists" in text
    assert "do **not** re-derive decision" in text
    assert "relitigating a committed criterion set here invites" in text
    assert "HARKing" in text
    assert "treat it as an amendment question rather than a" in text


def test_generated_plan_pipeline_skill_documents_mixed_access_public_slice_gate(
    tmp_path: Path,
) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-plan-pipeline"].read_text(encoding="utf-8")

    assert "`access.level: mixed` with public-slice consumption" in text
    assert "PASS/DEFER only for the named public slice" in text
    assert "controlled or commercial siblings remain out of scope" in text
    assert "HALT if the plan would consume any restricted sibling" in text


def test_generated_pre_register_skill_documents_runnable_now_gate(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-pre-register"].read_text(encoding="utf-8")

    assert "Execution-readiness gate" in text
    assert "runnable-now mode" in text
    assert "power floor, input QA, preprocessing checks, and required sensitivity checks" in text
    assert "gate verdict interpretability rather than data availability" in text


def test_generated_pre_register_skill_documents_multi_analysis_registry(
    tmp_path: Path,
) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-pre-register"].read_text(encoding="utf-8")

    assert "Analysis Registry" in text
    assert "one pre-registration covers multiple analyses" in text
    assert "mixed runnable/data-gated statuses" in text
    assert "Record each analysis's `mode` (`runnable-now` or `data-gated`)" in text
    assert "link each row to its readiness gate or vehicle-admissibility gate" in text


def test_generated_pre_register_skill_documents_in_run_calibration_gate(
    tmp_path: Path,
) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-pre-register"].read_text(encoding="utf-8")

    assert "Calibration Gate" in text
    assert "in-run, no-peeking, marginal-derived threshold" in text
    assert "marginal distributions or eligibility counts only" in text
    assert "forbid outcome labels, effect estimates, group-contrast results" in text
    assert "not a data-gated pre-registration" in text


def test_generated_pre_register_skill_loads_real_artifacts_before_locking_thresholds(
    tmp_path: Path,
) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
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
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-pre-register"].read_text(encoding="utf-8")

    assert "Count ledger" in text
    assert "every numeric count referenced anywhere in the pre-registration" in text
    assert "denominators, subgroup counts, exclusion counts, missingness counts" in text
    assert "supporting counts in prose, tables, or caveats" in text
    assert "Do not only verify the headline arm" in text
    assert "re-derived from the loaded artifact" in text


def test_generated_specify_model_skill_documents_proxy_directness_vocabulary(
    tmp_path: Path,
) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-specify-model"].read_text(encoding="utf-8")

    assert "`proxy_directness:` must be one of `direct`, `indirect`, or `derived`" in text
    assert "Do not write `proxy`; graph build rejects it." in text
    assert "`indirect` for a measured proxy of the target construct" in text
    assert "`derived` for a computed or model-derived proxy" in text


def test_generated_specify_model_skill_routes_hypotheses_to_proposition_bundles(
    tmp_path: Path,
) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-specify-model"].read_text(encoding="utf-8")

    assert "**Hypothesis / epistemic entity with no DAG yet**" in text
    assert "decompose the hypothesis into durable `proposition:` entities" in text
    assert "link each proposition back to the hypothesis with `related: [\"hypothesis:<id>\"]`" in text
    assert "add the proposition refs to the hypothesis's Proposition Bundle" in text
    assert "Do not leave the decomposition only as prose inside the hypothesis file." in text


def test_review_pipeline_generated_skill_uses_doc_reviews_for_reports(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-review-pipeline"].read_text(encoding="utf-8")

    assert "doc/reviews/<stem>-pipeline-review.md" in text
    assert "entities/plans/<stem>-review.md" not in text


def test_review_pipeline_skill_documents_data_availability_tightening(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
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


def test_explore_ideas_skill_documents_first_run_friction_guardrails() -> None:
    text = _read_skill("science-explore-ideas")
    normalized = _norm(text)

    assert "no `kind:`/entity frontmatter" in normalized
    assert "prose lint treats that directory as process-output space" in normalized
    assert 'Omit unknown identifier fields rather than writing empty placeholders such as `doi: ""` or `doi: null`' in normalized
    assert "anchors with no usable `ref`, `doi`, citekey, title, or `openalex_id` are ignored by the resolver" in normalized


def test_science_health_mentions_identity_policy_triage() -> None:
    text = _read_skill("science-health")

    assert "docs/process/entity-creation-cookbook.md" in text
    assert "external-id requirement" in text
    assert "prose-only fallback" in text


def test_science_health_generated_skill_uses_semantic_triage_for_topic_refs() -> None:
    text = _read_skill("science-health")

    assert "**looks_like=semantic-triage**" in text
    assert "Do not create `topic:*` stubs as" in text
    assert "Create stub topic entity files" not in text
    assert "Creating topic stubs" not in text


def test_create_graph_points_to_cookbook_for_new_entities() -> None:
    text = _read_skill("science-create-graph")

    assert "docs/process/entity-creation-cookbook.md" in text
    assert "check shared kinds" in text
    assert "prefer the most specific registered kind" in text
    assert 'science entity create concept "<title>"' in text


def test_update_graph_mentions_fix_on_touch_for_non_canonical_entities() -> None:
    text = _read_skill("science-update-graph")

    assert "fix-on-touch" in text
    assert "non-canonical entity IDs" in text
    assert "rename/xref addition needed to move it toward canonical identity" in text


def test_sync_mentions_scope_and_collision_warnings() -> None:
    text = _read_skill("science-sync")

    assert "`scope: shared`" in text
    assert "`scope: project`" in text
    assert "primary_external_id collision" in text


def test_next_steps_skill_scans_done_files_for_each_month_in_recent_window() -> None:
    text = _read_skill("science-next-steps")

    assert "derive the recent-progress window first" in text
    assert "scan every `tasks/done/YYYY-MM.md` file whose month intersects that window" in text
    assert "Do not stop at the current month file" in text
    assert "treat those rows as recent progress, not status drift" in text


def test_task_inquiry_committed_skills_reflect_command_boundaries() -> None:
    next_steps = _norm(_read_skill("science-next-steps"))
    sketch_model_raw = _read_skill("science-sketch-model")
    sketch_model = _norm(sketch_model_raw)
    specify_model = _norm(_read_skill("science-specify-model"))
    add_hypothesis = _norm(_read_skill("science-add-hypothesis"))

    assert "A next-steps run produces recommendations, not task records." in next_steps
    assert (
        "Convert recommendations into `science tasks add ...` only after user acceptance."
        in next_steps
    )
    assert "`science graph add concept` is retired" in sketch_model
    assert "use source-authored concept owners or project-local patch prose" in sketch_model
    assert (
        "If no supported durable source kind exists yet, describe the term in the inquiry patch prose"
        in sketch_model
    )
    assert "defer boundary roles or flow edges until a source owner is available" in sketch_model
    assert "Unknown markers may be used in sketch as temporary uncertainty markers" in sketch_model
    assert "resolve or justify them before moving out of sketch" in sketch_model
    assert "Use the patch source for inquiry-local assumptions and transformations" in sketch_model
    assert "the inquiry compiler mints those local nodes from the authored patch" in sketch_model
    assert "```bash\nscience graph add concept" not in sketch_model_raw
    assert "`science graph add concept` is retired." in specify_model
    assert (
        "For inquiry-patch projects, record durable variable refs in `entities/patches/<slug>.md`."
        in specify_model
    )
    assert "Create first, then draft." in add_hypothesis
    assert (
        "`science hypotheses create` owns ID sequencing, frontmatter, file placement, "
        "and prospective validation."
        in add_hypothesis
    )


def test_concept_ownership_committed_skills_reflect_command_boundaries() -> None:
    sketch_model_raw = _read_skill("science-sketch-model")
    sketch_model = _norm(sketch_model_raw)
    specify_model = _norm(_read_skill("science-specify-model"))
    plan_pipeline_raw = _read_skill("science-plan-pipeline")
    plan_pipeline = _norm(plan_pipeline_raw)

    assert "Use the most specific registered source kind available before creating a local concept." in sketch_model
    assert "Use `science entity create concept" in sketch_model
    assert "when the model genuinely needs a reusable project-local concept" in sketch_model
    assert "Keep weak ideas in prose when they do not need graph refs yet." in sketch_model
    assert "```bash\nscience graph add concept" not in sketch_model_raw
    assert "Make sure those refs resolve through source records or entity owners" in specify_model
    assert "Do not treat retired graph-writer output as an owner for variables, treatment/outcome refs, or unknowns." in specify_model
    assert "Transformation `validated_by` refs should point to existing validation artifacts" in plan_pipeline
    assert "Do not use `concept:<check>` as a placeholder for a validation record that does not exist." in plan_pipeline
    assert 'validated_by: "<existing-validation-ref>"' in plan_pipeline_raw
    assert 'validated_by: "concept:<check>"' not in plan_pipeline_raw


def test_generated_concept_ownership_skills_reflect_command_boundaries(
    tmp_path: Path,
) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
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
    assert "Do not treat retired graph-writer output as an owner for variables, treatment/outcome refs, or unknowns." in specify_model
    assert "Transformation `validated_by` refs should point to existing validation artifacts" in plan_pipeline
    assert "Do not use `concept:<check>` as a placeholder for a validation record that does not exist." in plan_pipeline
    assert 'validated_by: "<existing-validation-ref>"' in plan_pipeline_raw
    assert 'validated_by: "concept:<check>"' not in plan_pipeline_raw


def test_concept_authoring_committed_skills_use_entity_owners() -> None:
    create_graph = _norm(_read_skill("science-create-graph"))
    health = _norm(_read_skill("science-health"))

    assert 'Use `science entity create concept "<title>"` when a project-scoped concept needs a durable graph identity' in create_graph
    assert 'create a concept entity with `science entity create concept "<title>"`' in health


def test_concept_authoring_generated_skills_use_entity_owners(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    create_graph = _norm(generated["science-create-graph"].read_text(encoding="utf-8"))
    health = _norm(generated["science-health"].read_text(encoding="utf-8"))

    assert 'Use `science entity create concept "<title>"` when a project-scoped concept needs a durable graph identity' in create_graph
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

CODEX_SKILLS_ROOT = ROOT / "codex-skills"
USER_GUIDE_DOC = "docs/" + "user-guide.md"
PROJECT_ORGANIZATION_DOC = "docs/" + "project-organization-profiles.md"
PROJECT_WORKING_MODEL_DOC = "docs/conventions/" + "project-working-model-" + "h00.md"
PROJECT_WORKING_MODEL_STEM = "project-working-model-" + "h00"
PROPOSITION_MODEL_DOC = "docs/" + "proposition-and-evidence-model.md"
CLAIM_MODEL_DOC = "docs/" + "claim-and-evidence-model.md"


def test_no_generated_skill_has_at_core_injection_guidance() -> None:
    """Generated skills must not instruct agents to insert @core/* includes.

    Prose references to @core/*.md that explain what to *remove* are fine.
    Only positive injection instructions (the old pattern) are forbidden.
    """
    if not CODEX_SKILLS_ROOT.is_dir():
        return  # Repo checkout without generated artifacts; skip silently.
    offenders: list[str] = []
    for skill_md in CODEX_SKILLS_ROOT.rglob("SKILL.md"):
        text = skill_md.read_text(encoding="utf-8")
        if any(phrase in text for phrase in _INJECTION_PHRASES):
            offenders.append(str(skill_md.relative_to(ROOT)))
    assert not offenders, (
        "Generated codex-skills must not instruct agents to insert @core/*.md includes. "
        "Regenerate via scripts/generate_codex_skills.py after editing commands/. "
        f"Offenders: {offenders}"
    )


def test_no_generated_skill_references_retired_user_docs() -> None:
    retired = (
        USER_GUIDE_DOC,
        PROJECT_ORGANIZATION_DOC,
        PROJECT_WORKING_MODEL_DOC,
        PROJECT_WORKING_MODEL_STEM,
        PROPOSITION_MODEL_DOC,
        CLAIM_MODEL_DOC,
    )
    offenders: list[str] = []
    for skill_md in CODEX_SKILLS_ROOT.rglob("SKILL.md"):
        text = skill_md.read_text(encoding="utf-8")
        if any(token in text for token in retired):
            offenders.append(str(skill_md.relative_to(ROOT)))

    assert not offenders, (
        "Generated codex-skills must be regenerated after user-guide doc migration. "
        f"Offenders: {offenders}"
    )


def test_agents_md_template_has_no_at_core_includes() -> None:
    """The canonical AGENTS.md template must not contain @core/ include directives."""
    template = ROOT / "templates" / "agents-md.md"
    text = template.read_text(encoding="utf-8")
    assert "@core/overview.md" not in text
    assert "@core/decisions.md" not in text
