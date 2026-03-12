# Graph Checks in validate.sh — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add knowledge graph validation checks to `validate.sh` so projects with `knowledge/graph.trig` get structural feedback during the standard validation workflow.

**Architecture:** Add an orphaned-node check to `validate_graph()` in store.py (TDD), then add section 13 to `scripts/validate.sh` that shells out to `science-tool graph validate` and `science-tool graph diff` when `knowledge/graph.trig` exists. Parse JSON output in bash.

**Tech Stack:** Python (rdflib, click, pytest), Bash

---

### Task 1: Add orphaned node check — failing test

**Files:**
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing test**

Add this test after the existing `test_graph_validate_fails_on_causal_cycle` test:

```python
def test_graph_validate_warns_orphaned_nodes() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        # Add a concept with no edges (only rdf:type triple)
        assert (
            runner.invoke(
                main,
                ["graph", "add", "concept", "Orphan Node", "--type", "biolink:Gene"],
            ).exit_code
            == 0
        )

        result = runner.invoke(main, ["graph", "validate", "--format", "json"])
        # Orphan check should be a warning (status=warn), not a failure
        assert result.exit_code == 0

        payload = json.loads(result.output)
        orphan_rows = [r for r in payload["rows"] if r["check"] == "orphaned_nodes"]
        assert len(orphan_rows) == 1
        assert orphan_rows[0]["status"] == "warn"
        assert "1" in orphan_rows[0]["details"]
```

**Step 2: Run test to verify it fails**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_validate_warns_orphaned_nodes -v`
Expected: FAIL — no `orphaned_nodes` check exists yet.

---

### Task 2: Add orphaned node check — implementation

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py` (in `validate_graph`, before `has_failures` line)

**Step 1: Add the orphaned node check**

Insert before the final `has_failures = ...` line in `validate_graph()`:

```python
    # Orphaned nodes: entities with rdf:type but no other triples as subject or object
    typed_entities = set()
    for entity_type in (SCI_NS.Concept, SCI_NS.Claim, SCI_NS.Hypothesis, SCI_NS.Question):
        for entity, _, _ in knowledge.triples((None, RDF.type, entity_type)):
            typed_entities.add(entity)
    for entity, _, _ in knowledge.triples((None, RDF.type, SCIC_NS.Variable)):
        typed_entities.add(entity)

    orphaned = 0
    for entity in typed_entities:
        # Count triples where entity appears as subject (excluding rdf:type)
        as_subject = sum(1 for _, p, _ in knowledge.triples((entity, None, None)) if p != RDF.type)
        # Count triples where entity appears as object
        as_object = sum(1 for _ in knowledge.triples((None, None, entity)))
        if as_subject == 0 and as_object == 0:
            orphaned += 1

    if orphaned:
        rows.append(
            {
                "check": "orphaned_nodes",
                "status": "warn",
                "details": f"{orphaned} entities have no edges (only rdf:type)",
            }
        )
    else:
        rows.append(
            {
                "check": "orphaned_nodes",
                "status": "pass",
                "details": "all entities have at least one edge",
            }
        )
```

Note: orphaned nodes use `status: "warn"` not `"fail"` — they're informational, not blocking. The `has_failures` line already only checks for `"fail"`, so this won't change exit codes.

**Step 2: Run test to verify it passes**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_graph_validate_warns_orphaned_nodes -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py -v`
Expected: all tests pass (existing `test_graph_validate_passes_on_fresh_graph` should still pass since a fresh graph has no entities)

**Step 4: Lint and type check**

Run: `cd science-tool && uv run --frozen ruff check . && uv run --frozen ruff format --check .`
Expected: clean

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_graph_cli.py
git commit -m "feat: add orphaned node check to graph validate"
```

---

### Task 3: Add section 13 to validate.sh

**Files:**
- Modify: `scripts/validate.sh` (insert new section before the Summary section)

**Step 1: Add graph checks section**

Insert before the `# ─── Summary` line:

```bash
# ─── 13. Knowledge graph checks ──────────────────────────────────
echo ""
echo "Checking knowledge graph..."

if [ -f "knowledge/graph.trig" ]; then
    # Resolve science-tool command
    SCIENCE_TOOL=""
    if command -v science-tool &>/dev/null; then
        SCIENCE_TOOL="science-tool"
    elif command -v uv &>/dev/null && uv run science-tool --help &>/dev/null 2>&1; then
        SCIENCE_TOOL="uv run science-tool"
    fi

    if [ -z "$SCIENCE_TOOL" ]; then
        error "knowledge/graph.trig exists but science-tool is not available (install via uv or add to PATH)"
    else
        info "Using: ${SCIENCE_TOOL}"

        # 13a-d: Run graph validate (parseable, provenance, acyclicity, orphaned)
        validate_output=$($SCIENCE_TOOL graph validate --format json --path knowledge/graph.trig 2>&1) || true
        if printf "%s" "$validate_output" | python3 -c "import sys,json; json.load(sys.stdin)" &>/dev/null; then
            while IFS= read -r row; do
                check=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['check'])")
                status=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
                details=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['details'])")

                if [ "$status" = "fail" ]; then
                    error "graph validate: ${check} — ${details}"
                elif [ "$status" = "warn" ]; then
                    warn "graph validate: ${check} — ${details}"
                else
                    info "graph validate: ${check} — ${details}"
                fi
            done < <(printf "%s" "$validate_output" | python3 -c "
import sys, json
for row in json.load(sys.stdin)['rows']:
    print(json.dumps(row))
")
        else
            error "graph validate produced unparseable output"
        fi

        # 13e: Graph-prose sync staleness
        diff_output=$($SCIENCE_TOOL graph diff --format json --path knowledge/graph.trig 2>&1) || true
        if printf "%s" "$diff_output" | python3 -c "import sys,json; json.load(sys.stdin)" &>/dev/null; then
            stale_count=$(printf "%s" "$diff_output" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['rows']))")
            if [ "$stale_count" -gt 0 ]; then
                stale_files=$(printf "%s" "$diff_output" | python3 -c "
import sys, json
for row in json.load(sys.stdin)['rows']:
    print(f\"  {row['path']} ({row['reason']})\")
")
                warn "graph has ${stale_count} stale input file(s) — run /science:update-graph"
                if [ "$VERBOSE" = "--verbose" ]; then
                    printf "%s\n" "$stale_files"
                fi
            else
                info "graph-prose sync: all inputs up to date"
            fi
        else
            # diff may fail if no revision metadata exists yet (fresh graph)
            info "graph diff: no revision metadata (expected for new graphs)"
        fi
    fi
else
    info "No knowledge/graph.trig — skipping graph checks"
fi
```

**Step 2: Verify validate.sh has no syntax errors**

Run: `bash -n scripts/validate.sh`
Expected: no output (clean parse)

**Step 3: Commit**

```bash
git add scripts/validate.sh
git commit -m "feat: add graph validation checks to validate.sh (section 13)"
```

---

### Task 4: Integration test — validate.sh against a test graph

**Step 1: Manual smoke test**

Run from the science-tool directory (which has no `knowledge/graph.trig`):

```bash
cd /tmp && mkdir -p test-validate && cd test-validate
# Create minimal project structure
mkdir -p specs doc papers data code knowledge
touch science.yaml CLAUDE.md AGENTS.md RESEARCH_PLAN.md specs/research-question.md
echo "name: test" >> science.yaml
echo "created: 2026-03-06" >> science.yaml
echo "last_modified: 2026-03-06" >> science.yaml
echo "status: active" >> science.yaml
echo "summary: test project" >> science.yaml

# Init a graph and add an orphaned concept
uv run --with /mnt/ssd/Dropbox/science/science-tool science-tool graph init
uv run --with /mnt/ssd/Dropbox/science/science-tool science-tool graph add concept "Orphan" --type biolink:Gene

# Run validate.sh
bash /mnt/ssd/Dropbox/science/scripts/validate.sh --verbose
```

Expected: should show graph validate checks (parseable=pass, provenance=pass, acyclicity=pass, orphaned=warn), plus a staleness warning or "no revision metadata" info.

**Step 2: Clean up**

```bash
rm -rf /tmp/test-validate
```

---

### Task 5: Update plan.md deliverables

**Files:**
- Modify: `docs/plan.md`

**Step 1: Check off the validate.sh graph checks deliverable**

In the 3d deliverables section, change:
```
- [ ] `validate.sh` graph checks: parseable TriG, provenance completeness, orphaned nodes, causal acyclicity, graph-prose sync staleness
```
to:
```
- [x] `validate.sh` graph checks: parseable TriG, provenance completeness, orphaned nodes, causal acyclicity, graph-prose sync staleness
```

Also update the Immediate Next Steps section item 7 to show completion.

**Step 2: Commit**

```bash
git add -f docs/plan.md
git commit -m "docs: mark validate.sh graph checks as complete"
```
