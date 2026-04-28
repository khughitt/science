# Paper Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Prerequisite:** The Project Model plan (`2026-04-05-project-model.md`) must be completed first. It adds the entity types (finding, story, paper, observation, proposition) and relation kinds (contains, grounded_by, synthesizes, organized_by, comprises) to the enum and core profile.

**Goal:** Implement the compositional paper hierarchy — graph store operations, CLI commands, and skill updates that let users assemble findings into interpretations, stories, and papers with full traceability.

**Architecture:** Builds on the Project Model foundation. Adds graph store functions for compositional entities, CLI commands for paper assembly/gap-analysis, and updates the `interpret-results` skill to produce structured findings. The compositional entities compose bottom-up (findings accumulate → stories form → papers emerge) and support top-down gap analysis.

**Tech Stack:** Python 3.11+, Pydantic v2, rdflib, Click, pytest

**Spec:** `docs/specs/2026-04-05-paper-model-design.md`

---

### Task 1: Graph Store — Finding Operations

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_paper_model.py`

- [ ] **Step 1: Write failing test for add_finding**

```python
# science-tool/tests/test_paper_model.py

from pathlib import Path
from rdflib.namespace import RDF
from science_tool.graph.store import (
    add_finding,
    add_proposition,
    add_observation,
    _load_dataset,
    _graph_uri,
    SCI_NS,
    PROJECT_NS,
    init_graph_file,
)
import pytest


@pytest.fixture()
def tmp_graph(tmp_path: Path) -> Path:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    init_graph_file(graph_path)
    return graph_path


def test_add_finding(tmp_graph: Path) -> None:
    """add_finding creates a Finding node linked to propositions and observations."""
    prop_uri = add_proposition(
        tmp_graph, text="X correlates with Y", source="article:a", proposition_id="p1"
    )
    obs_uri = add_observation(
        tmp_graph, description="r=0.73", data_source="data-package:results", observation_id="obs1"
    )
    finding_uri = add_finding(
        tmp_graph,
        summary="Analysis shows X-Y correlation",
        confidence="moderate",
        propositions=["proposition:p1"],
        observations=["observation:obs1"],
        source="data-package:results",
        finding_id="f01",
    )
    dataset = _load_dataset(tmp_graph)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    assert (finding_uri, RDF.type, SCI_NS.Finding) in knowledge
    # Contains edges to proposition and observation
    prop_ref = PROJECT_NS["proposition/p1"]
    obs_ref = PROJECT_NS["observation/obs1"]
    assert (finding_uri, SCI_NS.contains, prop_ref) in knowledge
    assert (finding_uri, SCI_NS.contains, obs_ref) in knowledge
    # Grounded by data package
    dp_ref = PROJECT_NS["data-package/results"]
    assert (finding_uri, SCI_NS.groundedBy, dp_ref) in knowledge
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science-tool && uv run --frozen pytest tests/test_paper_model.py::test_add_finding -v`
Expected: FAIL — `add_finding` does not exist.

- [ ] **Step 3: Implement add_finding**

Add to `science-tool/src/science_tool/graph/store.py`:

```python
def add_finding(
    graph_path: Path,
    summary: str,
    confidence: str,
    propositions: list[str],
    observations: list[str],
    source: str,
    finding_id: str | None = None,
) -> URIRef:
    """Add a finding — propositions grounded by observations from an analysis."""
    if confidence not in ("high", "moderate", "low", "speculative"):
        raise click.ClickException(f"Confidence must be high/moderate/low/speculative, got '{confidence}'")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if finding_id is not None:
        token = _slug(finding_id)
        if not token:
            raise click.ClickException("Finding ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{source}|{summary}".encode("utf-8")).hexdigest()[:12]

    finding_uri = URIRef(PROJECT_NS[f"finding/{token}"])
    knowledge.add((finding_uri, RDF.type, SCI_NS.Finding))
    knowledge.add((finding_uri, SCHEMA_NS.description, Literal(summary)))
    knowledge.add((finding_uri, SCI_NS.confidence, Literal(confidence)))

    for prop_ref in propositions:
        knowledge.add((finding_uri, SCI_NS.contains, _resolve_term(prop_ref)))

    for obs_ref in observations:
        knowledge.add((finding_uri, SCI_NS.contains, _resolve_term(obs_ref)))

    knowledge.add((finding_uri, SCI_NS.groundedBy, _resolve_term(source)))

    _save_dataset(dataset, graph_path)
    return finding_uri
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science-tool && uv run --frozen pytest tests/test_paper_model.py::test_add_finding -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd science-tool && git add src/science_tool/graph/store.py tests/test_paper_model.py
git commit -m "feat: add add_finding to graph store

