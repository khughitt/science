# B2 Dataset-Derived Independence Design

Date: 2026-05-29

Status: design drafted; implementation plan next

Related:
- `docs/plans/2026-05-26-bio-dataset-influence-provenance-design.md` — Pillar B north star and B2 boundary
- `docs/plans/2026-05-29-b-migration-paper-datasets-design.md` — single-system migration path for papers
- `docs/plans/2026-05-22-evidence-aggregation-and-belief-design.md` — independence collapse and `suspect-circular`
- `science/src/science_tool/graph/dataset_usage.py` — B1 materialized usage records
- `science/src/science_tool/graph/belief.py` — current aggregation reads committed independence fields
- `science/src/science_tool/validate/checks/evidence_lines.py` — current authored `suspect-circular` check
- `science/src/science_tool/graph/freshness.py` — existing `bears_on` closure derivation

---

## 1. Purpose And Scope

B1 made dataset use queryable. B2 interprets that graph truth so the system can detect when evidence
lines are not independent because they rest on the same upstream dataset.

B2 must be conservative. It should surface derived non-independence without silently changing belief
scores for ambiguous cases. The key split is:

- **committed dependence:** strong enough to affect aggregation because the shared dataset dependence is
  direct and full-overlap;
- **candidate dependence:** useful reviewer signal, but not enough to alter scoring.

`aggregate_belief` continues to read committed independence metadata only. Candidate signals feed
validation/reporting, especially `suspect-circular`, but do not collapse evidence units by themselves.

---

## 2. Inputs From B1 And Existing Graphs

B2 reads from the materialized graph, not raw frontmatter.

Primary input:

```text
consumer    sci:hasDatasetUsage  usage-node
usage-node  rdf:type             sci:DatasetUsage
usage-node  sci:dataset          dataset-uri
usage-node  sci:usageRole        role
usage-node  sci:usageOverlap     overlap
usage-node  sci:usageSource      source
```

Context input:

- evidence-line nodes and their `cito:supports` / `cito:disputes` edges;
- current authored independence metadata (`sci:evidenceIndependence`, `sci:independenceGroup`,
  `sci:sharedDataset`);
- `prov:wasDerivedFrom` and the existing `bears_on` closure that connects consumers to propositions;
- virtual gene-set member URIs from B1, where row-level usage is visible but may not yet connect to a
  proposition until D2 or an explicit evidence relation creates a path.

B2 should not parse papers, datasets, or gene-set CSV rows again. If a fact is not in the graph, it is
out of scope for B2.

---

## 3. Usage Reduction

B1 may emit multiple usage nodes for the same `(consumer, dataset)` pair. B2 first reduces those nodes to
one interpreted dependence record per pair.

### B2-D1 -- Role Interpretation

Roles are interpreted as:

| Role | Dependence interpretation |
|---|---|
| `analyzed` | dependence |
| `set_definition_source` | dependence |
| `training` | dependence |
| `upstream` | dependence |
| `validation_source` | independence-positive unless the same pair also has a dependence role |
| `cited` | informational only |

### B2-D2 -- Most-Dependent-Wins

When several usage records exist for the same `(consumer, dataset)` pair, B2 chooses the most dependent
interpretation:

1. Any dependence role beats `validation_source` and `cited`.
2. `validation_source` beats `cited` only as an independence-positive annotation.
3. Overlap rank is `full > partial > unknown` for dependence severity.
4. `source` is retained as a set of contributing sources, not used as the semantic winner.

For reduced dependence records, overlap is the maximum overlap rank among contributing
dependence-role records, not merely the overlap attached to a single winning source record. A
`validation_source` or `cited` record does not upgrade the overlap of a dependence interpretation.

This handles the realistic B1 case where a derived dataset has both an authored
`{role: analyzed, overlap: full}` entry and a `derivation.inputs` `{role: upstream, overlap: unknown}`
entry for the same upstream dataset. The graph facts are not contradictory; B2 reduces them to one
dependence interpretation before deriving independence signals.

---

## 4. Evidence-Line Dataset Ancestors

B2 needs to ask: for each evidence line, which dataset dependencies can reach it?

The derivation should walk from usage consumers to evidence lines/propositions through existing graph
relationships:

