from pathlib import Path

from science_tool.graph.storage_adapters.code import CodeAdapter


def _adapter(root: Path, **kw) -> CodeAdapter:
    return CodeAdapter(code_roots=(root / "code",), repo_root=root, excludes=kw.get("excludes", ()))


def test_discover_finds_code_files_and_applies_excludes(tmp_path: Path) -> None:
    (tmp_path / "code" / "stages").mkdir(parents=True)
    (tmp_path / "code" / "stages" / "run.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "code" / "notes.md").write_text("not code\n", encoding="utf-8")
    (tmp_path / "code" / "vendor").mkdir()
    (tmp_path / "code" / "vendor" / "lib.py").write_text("y=2\n", encoding="utf-8")

    (tmp_path / "code" / "Snakefile").write_text("rule all:\n    input: []\n", encoding="utf-8")
    (tmp_path / "code" / "rules.smk").write_text("rule x:\n    shell: 'true'\n", encoding="utf-8")

    refs = _adapter(tmp_path, excludes=("**/vendor/**",)).discover(tmp_path)
    paths = {ref.path for ref in refs}
    assert "code/stages/run.py" in paths
    assert "code/Snakefile" in paths           # Snakefile by name
    assert "code/rules.smk" in paths           # .smk suffix
    assert "code/notes.md" not in paths       # not a code suffix
    assert "code/vendor/lib.py" not in paths   # excluded


def test_load_raw_blockless_file_returns_no_kind(tmp_path: Path) -> None:
    (tmp_path / "code").mkdir()
    f = tmp_path / "code" / "x.py"
    f.write_text("print(1)\n", encoding="utf-8")
    import os

    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        from science_model.source_ref import SourceRef

        raw = _adapter(tmp_path).load_raw(SourceRef(adapter_name="code-file", path="code/x.py"))
    finally:
        os.chdir(prev)
    assert "kind" not in raw


def test_load_raw_builds_code_file_record(tmp_path: Path) -> None:
    import os

    from science_model.source_ref import SourceRef

    (tmp_path / "code" / "stages").mkdir(parents=True)
    f = tmp_path / "code" / "stages" / "run.py"
    f.write_text(
        "# science:code\n# task_ids: [t491]\n# decision_bearing: true\n# status: workflow-owned\n# science:end\nprint(1)\n",
        encoding="utf-8",
    )
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        raw = _adapter(tmp_path).load_raw(SourceRef(adapter_name="code-file", path="code/stages/run.py"))
    finally:
        os.chdir(prev)
    assert raw["kind"] == "code-file"
    assert raw["id"] == "code-file:stages/run.py"
    assert raw["title"] == "stages/run.py"
    assert raw["status"] == "workflow-owned"
    assert raw["decision_bearing"] is True
    assert raw["task_ids"] == ["t491"]
    assert raw["file_path"] == "code/stages/run.py"


def test_load_raw_decision_bearing_none_when_absent(tmp_path: Path) -> None:
    import os

    from science_model.source_ref import SourceRef

    (tmp_path / "code").mkdir()
    f = tmp_path / "code" / "run.py"
    f.write_text(
        '# science:code\n# status: workflow-owned\n# science:end\nif __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        raw = _adapter(tmp_path).load_raw(SourceRef(adapter_name="code-file", path="code/run.py"))
    finally:
        os.chdir(prev)
    assert raw["decision_bearing"] is None        # absent in block -> None (fail-closed default applied later)
    assert raw["executable"] is True              # has __main__ entrypoint


def test_load_raw_invalid_block_returns_no_kind(tmp_path: Path) -> None:
    import os

    from science_model.source_ref import SourceRef

    (tmp_path / "code").mkdir()
    # unterminated block -> invalid -> skipped (Plan B diagnoses the malformed block)
    (tmp_path / "code" / "x.py").write_text("# science:code\n# status: library\nprint(1)\n", encoding="utf-8")
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        raw = _adapter(tmp_path).load_raw(SourceRef(adapter_name="code-file", path="code/x.py"))
    finally:
        os.chdir(prev)
    assert "kind" not in raw
