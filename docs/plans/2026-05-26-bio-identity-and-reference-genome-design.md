# Bio Identity, Reference Genomes & ID Mapping (Pillar C)

Date: 2026-05-26

Status: design for review (Phase 1 of the bio data architecture; foundational)

Related (builds on):
- `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md` — umbrella; this is its Pillar C
- `docs/plans/2026-04-19-dataset-entity-lifecycle-design.md` — dataset mixin, `origin`, `access`
- `science/model/src/science_model/schemas/extension-bio-*.json` — `bio.rnaseq`/`bio.scrna`/`bio.cna` carry free-text `reference_genome`
- `docs/plans/2026-05-23-store-decomposition-design.md` — commons store (where pinned snapshots live)
- consumer context: `health/meta:doc/topics/large-scale-biological-datasets-landscape.md` shortlist #1 (`~/d/health/meta`)

---

## 1. Purpose & scope

Pillar C is the **identity substrate** for the bio data layer: nothing joins, dedupes, lifts over, or
aggregates across datasets without canonical molecular identifiers and explicit, validated reference
genomes. It is Phase 1 of the umbrella because every later pillar (taxonomy A, influence B, gene sets D,
Reactome E) resolves identity through it.

**Two decisions are already locked (umbrella review):**

1. **Scope = gene + protein + variant.** All three molecular identity tiers, *including* genomic
   coordinates and cross-assembly liftover, are in Phase 1. This is the heavyweight phase by design.
2. **Pinned-authoritative, live discovery-only.** Every in-pipeline join resolves through versioned,
   archive-durable local snapshots. Live services (MyGene.info, Ensembl REST, refgenieserver) are
   permitted for interactive discovery only, never inside a reproducible run.

**Explicit non-goals.** This pillar does **not** classify datasets by epistemic source (A), track
dataset influence (B), define the gene-set type (D), or ingest Reactome (E). It also does **not** resolve
*non-molecular* entity identity — cell lines (Cellosaurus), diseases/phenotypes (MONDO/HPO), tissues, and
other ontology terms. These are **resolver infrastructure, not epistemic taxonomy**, so they get their
*own later identity pillar* (not folded into A; §7). C covers molecular identity (gene/protein/variant)
plus reference-genome/assembly, and ships the **`identity_space` declaration interface** that the later
pillar will extend: every bio extension may declare the identity space of its keys, and any space outside
C resolves as **declared-unresolved** until that pillar lands.

---

## 2. What exists, what's missing

| Today | Gap C closes |
|---|---|
| `reference_genome` is **free text** on `bio.rnaseq`/`bio.scrna`/`bio.cna` (`GRCh37` and `hg19` do not unify; decoy/patch flavors silently conflated) | A content-digest assembly identity (refget seqcol), with accession/labels as aliases; assembly/coordinate-system mismatch becomes detectable |
| No identifier crosswalks anywhere in the framework | Pinned gene/protein crosswalk snapshots as the authoritative join layer |
| No representation of variants or genomic coordinates | A canonical, deterministic variant identity + assembly-anchored coordinates |
| No notion of "which id space are these keys in?" | An explicit identity-space declaration on datasets/extensions |
| Identity would otherwise be resolved ad hoc (live services, hand maps) | One reproducible resolver over pinned snapshots |

Identity is the umbrella's principle 5 ("the substrate") and the landscape topic's shortlist #1
("cross-resource identity graph, build first"). C is the concrete realization of both.

---

## 3. Locked design decisions

### C-D1 — Three molecular identity tiers, each canonical id + accepted inputs