Finding bundles propositions + observations with traceability to
the data-package/workflow-run that produced them."
```

---

### Task 2: Graph Store — Interpretation Operations

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_paper_model.py`

- [ ] **Step 1: Write failing test**

```python
# Append to science-tool/tests/test_paper_model.py

def test_add_interpretation(tmp_graph: Path) -> None:
    """add_interpretation creates an Interpretation linked to findings."""
    prop_uri = add_proposition(tmp_graph, text="X causes Y", source="article:a", proposition_id="p1")
    obs_uri = add_observation(tmp_graph, description="r=0.73", data_source="data-package:x", observation_id="obs1")
    finding_uri = add_finding(
        tmp_graph,
        summary="Correlation found",
        confidence="moderate",
        propositions=["proposition:p1"],
        observations=["observation:obs1"],
        source="data-package:x",
        finding_id="f01",
    )

    from science_tool.graph.store import add_interpretation

    interp_uri = add_interpretation(
        tmp_graph,
        summary="Initial expression analysis suggests X-Y link",
        findings=["finding:f01"],
        context="Exploratory analysis of dataset X",
        interpretation_id="interp-01",
    )
    dataset = _load_dataset(tmp_graph)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    assert (interp_uri, RDF.type, SCI_NS.Interpretation) in knowledge
    assert (interp_uri, SCI_NS.contains, PROJECT_NS["finding/f01"]) in knowledge
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science-tool && uv run --frozen pytest tests/test_paper_model.py::test_add_interpretation -v`
Expected: FAIL

- [ ] **Step 3: Implement add_interpretation**

```python
def add_interpretation(
    graph_path: Path,
    summary: str,
    findings: list[str],
    context: str | None = None,
    prior: str | None = None,
    interpretation_id: str | None = None,
) -> URIRef:
    """Add an interpretation — one analysis session's narrative and findings."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if interpretation_id is not None:
        token = _slug(interpretation_id)
        if not token:
            raise click.ClickException("Interpretation ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{summary}".encode("utf-8")).hexdigest()[:12]

    interp_uri = URIRef(PROJECT_NS[f"interpretation/{token}"])
    knowledge.add((interp_uri, RDF.type, SCI_NS.Interpretation))
    knowledge.add((interp_uri, SCHEMA_NS.description, Literal(summary)))

    if context:
        knowledge.add((interp_uri, SCI_NS.context, Literal(context)))

    for finding_ref in findings:
        knowledge.add((interp_uri, SCI_NS.contains, _resolve_term(finding_ref)))

    if prior:
        provenance = dataset.graph(_graph_uri("graph/provenance"))
        provenance.add((interp_uri, PROV.wasDerivedFrom, _resolve_term(prior)))

    _save_dataset(dataset, graph_path)
    return interp_uri
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science-tool && uv run --frozen pytest tests/test_paper_model.py::test_add_interpretation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd science-tool && git add src/science_tool/graph/store.py tests/test_paper_model.py
git commit -m "feat: add add_interpretation to graph store"
```

---

### Task 3: Graph Store — Story and Paper Operations

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_paper_model.py`

- [ ] **Step 1: Write failing tests**

```python
# Append to science-tool/tests/test_paper_model.py

def test_add_story(tmp_graph: Path) -> None:
    from science_tool.graph.store import add_story

    story_uri = add_story(
        tmp_graph,
        title="X regulates Y through pathway Z",
        summary="Evidence from multiple analyses converges on X-Y regulation",
        about="hypothesis:h01",
        interpretations=["interpretation:interp-01"],
        status="developing",
        story_id="s01",
    )
    dataset = _load_dataset(tmp_graph)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    assert (story_uri, RDF.type, SCI_NS.Story) in knowledge
    assert (story_uri, SCI_NS.synthesizes, PROJECT_NS["interpretation/interp-01"]) in knowledge
    assert (story_uri, SCI_NS.organizedBy, PROJECT_NS["hypothesis/h01"]) in knowledge


