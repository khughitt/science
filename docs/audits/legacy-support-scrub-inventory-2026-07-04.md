# Legacy Support Scrub Inventory

Generated at: `2026-07-06T00:40:43Z`
Config path: `~/.config/science/config.yaml`

## Summary

| metric | count |
| --- | ---: |
| `registered_entries` | 23 |
| `unique_registered_paths` | 23 |
| `duplicate_registered_entries` | 0 |
| `shared_repository_entries` | 1 |
| `scanned_projects` | 22 |
| `skipped_registered_projects` | 1 |
| `unregistered_science_yaml` | 0 |
| `total_findings` | 8 |

## Surface Totals

| surface | findings |
| --- | ---: |
| `legacy_marker_alias` | 4 |
| `retired_edges_yaml` | 4 |

## Projects

| project | findings | surfaces |
| --- | ---: | --- |
| `~/d/3d-attention-bias` | 1 | `legacy_marker_alias`=1 |
| `~/d/cancer/cancer-types/breast` | 0 |  |
| `~/d/cancer/cancer-types/head-and-neck` | 0 |  |
| `~/d/cancer/cancer-types/multiple-myeloma` | 1 | `retired_edges_yaml`=1 |
| `~/d/cancer/cancer-types/ovarian` | 0 |  |
| `~/d/cancer/cancer-types/prostate` | 0 |  |
| `~/d/cancer/conditions/pre-cancer` | 0 |  |
| `~/d/cancer/data-sources/cbioportal` | 2 | `retired_edges_yaml`=2 |
| `~/d/cancer/mechanisms/evolution` | 0 |  |
| `~/d/cancer/meta` | 0 |  |
| `~/d/cancer/therapeutics` | 0 |  |
| `~/d/cats` | 0 |  |
| `~/d/health/comparisons/pan-disease` | 0 |  |
| `~/d/health/meta` | 0 |  |
| `~/d/health/processes/cycles` | 0 |  |
| `~/d/health/processes/immunity` | 0 |  |
| `~/d/health/processes/post-acute-infection` | 0 |  |
| `~/d/natural-systems` | 2 | `legacy_marker_alias`=2 |
| `~/d/protein-landscape` | 1 | `retired_edges_yaml`=1 |
| `~/d/science-commons` | 0 |  |
| `~/d/science/meta` | 0 |  |
| `~/d/seq-feats` | 1 | `legacy_marker_alias`=1 |

## Findings

| project | surface | path | detail |
| --- | --- | --- | --- |
| `~/d/3d-attention-bias` | `legacy_marker_alias` | `AGENTS.md` | [NEEDS CITATION] |
| `~/d/cancer/cancer-types/multiple-myeloma` | `retired_edges_yaml` | `tests/migration/fixtures/mini_patch.edges.yaml` | retired DAG edge file |
| `~/d/cancer/data-sources/cbioportal` | `retired_edges_yaml` | `doc/figures/dags/h02-cross-study-ranking-divergence.edges.yaml` | retired DAG edge file |
| `~/d/cancer/data-sources/cbioportal` | `retired_edges_yaml` | `doc/figures/dags/h08-agnostic-covariate-association.edges.yaml` | retired DAG edge file |
| `~/d/natural-systems` | `legacy_marker_alias` | `AGENTS.md` | [NEEDS CITATION] |
| `~/d/natural-systems` | `legacy_marker_alias` | `tasks/done/2026-05.md` | [NEEDS CITATION] |
| `~/d/protein-landscape` | `retired_edges_yaml` | `archive/dag-retired-edges/h01-multi-manifold-protein-universe.edges.yaml` | retired DAG edge file |
| `~/d/seq-feats` | `legacy_marker_alias` | `AGENTS.md` | [NEEDS CITATION] |

## Skipped Registered Projects

| project root | reason |
| --- | --- |
| `~/d/natural-systems/.worktrees/validation-strict-cleanup` | missing directory |

## Coverage Sweep

_No unregistered `science.yaml` files found in search roots._
