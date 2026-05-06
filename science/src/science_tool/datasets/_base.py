"""Base types for dataset adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class DatasetResult:
    """A dataset found by search."""

    source: str
    id: str
    title: str
    description: str = ""
    doi: str | None = None
    url: str | None = None
    year: int | None = None
    license: str | None = None
    keywords: list[str] = field(default_factory=list)
    organism: str | None = None
    modality: str | None = None
    sample_count: int | None = None
    file_count: int | None = None
    total_size_bytes: int | None = None


@dataclass(frozen=True)
class FileInfo:
    """A downloadable file within a dataset."""

    filename: str
    url: str
    size_bytes: int | None = None
    checksum: str | None = None
    format: str | None = None


@runtime_checkable
class DatasetAdapter(Protocol):
    """Common interface for dataset repository adapters."""

    name: str

    def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]: ...

    def metadata(self, dataset_id: str) -> DatasetResult: ...

    def files(self, dataset_id: str) -> list[FileInfo]: ...

    def download(self, file_info: FileInfo, dest_dir: Path) -> Path: ...
