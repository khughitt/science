# Big-picture identity and neighborhood — implementation plan

> **For agentic workers:** implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix the nine live defects in the big-picture / graph-query surface, guard the one
already-shipped fix that has no test, and close all 13 feedback items.

**Design:** [`2026-07-11-big-picture-identity-design.md`](2026-07-11-big-picture-identity-design.md)

**Architecture:** Four roots. (A) The neighborhood walk discards the predicate, so `rdf:type`
forms a class hub — fix by walking the *entity* graph, which also yields CURIEs for free. (B)
The synthesis output path is composed rather than resolved. (C) Canonical-ID discipline is
enforced only after the write. (D) Three defects of measurement and order, plus a new
`disposition` axis separating epistemic verdict from workflow state.

**Tech stack:** Python 3.13, click, rdflib, pytest. Package root is `science/` — **there is no
root `pyproject.toml`**.

## Global constraints

- **Always `cd science/` (or `science/model/`) before any `uv run`.** Running from the repo
  root is the most common orientation mistake here.
- Validation: `cd science && uv run --frozen pytest`; `uv run ruff check`; `uv run pyright`;
  `uv run --frozen science skills lint --root ../skills`. Model: `cd science/model && uv run
  --frozen pytest`.
- **Two template copies.** `templates/<kind>.md` AND the packaged shadow
  `science/model/src/science_model/templates/<kind>.md`. A test asserts byte-identity and the
  **packaged** copy is what `Renderer` reads. Editing only the root silently changes nothing.
- `codex-skills/` is a **generated** mirror (`cd science && uv run --frozen python
  ../scripts/generate_codex_skills.py`). Only `commands/*.md` are mirrored. **No drift test** —
  regenerate any pre-existing drift in its **own** commit, first.
- Feedback terminal status is **`addressed`**. There is no `resolved`.
- No AI-attribution trailers. No "legacy"/"compat" layers. No `Unified` prefix. Composition over
  inheritance; explicit over defensive; fail early.
- Branch: `bigpicture-ids`, in the worktree
  `~/d/science/.claude/worktrees/instrument-result`. **Do not `cd` to the main checkout.**

---

## Task 1: Guard `entities/` in the manifest walk-set

The fix already shipped (`bbedacbe`); the guard did not. Today you can delete `pp.entities_dir`
from `include_dirs` and the whole suite still passes.

**Files:**
- Test: `science/tests/test_graph_io_revision_manifest.py`

- [ ] **Step 1: Write the failing test**

```python
def test_entities_dir_is_in_the_walk_set(tmp_path: Path) -> None:
    """`entities/` MUST be walked. It was omitted for two months (fb-2026-07-11-016),
    so a project could add a brand-new hypothesis and `graph diff` would report the
    graph 'up to date'. The fix landed without a guard; this is that guard.
    """
    (tmp_path / "entities" / "hypotheses").mkdir(parents=True)
    (tmp_path / "entities" / "hypotheses" / "0001-x.md").write_text("---\nid: hypothesis:0001-x\n---\n")
    (tmp_path / "knowledge").mkdir()

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")

    assert "entities" in manifest.walked
    assert any(key.startswith("entities/") for key in manifest.files), (
        "entities/ was walked but no entity file was recorded"
    )
```

- [ ] **Step 2: Run it — it must PASS** (the behavior is already correct)

`cd science && uv run --frozen pytest tests/test_graph_io_revision_manifest.py -k walk_set -v`

- [ ] **Step 3: Prove the guard can fail.** Temporarily comment out `pp.entities_dir` in
  `src/science_tool/graph/io.py:367`, re-run the test, and confirm it FAILS. Then restore the
  line. **A guard you have not seen fail is not a guard** — this is the estimator doctrine's
  Principle 2 applied to our own test.

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_graph_io_revision_manifest.py
git commit -m "test(graph): guard entities/ in the revision-manifest walk-set"
```

---

## Task 2: Walk the entity graph, not the RDF graph (fb-010, fb-011)

**Files:**
- Modify: `science/src/science_tool/graph/store/summary.py:30` (import), `:788` (adjacency),
  `:811` (degree), `:851` (entity emission)
- Test: `science/tests/` — the graph-summary/gaps test module

**Interfaces:**
- Consumes: `canonical_id_from_entity_uri(uri: str) -> str | None` from
  `science_tool.graph.store.identity` — returns `None` for any non-project-entity URI
  (including `sci:Hypothesis`), which is exactly the "is this a claim edge?" predicate.

- [ ] **Step 1: Write the failing test — three hypotheses, zero edges between them**

```python
def test_gaps_center_does_not_leak_across_the_rdf_type_hub(tmp_path: Path) -> None:
    """A 2-hop neighborhood must not include every entity of the same rdf:type.

    The adjacency previously discarded the predicate, so `hypothesis:X rdf:type
    sci:Hypothesis` made the CLASS node a hub: every hypothesis sat 1 hop from it and
    therefore 2 hops from every other. At the default hops=2 the 'neighborhood' was the
    whole project (fb-2026-07-11-010).
    """
    # Three hypotheses, NO edges between them.
    graph = _build_graph_with_hypotheses(tmp_path, ["0001-alpha", "0002-beta", "0003-gamma"])

    result = query_gaps(graph, center="hypothesis:0001-alpha", hops=2)

    entities = {row["entity"] for row in result.rows}
    assert entities == {"hypothesis:0001-alpha"}, (
        f"center leaked into unrelated hypotheses: {entities}"
    )


