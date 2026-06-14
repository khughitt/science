# Kind Descriptor Keystone — design

**Status:** Design / approved direction — pre-implementation.

**Spec:** Patchwork kernel **Spec 2 — Kind Descriptor & Model Registry**, increment 1
(keystone). Parent architecture: `~/d/science/docs/plans/2026-06-14-patchwork-kernel-architecture-design.md`
(subsystem-specs table, row 2). Sibling shipped specs: Patch Contract keystone
(`~/d/science/docs/plans/2026-06-14-patch-contract-keystone-design.md`) and inquiry↔patch
subsumption (`~/d/science/docs/plans/2026-06-14-inquiry-patch-profile-subsumption-design.md`).

## §0. Problem

The same ~48 entity kinds are enumerated and configured across **at least ten separate
structures spanning two packages**. Adding or changing a kind means editing many of them in
lockstep; the recently-shipped inquiry work tripped over a symptom of this (the six required
no-default base-`Entity` fields). The duplication, today:

**In `science_model/`:**
- `EntityType` enum (48 members) — the canonical kind-name list.
- Entity subclasses + `EntityRegistry.register_core_kind` wiring (`graph/entity_registry.py`,
  ~20 calls; many markdown kinds register against `ProjectEntity` directly) → kind → class +
  `EntityClass` (operational/reference/domain).
- `_CORE_KIND_CLASSES` map.
- `ProfileManifest` / `CORE_PROFILE` (the profile system).
- `MIGRATED_KINDS` + `templates/*.md` (which kinds have authoring templates).
- Required base-`Entity` fields.

**In `science_tool/`:**
- `_BUILTIN_MARKDOWN_POLICIES` — path + filename strategy per kind (`entities.py`).
- `_SHORTFORM_ENTITY_KINDS` — single-letter shortform aliases.
- `_DEFAULT_STATUS` — default status per kind.
- `_STATUS_VALUES` — controlled status vocabulary per kind.

The architecture doc frames the open decisions as: *"Is core just a built-in manifest? Which
schema system is canonical? How are descriptors generated and tested?"*

## §1. Thesis & scope

**One descriptor per kind is the single source of truth; every other structure derives from it.**

This document covers **increment 1 (the keystone) only**: stand up the descriptor SSOT, then
migrate the four kind-keyed dicts in `science_tool/entities.py` onto it, deleting them. The
heavier consumers (the registry, templates/`MIGRATED_KINDS`, profiles) are explicitly deferred
to increments 2 and 3 (§6). The keystone proves the SSOT end-to-end with the lowest-risk
consumer set, exactly as the Patch Contract keystone did before its follow-ons.

Decisions locked during brainstorming:
- **SSOT form:** a built-in *manifest of descriptor objects* (not a per-class `ClassVar`, not an
  external data file). Chosen because many core kinds share `ProjectEntity` and have no dedicated
  subclass, so only a manifest covers all kinds uniformly.
- **Coexistence:** the manifest lists **all** core kinds from the start; the keystone fully
  rewires its consumers with **no per-kind shim** and **no `descriptor-else-legacy` fallback**
  (which would be a compatibility layer). Remaining consumers keep reading their own structures
  until their increment.
- **Location:** the descriptor lives in `science_model` (the SSOT layer, which already owns
  `EntityType` and templates).

## §2. The descriptor model & location

New module `science_model/kinds.py`. It also becomes the home of the `EntityFilenameStrategy`
literal, which today lives in `science_tool/entities.py` (line 25). The strategy vocabulary is part
of the kind SSOT, so it moves to the model layer; `science_tool/entities.py` then imports it from
`science_model.kinds` (the correct dependency direction — tool depends on model, never the reverse).

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

EntityFilenameStrategy = Literal["numeric", "citekey", "singleton", "slug", "verbatim"]  # moved from science_tool


@dataclass(frozen=True)
class KindDescriptor:
    name: str                                       # canonical kind, e.g. "hypothesis"
    path: Path | None = None                        # markdown home: a dir, or a file for singletons
    strategy: EntityFilenameStrategy | None = None  # filename strategy; None for non-markdown kinds
    statuses: frozenset[str] | None = None          # controlled vocab; None = open set
    default_status: str | None = None
    shortform: str | None = None                    # single-letter alias, e.g. "h" -> hypothesis
    # SSOT placeholders consumed by later increments (left None in the keystone, see §6):
    # model_class: type[Entity] | None = None
    # entity_class: EntityClass | None = None
    # template: str | None = None


