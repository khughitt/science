# Convergence Phase 6 — promote.py decomposition

Branch: design/convergence-phase6   Base: d2fc4d13
Plan: docs/plans/2026-07-11-convergence-phase6-promote-decomposition-plan.md

- [x] Task 1: promote_types.py (shared vocabulary — MUST land first)
- [x] Task 2: git.py
- [x] Task 3: promote_render.py
- [ ] Task 4: promote_dataset.py
- [ ] Task 5: prompt_resolve -> cli.py (evicts click)
- [ ] Task 6: guard (test_commons_domain_purity.py)
Task 1: complete (promote_types.py 313 lines, promote.py 3490->3226, 8017 passed, snapshot green)
NOTE: main had a RED snapshot gate (stale text_default.txt, 58 vs 59 checks, from 5c2b44f1). Fixed on main as 04eec7c0 and merged in.
Task 2: complete (git.py 214 lines, promote.py 3226->3038, 8017 passed)
NOTE: main ALSO had a date time-bomb (4 feedback tests, 14-day telemetry window vs pinned 2026-06-27 fixtures). Fixed on main as bd6b8850 and merged in.
Task 3: complete (promote_render.py 308 lines, promote.py 3038->2760, 8017 passed, golden green)
