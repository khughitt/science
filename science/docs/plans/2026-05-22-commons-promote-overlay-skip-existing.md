# commons promote: overlay/skip papers already in the commons

- **Date:** 2026-05-22
- **Status:** proposal (no code changes yet); revised after code review (2026-05-22) — see "Review corrections".
- **Task:** science-meta `t063`
- **Feedback:** `fb-2026-05-22-001` (overlay/skip gap), `-002` (no reindex after apply), `-003` (orphan failure audit log blocks retries) — this plan covers all three (bundled by decision below).
- **Scope:** `commons promote paper` apply flow. Paper kind only for now; design is kind-agnostic where cheap, but datasets/topics/themes are explicit follow-ups (see Open Questions).
- **Trigger:** `commons promote paper --from <project> --apply` aborts the whole batch when any paper slug already has a `paper/<slug>/1.0.0` tag in the commons. A project that shares a paper with an already-promoted sibling cannot be promoted independently — currently blocking `multiple-myeloma` (shares ~5 papers with `evolution`/`pan-disease`).

## Problem

The apply path always mints a fresh canonical entity at a hard-coded version and refuses any tag clash:

- `PromoteDecision.canonical_version` is the literal `"1.0.0"` everywhere it is set — `promote.py:720, 733, 747, 835`.
- Tag preflight aborts the batch if `paper/<slug>/1.0.0` already exists — `promote.py:1254-1263`, raising `PromoteWriteError(stage="write_commons")`.
- Cross-project dedup happens **only within one invocation's `--from` set** (`discover_candidates` groups by normalized slug across the batch — `promote.py:452-470`); it never consults what is already committed in the commons.

So once project A is promoted, promoting project B that shares any slug — whether a genuinely shared paper or a true `FirstAuthorYear` collision — aborts. The intended workflow ("one `--from A --from B …` for all contributors at once") does not survive incremental, project-by-project promotion.

### Building blocks that already exist

- **Discovery already skips overlays.** Files with `overlay_of` in frontmatter are filtered at scan time — so once a source summary is rewritten as an overlay it is naturally excluded from future discovery.
- **A lookup layer exists but is unused by promote.** `CommonsQuery.show(canonical_id)` / `.find(...)` (`query.py:40, 52`) read the registry; `RegistryBuilder.rebuild()` (`registry.py:82`) is importable. Neither is called from the apply path.
- **Version tags are the source of truth.** Tags are `<kind>/<slug>/<version>` (`promote.py:1257`), independent of the (possibly stale) `registry.sqlite`.
- **The overlay renderer already pins to the decision's version.** `_render_overlay` sets `pin_version = decision.canonical_version` (`promote.py:2446-2473`). If we set that to an *existing* version, the overlay pins correctly with no renderer change.
- **A field-conflict resolution channel already exists.** `plan_promote(..., resolve_conflict=...)` (`promote.py:508`) surfaces `FieldConflict`s to a CLI callback — reusable for divergence prompts.

## Design decisions (resolved)

1. **Divergence policy — "overlay if same, else conflict."** When a slug already exists in the commons: build the would-be canonical entity from the merged source fields, compare it to the committed canonical entity. If the source's canonical fields are equal-or-subset (source adds nothing the existing entity lacks), rewrite the source as an overlay pinned to the existing version. If the source diverges (introduces a new value or a richer field), surface a conflict through the existing `resolve_conflict` channel — never silently discard. No new versions are minted in this iteration (full semver bump-on-divergence is deferred — Open Questions).
2. **Bundle the two adjacent operational fixes** (`fb-002`, `fb-003`) into this change — both live in `apply_promote`'s success/failure paths and the reindex is required for the new overlays to resolve immediately after apply.

## Implementation

### 1. Detect the existing canonical (case-insensitively) at plan time

The match must be on the **normalized** slug, not the source-derived case, or it misses an existing entity whose committed case differs (e.g. source `dubois2022.md` vs committed `paper/Dubois2022/1.0.0`). Discovery already keys each group by `slug_normalized` (casefold for paper — `_normalize_slug_for_match`), so the helper takes that key, scans all `<kind>/*` tags, and returns **both the committed canonical case and the latest version** (reads tags, not the registry — avoids staleness affecting planning):

