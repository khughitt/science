# Final whole-branch review fix report

Status: **DONE**

## Commits

- `74e424b5 fix(findings): close final review trust gaps`
- `04373c70 fix(findings): close reviewer fail-open edges`

## Changed files

- `docs/plans/2026-07-27-finding-convergence-design.md`
- `docs/plans/2026-07-27-finding-convergence-plan-1-contract.md`
- `science/model/src/science_model/audit/report.py`
- `science/model/src/science_model/audit/subjects.py`
- `science/model/tests/test_audit_evidence.py`
- `science/model/tests/test_audit_record.py`
- `science/model/tests/test_audit_subjects.py`
- `science/src/science_tool/findings/cli.py`
- `science/src/science_tool/findings/ingest.py`
- `science/src/science_tool/findings/paths.py`
- `science/src/science_tool/findings/storage.py`
- `science/src/science_tool/graph/sources.py`
- `science/tests/test_findings_cli.py`
- `science/tests/test_findings_ingest.py`
- `science/tests/test_findings_isolation.py`
- `science/tests/test_findings_paths.py`
- `science/tests/test_findings_storage.py`

## API and contract decisions

- Added frozen, extra-forbidding `IngestionProvenance` with trusted
  `ingestion_ref`, `generated_at`, and `producer_ids`.
- Added frozen, extra-forbidding `IngestionContext` with the trusted
  `canonical_entity_ids`.
- The public ingestion signature is:

  ```python
  ingest_report(
      project_root: Path,
      report: AuditReport,
      registry: FindingRegistry,
      *,
      provenance: IngestionProvenance,
      context: IngestionContext,
      actor: str = "ingest",
  ) -> IngestOutcome
  ```

- There is no report-derived fallback. Ingestion compares the report ref, exact
  timestamp spelling, and
  `meta.producers_run ∪ {item.producer_id for item in unwired}` exactly with
  trusted provenance before opening the case store. Trusted values feed
  occurrences and occurrence keys.
- `science findings ingest` requires `--attest-ingestion-ref`,
  `--attest-generated-at`, and one-or-more `--attest-producer-id` options. It
  constructs entity context from default strict
  `load_project_sources(project_root).entities`. Graph, commons, malformed YAML,
  and non-mapping configuration failures are exit-2, zero-write refusals.
- Genesis remains append-only creation history. Canonical occurrence sorting
  never rewrites the original `None -> proposed` transition.
- `CaseStore.names()` ignores only the exact lock leaf and exact writer temp-name
  shape. Every Markdown leaf is parsed as a claimed case; every other leaf is
  refused rather than silently skipped. The aggregate store is preloaded before
  any write classification.
- Project paths reject NUL at the model boundary. `resolve_inside()` walks from
  one held root descriptor with `O_DIRECTORY|O_NOFOLLOW`, judges the leaf with
  descriptor-relative `lstat`, accepts a genuinely absent leaf, and refuses
  symlinks and concurrent pathname swaps.
- Persisted occurrence and review hashes have literal independent golden
  vectors.

## RED evidence

- Introducing `IngestionProvenance`/`IngestionContext` tests initially failed at
  collection because the trusted API did not exist.
- NUL subject/evidence tests failed because NUL was accepted; descriptor race
  tests failed because path components and the root were re-resolved.
- Renamed `notes.md`/`.hidden.md` storage, list, and ingestion tests failed
  because hidden or noncanonical leaves were skipped.
- Opposite-time arrival assertions exposed genesis rewriting.
- Malformed project YAML initially escaped Click as `ParserError` with exit 1.
- The final reviewer regressions were run with:

  ```text
  cd science
  uv run --frozen pytest tests/test_findings_cli.py::test_ingest_cli_refuses_non_mapping_graph_configuration tests/test_findings_storage.py::test_load_cases_refuses_every_non_operational_leaf -q
  ```

  Result: 5 failures. List/scalar `science.yaml` roots escaped as
  `AttributeError`/`TypeError`, and `notes.txt`, `backup`, and `.hidden` were
  silently ignored.

## GREEN verification

No full package suite was run, as required by the brief. Suites were serial.

```text
cd science/model
uv run --frozen pytest tests/test_audit_record.py tests/test_audit_subjects.py tests/test_audit_evidence.py -q
```

Result: exit 0, 95 tests passed.

```text
cd science
uv run --frozen pytest tests/test_findings_ingest.py tests/test_findings_storage.py tests/test_findings_cli.py tests/test_findings_isolation.py tests/test_findings_paths.py -q
```

Result: exit 0, 165 tests passed; only six pre-existing rdflib deprecation
warnings.

```text
cd science
uv run --frozen pytest tests/test_findings_cli.py::test_ingest_cli_refuses_non_mapping_graph_configuration tests/test_findings_storage.py::test_load_cases_refuses_every_non_operational_leaf tests/test_findings_storage.py::test_load_cases_refuses_case_shaped_noncanonical_extensions -q
```

Result: exit 0, 7 tests passed.

Independent hash oracles:

```text
printf 'science.occurrence.v1\n%s\0%s\0%s' \
  'dataset_anomalies' 'run:résumé-β' \
  'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' | sha256sum
```

Result:
`c89b7da3f53191cb6c108935d8fcd9d460e7401ab8498ef52aed09a2ebe8d2b4`.

```text
printf 'science.review.v1\n%s\0%s\0%s\0%s\0%s' \
  'agent' 'curation-sweep' 'grounding-β' 'run:résumé' \
  'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' | sha256sum
```

Result:
`dbe4266d101b03b1f75d9a64cf7c9856079ff19e892f1a669630081e85dc17db`.

Static checks:

```text
cd science
uv run --frozen ruff check
```

Result: `All checks passed!`

```text
cd science
uv run --frozen pyright
```

Result: `0 errors, 0 warnings, 0 informations`.

```text
git diff --check
```

Result: exit 0, no output.

## Documentation

The design is revision 7 and now states the trusted provenance/context boundary,
graph-arbitrated entity universe, append-only genesis ruling, exact case-store
leaf policy, descriptor path judgment, NUL refusal, and persisted hash goldens.
Plan 1 mirrors the final public API and removes stale scanner, provenance,
genesis-rewrite, and case-leaf snippets.

## Self-review

The first independent whole-branch review found no Critical findings and two
Important fail-open edges: non-mapping `science.yaml` roots and arbitrary
non-operational case-store leaves. Both received RED tests and fixes in
`04373c70`; the nested final review is clean.

Open concerns: none. Full suites remain for the top-level agent, per the brief.
