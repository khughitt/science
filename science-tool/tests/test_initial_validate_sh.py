"""data/validate.sh: header valid, hook infra present, behavior preserved."""

import subprocess
from importlib import resources
from pathlib import Path

from science_tool.project_artifacts.hashing import body_hash
from science_tool.project_artifacts.header import parse_header
from science_tool.project_artifacts.loader import load_packaged_registry
from science_tool.project_artifacts.registry_schema import HeaderKind, HeaderProtocol

SHEBANG = HeaderProtocol(kind=HeaderKind.SHEBANG_COMMENT, comment_prefix="#")


def _canonical_path() -> Path:
    files = resources.files("science_tool.project_artifacts")
    with resources.as_file(files / "data" / "validate.sh") as p:
        return Path(p)


def test_canonical_exists_and_has_shebang() -> None:
    p = _canonical_path()
    assert p.exists()
    raw = p.read_bytes()
    assert raw.startswith(b"#!/usr/bin/env bash\n")


def test_canonical_header_parses() -> None:
    parsed = parse_header(_canonical_path().read_bytes(), SHEBANG)
    assert parsed is not None
    assert parsed.name == "validate.sh"


def test_current_hash_matches_body() -> None:
    raw = _canonical_path().read_bytes()
    expected = body_hash(raw, SHEBANG)
    reg = load_packaged_registry()
    art = next(a for a in reg.artifacts if a.name == "validate.sh")
    assert art.current_hash == expected


def test_canonical_contains_hook_infrastructure() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    assert "declare -A SCIENCE_VALIDATE_HOOKS" in text
    assert "register_validation_hook()" in text
    assert "dispatch_hook()" in text
    assert 'source "validate.local.sh"' in text


def test_canonical_runs_against_minimal_project(tmp_path: Path, monkeypatch: "object") -> None:
    """Smoke: bash data/validate.sh runs cleanly against a minimal Science project.

    The fixture is expanded to satisfy validate.sh's required-field and
    required-directory checks; we exit with science-tool absent by setting
    SCIENCE_VALIDATE_SKIP_DOTENV=1 (no .env probe) and pre-resolving via
    SCIENCE_TOOL_PATH pointing at this repo's science-tool.
    """
    (tmp_path / "science.yaml").write_text(
        "name: test-project\n"
        "profile: software\n"
        "created: 2026-04-26\n"
        "last_modified: 2026-04-26\n"
        "status: active\n"
        "summary: Minimal fixture for validate.sh smoke test.\n"
        "layout_version: 1\n"
        "knowledge_profiles:\n"
        "  local: local\n"
        "  curated: []\n",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("# Test\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
    (tmp_path / "doc").mkdir()
    (tmp_path / "specs").mkdir()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text("# Active tasks\n", encoding="utf-8")
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "src").mkdir()

    repo_root = Path(__file__).resolve().parents[2]
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(tmp_path),
        "SCIENCE_TOOL_PATH": str(repo_root / "science-tool"),
        "SCIENCE_VALIDATE_SKIP_DOTENV": "1",
    }
    # Inherit uv-related env so SCIENCE_TOOL_PATH is usable; keep a clean PATH otherwise.
    import os as _os

    for k in ("UV_CACHE_DIR", "UV_PYTHON", "UV_LINK_MODE"):
        if k in _os.environ:
            env[k] = _os.environ[k]
    # uv needs to be on PATH; if it's not in /usr/bin, augment.
    import shutil as _shutil

    uv_bin = _shutil.which("uv")
    if uv_bin:
        env["PATH"] = f"{Path(uv_bin).parent}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(_canonical_path())],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, f"validate.sh failed:\n{result.stdout}\n{result.stderr}"
