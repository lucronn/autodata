"""Provider-neutral connector for deterministic local source drops."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .source_adapters import SourceResource


class DirectorySourceConnector:
    """Expose every file in a directory as an immutable source resource.

    The connector deliberately does not infer a domain schema. Media type is
    resolved from the payload first, while the relative path is retained only
    as a stable locator and source URI component.
    """

    name = "local-directory"

    def __init__(self, directory: str | Path, source_version: str):
        self._directory = Path(directory)
        self._source_version = str(source_version).strip()
        if not self._source_version:
            raise ValueError("source version is required")

    def fetch(self, _request: dict[str, Any]) -> list[SourceResource]:
        if not self._directory.is_dir():
            raise ValueError(f"source directory does not exist: {self._directory}")

        resources = []
        for path in sorted(item for item in self._directory.rglob("*") if item.is_file()):
            relative_path = path.relative_to(self._directory).as_posix()
            resources.append(
                SourceResource.from_bytes(
                    source_uri=f"file://{relative_path}",
                    source_version=self._source_version,
                    payload=path.read_bytes(),
                    media_type=None,
                    locator=relative_path,
                    metadata={"connector": self.name, "source_path": relative_path},
                )
            )
        return resources
