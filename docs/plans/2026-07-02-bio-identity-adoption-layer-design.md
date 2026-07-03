# Bio Identity Adoption Layer — Design

- **Status:** Draft (approved in brainstorm 2026-07-02)
- **Date:** 2026-07-02
- **Scope:** `science` framework (model, CLI, validation, workflow-output contract, planning surfaces) + the MM30-critical `science-commons` pinned artifacts (assembly-registry, gene crosswalk, GRCh37↔GRCh38 liftover chains) + MM30 as the first fully-resolved consumer.
- **Depends on:** Pillar C (`bio.identity_context`), the reference-collection member-promotion substrate, existing commons datasets (`dataset:assembly-registry`, `dataset:assembly-liftover-grch37-grch38`, `dataset:gene-crosswalk-hgnc`), the dataset lifecycle commands (`dataset add` / `register-run`, `commons dataset init`), the plan data-access + reproducibility gates, and the `entities/workflows/<slug>.md` `outputs:` surface read by `register-run`.
- **Predecessor:** `docs/plans/historical/2026-05-26-bio-identity-and-reference-genome-design.md` (Pillar C — the identity model this layer adopts, not remodels).

## Purpose — the invariant

> Every **identity-bearing** dataset and every **coordinate- or feature-emitting workflow output** carries a machine-checkable organism + reference-genome declaration — either **resolved** to a canonical seqcol/namespace identity, or **explicitly `declared_unresolved`** — sourced from the **entity** as the single authority, **stamped** read-only into the datapackage for transport, and **enforced strict-by-default**. A cross-build or cross-namespace mix is never silent: it is either resolved, or declared as a structured `proxy`/`transform`, or it fails loud.

Everything in this design serves that one sentence. Pillar C already answers *what the canonical identity model is* (integer `taxon`, GA4GH refget seqcol-digest `assembly`, species-aware `{taxon, namespace, id}` gene keys) and already **validates** it — `identity_context.assembly`, cross-dataset assembly mismatch, gene/protein tier declarations, liftover remedies, and variant-row minting are live checks. What it does **not** do is make declaring identity a normal, cheap, enforced part of authoring a dataset or writing a workflow. This design closes exactly that gap and proves it end-to-end on MM30.

## Motivating failure

The t665 3D-genome locus ledger joins **GSE131651 (hg38)**, **GSE87585 (hg19)**, and MM30 meta scores (**GRCh38 HGNC-symbol space**) and emits a **cytoband-proxy** ledger whose coordinates are in *no single input build*. Today that build mix survives only as prose in the dataset entity body and a hand-rolled `genome_build` column invented locally in one script; the ledger's `causal_verdict` stays `not-promoted` and the TAD / A-B-compartment axes are explicitly deferred "behind the spun-off upstream genome-build-reconciliation work" — i.e. behind *this* effort.

The surrounding status quo is worse than "unstructured":

- MM30 hardcodes `species: Homo sapiens / taxonomy_id: 9606` as a literal constant in its shared datapackage emitter — it is *impossible* to emit a non-human package through the standard path, and three real murine-model datasets carry no structured organism marker at all.
- Reference build survives only as the substring `grch38` inside hardcoded asset **paths**, as prose in ~a dozen entity bodies, and as one bespoke per-script validator.
- Gene identity is silently harmonized to GRCh38 HGNC **symbols** at ingest (GRCh37-symbol → Ensembl → GRCh38-symbol via `annotables`), with coordinates discarded — a build/namespace transform that no contract records.
- MM30 consumes **none** of Pillar C: grep for `identity_context | seqcol | bio.rnaseq` across the repo returns zero hits.

The framework cannot currently detect an hg19/GRCh38 coordinate mismatch, decide whether two coordinate datasets are joinable, or drive a liftover — which is precisely why MM30 collapses to symbols and falls back to cytoband-proxy joins. This design makes build/organism **visible to tooling** everywhere, and turns the t665 proxy join from a hand-written caveat into a machine-checked property.

## What exists vs. what is missing

**Exists (Pillar C, implemented + merged):** the `bio.identity_context` schema (`taxon`, seqcol `assembly`, `molecular_ids` tiers, `resolution_status`); the offline resolvers and reference-collection substrate backing them; commons datasets `assembly-registry` (seqcol-keyed), `assembly-liftover-grch37-grch38`, `gene-crosswalk-hgnc`, `variant-labels-dbsnp-human`; and the validation checks that enforce the schema when it is present.

