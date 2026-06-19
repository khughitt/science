"""Tests for the science health command and its component checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from science_tool.graph.health import check_dataset_anomalies


def _write_identity_policy_project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text(
        "name: test\nprofile: research\nprofiles: {local: local}\nontologies: [biology]\n",
        encoding="utf-8",
    )
    genes_dir = tmp_path / "entities" / "genes"
    genes_dir.mkdir(parents=True)
    (genes_dir / "ezh2.md").write_text(
        "\n".join(
            [
                "---",
                'id: "gene:EZH2"',
                'kind: "gene"',
                'title: "EZH2"',
                "---",
                "",
                "Missing identity metadata.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    relations_dir = tmp_path / "knowledge" / "sources" / "local"
    relations_dir.mkdir(parents=True)
    (relations_dir / "entities.yaml").write_text(
        "\n".join(
            [
                "entities:",
                "  - canonical_id: gene:ATP5B",
                "    kind: gene",
                "    title: ATP5B",
                "    primary_external_id:",
                "      source: HGNC",
                "      id: '830'",
                "      curie: HGNC:830",
                "      provenance: manual",
                "    taxon: NCBITaxon:9606",
                "  - canonical_id: gene:ATP5F1B",
                "    kind: gene",
                "    title: ATP5F1B",
                "    primary_external_id:",
                "      source: HGNC",
                "      id: '830'",
                "      curie: HGNC:830",
                "      provenance: manual",
                "    taxon: NCBITaxon:9606",
                "  - canonical_id: concept:aaa-consumer",
                "    kind: concept",
                "    title: Consumer",
                "    related:",
                "      - concept:zzz-old",
                "  - canonical_id: concept:zzz-new",
                "    kind: concept",
                "    title: Replacement",
                "    deprecated_ids:",
                "      - concept:zzz-old",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (relations_dir / "terms.yaml").write_text(
        "\n".join(
            [
                "terms:",
                "  - id: concept:HighProliferationRate",
                "    title: High proliferation rate",
                "    description: Invalid local id casing.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (relations_dir / "relations.yaml").write_text(
        "\n".join(
            [
                "relations:",
                "  - subject: EZH2",
                "    predicate: interacts_with",
                "    object: PRC2",
                '    graph_layer: "graph/knowledge"',
                '    source_path: "knowledge/sources/local/relations.yaml"',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "questions" / "q01.md").write_text(
        "\n".join(
            [
                "---",
                'id: "question:q01"',
                'type: "question"',
                'title: "Question"',
                'related: ["gene:RBL1"]',
                'source_refs: ["gene:RBL1"]',
                "---",
                "",
                "Question body.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return tmp_path


def _write_layered_claim_project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: test\n")
    propositions_dir = tmp_path / "entities" / "propositions"
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
        spec = tmp_path / "entities" / "hypotheses"
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
        spec = tmp_path / "entities" / "hypotheses"
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
        spec = tmp_path / "entities" / "hypotheses"
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
        assert by_target["topic:genomics"] == "semantic-triage"


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
        spec = tmp_path / "entities" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [topic:foo]\n'
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )
        # Lingering-tags is a legacy-cleanup check that still scans doc/specs.
        legacy = tmp_path / "doc" / "hypotheses"
        legacy.mkdir(parents=True)
        (legacy / "h02.md").write_text(
            '---\nid: "hypothesis:h02"\ntype: "hypothesis"\ntitle: "H2"\n'
            'status: "proposed"\ntags: [legacy]\nrelated: []\n'
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
        assert report["agent_context"] == []
        assert report["layered_claims"]["migration_issues"] == []

    def test_build_health_report_flags_agent_context_drift(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
        (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n@core/overview.md\n", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("@core/decisions.md\n\n# Agent guide\n", encoding="utf-8")
        (tmp_path / "core").mkdir()
        (tmp_path / "core" / "overview.md").write_text("\n".join(["# Overview", *["- detail"] * 151]), encoding="utf-8")

        report = build_health_report(tmp_path, checks={"agent_context"})

        codes = {row["code"] for row in report["agent_context"]}
        assert "claude_md_legacy_includes" in codes
        assert "agents_md_legacy_includes" in codes
        assert "overview_too_long" in codes
        assert report["total_issues"] == len(report["agent_context"])

    def test_build_health_report_reuses_loaded_project_sources(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import science_tool.graph.health as health_module

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
        real_load_project_sources = health_module.load_project_sources
        call_count = 0

        def counted_load_project_sources(project_root: Path, **kwargs: object):
            nonlocal call_count
            call_count += 1
            return real_load_project_sources(project_root, **kwargs)

        monkeypatch.setattr(health_module, "load_project_sources", counted_load_project_sources)

        health_module.build_health_report(tmp_path)

        assert call_count == 1

    def test_build_health_report_can_include_timing_metadata(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")

        report = build_health_report(tmp_path, collect_timings=True)

        meta = report["_meta"]
        timings = meta["timings"]
        names = [row["name"] for row in timings]
        assert "load_project_sources" in names
        assert "unresolved_refs" in names
        assert meta["total_duration_seconds"] >= 0
        assert all(row["duration_seconds"] >= 0 for row in timings)

    def test_health_check_registry_drives_timing_rows(self, tmp_path: Path) -> None:
        from science_tool.graph.health import HEALTH_CHECKS, build_health_report

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")

        check_names = [check.name for check in HEALTH_CHECKS]
        report = build_health_report(tmp_path, collect_timings=True)
        timing_names = [row["name"] for row in report["_meta"]["timings"]]

        assert len(check_names) == len(set(check_names))
        assert timing_names == ["load_project_sources", *check_names]

    def test_build_health_report_can_run_only_named_checks(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
        doc = tmp_path / "entities" / "questions"
        doc.mkdir(parents=True)
        (doc / "q01.md").write_text(
            "---\n"
            'id: "question:q01"\n'
            'type: "question"\n'
            'title: "Q1"\n'
            'status: "open"\n'
            'related: ["gadget:missing", "gizmo:d1"]\n'
            "---\n"
            "Body.\n",
            encoding="utf-8",
        )

        report = build_health_report(tmp_path, checks={"unregistered_ref_kinds"}, collect_timings=True)

        assert report["unregistered_ref_kinds"][0]["kind"] == "gadget"
        assert report["unresolved_refs"] == []
        assert report["_meta"]["timings"][1:] == [
            {
                "name": "unregistered_ref_kinds",
                "duration_seconds": report["_meta"]["timings"][1]["duration_seconds"],
            }
        ]

    def test_build_health_report_validate_check_surfaces_runner_findings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from science_tool.graph.health import build_health_report
        from science_tool.validate.result import Result, Severity
        from science_tool.validate.runner import RunResult
        import science_tool.validate.runner as validate_runner

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")

        def fake_run(project_root: Path, *, strict: bool, verbose: bool, enable_python_sidecar: bool) -> RunResult:
            assert project_root == tmp_path.resolve()
            assert strict is False
            assert verbose is False
            assert enable_python_sidecar is False
            return RunResult(
                results=[
                    Result(
                        Severity.ERROR,
                        Path("science.yaml"),
                        1,
                        "manifest is broken",
                        "manifest",
                        "task:t001",
                    ),
                    Result(Severity.WARN, Path("doc/q.md"), None, "doc warning", "document_structure", None),
                    Result(Severity.INFO, None, None, "advisory", "notes", None),
                ],
                errors=1,
                warnings=1,
                infos=1,
            )

        monkeypatch.setattr(validate_runner, "run", fake_run)

        report = build_health_report(tmp_path, checks={"validate"})

        assert report["validation"] == [
            {
                "severity": "error",
                "path": "science.yaml",
                "line": 1,
                "message": "manifest is broken",
                "rule": "manifest",
                "task": "task:t001",
            },
            {
                "severity": "warning",
                "path": "doc/q.md",
                "line": None,
                "message": "doc warning",
                "rule": "document_structure",
                "task": None,
            },
        ]
        assert report["total_issues"] == 2

    def test_build_health_report_validate_check_disables_legacy_sidecar_subprocess(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from science_tool.graph.health import build_health_report
        import subprocess

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
        sidecar = tmp_path / "validate.local.sh"
        sidecar.write_text("#!/usr/bin/env bash\necho sidecar >&2\n", encoding="utf-8")
        sidecar.chmod(0o755)

        def fail_subprocess_run(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("science health validation must not run legacy sidecar subprocesses")

        monkeypatch.setattr(subprocess, "run", fail_subprocess_run)

        report = build_health_report(tmp_path, checks={"validate"})

        assert all("sidecar" not in finding["message"] for finding in report["validation"])

    def test_build_health_report_validate_check_skips_registered_post_hooks(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report
        from science_tool.validate import ValidateContext, hook
        from science_tool.validate.runner import clear_hooks_for_tests

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
        fired: list[str] = []

        @hook("post_validation")
        def post(ctx: ValidateContext) -> list[object]:
            fired.append("post")
            raise RuntimeError("health should not run validation hooks")

        try:
            build_health_report(tmp_path, checks={"validate"})
        finally:
            clear_hooks_for_tests()

        assert fired == []

    def test_build_health_report_can_skip_named_checks(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
        doc = tmp_path / "doc" / "questions"
        doc.mkdir(parents=True)
        (doc / "q01.md").write_text(
            "---\n"
            'id: "question:q01"\n'
            'type: "question"\n'
            'title: "Q1"\n'
            'status: "open"\n'
            'related: ["decision:d1"]\n'
            "---\n"
            "Body.\n",
            encoding="utf-8",
        )

        report = build_health_report(tmp_path, skip_checks={"unregistered_ref_kinds"}, collect_timings=True)

        assert report["unregistered_ref_kinds"] == []
        assert "unregistered_ref_kinds" not in [row["name"] for row in report["_meta"]["timings"]]

    def test_fast_health_report_skips_source_required_checks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import science_tool.graph.health as health_module

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")

        def fail_load_project_sources(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("fast health should not load project sources")

        monkeypatch.setattr(health_module, "load_project_sources", fail_load_project_sources)

        report = health_module.build_health_report(tmp_path, fast=True, collect_timings=True)

        timing_names = [row["name"] for row in report["_meta"]["timings"]]
        assert "load_project_sources" not in timing_names
        assert "unregistered_ref_kinds" not in timing_names
        assert "archive_lag" in timing_names
        assert report["unregistered_ref_kinds"] == []

    def test_reports_unregistered_reference_kinds_in_identity_fields(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
        doc = tmp_path / "entities" / "questions"
        doc.mkdir(parents=True)
        (doc / "q01.md").write_text(
            "---\n"
            'id: "question:q01"\n'
            'type: "question"\n'
            'title: "Q1"\n'
            'status: "open"\n'
            'related: ["gadget:d1", "hypothesis:h01"]\n'
            'commits_to: ["latent:l1"]\n'
            'source_refs: ["go:0008150"]\n'
            "---\n"
            "Body.\n",
            encoding="utf-8",
        )

        report = build_health_report(tmp_path)

        assert report["unregistered_ref_kinds"] == [
            {
                "kind": "gadget",
                "field": "related",
                "mention_count": 1,
                "refs": ["gadget:d1"],
                "sources": ["entities/questions/q01.md"],
            },
            {
                "kind": "latent",
                "field": "commits_to",
                "mention_count": 1,
                "refs": ["latent:l1"],
                "sources": ["entities/questions/q01.md"],
            },
        ]
        assert any(row["target"] == "hypothesis:h01" for row in report["unresolved_refs"])
        assert report["total_issues"] >= 2

    def test_bibliography_refs_are_not_unregistered_ref_kinds(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
        doc = tmp_path / "doc" / "questions"
        doc.mkdir(parents=True)
        (doc / "q01.md").write_text(
            "---\n"
            'id: "question:q01"\n'
            'type: "question"\n'
            'title: "Q1"\n'
            'status: "open"\n'
            'source_refs: ["cite:Smith2024"]\n'
            "---\n"
            "Body.\n",
            encoding="utf-8",
        )

        report = build_health_report(tmp_path, checks={"unregistered_ref_kinds", "unresolved_refs"})

        assert report["unregistered_ref_kinds"] == []
        assert report["unresolved_refs"] == []

    def test_includes_identity_policy_section(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        project = _write_identity_policy_project(tmp_path)

        report = build_health_report(project)

        assert "identity_policy" in report
        codes = {row["check"] for row in report["identity_policy"]}
        assert "missing_primary_external_id" in codes
        assert "primary_external_id_collision" in codes
        assert "missing_taxon" in codes
        assert "deprecated_id_inbound_ref" in codes
        assert "relation_endpoint_disambiguation" in codes
        assert "invalid_local_id_syntax" in codes
        assert any(
            row["check"] == "invalid_local_id_syntax" and row["source_file"] == "knowledge/sources/local/terms.yaml"
            for row in report["identity_policy"]
        )

    def test_deprecated_id_inbound_ref_is_order_independent(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        project = _write_identity_policy_project(tmp_path)

        report = build_health_report(project)

        rows = [row for row in report["identity_policy"] if row["check"] == "deprecated_id_inbound_ref"]
        assert rows
        assert any(row["entity_id"] == "concept:aaa-consumer" for row in rows)

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

    def test_archive_lag_zero_when_active_md_missing(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        (tmp_path / "science.yaml").write_text("name: test\n")
        report = build_health_report(tmp_path)
        assert report["archive_lag"] == {
            "done_in_active": 0,
            "retired_in_active": 0,
            "missing_completed": 0,
        }

    def test_archive_lag_counts_done_and_retired(self, tmp_path: Path) -> None:
        from science_tool.graph.health import build_health_report

        (tmp_path / "science.yaml").write_text("name: test\n")
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "active.md").write_text(
            """\