def test_add_paper(tmp_graph: Path) -> None:
    from science_tool.graph.store import add_paper_entity

    paper_uri = add_paper_entity(
        tmp_graph,
        title="The Role of X in Y Regulation",
        stories=["story:s01"],
        status="outline",
        paper_id="paper-01",
    )
    dataset = _load_dataset(tmp_graph)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    assert (paper_uri, RDF.type, SCI_NS.Paper) in knowledge
    assert (paper_uri, SCI_NS.comprises, PROJECT_NS["story/s01"]) in knowledge
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_paper_model.py -v -k "add_story or add_paper"`
Expected: FAIL

- [ ] **Step 3: Implement add_story**

```python
def add_story(
    graph_path: Path,
    title: str,
    summary: str,
    about: str,
    interpretations: list[str],
    status: str = "draft",
    story_id: str | None = None,
) -> URIRef:
    """Add a story — a narrative arc synthesizing interpretations around a question or hypothesis."""
    if status not in ("draft", "developing", "mature"):
        raise click.ClickException(f"Story status must be draft/developing/mature, got '{status}'")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if story_id is not None:
        token = _slug(story_id)
        if not token:
            raise click.ClickException("Story ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{title}".encode("utf-8")).hexdigest()[:12]

    story_uri = URIRef(PROJECT_NS[f"story/{token}"])
    knowledge.add((story_uri, RDF.type, SCI_NS.Story))
    knowledge.add((story_uri, SKOS.prefLabel, Literal(title)))
    knowledge.add((story_uri, SCHEMA_NS.description, Literal(summary)))
    knowledge.add((story_uri, SCI_NS.projectStatus, Literal(status)))
    knowledge.add((story_uri, SCI_NS.organizedBy, _resolve_term(about)))

    for interp_ref in interpretations:
        knowledge.add((story_uri, SCI_NS.synthesizes, _resolve_term(interp_ref)))

    _save_dataset(dataset, graph_path)
    return story_uri
```

- [ ] **Step 4: Implement add_paper_entity**

```python
def add_paper_entity(
    graph_path: Path,
    title: str,
    stories: list[str],
    status: str = "outline",
    abstract: str | None = None,
    paper_id: str | None = None,
) -> URIRef:
    """Add a paper — an ordered composition of stories for communication."""
    if status not in ("outline", "draft", "revision", "final"):
        raise click.ClickException(f"Paper status must be outline/draft/revision/final, got '{status}'")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if paper_id is not None:
        token = _slug(paper_id)
        if not token:
            raise click.ClickException("Paper ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{title}".encode("utf-8")).hexdigest()[:12]

    paper_uri = URIRef(PROJECT_NS[f"paper/{token}"])
    knowledge.add((paper_uri, RDF.type, SCI_NS.Paper))
    knowledge.add((paper_uri, SKOS.prefLabel, Literal(title)))
    knowledge.add((paper_uri, SCI_NS.projectStatus, Literal(status)))

    if abstract:
        knowledge.add((paper_uri, SCHEMA_NS.description, Literal(abstract)))

    for story_ref in stories:
        knowledge.add((paper_uri, SCI_NS.comprises, _resolve_term(story_ref)))

    _save_dataset(dataset, graph_path)
    return paper_uri
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_paper_model.py -v -k "add_story or add_paper"`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd science-tool && git add src/science_tool/graph/store.py tests/test_paper_model.py
git commit -m "feat: add story and paper operations to graph store

add_story creates narrative arcs organized by question/hypothesis.
add_paper_entity composes stories into communicable documents."
```

---

### Task 4: CLI Commands — Compositional Entities

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`

- [ ] **Step 1: Add `graph add finding` command**

```python
@graph_add.command("finding")
@click.argument("summary")
@click.option("--confidence", required=True, type=click.Choice(["high", "moderate", "low", "speculative"]))
@click.option("--proposition", "propositions", multiple=True, required=True, help="Proposition ref(s)")
@click.option("--observation", "observations", multiple=True, required=True, help="Observation ref(s)")
@click.option("--source", required=True, help="data-package or workflow-run that produced the observations")
@click.option("--id", "finding_id", default=None, help="Custom finding ID slug")
@click.pass_context
def add_finding_cmd(ctx, summary, confidence, propositions, observations, source, finding_id):
    """Add a finding — propositions grounded by observations."""
    graph_path = _graph_path(ctx)
    uri = add_finding(graph_path, summary, confidence, list(propositions), list(observations), source, finding_id)
    click.echo(f"Added finding: {uri}")
