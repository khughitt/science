from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx


OPENALEX_BASE_URL = "https://api.openalex.org"
OPENALEX_MAX_PER_PAGE = 100
RESOLVED_STATUSES = {"ok", "empty"}


class OpenAlexStatus(StrEnum):
    OK = "ok"
    EMPTY = "empty"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    REQUEST_ERROR = "request_error"


@dataclass(frozen=True)
class OpenAlexRecord:
    key: str
    endpoint: str
    params: dict[str, str]
    status: OpenAlexStatus
    payload: dict[str, Any] | None
    error: str | None = None
    from_cache: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "endpoint": self.endpoint,
            "params": self.params,
            "status": self.status.value,
            "payload": self.payload,
            "error": self.error,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any], *, from_cache: bool = False) -> "OpenAlexRecord":
        return cls(
            key=str(data["key"]),
            endpoint=str(data["endpoint"]),
            params={str(key): str(value) for key, value in dict(data.get("params", {})).items()},
            status=OpenAlexStatus(str(data["status"])),
            payload=data.get("payload") if isinstance(data.get("payload"), dict) else None,
            error=str(data["error"]) if data.get("error") is not None else None,
            from_cache=from_cache,
        )


class OpenAlexRequestCache:
    def __init__(self, path: Path):
        self.path = path

    def get(self, key: str) -> OpenAlexRecord | None:
        for record in reversed(self.records()):
            if record.key == key and record.status.value in RESOLVED_STATUSES:
                return OpenAlexRecord.from_json(record.to_json(), from_cache=True)
        return None

    def put(self, record: OpenAlexRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_json(), sort_keys=True) + "\n")

    def records(self) -> list[OpenAlexRecord]:
        if not self.path.exists():
            return []
        rows: list[OpenAlexRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.append(OpenAlexRecord.from_json(json.loads(line)))
        return rows


def openalex_request_key(endpoint: str, params: Mapping[str, str]) -> str:
    stable = json.dumps({"endpoint": endpoint, "params": dict(sorted(params.items()))}, sort_keys=True)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


class OpenAlexClient:
    def __init__(
        self,
        *,
        http: httpx.Client | None = None,
        cache: OpenAlexRequestCache | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 6,
    ):
        self.http = http if http is not None else httpx.Client(base_url=OPENALEX_BASE_URL, timeout=30.0)
        self.cache = cache
        self.sleep = sleep
        self.max_retries = max_retries

    def get(self, endpoint: str, *, params: Mapping[str, str]) -> OpenAlexRecord:
        normalized_params = {str(key): str(value) for key, value in params.items()}
        key = openalex_request_key(endpoint, normalized_params)
        if self.cache is not None:
            cached = self.cache.get(key)
            if cached is not None:
                return cached

        record = self._fetch(endpoint, normalized_params, key)
        if self.cache is not None:
            self.cache.put(record)
        return record

    def _fetch(self, endpoint: str, params: dict[str, str], key: str) -> OpenAlexRecord:
        backoff = 1.0
        last_rate_limit_error = "HTTP 429"
        for attempt in range(self.max_retries + 1):
            try:
                response = self.http.get(endpoint, params=params)
            except httpx.RequestError as exc:
                return OpenAlexRecord(
                    key=key,
                    endpoint=endpoint,
                    params=params,
                    status=OpenAlexStatus.REQUEST_ERROR,
                    payload=None,
                    error=str(exc),
                )

            if response.status_code == 429:
                last_rate_limit_error = f"HTTP 429: {response.text[:200]}"
                if attempt < self.max_retries:
                    retry_after = response.headers.get("retry-after")
                    delay = float(retry_after) if retry_after is not None else backoff
                    self.sleep(delay)
                    backoff *= 2
                    continue
                return OpenAlexRecord(
                    key=key,
                    endpoint=endpoint,
                    params=params,
                    status=OpenAlexStatus.RATE_LIMITED,
                    payload=None,
                    error=last_rate_limit_error,
                )

            if response.status_code >= 500:
                return OpenAlexRecord(
                    key=key,
                    endpoint=endpoint,
                    params=params,
                    status=OpenAlexStatus.SERVER_ERROR,
                    payload=None,
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                )

            try:
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                return OpenAlexRecord(
                    key=key,
                    endpoint=endpoint,
                    params=params,
                    status=OpenAlexStatus.REQUEST_ERROR,
                    payload=None,
                    error=str(exc),
                )

            if _is_empty_openalex_payload(payload):
                return OpenAlexRecord(
                    key=key,
                    endpoint=endpoint,
                    params=params,
                    status=OpenAlexStatus.EMPTY,
                    payload=payload,
                )
            return OpenAlexRecord(
                key=key,
                endpoint=endpoint,
                params=params,
                status=OpenAlexStatus.OK,
                payload=payload,
            )

        return OpenAlexRecord(
            key=key,
            endpoint=endpoint,
            params=params,
            status=OpenAlexStatus.RATE_LIMITED,
            payload=None,
            error=last_rate_limit_error,
        )


def _is_empty_openalex_payload(payload: dict[str, Any]) -> bool:
    results = payload.get("results")
    meta = payload.get("meta")
    if isinstance(results, list) and len(results) == 0:
        if isinstance(meta, dict):
            return int(meta.get("count") or 0) == 0
        return True
    return False


def assert_no_unresolved_openalex_failures(cache_path: Path) -> None:
    cache = OpenAlexRequestCache(cache_path)
    latest_by_key = {record.key: record for record in cache.records()}
    unresolved = [
        f"{record.status.value}:{record.endpoint}:{record.params}"
        for record in latest_by_key.values()
        if record.status.value not in RESOLVED_STATUSES
    ]
    if unresolved:
        raise ValueError(f"OpenAlex cache contains unresolved request failures: {unresolved}")
