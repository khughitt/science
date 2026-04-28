# Validate.sh Hook Points — Design

**Status:** Draft. Targets canonical version bump `2026.04.26.1 → 2026.04.26.2`.

**Builds on:** `2026-04-26-managed-artifacts-long-term-design.md` (the managed-artifact spec) and Task 27 / Task 28 of the implementation plan, which landed the hook *infrastructure* (`SCIENCE_VALIDATE_HOOKS` associative array, `register_validation_hook`, `dispatch_hook`, sidecar source) but NOT the dispatch *call sites* in the canonical body.

## Problem

Phase 10 / 11 of the managed-artifacts rollout shipped the hook contract as a function vocabulary but did not exercise it. The canonical `validate.sh` defines `dispatch_hook` and sources `validate.local.sh`, but no `dispatch_hook` calls fire from the body. Projects can register hooks; they will never run.

This is "no legacy / compatibility layers" violated by half-measure: the spec promises an extension protocol the canonical doesn't honor. The four reference projects (`mm30`, `cbioportal`, `natural-systems`, `protein-landscape`) cannot migrate without it — anything that customizes their current `validate.sh` body has nowhere to land.

## Solution

Add three named dispatch points to the canonical body. Bump the canonical version. Hooks become real.

### Hook taxonomy (v1)

Three points. Minimal but principled — covers every customization observed across the four reference projects without per-section proliferation.

| Hook | Fires | Use case |
|---|---|---|
| `pre_validation` | After helpers and the banner are emitted, before section 1 starts. | Project-specific environment setup, sanity-checking external tooling, declaring globals consumed by later hooks. |
| `extra_checks` | After all canonical sections complete, before the summary banner. | Project-specific structural checks that don't fit the canonical's fixed section model. |
| `post_validation` | At process exit, regardless of pass/fail. | Cleanup, custom reporting, logging. Implemented as `trap '...' EXIT` so it fires on `exit`, on uncaught error under `set -e`, and on signal. |

Per-section hooks are intentionally **not** in v1. They can be added incrementally when concrete demand surfaces — adding them later is a non-breaking version bump (sidecars that don't register against them are unaffected).

### Contract

- **Ordering.** Hooks dispatch in the order they were registered. Multiple hooks per name supported.
- **Errors.** Hook functions run under the canonical's `set -euo pipefail`. A hook that exits non-zero terminates validation immediately. A hook that wants to *report* an error without aborting must call the canonical's `error` / `warn` helpers (defined before any hook fires) and return 0.
- **Re-entry.** `register_validation_hook` is idempotent in shape — calling it twice with the same `(hook, fn)` pair appends `fn` twice and dispatches twice. Sidecars are responsible for not double-registering.
- **Visibility of canonical state.** Hooks see all helpers (`error`, `warn`, `info`, color functions), all canonical-set globals (`PROFILE`, `LOCAL_PROFILE`, `DOC_DIR`, `SPECS_DIR`, etc.), and the running counters (`ERRORS`, `WARNINGS`). Mutating counters from hooks IS supported and is how projects contribute to the final pass/fail tally.
- **`post_validation` exit code visibility.** The hook does not see the exit code directly (bash `trap EXIT` runs before `exit` returns control); it sees `ERRORS` and `WARNINGS` globals which determine pass/fail.

### API (no changes; reaffirmed)

Sidecars register hooks via the existing function:

```bash
# validate.local.sh
my_pre_check() {
    if [ -z "${MY_PROJECT_ENV:-}" ]; then
        warn "MY_PROJECT_ENV not set"
    fi
}

register_validation_hook pre_validation my_pre_check
```

### Worked example: `protein-landscape` migration sketch

The project currently has an `extract_json_payload` Python helper inlined in its `validate.sh` and uses it in two custom checks. After Phase A:

```bash
# protein-landscape/validate.local.sh
extract_json_payload() {
    python3 -c '...'  # the existing helper
}

check_protein_landscape_specifics() {
    # uses extract_json_payload to parse some output
    ...
}

register_validation_hook extra_checks check_protein_landscape_specifics
```

The project's `validate.sh` itself becomes the canonical (via `install --force-adopt` then `update --force --yes`). Custom logic lives entirely in the sidecar.

### Versioning

`2026.04.26.1 → 2026.04.26.2`. `byte_replace` migration (no project-action steps). Previous hash of `2026.04.26.1` moves into `previous_hashes`. Changelog entry: "Add named hook dispatch points (`pre_validation`, `extra_checks`, `post_validation`); the hook contract is now functional end-to-end."

The bump itself dogfoods the managed-artifact update workflow. Any project that has already adopted v2026.04.26.1 (none yet, but proves the path) would update via `science-tool project artifacts update validate.sh --force --yes`.

### Acceptance criteria

1. The canonical contains exactly one `dispatch_hook "pre_validation"` call, exactly one `dispatch_hook "extra_checks"` call, and exactly one `trap 'dispatch_hook post_validation' EXIT` setup.
2. `dispatch_hook "pre_validation"` fires AFTER all helpers + globals are set, BEFORE section 1's output appears.
3. `dispatch_hook "extra_checks"` fires AFTER section 17's last output, BEFORE the `# ─── Summary ───` banner.
4. The `EXIT` trap dispatches `post_validation` exactly once, on every exit path (success, failure, set -e abort, signal).
5. A test sidecar that registers one hook per name and increments a counter file shows: (a) all three hooks fired exactly once, (b) in registration order, (c) `post_validation` fired even when `extra_checks` deliberately raises an error.
6. The canonical's body hash matches the registry's `current_hash` for `2026.04.26.2`. The previous hash for `2026.04.26.1` is preserved in `previous_hashes`.
7. The `migrations` list contains a `byte_replace` entry from `2026.04.26.1` to `2026.04.26.2`.
8. The registry's `extension_protocol.contract` field is updated to enumerate the three hook points and their semantics.
9. Existing tests for the artifact (`test_initial_validate_sh.py`, `test_first_version_bump.py`, `test_extensions_validate_hooks.py`) still pass.
10. The acceptance-test sidecar idiom is exercised in a new test (`test_validate_hook_points.py`) that runs the canonical against a synthetic project with a sidecar registering one hook per point.

### What this does NOT do

- Does not add per-section hook points. Future bump if needed.
- Does not change the `register_validation_hook` / `dispatch_hook` API. Same shapes as Task 27.
- Does not add hook-registration helpers like `unregister`, `list_hooks`. Sidecars are simple; if usage justifies more API, add later.
- Does not provide a way for hooks to influence canonical *behavior* beyond mutating `ERRORS`/`WARNINGS`. Hooks observe and add; they do not replace canonical checks.

### Open questions resolved during drafting

- **Should `post_validation` fire on `set -e` aborts?** Yes — `trap EXIT` is unconditional. Verified by acceptance criterion 5(c).
- **Should hooks be allowed to run more checks via the canonical's helpers?** Yes — they see all globals including `error`/`warn`/`info`. That's the whole point.
- **What if a sidecar registers a hook for a name the canonical never dispatches?** Silent no-op. The hook is stored but never fires. This is the right semantics: forward-compat for future hook points the sidecar might want to opt into early.

### Cross-references

- Supersedes the "future-tense hook capability" note in `docs/superpowers/specs/2026-04-26-managed-artifacts-long-term-design.md` (sourced_sidecar contract section).
- Unblocks the four-project migration captured in (forthcoming) `docs/migration/2026-04-27-managed-artifacts-rollout.md`.
- Implementation plan: `docs/superpowers/plans/2026-04-27-validate-hook-points-implementation.md`.
