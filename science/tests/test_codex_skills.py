from __future__ import annotations

from pathlib import Path

from science_tool.codex_skills import command_to_skill_name, generate_codex_skills

ROOT = Path(__file__).resolve().parents[2]


def _read_skill(name: str) -> str:
    return (ROOT / "codex-skills" / name / "SKILL.md").read_text(encoding="utf-8")


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
    readme_text = (ROOT / "docs" / "README.codex.md").read_text(encoding="utf-8")

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


def test_catalog_datasets_generated_skill_is_layout_v3_aware(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-catalog-datasets"].read_text(encoding="utf-8")

    assert "entities/questions/" in text
    assert "entities/hypotheses/" in text
    assert "legacy specs/research-question.md only if it exists" in text
    assert "legacy specs/scope-boundaries.md only if it exists" in text
    assert "Read `specs/research-question.md` for project context" not in text
    assert "- `specs/research-question.md`" not in text
    assert "- `specs/scope-boundaries.md`" not in text


def test_catalog_datasets_generated_skill_warns_about_legacy_metadata_backfill(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-catalog-datasets"].read_text(encoding="utf-8")

    assert "When connecting or backfilling legacy dataset entities" in text
    assert "do not add `origin: external` by itself" in text
    assert "set `license:` at the same time" in text
    assert "`unknown` is acceptable" in text
    assert "source_class: derived" in text
    assert "dataset_usage" in text
    assert "role: \"upstream\"" in text
    assert "role: \"training\"" in text


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


def test_science_health_mentions_identity_policy_triage() -> None:
    text = _read_skill("science-health")

    assert "docs/process/entity-creation-cookbook.md" in text
    assert "external-id requirement" in text
    assert "prose-only fallback" in text


def test_create_graph_points_to_cookbook_for_new_entities() -> None:
    text = _read_skill("science-create-graph")

    assert "docs/process/entity-creation-cookbook.md" in text
    assert "check shared kinds" in text
    assert "local `concept:*`" in text


def test_update_graph_mentions_fix_on_touch_for_legacy_entities() -> None:
    text = _read_skill("science-update-graph")

    assert "fix-on-touch" in text
    assert "safe rename/xref addition" in text


def test_sync_mentions_scope_and_collision_warnings() -> None:
    text = _read_skill("science-sync")

    assert "`scope: shared`" in text
    assert "`scope: project`" in text
    assert "primary_external_id collision" in text


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