- if the evidence line itself has usage records, those datasets apply directly;
- if the evidence line `prov:wasDerivedFrom` a consumer with usage records, those datasets apply;
- if a consumer with usage records `bears_on` the evidence line's target proposition, the dataset is a
  candidate ancestor for that line only;
- virtual gene-set member consumers participate only when a graph path connects that virtual URI to the
  evidence line or its target.

The implementation should keep the first B2 pass narrow: derive candidate/committed component signals
among evidence lines that share a target. Global influence reporting can reuse the same ancestor index
later, but B2 acceptance is about independence and circularity, not a complete UI for influence
exploration.

Virtual gene-set member paths never commit in B2. They stay candidate-only until D2 promotion or another
explicit graph relation makes the individual set a normal evidence source with direct provenance.

---

## 5. Committed Versus Candidate Signals

### B2-D3 -- Committed Dependence

B2 may commit a collapse signal only when two evidence lines on the same target share a dataset ancestor
through a dependence role, the winning overlap is `full` on both sides, and the ancestry path is direct.

Direct ancestry means either:

- the evidence line itself has the relevant usage record, or
- the evidence line is directly `prov:wasDerivedFrom` a consumer with the relevant usage record.

`bears_on`-only ancestry is never enough to commit a collapse. `bears_on` is a broad closure for
influence queries; using it as a scoring input would over-commit ambiguous provenance. Shared datasets
found only through `bears_on` produce candidates with reason `indirect-bears-on`.

Committed output should align with existing aggregation inputs, but through one derived component per
target rather than one group per dataset:

- `independence = shared-source`;
- `independence_group = dataset-derived:<dataset-or-dataset-set-key>` stable group key;
- `shared_dataset = dataset:<slug>` when a component has one shared dataset, or a deterministic
  comma-separated/multi-value graph representation when several shared datasets justify the same
  component.

`shared_dataset` is explanatory observability metadata only. Scoring must key on
`independence_group`; `aggregate_belief` must not parse comma-joined or multi-value `shared_dataset`
payloads to decide collapse behavior.

The component rule is necessary because the current `EvidenceUnit` model has a single
`independence_group` field. If line A shares full-overlap dataset X with line B and full-overlap dataset Y
with line C, B2 forms one connected committed component `{A, B, C}` for that target. That component maps
to one derived group key, with both datasets retained as justification. B2 must not emit multiple
committed independence groups for one evidence line.

This is an equivalence-class collapse, and it is deliberately conservative. In the `{A, B, C}` example,
line A and line C may not pairwise share any dataset; they are collapsed because hub line B shares
different full-overlap datasets with each. That can under-credit independent evidence, but it does not
inflate support. A finer correlation model that can represent overlapping-but-not-transitive dependence
sets is deferred beyond B2.

The component key must not include stance. The existing reducer chooses winners by `(independence_group,
stance)` and separately marks a group contested when both support and dispute winners share the group. If
a support line and a dispute line share the same full-overlap dataset, they need the same derived group
key so the current contested-group behavior still works.

Derived group keys should be deterministic without churning on every component membership change:

- single-dataset committed components use `dataset-derived:<dataset-slug>` or an equivalent stable
  dataset-derived key;
- multi-dataset committed components use `dataset-derived:<hash(sorted-dataset-refs)>`;
- the component record URI may hash the full payload, including evidence-line members, but the
  `independence_group` value exposed to aggregation should not hash sorted evidence-line URIs.

Adding a new line to an existing single-dataset component therefore does not rename the group for
pre-existing lines. Adding a genuinely new shared dataset to a multi-dataset component may change the
dataset-set key; that reflects a changed dependence explanation rather than incidental membership churn.

The implementation may choose whether to materialize component metadata as graph-only derived metadata or
to expose it through the same `EvidenceUnit` fields read by `aggregate_belief`. It must not rewrite
source frontmatter.

Once committed metadata is visible to `aggregate_belief`, `CONFIG_VERSION` in
`science_tool.graph.belief_weights` must be bumped because belief snapshots can change.

### B2-D4 -- Candidate Dependence

All weaker shared-dataset cases are candidates:

- either side has `overlap: unknown`;
- either side has `overlap: partial`;
- the shared ancestry exists only through `bears_on` rather than direct line/source provenance;
- the path is through a virtual gene-set member that is not promoted or explicitly connected enough to
  prove direct dependence;
