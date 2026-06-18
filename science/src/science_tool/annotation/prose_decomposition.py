from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from science_tool.annotation.statement_extract import CandidateError, StatementCandidate, parse_candidates

SUPPORTED_SCHEMA_VERSION = 1
SOURCE_KIND = "prose-source"
SKIP_REASON_CODES = frozenset(
    {
        "meta_commentary",
        "not_a_claim",
        "duplicate_or_restatement",
        "citation_or_reference_only",
        "out_of_scope",
        "unresolved_or_malformed",
    }
)
LOCATOR_REGIMES = frozenset({"markdown-heading-path", "markdown-heading-path-with-quote"})
_TOP_LEVEL_KEYS = frozenset({"schema_version", "source", "artifact", "units"})
_SOURCE_KEYS = frozenset({"kind", "slug", "path", "title", "content_hash"})
_ARTIFACT_KEYS = frozenset({"id", "generated_at", "producer"})
_CANDIDATE_UNIT_KEYS = frozenset({"unit_id", "disposition", "locator", "payload"})
_SKIP_UNIT_KEYS = frozenset({"unit_id", "disposition", "locator", "reason"})
_LOCATOR_KEYS = frozenset({"regime", "value", "quote"})
_QUOTE_KEYS = frozenset({"exact", "prefix", "suffix"})
_REASON_KEYS = frozenset({"code", "detail"})
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_ID_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?$")


class DecompositionError(ValueError):
    """Raised when a prose decomposition artifact is structurally invalid."""


@dataclass(frozen=True)
class Quote:
    exact: str
    prefix: str = ""
    suffix: str = ""


@dataclass(frozen=True)
class MarkdownLocator:
    regime: str
    heading_path: tuple[str, ...]
    quote: Quote | None = None


@dataclass(frozen=True)
class DecompositionSource:
    kind: str
    slug: str
    path: Path
    title: str
    content_hash: str


@dataclass(frozen=True)
class DecompositionArtifactMeta:
    artifact_id: str
    generated_at: str
    producer: str


@dataclass(frozen=True)
class DecompositionUnit:
    unit_id: str
    disposition: Literal["candidate", "skip"]
    locator: MarkdownLocator
    fingerprint: str
    candidate: StatementCandidate | None = None
    reason_code: str | None = None
    reason_detail: str = ""


@dataclass(frozen=True)
class DecompositionArtifact:
    schema_version: int
    source: DecompositionSource
    artifact: DecompositionArtifactMeta
    units: tuple[DecompositionUnit, ...]

    @property
    def source_ref(self) -> str:
        return f"{self.source.kind}:{self.source.slug}"


@dataclass(frozen=True)
class StorePersistReport:
    source_slug: str
    artifact_id: str
    stale_fingerprints: list[str]


_SPACE_RE = re.compile(r"\s+")


