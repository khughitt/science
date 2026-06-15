from __future__ import annotations

import httpx
from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group

# Inline a minimal BioC record (do NOT cross-import from tests.test_pubtator_seed —
# `tests` is not an importable package here; only a conftest.py exists).
_CLI_BIOC = {
    "PubTator3": [
        {
            "id": "12345678",
            "infons": {"_release": "2025-01"},
            "passages": [
                {
                    "infons": {"type": "title"},
                    "offset": 0,
                    "text": "BRCA1 in breast cancer",
                    "annotations": [
                        {"infons": {"identifier": "672", "type": "Gene"}, "text": "BRCA1", "locations": [{"offset": 0, "length": 5}]},
                        {"infons": {"identifier": "MESH:D001943", "type": "Disease"}, "text": "breast cancer", "locations": [{"offset": 9, "length": 13}]},
                    ],
                },
                {"infons": {"type": "abstract"}, "offset": 23, "text": "An abstract sentence.", "annotations": []},
            ],
        }
    ]
}


def _handler(request: httpx.Request) -> httpx.Response:
    if "pubtator3-api" in str(request.url):
        return httpx.Response(200, json=_CLI_BIOC)
    return httpx.Response(200, json={"resultList": {"result": []}})


def _entity(tmp_path):
    d = tmp_path / "doc" / "background" / "papers"
    d.mkdir(parents=True)
    (d / "doe2020.md").write_text("---\nkind: paper\npmid: 12345678\n---\n\n# Doe 2020\n")
    return d


def test_cli_pubtator_seeds(tmp_path, monkeypatch):
    _entity(tmp_path)
    # Inject the MockTransport client into both persist + seed by monkeypatching the
    # httpx.Client constructor used when http=None flows through the CLI.
    real_client = httpx.Client

    def _factory(*args, **kwargs):
        return real_client(transport=httpx.MockTransport(_handler))

    monkeypatch.setattr("science_tool.annotation.source_text.httpx.Client", _factory)
    monkeypatch.setattr("science_tool.annotation.pubtator_seed.httpx.Client", _factory)

    runner = CliRunner()
    from science_tool.cli import main as root_main

    cache = str(tmp_path / "cache")  # keep FetchConfig off ~/.cache/science (sandbox + state)
    persist = runner.invoke(
        root_main,
        ["paper", "persist-source", "12345678", "--project-root", str(tmp_path),
         "--email", "t@example.com", "--cache-dir", cache],
    )
    assert persist.exit_code == 0, persist.output

    result = runner.invoke(
        annotate_group,
        ["pubtator", "12345678", "--project-root", str(tmp_path),
         "--email", "t@example.com", "--actor", "tester", "--cache-dir", cache],
    )
    assert result.exit_code == 0, result.output
    assert "Wrote 2" in result.output  # gene + disease from the inline title passage


def test_cli_pubtator_missing_source_md_errors(tmp_path):
    _entity(tmp_path)  # entity but no .source.md
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        ["pubtator", "12345678", "--project-root", str(tmp_path),
         "--email", "t@example.com", "--cache-dir", str(tmp_path / "cache")],
    )
    assert result.exit_code != 0
    assert "persist-source" in result.output