- the shared role is only `validation_source`;
- one side uses a dependence role and the other side uses `validation_source`;
- the shared fact is only `cited`.

Candidates must be queryable and reportable, but they do not affect `aggregate_belief`. They should
feed an expanded `suspect-circular` check so reviewers see likely double-counting before the model
commits to collapse. Near-term, migrated legacy `paper.datasets` refs have `overlap: unknown`, so they
can produce candidates but not committed collapse until authors enrich overlap explicitly.

Candidate records should include enough explanation for review:

- target proposition,
- evidence-line member set, with pairwise explanations derivable for display,
- shared dataset or datasets,
- reduced role/overlap per member line,
- whether the reason is unknown overlap, partial overlap, indirect `bears_on`, virtual row path,
  validation, mixed validation/dependence, or citation only.

---

## 6. Interaction With Authored Metadata

Authored independence fields remain valid. B2 adds derived signals; it does not remove the manual escape
hatch.

Derived commitment records must not create nondeterministic same-predicate collisions on evidence-line
nodes. The existing belief reader currently treats `sci:evidenceIndependence` and
`sci:independenceGroup` as single-valued fields; if a line has both authored and derived triples with the
same predicate, RDF iteration order would decide the result. B2 therefore keeps derived commitment facts
on the commitment record and adds an explicit merge step in the evidence-unit collection path.

Merge precedence is pinned:

1. authored `circular` wins over derived shared-source;
2. authored `shared-source` wins when present, with validation warnings for dataset-backed disagreement;
3. authored `independent` plus committed derived dependence is an ERROR and should block a clean validate
   run; collection may still leave the authored value untouched to avoid hiding the contradiction;
4. untagged lines may receive derived `shared-source` metadata from B2 commitment records;
5. candidate records never populate aggregation fields.

Conflict policy:

- authored `independence: circular` remains stronger than derived shared-source;
- authored `independence: shared-source` remains acceptable if the derived group agrees;
- authored `independence: independent` plus committed derived full-overlap dependence is an ERROR-class
  contradiction in validation;
- authored `independence: independent` plus candidate dependence remains a WARN-class
  `suspect-circular` result;
- authored dataset-based committed metadata may continue to drive aggregation even when B2 cannot derive
  the same signal, but validation should report a review warning when `sci:sharedDataset` is present and
  B2 has enough graph data to refute that dataset basis. Non-dataset groups, such as shared lab, shared
  cohort, shared platform, or shared method, are outside B2's evidence base and should not warn merely
  because B2 cannot derive them.

This policy preserves current projects while making derived graph evidence visible.

---

## 7. Graph Output

B2 should materialize derived records in the provenance graph rather than inventing a separate file
format. B2 introduces two derived record classes:

- `sci:DatasetIndependenceCandidate` for review-only component signals;
- `sci:DatasetIndependenceCommitment` for full-overlap dependence that aggregation may consume.

B2 materializes one record per `(target, kind, reason, connected evidence-line component)` rather than
one record per evidence-line pair. A component record may contain two or more member triples. This avoids
an O(K^2) record blow-up for heavily supported propositions while still allowing validation and review
code to derive pairwise explanations from the member set.

Both record types should be deterministic from their payloads so graph builds are stable. They should
point at the evidence lines, the shared dataset or datasets, the target proposition, and the usage records
or reduced usage facts that justify the signal.

The predicate surface should be explicit, small, and non-overloaded. B2 must not reuse
`sci:evidenceLine` for membership because that predicate already means proposition-to-JSON-encoded
evidence line in the graph store. B2 must also avoid reusing broad `sci:target`; the record target is a
specific proposition/finding target for an independence derivation, not an inquiry target. Use
B2-specific predicates instead:

```text
record  rdf:type                    sci:DatasetIndependenceCandidate | sci:DatasetIndependenceCommitment
record  sci:independenceTarget      proposition-uri
record  sci:independenceMember      evidence-line-uri
record  sci:independenceMember      evidence-line-uri
record  sci:sharedDataset           dataset-uri-or-canonical-ref
record  sci:independenceGroup       stable-derived-group
record  sci:independenceReason      reason-token
record  sci:derivedFromDatasetUsage usage-node
```

