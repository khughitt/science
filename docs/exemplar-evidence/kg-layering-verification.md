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

Follow-up verification on `/home/keith/d/seq-feats` after landing the migration CLI:

```bash
cd /home/keith/d/seq-feats
UV_CACHE_DIR=/tmp/uv-cache uv run --project /home/keith/d/science/science-tool science-tool graph migrate --project-root /home/keith/d/seq-feats --format json
UV_CACHE_DIR=/tmp/uv-cache uv run --project /home/keith/d/science/science-tool science-tool graph build --project-root /home/keith/d/seq-feats
UV_CACHE_DIR=/tmp/uv-cache uv run --project /home/keith/d/science/science-tool science-tool graph validate --format json --path /home/keith/d/seq-feats/knowledge/graph.trig
bash validate.sh --verbose
```

- `seq-feats` migration was already clean under the new workflow: `rewritten_file_count = 0` and `unresolved_reference_count = 0`.
- The refreshed migration audit report was written to `knowledge/reports/kg-migration-audit.json`.
- The rebuilt `knowledge/graph.trig` still passed all structural validation checks.
- Running `validate.sh --verbose` from the project root passed with warnings only, confirming the project works end-to-end with the migrated `science-tool graph migrate` / `graph build` flow.

Delivered behavior:
- Canonical IDs are now shared across project docs, tasks, RDF materialization, and the web graph consumer.
- Tasks are first-class graph entities in the materialized KG.
- Layer/profile selection is explicit through `core`, curated profiles such as `bio`, and `project_specific`.
- Manual curation flows through structured upstream sources in `knowledge/sources/project_specific/` rather than direct editing of `knowledge/graph.trig`.

Residual risks:
- The remaining `seq-feats` warnings are now content-quality warnings rather than KG-identity drift: missing citations, `[UNVERIFIED]` markers, and missing template sections in a handful of notes/meta docs.
- The package-root `pyright` and repo-root `ruff check .` workflows outside package directories still surface unrelated pre-existing issues. Verification should continue using package-scoped commands until those broader repo hygiene issues are cleaned up.

Follow-up assessment on `/home/keith/d/mindful/natural-systems-guide`:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --project /mnt/ssd/Dropbox/science/science-tool science-tool graph audit --project-root /home/keith/d/mindful/natural-systems-guide --format json

