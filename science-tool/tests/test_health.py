"""Tests for the science-tool health command and its component checks."""

from __future__ import annotations

import json
from pathlib import Path

from science_tool.graph.health import check_dataset_anomalies


def _write_layered_claim_project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: test\n")
    propositions_dir = tmp_path / "specs" / "propositions"
    propositions_dir.mkdir(parents=True)
    (propositions_dir / "p01.md").write_text(
        "\n".join(
            [
                "---",
                'id: "proposition:p01"',
                'type: "proposition"',
                'title: "Causal proposition"',
                'status: "draft"',
                'claim_layer: "causal_effect"',
                "related: []",
                "source_refs: []",
                "rival_model_packet:",
                '  packet_id: "packet:p01"',
                '  target_hypothesis: "hypothesis:h01"',
                'created: "2026-04-15"',
                "---",
                "",
                "A CRISPR perturbation supports this causal interpretation.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (propositions_dir / "p02.md").write_text(
        "\n".join(
            [
                "---",
                'id: "proposition:p02"',
                'type: "proposition"',
                'title: "Mechanistic proposition"',
                'status: "draft"',
                "related: []",
                "source_refs: []",
                'created: "2026-04-15"',
                "---",
                "",
                "PHF19 activates PRC2 through a mechanistic cascade.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return tmp_path


class TestCollectUnresolvedRefs:
    def test_groups_by_target_with_mention_counts(self, tmp_path: Path) -> None:
        from science_tool.graph.health import collect_unresolved_refs

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        # Two hypotheses both reference topic:foo (which doesn't exist)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [topic:foo]\nsource_refs: []\n'
            'created: "2026-04-13"\n---\nBody.\n'
        )
        (spec / "h02.md").write_text(
            '---\nid: "hypothesis:h02"\ntype: "hypothesis"\ntitle: "H2"\n'
            'status: "proposed"\nrelated: [topic:foo, topic:bar]\nsource_refs: []\n'
            'created: "2026-04-13"\n---\nBody.\n'
        )

        unresolved = collect_unresolved_refs(tmp_path)

        # Sorted by mention count desc
        assert unresolved[0]["target"] == "topic:foo"
        assert unresolved[0]["mention_count"] == 2
        assert sorted(unresolved[0]["sources"]) == ["hypothesis:h01", "hypothesis:h02"]
        assert unresolved[1]["target"] == "topic:bar"
        assert unresolved[1]["mention_count"] == 1
        assert unresolved[1]["sources"] == ["hypothesis:h02"]

    def test_meta_refs_not_reported_as_unresolved(self, tmp_path: Path) -> None:
        from science_tool.graph.health import collect_unresolved_refs

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [meta:phase3b]\nsource_refs: []\n'
            'created: "2026-04-13"\n---\nBody.\n'
        )

        unresolved = collect_unresolved_refs(tmp_path)
        assert unresolved == []

    def test_looks_like_heuristic_for_task_ids(self, tmp_path: Path) -> None:
        from science_tool.graph.health import collect_unresolved_refs

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [topic:t143]\nsource_refs: []\n'
            'created: "2026-04-13"\n---\nBody.\n'
        )

        unresolved = collect_unresolved_refs(tmp_path)
        assert unresolved[0]["target"] == "topic:t143"
        assert unresolved[0]["looks_like"] == "task"

    def test_looks_like_classifies_question_and_hypothesis(self, tmp_path: Path) -> None:
        from science_tool.graph.health import collect_unresolved_refs

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [topic:q05-foo, topic:h99-bar, topic:genomics]\n'
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )

        unresolved = collect_unresolved_refs(tmp_path)
        by_target = {row["target"]: row["looks_like"] for row in unresolved}
        assert by_target["topic:q05-foo"] == "question"
        assert by_target["topic:h99-bar"] == "hypothesis"
        assert by_target["topic:genomics"] == "topic"


class TestCollectLingeringTags:
    def test_finds_tags_lines_in_entity_files(self, tmp_path: Path) -> None:
        from science_tool.graph.health import collect_lingering_tags

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\ntags: [legacy-tag]\nrelated: []\n'
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )
        (spec / "h02.md").write_text(  # No tags line
            '---\nid: "hypothesis:h02"\ntype: "hypothesis"\ntitle: "H2"\n'
            'status: "proposed"\nrelated: []\nsource_refs: []\n'
            'created: "2026-04-13"\n---\nBody.\n'
        )

        results = collect_lingering_tags(tmp_path)

        assert len(results) == 1
        assert results[0]["file"].endswith("h01.md")
        assert results[0]["values"] == ["legacy-tag"]

    def test_finds_tags_lines_in_task_files(self, tmp_path: Path) -> None:
        from science_tool.graph.health import collect_lingering_tags

        (tmp_path / "science.yaml").write_text("name: test\n")
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "active.md").write_text(
            "## [t001] Task\n"
            "- type: dev\n"
            "- priority: P1\n"
            "- status: active\n"
            "- tags: [foo, bar]\n"
            "- created: 2026-04-13\n"
            "\nDesc.\n"
        )

        results = collect_lingering_tags(tmp_path)

        assert len(results) == 1
        assert results[0]["file"].endswith("active.md")
        assert results[0]["values"] == ["foo", "bar"]


