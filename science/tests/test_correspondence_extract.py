from science_tool.correspondence.extract import extract_deliverables, extract_task_refs


def test_extracts_backticked_code_paths():
    body = "Add `src/foo/bar.py` and `tests/test_bar.py`.\n"
    assert extract_deliverables(body) == ["src/foo/bar.py", "tests/test_bar.py"]


def test_deduplicates_preserving_first_occurrence_order():
    body = "`b/y.py` then `a/x.py` then `b/y.py` again\n"
    assert extract_deliverables(body) == ["b/y.py", "a/x.py"]


def test_ignores_bare_filenames_without_a_directory():
    """`foo.py` cannot be resolved to a location -- it is ambiguous, not absent."""
    assert extract_deliverables("see `foo.py` somewhere\n") == []


def test_ignores_prose_in_backticks():
    assert extract_deliverables("the `status` field and `--apply` flag\n") == []


def test_extracts_supported_extensions_only():
    body = "`a/b.py` `c/d.ts` `e/f.md` `g/h.yaml` `i/j.json` `k/l.png` `m/n.exe`\n"
    assert extract_deliverables(body) == [
        "a/b.py", "c/d.ts", "e/f.md", "g/h.yaml", "i/j.json",
    ]


def test_extracts_task_refs():
    assert extract_task_refs("closes `task:t254` and task:t007\n") == ["t254", "t007"]


def test_task_refs_deduplicated():
    assert extract_task_refs("task:t1 task:t1 task:t2\n") == ["t1", "t2"]


def test_no_task_refs_returns_empty():
    assert extract_task_refs("no tasks here\n") == []
