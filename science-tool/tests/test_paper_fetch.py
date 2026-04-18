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
    fetch_paper,
    normalize_doi,
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
        limiter = RateLimiter(
            _cfg(tmp_path, host_delays={"a.com": 60.0, "b.com": 60.0}, sleep=clock.sleep)
        )
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

        result = fetch_paper(
            doi="10.48550/arxiv.1234.5678", cfg=_cfg(tmp_path), http=_make_client(handler)
        )
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

        result = fetch_paper(
            url="https://example.com/paper", cfg=_cfg(tmp_path), http=_make_client(handler)
        )
        assert result.status == "not_found"
        assert "no DOI supplied" in result.errors[0]


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep real home cache directory out of test runs."""
    monkeypatch.setenv("SCIENCE_CACHE_DIR", str(tmp_path / "cache"))
