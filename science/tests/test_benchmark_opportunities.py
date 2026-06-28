from __future__ import annotations

import sqlite3
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _write_entity(root: Path, kind_dir: str, slug: str, frontmatter: str, body: str = "body") -> None:
    path = root / "entities" / kind_dir / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}\n", encoding="utf-8")


def _write_dataset(root: Path, slug: str, frontmatter: str, body: str = "body") -> None:
    _write_entity(root, "datasets", slug, frontmatter, body=body)


def _invoke(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "opportunities", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )


def _invoke_with_commons(tmp_path: Path, commons_root: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "opportunities", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(commons_root)},
    )


def _write_corrupt_commons_registry(root: Path, frontmatter_json: str = "{not-json") -> None:
    root.mkdir()
    conn = sqlite3.connect(root / "registry.sqlite")
    try:
        conn.executescript(
            """
            CREATE TABLE entities (
                canonical_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                slug TEXT NOT NULL,
                title TEXT,
                schema_profile TEXT NOT NULL,
                body_path TEXT NOT NULL,
                datapackage_path TEXT,
                mtime_ns INTEGER NOT NULL,
                frontmatter_json TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO entities "
            "(canonical_id, type, slug, title, schema_profile, body_path, datapackage_path, mtime_ns, frontmatter_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "dataset:corrupt",
                "dataset",
                "corrupt",
                "Corrupt",
                "dataset/v1",
                "datasets/corrupt/entity.md",
                None,
                0,
                frontmatter_json,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def test_benchmark_sources_preserve_task_details_notes_and_limitations(tmp_path: Path) -> None:
    from science_tool.benchmark_catalog import benchmark_sources

    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq, perturbation]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  notes:
    - Useful perturbation benchmark.
  limitations:
    - No local datapackage staged.
  tasks:
    - id: compound-response
      prediction_target: post-treatment expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured expression
""",
    )

    sources, notice = benchmark_sources(tmp_path)

    assert notice is None
    assert len(sources) == 1
    source = sources[0]
    assert source["fallback_id"] == "dataset:sciplex3"
    assert source["scope"] == "local"
    benchmark = source["frontmatter"]["benchmark"]
    assert benchmark["notes"] == ["Useful perturbation benchmark."]
    assert benchmark["limitations"] == ["No local datapackage staged."]
    assert benchmark["tasks"][0] == {
        "id": "compound-response",
        "prediction_target": "post-treatment expression",
        "held_out_unit": "compound",
        "metric": "rank-correlation",
        "baseline": "nearest-neighbor",
        "ground_truth": {
            "type": "measured-outcome",
            "description": "measured expression",
        },
    }
