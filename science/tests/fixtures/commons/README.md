# Commons test fixtures

Synthetic stores used by Phase B's commons-layer tests. Each directory under
`valid/` is a self-contained snippet of a `~/d/science-commons/` store laid
out exactly as the real one would be. Directories under `invalid/` capture
one specific failure mode per directory; the directory name describes the
expected failure.

Tests in `science/tests/test_commons_*.py` copy from these into a `tmp_path`
to avoid mutating the fixtures.
