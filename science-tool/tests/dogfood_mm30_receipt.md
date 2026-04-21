# MM30 Verdict Dogfood Receipt

Date: 2026-04-21
Worktree: `/mnt/ssd/Dropbox/science/.worktrees/verdict-parse-rollup-mvp/science-tool`

## Parse validation

Command pattern:

```bash
uv run science-tool verdict parse <doc> --registry /mnt/ssd/Dropbox/r/mm30/specs/claim-registry.yaml
```

Docs checked:

- `/mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-19-t221-literature-gene-lookups.md`
- `/mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-14-t197-gse155135-ezh2i-replication.md`
- `/mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-19-t234-hopfield-hamming-robustness.md`
- `/mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-18-t204-bulk-composition-beyond-pc-maturity-verdict.md`
- `/mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-12-t163-prolif-adjusted-tf-edges.md`
- `/mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-12-ribosome-regulator-screen-clr.md`
- `/mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-21-t099-skerget-transition-matrix.md`
- `/mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-21-t240-misund-phf19-trajectory.md`
- `/mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-21-t258-phf19-pathway-specificity.md`

Result:

- 9/9 atomic-decomposition docs parse cleanly
- `unresolved_claim_ids=0`
- `rule_disagrees_with_body: true` only for `t163`
- `t099_rule_derived_composite=[+]`
- `t240_rule_derived_composite=[~]`

## Claim rollup validation

Command:

```bash
uv run science-tool verdict rollup --scope claim --root /mnt/ssd/Dropbox/r/mm30/doc/interpretations --registry /mnt/ssd/Dropbox/r/mm30/specs/claim-registry.yaml --output json
```

Result:

- `scope=claim`
- `n_documents=9`
- `n_groups=37`
- Tallies are per-claim polarity tokens, not per-document composite
  tokens.
- Canonical groups checked:
  - `h2#strict-block-diagonal-transition-null`: `[-]=1`
  - `h4#c3-funnel-cross-cytogenetic-convergence-to-pr`
  - `t099#full-transition-matrix-single-patient-precision`: `[?]=1`
  - `t240#clonal-change-n-phf19-autonomous-ratchet`: `[?]=1`
  - `t240#phf19-log2fc-correlates-with-pi-change`: `[+]=1`
  - `t240#phf19-monotone-up-across-paired-cohort`: `[?]=1`

## Alias validation

Commands:

```bash
uv run science-tool verdict rollup --scope claim --root /mnt/ssd/Dropbox/r/mm30/doc/interpretations --registry /mnt/ssd/Dropbox/r/mm30/specs/claim-registry.yaml --output json > /tmp/mm30_scope_claim.json
uv run science-tool verdict rollup --by-claim --root /mnt/ssd/Dropbox/r/mm30/doc/interpretations --registry /mnt/ssd/Dropbox/r/mm30/specs/claim-registry.yaml --output json > /tmp/mm30_by_claim.json
cmp /tmp/mm30_scope_claim.json /tmp/mm30_by_claim.json
```

Result:

- `cmp exit=0`
- `sha256=48be93b60881e5e82752ef73a3b671fb95a27caff810ae74266b696a20ee61dd`
- `bytes=10556`

## Strict validation

Command:

```bash
uv run science-tool verdict rollup --scope claim --strict --root /mnt/ssd/Dropbox/r/mm30/doc/interpretations --registry /mnt/ssd/Dropbox/r/mm30/specs/claim-registry.yaml --output json
```

Result:

- `--strict exit=0`

## All-scope table validation

Command:

```bash
uv run science-tool verdict rollup --scope all --root /mnt/ssd/Dropbox/r/mm30/doc/interpretations --output table
```

Result:

```text
Group=all n=9 [+]=2 [-]=0 [~]=6 [?]=0 [⌀]=1
```

Tally sum: `2 + 0 + 6 + 0 + 1 = 9`.
