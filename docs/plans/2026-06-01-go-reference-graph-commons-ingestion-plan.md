# GO Reference Graph Commons Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Drafted and reviewed 2026-06-01; revised per adversarial + user review (added required
`version`/`member_key_space` entity fields; S3 ListObjects archive listing instead of the client-side
browser HTML; preflight now computes the *projected* edge count and uses the build's own GO-membership
predicate; predicate encodings discovered at preflight rather than guessed; RG2 smoke uses the lower-level
`resolve_reference_graph_member_payload`; two-repo verification/commit). Ready to implement; not yet
implemented.

**Goal:** Ingest a pinned Gene Ontology release into `~/d/science-commons` as the second real
`bio.reference_graph` commons dataset (`dataset:go`), directly reusing the `obograph_json` recipe path
proven by `dataset:mondo` (RG4). This is the GO instantiation anticipated by
`docs/plans/2026-05-31-bio-reference-graph-design.md` (line 383: "Term graph keyed by `GO:` CURIEs;
obsolete/replaced terms matter; `is_a`/`part_of` edges live in graph artifact").

**Architecture:** GO is published as OBO Graph JSON. The recipe pins one immutable, dated GO release,
projects it into the implemented RG1 node-index + edge CSV contract, and registers a `dataset` +
`bio.reference_graph` entity whose canonical `graph` resource is the upstream `go.json` (hash-pinned). The
build is a near-direct clone of the MONDO recipe (`~/d/science-commons/datasets/mondo/recipe/build.py`)
with two GO-specific deltas settled below. **No science-repo schema or format changes are needed** — the
`obograph_json` graph format, the `reference_graph` node/edge parser, RG1 validation, and RG2 virtual
member payload resolution already shipped with MONDO and are reused unchanged.

**Tech Stack:** Python stdlib (`csv`, `hashlib`, `json`, `re`, `urllib.request`), `pyyaml`, the local
`science` package (`science_tool.commons.config.resolve_commons_data_root`,
`science_tool.commons.datapackage.stream_sha256_and_bytes`,
`science_tool.commons.reference_graph.parse_node_index_rows` / `parse_edge_rows`), `uv run --frozen
--project ~/d/science/science`, and the commons resolve/validate commands.

---

## Settled decisions (this plan)

1. **Product = full `go.json`** (not `go-basic.json`, not `go-plus.json`). Faithful complete term graph
   (`is_a`, `part_of`/`BFO:0000050`, `regulates`/`RO:*`, `has_part`, `occurs_in`, …), matching MONDO's
   "ingest the full ontology, do not pre-filter" precedent. Cross-ontology referents (e.g. `BFO:`, `RO:`,
   `CL:`) may appear as edge *endpoints* but are never `GO:` members; they are retained only via the
   keep-edge-if-either-endpoint-is-a-member rule, exactly as MONDO retains xref/edge targets.
2. **Sub-ontology carried in `member_kind`.** Each GO term's `member_kind` is its OBO namespace —
   `biological_process | molecular_function | cellular_component` — read from the
   `oboInOwl#hasOBONamespace` basic property value. `member_kind` is a free-string column (the
   `reference_graph` parser only requires it to be non-blank), so this is schema-valid and needs no
   extension; it generalizes MONDO's uniform `"term"`. A GO `CLASS` node with no resolvable namespace falls
   back to `member_kind: "term"` and is counted in `summary.namespace_fallback_count` — obsolete GO terms in
   particular frequently lack `hasOBONamespace`, so this count may be substantial (Task 1 measures it; do
   not assume "rare"). The BP/MF/CC split is also recorded in `summary.namespace_counts`.
3. **Predicates kept as `curie_or_iri(edge.pred)`**, identical to MONDO — no predicate-to-readable-token
   mapping (faithful + consistent with `dataset:mondo`). **Do not pre-assume the encoding.** `curie_or_iri`
   only normalizes IRIs matching `http://purl.obolibrary.org/obo/<PREFIX>_<id>`; a bare label like `is_a`
   passes through unchanged. GO's obograph may emit `part_of` either as the `BFO_0000050` PURL (→
   `BFO:0000050`) **or** as the bare label `"part_of"` depending on the ROBOT export. Task 1's preflight
   prints the distinct `edge.pred` value set, and Task 2's fixtures/assertions use whatever GO actually
   emits — not a guessed `BFO:0000050`.
