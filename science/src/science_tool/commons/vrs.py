"""Single ga4gh.vrs boundary for C4a; every ga4gh.vrs import lives here."""

from __future__ import annotations

from typing import Any, Protocol

from ga4gh.core import ga4gh_identify
from ga4gh.vrs.extras.translator import AlleleTranslator

_ACCEPTED_FMTS = frozenset({"spdi", "hgvs"})
_GA4GH_REFGET_SPDI_PREFIX = "ga4gh:SQ."


class _Proxy(Protocol):
    def get_sequence(self, identifier: str, start: int | None = None, end: int | None = None) -> str: ...

    def get_metadata(self, identifier: str) -> dict[str, Any]: ...

    def derive_refget_accession(self, identifier: str) -> str: ...


def _translator(proxy: _Proxy) -> AlleleTranslator:
    return AlleleTranslator(data_proxy=proxy)


def _translator_expr(fmt: str, expr: str) -> str:
    # ga4gh-vrs 2.3.2 parses SPDI by colon separators, so `ga4gh:SQ...`
    # cannot be accepted directly. Strip only that prefix and preserve the
    # `SQ...` refget digest that anchors variant identity.
    if fmt == "spdi" and expr.startswith(_GA4GH_REFGET_SPDI_PREFIX):
        return expr.removeprefix("ga4gh:")
    return expr


def compute_vrs_id(proxy: _Proxy, *, fmt: str, expr: str) -> str:
    if fmt not in _ACCEPTED_FMTS:
        raise ValueError(f"unsupported variant fmt {fmt!r}")

    allele = _translator(proxy).translate_from(_translator_expr(fmt, expr), fmt=fmt, do_normalize=True)
    return ga4gh_identify(allele)
