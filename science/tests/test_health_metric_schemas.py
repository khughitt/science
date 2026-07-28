from pathlib import Path

import pytest
from science_model.audit import ProducerMetrics

from science_tool.findings.catalog import build_project_registry
from science_tool.findings.producers import (
    FindingProducerResult,
    RegistryError,
    validate_producer_result,
)
from science_tool.graph.health_checks import (
    cross_paper_evidence,
    managed_artifacts,
    prose_epistemics,
)
from science_tool.instruments import InstrumentResult


def _cross_paper_metrics() -> dict[str, object]:
    return {
        "status": "ok",
        "empty_state": "active",
        "summary": {
            "propositions": 1,
            "propositions_with_units": 1,
            "units": 1,
            "faults": 0,
            "faults_by_reason": {},
            "contested": 0,
        },
        "propositions": [
            {
                "proposition": "proposition:p",
                "unit_count": 1,
                "supporting_papers": 1,
                "disputing_papers": 0,
                "belief": {
                    "belief_magnitude": "fragile",
                    "contested": False,
                    "contested_groups": [],
                    "support_units": 1,
                    "dispute_units": 0,
                },
            }
        ],
    }


def _managed_metrics() -> dict[str, object]:
    return {
        "inventory": [
            {
                "name": "commands",
                "install_target": ".claude/commands",
                "version": "v1",
                "status": "current",
                "detail": "",
                "counts_as_issue": False,
            }
        ]
    }


def _prose_metrics() -> dict[str, object]:
    source_summary = {
        "current_candidate_units": 1,
        "promoted_units": 1,
        "grounded_units": 1,
        "below_floor_units": 0,
        "unbacked_units": 0,
        "unpromoted_units": 0,
        "skipped_units": 0,
        "stale_units": 0,
        "contested_units": 0,
    }
    return {
        "applicable": True,
        "summary": {
            "declared_sources": 1,
            "sources_with_decomposition": 1,
            "sources_with_grounding": 1,
            **source_summary,
        },
        "coverage": {
            "promotion": {"numerator": 1, "denominator": 1, "ratio": 1.0},
            "grounding": {"numerator": 1, "denominator": 1, "ratio": 1.0},
            "strict_grounding": {
                "numerator": 1,
                "denominator": 1,
                "ratio": 1.0,
            },
        },
        "sources": [
            {
                "source_ref": "paper:p",
                "title": "Paper",
                "path": "sources/paper.md",
                "decomposition_artifact_id": "artifact:one",
                "grounding_report_path": "data/prose-health/paper/grounding.json",
                "summary": source_summary,
                "state": "complete",
            }
        ],
    }


@pytest.mark.parametrize(
    ("producer_id", "payload"),
    (
        (
            "cross_paper_evidence",
            {
                **_cross_paper_metrics(),
                "summary": {
                    **_cross_paper_metrics()["summary"],  # type: ignore[misc]
                    "unexpected": 1,
                },
            },
        ),
        (
            "cross_paper_evidence",
            {**_cross_paper_metrics(), "status": "unknown"},
        ),
        (
            "managed_artifacts",
            {
                "inventory": [
                    {
                        **_managed_metrics()["inventory"][0],  # type: ignore[index]
                        "unexpected": True,
                    }
                ]
            },
        ),
        (
            "prose_epistemics",
            {
                **_prose_metrics(),
                "sources": [
                    {
                        **_prose_metrics()["sources"][0],  # type: ignore[index]
                        "state": "unknown",
                    }
                ],
            },
        ),
        (
            "prose_epistemics",
            {
                **_prose_metrics(),
                "coverage": {
                    **_prose_metrics()["coverage"],  # type: ignore[misc]
                    "promotion": {
                        "numerator": 1,
                        "denominator": 1,
                        "ratio": 1.0,
                        "unexpected": 1,
                    },
                },
            },
        ),
    ),
)
def test_nested_metric_models_reject_malformed_or_extra_data(
    tmp_path: Path,
    producer_id: str,
    payload: dict[str, object],
) -> None:
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    producer = {
        "cross_paper_evidence": cross_paper_evidence.PRODUCER,
        "managed_artifacts": managed_artifacts.PRODUCER,
        "prose_epistemics": prose_epistemics.PRODUCER,
    }[producer_id]
    result = FindingProducerResult(
        instrument=InstrumentResult.empty(),
        metrics=ProducerMetrics.model_validate(payload),
    )

    with pytest.raises(RegistryError, match="metrics invalid"):
        validate_producer_result(
            build_project_registry(tmp_path),
            producer.producer_id,
            result,
        )
