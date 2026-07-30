# Retiring project-local validation sidecars

`science validate` no longer executes project-authored validation code. This
includes both the old `validate.local.sh` file and `validate_local.py`.
`validate.sh` remains the managed shim for `science validate`; it does not add a
project extension point.

When either retired file is present, validation reports an error so the project
removes or renames it explicitly. The error is deliberate: a file that looks
like active validation should not silently stop running.

## Decide where the check belongs

The destination follows the policy's scope, not its previous implementation.

- A check expressing a reusable Science policy belongs in the toolkit. Open a
  design conversation before implementing it, so the policy, its diagnostic,
  and its enforcement level are reusable across projects.
- A check that is genuinely specific to one project belongs in a project-owned
  command, script, or workflow target. The project decides when to run it and
  owns its output; nothing in `science validate` enforces it.

Do not recreate either retired file to preserve a check. Move the logic to its
proper owner, then remove the retired file.

## Migration steps

1. Inventory the checks previously run from `validate.local.sh` or
   `validate_local.py`.
2. Classify each check as reusable toolkit policy or genuinely project-specific
   behavior.
3. Open a design conversation for each reusable policy check. Do not add it as
   a project-local exception.
4. Move each project-specific check to a clearly named project-owned command
   and document how that project runs it.
5. Remove or rename both retired files, then run `science validate` to confirm
   the retirement error is gone.

For the durable validator contract, see
[`science validate`](../conventions/validate.md).
