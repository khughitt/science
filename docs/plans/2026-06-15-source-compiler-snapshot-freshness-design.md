# Source Compiler Slice B — `SourceSnapshot` & Freshness-Origin Records

**Status:** approved design (2026-06-15)
**Spec:** patchwork kernel Spec 3 (Source Compiler & Identity Substrate), Slice B
**Architecture:** `~/d/science/docs/plans/2026-06-14-patchwork-kernel-architecture-design.md`
**Predecessor:** Slice A (Adapter Policy keystone) — `~/d/science/docs/plans/2026-06-15-source-compiler-adapter-policy-keystone-design.md`

## 1. Goal

One sentence: introduce a typed, persisted `SourceSnapshot` primitive that pins
each local source's observed content identity, so the compiler can detect when a
source's content actually changed and emit a typed `SourceChange` freshness-origin
record that drives the existing `bears_on` / freshness machinery — **content-derived,
not date-derived**.

This closes the gap where editing a source file's content without bumping its
`updated:` frontmatter leaves dependents looking fresh.

## 2. Background: what exists today

- **`graph/freshness.py::derive_freshness`** computes epistemic freshness, but it is
  **date-driven**: for each epistemic entity it compares a baseline
  (`last_reviewed or created`) against each upstream `bears_on` source's
  `updated or created`. A content change with no date bump is invisible to it.
  There is also no story for remote sources (no local mtime).
- **`graph/io.py::build_input_manifest` / `read_revision_manifest`** already compute a
  per-file `{sha256, mtime_ns}` manifest stored as one JSON blob in the provenance
  graph under `REVISION_URI`. This is a **whole-build rebuild cache** keyed by relative
  path: untyped, not tied to entities, and not connected to freshness. `science validate`
  consumes it via `store/validation.py::diff_graph_inputs` (baseline = prior graph's
  manifest, current = filesystem) — the exact prior-dataset-as-baseline pattern Slice B
  reuses.
- **`graph/freshness.py::_emit_bears_on_edge`** emits a reified `sci:BearsOnEdge`
  (source, target, depth) alongside each `sci:bearsOn` triple, content-addressed by
  `sha256(source\x00target\x00depth)`. Every existing direct-edge deriver calls it; depth
  and neighbor consumers (Phase 2 sampling, attention) read these reified nodes.

`SourceSnapshot` is the architecture's net-new primitive (kernel primitive table) and is
explicitly **provenance/compiler state, not a truth-apt entity** — it does not carry
belief. The architecture assigns the Source Compiler ownership of "the freshness-origin
record type emitted when a `SourceSnapshot` changes," consumed by Provenance/Review and
Epistemic Semantics.

## 3. Scope

### In scope (keystone)

- Typed `SourceSnapshot` (content sha256) for **loaded markdown-backed entity files**.
- Typed `SourceChange` freshness-origin record, emitted only on a content-hash change.
- In-graph persistence of snapshots (provenance graph), diffed across builds against the
  prior `graph.trig`.
- `SourceSnapshot` participates in the `bears_on` dependency layer (with a reified
  `sci:BearsOnEdge`, like every other direct-edge deriver).
- One new input to `derive_freshness` so a snapshot change newer than an entity's baseline
  marks it `needs-review`, with the cause distinguishable from date-driven staleness.

### Out of scope (deferred fill-out)

- Remote / DOI / Zenodo / API / dataset-manifest observations and richer revision
  coordinates (git revision, version strings). Snapshot is local-file-content only here.
- Aggregate (`entities.yaml`) / datapackage / structured-source snapshots. Only
  markdown-backed entity files are snapshotted in the keystone.
- `io.py` revision-manifest unification. The revision manifest stays a separate whole-build
  cache; Slice B does not absorb or replace it.
- **Change history.** Slice B persists only the *current/latest* `SourceChange` cause per
  source, not a log of past changes (see §6.4).
- Semantic-content hash normalization (whitespace-insensitive diffs). Keystone hashes raw
  file bytes (§6.2).

## 4. Load-bearing decisions (locked during brainstorming)

1. **Keystone scope** = local-file snapshot → freshness origin. Remote sources, io.py
   unification, and richer coordinates are fill-out.
2. **Typed freshness-origin record**, not an effective-date injection. A content-hash change
   is a distinct fact from `updated:` changing; collapsing it into a synthetic entity date
   would weaken the primitive and force every later remote-source story to reverse-engineer
   "why did this go stale?". The engine change is **narrow**: one new input to
   `derive_freshness`, not a rewrite. Date-driven and source-change triggers must remain
   distinguishable in output triples.
3. **`sci:triggeredBy` stays homogeneous** — it always points to an upstream *dependency
   node*. `SourceSnapshot` becomes that durable dependency node for content-driven
   staleness; `SourceChange` is the *event* explaining why the snapshot is currently
   considered changed, linked from the snapshot via `sci:latestSourceChange` (event-specific
   name, not a generic `lastChange`). Events never enter the dependency topology.