4. **Pin source differs from MONDO.** GO does *not* publish GitHub release assets. The authoritative
   immutable handle is the dated release archive
   `https://release.geneontology.org/<YYYY-MM-DD>/ontology/go.json` (equivalently the versioned PURL
   `http://purl.obolibrary.org/obo/go/releases/<YYYY-MM-DD>/go.json`). `fetch.py` must **reject** the
   mutable `purl.obolibrary.org/obo/go.json`, `current/`, and `snapshot/` URLs and require a dated path,
   with the lockfile `sha256` as the integrity backstop.

## Current-code alignment

- Reuse, do not re-add: `REFERENCE_GRAPH_FORMATS` already includes `obograph_json`; the
  `extension-bio-reference_graph-1.0.json` enum already lists it; `parse_node_index_rows` /
  `parse_edge_rows` already enforce the node/edge column contract; `status` is constrained to
  `{active, deprecated, withdrawn}`; `member_kind` is free-string non-blank.
- The MONDO recipe is the template. `build.py`'s `curie_or_iri`, `load_obograph` (single-graph
  enforcement), `_replacement_values` (via `IAO:0100001`), `_xref_values`, the duplicate-key rejection,
  the blank-active-label hard error + deprecated-label fallback, the keep-edge-if-either-endpoint rule,
  the deterministic sort, `write_tables`, `verify_entity`, and `main` all carry over with GO renames.
- `dataset:gene-crosswalk-hgnc` / C2 are irrelevant here — a reference graph resolves no gene identifiers;
  GO members are `GO:` CURIEs in `member_kind`-typed node rows.
- Built data lives outside the repos under `${OUTPUT_ROOT}/go/` (i.e. `~/d/science-commons-data/go/`),
  exactly like MONDO; only the hash-recording `datapackage.yaml`, `entity.md`, and `recipe/` are committed.

## File Map

- Create: `~/d/science-commons/datasets/go/recipe/fetch.py` — pin + download go.json, maintain `lockfile.yaml`.
- Create: `~/d/science-commons/datasets/go/recipe/build.py` — project go.json into nodes/edges/build-summary CSVs.
- Create: `~/d/science-commons/datasets/go/recipe/build_datapackage.py` — render `datapackage.yaml` with hashes + bytes.
- Create: `~/d/science-commons/datasets/go/recipe/test_go_recipe.py` — hermetic pure tests.
- Create: `~/d/science-commons/datasets/go/recipe/lockfile.yaml` — pinned release/url/sha256/bytes (written by fetch).
- Create: `~/d/science-commons/datasets/go/recipe/README.md` — operator rebuild instructions.
- Create: `~/d/science-commons/datasets/go/datapackage.yaml` — graph (`_src/go.json`) + nodes + edges + build_summary resources.
- Create: `~/d/science-commons/datasets/go/entity.md` — `dataset:go` reference-graph record.
- Modify: `docs/plans/2026-05-31-bio-reference-graph-design.md` — mark the GO recipe implemented.
- Modify: `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md` — add `dataset:go` to the reference-graph status.

---

## Task 1: Preflight — Pin The GO Release And Ground The Numbers

**Files:**
- Create (draft): `~/d/science-commons/datasets/go/recipe/lockfile.yaml`

This task pins the exact release and discovers the real counts that later tasks assert. It mirrors the
real-data preflight that grounded the MONDO plan. **Task 1 must run to completion before Task 2** — its
measured numbers (including whether deprecated terms and namespace-less classes exist at all) are what the
recipe tests and `entity.md` assert. Do not pre-assume any count.

- [ ] **Step 1: Determine the latest dated release**

`https://release.geneontology.org/` is a **client-side S3 browser** — grepping its HTML only returns the
example date `2005-04-01`, not the real listing. Query the S3 bucket listing (ListObjects) directly, which
exposes the dated folders as `CommonPrefixes`:

```bash
# The archive is S3-backed; list the top-level dated folders via the bucket ListObjects endpoint.
curl -sSL --max-time 60 "https://release.geneontology.org/?delimiter=/&prefix=" \
  | grep -oE '20[0-9]{2}-[0-9]{2}-[0-9]{2}' | sort -u | tail -5
```

