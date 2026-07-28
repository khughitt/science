from pathlib import Path

from science_tool.findings.catalog import build_project_registry
from science_tool.graph.health import build_health_report
from science_tool.graph.health_cli import render_health_report


class _Console:
    def print(self, value: object) -> None:
        self.values.append(value)

    def __init__(self) -> None:
        self.values: list[object] = []


class _Sink:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.console = _Console()

    def echo(self, value: object = "") -> None:
        self.lines.append(str(value))


def test_unwired_is_separate_and_renderer_refuses_clean(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    report = build_health_report(
        tmp_path,
        ingestion_ref="health:test",
        generated_at="2026-07-28T12:00:00+00:00",
        checks={"unresolved_refs"},
    )
    assert report.totals.findings_total == 0
    assert report.totals.unwired_total == 1
    sink = _Sink()
    render_health_report(report, build_project_registry(tmp_path), sink)
    assert "Project is not clean: one or more diagnostics could not run." in sink.lines
    assert "Project is clean." not in sink.lines


def test_wired_zero_renderer_is_clean(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[dependency-groups]\ndev=['science']\n"
        "[tool.uv.sources]\nscience={git='https://github.com/khughitt/science.git', subdirectory='science'}\n",
        encoding="utf-8",
    )
    report = build_health_report(
        tmp_path,
        ingestion_ref="health:test",
        generated_at="2026-07-28T12:00:00+00:00",
        checks={"tooling_scaffold"},
    )
    sink = _Sink()
    render_health_report(report, build_project_registry(tmp_path), sink)
    assert "Project is clean." in sink.lines
