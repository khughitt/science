"""Audit-finding contract: the shared payload deterministic checks and agentic
lenses both emit, and the project-state case it is stored as.

Deliberately NOT an entity kind. `EntityKind.FINDING` is a live epistemic kind
meaning "propositions grounded by observations"; an audit finding is a case about
repository or corpus hygiene and never reaches the knowledge graph, belief, or
attention. See docs/plans/2026-07-27-finding-convergence-design.md §5.
"""