```python
def _existing_canonical_for_slug(
    commons_root: Path, kind: PromoteKindConfig, slug_normalized: str
) -> tuple[str, str] | None:
    """(committed_canonical_case, latest_version) for an already-promoted slug,
    matched per kind.slug_match (casefold for paper); or None."""
    out = _git(commons_root, "tag", "--list", f"{kind.kind}/*").stdout
    by_case: dict[str, str] = {}  # committed_case -> latest version seen
    for line in (ln.strip() for ln in out.splitlines()):
        if not line:
            continue
        _, _, rest = line.partition("/")          # drop "<kind>/"
        case_slug, _, version = rest.rpartition("/")
        if _normalize_slug_for_match(case_slug, kind) != slug_normalized:
            continue
        cur = by_case.get(case_slug)
        if cur is None or _semver_key(version) > _semver_key(cur):
            by_case[case_slug] = version
    if not by_case:
        return None
    if len(by_case) > 1:
        raise PromoteInputError(
            f"commons integrity: {kind.kind} slug {slug_normalized!r} is committed "
            f"under multiple cases {sorted(by_case)}; resolve before promoting"
        )
    (case_slug, version), = by_case.items()
    return (case_slug, version)
```

The returned `committed_canonical_case` — **not** the source-derived `canonical_case` from `_pick_canonical_bibkey_case` (`promote.py:619`) — becomes the slug used for the decision, the overlay `id`/`overlay_of` (`paper:<committed_case>`), the overlay target path, and the canonical-file read. This keeps a project's overlay consistent with the already-published entity's case.

**Integrity guard:** if the commons already holds the *same normalized slug under more than one case* (e.g. both `paper/Dubois2022/1.0.0` and `paper/dubois2022/1.0.0`), that is a pre-existing commons corruption — the helper fails loud rather than arbitrarily picking a case to overlay against (*fail early / avoid silent fallbacks*). It must be resolved in the commons before promotion proceeds.

### 2. Mark the decision's mode

Extend `PromoteDecision` (`promote.py:375-382`) with an explicit discriminator rather than overloading `canonical_version`:

```python
mode: Literal["mint", "overlay_existing"] = "mint"
existing_version: str | None = None   # set when mode == "overlay_existing"
```

For an `overlay_existing` decision: `canonical_artifacts = []` (nothing to write to the commons), `canonical_version = existing_version` (so the overlay pins to it via the unchanged renderer), and no tag is minted.

### 3. Branch in `plan_promote`

Detection happens **before** the canonical-case is finalized, so the existing committed case can override it (and feed the collision pre-check at `promote.py:624-636` and overlay-target computation). Restructure the per-group body (around `promote.py:619`):