tmpdir=$(mktemp -d /tmp/nsg-kg-check.XXXXXX)
cp -a /home/keith/d/mindful/natural-systems-guide/. "$tmpdir"
UV_CACHE_DIR=/tmp/uv-cache uv run --project /mnt/ssd/Dropbox/science/science-tool science-tool graph build --project-root "$tmpdir"
UV_CACHE_DIR=/tmp/uv-cache uv run --project /mnt/ssd/Dropbox/science/science-tool science-tool graph validate --format json --path "$tmpdir/knowledge/graph.trig"
```

- `science-tool` now materializes authored `knowledge/sources/<local-profile>/relations.yaml` entries, including internal project edges such as `cito:discusses` and external-term links from bare `ontology_terms` tokens.
- `natural-systems-guide` now audits cleanly with its question/task sources plus structured project-local paper, ontology, and community-layer relation data.
- A temporary canonical rebuild succeeded and passed `graph validate`, which confirms the project can be rebuilt without the old `build-community-layer.ts`.
- The project is still not fully migrated to the canonical layered model. Comparing the checked-in graph to the temporary canonical rebuild shows the remaining gap is the old model layer: current `knowledge/graph.trig` has `247` `sci:Model` nodes and `104` `sci:CanonicalParameter` nodes, while the canonical rebuild currently has `0` of each.
- Current vs temporary rebuild counts: current graph `4493` knowledge-layer triples, rebuilt graph `601`; papers `11` vs `12`; questions `29` vs `29`; tasks `35` vs `35`.
- Conclusion: `natural-systems-guide` is now clean on IDs and build mechanics, and its literature/community layer is migrated, but it still needs canonical source coverage for model/parameter content before the repo can drop `knowledge/scripts/build-model-layer.ts` and fully adopt `science-tool graph build` for the checked-in graph.

Follow-up implementation on `/home/keith/d/mindful/natural-systems-guide` after adding typed model-layer source contracts:

```bash
cd /home/keith/d/mindful/natural-systems-guide
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/export_kg_model_sources.py
UV_CACHE_DIR=/tmp/uv-cache uv run --project /mnt/ssd/Dropbox/science/science-tool science-tool graph audit --project-root /home/keith/d/mindful/natural-systems-guide --format json
UV_CACHE_DIR=/tmp/uv-cache uv run --project /mnt/ssd/Dropbox/science/science-tool science-tool graph build --project-root /home/keith/d/mindful/natural-systems-guide
UV_CACHE_DIR=/tmp/uv-cache uv run --project /mnt/ssd/Dropbox/science/science-tool science-tool graph validate --format json --path /home/keith/d/mindful/natural-systems-guide/knowledge/graph.trig
bash validate.sh --verbose
```

- The project-local exporter now generates canonical `models.yaml`, `parameters.yaml`, and `bindings.yaml` from the existing app-internal registry sources.
- `graph audit` returned zero unresolved canonical references against the full model-layer source set.
- `graph build` succeeded on the real repo, and `graph validate` passed all four checks.
- `validate.sh --verbose` passed with warnings only and reported `graph-prose sync: all inputs up to date`.
- The rebuilt graph now preserves the expected model-layer coverage: `247` `sci:Model` nodes, `104` `sci:CanonicalParameter` nodes, `67` provenance-layer `sci:ParameterBinding` nodes, `29` questions, `35` tasks, and `12` papers.
- This closes the main `natural-systems-guide` migration blocker: the checked-in graph can now be rebuilt from canonical source files without relying on the old model/community layer builders on the critical path.

## Addendum (2026-03-14)

Follow-up verification for Task 6C (`science-web` model-layer consumer contract) and Task 7 docs/validation alignment:

```bash
cd /mnt/ssd/Dropbox/science/science-model
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest -q
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen ruff check .

cd /mnt/ssd/Dropbox/science/science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest -q
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen ruff check .

cd /mnt/ssd/Dropbox/science-web
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest -q
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright
cd frontend && npm run build

cd /mnt/ssd/Dropbox/seq-feats
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph build --project-root .
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph audit --project-root . --format json
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph validate --format json --path knowledge/graph.trig
bash validate.sh --verbose

cd /mnt/ssd/Dropbox/mindful/natural-systems-guide
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../../science/science-tool science-tool graph audit --project-root . --format json
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../../science/science-tool science-tool graph build --project-root .
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../../science/science-tool science-tool graph validate --format json --path knowledge/graph.trig

cd /mnt/ssd/Dropbox/science
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science-web python - <<'PY'
from pathlib import Path
from backend.graph import load_graph
for path in [Path("../seq-feats/knowledge/graph.trig"), Path("../mindful/natural-systems-guide/knowledge/graph.trig")]:
    data = load_graph(path, lod=1.0)
    print(path, len(data.nodes), len(data.edges), sorted({node.type for node in data.nodes})[:12])
