# KG Layering Verification

Date: 2026-03-13

Repos verified:
- `science-model`
- `science-tool`
- `science-web`
- `seq-feats`

Commands run:

```bash
cd /mnt/ssd/Dropbox/science/science-model
TMPDIR=/mnt/ssd/Dropbox/science/.tmp UV_CACHE_DIR=/tmp/uv-cache uv run --frozen python -m pytest -q
TMPDIR=/mnt/ssd/Dropbox/science/.tmp UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright
TMPDIR=/mnt/ssd/Dropbox/science/.tmp UV_CACHE_DIR=/tmp/uv-cache uv run --frozen ruff check .

cd /mnt/ssd/Dropbox/science
TMPDIR=/mnt/ssd/Dropbox/science/.tmp UV_CACHE_DIR=/tmp/uv-cache uv run --project science-tool --frozen python -m pytest science-tool/tests/test_graph_materialize.py science-tool/tests/test_graph_migrate.py science-tool/tests/test_graph_cli.py science-tool/tests/test_inquiry.py -q
TMPDIR=/mnt/ssd/Dropbox/science/.tmp UV_CACHE_DIR=/tmp/uv-cache uv run --project science-tool --frozen python -m pytest science-tool/tests/test_graph_materialize.py -k across_processes -q
TMPDIR=/mnt/ssd/Dropbox/science/.tmp UV_CACHE_DIR=/tmp/uv-cache uv run --project science-tool --frozen ruff check science-tool/src/science_tool/graph science-tool/tests/test_graph_migrate.py science-tool/tests/test_graph_materialize.py
TMPDIR=/mnt/ssd/Dropbox/science/.tmp UV_CACHE_DIR=/tmp/uv-cache uv run --project science-tool --frozen python -m pytest -q

cd /home/keith/d/science-web
uv run --frozen pytest -q
uv run --frozen pyright
npm run build

cd /mnt/ssd/Dropbox/seq-feats
TMPDIR=/mnt/ssd/Dropbox/science/.tmp UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool --frozen science-tool graph build --project-root .
TMPDIR=/mnt/ssd/Dropbox/science/.tmp UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool --frozen science-tool graph build --project-root .
sha256sum knowledge/graph.trig
TMPDIR=/mnt/ssd/Dropbox/science/.tmp UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool --frozen science-tool graph audit --project-root . --format json
TMPDIR=/mnt/ssd/Dropbox/science/.tmp UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool --frozen science-tool graph validate --format json --path knowledge/graph.trig
TMPDIR=/mnt/ssd/Dropbox/science/.tmp UV_CACHE_DIR=/tmp/uv-cache ./validate.sh --verbose
```

Key outcomes:
- `science-model` package-scoped tests, `pyright`, and `ruff check` all passed.
- `science-tool` graph-focused test suite passed, including the new cross-process determinism regression test.
- `science-tool` full-suite collection still fails in `science-tool/tests/test_datasets.py` because `httpx` is not installed. This was a pre-existing environment/dependency gap, not a regression from KG layering work.
- `science-web` backend tests, typecheck, and frontend build passed earlier in this implementation run. The remaining work after that point was limited to `science-tool`, `seq-feats`, and shared docs.
- `seq-feats` now materializes a deterministic `knowledge/graph.trig`; two consecutive final builds produced the same SHA-256 digest: `d2f7296c60ba37aaebd10ed062594efbe435bfbfc5b0396f29e9925f8dfb0251`.
- `seq-feats` graph audit returned zero unresolved canonical references.
- `seq-feats` graph validation passed all checks: parseability, provenance completeness, causal acyclicity, and orphaned-node detection.
- `seq-feats` `validate.sh --verbose` now auto-discovers `../science/science-tool`, reports all frontmatter cross-references valid, and passes with warnings only.

Delivered behavior:
- Canonical IDs are now shared across project docs, tasks, RDF materialization, and the web graph consumer.
- Tasks are first-class graph entities in the materialized KG.
- Layer/profile selection is explicit through `core`, curated profiles such as `bio`, and `project_specific`.
- Manual curation flows through structured upstream sources in `knowledge/sources/project_specific/` rather than direct editing of `knowledge/graph.trig`.

Residual risks:
- The remaining `seq-feats` warnings are now content-quality warnings rather than KG-identity drift: missing citations, `[UNVERIFIED]` markers, and missing template sections in a handful of notes/meta docs.
- The package-root `pyright` and repo-root `ruff check .` workflows outside package directories still surface unrelated pre-existing issues. Verification should continue using package-scoped commands until those broader repo hygiene issues are cleaned up.
