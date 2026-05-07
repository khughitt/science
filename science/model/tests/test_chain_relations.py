"""Tests for has_link and audits relation kinds in the core profile."""

from __future__ import annotations

from science_model.profiles.core import CORE_PROFILE
from science_model.relations import relation_allows_kinds


def _relation(name: str):
    return next(r for r in CORE_PROFILE.relation_kinds if r.name == name)


class TestHasLink:
    def test_declared(self):
        assert "has_link" in {r.name for r in CORE_PROFILE.relation_kinds}

    def test_predicate(self):
        assert _relation("has_link").predicate == "sci:hasLink"

    def test_source_restricted_to_structural_chain(self):
        assert _relation("has_link").source_kinds == ["structural-chain"]

    def test_target_kinds_match_allowlist(self):
        expected = {"mechanism", "model", "proposition", "observation", "finding"}
        assert set(_relation("has_link").target_kinds) == expected

    def test_relation_allows_valid_pair(self):
        assert relation_allows_kinds(_relation("has_link"), "structural-chain", "mechanism")
        assert relation_allows_kinds(_relation("has_link"), "structural-chain", "finding")

    def test_relation_rejects_invalid_target_kind(self):
        # task is not in the link allowlist
        assert not relation_allows_kinds(_relation("has_link"), "structural-chain", "task")

    def test_relation_rejects_non_chain_source(self):
        assert not relation_allows_kinds(_relation("has_link"), "hypothesis", "mechanism")


class TestAudits:
    def test_declared(self):
        assert "audits" in {r.name for r in CORE_PROFILE.relation_kinds}

    def test_predicate(self):
        assert _relation("audits").predicate == "sci:audits"

    def test_source_restricted_to_chain_audit(self):
        assert _relation("audits").source_kinds == ["chain-audit"]

    def test_target_restricted_to_structural_chain(self):
        assert _relation("audits").target_kinds == ["structural-chain"]

    def test_relation_allows_valid_pair(self):
        assert relation_allows_kinds(_relation("audits"), "chain-audit", "structural-chain")

    def test_relation_rejects_non_audit_source(self):
        assert not relation_allows_kinds(_relation("audits"), "interpretation", "structural-chain")

    def test_relation_rejects_non_chain_target(self):
        assert not relation_allows_kinds(_relation("audits"), "chain-audit", "hypothesis")