1. `provisional_case = _pick_canonical_bibkey_case(classified, from_order)` (unchanged).
2. `existing = _existing_canonical_for_slug(commons_root, kind, slug_norm)`.
3. If `existing is None` → `canonical_case = provisional_case`, unchanged mint path (`mode="mint"`, version `"1.0.0"`).
4. If `existing` is set → unpack `(committed_case, existing_version)`, set `canonical_case = committed_case`, then:
   - Read the committed canonical entity (`papers/<committed_case>.md` under `commons_root`, parsed to frontmatter+body).
   - Compare against the merged source-derived canonical fields using the mixin-paper canonical field set (`title, authors, year, venue, doi, pmid, pmcid, arxiv, url, datasets, key_findings, methods_summary, limitations` + canonical body sections from `mixin-paper-2.0.json`'s `x-canonical-body-sections`).
   - **Equal-or-subset** (every source canonical field is absent-in-source or value-equal to existing; existing may be richer) → `mode="overlay_existing"`, `existing_version=existing_version`, `canonical_version=existing_version`, `canonical_artifacts=[]`.
   - **Divergent** (source introduces a value the existing entity lacks or contradicts) → emit conflict(s) per §3a. On keep-existing → `overlay_existing` as above; on abort → propagate `PromoteConflictAbort`. (Minting a bumped version is intentionally **not** offered yet.)

Comparison normalization: case-insensitive title; order-insensitive list compare for `authors`/`datasets`/`key_findings`/`limitations`; whitespace-trimmed body sections. Keep the normalizer in one helper, `_canonical_fields_equal_or_subset(source, existing) -> _Cmp` returning equal / subset / divergent + the offending field(s).

### 3a. The existing-canonical conflict (distinct from `FieldConflict`)

`FieldConflict` (`promote.py:332-336`) models *which contributing project's value wins* — `candidates: dict[project_slug → value]`, resolved by picking a candidate or entering a manual value (`prompt_resolve`, `promote.py:473`). The existing-canonical case is a different shape: source-vs-committed, with only **keep-existing** or **abort** (no manual entry, no per-project candidates, no version bump this iteration). So introduce a distinct type and broaden the callback rather than overload `FieldConflict`:

- New `@dataclass(frozen=True, slots=True) ExistingCanonicalConflict(slug, kind, field, source_value, existing_value, existing_version)`.
- Broaden the callback type to `Callable[[FieldConflict | ExistingCanonicalConflict], Any]` (signature on `plan_promote`, `promote.py:513`).
- Extend `prompt_resolve` with a branch for the new type: print the field + source-vs-existing values and prompt `[k] keep existing (overlay) / [a] abort`. Return the module sentinel `KEEP_EXISTING` on `k`; raise `PromoteConflictAbort` on `a`/Ctrl-C. (No candidate enumeration, no manual-entry branch.)
- One conflict is emitted per diverging field (for legible reporting); resolving all as keep-existing yields `overlay_existing`, any abort aborts the batch.
- **Audit:** record the resolution through the existing `ConflictResolution` shape (`promote.py:339-345`) so the audit-log schema is unchanged — `candidates={"<commons-existing>": existing_value, "<source-merged>": source_value}`, `resolved_to=existing_value`, `source_project=None`. Both keys are **reserved labels**: `<commons-existing>` denotes the already-committed entity, and `<source-merged>` denotes the source-side value, which may itself be the merge of several contributing projects in the batch — so there is no single source project to name (and `ExistingCanonicalConflict` deliberately carries no `source_project`). If per-project provenance is ever needed in the audit, carry it explicitly on the conflict instead of overloading the candidate key.

### 4. Skip canonical write + tag for `overlay_existing` in `apply_promote`

In `apply_promote` (`promote.py:1177-1500`):

- **Tag preflight (1254-1263):** only applies to `mode == "mint"`. With planning now routing existing slugs to `overlay_existing`, a mint decision whose tag already exists is a genuine internal inconsistency — keep the abort as a defensive guard (`explicit > defensive`: it should never fire in normal flow, and if it does, failing loud is correct).
- **Canonical write (1265-1290) + commit (1292-1331) + tag (1320-1331):** iterate only `mint` decisions. If *all* decisions are `overlay_existing`, `canonical_writes` is empty → skip the commit and leave **`commons_commit = None`** (not the current `HEAD`). The audit renderer turns a non-`None` `commons_commit` into `git revert <commit>` rollback guidance (`promote.py:2611`); recording `HEAD` there would emit guidance to revert an unrelated commit. There is no promote-owned canonical commit in this case, so `None` is correct. The separate audit-log commit (Step 7 / §6) is *not* the canonical promote commit and is never stored in `commons_commit` (consistent with the success path, which captures `commons_commit` at 1311 before the audit commit at 1447).
- **Overlay rewrite (1361-1407):** unchanged — runs for every decision and already pins `pin_version = decision.canonical_version`, which is now `existing_version` for overlay-existing slugs.

Net effect: an all-shared-papers promote writes zero commons commits and only rewrites the source summaries as overlays pinned to the existing versions; a mixed batch mints the net-new papers and overlays the rest, in one apply.

### 5. fb-002 — reindex after apply

After a successful `apply_promote`, rebuild the commons registry so the freshly written overlays/canonicals resolve without a manual `commons index rebuild`:

```python
from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder
RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()
```

Place it in the CLI orchestrator `_promote_kind_cmd` (`cli.py:725+`) on the success branch — keeps `apply_promote` git-focused (single responsibility) and matches where `root` is already resolved. `registry.sqlite` is gitignored, so the rebuild does not dirty the working tree or interact with the clean preflight.

**Contract (explicit):** `apply_promote` does **not** rebuild the index — by design it leaves that to its caller. The CLI is the only first-class caller (programmatic callers, including the existing tests, invoke `apply_promote` directly and observe a stale index, which is correct). The fb-002 test therefore asserts at the **CLI level** (drive the `commons promote … --apply` command via `CliRunner`, then assert `registry.is_stale()` is `False`) — not against a raw `apply_promote` call.

### 6. fb-003 — don't let the failure audit log block retries

Today the failure path writes `.migrations/<stamp>-<op>.yaml` **uncommitted** (`_write_failure_audit_log`, `promote.py:1077-1135`) and re-raises. The next run's clean preflight treats untracked `.migrations/` files as dirty (`_commons_is_clean`, `promote.py:945-960`) and aborts — self-perpetuating.

**Do not add new rollback** — the per-stage handlers already leave the commons working tree clean: Step 4 / 5.2 call `_restore_paths_to_head` (`promote.py:1286, 1305`), Step 5.3 / 5.4 call `_rollback_step5` (`promote.py:1324, 1352`). The one deliberate exception is **Step 6 rewrite_projects for paper kind**, which *preserves* the already-committed canonical commit+tag and only rolls the commons back when side-channel state exists (`promote.py:1388`). That durable commit is intended and must be kept. So in every non-audit failure stage the commons tree is clean **except for the uncommitted `.migrations` audit file** the outer handler writes.

Fix: in the outer handler (`promote.py:1481-1500`), when `_write_failure_audit_log` returns a non-`None` `audit_path`, commit it path-limited — symmetric with the success path — *after* whatever per-stage rollback already occurred:

```python
git add -- .migrations/<file>
git commit -m "audit: failed op <op_id>"
```

then re-raise the **original** failure (with `failure_audit_yaml` still attached for stderr surfacing). The audit-stage failure branch (`promote.py:1482`) is untouched — it attaches the YAML to the exception and writes no `.migrations` file, so there is nothing to commit.

**If the audit `git add`/`git commit` itself fails**, it must not replace the original failure with a bare git error. Wrap it in `try/except (subprocess.CalledProcessError, OSError)`: on failure, attach `failure_audit_yaml` to the *original* `exc` (chaining the git error via `from`/logging, not raising it), and re-raise `exc`. In that degraded case the `.migrations` file may remain (git is itself broken — the same situation as today, and the worst that happens is the existing manual cleanup), but the operator sees the real cause rather than a misleading commit error. The common path (git healthy) commits the log and leaves a clean tree so a retry's preflight passes — removing the manual `git ls-files --others … | xargs rm` step.

**Synergy with §3-4:** because a Step-6 paper failure leaves the canonical *durably committed+tagged*, a retry now finds the slug already present and routes it to `overlay_existing` (§3) — so the retry simply completes the project overlay rewrite instead of re-minting. The overlay/skip feature makes Step-6 failures cleanly resumable.

## Tests

- **plan** (`test_commons_promote_plan.py`):
  - existing slug, identical canonical → decision `mode == "overlay_existing"`, `canonical_artifacts == []`, `canonical_version == existing`.
  - existing slug, source poorer/subset → `overlay_existing` (no conflict).
  - existing slug, divergent field → `resolve_conflict` invoked with `ExistingCanonicalConflict`; *abort* propagates, *keep-existing* yields `overlay_existing`.
  - **case-insensitive match** — source `dubois2022.md`, committed `paper/Dubois2022/1.0.0` → matched; the decision slug, overlay `id`/`overlay_of`, target path and canonical read all use the committed `Dubois2022` case.
  - **integrity guard** — commons holding both `paper/Dubois2022/1.0.0` and `paper/dubois2022/1.0.0` → `_existing_canonical_for_slug` raises `PromoteInputError` (no arbitrary pick).
  - version selection picks max semver across multiple `<kind>/<slug>/*` tags.
- **apply** (`test_commons_promote_apply.py`):
  - all-`overlay_existing` batch → no new tag, no commons canonical commit, `result.commons_commit is None`, the rendered audit log emits **no** `git revert` guidance, source overlays written + pinned to existing version; idempotent on re-run.
  - failure path with a broken audit commit → the *original* failure is surfaced (not a git error) and `failure_audit_yaml` is attached.
  - mixed batch → net-new minted, shared overlaid, in one apply.
  - **update** `test_apply_promote_tag_preflight_rejects_existing_tag` (818): the pre-existing-tag scenario is now resolved at plan time to `overlay_existing`; re-target the test to assert the plan outcome, and add a separate test that the apply-time preflight still fails loud for a hand-constructed `mint` decision whose tag exists (defensive guard).
- **fb-002 (CLI-level):** drive `commons promote … --apply` via `CliRunner`, then assert `registry.is_stale()` is `False`. (A raw `apply_promote` call still leaves it stale — that is the contract.)
- **fb-003:** after a forced mid-apply failure, `_commons_is_clean` returns clean (the `.migrations` audit log is committed, not orphaned), and an immediate re-apply is not blocked.

## Rollout — unblocks the family

After this lands, the held `multiple-myeloma` promotion runs as one pass on `main` (worktree-on-main pattern if `t688-causal-evidence-layer` is still checked out — see the worktree gotchas note):

1. Rename the two true collisions: `Lee2026 → Lee2026b`, `Wang2025 → Wang2025b`.
2. `commons promote paper --from multiple-myeloma --apply` — the ~5 shared papers (`Dubois2022` + 4) overlay the existing commons entities at their current versions; the net-new MM papers mint fresh.
3. Reindex now happens automatically (fb-002).

The two `id: meta` projects remain gated on the separate id-uniqueness work (see `2026-05-22-project-id-uniqueness-and-peer-resolution.md`); that is orthogonal to this change.

## Review corrections (2026-05-22)

Incorporated after a code review of the first draft:

- **High — case-insensitive existing-entity match.** The lookup originally keyed on the source-derived `canonical_case`, missing a committed entity whose slug differs only by case (e.g. `dubois2022` vs `Dubois2022`). Now `_existing_canonical_for_slug` matches on the normalized slug and returns the committed case, which overrides `canonical_case` for the decision/overlay/id/read (§1, §3, plan test added).
- **Medium — reindex location vs test.** Stated `apply_promote`'s no-reindex contract explicitly and moved the fb-002 assertion to the CLI level, so it matches where the rebuild actually runs (`_promote_kind_cmd`) rather than a raw `apply_promote` call (§5, tests).
- **Medium — fb-003 over-broad rollback.** Removed the "roll back commons commit/tags before audit" step; the per-stage handlers already clean the tree, and Step-6 paper failures *intentionally* keep the durable commit+tag (`promote.py:1388`). The fix is only to commit the `.migrations` audit log path-limited after whatever rollback already occurred (§6).
- **Medium — `ExistingCanonicalConflict` shape.** Specified it as a distinct type (not an overloaded `FieldConflict`), broadened the `resolve_conflict` callback type, defined the keep-existing/abort `prompt_resolve` branch and `KEEP_EXISTING` sentinel, and mapped the resolution onto the existing `ConflictResolution` audit shape (§3a).

Second review round:

- **Medium — `commons_commit` for all-overlay runs.** Set it to `None` (not current `HEAD`) when nothing canonical is committed; otherwise the audit renderer (`promote.py:2611`) would emit `git revert <HEAD>` guidance against an unrelated commit. The separate audit-log commit is never recorded as the canonical promote commit (§4, tests).
- **Medium — multiple committed cases for one slug.** `_existing_canonical_for_slug` now fails loud if the commons holds the same normalized slug under >1 case, rather than arbitrarily choosing one (§1, test).
- **Low — audit candidate provenance.** The source side of an `ExistingCanonicalConflict` resolution is recorded under the reserved `<source-merged>` label (it may be a merge of several projects; the conflict carries no single `source_project`) (§3a).
- **Low — failed audit commit.** Wrapped the failure-path audit `git add`/`commit` so a git error cannot mask the original failure or silently leave the retry-blocking `.migrations` file unreported (§6, test).

## Open questions

1. **Subset semantics.** Confirm "existing richer than source = safe overlay (no conflict)" is desired (the plan assumes yes). The inverse — source richer — is always a conflict under this iteration.
2. **Deferred: bump-on-divergence.** Full semver (mint `N+1` capturing the source's richer content, retag, pin overlay to new version) is the natural follow-up once a divergence is common in practice. Out of scope here.
3. **Other kinds.** `canonical_version="1.0.0"` is also hard-coded for dataset/topic/theme (`promote.py:720, 733, 747`). The version-lookup + `overlay_existing` mode generalize, but datasets carry a datapackage side-channel and a different layout (`datasets/<slug>/entity.md`) — overlay-existing for datasets needs its own pass. Paper-only for `t063`.
4. **Version comparator.** Confirm a strict semver parse for `_semver_key` (all current tags are `1.0.0`, so `max` is trivial today, but the comparator should be correct for the eventual bump path).
