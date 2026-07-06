# Legacy Support Scrub Final Verification

Date: 2026-07-06
Branch: `refactor/legacy-scrub-final-verification`

## Inventory Gate

Final inventory report:

- Markdown: `docs/audits/legacy-support-scrub-final-inventory-2026-07-06.md`
- JSON: `docs/audits/legacy-support-scrub-final-inventory-2026-07-06.json`

Result:

- `registered_entries`: 23
- `unique_registered_paths`: 23
- `shared_repository_entries`: 1 (`~/d/science-commons`)
- `scanned_projects`: 22
- `skipped_registered_projects`: 1 (`~/d/natural-systems/.worktrees/validation-strict-cleanup`, missing directory)
- `unregistered_science_yaml`: 0
- `total_findings`: 0

The scanner reported no findings for the retired legacy surfaces.

## Search Triage

Active toolkit scan covered:

- `science/src`
- `science/tests`
- `commands`
- `templates`
- `references`
- `codex-skills`
- `docs/user-guide`
- `docs/conventions`

Classified hits:

- Negative guidance for `article:<bibkey>` remains in active docs to steer users to `paper:<bibkey>`.
- `_SCAN_DIRS = ("doc", "entities")` remains in prose/ref/marker scanners; it scans current prose plus current entity owner files and no longer includes `specs`.
- `.edges.yaml`, retired migration commands, marker aliases, and aggregate manifests remain only in rejection paths, retired-command tests, inventory fixtures, or "do not create" guidance.
- Current structured-source code may mention aggregate manifests as the thing it replaced; it does not load retired aggregate manifests.

Registered-project broad `rg` triage was noisy by design. Hits were historical plan snippets, script/test fixtures, generated reports, current datapackage `profiles:` keys, current task/frontmatter `parent:` fields outside `science.yaml`, live `article` records, or unreadable `pgdata` directories. The structured inventory is the authoritative data gate and reported zero findings.

## Downstream Validation

Command shape:

```bash
env PYTHONPATH=science/src:science/model/src SCIENCE_TEST_TMPDIR=/tmp/science-pytest-basetemp \
  uv run --project science --frozen science validate --profile commit --format json --project-root <project>
```

Summary with a 60-second per-project timeout:

- OK: 12
- Failed: 9
- Timed out: 1
- Total checked: 22

Passing projects:

- `~/d/cancer/data-sources/cbioportal`
- `~/d/cancer/mechanisms/evolution`
- `~/d/cancer/meta`
- `~/d/cancer/therapeutics`
- `~/d/cats`
- `~/d/health/comparisons/pan-disease`
- `~/d/health/meta`
- `~/d/health/processes/cycles`
- `~/d/health/processes/immunity`
- `~/d/health/processes/post-acute-infection`
- `~/d/natural-systems`
- `~/d/seq-feats`

Non-passing projects:

| Project | Result | Classification |
| --- | --- | --- |
| `~/d/3d-attention-bias` | 8 errors, 874 warnings | Existing project validation findings; no legacy inventory findings. |
| `~/d/cancer/cancer-types/breast` | 1 error, 3 warnings | Broken namespace ref; no legacy inventory findings. |
| `~/d/cancer/cancer-types/head-and-neck` | 1 error, 3 warnings | Broken namespace ref; no legacy inventory findings. |
| `~/d/cancer/cancer-types/ovarian` | 1 error, 2 warnings | Broken namespace ref; no legacy inventory findings. |
| `~/d/cancer/cancer-types/prostate` | 1 error, 6 warnings | Broken namespace ref; no legacy inventory findings. |
| `~/d/cancer/conditions/pre-cancer` | 5 errors, 7 warnings | Existing project/tooling validation findings; no legacy inventory findings. |
| `~/d/cancer/cancer-types/multiple-myeloma` | timeout | Large project did not complete within 60 seconds; no legacy inventory findings. |
| `~/d/protein-landscape` | 7 errors, 2829 warnings | Permission/tooling validation issue around `.env`; no legacy inventory findings. |
| `~/d/science/meta` | traceback | Local validation hook imports missing `t034_validator`; no legacy inventory findings. |
| `~/d/science-commons` | 12 errors, 2 warnings | Shared repository is not a normal uv project; no legacy inventory findings. |

`science graph materialize` is not a current CLI command. The current materialization command is `science graph build`, which writes graph artifacts, so it was not run across downstream repositories during this read-only verification pass.

## Toolkit Verification

Passed:

```bash
cd science && env PYTHONPATH=src:model/src SCIENCE_TEST_TMPDIR=/tmp/science-pytest-basetemp uv run --frozen pytest --basetemp=/tmp/science-pytest-basetemp-final-verification-science -q
cd science/model && env SCIENCE_TEST_TMPDIR=/tmp/science-pytest-basetemp uv run --frozen pytest --basetemp=/tmp/science-pytest-basetemp-final-verification-model -q
cd science/qa && env SCIENCE_TEST_TMPDIR=/tmp/science-pytest-basetemp uv run --frozen pytest --basetemp=/tmp/science-pytest-basetemp-final-verification-qa -q
```

Known unrelated failures:

```bash
cd science && uv run --frozen ruff check
```

Fails with 45 existing lint errors in annotation, belief, proposition synthesis, statement extraction, text-source adapter, and kind-map tests.

```bash
cd science && uv run --frozen pyright
```

Fails with 45 existing type errors in annotation reconciliation, benchmark CLI formatting, dataset catalog/identity, feedback, explore ideas, and labnote export code.

These failures are outside the final legacy-support scrub changes, which add audit reports and plan/audit status updates only.
