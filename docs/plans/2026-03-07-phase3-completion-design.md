# Phase 3 Completion — Design

*Date: 2026-03-07*
*Status: Approved*

## Goal

Close the Phase 3 gate by running a real biomedical research project end-to-end through Phases 1-3, generating infrastructure artifacts (OpenAlex snapshot, biomedical starter profile) driven by actual usage, and archiving evidence.

## Phase 3 Gate Criteria

> At least one project can agent-construct a knowledge graph from prose, import a distilled snapshot, run use-case queries with table/json output, detect changes via hybrid `graph diff`, pass `graph validate` + `validate.sh`, and provide an archived exemplar evidence bundle.

## Research Project

**Title:** 3D Structure-Aware Attention Bias for Nucleic Acid Foundation Models

**Research question:** Can we use inferred 3D DNA/RNA structures to adjust pairwise attention weights between base pairs in a sequence based on their predicted distance from one another in 3D space?

**Core intuition:** Current nucleic acid foundation models treat sequence as 1D. Attention decays with linear position distance (or is position-agnostic). Models might perform better if attention were modulated by predicted 3D distance — positions close in folded space but far in linear sequence (e.g., promoter-enhancer loops, RNA tertiary contacts) would attend more strongly to each other.

**Proposed approach:** Use AlphaFold 3 to predict 3D structures for input sequences, compute pairwise distance matrices, and modify the embedding model to incorporate 3D distance as attention bias (similar to ALiBi but with structural distance).

**Open questions (to be captured in project):**
1. Do any existing models already incorporate 3D structural distance effectively?
2. How should 3D distance be incorporated? (pre-training attention bias, fine-tuning, regularization)
3. How big of a window surrounding a sequence of interest should be considered?
4. Are there cases where 3D contextual information is more/less important, and can we adapt accordingly?

**Project location:** `~/d/3d-attention-bias/` (separate repo)

## Execution Flow

### Step 1: Scaffold project

Run `/science:create-project` in `~/d/3d-attention-bias/`.

Inputs:
- Research question as stated above
- 4 open questions into `specs/` and `doc/08-open-questions.md`
- Tags: `genomics`, `deep-learning`, `structural-biology`, `attention-mechanisms`

### Step 2: Background research

Research 3-5 topics with 3-5 papers per topic (~15-25 paper summaries total).

**Topics:**
1. **Nucleic acid foundation models** — DNABERT-2, Nucleotide Transformer, RNA-FM, Caduceus, Evo
2. **AlphaFold 3 and nucleic acid structure prediction** — AF3, RoseTTAFold2NA, trRosettaRNA
3. **Attention bias and positional encoding** — ALiBi, RoPE, relative position encodings, structure-conditioned attention
4. **Structure-aware protein language models** — ESM-IF, GearNet, SaProt (precedent from protein domain)
5. **DNA/RNA 3D structure and function** — chromatin looping, RNA tertiary structure, enhancer-promoter interactions

Use `/science:research-topic` for each topic, `/science:research-paper` for individual papers.

### Step 3: Build knowledge graph

Run `/science:create-graph` — agent extracts entities, relations, claims from background docs.

Expected graph characteristics:
- ~30-50 concept entities with rich properties (`--note`, `--property`, `--status`, `--source`)
- ~15-25 paper entities
- ~20-40 claims with provenance and confidence
- Hypotheses from `specs/hypotheses/`
- Open questions linked to hypotheses
- CiTO predicates (`cito:supports`, `cito:discusses`, `cito:extends`)
- Biolink types for biological entities (`biolink:Gene`, `biolink:BiologicalProcess`)

### Step 4: Generate and import OpenAlex snapshot

**Infrastructure work (in science repo):**
1. Run `science-tool distill openalex --level subfields` with real API call
2. Commit resulting `data/snapshots/openalex-science-map.ttl` + `manifest.ttl` to science repo

**In exemplar project:**
3. Run `science-tool graph import <path-to-snapshot>`
4. Verify import with `graph stats`

### Step 5: Validate and capture evidence

Run in exemplar project:
```bash
science-tool graph stats --format json
science-tool graph validate --format json
science-tool graph diff --mode hybrid --format json
science-tool graph neighborhood "DNABERT-2" --hops 2 --format json
science-tool graph claims --format json
science-tool graph coverage --format json
validate.sh
```

Archive outputs into `docs/exemplar-evidence/` in the science plugin repo:
- `graph-stats.json`
- `graph-validate.json`
- `graph-diff.json`
- `query-neighborhood.json`
- `query-claims.json`
- `query-coverage.json`
- `validate-sh.log`
- `README.md` pointing to exemplar repo

### Step 6: Biomedical starter profile

After the exemplar is complete, extract what was actually useful:
- Which Biolink types were used
- Which CURIE prefixes were needed
- Example `graph add concept` invocations with full flags
- Recommended predicates for bioinformatics/genomics projects

Package as a reference doc (not code) — a "getting started with biomedical graphs" section in the knowledge-graph skill or a standalone reference file.

### Step 7: Close Phase 3 gate

Update `docs/plan.md`:
- Mark 3c and 3d deliverables as done
- Update Phase 3 progress snapshot
- Reference exemplar evidence location
- Update immediate next steps to focus on Phase 4b

## Scope Boundaries

**In scope:**
- Full project scaffolding with real research question
- 3-5 background topic docs + 3-5 paper summaries per topic
- Knowledge graph with ~30-50 entities, rich properties, CiTO predicates
- OpenAlex snapshot generation (real API call, committed to science repo)
- Snapshot import into project graph
- Full validation pass + archived evidence bundle
- Biomedical starter profile derived from actual usage
- Phase 3 gate closure

**Out of scope:**
- Ontology caching (`ontology cache` command) — deferred to Phase 4b
- PrimeKG-specific distiller — generic PyKEEN covers this use case
- Exhaustive literature review — enough for a solid graph, not a complete survey
- Any Phase 4 work (inquiry workflow, DAG export, pipelines)
- Autonomous loops

**Decisions:**
- Ontology caching deferred: not required by Phase 3 gate criteria, groundwork for future entity matching
- Separate repo for exemplar: keeps science plugin repo problem-agnostic; exemplar outputs archived as evidence only
- Infrastructure built exemplar-driven: OpenAlex snapshot and starter profile are built when the exemplar needs them, validated by real usage