class TestBuildHealthReport:
    def test_aggregates_all_checks(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\ntags: [legacy]\nrelated: [topic:foo]\n'
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )

        report = build_health_report(tmp_path)

        assert "unresolved_refs" in report
        assert "lingering_tags_lines" in report
        assert "layered_claims" in report
        assert len(report["unresolved_refs"]) >= 1
        assert len(report["lingering_tags_lines"]) >= 1

    def test_empty_project_has_clean_report(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        (tmp_path / "science.yaml").write_text("name: test\n")
        report = build_health_report(tmp_path)

        assert report["unresolved_refs"] == []
        assert report["lingering_tags_lines"] == []
        assert report["layered_claims"]["migration_issues"] == []

    def test_layered_claim_report_surfaces_adoption_gaps_and_rival_model_issues(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        project = _write_layered_claim_project(tmp_path)

        report = build_health_report(project)

        assert report["layered_claims"]["proposition_claim_layer_coverage"] == {
            "numerator": 1,
            "denominator": 2,
            "fraction": 0.5,
        }
        assert report["layered_claims"]["causal_leaning_identification_coverage"] == {
            "numerator": 0,
            "denominator": 2,
            "fraction": 0.0,
        }
        rival_gaps = report["layered_claims"]["rival_model_packets_missing_discriminating_predictions"]
        assert rival_gaps[0]["packet_id"] == "packet:p01"
        migration_issues = report["layered_claims"]["migration_issues"]
        assert any("mechanistic" in " ".join(row["warnings"]).lower() for row in migration_issues)


class TestHealthCLI:
    def test_table_output_default(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [topic:missing]\n'
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )

        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert "topic:missing" in result.output

    def test_json_output(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "specs" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [topic:missing]\n'
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )

        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(tmp_path), "--format", "json"])

        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        assert "unresolved_refs" in report
        assert report["unresolved_refs"][0]["target"] == "topic:missing"

    def test_table_output_includes_layered_claim_sections(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        project = _write_layered_claim_project(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(project)])

        assert result.exit_code == 0, result.output
        assert "Layered-Claim Adoption" in result.output
        assert "packet:p01" in result.output

    def test_clean_project_exits_zero(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n")
        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(tmp_path)])

        assert result.exit_code == 0
        assert "no issues" in result.output.lower() or "clean" in result.output.lower()


def test_health_flags_legacy_task_type_field(tmp_path) -> None:
    from pathlib import Path

    from science_tool.graph.health import collect_legacy_task_type

    project_root = Path(tmp_path)
    (project_root / "tasks").mkdir()
    (project_root / "tasks" / "active.md").write_text(
        "## [t001] Legacy\n- type: research\n- priority: P2\n- status: proposed\n- created: 2026-04-01\n\nBody.\n"
    )
    findings = collect_legacy_task_type(project_root)
    assert len(findings) == 1
    assert findings[0]["task_id"] == "t001"
    assert findings[0]["legacy_type"] == "research"


def test_health_flags_invalid_entity_aspects(tmp_path) -> None:
    from pathlib import Path

    from science_tool.graph.health import collect_invalid_entity_aspects

    project_root = Path(tmp_path)
    (project_root / "doc" / "questions").mkdir(parents=True)
    (project_root / "science.yaml").write_text("name: demo\nprofile: research\naspects: [hypothesis-testing]\n")
    (project_root / "doc" / "questions" / "q01.md").write_text(
        '---\nid: "question:q01"\naspects: ["not-declared"]\n---\nBroken.\n'
    )
    findings = collect_invalid_entity_aspects(project_root)
    assert len(findings) == 1
    assert "not-declared" in findings[0]["message"]


def test_health_flags_legacy_article_prefixes_in_structured_sources(tmp_path) -> None:
    from pathlib import Path

    from science_tool.graph.health import collect_legacy_structured_literature_prefixes

    project_root = Path(tmp_path)
    (project_root / "science.yaml").write_text("name: demo\n")
    sources_dir = project_root / "knowledge" / "sources" / "local"
    sources_dir.mkdir(parents=True)
    (sources_dir / "entities.yaml").write_text(
        "entities:\n- canonical_id: article:Smith2024\n  kind: paper\n  title: Smith\n",
        encoding="utf-8",
    )

    findings = collect_legacy_structured_literature_prefixes(project_root)
    assert len(findings) == 1
    assert findings[0]["source_file"] == "knowledge/sources/local/entities.yaml"
    assert findings[0]["legacy_ref"] == "article:Smith2024"


