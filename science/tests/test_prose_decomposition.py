import json
from pathlib import Path

import pytest

from science_tool.annotation.prose_decomposition import (
    DecompositionError,
    ProseDecompositionStore,
    artifact_unit_ref,
    parse_submitted_decomposition,
)


def _artifact(tmp_path: Path, *, unit_id: str = "u001", heading=None, quote=None) -> dict:
    if heading is None:
        heading = ["Section"]
    if quote is None:
        quote = "Basalt flows record the cooling history."
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# Section\n\nBasalt flows record the cooling history.\n", encoding="utf-8")
    return {
        "schema_version": 1,
        "source": {
            "kind": "prose-source",
            "slug": "example",
            "path": str(source),
            "title": "Example",
            "content_hash": "sha256:" + "0" * 64,
        },
        "artifact": {
            "id": "decomp-1",
            "generated_at": "2026-06-18T12:00:00Z",
            "producer": "offline-agent",
        },
        "units": [
            {
                "unit_id": unit_id,
                "disposition": "candidate",
                "locator": {"regime": "markdown-heading-path", "value": heading},
                "payload": {
                    "type": "proposition",
                    "exact": quote,
                    "prefix": "",
                    "suffix": "",
                    "stance": "asserted",
                },
            },
            {
                "unit_id": "s001",
                "disposition": "skip",
                "reason": {"code": "not_a_claim", "detail": "Heading only."},
                "locator": {
                    "regime": "markdown-heading-path-with-quote",
                    "value": ["Section"],
                    "quote": {"exact": "Basalt flows", "prefix": "", "suffix": ""},
                },
            },
        ],
    }


def test_parse_valid_decomposition(tmp_path):
    artifact = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    assert artifact.schema_version == 1
    assert artifact.source_ref == "prose-source:example"
    assert artifact.units[0].unit_id == "u001"
    assert artifact.units[0].candidate is not None
    assert artifact.units[1].reason_code == "not_a_claim"


