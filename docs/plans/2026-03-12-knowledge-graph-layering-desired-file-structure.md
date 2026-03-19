# Desired File Structure

This refactor introduces a profile-driven, layered KG model spanning `science-model`, `science-tool`, `science-web`, and project repos such as `seq-feats`.

## Target Layout

```text
science/
├── doc/
│   └── kg-model/
│       ├── desired_file_structure.md
│       └── files_to_remove.md
├── docs/
│   └── plans/
├── science-model/
│   ├── src/science_model/
│   │   ├── __init__.py
│   │   ├── entities.py
│   │   ├── graph.py
│   │   ├── ids.py
│   │   ├── relations.py
│   │   └── profiles/
│   │       ├── __init__.py
│   │       ├── schema.py
│   │       ├── core.py
│   │       ├── bio.py
│   │       └── project_specific.py
│   └── tests/
│       ├── test_ids.py
│       ├── test_relations.py
│       ├── test_profiles.py
│       └── test_profile_manifests.py
└── science-tool/
    ├── src/science_tool/graph/
    │   ├── __init__.py
    │   ├── store.py
    │   ├── sources.py
    │   ├── materialize.py
    │   └── migrate.py
    └── tests/
        ├── test_graph_materialize.py
        └── test_graph_migrate.py
```

## Neighbor Repos

```text
science-web/
├── backend/
│   ├── graph.py
│   ├── indexer.py
│   ├── profiles.py
│   └── store.py
├── frontend/src/
│   ├── routes/
│   └── types/
└── tests/

seq-feats/
├── knowledge/
│   ├── graph.trig
│   ├── reports/
│   └── sources/
│       └── project_specific/
├── tasks/
└── science.yaml
```

## Structural Intent

1. `science-model` owns canonical IDs, entity kinds, relation kinds, and profile manifests.
2. `science-tool` owns parsing structured upstream sources and materializing RDF layers.
3. `science-web` consumes the shared model instead of hardcoding graph semantics.
4. Project repos provide canonical entity docs, tasks, and structured `project_specific` sources.
5. `knowledge/graph.trig` remains a generated artifact, not a direct authoring surface.