**Missing (this effort), stated precisely:**

1. **No cheap authoring path.** Identity lives only in an opt-in `profiles: [bio.identity_context]` extension keyed on a 100-char seqcol digest. Authors think `hg19`, not digests, and there is no mandatory lightweight declaration on the base dataset surface.
2. **The gate is not strict-by-default.** The checks fire only when the profile is present; nothing *requires* an identity-bearing dataset or a coordinate-emitting workflow output to declare anything.
3. **The CLI does not make identity a normal workflow step.** The resolvers are wired into validation but not into an *authoring* or *workflow* surface — there is no `resolve hg38`, no `stamp this dataset`, no `map this gene namespace` verb, and no workflow-output identity contract.

## Key decisions

Each names the chosen approach and the rejected alternative.

### Key decision 1: Adopt Pillar C, do not remodel it
- **Chosen:** treat `identity_context` (int `taxon`, seqcol-digest `assembly`, `molecular_ids` tiers, `resolution_status`) as settled; this effort is an adoption/ergonomics/enforcement layer on top.
- **Rejected:** reopening seqcol-digest-as-identity, the HGNC gene anchor, or the entity-vs-datapackage split. These are correct and merely under-adopted; reopening them spends the effort's budget on litigation instead of leverage.

### Key decision 2: Entity is the authority; the datapackage carries a derived read-only stamp
- **Chosen:** the dataset entity's `identity_context` is the single source of truth (matching the `entities.md` lifecycle split — entity frontmatter owns project-level metadata, datapackages own resource/file metadata). At promote/build time a `science.identity_context` stamp is written into `datapackage.json` as a derived, read-only cache; validation **fails if an authored stamp disagrees with the entity**.
- **Rejected:** *datapackage-first* (splits identity across two homes, inverts the entity/datapackage boundary, invites resource metadata to become project semantics); *entity-only with no stamp* (repeats the ergonomics failure — artifacts travel, downstream tools see only the datapackage). The stamp is a transport/cache surface, never the authority.

### Key decision 3: Mandatory is profile-scoped, not universal
- **Chosen:** requirement is keyed to the dataset/output **profile**. Coordinate-bearing assays require `assembly`; gene/protein/variant-bearing datasets require the relevant `molecular_ids` tier; **all** identity-bearing datasets require `taxon`. A purely clinical table needs `taxon` only when a downstream analysis makes it identity-bearing, never an assembly.
- **Rejected:** requiring organism+build on *every* base dataset (produces meaningless `UNKNOWN` noise on non-bio records and trains authors to rubber-stamp the gate).