def test_build_health_report_includes_aspect_findings(tmp_path) -> None:
    from pathlib import Path

    from science_tool.graph.health import build_health_report

    project_root = Path(tmp_path)
    (project_root / "tasks").mkdir()
    (project_root / "tasks" / "active.md").write_text(
        "## [t001] Legacy task\n- type: dev\n- priority: P2\n- status: proposed\n- created: 2026-04-01\n\nBody.\n"
    )
    (project_root / "doc" / "questions").mkdir(parents=True)
    (project_root / "science.yaml").write_text("name: demo\nprofile: research\naspects: [hypothesis-testing]\n")
    (project_root / "doc" / "questions" / "q01.md").write_text(
        '---\nid: "question:q01"\naspects: ["not-declared"]\n---\nBroken.\n'
    )

    report = build_health_report(project_root)
    assert "legacy_task_type" in report
    assert "invalid_entity_aspects" in report
    assert len(report["legacy_task_type"]) == 1
    assert len(report["invalid_entity_aspects"]) == 1


def test_build_health_report_includes_legacy_structured_literature_findings(tmp_path) -> None:
    from pathlib import Path

    from science_tool.graph.health import build_health_report

    project_root = Path(tmp_path)
    (project_root / "science.yaml").write_text("name: demo\n")
    sources_dir = project_root / "knowledge" / "sources" / "local"
    sources_dir.mkdir(parents=True)
    (sources_dir / "entities.yaml").write_text(
        "entities:\n- canonical_id: article:Smith2024\n  kind: paper\n  title: Smith\n",
        encoding="utf-8",
    )

    report = build_health_report(project_root)
    assert "legacy_structured_literature_prefixes" in report
    assert len(report["legacy_structured_literature_prefixes"]) == 1


def test_dataset_anomaly_codes_registered() -> None:
    from science_tool.graph.health import DATASET_ANOMALY_CODES

    expected = {
        "dataset_consumed_but_unverified",
        "dataset_stale_review",
        "dataset_missing_source_url",
        "dataset_cached_field_drift",
        "dataset_invariant_violation",
        "dataset_derived_missing_workflow_run",
        "dataset_derived_asymmetric_edge",
        "dataset_derived_input_chain_broken",
        "dataset_origin_block_mismatch",
        "dataset_verified_but_unstageable",
        "dataset_research_package_asymmetric",
        "data_package_unmigrated",
    }
    assert expected.issubset(set(DATASET_ANOMALY_CODES))


def _write_dataset(p: Path, slug: str, *, origin: str, body: str) -> Path:
    f = p / "doc" / "datasets" / f"{slug}.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        f'---\nid: "dataset:{slug}"\ntype: "dataset"\ntitle: "{slug}"\norigin: "{origin}"\n{body}\n---\n',
        encoding="utf-8",
    )
    return f


def test_external_with_derivation_flagged(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "x",
        origin="external",
        body=(
            'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19"}\n'
            'derivation: {workflow: "workflow:w", workflow_run: "workflow-run:w-r1", git_commit: "a", config_snapshot: "c", produced_at: "t", inputs: []}'
        ),
    )
    issues = check_dataset_anomalies(tmp_path)
    codes = {i["code"] for i in issues}
    assert "dataset_origin_block_mismatch" in codes


def test_derived_with_access_flagged(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "y",
        origin="derived",
        body=(
            'derivation: {workflow: "workflow:w", workflow_run: "workflow-run:w-r1", git_commit: "a", config_snapshot: "c", produced_at: "t", inputs: []}\n'
            'access: {level: "public", verified: true}'
        ),
    )
    issues = check_dataset_anomalies(tmp_path)
    codes = {i["code"] for i in issues}
    assert "dataset_origin_block_mismatch" in codes


def test_external_consumed_unverified_flagged(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "u",
        origin="external",
        body='access: {level: "public", verified: false}\nconsumed_by: ["plan:p1"]',
    )
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_consumed_but_unverified" for i in issues)


def test_external_stale_review_flagged(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "s",
        origin="external",
        body='access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2024-01-01", source_url: "https://x"}',
    )
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_stale_review" for i in issues)


def test_external_verified_no_source_url_flagged(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "n",
        origin="external",
        body='access: {level: "public", verified: true, verification_method: "credential-confirmed", last_reviewed: "2026-04-19"}',
    )
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_missing_source_url" for i in issues)