Pick the most recent fully-published date `<REL>` (at the time of writing the latest folder was around
`2026-05-19`; confirm the actual latest). The canonical asset is
`https://release.geneontology.org/<REL>/ontology/go.json`. The downloaded file's own
`graphs[0].meta.version` (Step 3) is the authoritative confirmation that `<REL>` is what you pinned.

- [ ] **Step 2: Download and hash the pinned asset**

```bash
mkdir -p ~/d/science-commons-data/go/_src
curl -sSL --max-time 600 "https://release.geneontology.org/<REL>/ontology/go.json" \
  -o ~/d/science-commons-data/go/_src/go.json
cd ~/d/science
rtk uv run --frozen --project science python -c "from pathlib import Path; from science_tool.commons.datapackage import stream_sha256_and_bytes; h,b=stream_sha256_and_bytes(Path.home()/'d/science-commons-data/go/_src/go.json'); print(h); print(b)"
```

- [ ] **Step 3: Verify shape and record sentinel counts**

This preflight must use the **same** GO-membership predicate as `build.py` — `curie_or_iri(id)` then
`startswith("GO:")` — not a `"/GO_"` substring test (which over/under-matches relative to the build and
would make the Task 3 sentinel gate spuriously fail). It must also compute the **projected** edge count the
way `build_go_tables` will (xref edges + graph edges kept iff either endpoint is a GO member), not raw
`len(graph["edges"])`.

```bash
cd ~/d/science
rtk uv run --frozen --project science python - <<'PY'
import json, collections, re
from pathlib import Path
_OBO = re.compile(r"^http://purl\.obolibrary\.org/obo/([A-Za-z][A-Za-z0-9]*)_(.+)$")
def curie_or_iri(v):
    t = str(v or "").strip(); m = _OBO.fullmatch(t)
    return f"{m.group(1)}:{m.group(2)}" if m else t
raw = json.loads((Path.home()/'d/science-commons-data/go/_src/go.json').read_text())
graphs = raw["graphs"]
print("graph_count:", len(graphs))            # MUST be 1 (load_obograph enforces this)
g = graphs[0]
print("meta.version:", g.get("meta", {}).get("version"))   # MUST contain <REL>
NS = "http://www.geneontology.org/formats/oboInOwl#hasOBONamespace"
go_class = obsolete = blank_active = dup = nofs = xref_edges = 0
seen = set(); nsc = collections.Counter()
for n in g["nodes"]:
    key = curie_or_iri(n.get("id"))
    if not key.startswith("GO:"): continue
    if n.get("type") != "CLASS": continue
    go_class += 1
    if key in seen: dup += 1
    seen.add(key)
    meta = n.get("meta") or {}
    dep = meta.get("deprecated") is True
    if dep: obsolete += 1
    lbl = (n.get("lbl") or "").strip()
    if not lbl and not dep: blank_active += 1
    found = next((b.get("val") for b in (meta.get("basicPropertyValues") or []) if b.get("pred") == NS), None)
    if found in ("biological_process","molecular_function","cellular_component"): nsc[found]+=1
    else: nofs += 1
    xref_edges += sum(1 for x in (meta.get("xrefs") or []) if str(x.get("val") or "").strip())
preds = collections.Counter()
kept = 0
for e in g["edges"]:
    s = curie_or_iri(e.get("sub") or e.get("subj")); o = curie_or_iri(e.get("obj"))
    if s in seen or o in seen:
        kept += 1; preds[curie_or_iri(e.get("pred"))]+=1
print("go_class_nodes (== member_count):", go_class)
print("duplicate_go_ids:", dup)
print("obsolete_go_classes:", obsolete)
print("blank_label_active:", blank_active)   # MUST be 0; if >0 the build hard-errors — investigate
print("namespace_counts:", dict(nsc))
print("namespace_fallback (GO class, no/odd namespace):", nofs)
print("projected_edge_count (== edge_count):", kept + xref_edges, "(graph", kept, "+ xref", xref_edges, ")")
print("distinct edge predicates (kept):", dict(preds))
PY
```

Record these numbers; they become the expected `entity.md` (`member_count` = `go_class_nodes`,
`edge_count` = `projected_edge_count`) and `build-summary.yaml` values (`status_counts`,
`namespace_counts`, `namespace_fallback_count`). **Use the distinct-predicate set to fix Task 2's fixture
predicate encodings.** **Hard gates:** `graph_count == 1`; `meta.version` contains `<REL>`;
`duplicate_go_ids == 0`; `blank_label_active == 0`.

