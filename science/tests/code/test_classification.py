from science_tool.code.classification import classify_code_file, is_executable


def test_r_and_sh_are_always_executable() -> None:
    assert is_executable("code/a.R", "x <- 1\n")
    assert is_executable("code/a.sh", "echo hi\n")


def test_python_with_main_is_executable() -> None:
    assert is_executable("code/a.py", 'if __name__ == "__main__":\n    pass\n')


def test_python_with_argparse_is_executable() -> None:
    assert is_executable("code/a.py", "p = argparse.ArgumentParser()\n")


def test_python_library_is_not_executable() -> None:
    assert not is_executable("code/a.py", "def helper():\n    return 1\n")


def test_smk_and_snakefile_are_not_executable() -> None:
    assert not is_executable("code/workflows/x.smk", "rule a:\n    shell: 'echo'\n")
    assert not is_executable("code/workflows/Snakefile", "rule a:\n    shell: 'echo'\n")


def test_orphaned_executable_when_unreferenced() -> None:
    c = classify_code_file(
        "code/a.py",
        'if __name__ == "__main__":\n    pass\n',
        declared_decision_bearing=None,
        workflow_referenced=False,
    )
    assert c.classification == "orphaned-executable"
    assert c.effective_decision_bearing is True  # fail-closed default


def test_workflow_owned_executable_when_referenced() -> None:
    c = classify_code_file(
        "code/a.py",
        'if __name__ == "__main__":\n    pass\n',
        declared_decision_bearing=None,
        workflow_referenced=True,
    )
    assert c.classification == "workflow-owned-executable"
    assert c.effective_decision_bearing is False


def test_declared_non_decision_bearing_overrides_default() -> None:
    c = classify_code_file(
        "code/a.py",
        'if __name__ == "__main__":\n    pass\n',
        declared_decision_bearing=False,
        workflow_referenced=False,
    )
    assert c.classification == "orphaned-executable"
    assert c.effective_decision_bearing is False


def test_package_marker() -> None:
    c = classify_code_file(
        "code/pkg/__init__.py", "", declared_decision_bearing=None, workflow_referenced=False
    )
    assert c.classification == "package-marker"
    assert c.executable is False


def test_test_file_is_classified_test() -> None:
    c = classify_code_file(
        "code/tests/test_x.py",
        'if __name__ == "__main__":\n    pass\n',
        declared_decision_bearing=None,
        workflow_referenced=False,
    )
    assert c.classification == "test"


def test_workflow_definition_is_classified() -> None:
    c = classify_code_file(
        "code/workflows/main.smk",
        "rule a:\n    shell: 'echo'\n",
        declared_decision_bearing=None,
        workflow_referenced=False,
    )
    assert c.classification == "workflow-definition"


def test_non_executable_is_library() -> None:
    c = classify_code_file(
        "code/lib.py", "def f():\n    return 1\n", declared_decision_bearing=None, workflow_referenced=False
    )
    assert c.classification == "library"
