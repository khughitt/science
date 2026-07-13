# Git-Sourced Science Conversion Receipt

**Date:** 2026-07-13
**Toolkit publication:** `29998019ee1e3abc44f05a976c8a6911c5c82a96`, verified reachable from `origin/main` before consumer conversion.
**Registry:** `~/.config/science/config.yaml`

All 20 persistent external consumers use the canonical public Git source with
the exact toolkit revision pinned in `uv.lock`. In every consumer,
`uv sync --frozen` and `uv run --frozen science --version` succeeded without an
editable overlay; the installed version was `science 0.3.0`. Every selected SHA
was parsed from the lock and verified as an ancestor of toolkit `origin/main`.

The full validator also ran in every consumer. Its repository-content result is
recorded separately below: a nonzero content result does not indicate a Git
source, environment, or worktree failure.

| Project | Classification | Migration checks | Full validation |
|---|---|---|---|
| `~/d/3d-attention-bias` | external consumer | passed | existing content failures: 26 errors, 418 warnings |
| `~/d/cats` | external consumer; shallow nested-worktree smoke | passed | passed |
| `~/d/protein-landscape` | external consumer | passed | existing content failures: 18 errors, 64 warnings |
| `~/d/natural-systems` | external consumer; isolated nested-worktree conversion | passed | existing content failures: 202 errors, 149 warnings |
| `~/d/cancer/cancer-types/multiple-myeloma` | external consumer; deep nested-worktree smoke | passed | 184 pre-existing status-vocabulary errors, reproduced with Science 0.2.0 |
| `~/d/cancer/meta` | external consumer | passed | existing content failures: 1 error, 24 warnings |
| `~/d/cancer/mechanisms/evolution` | external consumer | passed | existing content failures: 11 errors, 59 warnings |
| `~/d/cancer/conditions/pre-cancer` | external consumer | passed | existing content failures: 5 errors, 8 warnings |
| `~/d/cancer/data-sources/cbioportal` | external consumer | passed | existing content failures: 62 errors, 48 warnings |
| `~/d/seq-feats` | external consumer | passed | existing content failures: 44 errors, 2702 warnings |
| `~/d/health/meta` | external consumer | passed | existing content failures: 13 errors, 142 warnings |
| `~/d/health/comparisons/pan-disease` | external consumer | passed | existing content failures: 22 errors, 104 warnings |
| `~/d/health/processes/cycles` | external consumer | passed | existing content failures: 17 errors, 138 warnings |
| `~/d/cancer/cancer-types/ovarian` | external consumer | passed | existing content failures: 1 error, 2 warnings |
| `~/d/cancer/cancer-types/head-and-neck` | external consumer | passed | existing content failures: 1 error, 3 warnings |
| `~/d/cancer/cancer-types/prostate` | external consumer | passed | existing content failures: 1 error, 6 warnings |
| `~/d/cancer/cancer-types/breast` | external consumer | passed | existing content failures: 1 error, 3 warnings |
| `~/d/health/processes/immunity` | external consumer | passed | passed |
| `~/d/health/processes/post-acute-infection` | external consumer | passed | existing content failures: 18 errors, 18 warnings |
| `~/d/cancer/therapeutics` | external consumer | passed | existing content failures: 20 errors, 31 warnings |
| `~/d/science/meta` | excluded: same-repository editable source | not converted | not applicable |
| `~/d/science-commons` | excluded: no root Python manifest | not converted | not applicable |
| `/tmp/tmpe4t7vbzt` | transient stale registry entry | excluded as nonpersistent | not applicable |
| `/tmp/tmpgwijrm7p` | transient stale registry entry | excluded as nonpersistent | not applicable |

The representative shallow and deep nested worktrees both completed frozen sync
and version checks without main-checkout routing or sandbox exceptions. The
shallow `cats` worktree passed full validation. The deep multiple-myeloma
worktree reached the validator and reproduced the main checkout's 184 existing
status-vocabulary errors. `natural-systems` was additionally converted and
validated inside a nested worktree while unrelated main-checkout changes
remained untouched.

The dependency migration commits for `3d-attention-bias` and `seq-feats` were
made on their pre-existing `refactor/aggregate-manifest-retirement` branches;
all other consumer commits were made on their active `main` branches.