4. **In-graph provenance persistence.** Baseline snapshots are read from the prior
   `graph.trig`; current snapshots are persisted back into `graph.trig`. No JSON sidecar
   (would be a second source of truth for what the graph should own); no premature reuse of
   the path-keyed revision manifest (a different primitive).
5. **Churn guardrail.** A snapshot's `observed_on` is the first-observation time of the
   *current* hash and must not move on unchanged rebuilds. Carry the prior snapshot's hash
   and latest change forward verbatim when the hash is unchanged; mint a new `SourceChange`
   only when the observed identity actually changes. Unchanged rebuild → byte-identical
   snapshot + change triples.

## 5. New primitives (`graph/source_records.py`)

`source_records.py` is the leaf module Slice A created (stdlib + pydantic only, no
`science_tool` imports) precisely as the home for these.

```python
@dataclass(frozen=True, slots=True)
class SourceChange:
    """A freshness-origin event: the observed content identity of a source changed."""
    sha256: str
    observed_on: date


class SourceSnapshot(BaseModel):
    """A pinned observation of a local source's content identity.

    Durable: carried forward verbatim across builds when the content is unchanged.
    `latest_change` is None until the first time a change is observed against an
    established baseline (the first-ever observation establishes the baseline and is
    not itself a change).
    """
    source_path: str          # relative, posix
    sha256: str               # sha256 of raw file bytes
    latest_change: SourceChange | None = None
```

`SourceChange` is frozen (an immutable event); `SourceSnapshot` is a pydantic model
mirroring `MarkdownSourceDocument`'s style. Both are leaf-pure so adapters and the future
remote fill-out can return them without an import cycle.

## 6. Graph contract

### 6.1 Vocabulary (new in `SCI_NS`)

```
SS  a sci:SourceSnapshot ; sci:sourcePath "<rel/posix>" ; schema:sha256 "<hash>" .
SS  sci:latestSourceChange  C .                 # only after a change has been observed
C   a sci:SourceChange ; schema:sha256 "<hash>" ; sci:observedOn "<date>"^^xsd:date .
SS  sci:bearsOn  <entity> .                      # snapshot is a first-class dependency node
```

- **`SS` IRI** = `PROJECT_NS["source-snapshot/<path-slug>"]`, stable per source path.
- **`C` IRI** = `PROJECT_NS["source-change/" + sha256(path + "\x00" + new_hash)[:16]]`,
  stable per `(path, new-hash)` so carry-forward across unchanged builds is byte-identical.
- Snapshot/change triples (`SS` type/`sourcePath`/`sha256`/`latestSourceChange`, `C`
  type/`sha256`/`observedOn`) live in **`graph/provenance`** — no new named-graph layer is
  introduced in the keystone.
- The `SS sci:bearsOn entity` triple lives in **`graph/knowledge`** where `bears_on`
  already lives, and is accompanied by a reified `sci:BearsOnEdge` at **depth 1** via the
  existing `freshness.py::_emit_bears_on_edge` helper, so snapshot edges honor the same
  direct-edge contract as every other deriver (depth/neighbor consumers stay consistent).

### 6.2 Content hash

Hash is over **raw file bytes** via the existing `io.py::_sha256_file` helper (promoted to
a reusable import if needed). A whitespace-only edit therefore flags review — conservative
and deterministic, matching the revision manifest. Semantic normalization is a deferred
fill-out, not part of the keystone.

### 6.3 Which sources are snapshotted

Only **loaded markdown-backed entity files** — i.e. a markdown source document that
produced a successfully-loaded entity (there is an entity target for `SS sci:bearsOn
entity`). Skipped / missing-identity / non-entity markdown documents get **no** snapshot
node in this slice, because there is nothing for the snapshot to bear on. Aggregate and
datapackage sources are deferred.

### 6.4 Current cause only, no history

Slice B persists only the **current/latest** `SourceChange` per source. With `C` keyed by
`(path, new-hash)`, carrying the latest event forward is deterministic and byte-stable. If
full change history is ever retained later, the event identity scheme must be revisited
(a `(path, new-hash)` key collapses repeat transitions through the same hash).

## 7. Build pipeline

A new layer `_derive_source_snapshot_layer` runs in `materialize.py` **before**
`_derive_bears_on_layer` (so `SS bears_on entity` edges exist before `close_bears_on`) and
before `_derive_freshness_layer`.

1. **Baseline.** If a prior `graph.trig` exists, load it and read `SourceSnapshot` nodes
   from its provenance graph into `{source_path: (sha256, latest_change)}`. A missing prior
   graph, or a pre-Slice-B graph with no snapshot nodes, yields an empty baseline (not an
   error). This reuses the prior-dataset-as-baseline pattern of `diff_graph_inputs`.
2. **Observe.** Content-hash each loaded markdown-backed entity file.
3. **Diff + carry-forward** (the churn guardrail):
   - no prior entry for this path → establish baseline; **emit no `SourceChange`**;
   - `hash == prior.sha256` → carry `prior.sha256` and `prior.latest_change` forward
     **verbatim** (no new event, no timestamp movement);
   - `hash != prior.sha256` → mint `SourceChange{sha256=hash, observed_on=today}` and set
     it as `latest_change`.