The `sci:independenceMember` triples form an unordered member set; deterministic record identity comes
from the sorted evidence-line URIs, target, sorted datasets, reason, and reduced usage payload. The
committed record may emit derived metadata only on the commitment record itself. It must not emit
`sci:evidenceIndependence`, `sci:independenceGroup`, or `sci:sharedDataset` convenience triples onto
evidence-line nodes; the collection path handles the authored-vs-derived merge explicitly.

---

## 8. Validate Check Changes

B2 extends validation in two places:

1. `independence.suspect-circular` should include graph-derived candidates in addition to authored
   `shared_dataset` / `independence_group` coincidences.
2. A new or extended check should report contradictions between authored independence and committed
   derived dependence.

Keeping the existing `independence.suspect-circular` rule id is intentional: B2 expands the source of
the suspicion from authored observability fields to derived dataset candidates, but the reviewer-facing
meaning remains "authored independence may be circular or double-counted."

Pinned severities:

| Case | Severity |
|---|---|
| derived candidate between two authored-independent or untagged lines on same target | WARNING |
| derived committed shared-source dependence but line is authored `independent` | ERROR |
| authored `shared_dataset` group cannot be supported by B2 but B2 has enough graph data to check that dataset basis | WARNING |
| graph data unavailable or no usage path exists | no result |

The committed-vs-authored-independent ERROR is raised against a line's own direct full-overlap
shared-dataset edge. It is not raised merely because the line was swept into a connected component
through another line's hub relationship.

Validation should not require commons resources beyond what graph build already materialized. If graph
data is absent, B2 checks should degrade cleanly with no result rather than re-parsing source files or
emitting stale warnings.

"Enough graph data to check that dataset basis" means the authored `shared_dataset` value resolves to a
dataset URI, every evidence-line member of the authored group exists in the materialized graph, and each
member has either direct usage ancestry or an explicit absence of direct usage ancestry in the B2 ancestor
index. If any member is missing from the graph or only has candidate/indirect ancestry, B2 should not
claim to refute the authored dataset basis.

---

## 9. Belief Aggregation Boundary

B2 has one allowed path into scoring: committed derived metadata. Candidate metadata is excluded.

The implementation should keep this boundary testable:

- `aggregate_belief` with only candidate records produces the same result as before B2;
- committed shared-source records collapse like authored `independence_group`;
- authored circular records continue to exclude like they do before B2;
- snapshot outputs carry the new belief config version only once committed derived metadata can affect
  results.

B2 should not change evidence strength, curation down-weight, source-class handling, or dispute
semantics. Those belong to A and existing belief code.

---

## 10. Non-Goals

B2 does not mechanically migrate `paper.datasets`; that is B-migration. It does not promote gene-set rows
to first-class dataset entities; that is D2. It does not infer biological overlap between distinct
datasets, perform cohort/sample-level matching, or resolve accession aliases. It only interprets shared
canonical dataset refs already materialized by B1.

---

## 11. Acceptance Criteria

The B2 implementation plan should cover:

- pure tests for usage reduction and most-dependent-wins behavior;
- graph tests deriving candidate and committed records from B1 usage nodes;
- graph tests proving `bears_on`-only ancestry is candidate-only even when role and overlap are otherwise
  commitment-worthy;
- graph tests proving a line with multiple full-overlap shared datasets is assigned one connected
  component group, not multiple committed groups;
- graph tests for the transitive hub case: A-B share dataset X, B-C share dataset Y, and B2 produces one
  conservative connected component while preserving both datasets as justification;
- graph tests proving virtual gene-set member ancestry is candidate-only in B2;
- validation tests for candidate WARN and committed-vs-authored-independent ERROR;
- validation tests proving untagged same-target lines with derived dataset candidates warn, not just
  lines explicitly authored as `independent`;
- validation tests proving the ERROR attaches only to direct full-overlap shared-dataset edges, not mere
  component co-membership;
- aggregation tests proving candidates do not affect belief and committed full-overlap dependence does;
- aggregation tests proving authored independence metadata and derived commitment records merge by the
  pinned precedence, without relying on RDF triple iteration order;
- aggregation tests proving support/dispute lines in the same derived component still set `contested`;
- snapshot/version tests if `CONFIG_VERSION` changes;
- regression tests showing `cited` alone does not collapse and `validation_source` does not become
  dependence unless the same pair also has a dependence role.
