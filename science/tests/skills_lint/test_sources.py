import datetime
from pathlib import Path

from science_tool.skills_lint.sources import (
    iso_date,
    leaf_source_refs,
    load_sources,
    validate_record,
)

GIT_OK = {
    "title": "Baygent Skills",
    "authors": ["Alexandre Andorra"],
    "url": "https://github.com/Learning-Bayesian-Statistics/baygent-skills",
    "kind": "skill-repo",
    "license": "MIT",
    "upstream_ref": "a" * 40,
    "last_checked": "2026-07-18",
}
REF_OK = {
    "title": "Causal Inference: What If",
    "authors": ["Hernán", "Robins"],
    "url": "https://doi.org/10.1201/9781420076615",
    "kind": "book",
    "last_checked": "2026-07-18",
}


def test_valid_git_backed_record_has_no_problems() -> None:
    assert validate_record("baygent-skills", GIT_OK) == []


def test_valid_reference_record_without_license_ok() -> None:
    assert validate_record("whatif", REF_OK) == []


def test_missing_url_is_a_problem() -> None:
    raw = {k: v for k, v in GIT_OK.items() if k != "url"}
    assert any("url" in p for p in validate_record("x", raw))


def test_non_https_url_is_a_problem() -> None:
    assert any("https" in p for p in validate_record("x", {**GIT_OK, "url": "http://github.com/a/b"}))


def test_url_without_hostname_is_a_problem() -> None:
    assert any("hostname" in p for p in validate_record("x", {**GIT_OK, "url": "https:foo"}))


def test_abbreviated_upstream_ref_rejected() -> None:
    assert any("upstream_ref" in p for p in validate_record("x", {**GIT_OK, "upstream_ref": "aa940481"}))


def test_non_github_git_backed_host_rejected_in_loader() -> None:
    assert any("host" in p for p in validate_record("x", {**GIT_OK, "url": "https://gitlab.com/a/b"}))


def test_git_backed_missing_license_rejected() -> None:
    raw = {k: v for k, v in GIT_OK.items() if k != "license"}
    assert any("license" in p for p in validate_record("x", raw))


def test_reference_with_upstream_ref_rejected() -> None:
    assert any("upstream_ref" in p for p in validate_record("x", {**REF_OK, "upstream_ref": "b" * 40}))


def test_unknown_key_rejected() -> None:
    assert any("unknown" in p.lower() for p in validate_record("x", {**GIT_OK, "bogus": 1}))


def test_invalid_kind_rejected() -> None:
    assert any("kind" in p for p in validate_record("x", {**GIT_OK, "kind": "blog"}))


def test_malformed_doi_rejected() -> None:
    assert any("doi" in p for p in validate_record("x", {**REF_OK, "doi": "not-a-doi"}))


def test_wellformed_doi_accepted() -> None:
    assert validate_record("x", {**REF_OK, "doi": "10.7326/M16-2607"}) == []


def test_malformed_isbn_rejected() -> None:
    assert any("isbn" in p for p in validate_record("x", {**REF_OK, "isbn": "123"}))


def test_wellformed_isbn_accepted() -> None:
    assert validate_record("x", {**REF_OK, "isbn": "978-1-119-18684-7"}) == []


def test_malformed_arxiv_rejected() -> None:
    assert any("arxiv" in p for p in validate_record("x", {**REF_OK, "arxiv": "nope"}))


def test_non_string_optional_field_rejected() -> None:
    assert any("notes" in p for p in validate_record("x", {**REF_OK, "notes": 5}))


def test_non_string_identifier_rejected() -> None:
    assert any("doi" in p for p in validate_record("x", {**REF_OK, "doi": 123}))


def test_iso_date_coerces_python_date() -> None:
    assert iso_date(datetime.date(2026, 7, 18)) == "2026-07-18"
    assert iso_date("2026-07-18") == "2026-07-18"
    assert iso_date("not-a-date") is None


def test_load_sources_records_errors_and_declared_ids(tmp_path: Path) -> None:
    (tmp_path / "sources.yaml").write_text(
        "good:\n"
        "  title: Good\n  authors: [A]\n  url: https://doi.org/x\n"
        "  kind: paper\n  last_checked: 2026-07-18\n"
        "bad:\n"
        "  title: Bad\n  authors: [A]\n  kind: paper\n  last_checked: 2026-07-18\n",  # missing url
        encoding="utf-8",
    )
    reg = load_sources(tmp_path / "sources.yaml")
    assert "good" in reg.records
    assert "bad" not in reg.records
    assert "bad" in reg.errors and reg.errors["bad"]  # aggregated per id
    assert reg.declared_ids == frozenset({"good", "bad"})


def test_load_sources_missing_file_is_empty(tmp_path: Path) -> None:
    reg = load_sources(tmp_path / "sources.yaml")
    assert reg.records == {} and reg.errors == {} and reg.declared_ids == frozenset()


def test_leaf_source_refs_reads_list(tmp_path: Path) -> None:
    leaf = tmp_path / "leaf.md"
    leaf.write_text("---\nname: x\ndescription: y\nsources: [a, b]\n---\n# X\n", encoding="utf-8")
    assert leaf_source_refs(leaf) == (["a", "b"], None)


def test_leaf_source_refs_flags_non_list(tmp_path: Path) -> None:
    leaf = tmp_path / "leaf.md"
    leaf.write_text("---\nname: x\ndescription: y\nsources: nope\n---\n# X\n", encoding="utf-8")
    refs, error = leaf_source_refs(leaf)
    assert refs is None and error is not None


def test_leaf_without_sources_returns_none(tmp_path: Path) -> None:
    leaf = tmp_path / "leaf.md"
    leaf.write_text("---\nname: x\ndescription: y\n---\n# X\n", encoding="utf-8")
    assert leaf_source_refs(leaf) == (None, None)