PY
```

Observed outcomes:

- `science-web` checks passed after Task 6C implementation:
  - `pytest -q`: pass
  - `pyright`: `0 errors`
  - frontend build: pass
- Runtime graph load check confirms no regression for `seq-feats` and explicit model-layer coverage for `natural-systems-guide`:
  - `seq-feats`: `163` nodes, `246` edges, includes `Task`, `Question`, `Hypothesis` families
  - `natural-systems-guide`: `568` nodes, `1088` edges, includes `Model`, `CanonicalParameter`, `ParameterBinding`
- `seq-feats` verification passed:
  - `graph build` succeeded
  - `graph audit` rows were empty (`[]`)
  - `graph validate` returned pass for all checks
  - `validate.sh --verbose` passed with warnings only
- `natural-systems-guide` verification passed:
  - `graph audit` rows were empty (`[]`)
  - `graph build` succeeded
  - `graph validate` returned pass for all checks
- Task 7 doc alignment is now reflected in command docs and README wording:
  - canonical source + re-materialization workflow language is consistent
  - direct `graph.trig` authoring language was removed from the remaining stale README section

Environment constraints observed in this run:

- `science-model` and `science-tool` `uv run --frozen ruff check .` failed because `ruff` is not installed in the current runtime (`Failed to spawn: ruff`).
- `science-tool` full `pytest -q` and `pyright` remain blocked by pre-existing dependency/type issues (for example unresolved `httpx` import in dataset modules).

## Addendum (2026-03-14, verification refresh)

Commands run:

```bash
cd /mnt/ssd/Dropbox/science/science-model
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen ruff check .

cd /mnt/ssd/Dropbox/science/science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen ruff check .

cd /mnt/ssd/Dropbox/science-web
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright
cd frontend && npm run build

cd /mnt/ssd/Dropbox/seq-feats
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph build --project-root .
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph audit --project-root . --format json
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph validate --format json --path knowledge/graph.trig
sha256sum knowledge/graph.trig
bash validate.sh --verbose

cd /mnt/ssd/Dropbox/mindful/natural-systems-guide
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../../science/science-tool science-tool graph audit --project-root . --format json
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../../science/science-tool science-tool graph build --project-root .
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../../science/science-tool science-tool graph validate --format json --path knowledge/graph.trig

cd /mnt/ssd/Dropbox/science
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science-web python - <<'PY'
from pathlib import Path
from backend.graph import load_graph
for path in [Path("../seq-feats/knowledge/graph.trig"), Path("../mindful/natural-systems-guide/knowledge/graph.trig")]:
    data = load_graph(path, lod=1.0)
    print(path, len(data.nodes), len(data.edges), sorted({node.type for node in data.nodes})[:12])
PY
```

Observed outcomes:

- `science-model`: `pytest` passed (`23 passed`), `pyright` passed (`0 errors`).
- `science-model`: `ruff check .` blocked by environment (`Failed to spawn: ruff`).
- `science-tool`: full `pytest` still blocked during collection by pre-existing missing dependency (`ModuleNotFoundError: No module named 'httpx'` in dataset tests).
- `science-tool`: `pyright` still reports pre-existing dependency/type issues (`httpx`, `pykeen`, `pgmpy`, `marimo/altair/polars`, and existing `graph/store.py` typing issues). The earlier migration-related `cli.py`/`migrate.py` regressions are no longer present.
- `science-tool`: `ruff check .` blocked by environment (`Failed to spawn: ruff`).
- `science-web`: `pytest` passed (`42 passed`), `pyright` passed (`0 errors`), frontend build passed.
- `seq-feats`: `graph build` succeeded, `graph audit --format json` returned `{"rows": []}`, `graph validate` passed all checks, and `validate.sh --verbose` passed with warnings only.
- `seq-feats`: deterministic output hash in this refresh run was `733830f7990ecc81c0db8defcca6a2bffe98e797df5d1f45982a7b55cc9982f0`.
- `natural-systems-guide`: `graph audit` returned `{"rows": []}`, `graph build` succeeded, and `graph validate` passed all checks.
- Runtime graph load check still confirms expected consumer coverage:
  - `../seq-feats/knowledge/graph.trig`: `163` nodes, `246` edges, includes `Task`/`Question`/`Hypothesis` families.
  - `../mindful/natural-systems-guide/knowledge/graph.trig`: `568` nodes, `1088` edges, includes `Model`, `CanonicalParameter`, and `ParameterBinding`.