CORE_KINDS: tuple[KindDescriptor, ...] = (...)   # one entry per core kind (§3)
CORE_KINDS_BY_NAME: dict[str, KindDescriptor] = {k.name: k for k in CORE_KINDS}
```

Notes:
- `EntityFilenameStrategy` is **moved** here from `science_tool/entities.py` (it is part of the
  kind SSOT); the tool re-imports it. `EntityPathPolicy` stays in `science_tool` (it is a
  tool-side derivation target, not authored data).
- Frozen dataclass (matches the existing `EntityPathPolicy` style; data, not behavior).
- The later-increment fields are intentionally commented out of the keystone so we never
  transcribe data that no consumer reads yet (which would risk silent drift from the registry /
  `MIGRATED_KINDS`). Each field lands in the same increment as the consumer that reads it.

## §3. Manifest content & scope

`CORE_KINDS` enumerates **every core kind** (the `EntityType` roster). For the keystone:
- **Markdown-authored kinds** (the ~27 that appear in the four dicts) populate
  `path` / `strategy` / `statuses` / `default_status` / `shortform`, transcribed *verbatim* from
  today's literals in `science_tool/entities.py`.
- **Non-markdown kinds** (dataset, task, workflow-run, code-file, data-package, …) appear in the
  manifest with those fields left `None` — they are real core kinds but are not markdown-authored,
  so they have no path/status entry today.
- `model_class` / `entity_class` / `template` are `None` for all entries this increment.

Comments that annotate the current literals (e.g. *"was numeric (4c: slug identity kind)"* on
`topic`/`method`/`observation`) are carried over so the rationale is not lost.

## §4. Consumer rewiring (the keystone's actual code change)

All in `science_tool/entities.py`. **Delete** `_BUILTIN_MARKDOWN_POLICIES`, `_DEFAULT_STATUS`,
`_STATUS_VALUES`, `_SHORTFORM_ENTITY_KINDS`. Replace each with a thin derivation over
`CORE_KINDS`, filtering to entries that set the relevant field:

| Deleted structure | Derivation | Consumers preserved |
|---|---|---|
| `_BUILTIN_MARKDOWN_POLICIES` | `{k.name: EntityPathPolicy(k.path, k.strategy) for k in CORE_KINDS if k.path}` | path resolution, local-policy merge, `_CORE_HOME_DIR_NAMES` |
| `_DEFAULT_STATUS` | `{k.name: k.default_status for k in CORE_KINDS if k.default_status}` | `default_status()` core branch |
| `_STATUS_VALUES` | `{k.name: k.statuses for k in CORE_KINDS if k.statuses}` | `valid_statuses()` core branch |
| `_SHORTFORM_ENTITY_KINDS` | `{k.shortform: k.name for k in CORE_KINDS if k.shortform}` | shortform reference expansion |

These derived dicts may be built once at import (module-level), preserving the exact shapes the
existing functions consume — the functions' bodies barely change.

**Invariants that must hold unchanged:**
- **Project-local kind fallback is preserved verbatim.** `default_status()` and `valid_statuses()`
  fall back to the project `ProfileManifest` (`_local_entity_kind`) for non-core kinds; the
  keystone touches only the *core* lookup, not this fallback.
- **Local kinds may not shadow core kinds.** Today `_load_local_policies_and_warnings` skips a
  local kind whose name is in `_BUILTIN_MARKDOWN_POLICIES`; after the change it checks membership
  in the descriptor-derived core-policy map (same set, same behavior).
- **`_CORE_HOME_DIR_NAMES`** (used by the layout migrator to prevent local kinds from overwriting
  core homes) is derived from the same descriptor-derived policy map.
- **No `if kind in CORE_KINDS else legacy` branching** anywhere — the manifest is the sole core
  source.

## §5. Safety & tests

- **Guard test (zero-behavior-change):** the test file captures a *frozen copy* of the original
  four dict literals (pasted into the test), reconstructs each from `CORE_KINDS`, and asserts
  equality. This is the keystone's analogue of the Patch Contract build-gate invariant — it proves
  the data transcription is exact.
- **Descriptor-validation test:** `CORE_KINDS` has no duplicate `name`; every name that appears in
  any of the four original dicts has a `CORE_KINDS` entry (so the deletions are fully covered);
  `strategy == "singleton"` iff `path` points at a file (`.md`/`.yaml`), not a directory; every
  `shortform` is unique and single-character. (The exact relationship between the `CORE_KINDS`
  roster and the 48-member `EntityType` enum — which has more members than there are registered
  core kinds — is reconciled during implementation; the keystone requires only that every kind the
  four dicts configure is present.)
- **Regression:** the existing `tests/test_entities.py` plus path-resolution, status-validation,
  and layout-migration suites must stay green. Full suite green before merge.

## §6. Deferred to later increments (explicitly out of scope)

- **Increment 2 — registry:** `EntityRegistry.register_core_kind` iterates `CORE_KINDS` instead of
  ~20 hand-written calls; the `model_class` and `entity_class` descriptor fields are populated and
  guard-tested against the current registry.
- **Increment 3 — templates & profiles:** `MIGRATED_KINDS`/`templates/*.md` and the
  `ProfileManifest`/profile system fold onto descriptors; the `template` field is populated then.
- **Later:** required base-`Entity` field reduction; JSON-schema mixins; project-extension kinds
  expressed as descriptors rather than manifest-only.

## §7. Non-goals

- No change to runtime behavior for any kind (path, status vocab, default status, shortform all
  identical — enforced by the guard test).
- No new kinds; no removal of `EntityType` members.
- No touching of the registry, templates, or profile systems (their consumers still read their own
  structures this increment).
- No compatibility/shim layer (per project rule).

## §8. Open questions

None blocking. The model-class reference question (how `entity_class`/`model_class` are typed and
guard-tested) is deferred with increment 2, where it is the central concern.
