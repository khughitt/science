# Science Agent Capabilities — Design Draft

*Date: 2026-03-02*  
*Status: Draft*

## 1. Purpose

Define a first-pass capability API for Science as a staged research copilot system.
This document specifies:

- role profiles (multi-agent behavior over shared state),
- capability contracts (inputs, outputs, validations, metrics),
- a prioritized capability catalog for Stage A/B/C research workflows.

This is a design and framing document, not an implementation spec for any single command.

## 2. Framing and Boundaries

- **Primary framing:** Science is a research copilot first.
- **Flexible progression:** explore/discuss, formalization, software planning, and workflow operationalization are composable paths, not a fixed sequence.
- **Shared state model:** role profiles read/write the same project artifacts.
- **Non-goal:** Science does not become a new causal-modeling framework or workflow engine.
- **Approach:** Science orchestrates existing tools and libraries via skills, commands, and prompts.

## 3. Role Profiles

| Profile | Core objective | Typical stage | Reads | Writes |
|---|---|---|---|---|
| `research-assistant` | Build broad, reliable background context | Stage A | `specs/`, `doc/`, `papers/` | `doc/background/`, `papers/summaries/`, `references.bib` |
| `discussant` | Stress-test ideas, surface alternatives/confounders | Stage A/B | `specs/`, `doc/`, `knowledge/` | `doc/discussions/`, `doc/08-open-questions.md`, graph uncertainty notes |
| `modeler` | Formalize hypotheses into graph/causal structures | Stage B | `doc/`, `knowledge/`, datasets metadata | `knowledge/graph.trig`, `doc/09-causal-model.md`, `code/models/` |
| `workflow-architect` | Translate questions/models into reproducible execution paths | Stage C | `knowledge/`, `data/`, `code/`, `RESEARCH_PLAN.md` | `code/pipelines/`, `templates/`, validation outputs, task updates |

All profiles are modes over the same project, not isolated agents with separate memory.

## 4. Capability Contract Schema (First Pass)

Each capability should be specified with this contract:

```yaml
capability_id: "research_topic"
stage: "A|B|C"
default_profile: "research-assistant"
purpose: "One-sentence user value statement."
inputs:
  required: ["topic"]
  optional: ["scope", "time_window", "depth", "project_context_ref"]
reads:
  - "specs/research-question.md"
  - "doc/background/"
  - "papers/summaries/"
writes:
  - "doc/background/NN-topic-name.md"
  - "papers/references.bib"
output_contract:
  - "Structured summary with key claims, disagreements, uncertainty markers."
  - "Linked references and related project hypotheses/questions."
validation:
  - "Template conformance"
  - "Citation integrity"
  - "No unresolved required fields"
decision_quality_metrics:
  - "Coverage of core subtopics"
  - "Actionable follow-up questions created"
failure_modes:
  - "Shallow summary"
  - "Missing contradictory evidence"
dependencies:
  - "skills/research/SKILL.md"
  - "skills/writing/SKILL.md"
```

## 5. Initial Capability Catalog

| Capability | Stage | Default profile | Primary output | Success signal |
|---|---|---|---|---|
| `research_paper` | A | `research-assistant` | paper summary with provenance | clear claims + citation integrity + confidence labels |
| `research_topic` | A | `research-assistant` | topic synthesis doc | key themes, landmark papers, project links |
| `research_gaps` | A | `research-assistant` | gap analysis section + task proposals | high-value missing topics converted to concrete tasks |
| `find_datasets` | C | `workflow-architect` | dataset inventory table/doc | candidate datasets mapped to variables/questions |
| `discuss` | A/B | `discussant` | structured discussion record | alternatives/confounders surfaced and prioritized |
| `review_tasks` | A/B/C | `research-assistant` | prioritized task update | next steps ranked with explicit rationale |
| `create_graph` | B | `modeler` | updated `knowledge/graph.trig` + view | traceable claims/variables encoded with provenance |

### 5.1 Capability Interface Types (Commands, Prompts, Skills)

Each capability should declare four interfaces:

- **Command surface:** user-invokable action (`/science:*` command or equivalent).
- **Prompt contract:** role-specific prompt block with required context reads.
- **Skill bundle:** required skills loaded before writing outputs.
- **Template/output contract:** concrete artifact shape to validate.

### 5.2 First-Pass Interface Mapping

| Capability | Command surface (proposed) | Prompt profile | Required skills | Output template/artifact |
|---|---|---|---|---|
| `research_paper` | `/science:research-paper` | `research-assistant` | `research`, `writing` | `templates/paper-summary.md` |
| `research_topic` | `/science:research-topic` | `research-assistant` | `research`, `writing` | `templates/background-topic.md` |
| `research_gaps` | `/science:research-gaps` | `research-assistant` | `research`, `writing` | `doc/background/*` + gap table |
| `find_datasets` | `/science:find-datasets` | `workflow-architect` | `data` (+ source skills) | dataset inventory in `doc/05-data.md` or dedicated file |
| `discuss` | `/science:discuss` | `discussant` | `research`, `writing` | `doc/discussions/YYYY-MM-DD-<slug>.md` |
| `review_tasks` | `/science:review-tasks` | `research-assistant` | `research` | updated `RESEARCH_PLAN.md` |
| `create_graph` | `/science:create-graph` | `modeler` | `research`, `knowledge-graph`, `causal-dag` | updated `knowledge/graph.trig` + graph export |

## 6. Discussion Protocol: Double-Blind Mode

`discuss` supports a bias-reduction option where user and agent draft independently before synthesis.

### Workflow

1. Select focus (`question`, `hypothesis`, `topic`, `approach`) or randomly sample from open items/entities.
2. User writes a short private response draft.
3. Agent writes its own response draft to file before seeing user draft.
4. User reveals draft.
5. Agent publishes both + synthesis + challenge points + priority recommendations.

### Suggested Artifacts

- `doc/discussions/YYYY-MM-DD-<slug>.md` (full transcript and synthesis)
- `doc/08-open-questions.md` (new/refined questions)
- `RESEARCH_PLAN.md` (priority updates with rationale)
- optional graph updates (`sci:Claim`, `sci:refutes`, uncertainty annotations)

## 7. Prioritization Loop (Core Behavior)

Science follows a two-pass loop:

1. **Expand:** ensure broad context coverage and identify missing pieces.
2. **Compress:** prioritize a focused subset with explicit evidence-backed rationale.

Priority decisions should be written explicitly with:

- expected impact on research question,
- uncertainty reduction potential,
- feasibility/data availability,
- dependency ordering.

## 8. Decision-Quality Metrics

Track quality as decision support, not output volume:

- Time to first defensible hypothesis.
- Fraction of prioritized tasks with explicit evidence/rationale links.
- Contradiction coverage (how often conflicting evidence is surfaced and tracked).
- Graph traceability completeness (claims/hypotheses linked to provenance).
- Proportion of modeling steps blocked by missing data or identification issues (lower is better after maturation).

## 9. Implementation Order (Recommended)

1. Stage A core: `research_paper`, `research_topic`, `research_gaps`, `discuss`, `review_tasks`.
2. Stage B formalization: `create_graph`, causal critique, model-readiness checks.
3. Stage C operationalization: `find_datasets`, workflow recommendations, reproducibility handoff.

This order keeps the system useful for research-only projects while enabling deeper formalization when needed.
It is a recommended rollout order for implementation, not a required user journey at runtime.