def test_gaps_emits_curies_not_iris(tmp_path: Path) -> None:
    """Rows must be citable. An IRI is flagged `nonexistent_reference` by the
    big-picture validator, so IRI rows were unusable at the point of use
    (fb-2026-07-11-011).
    """
    graph = _build_graph_with_hypotheses(tmp_path, ["0001-alpha"])
    result = query_gaps(graph, center="hypothesis:0001-alpha", hops=1)
    assert all(not row["entity"].startswith("http") for row in result.rows)
    assert result.rows[0]["entity"] == "hypothesis:0001-alpha"


def test_isolated_entity_has_degree_zero(tmp_path: Path) -> None:
    """The rdf:type edge previously counted as connectivity, so an entity with NO
    real edges reported degree=1. Schema edges are not claims.
    """
    graph = _build_graph_with_hypotheses(tmp_path, ["0001-alpha"])
    result = query_gaps(graph, center="hypothesis:0001-alpha", hops=1)
    assert "degree=0" in result.rows[0]["issues"]
```

- [ ] **Step 2: Run — expect 3 failures** (3 rows not 1; `http://…` entity; `degree=1`)

- [ ] **Step 3: Import the identity helper** — `summary.py:30`

```python
from .identity import _graph_uri, _resolve_center_entity, _short_name, canonical_id_from_entity_uri, entity_in_graph
```

- [ ] **Step 4: Build adjacency over entity→entity edges only** — replace `summary.py:786-792`

```python
    # BFS over the ENTITY graph, not the RDF graph. An edge is admissible iff BOTH
    # endpoints are project entities. Discarding the predicate (the old `for subj, _, obj`)
    # admitted `rdf:type`, which made each CLASS node a hub: every hypothesis sat 1 hop from
    # sci:Hypothesis and therefore 2 hops from every other hypothesis. At the default hops=2
    # the "neighborhood" was the entire project (fb-2026-07-11-010).
    #
    # Do NOT special-case rdf:type. ANY predicate whose object is a shared vocabulary term
    # forms the same hub. The invariant is about the ENDPOINTS, not the predicate.
    adjacency: dict[URIRef, set[URIRef]] = {}
    for subj, _, obj in knowledge:
        if not isinstance(subj, URIRef) or not isinstance(obj, URIRef):
            continue
        if canonical_id_from_entity_uri(str(subj)) is None:
            continue
        if canonical_id_from_entity_uri(str(obj)) is None:
            continue
        adjacency.setdefault(subj, set()).add(obj)
        adjacency.setdefault(obj, set()).add(subj)
```

- [ ] **Step 5: Emit the CURIE** — `summary.py:849-855`

```python
            # Every node that survived the walk IS a project entity, so this cannot be
            # None -- the walk already established it. Emitting the IRI made gaps rows
            # uncitable: the big-picture validator flags an IRI as nonexistent_reference,
            # so subagents dropped the findings (fb-2026-07-11-011).
            canonical = canonical_id_from_entity_uri(str(uri))
            assert canonical is not None  # guaranteed by the adjacency filter above
            rows.append(
                {
                    "entity": canonical,
                    "label": label,
                    "issues": "; ".join(issues),
                }
            )
```

Note the center itself is added to `visited` before the walk, so it must also pass the entity
test — verify `_resolve_center_entity` yields a project-entity URI, and if a non-entity center
is possible, return `InstrumentResult.unwired(code="center_not_an_entity", …)` rather than
emitting a row with no CURIE.

- [ ] **Step 6: Run the tests — expect PASS**

- [ ] **Step 7: Run the FULL suite and read the diff in `low_connectivity` findings.**

`cd science && uv run --frozen pytest`

**Expect other tests to change, and do not silence them.** The `degree <= 1` threshold at
`summary.py:812` was calibrated against *inflated* degrees. Previously an isolated node read
`degree=1` and a node with exactly one real edge read `degree=2` (and so was **not** flagged).
After this fix the isolated node reads `0` and the one-edge node reads `1` — so **one-real-edge
nodes now correctly get flagged as low-connectivity**. More findings, not fewer. That is the
correct behavior (a node with a single connection *is* low-connectivity), but it will look like
a regression. Any test that asserted the old counts must be updated **with a comment saying
why**, not adjusted to match.