- [ ] **Step 4: Seed the lockfile**

Write `recipe/lockfile.yaml` with `go_release: "<REL>"`, the asset `url`, `sha256:`, and `bytes`. (Task 4's
`fetch.py` is the source of truth that regenerates it; this seed lets Tasks 2-3 proceed offline.)

## Task 2: Write Recipe Unit Tests (TDD red)

**Files:**
- Create: `~/d/science-commons/datasets/go/recipe/test_go_recipe.py`

- [ ] **Step 1: Author hermetic tests over a fixture obograph**

Import from the recipe (mirroring `test_mondo_recipe.py`):

```python
from build import OBO_REPLACED_BY, build_go_tables, curie_or_iri, load_obograph
```

Build a tiny in-memory single-graph fixture exercising every branch. **Encode `pred` values exactly as
Task 1's distinct-predicate output showed GO emits them** (e.g. `is_a` as the bare label; `part_of` as
whatever Task 1 reported — the `BFO_0000050` PURL or the bare `"part_of"`). Cover:

- a BP term (`GO:0008150`) with an `is_a` edge, a `part_of` edge (encoded per Task 1), and an xref;
- an MF term (`GO:0003674`) and a CC term (`GO:0005575`);
- a `regulates`-style edge between two GO terms (predicate encoded per Task 1);
- an edge whose object is a non-GO class (`CL:0000000`) but whose subject is GO (must be **kept**);
- an edge with neither endpoint GO (must be **dropped**);
- **only if Task 1 found `obsolete_go_classes > 0`**: a deprecated GO class with a blank label (→ status
  `deprecated`, label falls back to the key, `label_fallback_count` incremented) and a `replaced_by` via
  `IAO:0100001`. (The fixture should still exercise this code path even if the live data has none, so the
  branch is covered — but do not assert a nonzero count in `entity.md`/summary unless Task 1 confirmed it.)
- a GO `CLASS` node with no `hasOBONamespace` (→ `member_kind: "term"`, `namespace_fallback_count += 1`).

Assert:

- only `GO:`-prefixed `CLASS` nodes become members; non-GO classes never become members;
- `member_kind` equals the term's BP/MF/CC namespace, or `"term"` on namespace fallback;
- a blank label on an **active** term raises `ValueError("...: blank label")`; on a **deprecated** term it
  falls back to the member key and increments `label_fallback_count`;
- a duplicate `GO:` id raises `ValueError`;
- xref values become `predicate="xref"` edges; `IAO:0100001` populates `replaced_by`;
- edges are kept iff either endpoint is a GO member; dropped otherwise;
- `summary` carries `member_count`, `edge_count`, `status_counts`, `namespace_counts`,
  `namespace_fallback_count`, `label_fallback_count`, `skipped_non_class_go_count`;
- nodes are sorted by `member_key`; edges by `(subject, predicate, object)`.

- [ ] **Step 2: Confirm red**

```bash
cd ~/d/science-commons/datasets/go/recipe
rtk uv run --frozen --project ~/d/science/science pytest test_go_recipe.py -q
```

Expected: FAIL (no `build.py` yet).

## Task 3: Implement `build.py` (TDD green)

**Files:**
- Create: `~/d/science-commons/datasets/go/recipe/build.py`

- [ ] **Step 1: Clone the MONDO build with GO deltas**

Start from `~/d/science-commons/datasets/mondo/recipe/build.py` and change exactly these things:

- `_is_mondo_curie` → `_is_go_curie` (`value.startswith("GO:")`); rename `MondoTables` → `GoTables`,
  `build_mondo_tables` → `build_go_tables`, the `mondo_keys` set → `go_keys`.
- Add the namespace constant and reader:

```python
OBO_NAMESPACE = "http://www.geneontology.org/formats/oboInOwl#hasOBONamespace"
_GO_NAMESPACES = frozenset({"biological_process", "molecular_function", "cellular_component"})

def _namespace(meta: dict[str, Any]) -> str:
    for entry in meta.get("basicPropertyValues", []) or []:
        if isinstance(entry, dict) and entry.get("pred") == OBO_NAMESPACE:
            val = str(entry.get("val") or "").strip()
            if val in _GO_NAMESPACES:
                return val
    return ""
```

