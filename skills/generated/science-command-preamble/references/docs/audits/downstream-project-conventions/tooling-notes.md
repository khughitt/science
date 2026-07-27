# Tooling Notes — v0 Inventory Gaps

Gaps and limitations noticed while building / running `scripts/audit_downstream_project_inventory.py`. One bullet per gap. Each entry records what's missing, where it would matter, and a one-line proposed fix. Keep terse.

## v0 build (2026-04-25)

- **Canonical `validate.sh` lives at `meta/validate.sh`, not `templates/research/validate.sh`.** The plan's wording suggests a `templates/research/` comparator, but only `meta/validate.sh` exists today. Matters for any auditor expecting that path. Fix: either populate `templates/research/validate.sh` from `meta/` or update the plan to point at `meta/validate.sh`.

- **No top-level `pyproject.toml` in the Science repo.** PEP 723 inline metadata makes `uv run scripts/audit_downstream_project_inventory.py …` work, but the literal command `uv run python scripts/…` from the repo root fails because no project venv is active. Matters for anyone copy-pasting the plan's command. Fix: drop `python` from the documented invocation, or ship a minimal repo-root `pyproject.toml` for one-off scripts.

- **TOML-frontmatter detection is heuristic.** Files using `+++ … +++` are recorded as `frontmatter: unparsed`, but blocks using non-standard fences (e.g. `<!-- yaml -->` Hugo-style or RST directives) are silently skipped. Matters if a downstream project later adopts MDX/RST. Fix: extend `split_frontmatter` to recognize at least `+++` (already done) and explicit Hugo MDX `<!-- yaml --> … <!-- /yaml -->` blocks.

- **YAML templates with `{{...}}` placeholders register as parse errors.** `mm30/templates/gene-note.md` correctly surfaces as a parse error today, but template files are not really drift. Matters for projects that ship many template scaffolds. Fix: skip files under any tracked `templates/` directory by default (configurable), or detect `{{` in the frontmatter block and downgrade to `frontmatter: template-placeholder`. **Resolved 2026-04-25:** any path component named `templates` is now skipped from frontmatter / entity / observed-value accounting; `template_files_skipped` records the count.

- **`data_sources` shape inspection is shallow.** v0 records only `entry_kinds` (string vs object) and aggregate object-key counts. Matters when characterising how downstream projects describe protected/public data. Fix: record per-entry `(name, type, has_local_path, has_status)` tuples so Phase 2 can sample without re-reading `science.yaml`.

- **No per-file SHA list for entity files.** The inventory currently captures aggregate counts and per-id paths, but not content hashes. Matters for diffing two SHAs of the same project (e.g. before/after a Phase 2 sweep). Fix: optional `--include-file-hashes` flag that adds `sha256` per scanned markdown file, off by default to keep size in check.

- **Entity id detection only looks at frontmatter `id:` keys.** Some downstream files may use `task_id`, `hypothesis_id`, or naked filename-based ids (e.g. `q61-variational-as-annotation.md`). Matters for duplicate detection across naming styles. Fix: add a configurable list of id-equivalent fields and optionally derive a synthetic id from the filename stem.

- **`.audit-ignore` glob support is conservative.** v0 supports plain globs, `prefix/**`, and `prefix/`. Negation patterns (`!keep.md`) are not supported. Matters when projects want to ignore a directory but keep one file. Fix: pull in `pathspec` (gitignore-style) for full pattern support; current behaviour is documented as a subset.

- **Embedded-metadata heuristic is purely lexical.** Detects extra `---` blocks and runs of `key: value` lines after line 50. False positives expected on long markdown tables and reference lists. Matters for prioritising Phase 2 review. Fix: add a `confidence` field (e.g. high if `---` block, low if only key-run heuristic).

- **No tracking of git-tracked symlinks vs filesystem symlinks.** v0 walks the project root for symlinks but does not cross-check against `git ls-files`. Matters when a symlink target lives outside the repo and is expected to be ignored. Fix: tag each symlink with `tracked_in_git: true|false`.

- **`entity_id_prefix_counts` cannot parse `prefix:slug` ids.** v0's `ENTITY_ID_RE` required a trailing integer (`paper42`-style); ids of the form `paper:vinyals2024`, `discussion:2026-04-17-...`, `question:q61-...` all bucketed into `<unparseable>`. The per-id paths map was correct; only the aggregate counter was broken. **Resolved 2026-04-25:** `extract_entity_id_prefix()` now tries colon-split first, falls back to the trailing-digit form, then `<unparseable>`. Covered by `--self-test`.

- **`validate.structural_diff` only saw section title changes, not content drift.** v0 compared the list of section titles between local and canonical `validate.sh` and emitted `added`/`removed`/`reordered` records, missing within-section content drift entirely (e.g. natural-systems had 80 lines of real diff inside the same section headers and reported `structural_diff: []`). **Resolved 2026-04-25:** `summarize_validate()` now also emits `content_diff` (per-section sha256 + canonical/local line counts + changed-line count) and `content_diff_total_lines` aggregate. `structural_diff` semantics unchanged.

- **Gitignored top-level directories invisible.** v0's `find_present_untracked` only checked a hardcoded list of well-known dirs (`.snakemake`, `.venv`, `data`, `logs`, `models`, `node_modules`, `results`, `.worktrees`). Real, content-bearing gitignored dirs like cbioportal's `archive/` (30 files), mm30's `inc/` (272), or natural-systems' `dist/` (689) didn't appear anywhere in the inventory. **Resolved 2026-04-25:** new top-level `gitignored_top_level_dirs: [{name, file_count, total_size_bytes, sample_paths}]` enumerates every top-level directory present-on-disk and untracked, excluding the noise set (`.git`, `.venv`, `node_modules`, `__pycache__`, `.snakemake`, `.worktrees`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`) and anything already covered by `present_untracked_dirs`. Walks each candidate to depth 3.
