from pathlib import Path

import pytest
from pydantic import ValidationError

from science_tool.project_config import (
    PlanReproducibilityPolicy,
    ProjectConfig,
    ProjectRole,
    ReproducibilityPolicyConfig,
    ReproducibilityWaiver,
    effective_reproducibility_policy,
    load_plan_reproducibility_policy,
    load_project_config,
    validated_entity_schema_version,
)


def test_loads_minimal_existing_yaml(tmp_path: Path) -> None:
    """An existing science.yaml without new fields must still load."""
    project_root = tmp_path / "cbioportal"
    project_root.mkdir()
    yaml_text = """
name: cbioportal
created: "2025-02-21"
profile: research
research_question: "What is the structure of somatic mutations across cancers?"
"""
    (project_root / "science.yaml").write_text(yaml_text)

    cfg = load_project_config(project_root)
    assert cfg.name == "cbioportal"
    assert cfg.id == "cbioportal"
    assert cfg.role == "standalone"
    assert cfg.peers == []


def test_explicit_id_role_peers(tmp_path: Path) -> None:
    yaml_text = """
name: cbioportal
id: cbioportal
role: data-source
profile: research
research_question: "..."
peers:
  - id: meta
    path: ~/d/cancer/meta
"""
    (tmp_path / "science.yaml").write_text(yaml_text)
    cfg = load_project_config(tmp_path)
    assert cfg.role == ProjectRole.DATA_SOURCE
    assert cfg.peers[0].id == "meta"
    assert cfg.peers[0].path == "~/d/cancer/meta"


def test_meta_with_peers_manifest(tmp_path: Path) -> None:
    yaml_text = """
name: meta
id: meta
role: meta
profile: research
research_question: "Umbrella: cancer + pre-cancer."
peers:
  - id: cbioportal
    path: ~/d/cancer/data-sources/cbioportal
  - id: multiple-myeloma
    path: ~/d/cancer/cancer-types/multiple-myeloma
"""
    (tmp_path / "science.yaml").write_text(yaml_text)
    cfg = load_project_config(tmp_path)
    assert cfg.role == ProjectRole.META
    assert len(cfg.peers) == 2
    assert cfg.peers[0].id == "cbioportal"
    assert cfg.peers[0].path == "~/d/cancer/data-sources/cbioportal"


def test_role_string_extensible(tmp_path: Path) -> None:
    """Unknown roles are accepted but normalized as raw strings (vocabulary is extensible)."""
    yaml_text = """
name: foo
id: foo
role: model-system
profile: research
research_question: "..."
"""
    (tmp_path / "science.yaml").write_text(yaml_text)
    cfg = load_project_config(tmp_path)
    assert cfg.role == "model-system"


def test_project_config_accepts_peers(tmp_path: Path) -> None:
    """`peers:` is a list of {id, path}; loaded as PeerEntry objects."""
    project_root = tmp_path / "host"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: mm30
    path: ~/d/cancer/mm30
  - id: lit-explore
    path: ../../r/lit-explore
""",
        encoding="utf-8",
    )
    cfg = load_project_config(project_root)
    assert len(cfg.peers) == 2
    assert cfg.peers[0].id == "mm30"
    assert cfg.peers[0].path == "~/d/cancer/mm30"
    assert cfg.peers[1].id == "lit-explore"
    assert cfg.peers[1].path == "../../r/lit-explore"


def test_project_config_peers_default_empty(tmp_path: Path) -> None:
    """A config without peers: gets an empty list."""
    project_root = tmp_path / "host"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
""",
        encoding="utf-8",
    )
    cfg = load_project_config(project_root)
    assert cfg.peers == []


def test_peer_entry_accepts_unknown_fields_for_forward_compat(tmp_path: Path) -> None:
    """Reserved fields (git, url, etc.) parse without raising; surfaced by validator."""
    project_root = tmp_path / "host"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: future-peer
    path: ./somewhere
    git: https://github.com/example/future-peer
