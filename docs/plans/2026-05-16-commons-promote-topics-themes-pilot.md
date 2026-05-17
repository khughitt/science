# Phase F pilot: commons promote topics + themes

This runbook records the first production pilot for
`science commons promote topic` and `science commons promote theme`. It is not
part of CI; it is an operational step after the Phase F implementation lands.

## Preconditions

1. **Commons store initialized and clean.**
   ```bash
   cd ~/d/science-commons && git status --short
   ```
   Expected: no output. Commit or stash any pending commons work before the
   pilot. The `topics/`, `themes/`, and `.migrations/` paths must be clean.

2. **Commons config registered.** Confirm the pilot projects are registered
   with stable ids:
   ```bash
   yq '.projects[] | select(.id != null) | .id' ~/.config/science/config.yaml
   ```
   Expected output includes `natural-systems`, `multiple-myeloma`, and `meta`.
   If a pilot project is missing or has `id: null`, update
   `~/.config/science/config.yaml` before running promote.

3. **Pilot project working trees clean.**
   ```bash
   for d in ~/d/natural-systems ~/d/cancer/cancer-types/multiple-myeloma ~/d/cancer/meta; do
     echo "== $d =="; cd "$d" && git status --short
   done
   ```
   Expected: no output for each project. At minimum, the paths touched by the
   pilot must be clean: `doc/topics/`, `doc/background/topics/`, and
   `doc/themes/`.

4. **Branch ready.** Run from the Phase F implementation branch
   `feat/commons-promote-topics-themes`, branched from current `main`, after the
   implementation and tests have landed.

## Step 1: Dry-run

Dry-run the topic pilot first:

```bash
science commons promote topic \
  --from natural-systems \
  --from multiple-myeloma
```

Expected candidate shapes:
- `doc/topics/<slug>.md` in one project becomes a canonical
  `~/d/science-commons/topics/<slug>.md` plus one project overlay at
  `doc/topics/<slug>.md`.
- The same `<slug>` in both projects becomes one canonical topic plus two
  project overlays.
- `doc/background/topics/<slug>.md` is eligible and will be flattened to an
  overlay at `doc/topics/<slug>.md` on apply; dry-run should show the rename.
- Topic and theme slugs are lowercase-only. Valid lowercase spelling
  differences are separate candidates; uppercase or case-only differences fail
  discovery validation instead of merging.

Dry-run theme discovery for the same pilot set:

```bash
science commons promote theme \
  --from multiple-myeloma \
  --from meta
```

Expected candidate shapes:
- Only themes with `theme_scope: cross-project` are eligible for promotion.
- `theme_scope: project` themes are skipped by the eligibility filter.
- Missing or malformed `theme_scope` is reported as a failed candidate.
- If no cross-project themes are present, the command should report nothing to
  promote. That is an expected result for this pilot.

Review the summaries. If topic candidates or theme skips look wrong, fix the
source files and re-run the dry-runs before any apply.

## Step 2: Apply

Apply the topic pilot:

```bash
science commons promote topic \
  --from natural-systems \
  --from multiple-myeloma \
  --apply
```

Expected:
- One commons commit in `~/d/science-commons` with canonical topic files.
- One `topic/<slug>/1.0.0` tag per promoted topic.
- One audit log under `~/d/science-commons/.migrations/`.
- Uncommitted project overlay rewrites in each pilot project.

Promote does not commit project rewrites. Review each project working tree and
commit the overlays manually:

```bash
for d in ~/d/natural-systems ~/d/cancer/cancer-types/multiple-myeloma; do
  cd "$d"
  echo "== $d =="
  git diff --stat -- doc/topics/ doc/background/topics/
  git diff -- doc/topics/ doc/background/topics/
  echo "(review then run): git add doc/topics doc/background/topics && git commit -m 'promote topics to commons'"
done
```

Do not apply the theme pilot in this first run. See the caveat below.

## Step 3: Verify

Verify the commons inventory includes the new topic canonicals:

```bash
science commons inventory | rg '"id": "topic:'
```

`science commons inventory` verifies the commons store only. It does not prove
that project overlay files were rewritten. Inspect overlays directly before
each manual project commit:

```bash
for d in ~/d/natural-systems ~/d/cancer/cancer-types/multiple-myeloma; do
  cd "$d"
  echo "== $d =="
  git diff -- doc/topics/ doc/background/topics/
  rg -n '^overlay_of: "?topic:' doc/topics
done
```