Note also the inflation was never uniform: a node with many schema annotations looked better
connected than one with few, independent of its actual claims. The metric was not merely
shifted — it was *inconsistently* shifted.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/graph/store/summary.py science/tests/
git commit -m "fix(graph): walk the entity graph, not the RDF graph

The gaps adjacency discarded the predicate, so rdf:type made each class node a
hub: every hypothesis sat 1 hop from sci:Hypothesis and 2 hops from every other
hypothesis. At the default hops=2 a 'neighborhood' was the whole project, and 29
mm30 subagents each discarded the same six irrelevant rows by hand.

Admit an edge only when BOTH endpoints are project entities. This also makes
degree a real entity degree (an isolated node was reporting degree=1 -- that 1
was the type edge) and lets rows carry CURIEs, which makes them citable."
```

---

## Task 3: The Arc word cap must not count entity IDs (fb-015)

**Ships before Task 4.** Task 4 tells agents to cite *full canonical IDs* — the longest tokens
in the document — while this cap charges by the word for exactly those tokens. Shipping Task 4
first would tighten a rule and penalise compliance with it in the same release.

**Files:**
- Modify: `science/src/science_tool/big_picture/validator.py:74-77`
- Test: the big-picture validator test module

- [ ] **Step 1: Write the failing test**

```python
def test_arc_word_cap_excludes_entity_ids(tmp_path: Path, project: Path) -> None:
    """The 150-word Arc cap measures PROSE VERBOSITY. An entity ID is not prose.

    Long canonical slugs each counted as a word, so the cap penalised the agents that
    cited most carefully -- mm30's only two violations (154 and 163 words) were caused
    by citation density, not verbosity (fb-2026-07-11-015). Task 4 makes this strictly
    worse by requiring full-length IDs, so the two must ship together.
    """
    citations = " ".join(
        f"interpretation:{i:04d}-t869-bcl2-dependency-venetoclax-hmcl-p3-supported"
        for i in range(40)
    )
    prose = " ".join(["word"] * 100)          # 100 words of actual prose -- under the cap
    path = _write_synthesis(tmp_path, provenance_coverage="thin", arc=f"{prose} {citations}")

    result = validate_synthesis_file(path, project_root=project)

    assert not [i for i in result.rows if i.kind == "thin_coverage_marker_mismatch"], (
        "citation density was charged as verbosity"
    )
```

- [ ] **Step 2: Run — expect FAIL** (140 "words" > 150? no — 100 prose + 40 IDs = 140; raise the
  citation count until it exceeds 150 and confirm the test fails for the *right* reason before
  fixing. The point is that prose alone is well under the cap.)

- [ ] **Step 3: Strip entity IDs before counting** — `validator.py:74-77`

```python
    fm = read_frontmatter(path) or {}
    if fm.get("provenance_coverage") == "thin":
        arc = _extract_section(text, "Arc")
        # The cap measures PROSE verbosity. Entity IDs are citations, not prose, and
        # canonical slugs are long -- charging by the word penalised the sections that
        # cited most carefully (fb-2026-07-11-015). REFERENCE_PATTERN is already the
        # project's definition of "this token is a citation"; reuse it rather than
        # inventing a second one.
        prose_only = REFERENCE_PATTERN.sub("", arc)
        word_count = len(prose_only.split())
        if word_count > 150:
```

- [ ] **Step 4: Run — expect PASS.** Also add a test that a genuinely verbose Arc (200 words of
  prose, no citations) still trips the cap — otherwise you have built a check that cannot fail.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/big_picture/validator.py science/tests/
git commit -m "fix(big-picture): the Arc word cap measures prose, not citations"
```

---

## Task 4: Canonical-ID discipline at the boundary (fb-003, fb-012)

**Files:**
- Modify: `science/src/science_tool/big_picture/validator.py` (prefix expansion)
- Modify: `science/src/science_tool/big_picture/cli.py:52-60` (`--staged`)
- Modify: `agents/emergent-threads-synthesizer.md` (the never-truncate rule is missing here)
- Test: the big-picture validator + CLI test modules

**Do not** write more emphatic prose telling agents to try harder. natural-systems ran 4-of-14
truncations *against* an already-emphatic prohibition. That experiment has been run.

- [ ] **Step 1: Write the failing tests**

