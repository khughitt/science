# Final review fix report

## Findings and fixes

1. **Reject YAML merge keys**
   - Fixed `science/src/science_tool/graph/skill_loads.py` so the node-level alias
     parser rejects a key tagged `tag:yaml.org,2002:merge` before `safe_load`
     constructs merged mappings.
   - Added `test_validate_aliases_rejects_merge_key` in
     `science/tests/test_skill_loads.py`. It uses a merge that semantically
     overwrote an alias and now requires `SkillLoadValidationError`.
   - **RED evidence:** before the production change,
     `uv run --frozen pytest tests/test_skill_loads.py::test_validate_aliases_rejects_merge_key tests/test_skill_load_materialize.py::test_gen3_plan_materializes_canonical_skill_for_alias`
     produced `1 failed, 1 passed`; the merge-key test failed with
     `Failed: DID NOT RAISE SkillLoadValidationError`.

2. **Broaden `sci:usageSource` documentation**
   - Updated `science/src/science_tool/graph/store/constants.py` to describe it
     as the categorical projection source for a reified provenance record,
     including dataset usage and skill loads.

3. **Cover alias-through-materialization**
   - Added `test_gen3_plan_materializes_canonical_skill_for_alias` in
     `science/tests/test_skill_load_materialize.py`. It patches
     `science_tool.graph.sources.load_skill_aliases`, loads `retired-skill`, and
     verifies the graph contains `sci:skill/driver-selection` but not the retired
     URI.
   - The test was green before a production change because alias canonicalization
     was already correctly retained through source loading and materialization;
     this finding required missing end-to-end coverage, not a behavior fix.

4. **Correct provenance-export design text**
   - Updated `docs/plans/2026-07-24-skill-coverage-skillsloaded-design.md` to
     state that `graph/provenance` is exported and that
     `GRAPH_EXPORT_VISIBLE_LAYERS` does not govern that behavior. No export code
     changed.

## Verification

- `uv run --frozen pytest tests/test_skill_loads.py::test_validate_aliases_rejects_merge_key tests/test_skill_load_materialize.py::test_gen3_plan_materializes_canonical_skill_for_alias`
  - RED: `1 failed, 1 passed in 0.51s` (merge-key test failed as expected).
  - GREEN: `2 passed in 0.47s`.
- `uv run --frozen pytest tests/test_skill_loads.py tests/test_skill_load_materialize.py`
  - `55 passed in 0.71s`.
- `uv run --frozen ruff check src/science_tool/graph/skill_loads.py src/science_tool/graph/store/constants.py tests/test_skill_loads.py tests/test_skill_load_materialize.py`
  - `All checks passed!`
- `uv run --frozen pyright src/science_tool/graph/skill_loads.py src/science_tool/graph/store/constants.py`
  - `0 errors, 0 warnings, 0 informations`
- `git diff --check`
  - Exit status 0.

## Self-review

- The merge-key check is performed on the composed YAML node, before safe loading
  can materialize a merged map; literal duplicate-key rejection remains intact.
- The materialization test patches the exact source-loader binding used in the
  gen-3 load path and asserts both the canonical and retired URI cases.
- Registry and design edits are documentation-only and leave export behavior
  unchanged.

## Concerns

- None. The alias materialization regression was already green at baseline; this
  is documented above because it is coverage for an existing correct path rather
  than a new production behavior change.