## [t001] Done task
- priority: P1
- status: done
- created: 2026-03-01
- completed: 2026-03-15

Done.

## [t002] Retired task
- priority: P2
- status: retired
- created: 2026-03-20
- completed: 2026-04-02

Retired.

## [t003] Proposed task
- priority: P3
- status: proposed
- created: 2026-04-10

Proposed.
"""
        )
        report = build_health_report(tmp_path)
        assert report["archive_lag"] == {
            "done_in_active": 1,
            "retired_in_active": 1,
            "missing_completed": 0,
        }


class TestHealthCLI:
    def test_table_output_default(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "entities" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [topic:missing, gizmo:d1]\n'
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )

        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert "topic:missing" in result.output
        assert "Unregistered reference kinds" in result.output
        assert "gizmo" in result.output

    def test_json_output(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec = tmp_path / "entities" / "hypotheses"
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

    def test_json_output_with_timings_includes_meta(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(tmp_path), "--format", "json", "--timings"])

        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        assert report["_meta"]["total_duration_seconds"] >= 0
        assert any(row["name"] == "load_project_sources" for row in report["_meta"]["timings"])

    def test_table_output_with_timings_writes_stderr(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
        spec = tmp_path / "entities" / "hypotheses"
        spec.mkdir(parents=True)
        (spec / "h01.md").write_text(
            '---\nid: "hypothesis:h01"\ntype: "hypothesis"\ntitle: "H1"\n'
            'status: "proposed"\nrelated: [topic:missing]\n'
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n',
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(tmp_path), "--timings"])

        assert result.exit_code == 0, result.output
        assert "topic:missing" in result.output
        assert "health timings" in result.stderr.lower()
        assert "load_project_sources" in result.stderr

    def test_json_output_can_run_only_named_health_checks(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
        doc = tmp_path / "entities" / "questions"
        doc.mkdir(parents=True)
        (doc / "q01.md").write_text(
            "---\n"
            'id: "question:q01"\n'
            'type: "question"\n'
            'title: "Q1"\n'
            'status: "open"\n'
            'related: ["gadget:missing", "gizmo:d1"]\n'
            "---\n"
            "Body.\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "health",
                "--project-root",
                str(tmp_path),
                "--format",
                "json",
                "--timings",
                "--check",
                "unregistered_ref_kinds",
            ],
        )

        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        assert report["unregistered_ref_kinds"][0]["kind"] == "gadget"
        assert report["unresolved_refs"] == []
        assert [row["name"] for row in report["_meta"]["timings"]] == [
            "load_project_sources",
            "unregistered_ref_kinds",
        ]

    def test_json_output_validate_check_uses_runner_without_subprocess(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main
        from science_tool.validate.result import Result, Severity
        from science_tool.validate.runner import RunResult
        import science_tool.validate.runner as validate_runner
        import subprocess

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
        calls: list[Path] = []

        def fake_run(project_root: Path, *, strict: bool, verbose: bool, enable_python_sidecar: bool) -> RunResult:
            calls.append(project_root)
            assert enable_python_sidecar is False
            return RunResult(
                results=[
                    Result(Severity.WARN, Path("science.yaml"), 2, "strictness warning", "manifest", None),
                    Result(Severity.INFO, None, None, "info only", "notes", None),
                ],
                errors=0,
                warnings=1,
                infos=1,
            )

        def fail_subprocess_run(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("science health --check validate must not call subprocess.run")

        monkeypatch.setattr(validate_runner, "run", fake_run)
        monkeypatch.setattr(subprocess, "run", fail_subprocess_run)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["health", "--project-root", str(tmp_path), "--format", "json", "--check", "validate"],
        )

        assert result.exit_code == 0, result.output
        assert calls == [tmp_path.resolve()]
        report = json.loads(result.output)
        assert report["validation"] == [
            {
                "severity": "warning",
                "path": "science.yaml",
                "line": 2,
                "message": "strictness warning",
                "rule": "manifest",
                "task": None,
            }
        ]
        assert report["total_issues"] == 1

    def test_json_output_validate_check_reports_context_errors(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["health", "--project-root", str(tmp_path), "--format", "json", "--check", "validate"],
        )

        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        assert report["validation"] == [
            {
                "severity": "error",
                "path": None,
                "line": None,
                "message": f"science.yaml not found at {tmp_path.resolve() / 'science.yaml'}",
                "rule": "validate.context",
                "task": None,
            }
        ]
        assert report["total_issues"] == 1

    def test_table_output_validate_check_includes_validation_section(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main
        from science_tool.validate.result import Result, Severity
        from science_tool.validate.runner import RunResult
        import science_tool.validate.runner as validate_runner

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")

        def fake_run(project_root: Path, *, strict: bool, verbose: bool, enable_python_sidecar: bool) -> RunResult:
            assert enable_python_sidecar is False
            return RunResult(
                results=[
                    Result(
                        Severity.ERROR,
                        Path("science.yaml"),
                        1,
                        "manifest is broken",
                        "manifest",
                        "task:t042",
                    ),
                ],
                errors=1,
                warnings=0,
                infos=0,
            )

        monkeypatch.setattr(validate_runner, "run", fake_run)

        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(tmp_path), "--check", "validate"])

        assert result.exit_code == 0, result.output
        assert "Validation" in result.output
        assert "science.yaml" in result.output
        assert "manifest" in result.output
        assert "manifest is broken" in result.output
        assert "task:t042" in result.output

    def test_json_output_rejects_unknown_health_check(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(tmp_path), "--check", "not_a_check"])

        assert result.exit_code != 0
        assert "unknown health check" in result.output.lower()

    def test_json_output_fast_skips_source_required_health_checks(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        import science_tool.graph.health as health_module
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")

        def fail_load_project_sources(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("--fast should not load project sources")

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(health_module, "load_project_sources", fail_load_project_sources)
        try:
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["health", "--project-root", str(tmp_path), "--format", "json", "--timings", "--fast"],
            )
        finally:
            monkeypatch.undo()

        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        timing_names = [row["name"] for row in report["_meta"]["timings"]]
        assert "load_project_sources" not in timing_names
        assert "unregistered_ref_kinds" not in timing_names
        assert "archive_lag" in timing_names

    def test_fast_rejects_explicit_check_selection(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["health", "--project-root", str(tmp_path), "--fast", "--check", "archive_lag"],
        )

        assert result.exit_code != 0
        assert "cannot combine --fast and --check" in result.output.lower()

    def test_list_checks_table_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from click.testing import CliRunner
        import science_tool.graph.health as health_module
        from science_tool.cli import main

        def fail_build_report(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("--list-checks should not build a health report")

        monkeypatch.setattr(health_module, "build_health_report", fail_build_report)

        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(tmp_path), "--list-checks"])

        assert result.exit_code == 0, result.output
        assert "Health checks" in result.output
        assert "unregistered_ref_kinds" in result.output
        assert "Requires sources" in result.output

    def test_list_checks_json_output(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["health", "--project-root", str(tmp_path), "--format", "json", "--list-checks"],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        first = payload["checks"][0]
        assert set(first) == {"name", "description", "requires_sources"}
        assert any(row["name"] == "unregistered_ref_kinds" for row in payload["checks"])

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
        from science_tool.project_artifacts import canonical_path

        (tmp_path / "science.yaml").write_text("name: test\n")
        # Tooling scaffold required for a "clean" project.
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "t"\nversion = "0.0"\n[dependency-groups]\ndev = ["science"]\n'
        )
        (tmp_path / ".env").write_text("SCIENCE_TOOL_PATH=/dev/null\n")
        # Install canonical managed artifacts so the project is genuinely clean.
        target = tmp_path / "validate.sh"
        target.write_bytes(canonical_path("validate.sh").read_bytes())
        target.chmod(0o755)
        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(tmp_path), "--skip", "validate"])

        assert result.exit_code == 0
        assert "no issues" in result.output.lower() or "clean" in result.output.lower()

    def test_table_output_includes_identity_policy_section(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        project = _write_identity_policy_project(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(project)])

        assert result.exit_code == 0, result.output
        assert "Identity Policy" in result.output

    def test_table_output_includes_entity_identity_section(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
        doc = tmp_path / "entities"
        doc.mkdir(parents=True)
        (doc / "summary.md").write_text("This cites [[h999]] in prose.\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(tmp_path), "--check", "entity_identity"])

        assert result.exit_code == 0, result.output
        assert "Project is clean" not in result.output
        assert "Entity Identity" in result.output
        assert "unresolved-prose-reference" in result.output
        assert "h999" in result.output

    def test_json_output_includes_identity_policy_section(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from science_tool.cli import main

        project = _write_identity_policy_project(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["health", "--project-root", str(project), "--format", "json"])

        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        assert "identity_policy" in report
        assert any(row["check"] == "missing_primary_external_id" for row in report["identity_policy"])


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


def _write_workflow_run(p: Path, slug: str, *, produces: list[str], inputs: list[str]) -> None:
    f = p / "doc" / "workflow-runs" / f"{slug}.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        f'---\nid: "workflow-run:{slug}"\ntype: "workflow-run"\ntitle: "{slug}"\n'
        f'workflow: "workflow:wf"\nproduces: {produces}\ninputs: {inputs}\n---\n',
        encoding="utf-8",
    )


def _derived_dataset_body(workflow_run: str, inputs: list[str]) -> str:
    inp = "[" + ", ".join(f'"{i}"' for i in inputs) + "]"
    return (
        "derivation:\n"
        '  workflow: "workflow:wf"\n'
        f'  workflow_run: "{workflow_run}"\n'
        '  git_commit: "a"\n'
        '  config_snapshot: "c"\n'
        '  produced_at: "2026-04-19T00:00:00Z"\n'
        f"  inputs: {inp}"
    )


def test_derived_missing_workflow_run_flagged(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "d1", origin="derived", body=_derived_dataset_body("workflow-run:does-not-exist", []))
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_derived_missing_workflow_run" for i in issues)


def test_derived_asymmetric_edge_flagged(tmp_path: Path) -> None:
    _write_workflow_run(tmp_path, "w-r1", produces=[], inputs=[])  # missing dataset:d2 in produces
    _write_dataset(tmp_path, "d2", origin="derived", body=_derived_dataset_body("workflow-run:w-r1", []))
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_derived_asymmetric_edge" for i in issues)


def test_derived_symmetric_edge_no_flag(tmp_path: Path) -> None:
    _write_workflow_run(tmp_path, "w-r2", produces=["dataset:d3"], inputs=[])
    _write_dataset(tmp_path, "d3", origin="derived", body=_derived_dataset_body("workflow-run:w-r2", []))
    issues = check_dataset_anomalies(tmp_path)
    assert not any(
        i["code"] in {"dataset_derived_missing_workflow_run", "dataset_derived_asymmetric_edge"} for i in issues
    )


# ---------------------------------------------------------------------------
# Task 6.5: dataset_derived_input_chain_broken (cycle-safe transitive walk)
# ---------------------------------------------------------------------------


def test_derived_input_chain_unverified_external_flagged(tmp_path: Path) -> None:
    _write_dataset(tmp_path, "u_ext", origin="external", body='access: {level: "public", verified: false}')
    _write_workflow_run(tmp_path, "w-r3", produces=["dataset:d4"], inputs=["dataset:u_ext"])
    _write_dataset(tmp_path, "d4", origin="derived", body=_derived_dataset_body("workflow-run:w-r3", ["dataset:u_ext"]))
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_derived_input_chain_broken" for i in issues)


def test_derived_cycle_detected(tmp_path: Path) -> None:
    _write_workflow_run(tmp_path, "w-r4", produces=["dataset:d5"], inputs=["dataset:d6"])
    _write_workflow_run(tmp_path, "w-r5", produces=["dataset:d6"], inputs=["dataset:d5"])
    _write_dataset(tmp_path, "d5", origin="derived", body=_derived_dataset_body("workflow-run:w-r4", ["dataset:d6"]))
    _write_dataset(tmp_path, "d6", origin="derived", body=_derived_dataset_body("workflow-run:w-r5", ["dataset:d5"]))
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_derived_input_chain_broken" for i in issues)


def test_derived_shared_upstream_not_false_cycle(tmp_path: Path) -> None:
    """Two derived datasets share the same upstream — must NOT be reported as a cycle."""
    _write_dataset(
        tmp_path,
        "shared_up",
        origin="external",
        body='access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}',
    )
    _write_workflow_run(tmp_path, "w-r-a", produces=["dataset:branch_a"], inputs=["dataset:shared_up"])
    _write_workflow_run(tmp_path, "w-r-b", produces=["dataset:branch_b"], inputs=["dataset:shared_up"])
    _write_dataset(
        tmp_path, "branch_a", origin="derived", body=_derived_dataset_body("workflow-run:w-r-a", ["dataset:shared_up"])
    )
    _write_dataset(
        tmp_path, "branch_b", origin="derived", body=_derived_dataset_body("workflow-run:w-r-b", ["dataset:shared_up"])
    )
    _write_workflow_run(
        tmp_path, "w-r-merge", produces=["dataset:merged"], inputs=["dataset:branch_a", "dataset:branch_b"]
    )
    _write_dataset(
        tmp_path,
        "merged",
        origin="derived",
        body=_derived_dataset_body("workflow-run:w-r-merge", ["dataset:branch_a", "dataset:branch_b"]),
    )
    issues = check_dataset_anomalies(tmp_path)
    chain_issues = [i for i in issues if i["code"] == "dataset_derived_input_chain_broken"]
    assert chain_issues == [], f"shared upstream wrongly flagged as cycle: {chain_issues}"


# ---------------------------------------------------------------------------
# Task 6.6: dataset_verified_but_unstageable
# ---------------------------------------------------------------------------


def test_verified_no_datapackage_no_localpath_flagged(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "us",
        origin="external",
        body='access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}',
    )
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_verified_but_unstageable" for i in issues)


def test_verified_with_local_path_no_flag(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "ls",
        origin="external",
        body='local_path: "data/ls/file.csv"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}',
    )
    (tmp_path / "data" / "ls").mkdir(parents=True)
    (tmp_path / "data" / "ls" / "file.csv").write_text("col\n", encoding="utf-8")
    issues = check_dataset_anomalies(tmp_path)
    assert not any(i["code"] == "dataset_verified_but_unstageable" for i in issues)


def test_verified_unstageable_suppressed_for_track_tier(tmp_path: Path) -> None:
    # tier: track / evaluate-next are not-yet-staged triage tiers, where
    # "verified" means "confirmed reachable", not "staged" — must not warn.
    _write_dataset(
        tmp_path,
        "trk",
        origin="external",
        body='tier: "track"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}',
    )
    issues = check_dataset_anomalies(tmp_path)
    assert not any(i["code"] == "dataset_verified_but_unstageable" for i in issues)


def test_verified_unstageable_still_flags_use_now_tier(tmp_path: Path) -> None:
    # use-now is a staging-intent tier; verified-but-unstageable is still a real issue.
    _write_dataset(
        tmp_path,
        "un",
        origin="external",
        body='tier: "use-now"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}',
    )
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_verified_but_unstageable" for i in issues)


# ---------------------------------------------------------------------------
# Task 6.7: dataset_research_package_asymmetric (#11)
# ---------------------------------------------------------------------------


def _write_research_package(p: Path, slug: str, *, displays: list[str]) -> None:
    f = p / "research" / "packages" / "lens" / slug / "research-package.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        f'---\nid: "research-package:{slug}"\ntype: "research-package"\ntitle: "{slug}"\ndisplays: {displays}\n---\n',
        encoding="utf-8",
    )


def test_rp_displays_dataset_missing_consumed_by_flagged(tmp_path: Path) -> None:
    _write_research_package(tmp_path, "rp1", displays=["dataset:dr1"])
    _write_workflow_run(tmp_path, "w-r6", produces=["dataset:dr1"], inputs=[])
    _write_dataset(tmp_path, "dr1", origin="derived", body=_derived_dataset_body("workflow-run:w-r6", []))
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_research_package_asymmetric" for i in issues)


def test_dataset_consumed_by_rp_missing_displays_flagged(tmp_path: Path) -> None:
    _write_research_package(tmp_path, "rp2", displays=[])
    _write_workflow_run(tmp_path, "w-r7", produces=["dataset:dr2"], inputs=[])
    body = _derived_dataset_body("workflow-run:w-r7", []) + '\nconsumed_by: ["research-package:rp2"]'
    _write_dataset(tmp_path, "dr2", origin="derived", body=body)
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_research_package_asymmetric" for i in issues)


# ---------------------------------------------------------------------------
# Task 6.8: data_package_unmigrated (strict mode)
# ---------------------------------------------------------------------------


def test_data_package_without_superseded_status_flagged(tmp_path: Path) -> None:
    f = tmp_path / "doc" / "data-packages" / "old.md"
    f.parent.mkdir(parents=True)
    f.write_text(
        '---\nid: "data-package:old"\ntype: "data-package"\ntitle: "Legacy"\nstatus: "active"\n---\n',
        encoding="utf-8",
    )
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "data_package_unmigrated" for i in issues)


def test_superseded_data_package_no_flag(tmp_path: Path) -> None:
    f = tmp_path / "doc" / "data-packages" / "migrated.md"
    f.parent.mkdir(parents=True)
    f.write_text(
        '---\nid: "data-package:migrated"\ntype: "data-package"\ntitle: "Migrated"\n'
        'status: "superseded"\nsuperseded_by: "research-package:migrated"\n---\n',
        encoding="utf-8",
    )
    issues = check_dataset_anomalies(tmp_path)
    assert not any(i["code"] == "data_package_unmigrated" for i in issues)


# ---------------------------------------------------------------------------
# Task 6.9: dataset_invariant_violation (umbrella + lineage)
# ---------------------------------------------------------------------------


def test_umbrella_in_consumed_by_flagged(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path, "umb", origin="external", body='access: {level: "mixed", verified: false}\nsiblings: ["dataset:c1"]'
    )
    _write_dataset(
        tmp_path,
        "c1",
        origin="external",
        body='access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}\n'
        'parent_dataset: "dataset:umb"\nconsumed_by: ["plan:p"]',
    )
    _write_dataset(
        tmp_path,
        "wrong",
        origin="external",
        body='access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://y"}\n'
        "consumed_by: []",
    )
    f = tmp_path / "doc" / "datasets" / "consumer.md"
    f.write_text(
        '---\nid: "dataset:consumer"\ntype: "dataset"\ntitle: "Consumer"\norigin: "external"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://z"}\n'
        'consumed_by: ["dataset:umb"]\n---\n',
        encoding="utf-8",
    )
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_invariant_violation" and "umbrella" in i["message"].lower() for i in issues)


def test_lineage_drift_flagged(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path, "p1", origin="external", body='access: {level: "public", verified: false}\nsiblings: ["dataset:c2"]'
    )
    _write_dataset(
        tmp_path, "c2", origin="external", body='access: {level: "public", verified: false}\nparent_dataset: ""'
    )
    issues = check_dataset_anomalies(tmp_path)
    assert any(i["code"] == "dataset_invariant_violation" and "lineage" in i["message"].lower() for i in issues)


# ---------------------------------------------------------------------------
# Task 6.10: dataset_cached_field_drift
# ---------------------------------------------------------------------------


def test_cached_field_drift_flagged(tmp_path: Path) -> None:
    import yaml

    _write_dataset(
        tmp_path,
        "drift",
        origin="external",
        body='license: "CC-BY-4.0"\n'
        'ontology_terms: ["UBERON:0001"]\n'
        'datapackage: "data/drift/datapackage.yaml"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}',
    )
    rt = tmp_path / "data" / "drift" / "datapackage.yaml"
    rt.parent.mkdir(parents=True)
    rt.write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0"],
                "name": "drift",
                "license": "CC0-1.0",  # drift!
                "ontology_terms": ["UBERON:0002"],  # drift!
                "resources": [{"name": "x", "path": "x.csv", "format": "csv"}],
            }
        )
    )
    # Also seed the resource file so unstageable doesn't fire
    (tmp_path / "data" / "drift" / "x.csv").write_text("col\n")
    issues = check_dataset_anomalies(tmp_path)
    drift_msgs = [i["message"] for i in issues if i["code"] == "dataset_cached_field_drift"]
    assert any("license" in m for m in drift_msgs)
    assert any("ontology_terms" in m for m in drift_msgs)


def test_cached_field_drift_skips_datapackage_directory_entities(tmp_path: Path) -> None:
    """Promoted datasets (provider=datapackage-directory) have no two surfaces to drift between."""
    import yaml

    dp_dir = tmp_path / "data" / "myset"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0", "science-pkg-entity-1.0"],
                "name": "myset",
                "id": "dataset:myset",
                "type": "dataset",
                "title": "My promoted set",
                "license": "CC-BY-4.0",
                "ontology_terms": ["UBERON:0001"],
                "resources": [{"name": "r", "path": "r.csv"}],
            }
        ),
        encoding="utf-8",
    )
    issues = check_dataset_anomalies(tmp_path)
    drift_issues = [i for i in issues if i["code"] == "dataset_cached_field_drift"]
    assert drift_issues == [], f"unexpected drift on promoted dataset: {drift_issues}"


# ---------------------------------------------------------------------------
# Task 6.11: dataset anomalies exposed via build_health_report
# ---------------------------------------------------------------------------


def test_health_cli_includes_dataset_section(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path, "u", origin="external", body='access: {level: "public", verified: false}\nconsumed_by: ["plan:p"]'
    )
    from science_tool.graph.health import build_health_report

    result = build_health_report(tmp_path, skip_checks={"validate"})
    assert "dataset_anomalies" in result
    codes = {i["code"] for i in result["dataset_anomalies"]}
    assert "dataset_consumed_but_unverified" in codes


def _write_prose_health_artifact(root: Path, *, findings: list[dict] | None = None) -> Path:
    path = root / "data" / "prose-health" / "prose-health.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-06-18T14:00:00Z",
                "manifest_path": "data/prose-health/manifest.json",
                "summary": {
                    "declared_sources": 1,
                    "sources_with_decomposition": 1,
                    "sources_with_grounding": 1,
                    "current_candidate_units": 2,
                    "promoted_units": 1,
                    "grounded_units": 1,
                    "below_floor_units": 0,
                    "unbacked_units": 0,
                    "unpromoted_units": 1,
                    "skipped_units": 1,
                    "stale_units": 0,
                    "contested_units": 0,
                },
                "coverage": {
                    "promotion": {"numerator": 1, "denominator": 2, "ratio": 0.5},
                    "grounding": {"numerator": 1, "denominator": 1, "ratio": 1.0},
                    "strict_grounding": {"numerator": 1, "denominator": 2, "ratio": 0.5},
                },
                "sources": [
                    {
                        "source_ref": "prose-source:example",
                        "title": "Example",
                        "path": "docs/example.md",
                        "state": "complete",
                        "decomposition_artifact_id": "decomp-1",
                        "grounding_report_path": "data/prose-grounding/example/grounding.json",
                        "summary": {
                            "current_candidate_units": 2,
                            "promoted_units": 1,
                            "grounded_units": 1,
                            "below_floor_units": 0,
                            "unbacked_units": 0,
                            "unpromoted_units": 1,
                            "skipped_units": 1,
                            "stale_units": 0,
                            "contested_units": 0,
                        },
                    }
                ],
                "units": [],
                "findings": findings or [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _prose_epistemics_payload(report: object) -> dict[str, object]:
    assert isinstance(report, dict)
    prose_epistemics = report["prose_epistemics"]
    assert isinstance(prose_epistemics, dict)
    return cast("dict[str, object]", prose_epistemics)


def _prose_epistemics_findings(report: object) -> list[dict[str, object]]:
    findings = _prose_epistemics_payload(report)["findings"]
    assert isinstance(findings, list)
    assert all(isinstance(row, dict) for row in findings)
    return cast("list[dict[str, object]]", findings)


def test_health_report_includes_prose_epistemics_artifact(tmp_path: Path) -> None:
    from science_tool.graph.health import build_health_report

    _write_prose_health_artifact(tmp_path)

    report = build_health_report(tmp_path, checks={"prose_epistemics"})
    prose_epistemics = _prose_epistemics_payload(report)
    summary = prose_epistemics["summary"]
    coverage = prose_epistemics["coverage"]
    assert isinstance(summary, dict)
    assert isinstance(coverage, dict)
    strict_grounding = coverage["strict_grounding"]
    assert isinstance(strict_grounding, dict)

    assert summary["declared_sources"] == 1
    assert strict_grounding["ratio"] == 0.5
    assert prose_epistemics["findings"] == []
    assert report["total_issues"] == 0


def test_health_report_counts_prose_epistemics_findings_as_issues(tmp_path: Path) -> None:
    from science_tool.graph.health import build_health_report

    _write_prose_health_artifact(
        tmp_path,
        findings=[
            {
                "code": "missing_grounding",
                "severity": "warning",
                "counts_as_issue": True,
                "source_ref": "prose-source:example",
                "path": "docs/example.md",
                "message": "Declared prose source has no P3 grounding report.",
            },
            {
                "code": "undeclared_grounding_report",
                "severity": "warning",
                "counts_as_issue": False,
                "source_ref": "prose-source:extra",
                "path": "data/prose-grounding/extra/grounding.json",
                "message": "Extra report.",
            },
        ],
    )

    report = build_health_report(tmp_path, checks={"prose_epistemics"})

    assert len(_prose_epistemics_findings(report)) == 2
    assert report["total_issues"] == 1


def test_health_report_prose_health_manifest_without_artifact_surfaces_rebuild_finding(tmp_path: Path) -> None:
    from science_tool.graph.health import build_health_report

    manifest = tmp_path / "data" / "prose-health" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"schema_version": 1, "sources": []}), encoding="utf-8")

    report = build_health_report(tmp_path, checks={"prose_epistemics"})
    findings = _prose_epistemics_findings(report)

    assert findings[0]["code"] == "prose_health_artifact_missing"
    assert findings[0]["counts_as_issue"] is True
    assert report["total_issues"] == 1


def test_health_report_invalid_prose_health_manifest_surfaces_manifest_invalid(tmp_path: Path) -> None:
    from science_tool.graph.health import build_health_report

    manifest = tmp_path / "data" / "prose-health" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("{not json", encoding="utf-8")

    report = build_health_report(tmp_path, checks={"prose_epistemics"})
    findings = _prose_epistemics_findings(report)

    assert findings[0]["code"] == "manifest_invalid"
    assert findings[0]["counts_as_issue"] is True
    assert report["total_issues"] == 1


def test_health_report_invalid_prose_health_artifact_surfaces_artifact_invalid(tmp_path: Path) -> None:
    from science_tool.graph.health import build_health_report

    artifact = tmp_path / "data" / "prose-health" / "prose-health.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("{not json", encoding="utf-8")

    report = build_health_report(tmp_path, checks={"prose_epistemics"})
    findings = _prose_epistemics_findings(report)

    assert findings[0]["code"] == "prose_health_artifact_invalid"
    assert findings[0]["counts_as_issue"] is True
    assert report["total_issues"] == 1


def test_health_report_no_prose_health_manifest_no_artifact_is_not_applicable(tmp_path: Path) -> None:
    from science_tool.graph.health import build_health_report

    report = build_health_report(tmp_path, checks={"prose_epistemics"})
    prose_epistemics = _prose_epistemics_payload(report)

    assert prose_epistemics["applicable"] is False
    assert prose_epistemics["findings"] == []
    assert report["total_issues"] == 0


def test_health_cli_json_includes_prose_epistemics(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main

    _write_prose_health_artifact(tmp_path)

    result = CliRunner().invoke(
        main,
        ["health", "--project-root", str(tmp_path), "--format", "json", "--check", "prose_epistemics"],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["prose_epistemics"]["summary"]["grounded_units"] == 1


def test_health_list_checks_includes_prose_epistemics(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main

    result = CliRunner().invoke(
        main,
        ["health", "--project-root", str(tmp_path), "--format", "json", "--list-checks"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert any(row["name"] == "prose_epistemics" for row in payload["checks"])


def test_health_cli_table_includes_prose_epistemics_findings(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main

    _write_prose_health_artifact(
        tmp_path,
        findings=[
            {
                "code": "missing_grounding",
                "severity": "warning",
                "counts_as_issue": True,
                "source_ref": "prose-source:example",
                "path": "docs/example.md",
                "message": "Declared prose source has no P3 grounding report.",
            }
        ],
    )

    result = CliRunner().invoke(main, ["health", "--project-root", str(tmp_path), "--check", "prose_epistemics"])

    assert result.exit_code == 0, result.output
    assert "Prose Epistemics" in result.output
    assert "missing_grounding" in result.output
    assert "prose-source:example" in result.output
    assert "Next action" in result.output
    assert "science annotate build-prose-health --write" in result.output