If the overlay commit is already made, inspect the committed project overlay
files instead:

```bash
git -C ~/d/natural-systems show --stat HEAD -- doc/topics/ doc/background/topics/
git -C ~/d/natural-systems grep -n -E '^overlay_of: "?topic:' HEAD -- doc/topics
git -C ~/d/cancer/cancer-types/multiple-myeloma show --stat HEAD -- doc/topics/ doc/background/topics/
git -C ~/d/cancer/cancer-types/multiple-myeloma grep -n -E '^overlay_of: "?topic:' HEAD -- doc/topics
```

If the project inventory command is available in the deployed CLI, cross-check
the overlays through inventory v2:

```bash
science entities inventory --project ~/d/natural-systems --schema-version 2 | rg '"overlay_of": "topic:'
science entities inventory --project ~/d/cancer/cancer-types/multiple-myeloma --schema-version 2 | rg '"overlay_of": "topic:'
```

Verify commons history and tags:

```bash
cd ~/d/science-commons
git log --oneline -10
git tag --list 'topic/*'
git tag --list 'theme/*'
```

Expected: the commons log shows the new topic promotion commit and audit-log
commit. Topic tags exist for the promoted slugs. Theme tags should be unchanged
for this topic-only first pilot.

After the later theme apply, repeat the commons inventory and direct overlay
checks, then confirm:
- Canonical theme entities appear with ids like `theme:<slug>`.
- Project overlay files contain `overlay_of: theme:<slug>`.
- `git tag --list 'theme/*'` shows one tag per promoted theme.

## Theme pilot caveat

Design §7 identified three valid shapes for the theme pilot:

1. **Pre-pilot rewrite.** Identify selected themes that are genuinely
   cross-project, rewrite them from `theme_scope: project` to
   `theme_scope: cross-project` in a dedicated review, then run the theme
   promote pilot.
2. **Defer the theme pilot.** Ship the machinery, but wait to apply theme
   promotion until eligible cross-project themes are ready.
3. **Topic-only pilot.** Run only the topic apply now; revisit themes after
   explicit scope review.

This pilot follows option 3: topic-only first, then theme promotion after
explicit scope review. The conservative reason is that themes in
`~/d/cancer/cancer-types/multiple-myeloma/doc/themes/` and
`~/d/cancer/meta/doc/themes/` were expected at design time to be project-scoped.
Promoting them without a scope review would either skip every file or require
changing semantics during the operational run.

When the scope review is complete, run the theme pilot with the same pattern:

```bash
science commons promote theme \
  --from multiple-myeloma \
  --from meta

science commons promote theme \
  --from multiple-myeloma \
  --from meta \
  --apply
```

Then review and commit project overlays manually:

```bash
for d in ~/d/cancer/cancer-types/multiple-myeloma ~/d/cancer/meta; do
  cd "$d"
  echo "== $d =="
  git diff --stat -- doc/themes/
  git diff -- doc/themes/
  echo "(review then run): git add doc/themes && git commit -m 'promote themes to commons'"
done
```

## Rollback hints

If apply fails, use the failure audit from the exception output
(`failure_audit_yaml`) or the audit file under
`~/d/science-commons/.migrations/<ts>-<op-id>.yaml`. It records the commons
commit, tags, project files touched, and per-project rollback commands.

For commons commits that were written successfully, prefer a normal revert:

```bash
cd ~/d/science-commons && git revert <commons-commit>
```

Then delete only the promotion tags listed in the audit log's `commons_tags`.
Do not use wildcard tag deletion; stale promotion tags block reruns, but broad
deletion can remove unrelated history. Examples for tags copied from the audit:

```bash
cd ~/d/science-commons
git tag -d topic/<slug>/1.0.0
git tag -d theme/<slug>/1.0.0
```

For project working trees, use the path-limited checkout recorded in the audit
log. Examples:

```bash
git -C ~/d/natural-systems checkout HEAD -- doc/topics/ doc/background/topics/
git -C ~/d/cancer/cancer-types/multiple-myeloma checkout HEAD -- doc/topics/ doc/themes/
git -C ~/d/cancer/meta checkout HEAD -- doc/themes/
```

Do not hard-reset any repository. Rollback is intentionally path-limited so
unrelated user work in the same project is not discarded.