```python
def test_unique_numeric_prefix_expands_to_the_canonical_id(tmp_path, project) -> None:
    """`interpretation:0192` -> `interpretation:0192-t869-...`. The mapping is
    deterministic and both reporting projects wrote the same expansion script by hand
    (fb-2026-07-11-012). 76 of mm30's 84 first-pass issues were this one cause.
    """
    path = _write_synthesis(tmp_path, body="See interpretation:0192 for the argument.")
    result = validate_synthesis_file(path, project_root=project)
    assert not [i for i in result.rows if i.kind == "nonexistent_reference"]


def test_ambiguous_numeric_prefix_fails_loudly(tmp_path, project) -> None:
    """A prefix matching TWO canonical IDs must NOT be guessed. The failure mode we are
    removing is a human running a repair script; the failure mode we must not introduce
    is a tool silently citing the wrong entity.
    """
    # project fixture contains question:0042-alpha AND question:0042b-beta
    path = _write_synthesis(tmp_path, body="See question:0042 for the argument.")
    result = validate_synthesis_file(path, project_root=project)
    issues = [i for i in result.rows if i.kind == "ambiguous_reference"]
    assert issues, "an ambiguous prefix was silently resolved"
    assert "0042" in issues[0].message
```

- [ ] **Step 2: Run — expect FAIL** (`nonexistent_reference` on both; no `ambiguous_reference`
  kind exists yet)

- [ ] **Step 3: Add `ambiguous_reference` to the `IssueKind` literal** (top of `validator.py`,
  the list ending at `:25`).

- [ ] **Step 4: Expand unambiguous prefixes; fail loudly on ambiguity** — replace the
  `REFERENCE_PATTERN` loop at `validator.py:61-71`

```python
    # Index canonical IDs by their <kind>:<numeric-prefix>, so a truncated citation can be
    # expanded deterministically. Agents truncate despite an emphatic prohibition -- 4 of 14
    # in natural-systems, 76 of 84 first-pass issues in mm30 -- so prompt hardening is not a
    # fix, and this is not a "be lenient" concession: the mapping IS deterministic when the
    # prefix is unique, and MUST NOT be guessed when it is not.
    by_prefix: dict[str, list[str]] = {}
    for known in known_ids:
        kind, _, ident = known.partition(":")
        prefix = ident.split("-", 1)[0]
        if prefix and prefix != ident:
            by_prefix.setdefault(f"{kind}:{prefix}", []).append(known)

    for match in REFERENCE_PATTERN.finditer(text):
        kind, ident = match.group(1), match.group(2)
        full_id = f"{kind}:{ident}"
        if full_id in known_ids:
            continue
        candidates = by_prefix.get(full_id, [])
        if len(candidates) == 1:
            continue  # unique prefix -> deterministic expansion; not an issue
        if len(candidates) > 1:
            issues.append(
                ValidationIssue(
                    kind="ambiguous_reference",
                    message=(
                        f"Reference {full_id} is a truncated prefix matching "
                        f"{len(candidates)} entities: {', '.join(sorted(candidates))}. "
                        "Cite the full canonical ID."
                    ),
                    path=path,
                )
            )
            continue
        issues.append(
            ValidationIssue(
                kind="nonexistent_reference",
                message=f"Reference {full_id} does not exist in project.",
                path=path,
            )
        )
```

- [ ] **Step 5: Add `--staged <dir>` to the validate command** — `big_picture/cli.py:52-60`.
  Validate files in the staged directory against the *project's* known IDs, so truncation is
  caught **before** canonical entities are overwritten. Today validation is strictly post-hoc
  (`validator.py:1`), so every repair is done against already-published files.

```python
@click.option(
    "--staged",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=None,
    help="Validate generated files in this staging directory instead of entities/synthesis/, "
    "before they are reconciled into canonical entities.",
)
```

Point `synthesis_dir` at `staged` when given. Everything downstream is unchanged — the known-ID
corpus still comes from `project_root`.

- [ ] **Step 6: Close the spec asymmetry.** `agents/hypothesis-synthesizer.md:64` carries the
  never-truncate rule; `agents/emergent-threads-synthesizer.md:60` does not. Add the *same* rule
  there. This is correcting an omission, not raising the volume.

- [ ] **Step 7: Run tests — expect PASS.** Full suite.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/big_picture/ agents/emergent-threads-synthesizer.md science/tests/
git commit -m "fix(big-picture): expand unambiguous ID prefixes; validate staged output

Agents truncate canonical IDs despite an emphatic prohibition (4/14 in
natural-systems; 76 of 84 first-pass issues in mm30). Prompt hardening has been
tried and measured. The prefix->canonical mapping is deterministic when unique,
so expand it -- and fail loudly, never guess, when it is not.

