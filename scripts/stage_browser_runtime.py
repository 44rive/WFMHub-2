#!/usr/bin/env python3
"""Stage verified, self-hosted Pyodide assets for the offline browser spike."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PYODIDE_VERSION = "0.29.5"
PYODIDE_SOURCE = ROOT / "web" / "node_modules" / "pyodide"
DEFAULT_TARGET = ROOT / "web" / "public" / "vendor" / "pyodide"
BASE_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full"
CORE_FILES = (
    "pyodide.mjs",
    "pyodide.asm.js",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
)
ROOT_PACKAGES = ("scikit-learn", "statsmodels")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_lock() -> dict[str, Any]:
    package = json.loads((PYODIDE_SOURCE / "package.json").read_text(encoding="utf-8"))
    if package.get("version") != PYODIDE_VERSION:
        raise RuntimeError(
            f"installed Pyodide is {package.get('version')!r}, expected {PYODIDE_VERSION}"
        )
    return json.loads((PYODIDE_SOURCE / "pyodide-lock.json").read_text(encoding="utf-8"))


def required_packages(lock: dict[str, Any], roots: Iterable[str]) -> list[str]:
    packages = lock.get("packages")
    if not isinstance(packages, dict):
        raise RuntimeError("Pyodide lock is missing its package catalog")
    pending = list(roots)
    selected: set[str] = set()
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        raw = packages.get(name)
        if not isinstance(raw, dict):
            raise RuntimeError(f"Pyodide lock does not contain required package {name!r}")
        selected.add(name)
        dependencies = raw.get("depends", [])
        if not isinstance(dependencies, list) or not all(
            isinstance(value, str) for value in dependencies
        ):
            raise RuntimeError(f"Pyodide package {name!r} has an invalid dependency list")
        pending.extend(dependencies)
    return sorted(selected)


def download_verified(url: str, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and sha256(destination) == expected_sha256:
        return
    temporary = destination.with_suffix(destination.suffix + ".partial")
    temporary.unlink(missing_ok=True)
    print(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=180) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output)
    actual = sha256(temporary)
    if actual != expected_sha256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"Pyodide asset hash mismatch for {destination.name}: "
            f"expected {expected_sha256}, found {actual}"
        )
    temporary.replace(destination)


def write_manifest(target: Path) -> None:
    lines = [
        f"{sha256(path)}  {path.relative_to(target).as_posix()}"
        for path in sorted(target.iterdir())
        if path.is_file() and path.name != "PYODIDE_ASSETS.sha256"
    ]
    (target / "PYODIDE_ASSETS.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def stage(target: Path) -> None:
    lock = load_lock()
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    for name in CORE_FILES:
        source = PYODIDE_SOURCE / name
        if not source.is_file():
            raise FileNotFoundError(f"installed Pyodide core asset is missing: {source}")
        shutil.copy2(source, target / name)

    packages = lock["packages"]
    selected = required_packages(lock, ROOT_PACKAGES)
    for name in selected:
        metadata = packages[name]
        filename = metadata.get("file_name")
        expected = metadata.get("sha256")
        if not isinstance(filename, str) or not isinstance(expected, str):
            raise RuntimeError(f"Pyodide package {name!r} is missing file/hash metadata")
        download_verified(f"{BASE_URL}/{filename}", target / filename, expected)

    write_manifest(target)
    print(f"Staged {len(selected)} Pyodide packages and {len(CORE_FILES)} core assets at {target}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()
    stage(args.target.resolve())


if __name__ == "__main__":
    main()
