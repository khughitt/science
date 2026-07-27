from __future__ import annotations

import subprocess
import sys
import zipfile
from importlib import resources
from pathlib import Path

import pytest

from science_model.data_products import build_catalog, load_catalog

from science_tool.graph.skill_inventory import (
    SkillInventoryError,
    build_skill_inventory,
    companion_section,
    load_skill_inventory,
    load_index_registry,
    parse_skill_frontmatter,
    real_skill_paths,
    resolve_companions,
    serialize_inventory,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_parse_frontmatter_reads_mapping() -> None:
    text = "---\nname: transcriptomics-scrna-qa\narchetype: measurement-qa\n---\n\nBody.\n"
    assert parse_skill_frontmatter(text) == {
        "name": "transcriptomics-scrna-qa",
        "archetype": "measurement-qa",
    }


def test_parse_frontmatter_missing_block() -> None:
    with pytest.raises(SkillInventoryError, match="frontmatter"):
        parse_skill_frontmatter("no frontmatter here\n")


def test_parse_frontmatter_rejects_duplicate_key() -> None:
    text = "---\nname: a\ncovers:\n  - data-product:x\ncovers:\n  - data-product:y\n---\n\nB\n"
    with pytest.raises(SkillInventoryError, match="duplicate"):
        parse_skill_frontmatter(text)


def test_parse_frontmatter_rejects_yaml_equivalent_duplicate_key() -> None:
    text = "---\n1: first\n01: second\n---\n\nB\n"
    with pytest.raises(SkillInventoryError, match="duplicate"):
        parse_skill_frontmatter(text)


def test_parse_frontmatter_rejects_merge_key() -> None:
    text = "---\nbase: &b\n  k: v\nname: <<\n<<: *b\n---\n\nB\n"
    with pytest.raises(SkillInventoryError, match="merge"):
        parse_skill_frontmatter(text)


def test_parse_frontmatter_rejects_nested_duplicate_key() -> None:
    text = "---\nname: a\nmeta:\n  k: 1\n  k: 2\n---\n\nB\n"
    with pytest.raises(SkillInventoryError, match="duplicate"):
        parse_skill_frontmatter(text)


def test_parse_frontmatter_non_mapping() -> None:
    with pytest.raises(SkillInventoryError, match="mapping"):
        parse_skill_frontmatter("---\n- just\n- a list\n---\n\nB\n")


def _write(root: Path, rel: str, body: str = "---\nname: x\n---\n\nB\n") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _write_corpus(
    root: Path, entries: list[tuple[str, str]], *, index_lines: list[str] | None = None
) -> None:
    for _sid, rel in entries:
        _write(root, rel)
    lines = index_lines if index_lines is not None else [f"- `{sid}`: `{rel}`" for sid, rel in entries]
    _write(root, "skills/INDEX.md", "---\nname: science-skill-index\n---\n\n" + "\n".join(lines) + "\n")


def test_registry_reads_pairs_in_index_order(tmp_path: Path) -> None:
    entries = [("bio", "skills/bio/SKILL.md"), ("bio-x-qa", "skills/bio/x-qa.md")]
    _write_corpus(tmp_path, entries)
    assert load_index_registry(tmp_path) == entries


def test_registry_ignores_unrelated_inline_code_bullet(tmp_path: Path) -> None:
    entries = [("bio", "skills/bio/SKILL.md")]
    _write_corpus(
        tmp_path,
        entries,
        index_lines=[
            "- `bio`: `skills/bio/SKILL.md`",
            "- `science tasks` inspects project work.",
        ],
    )
    assert load_index_registry(tmp_path) == entries


def test_real_skill_paths_excludes_index_and_templates(tmp_path: Path) -> None:
    _write(tmp_path, "skills/bio/x-qa.md")
    _write(tmp_path, "skills/INDEX.md")
    _write(tmp_path, "skills/meta/templates/router.md")
    assert real_skill_paths(tmp_path) == {"skills/bio/x-qa.md"}


def test_real_skill_paths_excludes_generated_distribution(tmp_path: Path) -> None:
    _write(tmp_path, "skills/bio/x-qa.md")
    _write(tmp_path, "skills/generated/INDEX.md")
    _write(tmp_path, "skills/generated/science-status/SKILL.md")

    assert real_skill_paths(tmp_path) == {"skills/bio/x-qa.md"}


def test_registry_rejects_duplicate_id(tmp_path: Path) -> None:
    _write(tmp_path, "skills/a.md")
    _write(tmp_path, "skills/b.md")
    _write_corpus(tmp_path, [], index_lines=["- `dup`: `skills/a.md`", "- `dup`: `skills/b.md`"])
    with pytest.raises(SkillInventoryError, match="duplicate INDEX id"):
        load_index_registry(tmp_path)


def test_registry_rejects_duplicate_path(tmp_path: Path) -> None:
    _write(tmp_path, "skills/a.md")
    _write_corpus(tmp_path, [], index_lines=["- `one`: `skills/a.md`", "- `two`: `skills/a.md`"])
    with pytest.raises(SkillInventoryError, match="duplicate INDEX path"):
        load_index_registry(tmp_path)


def test_registry_rejects_bad_grammar(tmp_path: Path) -> None:
    _write(tmp_path, "skills/a.md")
    _write_corpus(tmp_path, [], index_lines=["- `Bad_Id`: `skills/a.md`"])
    with pytest.raises(SkillInventoryError, match="grammar"):
        load_index_registry(tmp_path)


def test_registry_rejects_path_outside_skills(tmp_path: Path) -> None:
    _write(tmp_path, "docs/not-a-skill.md")
    _write_corpus(
        tmp_path,
        [],
        index_lines=["- `off-corpus`: `docs/not-a-skill.md`"],
    )
    with pytest.raises(SkillInventoryError, match="under 'skills/'"):
        load_index_registry(tmp_path)


def test_registry_rejects_traversal_path(tmp_path: Path) -> None:
    _write(tmp_path, "docs/not-a-skill.md")
    _write_corpus(
        tmp_path,
        [],
        index_lines=["- `escaping`: `skills/../docs/not-a-skill.md`"],
    )
    with pytest.raises(SkillInventoryError, match="safe repository-relative"):
        load_index_registry(tmp_path)


@pytest.mark.parametrize(
    "row",
    [
        "- `trailing`: `skills/a.md` trailing text",
        "- `unclosed`: `skills/a.md",
    ],
    ids=["trailing-junk", "unclosed-path"],
)
def test_registry_rejects_malformed_registry_row(tmp_path: Path, row: str) -> None:
    _write(tmp_path, "skills/a.md")
    _write_corpus(tmp_path, [], index_lines=[row])
    with pytest.raises(SkillInventoryError, match="malformed"):
        load_index_registry(tmp_path)


def test_registry_rejects_missing_path(tmp_path: Path) -> None:
    _write_corpus(tmp_path, [], index_lines=["- `ghost`: `skills/ghost.md`"])
    with pytest.raises(SkillInventoryError, match="does not exist"):
        load_index_registry(tmp_path)


def test_registry_rejects_orphan_skill(tmp_path: Path) -> None:
    _write(tmp_path, "skills/listed.md")
    _write(tmp_path, "skills/orphan.md")
    _write_corpus(tmp_path, [], index_lines=["- `listed`: `skills/listed.md`"])
    with pytest.raises(SkillInventoryError, match="missing from INDEX"):
        load_index_registry(tmp_path)


def test_registry_rejects_extra_non_skill(tmp_path: Path) -> None:
    _write(tmp_path, "skills/real.md")
    _write(tmp_path, "skills/meta/templates/router.md")
    _write_corpus(
        tmp_path,
        [],
        index_lines=[
            "- `real`: `skills/real.md`",
            "- `tmpl`: `skills/meta/templates/router.md`",
        ],
    )
    with pytest.raises(SkillInventoryError, match="not a real skill"):
        load_index_registry(tmp_path)


_PATH_TO_ID = {
    "skills/bio/transcriptomics/cohort-qa.md": "transcriptomics-cohort-qa",
    "skills/bio/transcriptomics/SKILL.md": "transcriptomics",
    "skills/statistics/compositional-data.md": "statistics-compositional-data",
}


def test_companion_section_extracts_only_that_section() -> None:
    text = "# T\n\n## Companion Skills\n\n- [`a`](a.md)\n\n## Next\n\n- not this\n"
    assert "- [`a`](a.md)" in companion_section(text)
    assert "not this" not in companion_section(text)


def test_resolve_companions_typed_targets(tmp_path: Path) -> None:
    section = (
        "- [`cohort-qa.md`](cohort-qa.md) - x\n"
        "- [`SKILL.md`](SKILL.md) - the router\n"
        "- [`compositional-data`](../../statistics/compositional-data.md#anchor) - y\n"
        "- [`index`](../../INDEX.md) - the index\n"
    )
    edges = resolve_companions(tmp_path, "skills/bio/transcriptomics/scrna-qa.md", section, _PATH_TO_ID)
    assert edges == [
        {"target": "transcriptomics-cohort-qa", "role": "leaf"},
        {"target": "transcriptomics", "role": "router"},
        {"target": "statistics-compositional-data", "role": "leaf"},
        {"target": "science-skill-index", "role": "index"},
    ]


def test_resolve_companions_rejects_broken_target(tmp_path: Path) -> None:
    with pytest.raises(SkillInventoryError, match="non-skill"):
        resolve_companions(
            tmp_path,
            "skills/bio/transcriptomics/scrna-qa.md",
            "- [`x`](../../nope/ghost.md)\n",
            _PATH_TO_ID,
        )


@pytest.mark.parametrize(
    "link",
    ["- [`anchor`](#qa)\n", "- [`empty`]()\n"],
    ids=["anchor-only", "empty"],
)
def test_resolve_companions_rejects_link_without_file_target(
    tmp_path: Path, link: str
) -> None:
    with pytest.raises(SkillInventoryError, match="file target"):
        resolve_companions(
            tmp_path,
            "skills/bio/transcriptomics/scrna-qa.md",
            link,
            _PATH_TO_ID,
        )


def test_resolve_companions_rejects_duplicate_target(tmp_path: Path) -> None:
    section = "- [`a`](cohort-qa.md)\n- [`a again`](cohort-qa.md)\n"
    with pytest.raises(SkillInventoryError, match="duplicate companion"):
        resolve_companions(tmp_path, "skills/bio/transcriptomics/scrna-qa.md", section, _PATH_TO_ID)


def test_resolve_companions_empty_section() -> None:
    assert resolve_companions(Path("/x"), "skills/a.md", "", _PATH_TO_ID) == []


def _catalog():
    return build_catalog({
        "schema_version": "1",
        "terms": [
            {"id": "data-product:gene-expression-single-cell", "label": "scRNA", "assay": "rna"},
            {"id": "data-product:somatic-variant", "label": "SNV", "assay": "dna"},
        ],
    })


def _leaf(name, archetype="measurement-qa", covers="", sources="", companions=""):
    fm = f"---\nname: {name}\ndescription: d for {name}\narchetype: {archetype}\n"
    fm += covers + sources + "---\n\nBody.\n\n## Companion Skills\n\n" + companions
    return fm


def _router(name):
    return f"---\nname: {name}\ndescription: router {name}\n---\n\nBody.\n\n## Companion Skills\n\n"


def _mkcorpus(root: Path) -> None:
    (root / "skills").mkdir(parents=True, exist_ok=True)
    _write(root, "skills/SKILL.md", _router("bio"))
    _write(root, "skills/scrna.md", _leaf(
        "scrna",
        covers="covers:\n  - data-product:gene-expression-single-cell\n",
        sources="sources: [scanpy]\n",
        companions="- [`somatic`](somatic.md) - x\n",
    ))
    _write(root, "skills/somatic.md", _leaf("somatic", covers="covers:\n  - data-product:somatic-variant\n"))
    _write(root, "skills/INDEX.md",
           "---\nname: science-skill-index\n---\n\n"
           "- `bio`: `skills/SKILL.md`\n- `scrna`: `skills/scrna.md`\n- `somatic`: `skills/somatic.md`\n")


def test_build_inventory_shape_and_order(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    inv = build_skill_inventory(tmp_path, _catalog())
    assert [s["id"] for s in inv["skills"]] == ["bio", "scrna", "somatic"]  # id-sorted
    bio = inv["skills"][0]
    assert bio["role"] == "router" and "archetype" not in bio and "covers" not in bio
    scrna = inv["skills"][1]
    assert scrna["role"] == "leaf"
    assert scrna["archetype"] == "measurement-qa"
    assert scrna["covers"] == ["data-product:gene-expression-single-cell"]
    assert scrna["sources"] == ["scanpy"]
    assert scrna["companions"] == [{"target": "somatic", "role": "leaf"}]
    somatic = inv["skills"][2]
    assert "sources" not in somatic  # absent -> omitted
    assert "companions" not in somatic  # empty section -> omitted


def test_build_inventory_keys_off_index_not_name(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    # Rewrite one leaf's frontmatter name to diverge from its INDEX id.
    p = tmp_path / "skills/scrna.md"
    p.write_text(p.read_text().replace("name: scrna", "name: totally-different"), encoding="utf-8")
    inv = build_skill_inventory(tmp_path, _catalog())
    scrna = next(s for s in inv["skills"] if s["id"] == "scrna")
    assert scrna["id"] == "scrna" and scrna["name"] == "totally-different"


def test_serialized_inventory_changes_when_corpus_changes(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    baseline = serialize_inventory(build_skill_inventory(tmp_path, _catalog()))
    p = tmp_path / "skills/somatic.md"
    p.write_text(
        p.read_text(encoding="utf-8").replace(
            "description: d for somatic", "description: changed"
        ),
        encoding="utf-8",
    )
    changed = serialize_inventory(build_skill_inventory(tmp_path, _catalog()))
    assert changed != baseline


def test_build_inventory_rejects_off_catalog_covers(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    p = tmp_path / "skills/scrna.md"
    p.write_text(p.read_text().replace(
        "data-product:gene-expression-single-cell", "data-product:not-a-term"), encoding="utf-8")
    with pytest.raises(SkillInventoryError, match="not in .*catalog"):
        build_skill_inventory(tmp_path, _catalog())


def test_build_inventory_rejects_duplicate_covers(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    p = tmp_path / "skills/scrna.md"
    p.write_text(p.read_text().replace(
        "covers:\n  - data-product:gene-expression-single-cell\n",
        "covers:\n  - data-product:gene-expression-single-cell\n  - data-product:gene-expression-single-cell\n",
    ), encoding="utf-8")
    with pytest.raises(SkillInventoryError, match="duplicate covers"):
        build_skill_inventory(tmp_path, _catalog())


def test_build_inventory_rejects_null_covers(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    p = tmp_path / "skills/scrna.md"
    p.write_text(p.read_text().replace(
        "covers:\n  - data-product:gene-expression-single-cell\n", "covers: null\n"), encoding="utf-8")
    with pytest.raises(SkillInventoryError, match="list of strings"):
        build_skill_inventory(tmp_path, _catalog())


def test_build_inventory_rejects_router_with_covers(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    p = tmp_path / "skills/SKILL.md"
    p.write_text(p.read_text().replace(
        "description: router bio\n", "description: router bio\ncovers:\n  - data-product:somatic-variant\n"),
        encoding="utf-8",
    )
    with pytest.raises(SkillInventoryError, match="router.*covers"):
        build_skill_inventory(tmp_path, _catalog())


def test_build_inventory_rejects_leaf_without_archetype(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    p = tmp_path / "skills/somatic.md"
    p.write_text(p.read_text().replace("archetype: measurement-qa\n", ""), encoding="utf-8")
    with pytest.raises(SkillInventoryError, match="archetype"):
        build_skill_inventory(tmp_path, _catalog())


def test_serialize_is_canonical(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    text = serialize_inventory(build_skill_inventory(tmp_path, _catalog()))
    assert text.endswith("\n")
    assert text == serialize_inventory(build_skill_inventory(tmp_path, _catalog()))  # deterministic


def test_committed_inventory_matches_regeneration() -> None:
    generated = serialize_inventory(build_skill_inventory(_REPO_ROOT, load_catalog()))
    committed = (
        resources.files("science_tool.graph")
        .joinpath("skill_inventory.json")
        .read_text(encoding="utf-8")
    )
    assert (
        generated == committed
    ), "skill_inventory.json is stale — run scripts/generate_skill_inventory.py"


def test_load_skill_inventory_round_trips() -> None:
    inv = load_skill_inventory()
    ids = [s["id"] for s in inv["skills"]]
    assert ids == sorted(ids)  # canonical-id order
    assert "transcriptomics-scrna-qa" in ids
    scrna = next(s for s in inv["skills"] if s["id"] == "transcriptomics-scrna-qa")
    assert scrna["covers"] == ["data-product:gene-expression-single-cell"]


def test_load_skill_inventory_rejects_missing_skills(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "skill_inventory.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(resources, "files", lambda _package: tmp_path)
    with pytest.raises(SkillInventoryError, match="skills"):
        load_skill_inventory()


@pytest.mark.packaging
def test_installed_wheel_loads_inventory(tmp_path: Path) -> None:
    # Build the wheel and confirm the resource is packaged...
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=_REPO_ROOT / "science",
        check=True,
    )
    wheel = next(tmp_path.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        assert any(
            n.endswith("science_tool/graph/skill_inventory.json")
            for n in archive.namelist()
        )
    # ...then prove the INSTALLED loader resolves it without a network-dependent dependency
    # installation. Install only the wheel into an isolated target; the subprocess uses the
    # current test interpreter for dependencies but prepends that target and asserts science_tool
    # itself came from it. A cwd outside the source tree prevents accidental corpus-relative reads.
    site = tmp_path / "site"
    subprocess.run(
        ["uv", "pip", "install", "--target", str(site), "--no-deps", str(wheel)],
        check=True,
    )
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "site = Path(sys.argv[1]).resolve()\n"
        "sys.path.insert(0, str(site))\n"
        "import science_tool\n"
        "from science_tool.graph.skill_inventory import load_skill_inventory\n"
        "assert Path(science_tool.__file__).resolve().is_relative_to(site)\n"
        "print(len(load_skill_inventory()['skills']))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(site)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "60"
