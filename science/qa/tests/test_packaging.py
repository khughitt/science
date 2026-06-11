import subprocess
import sys


def test_module_entry_point_runs():
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "run" in result.stdout


def test_science_qa_does_not_import_science_tool():
    # The runtime must stay light: importing science_qa must not pull science_tool.
    code = "import science_qa, sys; assert 'science_tool' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
