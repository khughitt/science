# Promote test fixtures

Synthetic two-project corpus exercising the four candidate shapes promote
must handle. Used by `test_commons_promote_apply.py` / `test_commons_cli_promote.py`
as a stable on-disk read-only fixture; tests that need to mutate build their
own corpus under `tmp_path`.

| Bibkey       | Shape                                       | Source projects |
|--------------|---------------------------------------------|-----------------|
| Adams2025    | Single-instance, well-formed                | proj-alpha      |
| Bravo2024    | Single-instance, well-formed                | proj-beta       |
| Huh2024      | Multi-instance, no conflicts (auto-union)   | both            |
| Dang2023     | Multi-instance, real `year` conflict        | both            |

See docs/plans/2026-05-15-commons-promote-papers-design.md §8.
