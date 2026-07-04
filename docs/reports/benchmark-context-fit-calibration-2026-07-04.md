# Benchmark Context-Fit Calibration - 2026-07-04

## Commands

- `science benchmark tests --commons --exclude-fallback --state concrete --format json`
- `science benchmark test-triage --commons --format json`

## Projects

- `~/d/cancer/cancer-types/multiple-myeloma`
- `~/d/health/processes/post-acute-infection`
- `~/d/natural-systems`
- `~/d/cancer/data-sources/cbioportal`

## Concrete Non-Fallback Test Rows

| Project | rows | direct-fit | adjacent-fit | method-fit | blocked-fit | generic-fallback | out-of-context |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| multiple-myeloma | 226 | 74 | 13 | 77 | 52 | 0 | 10 |
| post-acute-infection | 9 | 3 | 0 | 5 | 1 | 0 | 0 |
| natural-systems | 4 | 0 | 0 | 3 | 1 | 0 | 0 |
| cbioportal | 15 | 5 | 3 | 7 | 0 | 0 | 0 |

## Full Triage Rows

| Project | rows | direct-fit | adjacent-fit | method-fit | blocked-fit | generic-fallback | out-of-context |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| multiple-myeloma | 1576 | 85 | 13 | 77 | 55 | 1334 | 12 |
| post-acute-infection | 219 | 6 | 0 | 5 | 2 | 206 | 0 |
| natural-systems | 481 | 0 | 0 | 3 | 1 | 477 | 0 |
| cbioportal | 183 | 10 | 3 | 7 | 2 | 158 | 3 |

## Decision

Context-fit is ready to merge: direct-fit rows remain plausible for
the active cancer/data-source projects, and natural-systems is not dominated
by direct-fit biology benchmark rows.