- In the node loop, after computing `status`/`label`, set `member_kind` from `_namespace(meta)`; if blank,
  use `"term"` and `namespace_fallback_count += 1`; tally `namespace_counts[member_kind] += 1` for the
  three real namespaces.
- Keep the predicate handling, xref edges, replaced-by, keep-edge rule, and sort **identical** to MONDO.
- Extend `summary` with `namespace_counts` and `namespace_fallback_count`; rename
  `skipped_non_class_mondo_count` → `skipped_non_class_go_count`.
- `main()`: default `output_dir = resolve_commons_data_root() / "go"`, default
  `source_json = output_dir / "_src" / "go.json"`; print `wrote {member_count} GO nodes and {edge_count}
  edges to {output_dir}`. Keep the optional `--verify-entity` guard.

- [ ] **Step 2: Confirm green**

```bash
cd ~/d/science-commons/datasets/go/recipe
rtk uv run --frozen --project ~/d/science/science pytest test_go_recipe.py -q
```

Expected: PASS.

- [ ] **Step 3: Real build + sentinel match**

```bash
cd ~/d/science
rtk uv run --frozen --project science python ~/d/science-commons/datasets/go/recipe/build.py
```

Expected: `member_count`, `edge_count`, `status_counts`, and `namespace_counts` in
`~/d/science-commons-data/go/build-summary.yaml` match the Task 1 preflight numbers exactly.

## Task 4: Implement Fetch And Datapackage Rendering

**Files:**
- Create: `~/d/science-commons/datasets/go/recipe/fetch.py`
- Create: `~/d/science-commons/datasets/go/recipe/build_datapackage.py`
- Create: `~/d/science-commons/datasets/go/recipe/README.md`