def parse_submitted_decomposition(raw: str, *, project_root: Path) -> DecompositionArtifact:
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DecompositionError(f"decomposition input is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise DecompositionError("decomposition input must be a JSON object")
    _reject_unknown_keys(doc, allowed=_TOP_LEVEL_KEYS, label="top-level")

    schema_version = doc.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise DecompositionError(f"schema_version must be {SUPPORTED_SCHEMA_VERSION}")

    source = _parse_source(doc.get("source"), project_root=project_root)
    artifact_meta = _parse_artifact_meta(doc.get("artifact"))
    units = _parse_units(doc.get("units"), source_ref=f"{source.kind}:{source.slug}")
    return DecompositionArtifact(
        schema_version=schema_version,
        source=source,
        artifact=artifact_meta,
        units=units,
    )


def artifact_storage_root(project_root: Path, slug: str) -> Path:
    return project_root / "data" / "prose-decompositions" / slug


def artifact_generation_relpath(artifact: DecompositionArtifact) -> Path:
    return (
        Path("data")
        / "prose-decompositions"
        / artifact.source.slug
        / "generations"
        / f"{artifact.artifact.artifact_id}.json"
    )


def artifact_unit_ref(artifact: DecompositionArtifact, unit: DecompositionUnit) -> str:
    return f"annotation:{artifact_generation_relpath(artifact).as_posix()}#{unit.unit_id}"


class ProseDecompositionStore:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def source_dir(self, slug: str) -> Path:
        slug = _validate_store_slug(slug)
        return artifact_storage_root(self.project_root, slug)

    def generation_path(self, artifact: DecompositionArtifact) -> Path:
        return self.project_root / artifact_generation_relpath(artifact)

    def index_path(self, slug: str) -> Path:
        slug = _validate_store_slug(slug)
        return self.source_dir(slug) / "index.json"

    def load_index(self, slug: str) -> dict[str, Any]:
        slug = _validate_store_slug(slug)
        path = self.index_path(slug)
        if not path.exists():
            return {
                "schema_version": 1,
                "source_ref": f"prose-source:{slug}",
                "latest_artifact_id": "",
                "artifacts": [],
                "units": {},
            }
        return json.loads(path.read_text(encoding="utf-8"))

    def persist(self, artifact: DecompositionArtifact) -> StorePersistReport:
        slug = artifact.source.slug
        artifact_id = artifact.artifact.artifact_id
        _atomic_write_json(self.generation_path(artifact), _artifact_to_json_payload(artifact))

        state = self.load_index(slug)
        if artifact_id not in state["artifacts"]:
            state["artifacts"].append(artifact_id)
        state["latest_artifact_id"] = artifact_id

        unit_rows = state["units"]
        current_fingerprints = {unit.fingerprint for unit in artifact.units}
        stale_fingerprints = sorted(set(unit_rows) - current_fingerprints)
        for fingerprint in stale_fingerprints:
            unit_rows[fingerprint]["stale"] = True

        for unit in artifact.units:
            existing = unit_rows.get(unit.fingerprint, {})
            row = dict(existing)
            row.update(
                {
                    "latest_unit_id": unit.unit_id,
                    "latest_artifact_id": artifact_id,
                    "latest_disposition": unit.disposition,
                    "artifact_unit_ref": artifact_unit_ref(artifact, unit),
                    "stale": False,
                }
            )
            unit_rows[unit.fingerprint] = row

        _atomic_write_json(self.index_path(slug), state)
        return StorePersistReport(source_slug=slug, artifact_id=artifact_id, stale_fingerprints=stale_fingerprints)

    def record_promotion(self, source_slug: str, fingerprint: str, promoted_to: str) -> None:
        source_slug = _validate_store_slug(source_slug)
        state = self.load_index(source_slug)
        if fingerprint not in state["units"]:
            raise DecompositionError(f"unknown decomposition unit fingerprint: {fingerprint}")
        state["units"][fingerprint]["promoted_to"] = promoted_to
        _atomic_write_json(self.index_path(source_slug), state)

    def load_latest(self, slug: str) -> DecompositionArtifact:
        slug = _validate_store_slug(slug)
        index = self.load_index(slug)
        if not isinstance(index, dict):
            raise DecompositionError(f"prose decomposition index must be an object for source slug: {slug}")
        artifact_id = index.get("latest_artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise DecompositionError(f"missing latest decomposition artifact for source slug: {slug}")
        artifact_id = _validate_store_artifact_id(artifact_id)
        path = self.source_dir(slug) / "generations" / f"{artifact_id}.json"
        if not path.exists():
            raise DecompositionError(f"latest prose decomposition generation is missing: {path}")
        return parse_submitted_decomposition(path.read_text(encoding="utf-8"), project_root=self.project_root)


def compute_source_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_text(value: str) -> str:
    return _SPACE_RE.sub(" ", value.strip()).casefold()


def source_span_fingerprint(
    *,
    source_ref: str,
    locator: MarkdownLocator,
    quote: Quote,
) -> str:
    payload = {
        "source_ref": source_ref,
        "locator_regime": locator.regime,
        "heading_path": [normalize_text(part) for part in locator.heading_path],
        "quote": {
            "exact": normalize_text(quote.exact),
            "prefix": normalize_text(quote.prefix),
            "suffix": normalize_text(quote.suffix),
        },
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _parse_source(raw: Any, *, project_root: Path) -> DecompositionSource:
    if not isinstance(raw, dict):
        raise DecompositionError("source must be an object")
    _reject_unknown_keys(raw, allowed=_SOURCE_KEYS, label="source")

    kind = _required_string(raw, "source.kind")
    if kind != SOURCE_KIND:
        raise DecompositionError(f"source.kind must be {SOURCE_KIND!r}")

    slug = _required_slug(raw, "source.slug")
    path_text = _required_string(raw, "source.path")
    title = _required_string(raw, "source.title")
    content_hash = _required_string(raw, "source.content_hash")
    return DecompositionSource(
        kind=kind,
        slug=slug,
        path=_resolve_source_path(path_text, project_root=project_root),
        title=title,
        content_hash=content_hash,
    )


def _parse_artifact_meta(raw: Any) -> DecompositionArtifactMeta:
    if not isinstance(raw, dict):
        raise DecompositionError("artifact must be an object")
    _reject_unknown_keys(raw, allowed=_ARTIFACT_KEYS, label="artifact")
    return DecompositionArtifactMeta(
        artifact_id=_required_identifier(raw, "artifact.id"),
        generated_at=_required_string(raw, "artifact.generated_at"),
        producer=_required_string(raw, "artifact.producer"),
    )


def _parse_units(raw: Any, *, source_ref: str) -> tuple[DecompositionUnit, ...]:
    if not isinstance(raw, list):
        raise DecompositionError("units must be an array")

    seen_unit_ids: set[str] = set()
    units: list[DecompositionUnit] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise DecompositionError(f"unit[{idx}] must be an object")
        disposition = _required_string(item, f"unit[{idx}].disposition")
        if disposition == "candidate":
            _reject_unknown_keys(item, allowed=_CANDIDATE_UNIT_KEYS, label="unit")
        elif disposition == "skip":
            _reject_unknown_keys(item, allowed=_SKIP_UNIT_KEYS, label="unit")
        else:
            raise DecompositionError(f"unit[{idx}].disposition must be 'candidate' or 'skip'")

        unit_id = _required_identifier(item, f"unit[{idx}].unit_id")
        if unit_id in seen_unit_ids:
            raise DecompositionError(f"duplicate unit_id: {unit_id}")
        seen_unit_ids.add(unit_id)

        locator = _parse_locator(item.get("locator"), unit_index=idx)
        if disposition == "candidate":
            units.append(_parse_candidate_unit(item, unit_id=unit_id, locator=locator, source_ref=source_ref))
        elif disposition == "skip":
            units.append(_parse_skip_unit(item, unit_id=unit_id, locator=locator, source_ref=source_ref))
        else:
            raise DecompositionError(f"unit[{idx}].disposition must be 'candidate' or 'skip'")
    return tuple(units)


def _parse_candidate_unit(
    item: dict[str, Any],
    *,
    unit_id: str,
    locator: MarkdownLocator,
    source_ref: str,
) -> DecompositionUnit:
    if locator.regime != "markdown-heading-path":
        raise DecompositionError("candidate unit locator.regime must be 'markdown-heading-path'")
    if locator.quote is not None:
        raise DecompositionError("candidate unit must not carry locator.quote")
    payload = item.get("payload")
    try:
        candidates = parse_candidates(json.dumps({"candidates": [payload]}))
    except (CandidateError, TypeError) as exc:
        raise DecompositionError(f"candidate unit payload must be a StatementCandidate: {exc}") from exc
    candidate = candidates[0]
    if not isinstance(candidate, StatementCandidate):
        raise DecompositionError("candidate unit payload must be a StatementCandidate")

    quote = Quote(exact=candidate.exact, prefix=candidate.prefix, suffix=candidate.suffix)
    return DecompositionUnit(
        unit_id=unit_id,
        disposition="candidate",
        locator=locator,
        fingerprint=source_span_fingerprint(source_ref=source_ref, locator=locator, quote=quote),
        candidate=candidate,
    )


def _parse_skip_unit(
    item: dict[str, Any],
    *,
    unit_id: str,
    locator: MarkdownLocator,
    source_ref: str,
) -> DecompositionUnit:
    if locator.regime != "markdown-heading-path-with-quote":
        raise DecompositionError("skip unit locator.regime must be 'markdown-heading-path-with-quote'")
    raw_reason = item.get("reason")
    if not isinstance(raw_reason, dict):
        raise DecompositionError("skip unit reason must be an object")
    _reject_unknown_keys(raw_reason, allowed=_REASON_KEYS, label="reason")
    reason_code = _required_string(raw_reason, "reason.code")
    if reason_code not in SKIP_REASON_CODES:
        raise DecompositionError(f"unknown skip reason: {reason_code}")
    reason_detail = raw_reason.get("detail", "")
    if not isinstance(reason_detail, str):
        raise DecompositionError("reason.detail must be a string")
    if locator.quote is None:
        raise DecompositionError("skip unit must carry locator.quote")

    return DecompositionUnit(
        unit_id=unit_id,
        disposition="skip",
        locator=locator,
        fingerprint=source_span_fingerprint(source_ref=source_ref, locator=locator, quote=locator.quote),
        reason_code=reason_code,
        reason_detail=reason_detail,
    )


def _parse_locator(raw: Any, *, unit_index: int) -> MarkdownLocator:
    if not isinstance(raw, dict):
        raise DecompositionError(f"unit[{unit_index}].locator must be an object")
    _reject_unknown_keys(raw, allowed=_LOCATOR_KEYS, label="locator")

    regime = _required_string(raw, f"unit[{unit_index}].locator.regime")
    if regime not in LOCATOR_REGIMES:
        raise DecompositionError(f"unknown locator regime: {regime}")

    value = raw.get("value")
    if not isinstance(value, list) or not value:
        raise DecompositionError(f"unit[{unit_index}].locator.value must be a non-empty list")
    heading_path = []
    for part_idx, part in enumerate(value):
        if not isinstance(part, str) or not part:
            raise DecompositionError(f"unit[{unit_index}].locator.value[{part_idx}] must be a non-empty string")
        heading_path.append(part)

    quote = None
    if "quote" in raw:
        quote = _parse_quote(raw["quote"], field_name=f"unit[{unit_index}].locator.quote")
    return MarkdownLocator(regime=regime, heading_path=tuple(heading_path), quote=quote)


def _parse_quote(raw: Any, *, field_name: str) -> Quote:
    if not isinstance(raw, dict):
        raise DecompositionError(f"{field_name} must be an object")
    _reject_unknown_keys(raw, allowed=_QUOTE_KEYS, label="quote")
    exact = _required_string(raw, f"{field_name}.exact")
    prefix = _optional_string(raw, f"{field_name}.prefix")
    suffix = _optional_string(raw, f"{field_name}.suffix")
    return Quote(exact=exact, prefix=prefix, suffix=suffix)


def _required_string(raw: dict[str, Any], dotted_name: str) -> str:
    key = dotted_name.rsplit(".", 1)[-1]
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise DecompositionError(f"{dotted_name} must be a non-empty string")
    return value


def _optional_string(raw: dict[str, Any], dotted_name: str) -> str:
    key = dotted_name.rsplit(".", 1)[-1]
    value = raw.get(key, "")
    if not isinstance(value, str):
        raise DecompositionError(f"{dotted_name} must be a string")
    return value


def _required_slug(raw: dict[str, Any], dotted_name: str) -> str:
    value = _required_string(raw, dotted_name)
    if not _SLUG_RE.fullmatch(value):
        raise DecompositionError(f"{dotted_name} must be a filesystem-safe lowercase slug")
    return value


def _required_identifier(raw: dict[str, Any], dotted_name: str) -> str:
    value = _required_string(raw, dotted_name)
    if not _ID_RE.fullmatch(value):
        raise DecompositionError(f"{dotted_name} must be path and fragment safe")
    return value


def _validate_store_slug(slug: str) -> str:
    if not isinstance(slug, str) or not _SLUG_RE.fullmatch(slug):
        raise DecompositionError("store source slug must be filesystem-safe lowercase slug")
    return slug


def _validate_store_artifact_id(artifact_id: str) -> str:
    if not _ID_RE.fullmatch(artifact_id):
        raise DecompositionError("latest decomposition artifact id must be path and fragment safe")
    return artifact_id


def _reject_unknown_keys(raw: dict[str, Any], *, allowed: frozenset[str], label: str) -> None:
    extra = set(raw) - allowed
    if extra:
        raise DecompositionError(f"unknown {label} keys: {sorted(extra)}")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _artifact_to_json_payload(artifact: DecompositionArtifact) -> dict[str, Any]:
    return {
        "schema_version": artifact.schema_version,
        "source": {
            "kind": artifact.source.kind,
            "slug": artifact.source.slug,
            "path": str(artifact.source.path),
            "title": artifact.source.title,
            "content_hash": artifact.source.content_hash,
        },
        "artifact": {
            "id": artifact.artifact.artifact_id,
            "generated_at": artifact.artifact.generated_at,
            "producer": artifact.artifact.producer,
        },
        "units": [_unit_to_json_payload(unit) for unit in artifact.units],
    }


def _unit_to_json_payload(unit: DecompositionUnit) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "unit_id": unit.unit_id,
        "disposition": unit.disposition,
        "locator": _locator_to_json_payload(unit.locator),
    }
    if unit.disposition == "candidate":
        if unit.candidate is None:
            raise DecompositionError(f"candidate unit {unit.unit_id} is missing candidate payload")
        payload["payload"] = _candidate_to_json_payload(unit.candidate)
        return payload
    if unit.reason_code is None:
        raise DecompositionError(f"skip unit {unit.unit_id} is missing skip reason")
    payload["reason"] = {"code": unit.reason_code, "detail": unit.reason_detail}
    return payload


def _locator_to_json_payload(locator: MarkdownLocator) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "regime": locator.regime,
        "value": list(locator.heading_path),
    }
    if locator.quote is not None:
        payload["quote"] = _quote_to_json_payload(locator.quote)
    return payload


def _quote_to_json_payload(quote: Quote) -> dict[str, Any]:
    return {
        "exact": quote.exact,
        "prefix": quote.prefix,
        "suffix": quote.suffix,
    }


def _candidate_to_json_payload(candidate: StatementCandidate) -> dict[str, Any]:
    payload = {
        "type": candidate.type,
        "exact": candidate.exact,
        "prefix": candidate.prefix,
        "suffix": candidate.suffix,
        "stance": candidate.stance,
    }
    for key in ("subject", "object", "subject_concept", "object_concept"):
        value = getattr(candidate, key)
        if value is not None:
            payload[key] = value
    return payload


def _resolve_source_path(value: str, *, project_root: Path) -> Path:
    if value == "~/d/science":
        return project_root
    if value.startswith("~/d/science/"):
        suffix = value.removeprefix("~/d/science").lstrip("/")
        return project_root / suffix
    return Path(value).expanduser()