def test_candidate_locator_quote_is_rejected(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][0]["locator"]["quote"] = {"exact": "duplicate", "prefix": "", "suffix": ""}
    with pytest.raises(DecompositionError, match="candidate unit must not carry locator.quote"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_unknown_skip_reason_fails(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][1]["reason"]["code"] = "mystery"
    with pytest.raises(DecompositionError, match="unknown skip reason"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_candidate_payload_must_be_statement_candidate(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][0]["payload"] = {
        "type": "metaphor",
        "exact": "Basalt flows",
        "prefix": "",
        "suffix": "",
        "source_domain": "geology",
        "target_domain": "history",
    }
    with pytest.raises(DecompositionError, match="StatementCandidate"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_duplicate_unit_id_fails(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][1]["unit_id"] = "u001"
    with pytest.raises(DecompositionError, match="duplicate unit_id"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda raw: raw.__setitem__("extra", True), "unknown top-level keys"),
        (lambda raw: raw["source"].__setitem__("extra", True), "unknown source keys"),
        (lambda raw: raw["artifact"].__setitem__("extra", True), "unknown artifact keys"),
        (lambda raw: raw["units"][0].__setitem__("extra", True), "unknown unit keys"),
        (lambda raw: raw["units"][0]["locator"].__setitem__("extra", True), "unknown locator keys"),
        (lambda raw: raw["units"][1]["locator"]["quote"].__setitem__("extra", True), "unknown quote keys"),
        (lambda raw: raw["units"][1]["reason"].__setitem__("extra", True), "unknown reason keys"),
    ],
)
def test_unknown_keys_fail_closed_schema(tmp_path, mutate, match):
    raw = _artifact(tmp_path)
    mutate(raw)
    with pytest.raises(DecompositionError, match=match):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("source.slug", "../bad", "source.slug"),
        ("artifact.id", "../bad", "artifact.id"),
        ("unit_id", "u001#bad", "unit_id"),
    ],
)
def test_path_and_fragment_identifiers_are_validated(tmp_path, field, value, match):
    raw = _artifact(tmp_path)
    if field == "source.slug":
        raw["source"]["slug"] = value
    elif field == "artifact.id":
        raw["artifact"]["id"] = value
    else:
        raw["units"][0]["unit_id"] = value
    with pytest.raises(DecompositionError, match=match):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_candidate_must_use_heading_path_locator_regime(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][0]["locator"]["regime"] = "markdown-heading-path-with-quote"
    with pytest.raises(DecompositionError, match="candidate unit locator.regime"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_skip_must_use_heading_path_with_quote_locator_regime(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][1]["locator"]["regime"] = "markdown-heading-path"
    with pytest.raises(DecompositionError, match="skip unit locator.regime"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_d_science_path_rewrite_respects_path_boundary(tmp_path):
    raw = _artifact(tmp_path)
    raw["source"]["path"] = "~/d/science-old/foo.md"
    artifact = parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)
    assert artifact.source.path == Path("~/d/science-old/foo.md").expanduser()


def test_fingerprint_ignores_artifact_local_unit_id(tmp_path):
    first = parse_submitted_decomposition(json.dumps(_artifact(tmp_path, unit_id="u001")), project_root=tmp_path)
    second = parse_submitted_decomposition(json.dumps(_artifact(tmp_path, unit_id="u777")), project_root=tmp_path)
    assert first.units[0].fingerprint == second.units[0].fingerprint


def test_artifact_unit_ref_uses_annotation_namespace(tmp_path):
    artifact = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    assert artifact_unit_ref(artifact, artifact.units[0]) == (
        "annotation:data/prose-decompositions/example/generations/decomp-1.json#u001"
    )


def test_store_persists_generation_and_index(tmp_path):
    artifact = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    report = store.persist(artifact)
    index_path = tmp_path / "data" / "prose-decompositions" / "example" / "index.json"
    assert report.artifact_id == "decomp-1"
    assert report.stale_fingerprints == []
    assert (tmp_path / "data" / "prose-decompositions" / "example" / "generations" / "decomp-1.json").exists()
    assert index_path.exists()
    state = json.loads(index_path.read_text(encoding="utf-8"))
    assert state["source_ref"] == "prose-source:example"
    assert state["artifacts"] == ["decomp-1"]
    assert state["latest_artifact_id"] == "decomp-1"
    row = state["units"][artifact.units[0].fingerprint]
    assert row["latest_unit_id"] == "u001"
    assert row["latest_artifact_id"] == "decomp-1"
    assert row["latest_disposition"] == "candidate"
    assert row["artifact_unit_ref"] == artifact_unit_ref(artifact, artifact.units[0])
    assert row["stale"] is False


def test_store_persist_allows_identical_generation_replay(tmp_path):
    first = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    replay = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    store.persist(first)
    generation_path = store.generation_path(first)
    generation_text = generation_path.read_text(encoding="utf-8")

    report = store.persist(replay)

    assert report.artifact_id == "decomp-1"
    assert generation_path.read_text(encoding="utf-8") == generation_text
    state = store.load_index("example")
    assert state["artifacts"] == ["decomp-1"]
    assert state["latest_artifact_id"] == "decomp-1"
    assert state["units"][first.units[0].fingerprint]["latest_unit_id"] == "u001"


def test_store_persist_rejects_conflicting_generation_replay_without_index_update(tmp_path):
    first = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    conflicting_raw = _artifact(tmp_path, unit_id="u777", quote="A different claim.")
    conflicting = parse_submitted_decomposition(json.dumps(conflicting_raw), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    store.persist(first)
    generation_path = store.generation_path(first)
    index_path = store.index_path("example")
    generation_text = generation_path.read_text(encoding="utf-8")
    index_text = index_path.read_text(encoding="utf-8")

    with pytest.raises(DecompositionError, match="generation already exists|immutable"):
        store.persist(conflicting)

    assert generation_path.read_text(encoding="utf-8") == generation_text
    assert index_path.read_text(encoding="utf-8") == index_text


def test_store_marks_missing_fingerprint_stale(tmp_path):
    first = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    raw_second = _artifact(tmp_path, quote="A different claim.")
    raw_second["artifact"]["id"] = "decomp-2"
    second = parse_submitted_decomposition(json.dumps(raw_second), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    store.persist(first)
    report = store.persist(second)
    assert len(report.stale_fingerprints) == 1
    state = store.load_index("example")
    assert state["units"][first.units[0].fingerprint]["stale"] is True
    assert state["units"][second.units[0].fingerprint]["stale"] is False


def test_store_preserves_promoted_link_across_unit_renumber(tmp_path):
    first = parse_submitted_decomposition(json.dumps(_artifact(tmp_path, unit_id="u001")), project_root=tmp_path)
    second_raw = _artifact(tmp_path, unit_id="u777")
    second_raw["artifact"]["id"] = "decomp-2"
    second = parse_submitted_decomposition(json.dumps(second_raw), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    store.persist(first)
    store.record_promotion(source_slug="example", fingerprint=first.units[0].fingerprint, promoted_to="proposition:x")
    store.persist(second)
    state = store.load_index("example")
    assert state["units"][first.units[0].fingerprint]["promoted_to"] == "proposition:x"
    assert state["units"][first.units[0].fingerprint]["latest_unit_id"] == "u777"
    assert state["units"][first.units[0].fingerprint]["stale"] is False


def test_store_load_latest_reparses_generation(tmp_path):
    artifact = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    store.persist(artifact)
    latest = store.load_latest("example")
    assert latest.artifact.artifact_id == "decomp-1"
    assert latest.units[0].unit_id == "u001"


def test_store_load_latest_fails_loudly_when_index_lacks_latest_artifact(tmp_path):
    store = ProseDecompositionStore(tmp_path)
    index_path = store.index_path("example")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_ref": "prose-source:example",
                "latest_artifact_id": "",
                "artifacts": [],
                "units": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(DecompositionError, match="missing latest decomposition artifact"):
        store.load_latest("example")


def test_store_rejects_invalid_slug_before_path_construction(tmp_path):
    store = ProseDecompositionStore(tmp_path)
    with pytest.raises(DecompositionError, match="store source slug"):
        store.load_index("../escape")
    assert not (tmp_path / "data" / "escape").exists()


def test_store_load_index_rejects_invalid_json(tmp_path):
    store = ProseDecompositionStore(tmp_path)
    index_path = store.index_path("example")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(DecompositionError, match="invalid prose decomposition index JSON"):
        store.load_index("example")


@pytest.mark.parametrize(
    ("state", "match"),
    [
        ([], "must be an object"),
        ({"schema_version": 2, "source_ref": "prose-source:example", "latest_artifact_id": "", "artifacts": [], "units": {}}, "schema_version"),
        ({"schema_version": 1, "source_ref": "prose-source:example", "artifacts": [], "units": {}}, "latest_artifact_id"),
        ({"schema_version": 1, "source_ref": 7, "latest_artifact_id": "", "artifacts": [], "units": {}}, "source_ref"),
        ({"schema_version": 1, "source_ref": "prose-source:other", "latest_artifact_id": "", "artifacts": [], "units": {}}, "source_ref"),
        ({"schema_version": 1, "source_ref": "prose-source:example", "latest_artifact_id": None, "artifacts": [], "units": {}}, "latest_artifact_id"),
        ({"schema_version": 1, "source_ref": "prose-source:example", "latest_artifact_id": "../escape", "artifacts": [], "units": {}}, "latest_artifact_id"),
        ({"schema_version": 1, "source_ref": "prose-source:example", "latest_artifact_id": "", "artifacts": ["decomp-1", 2], "units": {}}, "artifacts"),
        ({"schema_version": 1, "source_ref": "prose-source:example", "latest_artifact_id": "", "artifacts": ["../escape"], "units": {}}, "artifact id"),
        ({"schema_version": 1, "source_ref": "prose-source:example", "latest_artifact_id": "", "artifacts": [], "units": []}, "units"),
        ({"schema_version": 1, "source_ref": "prose-source:example", "latest_artifact_id": "", "artifacts": [], "units": {"abc": []}}, "unit row"),
        ({"schema_version": 1, "source_ref": "prose-source:example", "latest_artifact_id": "", "artifacts": [], "units": {"abc": {"stale": "false"}}}, "stale"),
        ({"schema_version": 1, "source_ref": "prose-source:example", "latest_artifact_id": "", "artifacts": [], "units": {"abc": {"latest_unit_id": 7}}}, "latest_unit_id"),
        ({"schema_version": 1, "source_ref": "prose-source:example", "latest_artifact_id": "", "artifacts": [], "units": {"abc": {"promoted_to": 7}}}, "promoted_to"),
    ],
)
def test_store_load_index_rejects_malformed_shape(tmp_path, state, match):
    store = ProseDecompositionStore(tmp_path)
    index_path = store.index_path("example")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(DecompositionError, match=match):
        store.load_index("example")


def test_store_load_latest_rejects_malformed_index_artifact_id(tmp_path):
    store = ProseDecompositionStore(tmp_path)
    index_path = store.index_path("example")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_ref": "prose-source:example",
                "latest_artifact_id": "../escape",
                "artifacts": ["../escape"],
                "units": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(DecompositionError, match="latest decomposition artifact id"):
        store.load_latest("example")


def test_store_record_promotion_unknown_fingerprint_fails(tmp_path):
    artifact = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    store.persist(artifact)
    with pytest.raises(DecompositionError, match="unknown decomposition unit fingerprint"):
        store.record_promotion(source_slug="example", fingerprint="missing", promoted_to="proposition:x")


def test_store_load_latest_missing_generation_fails(tmp_path):
    store = ProseDecompositionStore(tmp_path)
    index_path = store.index_path("example")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_ref": "prose-source:example",
                "latest_artifact_id": "decomp-1",
                "artifacts": ["decomp-1"],
                "units": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(DecompositionError, match="latest prose decomposition generation is missing"):
        store.load_latest("example")