--staged lets the orchestrator validate before reconciliation, so truncation is
caught before canonical entities are overwritten rather than after."
```

---

## Task 5: Resolve the synthesis path; correct the stale v2 agent specs (fb-002, fb-013)

**Files:**
- Create: a resolver in `science/src/science_tool/big_picture/` (mirror
  `digests.py:108 load_cluster_digests`, which already does exactly this for
  `report_kind: cluster-digest`)
- Modify: `agents/hypothesis-synthesizer.md:3,24`, `agents/emergent-threads-synthesizer.md:3,10,18`
- Modify: `commands/big-picture.md:141,161`

- [ ] **Step 1: Write the failing test**

```python
def test_synthesis_path_resolves_to_an_existing_numbered_entity(tmp_path: Path) -> None:
    """mm30 and natural-systems store synthesis as NUMBERED canonical entities
    (0022-epigenetic-commitment.md) bound to a hypothesis by frontmatter. Composing
    `<hyp-id>.md` would create 29 NEW files beside the 15 existing ones -- duplicate
    synthesis entities for the same hypotheses (fb-2026-07-11-013).
    """
    d = tmp_path / "entities" / "synthesis"
    d.mkdir(parents=True)
    (d / "0022-epigenetic-commitment.md").write_text(
        "---\nid: synthesis:0022-epigenetic-commitment\n"
        "report_kind: hypothesis-synthesis\nhypothesis: hypothesis:0007-abc\n---\n"
    )

    resolved = resolve_synthesis_path(tmp_path, "hypothesis:0007-abc")
    assert resolved == d / "0022-epigenetic-commitment.md"


def test_synthesis_path_falls_back_when_no_prior_file(tmp_path: Path) -> None:
    """Partial coverage is NORMAL -- mm30's prior run covered 15 of 29 hypotheses."""
    (tmp_path / "entities" / "synthesis").mkdir(parents=True)
    resolved = resolve_synthesis_path(tmp_path, "hypothesis:0007-abc")
    assert resolved.name == "0007-abc.md"
```

- [ ] **Step 2: Run — expect FAIL** (`resolve_synthesis_path` does not exist)

- [ ] **Step 3: Implement `resolve_synthesis_path`**, scanning `entities/synthesis/` for
  `report_kind: hypothesis-synthesis` and matching the `hypothesis:` frontmatter field. Fall back
  to `<hyp-id>.md` **only** when no prior file exists. Follow the shape of `load_cluster_digests`.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Correct the agent specs.** Both still name the **v2** path
  `doc/reports/synthesis/…`. The command says `entities/synthesis/…`. At runtime the
  dispatcher's inlined path wins, so output currently lands correctly — but an agent following
  its own spec writes where nothing reads. Replace with: *"Your target output path is supplied
  by the orchestrator. Write to exactly that path — do not compose one from the hypothesis ID."*

- [ ] **Step 6: Update `commands/big-picture.md`** so the orchestrator resolves the path and
  passes it to the agent, rather than documenting `<hyp-id>.md` as the target.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/big_picture/ agents/ commands/big-picture.md science/tests/
git commit -m "fix(big-picture): resolve the synthesis output path instead of composing it"
```

---

## Task 6a: Enforce the status vocabulary on committed files

The smallest fix with the largest reach. `entities.py:1374` validates status on **CLI writes
only** — hand-authored frontmatter is never re-checked, and `science validate` has **no
status-vocabulary check at all**. That is how `status: retired` (a **task** status —
`TaskStatus.RETIRED`, `tasks.py:737`) reached a committed hypothesis file in natural-systems.

This check alone would have caught fb-005 at commit time, and it protects **every** entity kind,
none of which are checked today.

**Files:**
- Create: a check in `science/src/science_tool/validate/checks/`
- Test: the corresponding validate-checks test module

- [ ] **Step 1: Write the failing test**

```python
def test_out_of_vocabulary_status_is_flagged(tmp_path: Path) -> None:
    """`retired` is a TASK status. It is NOT in the hypothesis vocabulary
    (proposed | under-investigation | partially-supported | supported | weakened |
    refuted | archived). natural-systems committed it anyway and nothing said a word
    (fb-2026-07-11-005).
    """
    _write_entity(tmp_path, "hypotheses/0009-x.md", id="hypothesis:0009-x", status="retired")
    issues = run_status_vocabulary_check(tmp_path)
    assert any("retired" in i.message and "hypothesis" in i.message for i in issues)
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Derive the vocabulary from the Kind Descriptors. Do NOT write a second table.**

`entities.allowed_statuses(kind, project_root)` (`entities.py:270-277`) is already the single
derivation and must be the **only** source:

- **core kinds** → `_STATUS_VALUES`, which is itself built from `_KIND_DESCRIPTORS`
  (`entities.py:187`) — the Kind Descriptor *is* the SSOT;
- **local-profile kinds** → `_local_entity_kind(project_root, kind)`;
- **a kind declaring no `statuses`** → returns `None`, meaning an **open set**. Skip it. An open
  vocabulary is a deliberate declaration, not a gap, and flagging it would make the check fire on
  kinds that never promised a closed set.
- **an unknown kind** → `allowed_statuses` raises `KeyError`. That is **not this check's job** —
  unknown kinds are already reported as `unknown_entity_kind` by the source loader
  (`sources.py:151`). Catch it and skip, so `validate` does not crash on an entity another check
  already owns. Two checks reporting the same defect is worse than one.

A hard-coded kind→status table in this check would be the same defect as the per-kind lists in
`document_structure.py` that the estimator doctrine's follow-on already indicts. Do not add a
fourth one.

- [ ] **Step 4: Add the tests that pin the derivation, not just the happy path**

```python
def test_local_profile_kind_status_vocabulary_is_enforced(tmp_path) -> None:
    """A project-declared kind's statuses come from its profile manifest, not from a
    table in this check."""
    _write_local_profile(tmp_path, kind="protocol", statuses=["drafted", "ratified"])
    _write_entity(tmp_path, "protocols/0001-x.md", id="protocol:0001-x", status="bogus")
    assert any("bogus" in i.message for i in run_status_vocabulary_check(tmp_path))


