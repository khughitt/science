# Phase G pilot: commons promote dataset

This runbook records the first production pilot for
`science commons promote dataset`. It is not part of CI; it is an operational
step after the Phase G implementation lands.

## Goal

Exercise the full Phase G surface end-to-end on
`dataset:ccle-proteomics-nusinow-2020` in `multiple-myeloma`: canonical
multi-file dataset artifacts, real-byte resource hashing, per-machine data
override, project overlay rewrite, audit log, and dataset tag.

## Preconditions

1. **Commons store initialized and clean.** `.gitignore` no longer ignores
   `.migrations/`.
   ```bash
   cd ~/d/science-commons && git status --short
   ```
   Expected: no output. Commit or stash any pending commons work before the
   pilot.

2. **Pilot project registered.** Confirm `multiple-myeloma` is registered with
   stable `id: multiple-myeloma`:
   ```bash
   yq '.projects[] | select(.id == "multiple-myeloma") | .id' ~/.config/science/config.yaml
   ```
   Expected output includes `multiple-myeloma`. If the project is missing or
   has `id: null`, update `~/.config/science/config.yaml` before running
   promote.

3. **Pilot project working tree clean.**
   ```bash
   cd ~/d/cancer/cancer-types/multiple-myeloma
   git status --short -- doc/datasets/data-ccle-proteomics.md data/external/ccle_proteomics/2020-01/
   ```
   Expected: no output for the dataset descriptor and data package tree.

4. **Pre-migration prep frontmatter committed.** The prep commit described
   below must already be committed before promote runs.

5. **No conflicting local data override.** `~/.config/science/data.yaml` either
   does not exist or does not already map `ccle-proteomics-nusinow-2020` to a
   conflicting path.

## Pre-migration prep commit

Before running promote, add this frontmatter block to
`~/d/cancer/cancer-types/multiple-myeloma/doc/datasets/data-ccle-proteomics.md`:

```yaml
datapackage: data/external/ccle_proteomics/2020-01/datapackage.json
origin: external
tier: evaluate-next
access:
  level: public
  verified: true
  source_url: "https://gygi.hms.harvard.edu/publications/ccle.html"
```

Commit the prep change separately:

```bash
cd ~/d/cancer/cancer-types/multiple-myeloma
git add doc/datasets/data-ccle-proteomics.md
git commit -m "docs(datasets): add Phase G prep frontmatter for ccle-proteomics"
```

## Step 1: Dry-run

```bash
science commons promote dataset \
  --from multiple-myeloma \
  --slug ccle-proteomics-nusinow-2020
```

Expected output:
- 1 candidate planned, 0 failed.
- Canonical artifact list:
  `commons/datasets/ccle-proteomics-nusinow-2020/entity.md`,
  `commons/datasets/ccle-proteomics-nusinow-2020/datapackage.yaml`,
  `commons/datasets/ccle-proteomics-nusinow-2020/recipe/README.md`.
- Per-resource hash + bytes: 2 hashes, about 1.3 MB total, dry-run under a
  second.
- Per-machine override line to be written.
- Project overlay rewrite stat for one file.
- Dropped fields list: expect `ontologies`, `datasets`, and possibly others
  depending on prep state.

Review the summary. If the canonical artifacts, resource hashes, override
line, overlay rewrite, or dropped fields look wrong, fix the source files and
re-run the dry-run before apply.

## Step 2: Apply

```bash
science commons promote dataset \
  --from multiple-myeloma \
  --slug ccle-proteomics-nusinow-2020 \
  --apply
```

Expected effects:
- 1 commons commit.
- 1 audit commit.
- 1 `dataset/ccle-proteomics-nusinow-2020/1.0.0` tag.
- 1 line upserted to `~/.config/science/data.yaml`, with the
  `.bak.<op-id>` backup retained.
- 1 project overlay rewritten but uncommitted at
  `~/d/cancer/cancer-types/multiple-myeloma/doc/datasets/data-ccle-proteomics.md`.

## Step 3: Commit Project Overlay

Promote does not commit project rewrites. Review and commit the overlay
manually:

```bash
cd ~/d/cancer/cancer-types/multiple-myeloma
git diff doc/datasets/data-ccle-proteomics.md
git add doc/datasets/data-ccle-proteomics.md
git commit -m "docs(datasets): promote ccle-proteomics to commons (Phase G pilot)"
```

## Step 4: Verify

Verify the commons inventory includes the new dataset canonical:

```bash
science commons inventory | rg '"id": "dataset:ccle-proteomics-nusinow-2020"'
```

Verify the merged entity reads through the project overlay:

```bash
science commons show dataset:ccle-proteomics-nusinow-2020 --project multiple-myeloma
```

Verify the data resolver finds the original project bytes through the local
override and checks them against the canonical hash:

```bash
science commons data resolve dataset:ccle-proteomics-nusinow-2020 mm-cell-lines.parquet
```

If all three commands succeed, the pilot has exercised the full Phase G path.

## Rollback hints

The audit log records every touched file. Rollback is path-limited.

For commons success path, prefer a normal revert:

```bash
cd ~/d/science-commons
git revert <commons-commit>
```

Then delete only the `dataset/ccle-proteomics-nusinow-2020/1.0.0` tag listed
in the audit log:

```bash
cd ~/d/science-commons
git tag -d dataset/ccle-proteomics-nusinow-2020/1.0.0
```

For the project overlay:

```bash
cd ~/d/cancer/cancer-types/multiple-myeloma
git checkout HEAD -- doc/datasets/data-ccle-proteomics.md
```

For the local override, restore from the `data.yaml.bak.<op-id>` path recorded
in the audit log.

Do not hard-reset any user repository. Rollback is path-limited so unrelated
work is preserved.
