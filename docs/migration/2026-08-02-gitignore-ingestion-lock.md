# The managed `.gitignore` block now ignores the ingestion lock

**Who this affects:** every Science-managed project with **declared boundary roots** in
`science.yaml` — those are the ones `science validate` reports drift for. The rendered
block itself gained the line unconditionally, but a project with no declared roots takes
no action until boundary enrollment: `science boundary sync` refuses a project that
declares no roots. Only a project with declared roots gets the drift error.

**Required action:** run `science boundary sync` once, and commit the resulting
`.gitignore`.

## What changed

`science findings ingest` takes a lock at `doc/audits/cases/.ingest.lock` and
deliberately never unlinks it — the lock file is permanent untracked residue in any
project that has ever ingested findings. The science-managed block in a project's root
`.gitignore` now ends with an unconditional line for it:

```
/doc/audits/cases/.ingest.lock
```

It is appended after every root-derived line, and that ordering is load-bearing rather
than cosmetic: `.gitignore` is last-match-wins, and a declared manifest root overlapping
`doc/audits/cases` may legally emit a negation that re-includes files under it.

## Why it is a hard error until you sync

`science validate`'s boundary check compares the managed block on disk against the block
the current toolkit renders, and reports `boundary.generated-drift` at `ERROR` severity
when they differ. That check runs under `science validate`, which runs under `science
health`'s validate producer. **A project that upgrades the toolkit and does not sync will
see a new health ERROR**, naming drift in a block it never edited.

The check is behaving correctly: the managed block is toolkit-owned, and a project whose
copy is stale is a project whose ignore rules are not the ones the toolkit expects. There
is no grace period and no compatibility fallback, because a check that tolerated one
version of the block would tolerate every other stale version too.

## Migration steps

1. From the project root, with a clean-enough working tree:

   ```bash
   science boundary sync
   ```

2. Review the diff. The only change should be the added lock line inside the
   `science-managed` markers; anything else means the project had hand-edits inside the
   managed block, which the block's markers exist to prevent.
3. Commit `.gitignore`.
4. Re-run `science validate` (or `science health`) and confirm
   `boundary.generated-drift` is gone.

If the project has already committed `doc/audits/cases/.ingest.lock`, remove it from the
index as well — the ignore rule does not untrack a file git is already following:

```bash
git rm --cached doc/audits/cases/.ingest.lock
```
