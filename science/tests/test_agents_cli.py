from __future__ import annotations

import os
import shutil
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from science_tool.agents_cli import (
    AgentName,
    InstallPlan,
    InstallScope,
    LinkSpec,
    agents_group,
    apply_install_plan,
    build_install_plan,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def generated_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "toolkit"
    (repo / "skills").mkdir(parents=True)
    (repo / "skills" / "INDEX.md").write_text("# Skills\n", encoding="utf-8")
    shutil.copytree(ROOT / "skills" / "generated", repo / "skills" / "generated")
    shutil.copytree(ROOT / "commands" / "opencode", repo / "commands" / "opencode")
    (repo / "references").mkdir()
    (repo / "references" / "command-preamble.md").write_text(
        "# Command Preamble\n",
        encoding="utf-8",
    )
    (repo / "aspects").mkdir()
    return repo


def _build_plan(
    generated_repo: Path,
    tmp_path: Path,
    *,
    agent: AgentName = "codex",
    scope: InstallScope = "project",
) -> InstallPlan:
    return build_install_plan(
        repo_root=generated_repo,
        agent=agent,
        scope=scope,
        project_dir=tmp_path / "project",
        user_home=tmp_path / "home",
    )


@pytest.mark.parametrize("agent", ["codex", "crush", "opencode"])
@pytest.mark.parametrize("scope", ["project", "user"])
def test_install_plan_contains_complete_skill_set_and_support_package(
    generated_repo: Path,
    tmp_path: Path,
    agent: AgentName,
    scope: InstallScope,
) -> None:
    plan = build_install_plan(
        repo_root=generated_repo,
        agent=agent,
        scope=scope,
        project_dir=tmp_path / "project",
        user_home=tmp_path / "home",
    )
    base = (
        tmp_path / "project" / ".agents" / "skills"
        if scope == "project"
        else tmp_path / "home" / ".agents" / "skills"
    )
    expected_skills = tuple(
        LinkSpec(source=package.resolve(), destination=base / package.name)
        for package in sorted((generated_repo / "skills" / "generated").glob("science-*"))
        if (package / "SKILL.md").is_file()
    )

    assert plan.links[: len(expected_skills)] == expected_skills
    assert base / "science-command-preamble" in {link.destination for link in plan.links}


@pytest.mark.parametrize("scope", ["project", "user"])
def test_opencode_plan_contains_complete_command_set(
    generated_repo: Path,
    tmp_path: Path,
    scope: InstallScope,
) -> None:
    plan = build_install_plan(
        repo_root=generated_repo,
        agent="opencode",
        scope=scope,
        project_dir=tmp_path / "project",
        user_home=tmp_path / "home",
    )
    base = (
        tmp_path / "project" / ".opencode" / "commands"
        if scope == "project"
        else tmp_path / "home" / ".config" / "opencode" / "commands"
    )
    expected_commands = tuple(
        LinkSpec(source=adapter.resolve(), destination=base / adapter.name)
        for adapter in sorted((generated_repo / "commands" / "opencode").glob("science-*.md"))
    )

    assert plan.links[-len(expected_commands) :] == expected_commands


@pytest.mark.parametrize("agent", ["codex", "crush"])
def test_non_opencode_plans_contain_no_command_links(
    generated_repo: Path,
    tmp_path: Path,
    agent: AgentName,
) -> None:
    plan = build_install_plan(
        repo_root=generated_repo,
        agent=agent,
        scope="project",
        project_dir=tmp_path / "project",
        user_home=tmp_path / "home",
    )

    assert all(link.source.parent.name != "opencode" for link in plan.links)


@pytest.mark.parametrize("agent", ["codex", "crush", "opencode"])
def test_missing_support_package_fails_before_creating_destinations(
    generated_repo: Path,
    tmp_path: Path,
    agent: AgentName,
) -> None:
    shutil.rmtree(generated_repo / "skills" / "generated" / "science-command-preamble")

    with pytest.raises(click.ClickException, match="science-command-preamble"):
        _build_plan(generated_repo, tmp_path, agent=agent)

    assert not (tmp_path / "project").exists()
    assert not (tmp_path / "home").exists()


@pytest.mark.parametrize(
    ("skill_text", "message"),
    [
        (
            "---\nname: science-not-status\ndescription: mismatch\n---\n",
            "name does not match",
        ),
        (
            "---\nname: [\n---\n",
            "invalid generated skill frontmatter",
        ),
    ],
)
def test_invalid_skill_frontmatter_fails_before_creating_destinations(
    generated_repo: Path,
    tmp_path: Path,
    skill_text: str,
    message: str,
) -> None:
    (generated_repo / "skills" / "generated" / "science-status" / "SKILL.md").write_text(
        skill_text,
        encoding="utf-8",
    )

    with pytest.raises(click.ClickException, match=message):
        _build_plan(generated_repo, tmp_path)

    assert not (tmp_path / "project").exists()


def test_opencode_adapter_without_matching_skill_fails_before_writes(
    generated_repo: Path,
    tmp_path: Path,
) -> None:
    (generated_repo / "commands" / "opencode" / "science-does-not-exist.md").write_text(
        "---\ndescription: invalid adapter\n---\n",
        encoding="utf-8",
    )

    with pytest.raises(click.ClickException, match="has no matching generated skill"):
        _build_plan(generated_repo, tmp_path, agent="opencode")

    assert not (tmp_path / "project").exists()


@pytest.mark.parametrize("collision_kind", ["file", "directory", "symlink", "dangling_symlink"])
def test_destination_collisions_are_preserved(
    generated_repo: Path,
    tmp_path: Path,
    collision_kind: str,
) -> None:
    destination = tmp_path / "project" / ".agents" / "skills" / "science-status"
    destination.parent.mkdir(parents=True)
    original_bytes = b"user-owned sentinel\x00bytes"
    external_target = tmp_path / "external-target"

    if collision_kind == "file":
        destination.write_bytes(original_bytes)
        sentinel = destination
    elif collision_kind == "directory":
        destination.mkdir()
        sentinel = destination / "sentinel.bin"
        sentinel.write_bytes(original_bytes)
    elif collision_kind == "symlink":
        external_target.write_bytes(original_bytes)
        destination.symlink_to(external_target)
        sentinel = external_target
    else:
        destination.symlink_to(external_target)
        sentinel = None

    original_link_target = destination.readlink() if destination.is_symlink() else None

    with pytest.raises(click.ClickException, match="destination collision"):
        _build_plan(generated_repo, tmp_path)

    if sentinel is not None:
        assert sentinel.read_bytes() == original_bytes
    if original_link_target is not None:
        assert destination.is_symlink()
        assert destination.readlink() == original_link_target
    assert not (destination.parent / "science-add-hypothesis").exists()


def test_literal_relative_link_to_correct_source_is_a_preserved_collision(
    generated_repo: Path,
    tmp_path: Path,
) -> None:
    first_plan = _build_plan(generated_repo, tmp_path)
    status_link = next(
        link for link in first_plan.links if link.destination.name == "science-status"
    )
    status_link.destination.parent.mkdir(parents=True)
    relative_target = Path(os.path.relpath(status_link.source, status_link.destination.parent))
    status_link.destination.symlink_to(relative_target)

    with pytest.raises(click.ClickException, match="destination collision"):
        _build_plan(generated_repo, tmp_path)

    assert status_link.destination.readlink() == relative_target


def test_all_destination_collisions_are_reported_together(
    generated_repo: Path,
    tmp_path: Path,
) -> None:
    destination_root = tmp_path / "project" / ".agents" / "skills"
    destination_root.mkdir(parents=True)
    collisions = (
        destination_root / "science-add-hypothesis",
        destination_root / "science-status",
    )
    for collision in collisions:
        collision.write_bytes(b"preserve")

    with pytest.raises(click.ClickException) as error:
        _build_plan(generated_repo, tmp_path)

    assert "destination collision" in error.value.message
    assert all(str(collision) in error.value.message for collision in collisions)
    assert all(collision.read_bytes() == b"preserve" for collision in collisions)


def test_late_collision_is_found_before_first_link_is_created(
    generated_repo: Path,
    tmp_path: Path,
) -> None:
    destination_root = tmp_path / "project" / ".agents" / "skills"
    destination_root.mkdir(parents=True)
    first_destination = destination_root / "science-add-hypothesis"
    later_collision = destination_root / "science-status"
    later_collision.write_bytes(b"preserve")

    with pytest.raises(click.ClickException, match="destination collision"):
        _build_plan(generated_repo, tmp_path)

    assert not first_destination.exists()
    assert later_collision.read_bytes() == b"preserve"


@pytest.mark.parametrize("ancestor_kind", ["file", "symlink"])
def test_opencode_parent_collision_cannot_redirect_or_partially_install(
    generated_repo: Path,
    tmp_path: Path,
    ancestor_kind: str,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    opencode_root = project / ".opencode"
    external_target = tmp_path / "external"
    if ancestor_kind == "file":
        opencode_root.write_bytes(b"preserve")
    else:
        external_target.mkdir()
        opencode_root.symlink_to(external_target, target_is_directory=True)

    with pytest.raises(click.ClickException, match="destination collision"):
        _build_plan(generated_repo, tmp_path, agent="opencode")

    assert not (project / ".agents").exists()
    if ancestor_kind == "file":
        assert opencode_root.read_bytes() == b"preserve"
    else:
        assert opencode_root.is_symlink()
        assert not tuple(external_target.iterdir())


def test_apply_creates_literal_absolute_links_and_reinstall_is_idempotent(
    generated_repo: Path,
    tmp_path: Path,
) -> None:
    plan = build_install_plan(
        repo_root=generated_repo,
        agent="opencode",
        scope="user",
        project_dir=tmp_path / "project",
        user_home=tmp_path / "home",
    )

    installed = apply_install_plan(plan)

    assert installed == plan.links
    assert not plan.current
    assert all(link.source.is_absolute() and link.source.exists() for link in installed)
    assert all(
        link.destination.is_symlink() and link.destination.readlink() == link.source
        for link in installed
    )

    second_plan = build_install_plan(
        repo_root=generated_repo,
        agent="opencode",
        scope="user",
        project_dir=tmp_path / "project",
        user_home=tmp_path / "home",
    )

    assert second_plan.current == second_plan.links
    assert apply_install_plan(second_plan) == ()


def test_install_cli_defaults_to_project_scope_and_reports_counts(
    generated_repo: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "consumer"
    runner = CliRunner()
    args = [
        "install",
        "--agent",
        "codex",
        "--repo-root",
        str(generated_repo),
        "--project-dir",
        str(project),
    ]

    first = runner.invoke(agents_group, args)
    second = runner.invoke(agents_group, args)

    assert first.exit_code == 0, first.output
    assert "Installed 53 links; 0 already current" in first.output
    assert second.exit_code == 0, second.output
    assert "Installed 0 links; 53 already current" in second.output
    assert (project / ".agents" / "skills" / "science-command-preamble").is_symlink()
    assert not (project / ".codex").exists()


def test_install_cli_invalid_repository_fails_before_writes(tmp_path: Path) -> None:
    project = tmp_path / "consumer"

    result = CliRunner().invoke(
        agents_group,
        [
            "install",
            "--agent",
            "codex",
            "--repo-root",
            str(tmp_path / "not-a-toolkit"),
            "--project-dir",
            str(project),
        ],
    )

    assert result.exit_code == 1
    assert "Error: not a Science toolkit root" in result.output
    assert not project.exists()


@pytest.mark.parametrize("removed_option", ["--copy", "--no-symlink"])
def test_install_cli_rejects_removed_copy_options(removed_option: str) -> None:
    result = CliRunner().invoke(
        agents_group,
        ["install", "--agent", "codex", removed_option],
    )

    assert result.exit_code == 2
    assert f"No such option: {removed_option}" in result.output


@pytest.mark.parametrize(
    "removed_options",
    [
        ["--agent", "codex"],
        ["--format", "agents"],
        ["--output-dir", "generated"],
    ],
)
def test_generate_cli_rejects_removed_generation_options(removed_options: list[str]) -> None:
    result = CliRunner().invoke(agents_group, ["generate", *removed_options])

    assert result.exit_code == 2
    assert f"No such option: {removed_options[0]}" in result.output