def test_open_vocabulary_kind_is_skipped(tmp_path) -> None:
    """A kind declaring NO statuses has an OPEN set. That is a declaration, not a gap --
    any status is legal and the check must stay silent."""
    _write_local_profile(tmp_path, kind="note", statuses=[])
    _write_entity(tmp_path, "notes/0001-x.md", id="note:0001-x", status="whatever")
    assert not run_status_vocabulary_check(tmp_path)


def test_unknown_kind_does_not_crash_the_check(tmp_path) -> None:
    """`allowed_statuses` raises KeyError for an unregistered kind. That defect is
    already owned by `unknown_entity_kind` in the source loader -- this check must skip,
    not crash and not double-report."""
    _write_entity(tmp_path, "aliens/0001-x.md", id="alien:0001-x", status="green")
    assert not run_status_vocabulary_check(tmp_path)  # and no exception
```

- [ ] **Step 5: Run — expect PASS. Then run the full suite and expect real fixtures to trip.**
  If a fixture carries an out-of-vocabulary status, that is a **finding**, not a test to relax.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/validate/ science/tests/
git commit -m "feat(validate): check entity status against its kind's declared vocabulary"
```

---

## Task 6b: The `disposition` axis (fb-005)

Implements design §5.2. **`status` is the epistemic verdict; `disposition` is the workflow
state; neither may be inferred from the other.** Do **not** add `retired` to `phase` — `phase`
is the *commitment* axis (`candidate` | `active`) and a lifecycle value there is a category
error.

### 6b.0 Adoption semantics — decide these BEFORE writing code

**Migration: `disposition` defaults to `open`. Existing hypotheses are NOT migrated.**

The default is not a convenience — it is the *correct* value. An existing hypothesis that nobody
has closed **is** open. There is no fact to migrate.

**The default MUST NOT be inferred from `status`.** A hypothesis with `status: refuted` and no
`disposition` becomes `disposition: open` — **not** `closed`. Inferring closure from a terminal
epistemic status would re-collapse the two axes this task exists to separate, and would silently
close hypotheses whose authors never said to. *Refuted and still being worked* is a legitimate,
common state (you are writing it up; you are probing why it failed).

Closure is therefore always an **explicit authored act**, and `disposition: closed` requires
`disposition_basis`. Nothing in this task closes anything on an author's behalf.

**Round-trip: the field must survive every hop, or it does not exist.**

`Entity` (`model/src/science_model/entities.py:299`) declares **no `model_config`**, so Pydantic
defaults to `extra="ignore"`. Frontmatter is loaded through `schema.model_validate(raw)`
(`graph/sources.py:377`), which **silently drops every key that is not a model field**.

**This has already happened, to `phase` itself.** `phase` is in the template known-keys set
(`templates.py:31`) but is **not a field on `Entity`** — so it is dropped at load and **never
reaches the graph**. The big-picture command only "sees" it by reading frontmatter directly. It
is decoration, not data. (This is also the mechanical reason the withdrawn `phase: retired`
proposal could never have worked: attention ranking is **graph**-based, and the graph cannot see
`phase`.)

So `disposition` must be wired at **five** layers, and the last one is the one that gets
forgotten:

1. a field on the **hypothesis kind** (`profiles/core.py`);
2. a field on **`Entity`** (`model/src/science_model/entities.py`) — *without this it is dropped
   at `model_validate` and nothing downstream ever sees it*;
3. the **template known-keys** set (`templates.py`);
4. **both** template copies — `templates/hypothesis.md` **and** the packaged
   `science/model/src/science_model/templates/hypothesis.md`, which is the one `Renderer` reads;
5. **materialized to a triple** in `materialize.py`, so graph consumers (attention ranking) can
   act on it.

**Validation:** `disposition` is a closed vocabulary (`open` | `closed`) and `disposition_basis`
is required when `closed`. Both are enforced at load, so an invalid value fails loudly rather
than being ignored.

- [ ] **Step 0: Write the round-trip test FIRST. It is the test that would have caught `phase`.**

