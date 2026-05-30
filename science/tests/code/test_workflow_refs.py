from pathlib import Path

from science_tool.code.workflow_refs import find_workflow_references


def _refs(project_root: Path, *smk_paths: Path) -> dict[str, list[str]]:
    return find_workflow_references(
        list(smk_paths), project_root=project_root, code_root_names=("code",)
    )


def test_detects_literal_script_and_shell_paths(tmp_path: Path) -> None:
    wf = tmp_path / "code" / "workflows" / "stages"
    wf.mkdir(parents=True)
    smk = wf / "example.smk"
    smk.write_text(
        'rule direct_script:\n'
        '    script:\n'
        '        "../../analysis/example/run.py"\n'
        '\n'
        'rule shell_module:\n'
        '    shell:\n'
        '        "uv run python code/qa/example_audit.py --out {output}"\n',
        encoding="utf-8",
    )
    refs = _refs(tmp_path, smk)
    assert refs["code/analysis/example/run.py"] == [
        "code/workflows/stages/example.smk::direct_script"
    ]
    assert refs["code/qa/example_audit.py"] == [
        "code/workflows/stages/example.smk::shell_module"
    ]


def test_expands_path_symbol_indirection_across_files(tmp_path: Path) -> None:
    wf = tmp_path / "code" / "workflows" / "hyp"
    wf.mkdir(parents=True)
    shared = wf / "shared.smk"
    shared.write_text(
        'from pathlib import Path\n\nHYP_SCRIPTS = Path("code/analysis/hyp")\n',
        encoding="utf-8",
    )
    h2 = wf / "h2.smk"
    h2.write_text(
        'H2_SCRIPTS = HYP_SCRIPTS / "h2"\n'
        '\n'
        'rule h2_enrich:\n'
        '    shell:\n'
        '        "uv run python {H2_SCRIPTS}/enrich.py "\n',
        encoding="utf-8",
    )
    refs = _refs(tmp_path, shared, h2)
    assert refs["code/analysis/hyp/h2/enrich.py"] == [
        "code/workflows/hyp/h2.smk::h2_enrich"
    ]


def test_reused_symbol_name_resolves_per_file(tmp_path: Path) -> None:
    """A symbol name reused across Snakefiles must resolve per-file, not globally.

    Regression for fb-2026-05-28-004: a global first-definition-wins symbol
    table made every workflow's `SCRIPTS = Path(...)` collapse to the first
    file's value, so later workflows' `{SCRIPTS}/x.py` resolved to the wrong
    directory and their real scripts were flagged code.orphaned-executable.
    """
    swan = tmp_path / "code" / "workflows" / "swan"
    cosmic = tmp_path / "code" / "workflows" / "cosmic"
    swan.mkdir(parents=True)
    cosmic.mkdir(parents=True)
    swan_smk = swan / "swan.smk"
    swan_smk.write_text(
        'from pathlib import Path\n\nSCRIPTS = Path("code/analysis/swan")\n'
        '\n'
        'rule swan_run:\n'
        '    shell:\n'
        '        "uv run python {SCRIPTS}/run.py"\n',
        encoding="utf-8",
    )
    cosmic_smk = cosmic / "cosmic.smk"
    cosmic_smk.write_text(
        'from pathlib import Path\n\nSCRIPTS = Path("code/analysis/cosmic")\n'
        '\n'
        'rule cosmic_run:\n'
        '    shell:\n'
        '        "uv run python {SCRIPTS}/run.py"\n',
        encoding="utf-8",
    )
    refs = _refs(tmp_path, swan_smk, cosmic_smk)
    assert refs["code/analysis/swan/run.py"] == ["code/workflows/swan/swan.smk::swan_run"]
    assert refs["code/analysis/cosmic/run.py"] == ["code/workflows/cosmic/cosmic.smk::cosmic_run"]