```

- [ ] **Step 2: Add `graph add interpretation` command**

```python
@graph_add.command("interpretation")
@click.argument("summary")
@click.option("--finding", "findings", multiple=True, required=True, help="Finding ref(s)")
@click.option("--context", default=None, help="What prompted this analysis")
@click.option("--prior", default=None, help="Previous interpretation ref (provenance chain)")
@click.option("--id", "interpretation_id", default=None, help="Custom interpretation ID slug")
@click.pass_context
def add_interpretation_cmd(ctx, summary, findings, context, prior, interpretation_id):
    """Add an interpretation — one analysis session's narrative and findings."""
    graph_path = _graph_path(ctx)
    uri = add_interpretation(graph_path, summary, list(findings), context, prior, interpretation_id)
    click.echo(f"Added interpretation: {uri}")
```

- [ ] **Step 3: Add `graph add story` command**

```python
@graph_add.command("story")
@click.argument("title")
@click.option("--summary", required=True, help="Brief summary of the narrative arc")
@click.option("--about", required=True, help="Question or hypothesis this story is about")
@click.option("--interpretation", "interpretations", multiple=True, required=True, help="Interpretation ref(s)")
@click.option("--status", default="draft", type=click.Choice(["draft", "developing", "mature"]))
@click.option("--id", "story_id", default=None, help="Custom story ID slug")
@click.pass_context
def add_story_cmd(ctx, title, summary, about, interpretations, status, story_id):
    """Add a story — a narrative arc around a question or hypothesis."""
    graph_path = _graph_path(ctx)
    uri = add_story(graph_path, title, summary, about, list(interpretations), status, story_id)
    click.echo(f"Added story: {uri}")
```

- [ ] **Step 4: Add `graph add paper` command (compositional, not literature)**

```python
@graph_add.command("paper")
@click.argument("title")
@click.option("--story", "stories", multiple=True, required=True, help="Story ref(s)")
@click.option("--status", default="outline", type=click.Choice(["outline", "draft", "revision", "final"]))
@click.option("--abstract", default=None, help="Paper abstract")
@click.option("--id", "paper_id", default=None, help="Custom paper ID slug")
@click.pass_context
def add_paper_cmd(ctx, title, stories, status, abstract, paper_id):
    """Add a paper — a composition of stories for communication."""
    graph_path = _graph_path(ctx)
    uri = add_paper_entity(graph_path, title, list(stories), status, abstract, paper_id)
    click.echo(f"Added paper: {uri}")
```

- [ ] **Step 5: Update imports at top of cli.py**

```python
from science_tool.graph.store import (
    add_finding,
    add_interpretation,
    add_story,
    add_paper_entity,
    # ... existing imports
)
```

- [ ] **Step 6: Commit**

```bash
cd science-tool && git add src/science_tool/cli.py
git commit -m "feat: add CLI commands for compositional entities

graph add finding/interpretation/story/paper commands enable
bottom-up assembly of research narratives."
```

---

### Task 5: Update interpret-results Skill

**Files:**
- Modify: `skills/interpret-results/SKILL.md` (or wherever this skill is defined)

- [ ] **Step 1: Find the interpret-results skill file**

```bash
find skills/ -name "*.md" | xargs grep -l "interpret.results" | head -5
```

- [ ] **Step 2: Update the skill to produce structured entities**

The interpret-results skill currently writes prose interpretation documents to `doc/interpretations/`. Update the skill guidance to:

1. **Create observations** for each empirical result identified in the analysis output.
2. **Create propositions** for each interpretive claim derived from the observations.
3. **Add evidence edges** connecting observations→propositions.
4. **Bundle into findings** linking propositions + observations + data source.
5. **Create an interpretation** containing all findings from this session.
6. **Continue writing** the prose interpretation document (for human readability).

Key additions to the skill:

```markdown
### Structured Output (New)

After analyzing results, create structured entities in addition to the prose document:

1. For each concrete empirical fact:
   `science-tool graph add observation "<description>" --data-source <data-package-ref> --metric <what> --value <value>`

