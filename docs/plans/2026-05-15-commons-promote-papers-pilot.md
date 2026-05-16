# Phase E pilot: promote papers (manual run)

This runbook records the exact procedure for the first production run of
`science commons promote paper`. It is not part of CI; it's a one-time
operational step after the implementation lands.

## Preconditions

1. **Commons store initialized.** Run once on this machine:
   ```bash
   science commons init
   ```
   This creates `~/d/science-commons/` with `papers/`, `datasets/`,
   `topics/`, `themes/`, `.migrations/`, and a `.git` repo.

2. **Project registry has `id:` for every pilot project.** Confirm:
   ```bash
   yq '.projects[] | select(.id != null) | .id' ~/.config/science/config.yaml
   ```
   Expected output includes `natural-systems`, `multiple-myeloma`, `meta`
   (cancer-meta), `evolution` (cancer-evolution), `protein-landscape`.
   If any of these have `id: null`, edit `~/.config/science/config.yaml`
   to assign an id (must be unique). The legacy `~/r/mm30` registration is
   intentionally id:null — leave it alone; promote will not include it.

3. **Working trees clean.**
   ```bash
   for d in ~/d/science-commons ~/d/natural-systems ~/d/cancer/cancer-types/multiple-myeloma ~/d/cancer/meta ~/d/cancer/mechanisms/evolution ~/d/protein-landscape; do
     echo "== $d =="; cd "$d" && git status --short
   done
   ```
   Commit / stash any pending work in `~/d/science-commons`. For the
   project repos, only files under `doc/papers/*.md` must be clean;
   other dirty files are fine.

## Step 1: Dry-run

```bash
science commons promote paper \
  --from natural-systems \
  --from multiple-myeloma \
  --from meta \
  --from evolution \
  --from protein-landscape
```

Expected: ~503 candidates discovered, ~9 multi-instance bibkeys. The
command will prompt for each canonical-field conflict (most multi-instance
bibkeys will auto-merge without prompts).

Review the summary. If anything looks off, fix the source files and re-run.

## Step 2: Apply

```bash
science commons promote paper \
  --from natural-systems \
  --from multiple-myeloma \
  --from meta \
  --from evolution \
  --from protein-landscape \
  --apply
```

Expected:
- One commit in `~/d/science-commons` with all canonical paper files.
- ~503 tags `paper/<bibkey>/1.0.0`.
- One audit-log commit `audit: op <op-id>`.
- ~503 project overlay rewrites (uncommitted in each project — see step 3).

## Step 3: Commit overlays per project

Promote does NOT commit project rewrites. Review the rewrites in each
project, then commit:

```bash
for d in ~/d/natural-systems ~/d/cancer/cancer-types/multiple-myeloma ~/d/cancer/meta ~/d/cancer/mechanisms/evolution ~/d/protein-landscape; do
  cd "$d"
  echo "== $d =="
  git diff --stat doc/papers/
  echo "(review then run): git add doc/papers/ && git commit -m 'promote papers to commons'"
done
```

## Step 4: Verify

```bash
science commons find paper --type paper | head
science commons show paper:Huh2024
```

Should show the merged canonical entity. Try the dashboard:

```bash
# From ~/d/dashboard (assuming the inventory_v2 pivot is shipped):
make dev
```

Each project's view should show the paper with its project's overlay
applied (tags, related, body sections preserved per project).

## Rollback (if needed)

The audit log in `~/d/science-commons/.migrations/<ts>-<op-id>.yaml` carries
the exact commands to undo the run. Roughly:

```bash
# Revert the commons commit:
cd ~/d/science-commons && git revert <commit-hash>

# Restore project files (per project):
cd ~/d/natural-systems && git checkout HEAD -- doc/papers/
```

Do NOT use `git reset --hard` anywhere — the rollback procedure is
path-limited by design.
