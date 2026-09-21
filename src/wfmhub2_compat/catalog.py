"""Read and fingerprint the old product's reviewed exact queue-map contract.

The reader never rewrites source configuration, guesses a queue, or imports
operational files. A caller may tie ``sha256`` to a refresh generation.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

QUEUE_MAPPING_COLUMNS = (
    "mapping_type",
    "source_system",
    "source_value",
    "service_scope",
    "designation",
)
_MAPPING_TYPES = {"queue", "forecast_file", "scope_rollup"}
_MAX_CATALOG_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class QueueMapping:
    mapping_type: str
    source_system: str
    source_value: str
    service_scope: str
    designation: str


@dataclass(frozen=True)
class QueueMappingSnapshot:
    sha256: str
    mappings: tuple[QueueMapping, ...]


def load_queue_mapping_snapshot(path: Path) -> QueueMappingSnapshot:
    """Validate the reviewed old-portable queue-map format and hash its bytes."""
    with path.open("rb") as handle:
        raw = handle.read(_MAX_CATALOG_BYTES + 1)
    if len(raw) > _MAX_CATALOG_BYTES:
        raise ValueError("queue mapping exceeds the 2 MiB catalog limit")
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    if tuple(reader.fieldnames or ()) != QUEUE_MAPPING_COLUMNS:
        raise ValueError("queue mapping must have the reviewed five-column header")

    seen: set[tuple[str, str, str]] = set()
    mappings: list[QueueMapping] = []
    for line_number, row in enumerate(reader, 2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"queue mapping line {line_number} has missing or extra fields")
        mapping = QueueMapping(
            mapping_type=cast(str, row["mapping_type"]).strip().lower(),
            source_system=cast(str, row["source_system"]).strip(),
            source_value=cast(str, row["source_value"]).strip(),
            service_scope=cast(str, row["service_scope"]).strip(),
            designation=cast(str, row["designation"]).strip(),
        )
        if not any(vars(mapping).values()):
            continue
        if mapping.mapping_type not in _MAPPING_TYPES:
            raise ValueError(f"queue mapping line {line_number} has unknown mapping_type")
        if not mapping.source_system or not mapping.source_value or not mapping.service_scope:
            raise ValueError(f"queue mapping line {line_number} has missing required fields")
        normalized_value = re.sub(r"[^A-Z0-9]+", "", mapping.source_value.upper())
        normalized_system = re.sub(r"[^A-Z0-9]+", "", mapping.source_system.upper())
        if not normalized_value or not normalized_system:
            raise ValueError(f"queue mapping line {line_number} has no usable source key")
        key = (
            mapping.mapping_type,
            normalized_system if mapping.mapping_type == "queue" else "",
            normalized_value,
        )
        if key in seen:
            raise ValueError(f"queue mapping line {line_number} duplicates a normalized source key")
        seen.add(key)
        mappings.append(mapping)
    if not mappings:
        raise ValueError("queue mapping has no rows")
    return QueueMappingSnapshot(hashlib.sha256(raw).hexdigest(), tuple(mappings))
