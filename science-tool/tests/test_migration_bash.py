"""Bash migration step runner: block-scalar requirement, working_dir, timeout."""

import pytest

from science_tool.project_artifacts.loader import RegistryLoadError, load_registry


def _registry_text(check_value: str, apply_value: str = "echo hi") -> str:
    """Render a tiny registry with one bash step."""
    return (
        "artifacts:\n"
        "  - name: x\n"
        "    source: data/x\n"
        "    install_target: x\n"
        "    description: d\n"
        "    content_type: text\n"
        "    newline: lf\n"
        "    mode: '0755'\n"
        "    consumer: direct_execute\n"
        "    header_protocol: {kind: shebang_comment, comment_prefix: '#'}\n"
        "    extension_protocol: {kind: sourced_sidecar, sidecar_path: x.local, hook_namespace: X}\n"
        "    mutation_policy: {}\n"
        "    version: '2026.04.26'\n"
        "    current_hash: " + "a" * 64 + "\n"
        "    migrations:\n"
        "      - from: '2026.04.20'\n"
        "        to: '2026.04.26'\n"
        "        kind: project_action\n"
        "        summary: x\n"
        "        steps:\n"
        "          - id: s1\n"
        "            description: d\n"
        "            touched_paths: ['x']\n"
        "            reversible: false\n"
        "            idempotent: true\n"
        "            impl:\n"
        "              kind: bash\n"
        "              shell: bash\n"
        "              working_dir: '.'\n"
        "              timeout_seconds: 5\n"
        f"              check: {check_value}\n"
        f"              apply: {apply_value}\n"
        "    previous_hashes: []\n"
        "    changelog: {'2026.04.26': 'x'}\n"
    )


def test_bash_check_must_be_block_scalar(tmp_path) -> None:
    """Plain-flow `check: ! grep ...` is rejected at load time."""
    p = tmp_path / "registry.yaml"
    p.write_text(_registry_text(check_value="exit 0"), encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="block scalar"):
        load_registry(p)


def test_bash_check_block_scalar_accepted(tmp_path) -> None:
    p = tmp_path / "registry.yaml"
    p.write_text(
        _registry_text(
            check_value="|\n                exit 0",
            apply_value="|\n                echo hi",
        ),
        encoding="utf-8",
    )
    reg = load_registry(p)
    assert reg.artifacts[0].migrations[0].steps[0].impl.kind == "bash"


def test_bash_step_runs_with_working_dir_and_timeout(tmp_path) -> None:
    """BashStepAdapter runs the script with declared working_dir + timeout."""
    from science_tool.project_artifacts.migrations.bash import BashStepAdapter
    from science_tool.project_artifacts.registry_schema import MigrationStep

    step = MigrationStep.model_validate(
        {
            "id": "s",
            "description": "d",
            "touched_paths": ["x"],
            "reversible": False,
            "idempotent": True,
            "impl": {
                "kind": "bash",
                "shell": "bash",
                "working_dir": ".",
                "timeout_seconds": 5,
                "check": "test -f x && exit 0 || exit 1\n",
                "apply": "touch x\n",
            },
        }
    )
    adapter = BashStepAdapter(step)
    assert adapter.check(tmp_path) is False  # x doesn't exist
    adapter.apply(tmp_path)
    assert adapter.check(tmp_path) is True  # x now exists
