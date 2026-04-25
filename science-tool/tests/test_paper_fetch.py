"""Tests for the tiered paper-fetch module."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from science_tool.paper_fetch import (
    FetchConfig,
    FetchResult,
    RateLimiter,
    arxiv_id_to_doi,
    fetch_paper,
    normalize_doi,
    normalize_pmcid,
    normalize_pmid,
    parse_url_identifier,
)


# --- normalize_doi ------------------------------------------------------------


class TestNormalizeDoi:
    def test_bare_doi(self) -> None:
        assert normalize_doi("10.1038/s41586-024-00001-1") == "10.1038/s41586-024-00001-1"

    def test_doi_url(self) -> None:
        assert normalize_doi("https://doi.org/10.1038/Foo-1") == "10.1038/foo-1"

    def test_dx_doi_url(self) -> None:
        assert normalize_doi("http://dx.doi.org/10.1038/BAR") == "10.1038/bar"

    def test_doi_prefix(self) -> None:
        assert normalize_doi("doi:10.1038/qux") == "10.1038/qux"

    def test_whitespace(self) -> None:
        assert normalize_doi("  10.1038/x  ") == "10.1038/x"

    def test_rejects_non_doi(self) -> None:
        assert normalize_doi("not-a-doi") is None

    def test_rejects_empty(self) -> None:
        assert normalize_doi("") is None
        assert normalize_doi(None) is None


# --- RateLimiter --------------------------------------------------------------


class _FakeClock:
    """Wall-clock fake driven by explicit advance() calls."""

    def __init__(self) -> None:
        self.slept: list[float] = []
        self._now = 0.0

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self._now += seconds


def _cfg(
    tmp_path: Path,
    *,
    host_delays: dict[str, float] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> FetchConfig:
    return FetchConfig(
        email="test@example.com",
        cache_dir=tmp_path,
        host_delays=host_delays if host_delays is not None else {"example.com": 1.0},
        default_host_delay=1.0,
        sleep=sleep or (lambda _s: None),
    )


class TestRateLimiter:
    def test_first_call_does_not_sleep(self, tmp_path: Path) -> None:
        clock = _FakeClock()
        limiter = RateLimiter(_cfg(tmp_path, sleep=clock.sleep))
        limiter.acquire("example.com")
        assert clock.slept == []

    def test_second_call_within_window_sleeps(self, tmp_path: Path) -> None:
        # Use a very large delay so the second call is guaranteed to fall inside the window.
        clock = _FakeClock()
        limiter = RateLimiter(_cfg(tmp_path, host_delays={"example.com": 60.0}, sleep=clock.sleep))
        limiter.acquire("example.com")
        limiter.acquire("example.com")
        assert len(clock.slept) == 1
        assert 0.0 < clock.slept[0] <= 60.0

    def test_different_hosts_do_not_interfere(self, tmp_path: Path) -> None:
        clock = _FakeClock()
        limiter = RateLimiter(_cfg(tmp_path, host_delays={"a.com": 60.0, "b.com": 60.0}, sleep=clock.sleep))
        limiter.acquire("a.com")
        limiter.acquire("b.com")
        assert clock.slept == []


# --- fetch_paper (mocked httpx) -----------------------------------------------


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


class TestFetchPaperBranches:
    def test_paywalled_short_circuits_full_text_probes(self, tmp_path: Path) -> None:
        seen: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            seen.append(req.url.host)
            if req.url.host == "api.crossref.org":
                return httpx.Response(
                    200,
                    json={"message": {"DOI": "10.9999/p", "title": ["Pay"], "publisher": "X"}},
                )
            if req.url.host == "api.unpaywall.org":
                return httpx.Response(200, json={"is_oa": False})
            raise AssertionError(f"unexpected host {req.url.host}")

        result = fetch_paper(doi="10.9999/p", cfg=_cfg(tmp_path), http=_make_client(handler))
        assert result.status == "paywalled"
        assert set(seen) == {"api.crossref.org", "api.unpaywall.org"}
        assert result.metadata["title"] == "Pay"

    def test_blocked_but_oa_when_unpaywall_says_oa_but_tiers_fail(self, tmp_path: Path) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"DOI": "10.9999/q", "title": ["Q"]}})
            if req.url.host == "api.unpaywall.org":
                return httpx.Response(
                    200,
                    json={
                        "is_oa": True,
                        "best_oa_location": {"url_for_pdf": "https://paywall.example/q.pdf"},
                    },
                )
            if req.url.host == "www.ncbi.nlm.nih.gov":
                return httpx.Response(200, json={"records": []})
            # bioRxiv / arXiv DOIs won't match; the direct PDF fetch will be the last attempt.
            return httpx.Response(403)

        result = fetch_paper(doi="10.9999/q", cfg=_cfg(tmp_path), http=_make_client(handler))
        assert result.status == "blocked_but_oa"
        assert "Unpaywall lists an OA copy" in (result.access_hint or "")
        assert result.metadata["oa_pdf_url"] == "https://paywall.example/q.pdf"

    def test_not_found_when_both_apis_404(self, tmp_path: Path) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        result = fetch_paper(doi="10.9999/missing", cfg=_cfg(tmp_path), http=_make_client(handler))
        assert result.status == "not_found"

    def test_arxiv_doi_downloads_pdf(self, tmp_path: Path) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"DOI": "10.48550/arxiv.1234.5678"}})
            if req.url.host == "api.unpaywall.org":
                return httpx.Response(200, json={"is_oa": True})
            if req.url.host == "arxiv.org":
                return httpx.Response(200, content=b"%PDF-1.7 fake pdf bytes")
            raise AssertionError(f"unexpected host {req.url.host}")

        result = fetch_paper(doi="10.48550/arxiv.1234.5678", cfg=_cfg(tmp_path), http=_make_client(handler))
        assert result.status == "ok"
        assert result.source == "arxiv"
        assert result.pdf_path is not None
        assert result.pdf_path.exists()
        assert result.pdf_path.read_bytes().startswith(b"%PDF")

    def test_cache_hit_returns_without_new_requests(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        # Seed the cache with a prior result.
        slug = "10.9999_cached"
        papers_dir = cfg.cache_dir / "paper-fetch"
        papers_dir.mkdir(parents=True)
        (papers_dir / f"{slug}.json").write_text(
            json.dumps(
                FetchResult(
                    status="ok",
                    source="test",
                    metadata={"doi": "10.9999/cached"},
                    tiers_attempted=["fake"],
                ).to_dict()
            ),
            encoding="utf-8",
        )

        def handler(_req: httpx.Request) -> httpx.Response:  # pragma: no cover
            raise AssertionError("cache hit must not issue requests")

        result = fetch_paper(doi="10.9999/cached", cfg=cfg, http=_make_client(handler))
        assert result.status == "ok"
        assert result.source == "test"

    def test_missing_doi_returns_not_found(self, tmp_path: Path) -> None:
        def handler(_req: httpx.Request) -> httpx.Response:  # pragma: no cover
            raise AssertionError("no HTTP should be issued")

        result = fetch_paper(url="https://example.com/paper", cfg=_cfg(tmp_path), http=_make_client(handler))
        assert result.status == "not_found"
        assert "no DOI supplied" in result.errors[0]


# --- Identifier normalization helpers ----------------------------------------


class TestNormalizePmid:
    def test_bare_pmid(self) -> None:
        assert normalize_pmid("39581534") == "39581534"

    def test_whitespace(self) -> None:
        assert normalize_pmid("  12345  ") == "12345"

    def test_rejects_non_numeric(self) -> None:
        assert normalize_pmid("PMC123") is None
        assert normalize_pmid("abc") is None
        assert normalize_pmid(None) is None
        assert normalize_pmid("") is None


class TestNormalizePmcid:
    def test_with_prefix(self) -> None:
        assert normalize_pmcid("PMC12934989") == "PMC12934989"

    def test_lowercase_prefix(self) -> None:
        assert normalize_pmcid("pmc12934989") == "PMC12934989"

    def test_bare_number(self) -> None:
        assert normalize_pmcid("12934989") == "PMC12934989"

    def test_rejects_garbage(self) -> None:
        assert normalize_pmcid("PMCabc") is None
        assert normalize_pmcid(None) is None


class TestArxivIdToDoi:
    def test_modern_id(self) -> None:
        assert arxiv_id_to_doi("2502.09135") == "10.48550/arxiv.2502.09135"

    def test_strips_version(self) -> None:
        assert arxiv_id_to_doi("2502.09135v3") == "10.48550/arxiv.2502.09135"

    def test_rejects_garbage(self) -> None:
        assert arxiv_id_to_doi("not an id") is None
        assert arxiv_id_to_doi(None) is None


class TestParseUrlIdentifier:
    def test_pubmed(self) -> None:
        assert parse_url_identifier("https://pubmed.ncbi.nlm.nih.gov/39581534/") == ("pmid", "39581534")

    def test_pmc(self) -> None:
        assert parse_url_identifier("https://pmc.ncbi.nlm.nih.gov/articles/PMC12934989/") == ("pmcid", "PMC12934989")

    def test_arxiv_abs(self) -> None:
        kind, value = parse_url_identifier("https://arxiv.org/abs/2502.09135") or (None, None)
        assert kind == "arxiv"
        assert value == "2502.09135"

    def test_arxiv_abs_with_version(self) -> None:
        kind, value = parse_url_identifier("https://arxiv.org/abs/2502.09135v2") or (None, None)
        assert kind == "arxiv"
        assert value == "2502.09135"

    def test_biorxiv(self) -> None:
        kind, value = parse_url_identifier("https://www.biorxiv.org/content/10.1101/2024.01.02.123456v1.full") or (
            None,
            None,
        )
        assert kind == "doi"
        assert value == "10.1101/2024.01.02.123456v1.full"  # raw extraction; normalize_doi handles cleanup downstream

    def test_doi_url(self) -> None:
        assert parse_url_identifier("https://doi.org/10.1038/s41586-024-00001-1") == (
            "doi",
            "10.1038/s41586-024-00001-1",
        )

    def test_unrecognized(self) -> None:
        assert parse_url_identifier("https://example.com/paper") is None
        assert parse_url_identifier(None) is None


# --- Identifier resolution paths in fetch_paper -------------------------------


class TestIdentifierResolution:
    def test_pmid_alone_resolves_to_doi_then_proceeds(self, tmp_path: Path) -> None:
        """PMID-only input should hit Europe PMC for DOI, then run the normal cascade."""
        seen_queries: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "www.ebi.ac.uk":
                seen_queries.append(dict(req.url.params).get("query", ""))
                return httpx.Response(
                    200,
                    json={"resultList": {"result": [{"doi": "10.1234/ok", "pmid": "39581534", "pmcid": ""}]}},
                )
            if req.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"DOI": "10.1234/ok", "title": ["Found"]}})
            if req.url.host == "api.unpaywall.org":
                return httpx.Response(200, json={"is_oa": False})
            raise AssertionError(f"unexpected host {req.url.host}")

        result = fetch_paper(pmid="39581534", cfg=_cfg(tmp_path), http=_make_client(handler))
        assert result.status == "paywalled"
        assert any("EXT_ID:39581534" in q for q in seen_queries)
        # DOI verification step also fires (DOI + PMID present after resolution).
        assert "europepmc:pmid->doi" in result.tiers_attempted
        assert "europepmc:verify" in result.tiers_attempted

    def test_pmcid_alone_resolves_to_doi(self, tmp_path: Path) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "www.ebi.ac.uk":
                query = dict(req.url.params).get("query", "")
                if query.startswith("PMCID:"):
                    return httpx.Response(
                        200,
                        json={"resultList": {"result": [{"doi": "10.1234/pmcok", "pmid": "", "pmcid": "PMC12934989"}]}},
                    )
                # DOI verification round
                return httpx.Response(
                    200,
                    json={"resultList": {"result": [{"doi": "10.1234/pmcok", "pmid": "", "pmcid": "PMC12934989"}]}},
                )
            if req.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"DOI": "10.1234/pmcok"}})
            if req.url.host == "api.unpaywall.org":
                return httpx.Response(200, json={"is_oa": False})
            raise AssertionError(f"unexpected host {req.url.host}")

        result = fetch_paper(pmcid="PMC12934989", cfg=_cfg(tmp_path), http=_make_client(handler))
        assert result.status == "paywalled"
        assert "europepmc:pmcid->doi" in result.tiers_attempted

    def test_arxiv_shortcut_constructs_doi_without_lookup(self, tmp_path: Path) -> None:
        """--arxiv builds the DOI deterministically; no Europe PMC call needed."""
        seen_hosts: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            seen_hosts.append(req.url.host)
            if req.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"DOI": "10.48550/arxiv.2502.09135", "title": ["A"]}})
            if req.url.host == "api.unpaywall.org":
                return httpx.Response(200, json={"is_oa": True})
            if req.url.host == "arxiv.org":
                return httpx.Response(200, content=b"%PDF-1.4 fake")
            raise AssertionError(f"unexpected host {req.url.host}")

        result = fetch_paper(arxiv="2502.09135", cfg=_cfg(tmp_path), http=_make_client(handler))
        assert result.status == "ok"
        assert result.source == "arxiv"
        assert "www.ebi.ac.uk" not in seen_hosts  # no resolver call needed

    def test_pubmed_url_extracts_pmid(self, tmp_path: Path) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "www.ebi.ac.uk":
                return httpx.Response(
                    200,
                    json={"resultList": {"result": [{"doi": "10.1234/ok", "pmid": "39581534", "pmcid": ""}]}},
                )
            if req.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"DOI": "10.1234/ok"}})
            if req.url.host == "api.unpaywall.org":
                return httpx.Response(200, json={"is_oa": False})
            raise AssertionError(f"unexpected host {req.url.host}")

        result = fetch_paper(
            url="https://pubmed.ncbi.nlm.nih.gov/39581534/", cfg=_cfg(tmp_path), http=_make_client(handler)
        )
        assert result.status == "paywalled"
        assert result.metadata.get("doi") == "10.1234/ok"

    def test_pmc_url_extracts_pmcid(self, tmp_path: Path) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "www.ebi.ac.uk":
                return httpx.Response(
                    200,
                    json={"resultList": {"result": [{"doi": "10.1234/pmcok", "pmcid": "PMC12934989"}]}},
                )
            if req.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"DOI": "10.1234/pmcok"}})
            if req.url.host == "api.unpaywall.org":
                return httpx.Response(200, json={"is_oa": False})
            raise AssertionError(f"unexpected host {req.url.host}")

        result = fetch_paper(
            url="https://pmc.ncbi.nlm.nih.gov/articles/PMC12934989/",
            cfg=_cfg(tmp_path),
            http=_make_client(handler),
        )
        assert result.status == "paywalled"

    def test_arxiv_url_takes_arxiv_path(self, tmp_path: Path) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"DOI": "10.48550/arxiv.2502.09135"}})
            if req.url.host == "api.unpaywall.org":
                return httpx.Response(200, json={"is_oa": True})
            if req.url.host == "arxiv.org":
                return httpx.Response(200, content=b"%PDF")
            raise AssertionError(f"unexpected host {req.url.host}")

        result = fetch_paper(url="https://arxiv.org/abs/2502.09135v2", cfg=_cfg(tmp_path), http=_make_client(handler))
        assert result.status == "ok"
        assert result.source == "arxiv"

    def test_no_identifier_returns_not_found(self, tmp_path: Path) -> None:
        def handler(_req: httpx.Request) -> httpx.Response:  # pragma: no cover
            raise AssertionError("no HTTP should be issued")

        result = fetch_paper(cfg=_cfg(tmp_path), http=_make_client(handler))
        assert result.status == "not_found"
        assert "PMID/PMCID/arXiv/URL" in result.errors[0]


class TestIdentifierMismatch:
    def test_doi_pmid_conflict_returns_error(self, tmp_path: Path) -> None:
        """DOI + PMID where Europe PMC says DOI maps to a different PMID -> status=error."""

        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"DOI": "10.1016/j.semcancer.2013.06.005"}})
            if req.url.host == "api.unpaywall.org":
                return httpx.Response(200, json={"is_oa": False})
            if req.url.host == "www.ebi.ac.uk":
                # The DOI actually belongs to PMID 11111111, not the user-supplied 23792873.
                return httpx.Response(
                    200,
                    json={"resultList": {"result": [{"doi": "10.1016/j.semcancer.2013.06.005", "pmid": "11111111"}]}},
                )
            raise AssertionError(f"unexpected host {req.url.host}")

        result = fetch_paper(
            doi="10.1016/j.semcancer.2013.06.005",
            pmid="23792873",
            cfg=_cfg(tmp_path),
            http=_make_client(handler),
        )
        assert result.status == "error"
        assert result.metadata["reason"] == "identifier_mismatch"
        assert result.metadata["mismatch"] == {"kind": "pmid", "expected": "23792873", "actual": "11111111"}
        assert "23792873" in (result.access_hint or "")

    def test_doi_pmid_match_proceeds_normally(self, tmp_path: Path) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"DOI": "10.1234/ok"}})
            if req.url.host == "api.unpaywall.org":
                return httpx.Response(200, json={"is_oa": False})
            if req.url.host == "www.ebi.ac.uk":
                return httpx.Response(200, json={"resultList": {"result": [{"doi": "10.1234/ok", "pmid": "39581534"}]}})
            raise AssertionError(f"unexpected host {req.url.host}")

        result = fetch_paper(doi="10.1234/ok", pmid="39581534", cfg=_cfg(tmp_path), http=_make_client(handler))
        assert result.status == "paywalled"

    def test_europepmc_silent_does_not_block(self, tmp_path: Path) -> None:
        """If Europe PMC has no record for the DOI, the verify step doesn't fail-closed."""

        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"DOI": "10.1234/obscure"}})
            if req.url.host == "api.unpaywall.org":
                return httpx.Response(200, json={"is_oa": False})
            if req.url.host == "www.ebi.ac.uk":
                return httpx.Response(200, json={"resultList": {"result": []}})
            raise AssertionError(f"unexpected host {req.url.host}")

        result = fetch_paper(doi="10.1234/obscure", pmid="99999999", cfg=_cfg(tmp_path), http=_make_client(handler))
        assert result.status == "paywalled"  # cross-check returned None silently; flow continued


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep real home cache directory out of test runs."""
    monkeypatch.setenv("SCIENCE_CACHE_DIR", str(tmp_path / "cache"))
