# Build-staged DuckDB extensions

This directory intentionally contains no committed extension binary.

`scripts/stage_ducklake.ps1` downloads the pinned DuckLake extension during a
networked Windows build, verifies both the compressed and decompressed SHA-256
digests, and writes the local file consumed by the embedded-CPython packager:

```text
ducklake.duckdb_extension
```

The binary and its generated manifest are ignored by Git. Production runtime
must load this staged local file; it must never download an extension.
