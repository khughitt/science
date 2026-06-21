# Cross-Project Work

Science projects can recognize peers, compose graphs, and synchronize shared
knowledge. Peers are declared project namespaces in `science.yaml`.

Useful inspection commands:

```bash
science peers list
science peers check
science sync status
```

Use sync commands when a project is ready to inspect or exchange shared
knowledge with peers:

```bash
science sync status
science sync run
```

Cross-project work follows the same model as within-project work: authored
source records remain the durable basis, and derived graph views are rebuilt.
Federation connects patches, projects, and project collections without erasing
local context.

For the deeper model, see [`docs/federation.md`](../federation.md).