| Tier | Canonical identity | Accepted input ids (mapped *to* canonical) | Notes |
|---|---|---|---|
| Gene | **Species-aware structured key** `{taxon, namespace, id}` — human anchor `{taxon: 9606, namespace: hgnc, id: HGNC:n}` | HGNC symbol, Entrez/NCBI Gene ID, Ensembl gene ID | Entrez is **not** canonical; Ensembl is a versioned *annotation* id, not the anchor (§7 d1). Never a bare gene id without taxon + namespace (§7 d6) |
| Protein | **UniProtKB accession** (Swiss-Prot canonical) | Ensembl protein/transcript, RefSeq protein, Entrez | Isoform accessions (`P12345-2`) are a valid *lower-level* identity for sequence-specific / proteomics / protein-variant work — **not collapsed** to the canonical (§7 d5) |
| Variant | **GA4GH VRS 2.0 computed identifier** (`ga4gh:VA…`) | genomic HGVS (with sequence accession), VCF (`chrom-pos-ref-alt`), SPDI | Deterministic/computed — needs *no* service. **rsID and transcript/protein HGVS are not initial inputs**: rsID needs a pinned dbSNP snapshot; transcript/protein HGVS needs transcript/protein reference resolution + projection policy (§7 d4/d5) |

VRS is the load-bearing choice for variants: it produces globally-unique identifiers *computationally,
without a central authority*, by fully-justified normalization extending NCBI's SPDI model, and its
reference implementation translates from HGVS/SPDI/VCF. A computed identifier is exactly what the
pinned-authoritative decision wants — variant identity is reproducible from the (assembly-anchored)
sequence + normalization rules alone, with no live lookup. The design targets **VRS 2.0** (GA4GH-approved;
its inherent-property computed-identifier model fits this design); C4 pins the exact VRS spec + library
version. Note the contrast that drives the input list: a VRS id is deterministic *once you hold the
allele/location object*, but resolving an external label such as an rsID *to* that object is itself a
versioned mapping — hence rsID is gated on a pinned dbSNP / NCBI Variation snapshot, not a free input.

### C-D2 — Reference genome / assembly as structured, validated metadata

- **Canonical assembly identity = GA4GH refget Sequence Collection (seqcol) digest.** The content-based
  collection digest *is* the identity key, because it captures the actual coordinate system; NCBI Assembly
  accession (`GCA_…`/`GCF_…`) and human labels (`GRCh38`, `hg38`) are **aliases/metadata**, not the key.
  This is deliberate: `b37`, `hs37d5`, and assorted decoy/alt/patch flavors are **not** simple synonyms
  for "GRCh37" — they are *different sequence collections* with potentially different coordinates, and a
  label-based synonym table would silently conflate them. seqcol's comparison protocol additionally lets
  us assert a *shared coordinate system* between two collections that are not byte-identical.
- **Per-contig refget sequence digests** still pin each contig to actual sequence bytes (the GA4GH
  sequence checksum) and tie to **refgenie** asset digests for genome assets (FASTA, indices); the seqcol
  digest is the collection-level roll-up over them.
- `reference_genome` is promoted from free text to a structured assembly field validated against a pinned
  **assembly registry** keyed by seqcol digest; an unrecognized assembly or a coordinate-system mismatch
  is a detectable condition.

### C-D3 — Pinned crosswalk sources (the authoritative join layer)

Each crosswalk/registry is itself a **commons `reference` dataset** (Pillar A class), with a recipe and
hash-verified bulk artifacts — identity infra dogfoods the dataset model:

| Artifact | Pinned source (archive-durable release) | Provides |
|---|---|---|
| Gene crosswalk | HGNC quarterly complete set; NCBI `gene_info` + `gene2ensembl`; Ensembl/BioMart release | structured gene key ↔ symbol ↔ Entrez ↔ Ensembl gene |
| Protein crosswalk | UniProt per-release `idmapping` (human) | UniProtKB ↔ Ensembl ↔ Entrez ↔ RefSeq; isoform accessions |
| Assembly registry | NCBI assembly reports + refget seqcol & sequence digests | seqcol digest ↔ accession ↔ labels/aliases ↔ per-contig digest |
| Liftover chains | UCSC / Ensembl release chain files (e.g. GRCh37→GRCh38) | cross-assembly coordinate mapping (C-D5) |
| Variant labels *(optional, C4+)* | dbSNP / NCBI Variation Services export | rsID ↔ allele/location (required only if rsID input is enabled) |
| Transcript/protein reference set *(optional, C4+)* | RefSeq / Ensembl transcript + protein release | resolves transcript/protein HGVS to sequence + projection |