```python
def test_disposition_round_trips_from_frontmatter_to_graph(tmp_path: Path) -> None:
    """Author -> Entity -> graph -> query. Every hop.

    `Entity` is `extra="ignore"`, so a field that is not declared on the model is
    SILENTLY DROPPED at `schema.model_validate(raw)`. That is exactly what happened to
    `phase`: it lives in the template known-keys set, is absent from `Entity`, and
    therefore never reaches the graph. A field that does not survive this test does not
    exist, however correct it looks in the template.
    """
    _write_hypothesis(tmp_path, id="hypothesis:0009-x", status="refuted",
                      disposition="closed", disposition_basis="pre-registration:0004-t078")

    sources = load_project_sources(tmp_path)
    entity = next(e for e in sources.entities if e.id == "hypothesis:0009-x")
    assert entity.disposition == "closed"          # survived model_validate

    graph = materialize(sources)
    assert _has_triple(graph, "hypothesis:0009-x", SCI_NS.disposition, "closed")  # survived emit


def test_disposition_defaults_to_open_and_is_never_inferred_from_status(tmp_path) -> None:
    """A refuted hypothesis with no authored disposition is OPEN. Inferring closure from
    a terminal epistemic status would re-collapse the two axes this field separates --
    and would close hypotheses whose authors never said to.
    """
    _write_hypothesis(tmp_path, id="hypothesis:0009-x", status="refuted")  # no disposition
    entity = _load_one(tmp_path, "hypothesis:0009-x")
    assert entity.disposition == "open"


def test_closed_requires_a_basis(tmp_path) -> None:
    with pytest.raises(ValidationError):
        _write_and_load_hypothesis(tmp_path, disposition="closed")  # no disposition_basis
```

- [ ] **Step 0b: Prove the round-trip test can fail.** Add the field to `Entity` *last*: first
  wire layers 1, 3, 4, 5 and confirm the round-trip test **FAILS at the `model_validate` hop**
  with the field silently absent. That failure is `phase`'s bug, reproduced on demand. Only then
  add the `Entity` field and watch it pass. A round-trip test you have not seen fail at the drop
  point does not guard the drop point.

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py` (hypothesis kind)
- Modify: `science/model/src/science_model/entities.py` (**the `Entity` field — layer 2**)
- Modify: `science/model/src/science_model/templates.py` (known-keys)
- Modify: **both** `templates/hypothesis.md` **and**
  `science/model/src/science_model/templates/hypothesis.md` — the packaged copy is what
  `Renderer` reads; a root-only edit changes nothing an author sees
- Modify: `science/src/science_tool/graph/materialize.py` (**emit the triple — layer 5**)
- Modify: `science/src/science_tool/graph/attention.py` (terminal exclusion; re-homing debt)
- Modify: the Candidate-frames selection in `commands/big-picture.md:208`

- [ ] **Step 1: Write the failing tests — the orthogonality table from design §5.2.3**

```python
@pytest.mark.parametrize(
    "status,disposition",
    [
        ("refuted", "open"),               # disproved, still being written up
        ("supported", "closed"),           # confirmed and done
        ("under-investigation", "closed"), # closed for PRAGMATIC reasons -- epistemically undecided
        ("refuted", "closed"),
    ],
)
def test_status_and_disposition_are_independent(tmp_path, status, disposition) -> None:
    """The third case is the one `status: retired` CANNOT represent without lying."""
    path = _create_hypothesis(tmp_path, status=status, disposition=disposition)
    fm = read_frontmatter(path)
    assert fm["status"] == status and fm["disposition"] == disposition


def test_terminal_hypothesis_does_not_lead_attention(tmp_path) -> None:
    """Today a refuted hypothesis TOPS the ranking: open_question_debt=10 and 27
    incoming bears_on put the hypothesis we believe least at the top of the work
    queue. Being disproved currently makes a hypothesis MORE attention-worthy.
    """
    ranked = _rank(tmp_path, terminal_hypothesis_with_10_open_questions())
    assert ranked[0].id != "hypothesis:0009-x"


def test_terminal_hypothesis_stays_queryable_and_provenance_visible(tmp_path) -> None:
    """Closure is NOT hiding. _LIVE_STATUSES is unchanged; sci:supersedes lineage must
    survive materialization.
    """
    assert _in_graph(tmp_path, "hypothesis:0009-x")


def test_questions_on_a_terminal_hypothesis_become_rehoming_debt(tmp_path) -> None:
    """Closing a hypothesis does not close its questions -- it UNHOUSES them. If they
    vanish from attention alongside their hypothesis, closure converts a visible debt
    into an invisible one, which is worse than the bug being fixed.
    """
    debt = _rehoming_debt(tmp_path)
    assert len(debt) == 10
