"""Executed schema-closure mutation matrix.

Each row below records a deliberately broken implementation, the named target gate, the exact
selection that was run, and every observed failing test. Each mutation was applied alone to a
clean worktree, reverted without being committed, and followed by another clean-status check.

1. Remove ``hypothesis: 1.0`` from generation 2.
   Target: ``test_GATE_1_every_generation_row_matches_the_closed_declaration``.
   Selection: ``(cd science/model && uv run --frozen pytest
   tests/test_schema_closed_gate.py -q)``.
   Observed failures:
   ``test_GATE_1_every_generation_row_matches_the_closed_declaration``.

2. Set ``schema_closed=True`` on ``concept`` without adding generation-row entries.
   Target: ``test_GATE_1_every_generation_row_matches_the_closed_declaration``.
   Selection: ``(cd science/model && uv run --frozen pytest
   tests/test_schema_closed_gate.py -q)``.
   Observed failures:
   ``test_this_mechanism_closes_NO_new_kind``;
   ``test_GATE_1_every_generation_row_matches_the_closed_declaration``.
   The row loop reports generation 2 first and stops at that assertion; the same mismatch exists
   in generation 3.

3. Add ``concept: 1.0`` to generation 2 without closing the declaration.
   Target: ``test_GATE_1_every_generation_row_matches_the_closed_declaration``.
   Selection: ``(cd science/model && uv run --frozen pytest
   tests/test_schema_closed_gate.py -q)``.
   Observed failures:
   ``test_GATE_1_every_generation_row_matches_the_closed_declaration``;
   ``test_GATE_2_every_ARMED_component_resolves_to_a_packaged_file``.

4. Rename ``mixin-hypothesis-1.0.json`` to
   ``mixin-hypothesis-1.0.json.disabled``.
   Target: ``test_GATE_2_every_ARMED_component_resolves_to_a_packaged_file``.
   Selection: ``(cd science/model && uv run --frozen pytest
   tests/test_schema_closed_gate.py -q)``.
   Observed failures:
   ``test_GATE_2_every_ARMED_component_resolves_to_a_packaged_file``.

5a. Set ``StructuredEntitySource.model_config`` to ``extra="ignore"``.
    Target: ``test_an_unknown_key_SURVIVES_the_source_contract``.
    Selection: ``(cd science && uv run --frozen pytest
    tests/test_entity_construction_boundary.py tests/test_undeclared_key_diagnostic.py -q)``.
    Observed failures:
    ``test_an_unknown_key_SURVIVES_the_source_contract``;
    ``test_an_authored_shadow_key_SURVIVES_the_whole_load_path``;
    ``test_an_alias_collision_is_refused_through_the_whole_load_path``;
    ``test_the_same_closed_row_WITHOUT_the_shadow_key_loads``;
    ``test_structured_validation_sees_normalized_authored_destinations``;
    ``test_structured_source_PRESERVES_an_unknown_reference_key``.
    Pydantic reports ``model_extra is None``, not ``{}``. The closed-shadow refusal remains green
    for the wrong immediate cause: stripping also removes required ``status``, so the row is still
    refused. The alias-collision and normalized-authored-destination controls enlarge the predicted
    cascade because both depend on extras surviving the source contract.

5b. Remove ``validate_against_schema(...)`` from ``EntityRegistry.build``.
    Target: ``test_build_validates_a_closed_kind_before_projecting``.
    Selection: ``(cd science && uv run --frozen pytest
    tests/test_entity_construction_boundary.py tests/test_undeclared_key_diagnostic.py -q)``.
    Observed failures:
    ``test_a_CLOSED_kind_refuses_a_shadow_key_through_the_whole_structured_path``;
    ``test_an_unauthored_optional_field_is_absent_from_what_VALIDATION_SEES``;
    ``test_structured_validation_sees_normalized_authored_destinations``;
    ``test_an_AUTHORED_bookkeeping_key_is_still_refused[content-prose]``;
    ``test_an_AUTHORED_bookkeeping_key_is_still_refused[evidence_refs-value1]``;
    ``test_build_validates_a_closed_kind_before_projecting``.
    The normalized-destination spy and both authored-bookkeeping controls enlarge the predicted
    cascade because the removed call is their observation or refusal point.

5c. Replace the structured loader's ``registry.build(...)`` with
    ``registry.resolve_class(kind_name).model_validate(raw)``.
    Target: ``test_NOTHING_in_the_loading_package_resolves_a_class_to_build_from``.
    Selection: ``(cd science && uv run --frozen pytest
    tests/test_entity_construction_boundary.py tests/test_undeclared_key_diagnostic.py -q)``.
    Observed failures:
    ``test_NOTHING_in_the_loading_package_resolves_a_class_to_build_from``;
    ``test_an_authored_shadow_key_SURVIVES_the_whole_load_path``;
    ``test_a_CLOSED_kind_refuses_a_shadow_key_through_the_whole_structured_path``;
    ``test_the_same_closed_row_WITHOUT_the_shadow_key_loads``;
    ``test_an_unauthored_optional_field_is_absent_from_what_VALIDATION_SEES``;
    ``test_structured_validation_sees_normalized_authored_destinations``;
    ``test_an_AUTHORED_bookkeeping_key_is_still_refused[content-prose]``;
    ``test_an_AUTHORED_bookkeeping_key_is_still_refused[evidence_refs-value1]``.
    The guard names ``sources.py:1276``. Bypassing ``build`` removes both validation and enrichment,
    so five additional structured-load controls fail during direct Pydantic projection. The two
    ``VALIDATION_SEES`` / normalized-destinations spy tests fail because the validator call is
    absent, not because projection rejects their rows.

5d. Change ``STRUCTURED_DROP_KEYS`` to ``frozenset({"kind", "title"})``.
    Target: ``test_kind_is_the_only_declared_DROP``.
    Selection: ``(cd science && uv run --frozen pytest
    tests/test_entity_construction_boundary.py tests/test_undeclared_key_diagnostic.py -q)``.
    Observed failures: ``test_kind_is_the_only_declared_DROP``.

6. Set the closed ``hypothesis`` descriptor's ``home=None``.
   Target: ``test_GATE_4_a_closed_kind_declares_entity_class_and_home``.
   Selection: ``(cd science/model && uv run --frozen pytest
   tests/test_schema_closed_gate.py -q)``.
   Observed failures: ``test_GATE_4_a_closed_kind_declares_entity_class_and_home``.

7. Set the closed ``hypothesis`` descriptor's ``entity_class=None``.
   Target: ``test_GATE_4_a_closed_kind_declares_entity_class_and_home``.
   Selection: ``(cd science/model && uv run --frozen pytest
   tests/test_schema_closed_gate.py -q)``.
   Observed failures: ``test_GATE_4_a_closed_kind_declares_entity_class_and_home``.

8. Replace ``ProfileManifest._refuse_toolkit_reserved_fields`` with ``return data``.
   Targets: both external-manifest ``schema_closed`` rejection tests and the tool-side loader
   rejection test.
   Selections: ``(cd science/model && uv run --frozen pytest
   tests/test_schema_closed_gate.py -q)``; then ``(cd science && uv run --frozen pytest
   tests/test_local_kind_registration_reserved_fields.py -q)``.
   Observed failures:
   ``test_an_external_manifest_may_NOT_author_schema_closed``;
   ``test_an_external_manifest_may_not_author_schema_closed_FALSE_either``;
   ``test_the_TOOL_side_loader_refuses_an_authored_schema_closed``.
"""