All are immutable, dated release handles (consistent with the Reactome/HGNC immutable-source rule already
adopted). `latest`/`current` endpoints are discovery-only.

### C-D4 — Live services: discovery-only

- **refgenie/refgenieserver** — sanctioned for genome *asset* provenance (digest-pinned assemblies and
  indices), not for id crosswalks.
- **MyGene.info, Ensembl REST, UniProt ID-mapping web tool** — interactive discovery and snapshot QA
  only; a reproducible run must not call them. (This is the locked decision, recorded here for the
  implementation plan.)

### C-D5 — Cross-assembly handling

- Every coordinate-bearing dataset **must declare its (source) assembly** by seqcol digest (C-D2). Joins
  across datasets on different assemblies are rejected unless lifted.
- **GRCh38 is the canonical analysis assembly; GRCh37 is a first-class *declared source* assembly** — not
  a co-equal canonical target. The default liftover target is GRCh38; a GRCh37 target requires explicit
  per-project opt-in. C provides **pinned liftover** to the canonical target, **flagging** unliftable,
  multi-mapping, or strand-ambiguous coordinates rather than silently dropping them.
- **Source and lifted assembly are preserved separately.** A lifted coordinate/variant is a *related
  re-identification*, recorded with its liftover provenance — **not** the same coordinate by assertion.
  Because VRS ids are assembly-anchored, the lifted variant is a distinct (linked) identity, making the
  re-identification explicit rather than an implicit coordinate coincidence.

---

## 4. How identity infra lives in the commons

The crosswalks, assembly registry, and liftover chains are pinned `reference` datasets under the commons
data root, each with `recipe/` (fetch + build + lockfile) and a `datapackage.yaml` carrying
`hash: sha256:…` per resource — the same structure as `ccle-proteomics-nusinow-2020`. A thin **resolver
library** reads these snapshots and exposes a **species-aware, namespace-explicit** API — e.g.
`to_canonical({taxon, namespace, id}, target_space)`, `assembly(label_or_digest) → registry entry`,
`liftover(coord, from_seqcol, to_seqcol)`, and `vrs_id(variant, assembly_seqcol)`. There is **no bare
`gene_id`**: every call carries taxon + namespace, so multi-species support (implementation deferred,
§7 d6) needs no later API break. The resolver is pure over pinned inputs (no network), so any pipeline
that uses it is reproducible by construction. It also honors the `identity_space` declaration: keys in a
space C does not yet resolve (cell line, ontology) pass through as **declared-unresolved**, not errors.

This makes Pillar C the **first real exercise of Pillar A's `reference` class** — a useful forcing
function: if the identity snapshots don't fit the dataset model cleanly, A needs revision before it
locks.

---

## 5. Validation surface (new checks)

1. **Assembly declared & recognized** — any `bio.*` extension carrying coordinates must set a structured
   assembly that resolves in the registry. Free-text-only `reference_genome` becomes a warning, then an
   error after migration.
2. **Identifier resolvability** — declared keys resolve against the pinned crosswalk for their declared
   `identity_space`; unresolved ids are reported with counts (not silently passed). Keys whose
   `identity_space` is outside C (cell line, ontology) are **declared-unresolved** and pass without error
   until the later identity pillar lands.
3. **Cross-dataset assembly mismatch** — a derived dataset whose inputs span assemblies (differing seqcol
   digests) without a liftover step is flagged. **C1 *detects* the mismatch; the remedy (liftover) is not
   available until C4** — until then the flag stands as a blocking condition the author resolves manually
   or by waiting for C4.
4. **Deprecated / merged / withdrawn ids** — merged Entrez ids, retired HGNC symbols, withdrawn UniProt
   accessions, and ambiguous many-to-one maps are *mapped through with provenance* and **flagged**, never
   dropped or guessed.

---

## 6. Stress-test recheck (against umbrella §5)

