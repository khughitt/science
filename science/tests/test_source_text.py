"""Tests for the .source.md anchor-surface module (Phase 1)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from science_tool.annotation.source_text import (
    Passage,
    PassageOffset,
    ResolvedPaper,
    SourcePassages,
    SourceTextError,
    is_whitelisted,
    parse_bioc_passages,
    render_source_md,
    resolve_license,
    resolve_paper_entity,
    verify_offset_map,
)


# Representative PubTator3 BioC abstract record: title + abstract passages, with a
# multi-byte character (em-dash) that round-trips unchanged through JSON decode.
_BIOC_RECORD = {
    "PubTator3": [
        {
            "id": "123456",
            "infons": {"_release": "2024.01"},
            "passages": [
                {"offset": 0, "text": "BRCA1 in cancer", "infons": {"type": "title"}},
                {
                    "offset": 16,
                    "text": "We show BRCA1 drives tumours — clearly.",
                    "infons": {"type": "abstract", "section_type": "ABSTRACT"},
                },
            ],
        }
    ]
}


class TestParseBiocPassages:
    def test_parses_title_and_abstract_in_order(self) -> None:
        parsed = parse_bioc_passages(_BIOC_RECORD)
        assert parsed.release == "2024.01"
        assert parsed.passages == (
            Passage(section="title", bioc_offset=0, text="BRCA1 in cancer"),
            Passage(
                section="abstract",
                bioc_offset=16,
                text="We show BRCA1 drives tumours — clearly.",
            ),
        )

    def test_documents_key_is_accepted(self) -> None:
        record = {"documents": _BIOC_RECORD["PubTator3"]}
        parsed = parse_bioc_passages(record)
        assert parsed.passages[0].text == "BRCA1 in cancer"

    def test_release_falls_back_to_constant_when_absent(self) -> None:
        record = {"PubTator3": [{"passages": [{"offset": 0, "text": "t", "infons": {"type": "title"}}]}]}
        parsed = parse_bioc_passages(record)
        assert parsed.release  # non-empty pinned constant

    def test_returns_none_for_empty_record(self) -> None:
        assert parse_bioc_passages({"PubTator3": []}) is None
        assert parse_bioc_passages({}) is None
        assert parse_bioc_passages({"PubTator3": [{"passages": []}]}) is None


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _write_paper(
    project_root: Path, citekey: str, *, doi: str = "", pmid: str = "",
    subdir: str = "entities/papers",
) -> Path:
    papers_dir = project_root / subdir
    papers_dir.mkdir(parents=True, exist_ok=True)
    path = papers_dir / f"{citekey}.md"
    fm = [f"id: paper:{citekey}", f"title: {citekey}"]
    if doi:
        fm.append(f"doi: {doi}")
    if pmid:
        fm.append(f'pmid: "{pmid}"')
    path.write_text("---\n" + "\n".join(fm) + "\n---\n\n## Key Findings\n\nx\n", encoding="utf-8")
    return path


class TestResolvePaperEntity:
    def test_resolves_by_doi_case_insensitive(self, tmp_path: Path) -> None:
        path = _write_paper(tmp_path, "Smith2024", doi="10.1038/Foo-1")
        resolved = resolve_paper_entity(tmp_path, doi="https://doi.org/10.1038/foo-1", pmid=None)
        assert resolved == ResolvedPaper(
            citekey="Smith2024", path=path, directory=path.parent, doi="10.1038/foo-1", pmid=None
        )

    def test_resolves_by_pmid(self, tmp_path: Path) -> None:
        path = _write_paper(tmp_path, "Jones2025", pmid="123456")
        resolved = resolve_paper_entity(tmp_path, doi=None, pmid="123456")
        assert resolved.citekey == "Jones2025"
        assert resolved.path == path

    def test_resolves_paper_under_doc_background_papers(self, tmp_path: Path) -> None:
        # Real checkouts (this meta repo) store paper summaries outside entities/papers;
        # the resolver must scan every canonical paper subdir, not the policy root.
        path = _write_paper(
            tmp_path, "Meta2026", doi="10.1101/meta", subdir="doc/background/papers"
        )
        resolved = resolve_paper_entity(tmp_path, doi="10.1101/meta", pmid=None)
        assert resolved.path == path
        assert resolved.directory == tmp_path / "doc" / "background" / "papers"

    def test_carries_entity_pmid_when_resolved_by_doi(self, tmp_path: Path) -> None:
        # Core of the resolver→acquisition contract: a DOI-invoked resolve still
        # surfaces the entity's PMID, so acquisition can prefer PubTator.
        _write_paper(tmp_path, "Smith2024", doi="10.1038/foo-1", pmid="123456")
        resolved = resolve_paper_entity(tmp_path, doi="10.1038/foo-1", pmid=None)
        assert resolved.doi == "10.1038/foo-1"
        assert resolved.pmid == "123456"

    def test_no_match_fails_loud(self, tmp_path: Path) -> None:
        _write_paper(tmp_path, "Smith2024", doi="10.1038/foo-1")
        with pytest.raises(SourceTextError) as exc:
            resolve_paper_entity(tmp_path, doi="10.9999/missing", pmid=None)
        msg = str(exc.value)
        assert "no paper entity" in msg
        assert "10.9999/missing" in msg
        assert "paper-fetch" in msg

    def test_multi_match_fails_loud_naming_both(self, tmp_path: Path) -> None:
        a = _write_paper(tmp_path, "Aaa2024", doi="10.1038/dup")
        b = _write_paper(tmp_path, "Bbb2024", doi="10.1038/dup")
        with pytest.raises(SourceTextError) as exc:
            resolve_paper_entity(tmp_path, doi="10.1038/dup", pmid=None)
        msg = str(exc.value)
        assert str(a) in msg and str(b) in msg

    def test_requires_an_identifier(self, tmp_path: Path) -> None:
        with pytest.raises(SourceTextError):
            resolve_paper_entity(tmp_path, doi=None, pmid=None)

    def test_skips_source_md_sidecar(self, tmp_path: Path) -> None:
        # A <citekey>.source.md sidecar in the same dir must never be treated as a
        # paper entity — the resolver must return the real .md file only.
        real = _write_paper(tmp_path, "Chu2024", doi="10.1038/s41586-024-0001-1")
        sidecar = tmp_path / "entities" / "papers" / "Chu2024.source.md"
        sidecar.write_text(
            "---\ndoi: 10.1038/s41586-024-0001-1\n---\n\nsidecar body\n",
            encoding="utf-8",
        )
        resolved = resolve_paper_entity(tmp_path, doi="10.1038/s41586-024-0001-1", pmid=None)
        assert resolved.path == real
        assert resolved.path != sidecar


class TestLicense:
    @pytest.mark.parametrize(
        "raw",
        ["CC0", "cc-by", "CC BY", "CC-BY-4.0", "cc-by-sa-3.0", "CC-BY-ND", "CC BY 4.0"],
    )
    def test_whitelisted_values(self, raw: str) -> None:
        assert is_whitelisted(raw) is True

    @pytest.mark.parametrize("raw", ["CC-BY-NC", "CC-BY-NC-4.0", "all-rights-reserved", "", "unknown", "  "])
    def test_non_whitelisted_values(self, raw: str) -> None:
        assert is_whitelisted(raw) is False

    def test_resolve_returns_verbatim_whitelisted_value(self) -> None:
        # Most-permissive whitelisted wins; the raw verbatim form is returned.
        license_, ok = resolve_license(["CC-BY-NC", "CC-BY-4.0"])
        assert ok is True
        assert license_ == "CC-BY-4.0"

    def test_resolve_prefers_more_permissive(self) -> None:
        license_, ok = resolve_license(["CC-BY-ND", "CC-BY"])
        assert ok is True
        assert license_ == "CC-BY"

    def test_resolve_unknown_when_none_whitelisted(self) -> None:
        license_, ok = resolve_license(["CC-BY-NC", "all-rights-reserved"])
        assert ok is False
        assert license_ == "CC-BY-NC"  # raw value retained for provenance

    def test_resolve_unknown_when_no_candidates(self) -> None:
        license_, ok = resolve_license([None, "", "  "])
        assert ok is False
        assert license_ == "unknown"


class TestOffsetMap:
    def _passages(self) -> SourcePassages:
        return SourcePassages(
            passages=(
                Passage(section="title", bioc_offset=0, text="BRCA1 in cancer"),
                Passage(section="abstract", bioc_offset=16, text="We show BRCA1 drives tumours — clearly."),
            ),
            release="2024.01",
        )

    def test_offsets_slice_back_to_passage_text(self) -> None:
        rendered = render_source_md(
            passages=self._passages(),
            retrieved_from="pubtator3",
            license_="CC-BY-4.0",
            pmid="123456",
            doi="10.1038/foo-1",
            fulltext=None,
        )
        file_text = rendered.text
        # Entries are positional 1:1 with passages (render order preserved).
        for off, src in zip(rendered.offset_map, self._passages().passages, strict=True):
            sliced = file_text[off.file_char_base : off.file_char_base + off.length]
            assert off.section == src.section
            assert sliced == src.text

    def test_offset_base_is_character_not_byte(self) -> None:
        # The em dash (U+2014) is 3 bytes but 1 character; offsets must stay in chars.
        rendered = render_source_md(
            passages=self._passages(),
            retrieved_from="pubtator3",
            license_="CC-BY-4.0",
            pmid=None,
            doi="10.1038/foo-1",
            fulltext=None,
        )
        abstract_off = next(o for o in rendered.offset_map if o.section == "abstract")
        sliced = rendered.text[abstract_off.file_char_base : abstract_off.file_char_base + abstract_off.length]
        assert "—" in sliced
        assert abstract_off.length == len("We show BRCA1 drives tumours — clearly.")

    def test_verify_offset_map_passes_on_self(self) -> None:
        rendered = render_source_md(
            passages=self._passages(),
            retrieved_from="pubtator3",
            license_="CC-BY-4.0",
            pmid=None,
            doi="10.1038/foo-1",
            fulltext=None,
        )
        # Must not raise: each map entry slices back to its source passage text.
        verify_offset_map(rendered.text, rendered.offset_map, self._passages())

    def test_verify_offset_map_raises_on_corruption(self) -> None:
        rendered = render_source_md(
            passages=self._passages(),
            retrieved_from="pubtator3",
            license_="CC-BY-4.0",
            pmid=None,
            doi="10.1038/foo-1",
            fulltext=None,
        )
        bad = [PassageOffset(section=o.section, file_char_base=o.file_char_base + 1, length=o.length) for o in rendered.offset_map]
        with pytest.raises(SourceTextError):
            verify_offset_map(rendered.text, bad, self._passages())

    def test_header_length_converges_across_digit_boundary(self) -> None:
        # Many passages force file_char_base values to grow in digit-count as the
        # header lengthens, which can push later bases across another digit
        # boundary. This passage count needs ~5 fixpoint iterations to stabilize —
        # more than the old fixed two-pass logic could absorb.
        passages = SourcePassages(
            passages=tuple(
                Passage(section="abstract", bioc_offset=i, text=f"passage number {i} text")
                for i in range(131)
            ),
            release="2024.01",
        )
        rendered = render_source_md(
            passages=passages,
            retrieved_from="pubtator3",
            license_="CC-BY-4.0",
            pmid="123456",
            doi="10.1038/foo-1",
            fulltext=None,
        )
        for off, src in zip(rendered.offset_map, passages.passages, strict=True):
            sliced = rendered.text[off.file_char_base : off.file_char_base + off.length]
            assert sliced == src.text

    def test_verify_offset_map_passes_for_fulltext(self) -> None:
        # The slice-verify safety net must cover abstract + full-text passages, not
        # just abstract-only. Build a combined SourcePassages in render order.
        abstract = self._passages()
        fulltext = SourcePassages(
            passages=(
                Passage(section="introduction", bioc_offset=100, text="Intro paragraph one."),
                Passage(section="methods", bioc_offset=200, text="We did experiments — many."),
            ),
            release="2024.01",
        )
        rendered = render_source_md(
            passages=abstract,
            retrieved_from="pubtator3",
            license_="CC-BY-4.0",
            pmid="123456",
            doi="10.1038/foo-1",
            fulltext=fulltext,
        )
        combined = SourcePassages(
            passages=abstract.passages + fulltext.passages, release="2024.01"
        )
        # Must not raise: every entry (abstract + full text) slices back exactly.
        verify_offset_map(rendered.text, rendered.offset_map, combined)