```

- [ ] **Step 2: Run — expect FAIL.** **Step 3:** add `disposition` (`open` | `closed`, default
  `open`) to the hypothesis kind + **both** template copies; add `disposition_basis`, **required
  when `closed`**. **Step 4:** exclude terminal hypotheses from Candidate-frames selection and
  from ordinary attention ranking, keeping them materialized and queryable. **Step 5:** surface
  questions resolving to a terminal hypothesis as **re-homing debt** — ranked, countable, named.

- [ ] **Step 6: Transition authority.** Auto-transition to `refuted` is licensed **only** when a
  linked pre-registration declares the decision rule, **the result satisfies it**, *and* **the
  Estimator Certification Gate passed**. Write the test that an **uncertified** estimator
  **cannot** drive an auto-refutation:

```python
def test_uncertified_estimator_cannot_auto_refute(tmp_path) -> None:
    """From the doctrine merged in 386326c1: a null result licenses refutation only if
    the instrument could have detected the effect. With E > rho*sigma_null(T) the null is
    INDETERMINATE, not negative. An uncertified estimator cannot refute anything.

    This is exactly hypothesis:0009's situation -- 'rejected by a pre-registered
    confirmatory null, z = -0.889'. |z| = 0.889 is NON-SIGNIFICANT: the study failed to
    confirm; it did not reject. The correct status was `weakened`, which already existed.
    """
    with pytest.raises(RefutationNotLicensed):
        auto_transition(tmp_path, hypothesis="hypothesis:0009-x", prereg=uncertified_prereg())
```

Closing is always authorable. **Refuting is not.**

- [ ] **Step 7:** Verify the packaged template actually changed:
  `cd science && uv run --frozen science entity sections hypothesis --format json`, and confirm
  byte-identity between the two copies. **Step 8:** full suite + `cd science/model && uv run
  --frozen pytest`.

- [ ] **Step 9: Commit**

```bash
git add science/model/ science/src/ templates/ commands/ science/tests/
git commit -m "feat(hypothesis): separate epistemic verdict from workflow disposition

status is what the evidence says; disposition is whether the hypothesis is still an
object of active work. Collapsing them into `status: retired` destroyed the epistemic
fact -- and recorded a refutation that never happened (z=-0.889 is non-significant:
the study failed to confirm, it did not reject).

Terminal hypotheses leave Candidate frames and the attention ranking but stay
queryable and provenance-visible. Their open questions become explicit re-homing debt
rather than vanishing. Auto-refutation requires a passing Estimator Certification
Gate: an uncertified estimator cannot refute anything."
```

---

## Task 7: Validate before stamping (fb-006)

A provenance record stamped before its subject is final is not provenance.

**Files:** `commands/big-picture.md:212-217` (stamp), `:270` (validate)

- [ ] **Step 1:** Reorder the documented phases so per-hypothesis files are **validated before**
  the rollup stamps `synthesized_from` SHAs — or re-stamp after any repair loop. The current
  order lets a legitimate validator rejection (e.g. Task 3's Arc cap) trigger a re-dispatch that
  rewrites the file, changes its SHA, and silently invalidates the rollup that already attested
  to the old one. Nothing re-checks it; the staleness warning fires only on the *next* run and is
  explicitly *"informational — do not block execution."*
- [ ] **Step 2:** Commit.

---

## Task 8: Regenerate the mirror; close the tickets

- [ ] **Step 1: Regenerate** `codex-skills/`:
  `cd science && uv run --frozen python ../scripts/generate_codex_skills.py`
- [ ] **Step 2:** Confirm **only** the command files this branch touched appear in the diff. Any
  unrelated file means pre-existing drift — commit that **separately** and first.
- [ ] **Step 3: Full gates.** `pytest` (science + model), `ruff check`, `pyright`,
  `science skills lint --root ../skills`. All must be green.
- [ ] **Step 4: Close all 13.** Terminal status is **`addressed`** — there is no `resolved`.

```bash
cd science
for id in 002 003 004 005 006 010 011 012 013 014 015 016 023; do
  uv run --frozen science feedback update "fb-2026-07-11-$id" --status addressed
done
uv run --frozen science feedback list --status open --format json   # confirm none of the 13 remain
```

Note `-004`, `-014`, `-016`, `-023` were fixed by the InstrumentResult convergence and are being
closed as **already-addressed** (Task 1 supplies `-016`'s missing guard). Say so in the
resolution text rather than implying this branch fixed them.

- [ ] **Step 5: Commit.**

---

## Self-review

- **Spec coverage:** design §2 → Task 2; §3 → Task 5; §4 → Tasks 3+4; §5.1 → Task 3; §5.2 →
  Tasks 6a+6b; §5.3 → Task 7; §1 (already-fixed four) → Tasks 1+8.
- **Ordering hazards, both load-bearing:** Task 3 **before** Task 4 (or the ID rule penalises
  itself); Task 6a **before** Task 6b (the vocabulary check would have caught the original
  defect on its own, and lands without a model change).
- **Two known traps, both previously bitten:** the packaged template shadow (Task 6b) and
  pre-existing `codex-skills/` drift (Task 8, regenerate separately and first).
