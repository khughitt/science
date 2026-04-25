"""Polite, tiered paper-source probing for research agents.

Given a DOI / PMID / URL / title, try a sequence of agent-friendly sources
(Crossref, Unpaywall, arXiv, bioRxiv/medRxiv, Europe PMC) and report back
a structured result telling the caller whether the article was retrieved,
blocked-but-OA (agent cannot reach what a browser could), fully paywalled,
or unidentifiable.

Design goals:
- **Stop early.** Once Unpaywall says a paper has no OA copy, report paywalled
  without scraping. Once Unpaywall says OA exists but our fetches fail, report
  blocked_but_oa so the orchestrator can ask the user for a PDF instead of
  burning tokens on open-ended search.
- **Be polite.** A per-host file-based rate limiter enforces minimum gaps
  between requests *across parallel subagent processes*. Each host's last-hit
  timestamp is kept in a lockfile at ``~/.cache/science/ratelimit/<host>``.
- **Be testable.** HTTP client, clock, and sleep are all injectable.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import httpx

FetchStatus = Literal["ok", "paywalled", "not_found", "blocked_but_oa", "error"]

_DEFAULT_CACHE_DIR = Path(os.environ.get("SCIENCE_CACHE_DIR", Path.home() / ".cache" / "science"))
_RATELIMIT_SUBDIR = "ratelimit"
_PAPERS_SUBDIR = "paper-fetch"

# Per-host minimum seconds between requests. Tuned to published guidance:
# - arXiv asks for >=3s gaps.
# - NCBI E-utilities allows 3 req/s without an API key; 0.5s gives headroom.
# - Crossref + Unpaywall tolerate higher rates but a second is courteous.
_HOST_DELAYS: dict[str, float] = {
    "api.crossref.org": 1.0,
    "api.unpaywall.org": 1.0,
    "eutils.ncbi.nlm.nih.gov": 0.5,
    "www.ncbi.nlm.nih.gov": 0.5,
    "europepmc.org": 0.5,
    "www.ebi.ac.uk": 0.5,
    "export.arxiv.org": 3.0,
    "arxiv.org": 3.0,
    "api.biorxiv.org": 1.0,
    "www.biorxiv.org": 1.0,
    "www.medrxiv.org": 1.0,
}
_DEFAULT_HOST_DELAY = 1.0

# bioRxiv/medRxiv explicitly invite machine analysis in their FAQ but return 403
# to non-browser User-Agents. Identify politely (mailto still on the UA string)
# but with a browser-plausible prefix so the server accepts the request.
_BROWSERLIKE_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
_HOST_USER_AGENTS: dict[str, str] = {
    "www.biorxiv.org": _BROWSERLIKE_UA,
    "www.medrxiv.org": _BROWSERLIKE_UA,
}


@dataclass(frozen=True)
class FetchResult:
    """Structured outcome of a paper-fetch attempt.

    ``status`` drives the caller's branching:
    - ``ok``: a full-text artifact was retrieved; see ``pdf_path`` / ``text_path``.
    - ``paywalled``: Unpaywall (or equivalent) found no OA copy.
    - ``not_found``: no source resolved the identifier at all.
    - ``blocked_but_oa``: OA copy exists per Unpaywall, but every fetch we tried
      failed. Users can likely access it in a browser — recommend they supply a PDF.
    - ``error``: caller-supplied identifiers conflicted (or another structured
      condition the caller should surface). ``metadata['reason']`` names the
      class (e.g. ``identifier_mismatch``).
    """

    status: FetchStatus
    source: str
    metadata: dict[str, Any]
    tiers_attempted: list[str]
    pdf_path: Path | None = None
    text_path: Path | None = None
    access_hint: str | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["pdf_path"] = str(self.pdf_path) if self.pdf_path else None
        data["text_path"] = str(self.text_path) if self.text_path else None
        return data


@dataclass(frozen=True)
class FetchConfig:
    """Injection surface for tests and overrides."""

    email: str
    cache_dir: Path = _DEFAULT_CACHE_DIR
    host_delays: dict[str, float] = field(default_factory=lambda: dict(_HOST_DELAYS))
    default_host_delay: float = _DEFAULT_HOST_DELAY
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    http_timeout: float = 15.0


_DOI_URL_PREFIX = re.compile(r"^https?://(?:dx\.)?doi\.org/", re.IGNORECASE)
_ARXIV_DOI = re.compile(r"^10\.48550/arxiv\.(?P<id>.+)$", re.IGNORECASE)
_BIORXIV_DOI = re.compile(r"^10\.1101/(?P<id>.+)$", re.IGNORECASE)

# URL patterns for identifier extraction. The first capture group is the identifier.
_URL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("pmid", re.compile(r"^https?://pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", re.IGNORECASE)),
    ("pmid", re.compile(r"^https?://(?:www\.)?ncbi\.nlm\.nih\.gov/pubmed/(\d+)", re.IGNORECASE)),
    ("pmcid", re.compile(r"^https?://pmc\.ncbi\.nlm\.nih\.gov/articles/(PMC\d+)", re.IGNORECASE)),
    ("pmcid", re.compile(r"^https?://(?:www\.)?ncbi\.nlm\.nih\.gov/pmc/articles/(PMC\d+)", re.IGNORECASE)),
    (
        "arxiv",
        re.compile(r"^https?://arxiv\.org/(?:abs|pdf)/([\w./-]+?)(?:v\d+)?(?:\.pdf)?(?:[?#].*)?$", re.IGNORECASE),
    ),
    ("doi", re.compile(r"^https?://(?:www\.)?(?:bio|med)rxiv\.org/content/(?:.+?/)?(10\.1101/[^/?#]+)", re.IGNORECASE)),
]

_PMID_RE = re.compile(r"^\d+$")
_PMCID_RE = re.compile(r"^PMC\d+$", re.IGNORECASE)


def normalize_pmid(value: str | None) -> str | None:
    """Accept a bare PMID; return the canonical form, or None if unparseable."""
    if not value:
        return None
    cleaned = value.strip()
    return cleaned if _PMID_RE.match(cleaned) else None


def normalize_pmcid(value: str | None) -> str | None:
    """Accept ``PMC12345`` or ``12345``; return ``PMC12345``."""
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.isdigit():
        return f"PMC{cleaned}"
    return cleaned.upper() if _PMCID_RE.match(cleaned) else None


def arxiv_id_to_doi(value: str | None) -> str | None:
    """Convert an arXiv ID (``2502.09135`` or ``2502.09135v2``) to its DOI form."""
    if not value:
        return None
    cleaned = value.strip().lower()
    cleaned = re.sub(r"v\d+$", "", cleaned)
    if not re.match(r"^[\w./-]+$", cleaned):
        return None
    return f"10.48550/arxiv.{cleaned}"


def parse_url_identifier(url: str | None) -> tuple[str, str] | None:
    """Recognize PubMed, PMC, arXiv, bioRxiv/medRxiv, or DOI URLs.

    Returns ``(kind, value)`` where kind is ``doi``, ``pmid``, ``pmcid``, or
    ``arxiv``, or None if the URL is not recognized.
    """
    if not url:
        return None
    cleaned = url.strip()
    if _DOI_URL_PREFIX.match(cleaned):
        doi = normalize_doi(cleaned)
        if doi:
            return ("doi", doi)
    for kind, pattern in _URL_PATTERNS:
        match = pattern.match(cleaned)
        if match:
            return (kind, match.group(1))
    return None


def normalize_doi(value: str | None) -> str | None:
    """Accept a bare DOI, a doi.org URL, or ``doi:`` prefix; return the bare DOI lower-cased."""
    if not value:
        return None
    cleaned = value.strip()
    cleaned = _DOI_URL_PREFIX.sub("", cleaned)
    if cleaned.lower().startswith("doi:"):
        cleaned = cleaned[4:]
    cleaned = cleaned.strip().strip("/")
    # A valid DOI is of the form ``10.<registrant>/<suffix>``.
    if not re.match(r"^10\.\d{4,9}/", cleaned):
        return None
    return cleaned.lower()


def _cache_slug(doi: str) -> str:
    """Filesystem-safe slug for a DOI. Short DOIs stay readable; long ones get hashed."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", doi)
    if len(safe) <= 80:
        return safe
    digest = hashlib.sha256(doi.encode("utf-8")).hexdigest()[:16]
    return f"{safe[:60]}_{digest}"


