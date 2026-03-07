# Exemplar Evidence Bundle (Phases 3 & 4)

**Date:** 2026-03-07
**Exemplar project:** `~/d/3d-attention-bias/` (3D Structure-Aware Attention Bias for Nucleic Acid Foundation Models)

## Gate Criteria Demonstrated

| Criterion | Evidence File | Result |
|-----------|--------------|--------|
| Agent-construct knowledge graph from prose | `graph-stats.json` | 2,761 triples (35 concepts, 25 papers, 27 claims) |
| Import distilled snapshot | `graph-stats.json` | 1,684 OpenAlex triples imported |
| Run use-case queries with table/json output | `query-neighborhood.json`, `query-claims.json`, `query-coverage.json` | All queries return structured JSON |
| Detect changes via hybrid `graph diff` | `graph-diff.json` | Diff runs successfully |
| Pass `graph validate` | `graph-validate.json` | 4/4 checks pass |
| Pass `validate.sh` | `validate-sh.log` | PASSED with 2 warnings |

## Files

- `graph-stats.json` — Triple counts per named graph layer
- `graph-validate.json` — Structural validation (parseable TriG, provenance, acyclicity, orphans)
- `graph-diff.json` — Hybrid diff output
- `query-neighborhood.json` — 2-hop neighborhood around DNABERT-2
- `query-claims.json` — Claims mentioning "attention"
- `query-coverage.json` — Variable coverage status
- `validate-sh.log` — Full validate.sh output

## Phase 4 Gate (Causal Modeling)

**Date:** 2026-03-07

| Criterion | Evidence File | Result |
|-----------|--------------|--------|
| Causal inquiry created with type=causal | `causal-validate.json` | Inquiry `3d-attention-effect` validates (acyclicity, boundary reachability) |
| pgmpy scaffold export | `causal-export-pgmpy.py` | BayesianNetwork + CausalInference script with 5 variables, 5 edges |
| ChiRho/Pyro scaffold export | `causal-export-chirho.py` | Pyro model function + `do()` intervention handler |

### Files (Phase 4)

- `causal-validate.json` — Causal inquiry validation output (acyclicity + boundary reachability)
- `causal-export-pgmpy.py` — Generated pgmpy scaffold script
- `causal-export-chirho.py` — Generated ChiRho/Pyro scaffold script

## Warnings (Expected)

- 2 `[UNVERIFIED]` markers in research docs (normal for in-progress research)
- 5 `[NEEDS CITATION]` markers (flagged for future citation passes)