""",
        encoding="utf-8",
    )
    cfg = load_project_config(project_root)
    assert cfg.peers[0].id == "future-peer"


def test_project_config_rejects_removed_parent_field(tmp_path: Path) -> None:
    """parent: is removed; loading a config with it must fail clearly."""
    project_root = tmp_path / "host"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
parent: ../meta
""",
        encoding="utf-8",
    )
    with pytest.raises(
        ValidationError,
        match=r"Use `peers:` instead; `parent:` and `children:` are removed project-config fields\.",
    ):
        load_project_config(project_root)


def test_load_plan_reproducibility_policy_from_frontmatter(tmp_path: Path):
    p = tmp_path / "plan.md"
    p.write_text(
        '---\nid: "plan:x"\nkind: "plan"\ntitle: "X"\n'
        "reproducibility_policy:\n"
        '  bar: "trust-based-output"\n'
        "  waivers:\n"
        '    - dataset: "dataset:n3c"\n'
        '      accepted_class: "trust-based-output"\n'
        '      decision_date: "2026-07-01"\n---\n',
        encoding="utf-8",
    )
    pol = load_plan_reproducibility_policy(p)
    assert pol is not None and pol.bar == "trust-based-output"
    assert pol.waivers[0].dataset == "dataset:n3c"


def test_load_plan_policy_absent_is_none(tmp_path: Path):
    p = tmp_path / "plain.md"
    p.write_text('---\nid: "plan:y"\nkind: "plan"\ntitle: "Y"\n---\n', encoding="utf-8")
    assert load_plan_reproducibility_policy(p) is None


def test_project_config_parses_reproducibility_policy():
    cfg = ProjectConfig.model_validate(
        {
            "name": "demo",
            "reproducibility_policy": {"bar": "credentialed-reproducible", "unknown": "warn"},
        }
    )
    assert cfg.reproducibility_policy.bar == "credentialed-reproducible"
    assert cfg.reproducibility_policy.unknown == "warn"
    assert cfg.reproducibility_policy.below_bar == "halt"  # default


def test_absent_policy_is_none():
    cfg = ProjectConfig.model_validate({"name": "demo"})
    assert cfg.reproducibility_policy is None


def test_effective_policy_plan_overrides_project():
    project = ReproducibilityPolicyConfig(bar="third-party-reproducible")
    plan = PlanReproducibilityPolicy(bar="trust-based-output")
    eff = effective_reproducibility_policy(project, plan)
    assert eff.bar == "trust-based-output"
    assert eff.unknown == "halt"  # inherited from project default


def test_effective_policy_plan_only_opts_in():
    plan = PlanReproducibilityPolicy(bar="third-party-reproducible")
    eff = effective_reproducibility_policy(None, plan)
    assert eff is not None and eff.bar == "third-party-reproducible"


def test_effective_policy_none_when_both_absent():
    assert effective_reproducibility_policy(None, None) is None


def test_waiver_requires_dataset_and_class():
    w = ReproducibilityWaiver(dataset="dataset:x", accepted_class="trust-based-output")
    assert w.dataset == "dataset:x"


def test_refs_config_defaults_when_absent(tmp_path):
    """ProjectConfig.refs is None when science.yaml omits the section."""
    from science_tool.project_config import load_project_config

    (tmp_path / "science.yaml").write_text("name: test-project\nprofile: research\n", encoding="utf-8")
    config = load_project_config(tmp_path)
    assert config.refs is None


def test_refs_config_parses_graph_truth_source(tmp_path):
    """`refs.entity_index_source: knowledge_graph` parses to the enum value."""
    from science_tool.project_config import EntityIndexSource, load_project_config

    (tmp_path / "science.yaml").write_text(
        "name: test-project\nprofile: research\n"
        "refs:\n"
        "  entity_index_source: knowledge_graph\n"
        "  scan_roots: [tasks, papers, core]\n",
        encoding="utf-8",
    )
    config = load_project_config(tmp_path)
    assert config.refs is not None
    assert config.refs.entity_index_source == EntityIndexSource.KNOWLEDGE_GRAPH
    assert config.refs.scan_roots == ["tasks", "papers", "core"]


