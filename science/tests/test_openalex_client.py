from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from science_tool.openalex import (
    OpenAlexClient,
    OpenAlexRequestCache,
    OpenAlexStatus,
    assert_no_unresolved_openalex_failures,
)


def test_openalex_client_retries_rate_limit_then_records_ok() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": "rate limit"})
        return httpx.Response(200, json={"meta": {"count": 1}, "results": [{"id": "https://openalex.org/W1"}]})

    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.openalex.org")
    client = OpenAlexClient(http=http, sleep=lambda _seconds: None)

    record = client.get("/works", params={"search": "diffusion"})

    assert attempts == 2
    assert record.status == OpenAlexStatus.OK
    assert record.payload["results"] == [{"id": "https://openalex.org/W1"}]
    assert record.error is None


def test_openalex_client_distinguishes_valid_empty_results() -> None:
    http = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"meta": {"count": 0}, "results": []})
        ),
        base_url="https://api.openalex.org",
    )
    client = OpenAlexClient(http=http, sleep=lambda _seconds: None)

    record = client.get("/works", params={"search": "not a real corpus topic"})

    assert record.status == OpenAlexStatus.EMPTY
    assert record.payload["results"] == []
    assert record.error is None


def test_openalex_client_persists_and_reuses_ok_cache_records(tmp_path: Path) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"meta": {"count": 1}, "results": [{"id": "https://openalex.org/W1"}]})

    cache = OpenAlexRequestCache(tmp_path / "openalex-cache.jsonl")
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.openalex.org")
    client = OpenAlexClient(http=http, cache=cache, sleep=lambda _seconds: None)

    first = client.get("/works", params={"search": "diffusion"})
    second = client.get("/works", params={"search": "diffusion"})

    assert calls == 1
    assert first.status == OpenAlexStatus.OK
    assert second.status == OpenAlexStatus.OK
    assert second.from_cache is True
    assert len(cache.records()) == 1


def test_openalex_qa_rejects_unresolved_rate_limit_records(tmp_path: Path) -> None:
    cache_path = tmp_path / "openalex-cache.jsonl"
    cache_path.write_text(
        json.dumps(
            {
                "key": "abc123",
                "endpoint": "/works",
                "params": {"search": "diffusion"},
                "status": "rate_limited",
                "payload": None,
                "error": "HTTP 429",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="rate_limited"):
        assert_no_unresolved_openalex_failures(cache_path)


def test_openalex_qa_allows_failure_records_resolved_by_later_success(tmp_path: Path) -> None:
    cache_path = tmp_path / "openalex-cache.jsonl"
    failed = {
        "key": "abc123",
        "endpoint": "/works",
        "params": {"search": "diffusion"},
        "status": "rate_limited",
        "payload": None,
        "error": "HTTP 429",
    }
    recovered = {
        **failed,
        "status": "ok",
        "payload": {"meta": {"count": 1}, "results": [{"id": "https://openalex.org/W1"}]},
        "error": None,
    }
    cache_path.write_text(
        json.dumps(failed) + "\n" + json.dumps(recovered) + "\n",
        encoding="utf-8",
    )

    assert_no_unresolved_openalex_failures(cache_path)
