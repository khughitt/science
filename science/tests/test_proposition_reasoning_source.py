from science_model.propositions import PropositionEntity

STAMP = "llm-synth:claude-opus-4-8:proposition-synthesize-v1"


def test_reasoning_source_defaults_none_and_omitted():
    p = PropositionEntity(id="proposition:x", title="t")
    assert p.reasoning_source is None
    # exclude_none (how write_entity_file serializes) ⇒ absent when unset
    assert "reasoning_source" not in p.model_dump(mode="json", exclude_none=True)


def test_reasoning_source_serializes_when_set():
    p = PropositionEntity(id="proposition:x", title="t", reasoning_source=STAMP)
    dumped = p.model_dump(mode="json", exclude_none=True)
    assert dumped["reasoning_source"] == STAMP