2. For each interpretive claim:
   `science-tool graph add proposition "<text>" --source <data-package-ref> --confidence <0-1>`

3. For each observation that bears on a proposition:
   `science-tool graph add evidence <observation-ref> <proposition-ref> --stance supports|disputes --strength strong|moderate|weak`

4. Bundle into a finding:
   `science-tool graph add finding "<summary>" --confidence moderate --proposition <ref> --observation <ref> --source <data-package-ref>`

5. Create the interpretation:
   `science-tool graph add interpretation "<summary>" --finding <ref> --context "<what prompted this>"`
```

- [ ] **Step 3: Commit**

```bash
git add skills/
git commit -m "feat: update interpret-results skill to produce structured entities

Now creates observations, propositions, evidence edges, findings,
and interpretations in the graph alongside the prose document."
```

---

### Task 6: Templates — Finding and Story

**Files:**
- Create: `templates/finding.md`
- Create: `templates/story.md`
- Create: `templates/paper.md` (compositional paper, not literature)

- [ ] **Step 1: Create finding template**

```markdown
---
id: "finding:{{finding_id}}"
type: "finding"
title: "{{title}}"
confidence: "{{confidence}}"  # high | moderate | low | speculative
propositions:
  - "proposition:{{prop_id}}"
observations:
  - "observation:{{obs_id}}"
source: "data-package:{{source_id}}"
related: []
source_refs: []
---

## Summary

{{Brief description of what was found.}}

## Observations

<!-- List the concrete empirical facts this finding is based on. -->

- observation:{{obs_id}} — {{description of observation}}

## Propositions

<!-- List the interpretive claims this finding makes. -->

- proposition:{{prop_id}} — {{claim text}}

## Evidence

<!-- How do the observations bear on the propositions? -->

- observation:{{obs_id}} **supports** proposition:{{prop_id}} (strength: {{moderate}})
  - Caveats: {{any limitations}}

## Source

Data from: data-package:{{source_id}}
Analysis: workflow-run:{{run_id}} (if applicable)
```

- [ ] **Step 2: Create story template**

```markdown
---
id: "story:{{story_id}}"
type: "story"
title: "{{title}}"
about: "{{question_or_hypothesis_ref}}"
status: "draft"  # draft | developing | mature
interpretations:
  - "interpretation:{{interp_id}}"
related: []
source_refs: []
---

## Summary

{{Brief summary of the narrative arc — what question does this story address
and what do the accumulated findings suggest?}}

## Interpretations

<!-- Ordered list of analysis sessions contributing to this story. -->

1. interpretation:{{interp_id}} — {{summary of what this session found}}

## Synthesis

{{Connective prose — the "so what" that ties the interpretations together.
What picture emerges? What patterns repeat? Where do the findings converge?}}

## Gaps

<!-- What's missing? What findings would strengthen this story? -->

- [ ] {{Description of missing evidence or analysis}}

## Status

Current status: **draft**

- [ ] Key findings established
- [ ] Synthesis narrative written
- [ ] Gaps identified and prioritized
- [ ] Ready for paper inclusion
```

- [ ] **Step 3: Create compositional paper template**

```markdown
---
id: "paper:{{paper_id}}"
type: "paper"
title: "{{title}}"
status: "outline"  # outline | draft | revision | final
stories:
  - "story:{{story_id}}"
related: []
source_refs: []
---

## Abstract

{{Paper abstract — written once stories are mature.}}

## Outline

### Introduction

{{Background, motivation, and aims. References propositions and questions.}}

### Methods

{{Approach descriptions. References methods, workflows, datasets.}}

### Results

<!-- Each story maps to a results subsection. -->

#### {{Story 1 title}}

Story: story:{{story_id}}
Status: {{draft | developing | mature}}

#### {{Story 2 title}}

Story: story:{{story_id_2}}
Status: {{draft | developing | mature}}

### Discussion

{{Synthesis, limitations, future directions. References open questions.}}

## Bibliography

<!-- Populated from article references across all stories. -->
```

- [ ] **Step 4: Commit**

```bash
git add templates/
git commit -m "feat: add finding, story, and paper templates

Templates for compositional entities in the Paper Model."
```

---

### Task 7: Integration Test — Full Composition Chain

**Files:**
- Test: `science-tool/tests/test_paper_model.py`

- [ ] **Step 1: Write integration test for full composition chain**

```python
# Append to science-tool/tests/test_paper_model.py

