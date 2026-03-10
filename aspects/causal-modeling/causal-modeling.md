---
name: causal-modeling
description: Causal inference and DAG-based reasoning
---

# Causal Modeling

Projects studying cause-effect relationships through directed acyclic graphs and structural causal models.

## interpret-results

### Additional section: Causal Model Implications

(insert after: Evidence vs. Open Questions)

If a causal inquiry exists:
- Do results suggest missing variables or edges?
- Should any edges be removed or reversed?
- Do effect sizes inform parameter estimates?
- Propose specific graph updates but do not execute them — list the `science-tool` commands that would make the changes.

If no causal model exists yet, note whether results suggest building one.

### Additional workflow

After evaluating findings against open questions, assess the causal model using the guidance above. Present proposed graph changes to the user before executing any `science-tool` commands.

## discuss

### Additional guidance

When discussing causal claims, explicitly consider:
- Reverse causation — could the effect cause the putative cause?
- Unmeasured confounders — what common causes might be missing?
- Selection bias — does the study design condition on a collider?
- Mediation vs direct effects — is the causal path fully specified?

## research-topic

### Additional guidance

When researching topics relevant to causal modeling, note:
- Known causal mechanisms and their evidence strength
- Common confounders in the domain
- Natural experiments or instrumental variables that could aid identification

## Signal categories

- **Confounded** — effect present but likely due to unmeasured variable

## Available commands

These commands become relevant with this aspect:
- `build-dag` — construct a causal DAG from variables and relationships
- `sketch-model` — sketch an informal causal model
- `specify-model` — formalize a causal model with parameters
- `critique-approach` — critically review a causal DAG inquiry
