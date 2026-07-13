from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

import pytest

from science_tool.cli import main


ROOT = Path(__file__).resolve().parents[2]
PREAMBLE = ROOT / "references" / "command-preamble.md"
COMMAND_RE = re.compile(r"\buv run(?: --frozen)? science ([a-z][a-z0-9-]*)")
FLOOR_RE = re.compile(r"^\s*SCIENCE_REQUIRED_VERSION=(\d+\.\d+\.\d+)$", re.MULTILINE)


def _release(value: str) -> tuple[int, int, int]:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", value)
    assert match is not None, value
    return tuple(map(int, match.groups()))


def _compatibility_block() -> str:
    text = PREAMBLE.read_text(encoding="utf-8")
    marker = "SCIENCE_REQUIRED_VERSION=0.3.0"
    marker_at = text.index(marker)
    start = text.rindex("```bash\n", 0, marker_at) + len("```bash\n")
    end = text.index("\n```", marker_at)
    return textwrap.dedent(text[start:end]) + "\n"


# A REAL pre-baseline CLI: a Click group with no version_option. Click — not this
# test — produces the resulting `--version` diagnostic, so the gate is exercised
# against whatever wording the installed Click actually emits.
PREBASELINE_CLI = """import click


@click.group()
@click.option("--color")
def main(color: str | None = None) -> None:
    pass


main()
"""

# A REAL baseline CLI, matching the option Task 1 adds.
BASELINE_CLI = """import click


@click.group()
@click.version_option(version="{version}", prog_name="science", message="%(prog)s %(version)s")
@click.option("--color")
def main(color: str | None = None) -> None:
    pass


main()
"""

# A CLI whose --version succeeds but prints something unparseable.
MALFORMED_CLI = """import sys

if "--version" in sys.argv:
    print("science malformed")
    sys.exit(0)
sys.exit(0)
"""


def _fake_uv(tmp_path: Path) -> Path:
    # Stands in for uv only as a dispatcher. It never fabricates CLI output:
    # `science` invocations exec a real Python CLI whose behavior the test selects
    # by choosing which CLI source to install, not by echoing canned strings.
    executable = tmp_path / "bin" / "uv"
    executable.parent.mkdir(parents=True)
    executable.write_text(
        """#!/usr/bin/env bash
set -u
case "$*" in
  "run --frozen science --version")
    if [ -n "${SCIENCE_TEST_UV_ERROR:-}" ]; then
      printf '%s\\n' "$SCIENCE_TEST_UV_ERROR" >&2
      exit 2
    fi
    exec "$SCIENCE_TEST_PYTHON" "$SCIENCE_TEST_CLI" --version
    ;;
  "run --frozen science --help")
    if [ -n "${SCIENCE_TEST_UV_ERROR:-}" ]; then
      printf '%s\\n' "$SCIENCE_TEST_UV_ERROR" >&2
      exit 2
    fi
    exec "$SCIENCE_TEST_PYTHON" "$SCIENCE_TEST_CLI" --help
    ;;
  "run --no-project python -")
    exec "$SCIENCE_TEST_PYTHON" -
    ;;
esac
printf 'unexpected fake uv invocation: %s\\n' "$*" >&2
exit 99
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _run_gate(
    tmp_path: Path,
    *,
    cli_source: str | None = None,
    uv_error: str | None = None,
) -> subprocess.CompletedProcess[str]:
    fake_uv = _fake_uv(tmp_path)
    cli_path = tmp_path / "science_cli.py"
    cli_path.write_text(cli_source or PREBASELINE_CLI, encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_uv.parent}{os.pathsep}{env['PATH']}",
            "SCIENCE_TEST_PYTHON": sys.executable,
            "SCIENCE_TEST_CLI": str(cli_path),
        }
    )
    if uv_error is not None:
        env["SCIENCE_TEST_UV_ERROR"] = uv_error

    return subprocess.run(
        ["bash"],
        input=_compatibility_block(),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_real_prebaseline_cli_becomes_upgrade_message(tmp_path: Path) -> None:
    # The CLI runs (--help works) but has no --version. Click emits whatever
    # diagnostic the installed version emits; the gate must not depend on it.
    result = _run_gate(tmp_path, cli_source=PREBASELINE_CLI)

    assert result.returncode == 1
    assert "requires science >=0.3.0" in result.stderr
    assert "unknown-or-pre-0.3.0" in result.stderr
    assert "No such option" not in result.stderr


def test_uv_environment_failure_passes_through_verbatim(tmp_path: Path) -> None:
    # Both probes fail, because the environment — not the CLI's age — is broken.
    message = "error: Unable to find lockfile at `uv.lock`, but `--frozen` was provided."
    result = _run_gate(tmp_path, uv_error=message)

    assert result.returncode == 1
    assert message in result.stderr
    assert "upgrade-package" not in result.stderr


def test_malformed_version_output_is_blocked(tmp_path: Path) -> None:
    result = _run_gate(tmp_path, cli_source=MALFORMED_CLI)

    assert result.returncode == 1
    assert "requires science >=0.3.0" in result.stderr
    assert "upgrade-package science" in result.stderr


def test_below_floor_version_is_blocked(tmp_path: Path) -> None:
    result = _run_gate(tmp_path, cli_source=BASELINE_CLI.format(version="0.2.0"))

    assert result.returncode == 1
    assert "requires science >=0.3.0" in result.stderr
    assert "upgrade-package science" in result.stderr


@pytest.mark.parametrize(
    "version",
    ["0.3.0", "0.3.1rc1", "0.3.0.dev1", "0.3.0+g8bf7829", "0.4.0", "1.0.0"],
)
def test_floor_and_newer_suffixed_versions_pass(tmp_path: Path, version: str) -> None:
    result = _run_gate(tmp_path, cli_source=BASELINE_CLI.format(version=version))

    assert result.returncode == 0
    assert result.stderr == ""


def test_release_versions_and_command_floor_obey_contract() -> None:
    package = tomllib.loads((ROOT / "science" / "pyproject.toml").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    floor_match = FLOOR_RE.search(PREAMBLE.read_text(encoding="utf-8"))
    assert floor_match is not None

    package_version = package["project"]["version"]
    assert plugin["version"] == package_version
    assert _release(floor_match.group(1)) <= _release(package_version)


def test_commands_that_invoke_cli_load_the_shared_preamble() -> None:
    missing: list[str] = []
    for path in sorted((ROOT / "commands").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if COMMAND_RE.search(text) and "references/command-preamble.md" not in text:
            missing.append(path.relative_to(ROOT).as_posix())

    assert missing == []


def test_documented_top_level_commands_exist_in_current_cli() -> None:
    referenced: set[str] = set()
    for path in sorted((ROOT / "commands").glob("*.md")):
        referenced.update(COMMAND_RE.findall(path.read_text(encoding="utf-8")))

    assert referenced <= set(main.commands)
