#!/usr/bin/env python3
"""Build the cross-platform policy-compatible browser-WASM portable ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
PYTHON_VERSION = "3.13.7"
PYTHON_ARCHIVE = f"python-{PYTHON_VERSION}-embed-amd64.zip"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{PYTHON_ARCHIVE}"
PYTHON_SHA256 = "f6cca216a359be84797cabb54149ce5e062afb16cc7567eb7fc51cacb2d86b65"
PRODUCT_VERSION = "0.2.0-phase1-source-preview.4"
TOP_LEVEL = "WFMHub-2"
NATIVE_SUFFIXES = (".dll", ".exe", ".pyd", ".so", ".duckdb_extension")
HASH_LINE = re.compile(r"^([0-9a-f]{64})  (.+)$")
REQUIREMENT_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[^ ]+) --hash=sha256:(?P<sha256>[0-9a-f]{64})$"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_files(root: Path) -> list[Path]:
    return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


def copy_windows_text(source: Path, destination: Path) -> None:
    content = source.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    destination.write_text(content, encoding="utf-8", newline="\r\n")


def download_verified(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        partial = destination.with_suffix(".partial")
        partial.unlink(missing_ok=True)
        print(f"Downloading {PYTHON_URL}")
        with urlopen(PYTHON_URL, timeout=180) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output)
        partial.replace(destination)
    actual = sha256(destination)
    if actual != PYTHON_SHA256:
        raise RuntimeError(
            f"CPython archive hash mismatch: expected {PYTHON_SHA256}, found {actual}"
        )


def native_manifest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in NATIVE_SUFFIXES
    }


def write_hash_manifest(path: Path, values: dict[str, str]) -> None:
    path.write_text(
        "\n".join(f"{digest}  {name}" for name, digest in sorted(values.items())) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def verify_pure_wheel(path: Path) -> None:
    if not path.name.lower().endswith("-none-any.whl"):
        raise RuntimeError(f"hybrid host accepts only pure-Python wheels: {path.name}")
    with zipfile.ZipFile(path) as archive:
        native = [
            name for name in archive.namelist() if Path(name).suffix.lower() in NATIVE_SUFFIXES
        ]
    if native:
        raise RuntimeError(f"pure-Python wheel contains native content: {path.name}: {native[:5]}")


def stage_pure_python_wheels(runtime: Path, download_root: Path) -> dict[str, str]:
    wheelhouse = download_root / "compat-wheelhouse"
    if wheelhouse.exists():
        shutil.rmtree(wheelhouse)
    wheelhouse.mkdir(parents=True)
    requirements = ROOT / "packaging/windows/compat-runtime-requirements.lock"
    for line in requirements.read_text(encoding="utf-8").splitlines():
        match = REQUIREMENT_LINE.fullmatch(line.strip())
        if match is None:
            raise RuntimeError(f"invalid compatibility requirement: {line!r}")
        name = match.group("name")
        version = match.group("version")
        expected_hash = match.group("sha256")
        with urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=60) as response:
            metadata = json.load(response)
        candidates = [
            item
            for item in metadata.get("urls", [])
            if item.get("packagetype") == "bdist_wheel"
            and str(item.get("filename", "")).lower().endswith("-none-any.whl")
            and item.get("digests", {}).get("sha256") == expected_hash
        ]
        if len(candidates) != 1:
            raise RuntimeError(
                f"expected one hash-matched pure wheel for {name}=={version}, "
                f"found {len(candidates)}"
            )
        candidate = candidates[0]
        filename = str(candidate["filename"])
        destination = wheelhouse / filename
        with (
            urlopen(str(candidate["url"]), timeout=120) as response,
            destination.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
        if sha256(destination) != expected_hash:
            raise RuntimeError(f"downloaded compatibility wheel hash mismatch: {filename}")
    wheels = runtime / "wheels"
    wheels.mkdir()
    manifest: dict[str, str] = {}
    for source in sorted(wheelhouse.glob("*.whl")):
        verify_pure_wheel(source)
        destination = wheels / source.name
        shutil.copy2(source, destination)
        manifest[f"wheels/{destination.name}"] = sha256(destination)
    if len(manifest) != 4:
        raise RuntimeError(f"expected four reviewed pure-Python wheels, found {len(manifest)}")
    return manifest


def configure_runtime(runtime: Path, wheel_manifest: dict[str, str]) -> None:
    pth = runtime / "python313._pth"
    if not pth.is_file():
        raise RuntimeError("official embedded runtime is missing python313._pth")
    lines = ["python313.zip", ".", "../app", *sorted(wheel_manifest)]
    pth.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def validate_web(web_dist: Path) -> dict[str, str]:
    required = (
        web_dist / "index.html",
        web_dist / "vendor/pyodide/pyodide.mjs",
        web_dist / "vendor/pyodide/pyodide.asm.wasm",
        web_dist / "vendor/pyodide/python_stdlib.zip",
        web_dist / "vendor/pyodide/pyodide-lock.json",
        web_dist / "vendor/pyodide/PYODIDE_ASSETS.sha256",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"offline browser runtime is incomplete: {missing}")
    wasm_files = sorted(web_dist.rglob("*.wasm"))
    if len(wasm_files) < 3:
        raise RuntimeError(
            "browser bundle must contain Pyodide, DuckDB-Wasm, and HiGHS-Wasm modules"
        )
    return {
        path.relative_to(web_dist).as_posix(): sha256(path)
        for path in sorted(web_dist.rglob("*"))
        if path.is_file()
    }


def validate_stage(stage: Path, cpython_native: dict[str, str]) -> None:
    expected_roots = {
        "DOCTOR.cmd",
        "Feed",
        "README-FIRST.txt",
        "Reports",
        "SETUP.cmd",
        "SHA256SUMS.txt",
        "WFMHub.cmd",
        "_system",
    }
    actual_roots = {path.name for path in stage.iterdir()}
    if actual_roots != expected_roots:
        raise RuntimeError(
            f"hybrid root mismatch: missing={sorted(expected_roots - actual_roots)}, "
            f"unexpected={sorted(actual_roots - expected_roots)}"
        )
    status_policy = stage / "_system/config/actual_status_rules.toml"
    if not status_policy.is_file():
        raise RuntimeError("hybrid host is missing the governed Agent Status policy")
    queue_mapping = stage / "_system/config/queue_mapping.csv"
    service_rules = stage / "_system/config/service_rules.toml"
    if not queue_mapping.is_file() or not service_rules.is_file():
        raise RuntimeError("hybrid host is missing governed Call-by-Call configuration")
    actual_native = native_manifest(stage)
    expected_prefixed = {f"_system/runtime/{name}": value for name, value in cpython_native.items()}
    if actual_native != expected_prefixed:
        added = sorted(set(actual_native) - set(expected_prefixed))
        missing = sorted(set(expected_prefixed) - set(actual_native))
        changed = sorted(
            name
            for name in set(actual_native) & set(expected_prefixed)
            if actual_native[name] != expected_prefixed[name]
        )
        raise RuntimeError(
            "hybrid host contains native files outside the official CPython archive: "
            f"added={added}, missing={missing}, changed={changed}"
        )
    forbidden_suffixes = {".sqlite", ".sqlite3", ".duckdb", ".parquet", ".log"}
    forbidden = [
        path
        for path in stage.rglob("*")
        if path.is_file() and path.suffix.lower() in forbidden_suffixes
    ]
    if forbidden:
        raise RuntimeError(f"hybrid stage contains user/runtime data: {forbidden[:10]}")


def build_stage(web_dist: Path) -> Path:
    browser_manifest = validate_web(web_dist)
    build_root = ROOT / "build/hybrid-spike"
    if build_root.exists():
        shutil.rmtree(build_root)
    stage = build_root / TOP_LEVEL
    runtime = stage / "_system/runtime"
    manifests = stage / "_system/manifests"
    runtime.mkdir(parents=True)
    manifests.mkdir(parents=True)

    archive_path = ROOT / "build/downloads" / PYTHON_ARCHIVE
    download_verified(archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(runtime)
    cpython_native = native_manifest(runtime)
    wheel_manifest = stage_pure_python_wheels(runtime, build_root)
    configure_runtime(runtime, wheel_manifest)

    copy_tree(ROOT / "src/wfmhub2_compat", stage / "_system/app/wfmhub2_compat")
    copy_tree(ROOT / "config", stage / "_system/config")
    copy_tree(web_dist, stage / "_system/web")
    copy_windows_text(ROOT / "packaging/windows/WFMHub-Hybrid.cmd", stage / "WFMHub.cmd")
    copy_windows_text(ROOT / "packaging/windows/DOCTOR-Hybrid.cmd", stage / "DOCTOR.cmd")
    copy_windows_text(ROOT / "packaging/windows/SETUP-Hybrid.cmd", stage / "SETUP.cmd")

    (stage / "Feed").mkdir()
    (stage / "Feed/README.txt").write_text(
        "WFMHub reads the configured local source folder without uploads or copying.\n",
        encoding="utf-8",
        newline="\r\n",
    )
    (stage / "Reports").mkdir()
    (stage / "Reports/README.txt").write_text(
        "Browser compatibility reports are saved under data\\compatibility.\n",
        encoding="utf-8",
        newline="\r\n",
    )
    (stage / "README-FIRST.txt").write_text(
        "\n".join(
            (
                "WFMHub 2 Phase 1 Source Preview",
                "",
                "Phase 1 preview: local source readiness, not yet the replacement WFM product.",
                "",
                "1. Extract the complete ZIP to a normal local writable folder.",
                "2. Run DOCTOR.cmd. It tests the proven Python/SQLite/Excel host.",
                "3. Run SETUP.cmd and paste the existing folder containing FTE and Verint.",
                "   Your source files remain in place and are read only.",
                "4. Run WFMHub.cmd. Microsoft Edge opens the local workbench.",
                "5. Select Refresh local sources on Command to inspect roster, schedule,",
                "   Agent Status, LILO, and Call-by-Call evidence. Storm sources are optional.",
                "6. Govern > Compatibility Doctor still runs the five browser probes.",
                "7. Close the browser tab and press Ctrl+C in the WFMHub console.",
                "",
                "No installation, administrator rights, file upload, "
                "or runtime internet is required.",
                "Do not use GitHub's Source code ZIP.",
            )
        )
        + "\n",
        encoding="utf-8",
        newline="\r\n",
    )

    write_hash_manifest(manifests / "CPYTHON_NATIVE.sha256", cpython_native)
    write_hash_manifest(manifests / "PURE_PYTHON_WHEELS.sha256", wheel_manifest)
    write_hash_manifest(manifests / "BROWSER_ASSETS.sha256", browser_manifest)
    write_json(
        manifests / "RUNTIME_ORIGIN.json",
        {
            "archive": PYTHON_ARCHIVE,
            "archive_sha256": PYTHON_SHA256,
            "architecture": "amd64",
            "origin": PYTHON_URL,
            "python_version": PYTHON_VERSION,
        },
    )
    write_json(
        manifests / "PROFILE.json",
        {
            "browser_capabilities": ["duckdb-wasm", "opfs", "pyodide", "highs-wasm"],
            "official_cpython_native_files": len(cpython_native),
            "profile": "phase0.4-hybrid-compatibility-spike",
            "third_party_host_native_files": 0,
            "version": PRODUCT_VERSION,
        },
    )
    payload = {
        path.as_posix(): sha256(stage / path)
        for path in relative_files(stage)
        if path.as_posix() != "SHA256SUMS.txt"
    }
    write_hash_manifest(stage / "SHA256SUMS.txt", payload)
    validate_stage(stage, cpython_native)
    return stage


def write_deterministic_zip(stage: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.unlink(missing_ok=True)
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for relative in relative_files(stage):
            info = zipfile.ZipInfo(f"{TOP_LEVEL}/{relative.as_posix()}", (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0
            archive.writestr(
                info,
                (stage / relative).read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )


def verify_archive(stage: Path, archive_path: Path) -> dict[str, object]:
    expected = sorted(f"{TOP_LEVEL}/{path.as_posix()}" for path in relative_files(stage))
    with tempfile.TemporaryDirectory(prefix="wfmhub2-hybrid-verify-") as raw:
        destination = Path(raw)
        with zipfile.ZipFile(archive_path) as archive:
            members = sorted(name for name in archive.namelist() if not name.endswith("/"))
            counts = Counter(members)
            duplicates = sorted(name for name, count in counts.items() if count > 1)
            if members != expected or duplicates:
                raise RuntimeError(
                    "hybrid ZIP inventory mismatch: "
                    f"missing={sorted(set(expected) - set(members))[:10]}, "
                    f"unexpected={sorted(set(members) - set(expected))[:10]}, "
                    f"duplicates={duplicates[:10]}"
                )
            archive.extractall(destination)
        extracted = destination / TOP_LEVEL
        for relative in relative_files(stage):
            if sha256(stage / relative) != sha256(extracted / relative):
                raise RuntimeError(f"hybrid ZIP hash mismatch: {relative.as_posix()}")
        lines = (extracted / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
        for line in lines:
            match = HASH_LINE.fullmatch(line)
            if match is None:
                raise RuntimeError(f"invalid SHA256SUMS line: {line}")
            digest, name = match.groups()
            if sha256(extracted / name) != digest:
                raise RuntimeError(f"SHA256SUMS mismatch: {name}")
    return {
        "archive": archive_path.name,
        "archive_bytes": archive_path.stat().st_size,
        "archive_sha256": sha256(archive_path),
        "expanded_and_verified": True,
        "member_count": len(expected),
        "schema_version": 1,
    }


def build(web_dist: Path) -> Path:
    stage = build_stage(web_dist.resolve())
    archive = ROOT / f"dist/WFMHub-2-v{PRODUCT_VERSION}-windows-x64.zip"
    write_deterministic_zip(stage, archive)
    evidence = verify_archive(stage, archive)
    archive.with_suffix(archive.suffix + ".sha256").write_text(
        f"{evidence['archive_sha256']}  {archive.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    evidence_path = ROOT / "qualification-evidence/hybrid-spike-archive.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(evidence_path, evidence)
    print(f"Hybrid compatibility archive: {archive}")
    print(f"Archive SHA-256: {evidence['archive_sha256']}")
    print(f"Verified members: {evidence['member_count']}")
    return archive


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web-dist", type=Path, default=ROOT / "web/dist")
    args = parser.parse_args(argv)
    build(args.web_dist)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