- [ ] **Step 1: `fetch.py`** (model on MONDO's, adapt the pin guard)

- Pin `go_release`, the `https://release.geneontology.org/<REL>/ontology/go.json` url, `sha256`, `bytes`
  in a `LOCK` dict; auto-write `lockfile.yaml`.
- `_reject_mutable_url`: require `scheme == "https"` and host `release.geneontology.org` (or
  `purl.obolibrary.org` with a `/obo/go/releases/<date>/` path); **reject** any url containing
  `/obo/go.json` without a release segment, `current/`, `snapshot/`, or `/latest/`. The dated path is
  mandatory; the lockfile sha256 is the integrity backstop.
- Atomic download to `${OUTPUT_ROOT}/go/_src/go.json`; verify sha256 + bytes against the lock; fail-early on
  mismatch.
- After download, verify the parsed `graphs[0].meta.version` contains `<REL>` (cross-check beyond the hash).

- [ ] **Step 2: `build_datapackage.py`** (model on MONDO's)

Render `datapackage.yaml` with a top-level `name: go` and four resources, each carrying `format`,
`mediatype`, a `source: {type: local, ref: ${OUTPUT_ROOT}/go/<file>}`, and computed `hash` + `bytes` via
`stream_sha256_and_bytes` — exactly MONDO's `datapackage.yaml` shape:

```yaml
name: go
resources:
  - name: graph         # path: _src/go.json       format json   mediatype application/json
  - name: nodes         # path: nodes.csv          format csv    mediatype text/csv
  - name: edges         # path: edges.csv          format csv    mediatype text/csv
  - name: build_summary # path: build-summary.yaml format yaml   mediatype application/yaml
```

The `graph` resource path is `_src/go.json` and its `hash` MUST equal the pinned `go.json` sha256 from the
lockfile. (The MONDO `build_datapackage.py` already derives `format`/`mediatype` from the extension and
emits the `${OUTPUT_ROOT}/<slug>/...` source ref — keep that logic, change the slug to `go`.)

- [ ] **Step 3: `README.md`**

Show the operator rebuild flow and state that `purl.obolibrary.org/obo/go.json`, `current/`, and
`snapshot/` are discovery-only and must never be pinned:

```bash
cd ~/d/science
rtk uv run --frozen --project science python ~/d/science-commons/datasets/go/recipe/fetch.py
rtk uv run --frozen --project science python ~/d/science-commons/datasets/go/recipe/build.py
rtk uv run --frozen --project science python ~/d/science-commons/datasets/go/recipe/build_datapackage.py
```

## Task 5: Create The `dataset:go` Entity And Datapackage

**Files:**
- Create: `~/d/science-commons/datasets/go/datapackage.yaml` (rendered in Task 4; confirm committed shape)
- Create: `~/d/science-commons/datasets/go/entity.md`

- [ ] **Step 1: Write `entity.md`** (copy `datasets/mondo/entity.md`'s field set exactly, then adapt)

`version: "1.0.0"` is required by `science-entity-base-1.0.json` and `member_key_space` is required by
`extension-bio-reference_graph-1.0.json` — both are present in the shipped MONDO record and **must** be
carried, or `commons validate` fails. Mirror MONDO's full frontmatter:

```yaml
---
schema_profile: science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0
id: dataset:go
type: dataset
title: Gene Ontology term reference graph
version: "1.0.0"
created: "2026-06-01"
updated: "2026-06-01"
tags: []
access:
  level: public
  availability: available
  verified: true
  verification_method: retrieved
datapackage: datapackage.yaml
graph_resource: graph
graph_format: obograph_json
member_key_space:
  kind: curie
  prefixes: [GO]
  resolution_status: resolved
node_index_resource: nodes
edge_resource: edges
member_count: <from build-summary.yaml>
edge_count: <from build-summary.yaml>
license: CC-BY-4.0
origin: external
source_class: reference
status: active
tier: use-now
---
```

Body: GO is a curated reference term graph; members are `GO:` CURIEs typed by sub-ontology in
`member_kind` (BP/MF/CC, with `term` fallback); graph edges (`is_a`/`part_of`/`regulates`, predicates as
emitted by GO) plus node xrefs as `predicate=xref` live in the edge projection; the canonical artifact is
the pinned upstream `go.json`. Mirror the MONDO body's framing of member/edge/deprecation semantics.

- [ ] **Step 2: Configure the per-machine data override**

Add a `go` entry to `~/.config/science/data.yaml` pointing at `~/d/science-commons-data/go` (preserve
existing keys; do not clobber `mondo`/`reactome`/etc.).

- [ ] **Step 3: Validate the dataset**

```bash
cd ~/d/science
rtk uv run --frozen --project science science commons validate --slug go
```

Expected: clean (no reference-graph or datapackage defects).

## Task 6: Verify Real RG1 Parse + RG2 Payload Over GO

- [ ] **Step 1: Resolve + parse the real node/edge resources through the real resolver**

Use the same reader the RG machinery uses (`read_commons_node_rows`/`read_commons_edge_rows`), which
resolves via the data root / per-machine override and hash-verifies — do **not** hand-join
`resolve_commons_data_root()/"go"` (that bypasses the override set in Task 5). Confirm the resolve CLI also
works (it accepts the resource filename, matching the `dataset:reactome sets.csv` precedent):

```bash
cd ~/d/science
rtk uv run --frozen --project science science commons data resolve dataset:go nodes.csv
rtk uv run --frozen --project science science commons data resolve dataset:go edges.csv
rtk uv run --frozen --project science python - <<'PY'
from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.reference_graph import parse_node_index_rows, parse_edge_rows
from science_tool.commons.reference_graph_resources import read_commons_node_rows, read_commons_edge_rows
rec = CommonsEntityAdapter(resolve_commons_root()).load("dataset:go")
nodes = parse_node_index_rows(read_commons_node_rows(rec.frontmatter))
edges = parse_edge_rows(read_commons_edge_rows(rec.frontmatter))
kinds = {n.member_kind for n in nodes}
print("validated", len(nodes), "GO nodes and", len(edges), "edges")
print("member_kinds:", sorted(kinds))
assert {"biological_process","molecular_function","cellular_component"} & kinds
PY
```

Expected: parse succeeds; member_kinds include the three GO namespaces.

- [ ] **Step 2: RG2 payload smoke for one GO term**

`resolve_virtual_member_payload()` first loads a *promoted* `bio.reference_graph.member` entity and follows
`derivation.kind: member_of` — this plan creates no such promoted member, so call the lower-level
`resolve_reference_graph_member_payload(parent=rec, member_of=MemberOf(...))` directly with a `MemberOf`
constructed for a known BP term present in the build (e.g. `GO:0008150`). Confirm it returns the node row
(with the GO `member_kind` intact) plus its directly incident edges. This is an ad-hoc verification script,
not a committed test — the generic resolver is namespace-agnostic and already covered by
`test_commons_reference_graph_payload.py`.

```python
from science_tool.commons.member import MemberOf
from science_tool.commons.reference_graph_payload import resolve_reference_graph_member_payload
# rec from Step 1; construct MemberOf for a known BP term (check MemberOf's exact fields)
payload = resolve_reference_graph_member_payload(parent=rec, member_of=MemberOf(member_key="GO:0008150", parent="dataset:go"))
print(payload.node.member_kind, len(payload.incident_edges))
```

## Task 7: Update Status Docs

**Files:**
- Modify: `docs/plans/2026-05-31-bio-reference-graph-design.md`
- Modify: `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`

- [ ] **Step 1: Reference-graph design doc**

Update the **line-5 status header** and the **roadmap/scope prose** that currently lists GO as follow-on
work (the "real GO/MONDO/Open Targets recipes are follow-on work" line near line 36, the "Do not build full
GO..." line near line 41, and the "additional real graph recipes such as GO and Open Targets" line near
line 434): remove GO from the pending set, recording that `dataset:go` is implemented as the second real
reference-graph commons dataset. **Do not** edit the §8 stress-test/fit table (the GO row there describes
fit, not implementation status, and has no status column). Do not over-claim RG3/RG5 or Open Targets (all
still pending).

- [ ] **Step 2: Umbrella doc**

In the §8 reference-graph prose and the header status line, add `dataset:go` alongside `dataset:mondo` as
an implemented `bio.reference_graph` recipe; keep "GO/Open Targets recipes pending" accurate by removing GO
from the pending list (Open Targets remains pending).

## Task 8: Final Verification

**This is a two-repo change:** the GO dataset (recipe + entity + datapackage) lands in `~/d/science-commons`,
while the Task 7 status-doc edits land in `~/d/science`. Verify and commit both.

```bash
cd ~/d/science-commons/datasets/go/recipe
rtk uv run --frozen --project ~/d/science/science pytest test_go_recipe.py -q

cd ~/d/science
rtk uv run --frozen --project science science commons validate --slug go
rtk uv run --frozen --project science pytest science/tests/test_commons_reference_graph.py science/tests/test_commons_reference_graph_payload.py science/tests/validate/test_checks_reference_graphs.py -q
rtk uv run --frozen --project science ruff check ~/d/science-commons/datasets/go/recipe

# commons repo: the dataset additions
cd ~/d/science-commons && rtk git status --short && rtk git diff --check
# science repo: the Task 7 doc edits
cd ~/d/science && rtk git status --short && rtk git diff --check
```

Expected:

- recipe tests pass; `commons validate --slug go` clean;
- existing reference-graph regression tests still pass (GO did not regress MONDO/RG machinery);
- ruff clean on the new recipe; no whitespace defects in either repo;
- `science-commons` shows only the intentional `datasets/go/` additions; `~/d/science` shows only the
  Task 7 doc edits.

Then commit each repo on its own feature branch and finish via superpowers:finishing-a-development-branch
(the user decides merge/push per repo, as with MONDO). Remember `~/d/science` is the default branch — branch
before committing there.

## Self-Review Notes

- **Reuses, does not fork:** no science-repo schema/format/parsing changes; `obograph_json` + the
  `reference_graph` machinery shipped with MONDO are exercised, not modified. This is the second
  instantiation the reference-graph design called for.
- **GO-specific risk surfaced:** the only build divergence from MONDO is the namespace→`member_kind`
  mapping and its fallback, both covered by Task 2 tests and a Task 1 hard gate
  (`blank_label_active == 0`, `graph_count == 1`, `meta.version` matches the pin).
- **Pin integrity:** dated-archive-only fetch guard + sha256/bytes lock + `meta.version` cross-check; the
  mutable `go.json`/`current`/`snapshot` URLs are explicitly rejected.
- **Deferred:** GO annotation (GAF gene→term) ingestion is *not* in scope — that is gene-set/association
  territory, not the term graph (this is exactly the "GO may tempt conflation with gene sets" caution from
  the reference-graph design §rationale). RG3 unpromoted-member B materialization, RG5 non-molecular
  identity resolvers, and Open Targets remain pending.
- **Built-data placement:** all bulk artifacts live under `~/d/science-commons-data/go/`; only metadata +
  recipe are committed, matching MONDO.