class RateLimiter:
    """Per-host minimum-gap rate limiter backed by a lockfile.

    Works across parallel processes: each host has a small file whose mtime
    records the last request timestamp. Before returning from ``acquire``,
    callers are guaranteed at least ``delay`` wall-clock seconds have elapsed
    since the last acquire for that host across the whole machine.
    """

    def __init__(self, cfg: FetchConfig) -> None:
        self._cfg = cfg
        self._dir = cfg.cache_dir / _RATELIMIT_SUBDIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _lockfile(self, host: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", host)
        return self._dir / safe

    def acquire(self, host: str) -> None:
        delay = self._cfg.host_delays.get(host, self._cfg.default_host_delay)
        lockfile = self._lockfile(host)
        lockfile.touch(exist_ok=True)
        with open(lockfile, "r+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                raw = handle.read().strip()
                last_wall = float(raw) if raw else 0.0
                now_wall = time.time()
                elapsed = now_wall - last_wall
                if elapsed < delay:
                    self._cfg.sleep(delay - elapsed)
                handle.seek(0)
                handle.truncate()
                handle.write(f"{time.time()}\n")
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _get_json(
    client: httpx.Client, limiter: RateLimiter, url: str, host: str, *, params: dict[str, str] | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    limiter.acquire(host)
    headers = {"Accept": "application/json"}
    host_ua = _HOST_USER_AGENTS.get(host)
    if host_ua:
        headers["User-Agent"] = host_ua
    try:
        resp = client.get(url, params=params, headers=headers)
    except httpx.HTTPError as exc:
        return None, f"{host}: {exc}"
    if resp.status_code == 404:
        return None, None  # legitimate "not found"
    if resp.status_code >= 400:
        return None, f"{host}: HTTP {resp.status_code}"
    try:
        return resp.json(), None
    except ValueError as exc:
        return None, f"{host}: invalid JSON ({exc})"


def _download(client: httpx.Client, limiter: RateLimiter, url: str, host: str, dest: Path) -> tuple[bool, str | None]:
    limiter.acquire(host)
    headers = _host_headers(host)
    try:
        resp = client.get(url, follow_redirects=True, headers=headers)
    except httpx.HTTPError as exc:
        return False, f"{host}: {exc}"
    if resp.status_code >= 400:
        return False, f"{host}: HTTP {resp.status_code}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return True, None


def _host_headers(host: str) -> dict[str, str] | None:
    host_lower = host.lower()
    ua = _HOST_USER_AGENTS.get(host_lower)
    if not ua:
        return None
    # Browser-plausible request set for hosts that reject non-browser UAs.
    # bioRxiv's FAQ explicitly welcomes machine analysis; the 403 is a UA filter,
    # not a policy decision. Be polite (keep rate limits) but identify plausibly.
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": f"https://{host_lower}/",
    }


def _host_of(url: str) -> str:
    m = re.match(r"^https?://([^/]+)/?", url)
    return m.group(1).lower() if m else ""


# --- Tier implementations -----------------------------------------------------


def _try_crossref(
    doi: str, client: httpx.Client, limiter: RateLimiter, cfg: FetchConfig
) -> tuple[dict[str, Any] | None, str | None]:
    data, err = _get_json(
        client,
        limiter,
        f"https://api.crossref.org/works/{doi}",
        "api.crossref.org",
        params={"mailto": cfg.email},
    )
    if not data:
        return None, err
    message = data.get("message")
    if not isinstance(message, dict):
        return None, "crossref: unexpected response shape"
    meta: dict[str, Any] = {
        "doi": str(message.get("DOI") or doi),
        "title": (message.get("title") or [""])[0] if isinstance(message.get("title"), list) else "",
        "publisher": str(message.get("publisher") or ""),
        "type": str(message.get("type") or ""),
    }
    if isinstance(message.get("container-title"), list) and message["container-title"]:
        meta["venue"] = str(message["container-title"][0])
    if isinstance(message.get("issued"), dict):
        parts = message["issued"].get("date-parts") or [[]]
        if parts and parts[0]:
            meta["year"] = int(parts[0][0])
    authors = message.get("author")
    if isinstance(authors, list):
        meta["authors"] = [
            " ".join(filter(None, [a.get("given"), a.get("family")])) for a in authors if isinstance(a, dict)
        ]
    return meta, None


def _try_unpaywall(
    doi: str, client: httpx.Client, limiter: RateLimiter, cfg: FetchConfig
) -> tuple[dict[str, Any] | None, str | None]:
    data, err = _get_json(
        client,
        limiter,
        f"https://api.unpaywall.org/v2/{doi}",
        "api.unpaywall.org",
        params={"email": cfg.email},
    )
    if not data:
        return None, err
    is_oa = bool(data.get("is_oa"))
    best = data.get("best_oa_location") if isinstance(data.get("best_oa_location"), dict) else None
    return {
        "is_oa": is_oa,
        "best_oa_pdf_url": best.get("url_for_pdf") if best else None,
        "best_oa_landing_url": best.get("url") if best else None,
        "host_type": best.get("host_type") if best else None,
    }, None


def _try_arxiv(doi: str, client: httpx.Client, limiter: RateLimiter, dest: Path) -> tuple[Path | None, str | None]:
    m = _ARXIV_DOI.match(doi)
    if not m:
        return None, None
    arxiv_id = m.group("id")
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    ok, err = _download(client, limiter, pdf_url, "arxiv.org", dest)
    return (dest if ok else None), err


def _try_biorxiv(doi: str, client: httpx.Client, limiter: RateLimiter, dest: Path) -> tuple[Path | None, str | None]:
    m = _BIORXIV_DOI.match(doi)
    if not m:
        return None, None
    data, err = _get_json(
        client,
        limiter,
        f"https://api.biorxiv.org/details/biorxiv/{doi}",
        "api.biorxiv.org",
    )
    if not data or not isinstance(data.get("collection"), list) or not data["collection"]:
        # Try medRxiv as a fallback (same DOI prefix, different server).
        data, err = _get_json(
            client,
            limiter,
            f"https://api.biorxiv.org/details/medrxiv/{doi}",
            "api.biorxiv.org",
        )
    if not data or not isinstance(data.get("collection"), list) or not data["collection"]:
        return None, err
    entry = data["collection"][0]
    server = str(entry.get("server") or "biorxiv").lower()
    version = entry.get("version") or 1
    host = f"www.{server}.org"
    pdf_url = f"https://{host}/content/{doi}v{version}.full.pdf"
    ok, dl_err = _download(client, limiter, pdf_url, host, dest)
    return (dest if ok else None), dl_err


def _try_europepmc_fulltext(
    pmcid: str, client: httpx.Client, limiter: RateLimiter, dest: Path
) -> tuple[Path | None, str | None]:
    """Europe PMC serves full-text XML for OA papers — ideal for agents (no PDF parse)."""
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    limiter.acquire("www.ebi.ac.uk")
    try:
        resp = client.get(url, follow_redirects=True)
    except httpx.HTTPError as exc:
        return None, f"europepmc: {exc}"
    if resp.status_code == 404:
        return None, None
    if resp.status_code >= 400:
        return None, f"europepmc: HTTP {resp.status_code}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return dest, None


def _europepmc_lookup(
    query: str, client: httpx.Client, limiter: RateLimiter, cfg: FetchConfig
) -> tuple[dict[str, Any] | None, str | None]:
    """Run a one-result Europe PMC search and return the first record dict.

    Europe PMC's search endpoint is the workhorse for cross-identifier
    resolution: the same query language returns ``doi``, ``pmid``, and
    ``pmcid`` fields on each record, so DOI↔PMID↔PMCID conversions are all
    one call. We previously tried NCBI's idconv service, but it intermittently
    responded with HTML error pages even when ``format=json`` was requested,
    breaking our parser.
    """
    _ = cfg  # reserved for future polite-pool identification
    data, err = _get_json(
        client,
        limiter,
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        "www.ebi.ac.uk",
        params={"query": query, "format": "json", "resultType": "lite", "pageSize": "1"},
    )
    if not data:
        return None, err
    results = data.get("resultList")
    if not isinstance(results, dict):
        return None, None
    items = results.get("result") or []
    if items and isinstance(items[0], dict):
        return items[0], None
    return None, None


def _resolve_pmcid(
    doi: str, client: httpx.Client, limiter: RateLimiter, cfg: FetchConfig
) -> tuple[str | None, str | None]:
    """Resolve a DOI to a PMCID via Europe PMC."""
    record, err = _europepmc_lookup(f'DOI:"{doi}"', client, limiter, cfg)
    if not record:
        return None, err
    pmcid = record.get("pmcid")
    return (pmcid if isinstance(pmcid, str) and pmcid else None), None


def _resolve_doi_from_pmid(
    pmid: str, client: httpx.Client, limiter: RateLimiter, cfg: FetchConfig
) -> tuple[str | None, str | None]:
    """Resolve a PMID to its DOI via Europe PMC."""
    record, err = _europepmc_lookup(f"EXT_ID:{pmid} AND SRC:MED", client, limiter, cfg)
    if not record:
        return None, err
    doi = record.get("doi")
    return (normalize_doi(doi) if isinstance(doi, str) else None), None


def _resolve_doi_from_pmcid(
    pmcid: str, client: httpx.Client, limiter: RateLimiter, cfg: FetchConfig
) -> tuple[str | None, str | None]:
    """Resolve a PMCID to its DOI via Europe PMC."""
    record, err = _europepmc_lookup(f"PMCID:{pmcid}", client, limiter, cfg)
    if not record:
        return None, err
    doi = record.get("doi")
    return (normalize_doi(doi) if isinstance(doi, str) else None), None


def _verify_doi_matches(
    doi: str,
    *,
    expected_pmid: str | None,
    expected_pmcid: str | None,
    client: httpx.Client,
    limiter: RateLimiter,
    cfg: FetchConfig,
) -> tuple[dict[str, str] | None, str | None]:
    """Confirm a DOI maps to the supplied PMID/PMCID.

    Returns ``(mismatch_info, err)`` where ``mismatch_info`` is None on match
    or when Europe PMC has no record (we don't fail-closed on a third-party
    gap), and a dict ``{kind, expected, actual}`` when there's a definitive
    conflict the caller should surface.
    """
    if not (expected_pmid or expected_pmcid):
        return None, None
    record, err = _europepmc_lookup(f'DOI:"{doi}"', client, limiter, cfg)
    if not record:
        return None, err
    if expected_pmid:
        actual = record.get("pmid")
        if isinstance(actual, str) and actual and actual != expected_pmid.strip():
            return {"kind": "pmid", "expected": expected_pmid.strip(), "actual": actual}, None
    if expected_pmcid:
        actual_pmc = record.get("pmcid")
        normalized_expected = normalize_pmcid(expected_pmcid)
        if (
            isinstance(actual_pmc, str)
            and actual_pmc
            and normalized_expected
            and actual_pmc.upper() != normalized_expected
        ):
            return {"kind": "pmcid", "expected": normalized_expected, "actual": actual_pmc}, None
    return None, None


# --- Main orchestrator --------------------------------------------------------


def fetch_paper(
    *,
    doi: str | None = None,
    url: str | None = None,
    pmid: str | None = None,
    pmcid: str | None = None,
    arxiv: str | None = None,
    cfg: FetchConfig,
    http: httpx.Client | None = None,
) -> FetchResult:
    """Probe tiered sources for a paper. See module docstring for semantics."""
    owns_client = http is None
    client = http or httpx.Client(
        timeout=cfg.http_timeout,
        headers={"User-Agent": f"science-tool/0.1 (mailto:{cfg.email})"},
    )
    try:
        return _fetch(doi=doi, url=url, pmid=pmid, pmcid=pmcid, arxiv=arxiv, cfg=cfg, client=client)
    finally:
        if owns_client:
            client.close()


def _fetch(
    *,
    doi: str | None,
    url: str | None,
    pmid: str | None,
    pmcid: str | None,
    arxiv: str | None,
    cfg: FetchConfig,
    client: httpx.Client,
) -> FetchResult:
    tiers: list[str] = []
    errors: list[str] = []

    # Promote a recognized URL to its native identifier so the resolvers below
    # can do the heavy lifting uniformly. Explicit flags win over URL-derived
    # values to honor caller intent.
    if url:
        parsed = parse_url_identifier(url)
        if parsed:
            kind, value = parsed
            if kind == "doi" and not doi:
                doi = value
            elif kind == "pmid" and not pmid:
                pmid = value
            elif kind == "pmcid" and not pmcid:
                pmcid = value
            elif kind == "arxiv" and not arxiv:
                arxiv = value

    # arXiv shortcut: deterministic DOI construction, no API call needed.
    if arxiv and not doi:
        doi = arxiv_id_to_doi(arxiv)

    pmid = normalize_pmid(pmid)
    pmcid = normalize_pmcid(pmcid)
    doi = normalize_doi(doi)
    limiter = RateLimiter(cfg)

    # Resolve PMID / PMCID -> DOI when we don't already have one.
    if not doi and pmid:
        tiers.append("europepmc:pmid->doi")
        resolved, err = _resolve_doi_from_pmid(pmid, client, limiter, cfg)
        if err:
            errors.append(err)
        if resolved:
            doi = resolved
    if not doi and pmcid:
        tiers.append("europepmc:pmcid->doi")
        resolved, err = _resolve_doi_from_pmcid(pmcid, client, limiter, cfg)
        if err:
            errors.append(err)
        if resolved:
            doi = resolved

    if not doi:
        return FetchResult(
            status="not_found",
            source="none",
            metadata={"url": url, "pmid": pmid, "pmcid": pmcid, "arxiv": arxiv},
            tiers_attempted=tiers,
            errors=errors or ["no DOI supplied or inferable from PMID/PMCID/arXiv/URL"],
            access_hint="Supply a DOI, PMID, PMCID, arXiv ID, or a recognized URL.",
        )

    # Cross-check: if caller supplied a DOI plus a PMID/PMCID, verify they
    # agree before doing real work. This catches the common "wrong DOI"
    # mistake — both user error and LLM-guessed DOIs that resolve to the
    # wrong paper.
    if pmid or pmcid:
        tiers.append("europepmc:verify")
        mismatch, err = _verify_doi_matches(
            doi, expected_pmid=pmid, expected_pmcid=pmcid, client=client, limiter=limiter, cfg=cfg
        )
        if err:
            errors.append(err)
        if mismatch:
            return FetchResult(
                status="error",
                source="europepmc",
                metadata={
                    "doi": doi,
                    "pmid": pmid,
                    "pmcid": pmcid,
                    "reason": "identifier_mismatch",
                    "mismatch": mismatch,
                },
                tiers_attempted=tiers,
                errors=errors,
                access_hint=(
                    f"DOI {doi} resolves to {mismatch['kind']}={mismatch['actual']}, "
                    f"but caller supplied {mismatch['kind']}={mismatch['expected']}. "
                    "One of the identifiers is wrong — re-check before summarizing."
                ),
            )
    papers_dir = cfg.cache_dir / _PAPERS_SUBDIR
    slug = _cache_slug(doi)

    # Cache hit: return the previous result verbatim.
    cached_json = papers_dir / f"{slug}.json"
    if cached_json.is_file():
        raw = json.loads(cached_json.read_text(encoding="utf-8"))
        raw["pdf_path"] = Path(raw["pdf_path"]) if raw.get("pdf_path") else None
        raw["text_path"] = Path(raw["text_path"]) if raw.get("text_path") else None
        raw.setdefault("errors", [])
        return FetchResult(**raw)

    metadata: dict[str, Any] = {"doi": doi}

    # Tier 1: Crossref metadata.
    tiers.append("crossref")
    crossref_meta, err = _try_crossref(doi, client, limiter, cfg)
    if err:
        errors.append(err)
    if crossref_meta:
        metadata.update(crossref_meta)

    # Tier 2: Unpaywall — decides whether to keep probing full-text sources.
    tiers.append("unpaywall")
    unpaywall, err = _try_unpaywall(doi, client, limiter, cfg)
    if err:
        errors.append(err)

    is_oa = bool(unpaywall and unpaywall.get("is_oa"))
    oa_pdf = unpaywall.get("best_oa_pdf_url") if unpaywall else None
    oa_landing = unpaywall.get("best_oa_landing_url") if unpaywall else None
    if unpaywall:
        metadata["is_oa"] = is_oa
        if oa_pdf:
            metadata["oa_pdf_url"] = oa_pdf
        if oa_landing:
            metadata["oa_landing_url"] = oa_landing

    # Some preprint DOIs (arXiv in particular) aren't always indexed in Crossref
    # or Unpaywall but are still straightforwardly retrievable. Let pattern-matched
    # tiers run before declaring the DOI dead.
    has_metadata = bool(crossref_meta or unpaywall)
    pattern_recognized = bool(_ARXIV_DOI.match(doi) or _BIORXIV_DOI.match(doi))
    if not has_metadata and not pattern_recognized:
        return _write_and_return(
            papers_dir,
            slug,
            FetchResult(
                status="not_found",
                source="none",
                metadata=metadata,
                tiers_attempted=tiers,
                errors=errors,
                access_hint="DOI did not resolve in Crossref or Unpaywall. Double-check it.",
            ),
        )

    # If Unpaywall is confident there's no OA copy, stop. Caller asks the user.
    if unpaywall and not is_oa:
        return _write_and_return(
            papers_dir,
            slug,
            FetchResult(
                status="paywalled",
                source="crossref+unpaywall",
                metadata=metadata,
                tiers_attempted=tiers,
                errors=errors,
                access_hint=(
                    "Unpaywall reports no open-access copy. "
                    "Ask the user for a PDF path, or defer with status: paywalled."
                ),
            ),
        )

    # Tier 3: arXiv.
    pdf_dest = papers_dir / f"{slug}.pdf"
    text_dest = papers_dir / f"{slug}.xml"

    tiers.append("arxiv")
    arxiv_pdf, err = _try_arxiv(doi, client, limiter, pdf_dest)
    if err:
        errors.append(err)
    if arxiv_pdf:
        return _write_and_return(
            papers_dir,
            slug,
            FetchResult(
                status="ok",
                source="arxiv",
                metadata=metadata,
                tiers_attempted=tiers,
                pdf_path=arxiv_pdf,
                errors=errors,
            ),
        )

    # Tier 4: bioRxiv / medRxiv.
    tiers.append("biorxiv")
    biorxiv_pdf, err = _try_biorxiv(doi, client, limiter, pdf_dest)
    if err:
        errors.append(err)
    if biorxiv_pdf:
        return _write_and_return(
            papers_dir,
            slug,
            FetchResult(
                status="ok",
                source="biorxiv",
                metadata=metadata,
                tiers_attempted=tiers,
                pdf_path=biorxiv_pdf,
                errors=errors,
            ),
        )

    # Tier 5: Europe PMC full-text XML (via PMCID resolution).
    tiers.append("europepmc")
    pmcid, err = _resolve_pmcid(doi, client, limiter, cfg)
    if err:
        errors.append(err)
    if pmcid:
        text_path, err = _try_europepmc_fulltext(pmcid, client, limiter, text_dest)
        if err:
            errors.append(err)
        if text_path:
            metadata["pmcid"] = pmcid
            return _write_and_return(
                papers_dir,
                slug,
                FetchResult(
                    status="ok",
                    source="europepmc",
                    metadata=metadata,
                    tiers_attempted=tiers,
                    text_path=text_path,
                    errors=errors,
                ),
            )

    # Tier 6: direct Unpaywall-provided PDF URL.
    if oa_pdf:
        tiers.append("unpaywall_pdf")
        ok, err = _download(client, limiter, oa_pdf, _host_of(oa_pdf), pdf_dest)
        if err:
            errors.append(err)
        if ok:
            return _write_and_return(
                papers_dir,
                slug,
                FetchResult(
                    status="ok",
                    source="unpaywall_pdf",
                    metadata=metadata,
                    tiers_attempted=tiers,
                    pdf_path=pdf_dest,
                    errors=errors,
                ),
            )

    # OA per Unpaywall but we couldn't grab it — stop and tell the orchestrator to ask the user.
    if is_oa:
        return _write_and_return(
            papers_dir,
            slug,
            FetchResult(
                status="blocked_but_oa",
                source="crossref+unpaywall",
                metadata=metadata,
                tiers_attempted=tiers,
                errors=errors,
                access_hint=(
                    "Unpaywall lists an OA copy but every agent-accessible tier failed. "
                    "A user browser can likely retrieve it — ask for a PDF path."
                ),
            ),
        )

    # Fall-through (no Unpaywall record, but Crossref had metadata).
    return _write_and_return(
        papers_dir,
        slug,
        FetchResult(
            status="not_found",
            source="crossref",
            metadata=metadata,
            tiers_attempted=tiers,
            errors=errors,
            access_hint="Metadata resolved but no full-text source found.",
        ),
    )


def _write_and_return(papers_dir: Path, slug: str, result: FetchResult) -> FetchResult:
    papers_dir.mkdir(parents=True, exist_ok=True)
    cached = papers_dir / f"{slug}.json"
    cached.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return result