def test_full_composition_chain(tmp_graph: Path) -> None:
    """Test: observation → proposition → finding → interpretation → story → paper."""
    from science_tool.graph.store import add_story, add_paper_entity, add_interpretation, add_hypothesis

    # Atoms
    add_hypothesis(tmp_graph, "h01", "X regulates Y", "article:smith-2024")
    obs1 = add_observation(tmp_graph, "r=0.73, p<0.001", "data-package:expr", observation_id="obs1")
    obs2 = add_observation(tmp_graph, "fold-change=2.1", "data-package:expr", observation_id="obs2")
    prop1 = add_proposition(tmp_graph, "X correlates with Y", "article:smith-2024", proposition_id="p1")
    prop2 = add_proposition(tmp_graph, "X upregulates Y expression", "data-package:expr", proposition_id="p2")

    # Findings
    f1 = add_finding(
        tmp_graph, "Correlation analysis", "moderate",
        ["proposition:p1"], ["observation:obs1"], "data-package:expr", "f01",
    )
    f2 = add_finding(
        tmp_graph, "Differential expression", "high",
        ["proposition:p2"], ["observation:obs2"], "data-package:expr", "f02",
    )

    # Interpretation
    interp = add_interpretation(
        tmp_graph, "Expression analysis suggests X-Y regulation",
        ["finding:f01", "finding:f02"], context="Initial exploratory analysis",
        interpretation_id="interp-01",
    )

    # Story
    story = add_story(
        tmp_graph, "X regulates Y", "Multiple lines of evidence for X-Y regulation",
        "hypothesis:h01", ["interpretation:interp-01"], status="developing", story_id="s01",
    )

    # Paper
    paper = add_paper_entity(
        tmp_graph, "The Role of X in Y Regulation",
        ["story:s01"], status="outline", paper_id="paper-01",
    )

    # Verify full chain exists in graph
    dataset = _load_dataset(tmp_graph)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    # Paper → Story
    assert (PROJECT_NS["paper/paper-01"], SCI_NS.comprises, PROJECT_NS["story/s01"]) in knowledge
    # Story → Interpretation
    assert (PROJECT_NS["story/s01"], SCI_NS.synthesizes, PROJECT_NS["interpretation/interp-01"]) in knowledge
    # Story → Hypothesis
    assert (PROJECT_NS["story/s01"], SCI_NS.organizedBy, PROJECT_NS["hypothesis/h01"]) in knowledge
    # Interpretation → Finding
    assert (PROJECT_NS["interpretation/interp-01"], SCI_NS.contains, PROJECT_NS["finding/f01"]) in knowledge
    # Finding → Proposition
    assert (PROJECT_NS["finding/f01"], SCI_NS.contains, PROJECT_NS["proposition/p1"]) in knowledge
    # Finding → Observation
    assert (PROJECT_NS["finding/f01"], SCI_NS.contains, PROJECT_NS["observation/obs1"]) in knowledge
    # Finding → Data source
    assert (PROJECT_NS["finding/f01"], SCI_NS.groundedBy, PROJECT_NS["data-package/expr"]) in knowledge
```

- [ ] **Step 2: Run integration test**

Run: `cd science-tool && uv run --frozen pytest tests/test_paper_model.py::test_full_composition_chain -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd science-tool && git add tests/test_paper_model.py
git commit -m "test: add full composition chain integration test

Verifies observation → proposition → finding → interpretation → story → paper
chain with all relations in the knowledge graph."
```

---

### Task 8: Final Verification

- [ ] **Step 1: Run full test suites**

```bash
cd science-model && uv run --frozen pytest -v
cd science-tool && uv run --frozen pytest -v
```
Expected: All PASS

- [ ] **Step 2: Run linting**

```bash
cd science-model && uv run --frozen ruff check . && uv run --frozen ruff format --check .
cd science-tool && uv run --frozen ruff check . && uv run --frozen ruff format --check .
```
Expected: Clean

- [ ] **Step 3: Run type checking**

```bash
cd science-model && uv run --frozen pyright
cd science-tool && uv run --frozen pyright
```
Expected: No new errors

- [ ] **Step 4: Commit any remaining fixes**

```bash
git add -A
git commit -m "fix: final Paper Model cleanup — linting, type checks"
```