def test_expands_multiline_f_string_reference(tmp_path: Path) -> None:
    wf = tmp_path / "code" / "workflows" / "external"
    wf.mkdir(parents=True)
    smk = wf / "walker.smk"
    smk.write_text(
        'from pathlib import Path\n'
        '\n'
        'WALKER_SCRIPTS = Path("code/analysis/external/walker")\n'
        '\n'
        'rule walker_build:\n'
        '    shell:\n'
        '        "uv run python "\n'
        '        f"{WALKER_SCRIPTS}/build.py "\n',
        encoding="utf-8",
    )
    refs = _refs(tmp_path, smk)
    assert refs["code/analysis/external/walker/build.py"] == [
        "code/workflows/external/walker.smk::walker_build"
    ]


def test_expands_wildcard_script_directory(tmp_path: Path) -> None:
    wf = tmp_path / "code" / "workflows" / "stages"
    wf.mkdir(parents=True)
    smk = wf / "geo.smk"
    smk.write_text(
        'rule geo_normalize:\n'
        '    script:\n'
        '        "../../analysis/geo/normalize/{wildcards.acc}.R"\n',
        encoding="utf-8",
    )
    norm = tmp_path / "code" / "analysis" / "geo" / "normalize"
    norm.mkdir(parents=True)
    (norm / "GSE9782.R").write_text("# concrete\n", encoding="utf-8")
    (norm / "GSE6477.R").write_text("# concrete\n", encoding="utf-8")
    refs = _refs(tmp_path, smk)
    assert refs["code/analysis/geo/normalize/GSE9782.R"] == [
        "code/workflows/stages/geo.smk::geo_normalize"
    ]
    assert refs["code/analysis/geo/normalize/GSE6477.R"] == [
        "code/workflows/stages/geo.smk::geo_normalize"
    ]


def test_expands_str_path_expression_reference(tmp_path: Path) -> None:
    wf = tmp_path / "code" / "workflows"
    wf.mkdir(parents=True)
    smk = wf / "t413.smk"
    smk.write_text(
        'from pathlib import Path\n'
        '\n'
        'T413_SCRIPTS = Path("code/analysis/h1/t413")\n'
        '\n'
        'rule t413_de:\n'
        '    input:\n'
        '        r_driver=str(T413_SCRIPTS / "_t413_de.R"),\n'
        '    shell:\n'
        '        "uv run python {T413_SCRIPTS}/de_families.py --r-driver {input.r_driver:q}"\n',
        encoding="utf-8",
    )
    refs = _refs(tmp_path, smk)
    # `{SYMBOL}/...` (shell) and `str(SYMBOL / "...")` (input) both resolve.
    assert refs["code/analysis/h1/t413/de_families.py"] == ["code/workflows/t413.smk::t413_de"]
    assert refs["code/analysis/h1/t413/_t413_de.R"] == ["code/workflows/t413.smk::t413_de"]


def test_detects_python_module_invocation(tmp_path: Path) -> None:
    wf = tmp_path / "code" / "workflows" / "stages"
    wf.mkdir(parents=True)
    smk = wf / "cyto.smk"
    smk.write_text(
        'rule cn_matrix:\n'
        '    shell:\n'
        '        "uv run --frozen python -m code.stages.cyto.cn_matrix "\n',
        encoding="utf-8",
    )
    refs = _refs(tmp_path, smk)
    assert refs["code/stages/cyto/cn_matrix.py"] == [
        "code/workflows/stages/cyto.smk::cn_matrix"
    ]


def test_no_workflow_files_is_empty(tmp_path: Path) -> None:
    assert find_workflow_references([], project_root=tmp_path, code_root_names=("code",)) == {}


def test_unreadable_workflow_file_is_skipped(tmp_path: Path) -> None:
    missing = tmp_path / "code" / "workflows" / "gone.smk"
    refs = find_workflow_references(
        [missing], project_root=tmp_path, code_root_names=("code",)
    )
    assert refs == {}
