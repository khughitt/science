from science_tool.code.provenance import code_file_id_from_tool_path


def test_strips_function_suffix_and_code_root() -> None:
    assert (
        code_file_id_from_tool_path("scripts/signatures/build.py::build_combined_corpus", code_root_names=("scripts",))
        == "code-file:signatures/build.py"
    )


def test_no_function_suffix_and_code_root() -> None:
    assert code_file_id_from_tool_path("code/stages/run.py", code_root_names=("code",)) == "code-file:stages/run.py"


def test_path_outside_declared_roots_kept_whole() -> None:
    assert code_file_id_from_tool_path("misc/run.py", code_root_names=("code",)) == "code-file:misc/run.py"
