"""Focused TriG loading for graph consumers that validate authored literals."""

from __future__ import annotations

from pathlib import Path
from typing import IO, cast

from rdflib import Dataset, Literal, URIRef
from rdflib.parser import create_input_source
from rdflib.plugins.parsers.notation3 import RDFSink
from rdflib.plugins.parsers.trig import TrigSinkParser


class _LiteralPreservingRDFSink(RDFSink):
    def newLiteral(self, s: str, dt: URIRef | None, lang: str | None) -> Literal:  # noqa: N802
        if dt is not None:
            return Literal(s, datatype=dt, normalize=False)
        return Literal(s, lang=lang, normalize=False)


def load_trig_dataset_preserving_literals(graph_path: Path) -> Dataset:
    """Load TriG without normalizing quoted literal lexicals."""
    dataset = Dataset()
    default_graph = dataset.default_graph

    source = create_input_source(source=graph_path, format="trig")
    try:
        # Strict graph validation needs authored lexicals before RDFLib's default
        # Literal construction normalizes parseable non-canonical values.
        sink = _LiteralPreservingRDFSink(default_graph)
        base_uri = default_graph.absolutize(source.getPublicId() or source.getSystemId() or "")
        parser = TrigSinkParser(sink, baseURI=base_uri, turtle=True)
        stream = cast(IO[str] | IO[bytes], source.getCharacterStream() or source.getByteStream())
        parser.loadStream(stream)
        for prefix, namespace in parser._bindings.items():
            default_graph.bind(prefix, namespace)
    finally:
        if source.auto_close:
            source.close()

    return dataset
