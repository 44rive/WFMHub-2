"""Point the portable host at an existing local source folder without copying data."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from wfmhub2_compat.rta_refresh import MAX_SOURCE_POINTER_BYTES, SOURCE_POINTER


def configure_source_root(home: Path, source_root: Path) -> Path:
    """Atomically record one validated local directory path; never alter sources."""
    resolved = source_root.expanduser().resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("The source root must be an existing directory.")
    value = str(resolved)
    if "\n" in value or "\r" in value or len(value.encode("utf-8")) + 1 > MAX_SOURCE_POINTER_BYTES:
        raise ValueError("The source-root path is not a valid single line.")
    pointer = home.resolve() / SOURCE_POINTER
    pointer.parent.mkdir(parents=True, exist_ok=True)
    temporary = pointer.with_name(pointer.name + ".tmp")
    try:
        temporary.write_text(value + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, pointer)
    finally:
        temporary.unlink(missing_ok=True)
    return pointer


def main() -> int:
    parser = argparse.ArgumentParser(prog="wfmhub2-compat-setup")
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    source_root = args.source_root
    if source_root is None:
        print("Paste the existing folder containing FTE and Verint; no files are copied.")
        entered = input("Source folder: ").strip().strip('"')
        if not entered:
            print("No folder entered; setup made no changes.")
            return 1
        source_root = Path(entered)
    try:
        configure_source_root(args.home, source_root)
    except (OSError, ValueError) as exc:
        print(f"Setup failed: {exc}")
        return 1
    print("Source folder configured. Run WFMHub.cmd, then Refresh local sources.")
    print("The source files were not changed or copied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