### Key decision 4: Two-level strictness (declaration always; resolution at the publish boundary)
- **Chosen:** **declaration** (`taxon` + an assembly *label*, or an explicit `UNKNOWN`) is mandatory and strict-by-default for identity-bearing profiles — cheap, needs no artifact, ships immediately. **Resolution** (a present `seqcol_digest`, a namespace resolved against a pinned crosswalk) is required only at the **promote/publish** boundary or when a project opts in. The resolver **degrades to `declared_unresolved` with a clear message** when a registry artifact is absent.
- **Rejected:** single strict "must be fully resolved" gate (blocks all authoring on operator-pending artifact builds — the adoption killer) and fully-advisory warnings (reproduces today's silent-drift status quo).

### Key decision 5: An explicit resolver engine, reached mostly through integration
- **Chosen:** a first-class, **idempotent, non-interactive, workflow-reachable, batch-capable** verb — `science dataset identity resolve` — is the engine (reusing the `commons` resolvers already backing the checks). The **primary authoring affordance** is integration: `dataset add` / `commons dataset init` refuse to complete for an identity-bearing profile without identity (or explicit `UNKNOWN`); `register-run` auto-propagates identity for derived datasets. `--suggest-identity` offers scaffold-only inference.
- **Rejected:** *explicit-command-only* (a step authors must remember gets skipped — the identity_context adoption failure again) and *integrated-only, no standalone verb* (un-reproducible: cannot appear in a Snakemake rule, cannot batch-retrofit existing entities, cannot re-run on artifact update).

### Key decision 6: The workflow output declaration is the identity contract for derived data
- **Chosen:** `entities/workflows/<slug>.md` `outputs[].identity`, colocated with `resource_names`, is the contract. The hierarchy is: **(1)** the contract; **(2)** `register-run` resolves/propagates it into the derived dataset's `identity_context`; **(3)** the per-output datapackage gets the derived read-only stamp; **(4)** an optional run sidecar (`identity_context.yaml`, or the stamp in the aggregate run datapackage) is an *execution assertion* checked against the contract and **fails on disagreement**; **(5)** input inference is a scaffold suggestion (`--suggest-identity`), never authority.
- **Rejected:** declaring identity directly in the Snakemake rule (build-tool-specific, invisible to `register-run`) or trusting a script-written sidecar as the authority (a script that emits hg19 while the contract says hg38 must be *caught*, not believed).

### Key decision 7: `transform` is tier-general and provenance-checked; cross-build outputs use a discriminated `proxy`
- **Chosen:** a `transform` block (`liftover | symbol_remap | namespace_map`) may appear on **any** tier (assembly or `molecular_ids.<tier>`), because MM30's dominant real reconciliation is a *symbol-space remap*, not a coordinate liftover. A cross-build/cross-namespace output whose result is in no single input system keeps `assembly` honest (`resolution_status: declared_unresolved`, `seqcol_digest: UNKNOWN`) and adds a **discriminated `proxy {type, via, sources[≥1]}`** block that says "this unresolved state is intentional and structured." Every `transform.dataset` / `proxy.via` must resolve to a real dataset entity and materialize as a `reference`-role usage (see Key decision 9); every `proxy.sources[].dataset` (a real data ancestor) must appear in the run's data `inputs`. Undeclared ⇒ rejected.
- **Rejected:** *assembly-only transforms* (leaves MM30's symbol-collapse silent — the single most common harmonization); *prose-only `declared_unresolved`* (leaves the motivating hg19/hg38 mix exactly as invisible as today); *deep coordinate-proxy semantics* (a full coordinate ontology is out of scope — the shallow `proxy.type` enum is the minimum machine-visible contract).

### Key decision 9: Reference artifacts are provenance-tracked but never data ancestors
- **Chosen:** the datasets named by `transform.dataset` and `proxy.via` (liftover chains, gene/protein crosswalks, the cytoband reference) are **reference machinery**, not data inputs. They propagate into the derived dataset's `derivation.transformations[].dataset` — the surface the existing coordinate-mismatch remedy validator already reads and provenance-checks (`validate/checks/identity_context.py:199-226`) *without* requiring the artifact in `derivation.inputs` — and materialize as a non-dependence usage **role** (`reference`, excluded from `DEPENDENCE_ROLES` exactly as `cited`/`validation_source` already are). They are **never** injected into `derivation.inputs`. Only `proxy.sources[].dataset` — the datasets whose signal flows into the join (e.g. GSE131651, GSE87585) — enter `derivation.inputs` as normal data ancestors.
- **Rejected:** *reference artifacts as normal `inputs:`* — `derivation.inputs` is a single overloaded spine (`datasets_register.py` fans it into every output's `derivation.inputs`, mints `consumed_by`, feeds the transitive plan **access** + **reproducibility-class** gates in `plan_gate.py`, and materializes `role: upstream` **dependence** usages driving B2 shared-source independence); a liftover chain placed there would falsely flag two evidence lines that merely share a coordinate-conversion tool as non-independent, and could drag an output's reproducibility class down to the chain's. *A parallel `reference_inputs:` list* — unnecessary duplication; the identity contract's `transform`/`proxy` blocks already name the artifacts, and `derivation.transformations[]` is the existing validated home for exactly this.

### Key decision 8: `inherit` is strict
- **Chosen:** `assembly: inherit` (or `taxon: inherit`, `molecular_ids.<tier>: inherit`) means *all relevant inputs agree exactly after resolution*, and **fails otherwise**. `inherit: { from: dataset:X }` selects one explicit source, and that selection is visible enough for a reviewer to ask why.
- **Rejected:** silent "pick the first / pick any" inheritance (normalization, aggregation, liftover, symbol-remap and proxy steps all look "same input, same output" from the outside unless intent is declared).

## Data model

### 1. Entity `identity_context` (source of truth)

Resolved coordinate assay:

```yaml
identity_context:
  taxon: 9606
  assembly:
    label: GRCh38
    seqcol_digest: g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp
    registry: dataset:assembly-registry
    resolution_status: resolved
  molecular_ids:
    gene:
      namespace: hgnc_symbol
      registry: dataset:gene-crosswalk-hgnc
      resolution_status: resolved
```

Honest unknown (declaration-level, no artifact needed):

```yaml
identity_context:
  taxon: 9606
  assembly:
    label: hg19-from-paper
    seqcol_digest: UNKNOWN
    registry: dataset:assembly-registry
    resolution_status: declared_unresolved
```

### 2. Datapackage stamp (derived, read-only, validated `== entity`)

```yaml
science:
  identity_context:
    taxon: 9606
    assembly:
      label: GRCh38
      seqcol_digest: g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp
      registry: dataset:assembly-registry
      resolution_status: resolved
```

The stamp is written by the resolver / `register-run`, never hand-authored as authority. `validate` fails if an authored stamp disagrees with the entity.

### 3. Workflow output contract — `entities/workflows/<slug>.md`

Pass-through (all inputs agree):

```yaml
outputs:
  - slug: normalized-expression
    title: "Normalized expression matrix"
    resource_names: ["expression"]
    identity:
      taxon: inherit
      assembly: inherit
      molecular_ids:
        gene: inherit
```

Symbol-space remap (the MM30-dominant gene-tier transform):

```yaml
    identity:
      taxon: inherit
      molecular_ids:
        gene:
          namespace: hgnc_symbol
          transform:
            type: symbol_remap          # GRCh37 symbols → Ensembl → GRCh38 symbols
            from: input
            dataset: dataset:gene-crosswalk-hgnc
```

Coordinate liftover (assembly-changing):

```yaml
    identity:
      taxon: inherit
      assembly:
        label: GRCh38
        transform:
          type: liftover
          from: input
          method: ucsc_chain
          dataset: dataset:assembly-liftover-grch37-grch38
      molecular_ids:
        variant: inherit
```

Cross-build proxy (the t665 case — no single output build):

```yaml
    identity:
      taxon: 9606
      assembly:
        resolution_status: declared_unresolved
        label: mixed-build-cytoband-proxy
        seqcol_digest: UNKNOWN
        registry: dataset:assembly-registry
        proxy:
          type: cytoband_proxy           # cytoband_proxy | interval_overlap_proxy | symbol_space_proxy
          via: dataset:cytoband-hg19
          sources:
            - { dataset: dataset:gse131651-shah2019-nsd2, assembly: inherit }
            - { dataset: dataset:gse87585-wu2017,          assembly: inherit }
```

### 4. Validation truth-table

| Situation | Verdict |
|---|---|
| Identity-bearing profile, no `assembly`/tier declared | **error** |
| `assembly` present, declaration only (`label` + `resolution_status: declared_unresolved`) | **pass** (declaration gate); resolution deferred |
| Mixed-build output, no `proxy`/`transform` | **error** (or strict warning during the migration window) |
| `declared_unresolved` **with** structured `proxy` | **pass**, precision caveat emitted |
| `transform.dataset` / `proxy.via` does not resolve to a real dataset entity (reference-role, lands in `derivation.transformations[]`, never `derivation.inputs`) | **error** |
| `proxy.sources[].dataset` (data ancestor) not in the run's data `inputs` | **error** |
| bare `inherit` with inputs disagreeing after resolution | **error** |
| authored datapackage stamp disagrees with entity | **error** |
| resolution required (promote/publish) but `seqcol_digest: UNKNOWN` | **error** at the publish boundary only |

`proxy` with a single source is legal (a lone-input proxy such as a pure symbol-space remap that changes join semantics without mixing builds).

## Architecture

```
~/d/science/                                          (framework)
  science/model/src/science_model/
    schemas/extension-bio-identity_context-1.0.json   MODIFY  add assembly.proxy + tier transform; relax additionalProperties
    packages/schema.py                                MODIFY  Pydantic models for proxy/transform; profile-scoped requiredness
    frontmatter.py                                    MODIFY  coerce identity_context sub-blocks
  science/src/science_tool/
    commons/identity_resolve.py                       NEW     the resolver engine (label→seqcol, namespace→crosswalk, degrade→declared_unresolved)
    commons/identity_stamp.py                         NEW     derive the science.identity_context stamp; agreement-check
    datasets_identity.py + cli.py (dataset_group)     NEW     `dataset identity resolve|show|suggest` (subgroup on cli.py:6696)
    datasets_catalog.py (add_dataset)                 MODIFY  require identity for identity-bearing profiles at add-time
    commons/dataset_lifecycle.py (scaffold_dataset..) MODIFY  require identity on `commons dataset init` (commons/cli.py)
    datasets_register.py (per-output dp + derived)    MODIFY  read outputs[].identity; propagate → identity_context + schema_profile token; route reference machinery to derivation.transformations[] vs data sources to derivation.inputs; stamp per-output dp; check sidecar
    validate/checks/identity_context.py               MODIFY  declaration gate (strict, schema_profile-keyed), stamp-agreement, proxy/transform provenance, strict inherit
    graph/dataset_usage.py, graph/dataset_independence MODIFY  add non-dependence `reference` usage role (excluded from DEPENDENCE_ROLES)
    project_config.py                                 MODIFY  identity_policy (declaration strict; resolution-at-publish; migration window)
  templates/dataset.md                                MODIFY  identity_context authoring block
  templates/workflow.md                               MODIFY  outputs[].identity contract
  docs/user-guide/entities.md                         MODIFY  authoring guidance
  commands/plan-pipeline.md, plan-analysis.md         MODIFY  identity in the data-availability gate

~/d/science-commons/                                  (pinned artifacts — P4, MM30-critical subset)
  datasets/assembly-registry/                         WIRE    build entrypoint for the seqcol registry
  datasets/gene-crosswalk-hgnc/                       WIRE    build entrypoint for the gene crosswalk
  datasets/assembly-liftover-grch37-grch38/           UNCHANGED (chains already pinned; ensure resolver consumes)
  datasets/cytoband-hg19/                             NEW?    promote the UCSC hg19 cytoBand as a proxy `via` reference (or keep MM30-local)

~/d/cancer/.../multiple-myeloma/                      (first fully-resolved consumer — P5)
  scripts/shared/datapackage.py                       MODIFY  drop the hardcoded species constant; stamp from entity identity
  entities/datasets/*.md (255)                         MODIFY  declaration-level identity backfill (batch); resolve coordinate/gene sets
  entities/workflows/*.md                              MODIFY  outputs[].identity contracts on coordinate-emitting workflows
  t665 ledger + entities                               MODIFY  structural cytoband proxy; unblock TAD / A-B-compartment axes
```

## Phases / Work Packages

P1–P3 land against `declared_unresolved` and are useful before P4 exists. **P4 is an enabling workstream inside this effort, not a follow-on.** P5 is not complete until the MM30-critical P4 artifacts actually resolve.

### P1 — Declaration + profile-scoped gate + datapackage stamp
- **Depends on:** Pillar C schema (present).
- **Entry point:** `extension-bio-identity_context-1.0.json`, `schema.py`, `frontmatter.py`, `validate/checks/identity_context.py`, `templates/dataset.md`, `project_config.py`.
- **Definition of done:** an identity-bearing dataset fails validation without `taxon` + `assembly` label (or explicit `UNKNOWN`); the datapackage stamp is derived + agreement-checked; no artifact required. Strict-shippable.

### P2 — Resolver engine + lifecycle integration
- **Depends on:** P1.
- **Entry point:** `commons/identity_resolve.py`, `identity_stamp.py`, `datasets/identity_cli.py`; `dataset add` / `commons dataset init` / `register-run` hooks.
- **Definition of done:** `science dataset identity resolve` resolves labels where a registry is available and degrades to `declared_unresolved` otherwise; `add`/`init` refuse identity-bearing profiles without identity; `--suggest-identity` proposes `inherit`.

### P3 — Workflow output contract + propagation + transform/proxy
- **Depends on:** P2.
- **Entry point:** `templates/workflow.md` `outputs[].identity`; `register-run` propagation; sidecar-vs-contract check; `transform`/`proxy` schema + provenance checks; strict `inherit`.
- **Definition of done:** a derived dataset minted by `register-run` carries a propagated `identity_context`; a mixed-build output without `proxy`/`transform` fails; `transform.dataset` / `proxy.via` are provenance-checked; the t665 proxy shape validates.

### P4 — MM30-critical pinned artifact builders (enabling)
- **Depends on:** P2 (resolver contract).
- **Entry point:** `science-commons` build entrypoints for `assembly-registry`, `gene-crosswalk-hgnc`, and consumption of `assembly-liftover-grch37-grch38`; promote/resolve `cytoband-hg19` as a proxy `via`.
- **Definition of done:** `resolve hg38 → seqcol`, `map GRCh37 → GRCh38 symbol`, and `lift hg19 → hg38` actually run offline against pinned, hash-verified artifacts.

### P5 — MM30 as first fully-resolved consumer
- **Depends on:** P3 + P4.
- **Entry point:** MM30 `scripts/shared/datapackage.py`, the 255 dataset entities, coordinate-emitting workflows, the t665 ledger.
- **Definition of done:** declaration-level coverage across the existing entities; resolved identity for the coordinate/gene datasets where artifacts exist; `register-run` propagation working for derived outputs; datapackage stamps checked; t665's cytoband-proxy output represented **structurally** rather than prose-only, unblocking the TAD / A-B-compartment axes.

## Scope decomposition

- **Owned in this effort (P1–P5):** the declaration fields + profile-scoped gate + datapackage stamp; the `dataset identity resolve` engine + lifecycle integration; the workflow `outputs[].identity` contract + propagation + transform/proxy validation; the MM30-critical pinned artifacts (assembly-registry, gene crosswalk, GRCh37↔GRCh38 chains, a cytoband proxy reference); and the MM30 retrofit through the t665 unblock.
- **Deferred unless already cheap:** dbSNP variant-label build, protein-crosswalk expansion, transcript/protein HGVS projection, reverse-strand/broad-interval liftover, GRCh37-as-target, richer proxy/coordinate semantics, and any actual multi-species population beyond the schema/API shape.
- **Definition of done (effort):** MM30 can **declare, resolve, propagate, stamp, validate, and unblock t665** — the end-to-end claim is real only when the motivating workflow is proven, not when the contract merely exists.

## Non-goals

- Reopening any Pillar C identity model decision (seqcol-as-key, HGNC anchor, entity-vs-datapackage authority).
- A full coordinate ontology or lift of arbitrary interval/BED geometry — the `proxy.type` enum is deliberately shallow.
- Making the datapackage stamp authoritative under any circumstance.
- Populating non-human taxa (schema/API stay multi-species-ready; only human is resolved).

## Open questions

- **`cytoband-hg19` home.** Is the proxy `via` reference a new `science-commons` dataset, or does it stay MM30-local and the contract points at the MM30 dataset entity? (Leaning: promote to commons in P4 so other projects reuse it; confirm the exact commons slugs for `assembly-registry` / `gene-crosswalk-hgnc` at build time.)
- **Migration window strictness.** For existing workflows/datasets without identity, is the first release a **warn-then-error** window, or error-immediately for newly-touched entities and warn for untouched? (Leaning: strict for entities touched after P1 lands; timed warn window for the untouched backlog, surfaced by a batch report so nothing is silently exempt.)
- **Multi-input `transform.from: input`.** When several inputs exist, `from: input` is sugar only for the single-input case; multi-input requires `from: dataset:X`. Confirm the validator rejects bare `input` under multiple inputs.

## Acceptance criteria

- [ ] An identity-bearing dataset without `taxon` + `assembly` (label or explicit `UNKNOWN`) fails `science validate` (P1).
- [ ] `datapackage.json` carries a derived `science.identity_context` stamp; an authored stamp disagreeing with the entity fails validation (P1).
- [ ] `science dataset identity resolve` resolves labels where artifacts exist and degrades to `declared_unresolved` with a message otherwise (P2/P4).
- [ ] `dataset add` / `commons dataset init` refuse an identity-bearing profile without identity or explicit `UNKNOWN` (P2).
- [ ] A `register-run`-minted derived dataset carries a propagated `identity_context`; a mixed-build output without `proxy`/`transform` fails; `transform.dataset` / `proxy.via` are provenance-checked; bare `inherit` on disagreeing inputs fails (P3).
- [ ] MM30's hardcoded species constant is removed and the datapackage stamp derives from entity identity (P5).
- [ ] MM30 has declaration-level identity across existing entities and resolved identity for the coordinate/gene datasets where artifacts exist (P5).
- [ ] The t665 ledger output declares a structured cytoband `proxy`, and the TAD / A-B-compartment axes are unblocked (P5).
