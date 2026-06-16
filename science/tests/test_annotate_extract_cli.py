import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.io import read_sidecar
from science_tool.annotation.source_text import Passage, SourcePassages, write_source_md

_MODEL = "claude-sonnet-4-6"


def _make_source_md(tmp_path: Path) -> Path:
    abstract = SourcePassages(
        passages=(
            Passage(section="title", bioc_offset=0, text="A study of BRCA1."),
            Passage(section="abstract", bioc_offset=18,
                    text="BRCA1 loss drives genomic instability in tumors."),
        ),
        release="2024",
    )
    return write_source_md(
        directory=tmp_path, citekey="Brca2024", abstract=abstract, fulltext=None,
        retrieved_from="https://example.org", license_="unknown", licensed=False,
        pmid="1", doi=None,
    )


def test_extract_cli_check_then_seed_round_trip(tmp_path: Path):
    src = _make_source_md(tmp_path)
    runner = CliRunner()

    # --check on a fresh paper -> changed
    r = runner.invoke(annotate_group, [
        "extract", "--source-md", str(src), "--model", _MODEL, "--check",
    ])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["status"] == "changed"

    # write candidates + run extract
    cand_file = tmp_path / "candidates.json"
    cand_file.write_text(json.dumps({"candidates": [{
        "type": "proposition",
        "exact": "BRCA1 loss drives genomic instability",
        "prefix": "", "suffix": " in tumors", "stance": "asserted",
    }]}), encoding="utf-8")
    r = runner.invoke(annotate_group, [
        "extract", "--source-md", str(src), "--model", _MODEL,
        "--input", str(cand_file), "--format", "json",
    ])
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["written"] == 1

    sidecar = read_sidecar(src.with_name("Brca2024.source.anno.trig"))
    assert any(a.annotation_type == "proposition" for a in sidecar.annotations)

    # --check now -> unchanged
    r = runner.invoke(annotate_group, [
        "extract", "--source-md", str(src), "--model", _MODEL, "--check",
    ])
    assert json.loads(r.output)["status"] == "unchanged"


def test_extract_cli_malformed_input_fails_loud(tmp_path: Path):
    src = _make_source_md(tmp_path)
    bad = tmp_path / "bad.json"
    # metaphor is a valid type now, but this one is missing required domains -> fail loud
    bad.write_text(json.dumps({"candidates": [{"type": "metaphor", "exact": "x",
                   "prefix": "", "suffix": ""}]}),
                   encoding="utf-8")
    r = CliRunner().invoke(annotate_group, [
        "extract", "--source-md", str(src), "--model", _MODEL, "--input", str(bad),
    ])
    assert r.exit_code != 0
    # nothing written: no sidecar created
    assert not src.with_name("Brca2024.source.anno.trig").exists()


def test_extract_cli_figurative_round_trip_and_neutral_output(tmp_path: Path):
    # source text whose abstract passage contains the figurative span
    abstract = SourcePassages(
        passages=(
            Passage(section="title", bioc_offset=0, text="On immunity."),
            Passage(section="abstract", bioc_offset=13,
                    text="The immune system mounts an attack on pathogens."),
        ),
        release="2024",
    )
    src = write_source_md(
        directory=tmp_path, citekey="Imm2024", abstract=abstract, fulltext=None,
        retrieved_from="https://example.org", license_="unknown", licensed=False,
        pmid="2", doi=None,
    )
    cand_file = tmp_path / "candidates.json"
    cand_file.write_text(json.dumps({"candidates": [{
        "type": "metaphor", "exact": "The immune system mounts an attack",
        "prefix": "", "suffix": " on pathogens",
        "source_domain": "warfare", "target_domain": "immune response",
    }]}), encoding="utf-8")
    runner = CliRunner()
    # table output (default) must be type-neutral: "annotation(s) written"
    r = runner.invoke(annotate_group, [
        "extract", "--source-md", str(src), "--model", _MODEL, "--input", str(cand_file),
    ])
    assert r.exit_code == 0, r.output
    assert "annotation(s) written" in r.output
    assert "statement(s) written" not in r.output

    sidecar = read_sidecar(src.with_name("Imm2024.source.anno.trig"))
    assert any(a.annotation_type == "metaphor" for a in sidecar.annotations)


def test_list_json_exposes_bodies_and_full_selector(tmp_path: Path):
    # Seed one statement, then `annotate list --format json` must carry bodies+selector.
    src = _make_source_md(tmp_path)
    cand_file = tmp_path / "c.json"
    cand_file.write_text(json.dumps({"candidates": [{
        "type": "proposition",
        "exact": "BRCA1 loss drives genomic instability",
        "prefix": "", "suffix": " in tumors", "stance": "asserted",
    }]}), encoding="utf-8")
    runner = CliRunner()
    runner.invoke(annotate_group, ["extract", "--source-md", str(src),
                  "--model", _MODEL, "--input", str(cand_file)])

    r = runner.invoke(annotate_group, ["list", "--root", str(tmp_path),
                      "--format", "json"])
    assert r.exit_code == 0, r.output
    item = json.loads(r.output)["annotations"][0]
    # backward-compatible keys still present
    assert "exact_preview" in item and "annotation_type" in item
    # new additive keys
    assert "bodies" in item and isinstance(item["bodies"], list)
    assert item["bodies"][0]["type"] == "textual"
    assert "selector" in item
    assert item["selector"]["exact"] == "BRCA1 loss drives genomic instability"
    assert "prefix" in item["selector"] and "suffix" in item["selector"]


def test_extract_cli_surfaces_note_on_anchor_failure(tmp_path: Path):
    src = _make_source_md(tmp_path)
    cand_file = tmp_path / "c.json"
    cand_file.write_text(json.dumps({"candidates": [{
        "type": "proposition", "exact": "absent from this document",
        "prefix": "", "suffix": "", "stance": "asserted",
    }]}), encoding="utf-8")
    r = CliRunner().invoke(annotate_group, [
        "extract", "--source-md", str(src), "--model", _MODEL,
        "--input", str(cand_file), "--format", "json",
    ])
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["written"] == 0 and out["source_text_hash_recorded"] is False
    assert out["note"] is not None and "failed to anchor" in out["note"]


def test_paper_annotate_agent_file_has_frontmatter():
    # repo root is three levels up from science/tests/
    repo_root = Path(__file__).resolve().parents[2]
    agent = repo_root / "agents" / "paper-annotate.md"
    assert agent.is_file(), "agents/paper-annotate.md must exist"
    text = agent.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "name: paper-annotate" in text
    assert "science annotate extract" in text  # documents the deterministic call
    # Phase 3b: the agent must document figurative extraction
    assert "metaphor" in text and "analogy" in text
    assert "source_domain" in text and "target_domain" in text
    cmd = repo_root / "commands" / "annotate-paper.md"
    assert cmd.is_file(), "commands/annotate-paper.md must exist"
    assert "--check" in cmd.read_text(encoding="utf-8")  # documents the precheck