| Source | What C must handle | Verdict |
|---|---|---|
| GTEx bulk RNA-seq | gene ids + single assembly | assembly registry + gene crosswalk (in scope) |
| DepMap | gene crosswalk **+ cell-line identity** | gene part in scope; **cell-line identity declared-unresolved** until the later identity pillar (§7 d3) — surfaced via `identity_space`, not half-solved |
| MSigDB / Reactome | symbol↔Entrez↔Ensembl mapping; the "unsafe pathway-co-membership join" lesson | gene crosswalk replaces unsafe joins (in scope) |
| Open Targets / GO / MONDO | gene + **disease/ontology identity** | gene part in scope; **disease/ontology identity declared-unresolved** until the later identity pillar (§7 d3) |
| AlphaMissense | variant identity + assembly-anchored coordinates + liftover | VRS 2.0 + C-D2 + C-D5 (in scope; the reason variant tier is Phase 1) |
| UniProt / AlphaFold | protein identity + protein↔gene | protein crosswalk (in scope) |

C cleanly serves the molecular-identity needs of all six; the two non-molecular identity needs (cell
line, disease/ontology) it surfaces are **declared-unresolved** via the `identity_space` interface and
routed to the later identity pillar — named and interface-stubbed, not half-solved.

---

## 7. Resolved decisions (review steer)

All six umbrella-review open questions were resolved in review; recorded here as decisions:

1. **(d1) Canonical gene anchor.** HGNC ID for human gene identity, expressed as a **species-aware
   structured key** `{taxon, namespace, id}` so the design is not a single-species dead end. Entrez is
   **not** canonical; Ensembl is kept as a versioned *annotation* identifier, not the anchor.
2. **(d2) Canonical assembly.** GRCh38 is the canonical analysis assembly; GRCh37 is a first-class
   *declared source* assembly, lifted to GRCh38 by default (a GRCh37 target requires explicit project
   opt-in). Source and lifted assembly are preserved separately (C-D5).
3. **(d3) Non-molecular identity.** Gets its **own later identity pillar** — it is resolver
   infrastructure, not epistemic taxonomy, so it is **not** folded into A. C ships the `identity_space`
   declaration interface now; spaces outside C are declared-unresolved until that pillar lands.
4. **(d4) VRS version.** Target **VRS 2.0** (GA4GH-approved; inherent-property computed-identifier model).
   C4 pins the exact spec + library version.
5. **(d5) Protein isoforms.** Canonical protein entity = UniProtKB accession; isoform accessions
   (`P12345-2`) are retained as a valid lower-level identity for sequence-specific / proteomics /
   protein-variant work and are **not** collapsed.
6. **(d6) Non-human species.** Implementation deferred, but the resolver API is **multi-species from the
   start** (taxon + namespace on every key; no bare gene id).

**Residual implementation-plan choices** (settled when writing C4, not blocking this design): whether the
dbSNP and transcript/protein-reference snapshots ship inside C4 or a C4+ increment; the depth of
transcript/protein HGVS projection support; and the exact pinned VRS library version.

---

## 8. Decomposition & phasing (within C)

C is large; it ships in independently-testable sub-phases:

| Sub-phase | Locks |
|---|---|
| C1 — Assembly registry (seqcol-keyed) + structured `reference_genome` + `identity_space` interface + checks 1 & 3 (detect-only) | assembly identity; cheapest win, unblocks GTEx-class data; mismatch *detected*, remedy in C4 |
| C2 — Gene crosswalk reference datasets + resolver `to_canonical` + checks 2 & 4 | gene identity; unblocks MSigDB/Reactome/GTEx joins |
| C3 — Protein crosswalk | protein identity; unblocks UniProt/AlphaFold |
| C4 — Variant identity (VRS 2.0 / SPDI) + liftover (C-D5); optional dbSNP + transcript-ref snapshots | variant identity; unblocks AlphaMissense-class; supplies the liftover remedy for check 3 |

C1→C2 are the critical path for the other pillars (A's `reference` class, D's gene-set identifier space,
B's dataset resolution all need gene identity first). C3/C4 can trail.

---

## 9. Status & next step

Pillar C design for review. On approval, the writing-plans skill produces the implementation plan,
starting with sub-phase **C1** (assembly registry + structured `reference_genome`), the cheapest piece on
the critical path. Pillar A (taxonomy) can begin in parallel once C1/C2 establish the `reference`-dataset
pattern this doc relies on.