def test_refs_config_default_source_is_frontmatter(tmp_path):
    """`refs:` block with only scan_roots defaults source to frontmatter."""
    from science_tool.project_config import EntityIndexSource, load_project_config

    (tmp_path / "science.yaml").write_text(
        "name: test-project\nprofile: research\nrefs:\n  scan_roots: [tasks]\n",
        encoding="utf-8",
    )
    config = load_project_config(tmp_path)
    assert config.refs is not None
    assert config.refs.entity_index_source == EntityIndexSource.FRONTMATTER
    assert config.refs.scan_roots == ["tasks"]


def test_refs_config_rejects_unknown_source(tmp_path):
    """`refs.entity_index_source` rejects unknown values via Pydantic validation."""
    from pydantic import ValidationError

    from science_tool.project_config import load_project_config

    (tmp_path / "science.yaml").write_text(
        "name: test-project\nprofile: research\nrefs:\n  entity_index_source: rdfox\n",
        encoding="utf-8",
    )
    try:
        load_project_config(tmp_path)
    except ValidationError:
        return
    raise AssertionError("Expected ValidationError for unknown source")


def test_project_config_rejects_removed_children_field(tmp_path: Path) -> None:
    """children: is removed; loading a config with it must fail clearly."""
    project_root = tmp_path / "meta"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: ../a
""",
        encoding="utf-8",
    )
    with pytest.raises(
        ValidationError,
        match=r"Use `peers:` instead; `parent:` and `children:` are removed project-config fields\.",
    ):
        load_project_config(project_root)


def _config(tmp_path: Path, body: str) -> Path:
    project_root = tmp_path / "proj"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        f"name: proj\nprofile: research\n{body}", encoding="utf-8"
    )
    return project_root


def test_entity_schema_version_is_the_authored_pin(tmp_path: Path) -> None:
    # Absent means 1 -- unmigrated -- and absence is the ONLY thing that may mean it. Nothing
    # infers the version from the shape of the project's files.
    assert load_project_config(_config(tmp_path, "")).entity_schema_version is None


def test_entity_schema_version_rejects_a_version_that_does_not_exist(tmp_path: Path) -> None:
    # The vocabulary is closed to the versions that EXIST. An unconstrained `int` would make `4` a
    # silent no-op -- accepted, meaningless, and indistinguishable from a real pin.
    with pytest.raises(ValidationError):
        load_project_config(_config(tmp_path, "entity_schema_version: 4\n"))


def test_generation_3_is_accepted() -> None:
    assert validated_entity_schema_version({"entity_schema_version": 3}) == 3


def test_generation_3_as_string_is_rejected() -> None:
    with pytest.raises(Exception):
        validated_entity_schema_version({"entity_schema_version": "3"})


def test_a_MISSPELLED_pin_is_refused_not_preserved(tmp_path: Path) -> None:
    """THE fail-silent this guard exists to close.

    `ProjectConfig` is `extra="allow"`, so `entity_schema_verison: 2` would otherwise be accepted,
    preserved in `model_extra`, and ignored -- leaving the project on schema 1, unvalidated, while
    its author believed it had migrated. Declaring the field does NOT catch this; only refusing the
    near-miss does.
    """
    with pytest.raises(ValidationError, match=r"did you mean 'entity_schema_version'"):
        load_project_config(_config(tmp_path, "entity_schema_verison: 2\n"))


def test_an_UNKNOWN_key_is_still_allowed(tmp_path: Path) -> None:
    # The guard refuses NEAR-MISSES, not unknowns. `extra="allow"` is deliberate: real science.yaml
    # files carry project-owned keys this model has no opinion about (`summary`, `tags`, `aspects`,
    # `layout_version`, ...), and every loadable config in the corpus does. A guard that rejected
    # unknown keys outright would refuse the entire corpus.
    cfg = load_project_config(_config(tmp_path, "summary: a project\ntags: [x]\n"))
    assert cfg.model_extra is not None and cfg.model_extra["summary"] == "a project"