4. **Emit.** Write `SourceSnapshot` + `SourceChange` triples to the provenance graph; write
   `SS sci:bearsOn entity` + the reified `BearsOnEdge` (depth 1) to the knowledge graph.
5. `derive_bears_on_*` + `close_bears_on` then propagate snapshot changes to dependents
   exactly as for any other `bears_on` source.

`today` (the build date) is threaded in the same way `_derive_freshness_layer` already
receives `today=_date.today()`; the snapshot baseline is a sibling temporal input to it.
The freshness layer is already the time-variant layer, so reading prior state here does not
introduce a new class of impurity.

## 8. `derive_freshness` extension (narrow)

Add one parameter:

```python
def derive_freshness(
    dataset, *, entities, today,
    source_changes: dict[str, date],   # snapshot-node URI -> latest_change.observed_on
) -> None:
```

In the existing inverse-`bears_on` walk over `bears_on_in[entity]`, an upstream node that is
a `SourceSnapshot` (present in `source_changes`) contributes `change_at =
source_changes[snapshot_uri]`; entities continue to contribute `updated or created`. The
existing precedence is unchanged: `change_at > baseline` → `needs-review`, with
`triggeredBy → SS` and `upstreamChangeAt = observed_on`.

**Cause distinguishability** comes for free from the topology, no overloaded date:

- `triggeredBy` target is typed `sci:SourceSnapshot` (vs. a project entity for date-driven
  triggers), and
- `SS sci:latestSourceChange C` exposes the exact `schema:sha256` + `sci:observedOn`
  evidence.

A review surface can therefore say "needs review because upstream snapshot changed" and
expand to the precise hash/date.

## 9. Idempotency / determinism

`observed_on` never moves on an unchanged rebuild (carry-forward), and `C` IRIs are keyed
by `(path, new-hash)`, so the snapshot + change triples are **byte-identical build over
build** when no source content changed. The only pre-existing temporal variance — the
`today`-driven `stale` horizon in `derive_freshness` — is untouched. An idempotency test
pins "rebuild an unchanged project → identical snapshot + change triples."

## 10. Error handling (fail-early, explicit)

- Missing prior graph / pre-Slice-B graph with no snapshots → empty baseline. Not an error;
  all sources establish baseline and no events fire.
- A source file that cannot be read at hash time → **fail loud**. A vanished/unreadable
  backing file for a loaded entity is a real inconsistency, not something to silently skip.

## 11. Testing (TDD)

1. **`source_records.py` types** — `SourceSnapshot` / `SourceChange` shape and round-trip;
   `source_records` still imports nothing from `science_tool` (extends Slice A's leaf
   guard).
2. **Snapshot derivation** — first build establishes baseline with no `SourceChange`; a
   changed hash mints exactly one `SourceChange` with `observed_on=today`; unchanged rebuild
   is byte-identical (idempotency / churn guardrail).
3. **bears_on contract** — `SS sci:bearsOn entity` is accompanied by a depth-1
   `sci:BearsOnEdge`, matching the other direct-edge derivers.
4. **`derive_freshness` extension** — snapshot `observed_on > baseline` → `needs-review` +
   `triggeredBy → SS` (typed `sci:SourceSnapshot`) + `latestSourceChange` evidence reachable;
   `observed_on <= baseline` → no trigger; the date-driven path is unchanged.
5. **End-to-end (the target failure mode)** — edit a markdown file's body WITHOUT bumping
   `updated:`, rebuild → the backed entity (and its `bears_on` dependents) go `needs-review`
   via the snapshot origin, which today's date-driven engine misses.
6. **Characterization guard** — a project with no prior snapshots / no changed snapshots
   produces freshness output equal to a captured baseline (behavior-neutral where nothing
   changed; the new layer only adds state when a real content change is observed).

## 12. Files (anticipated)

- `science/src/science_tool/graph/source_records.py` — add `SourceSnapshot`, `SourceChange`.
- `science/src/science_tool/graph/source_snapshots.py` *(new)* — observe / diff /
  carry-forward / emit + prior-graph baseline reader. (Kept out of `materialize.py` to keep
  that file focused; mirrors the per-layer module split already in `graph/`.)
- `science/src/science_tool/graph/freshness.py` — `derive_freshness` gains `source_changes`;
  reuse `_emit_bears_on_edge` for snapshot edges.
- `science/src/science_tool/graph/materialize.py` — wire `_derive_source_snapshot_layer`
  before bears_on/freshness; build the `source_changes` map for `_derive_freshness_layer`.
- `science/src/science_tool/graph/store/constants.py` — new `SCI_NS` terms if interned there.
- `science/tests/graph/` — new tests per §11.

## 13. Deferred follow-ups (documented, not done)

- Remote/DOI/Zenodo/API/dataset-manifest `SourceSnapshot`s with revision coordinates.
- Aggregate / datapackage / structured-source snapshots.
- `io.py` revision-manifest unification (make the rebuild cache a view over snapshots, or
  vice-versa) under the "no parallel stores" invariant.
- Semantic-content hash normalization.
- Change *history* (a `SourceChange` log) — requires a new event-identity scheme.
