#!/usr/bin/env python3
"""Build the verified Windows ZIP around official embedded CPython.

The produced release contains source Python, extracted locked dependencies, and
static web assets. It intentionally contains no WFMHub/Tauri/PyInstaller
executable and performs no installation or dependency extraction at runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PYTHON_VERSION = "3.14.7"
PYTHON_ARCHIVE = f"python-{PYTHON_VERSION}-embed-amd64.zip"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{PYTHON_ARCHIVE}"
PYTHON_SHA256 = "d297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15"
DUCKLAKE_SHA256 = "4546a5c6d9bc52cc122bc76e521c996e1ac31e71a25e01c531db8d3bb65e2ef0"
TOP_LEVEL = "WFMHub-2"
NATIVE_SUFFIXES = (".dll", ".exe", ".pyd", ".duckdb_extension")
HASH_LINE = re.compile(r"^([0-9a-f]{64})  (.+)$")
REQUIRED_MSVC_RUNTIME = {"msvcp140.dll", "vcomp140.dll"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


def download_verified(url: str, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = destination.with_suffix(f"{destination.suffix}.partial")
        temporary.unlink(missing_ok=True)
        print(f"Downloading {url}")
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        temporary.replace(destination)
    actual_sha256 = sha256(destination)
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            f"Pinned download hash mismatch for {destination.name}: "
            f"expected {expected_sha256}, found {actual_sha256}"
        )


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print("+", subprocess.list2cmdline(command))
    subprocess.run(command, cwd=cwd, check=True)


def relative_files(root: Path) -> list[Path]:
    return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())


def native_manifest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in NATIVE_SUFFIXES
    }


def write_hash_manifest(path: Path, values: dict[str, str]) -> None:
    lines = [f"{digest}  {name}" for name, digest in sorted(values.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def normalized_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def project_metadata() -> tuple[str, set[str]]:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    version = str(project["version"])
    direct_dependencies = {
        normalized_distribution_name(re.split(r"[<>=!~\[ ;]", dependency, maxsplit=1)[0])
        for dependency in project["dependencies"]
    }
    package_text = (ROOT / "src/wfmhub2/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "([^"]+)"$', package_text, flags=re.MULTILINE)
    if match is None or match.group(1) != version:
        raise RuntimeError("pyproject.toml and wfmhub2.__version__ must match")
    return version, direct_dependencies


def installed_distributions(site_packages: Path) -> dict[str, str]:
    distributions: dict[str, str] = {}
    for metadata in sorted(site_packages.glob("*.dist-info/METADATA")):
        name: str | None = None
        version: str | None = None
        for line in metadata.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Name: "):
                name = normalized_distribution_name(line[6:].strip())
            elif line.startswith("Version: "):
                version = line[9:].strip()
            if name is not None and version is not None:
                break
        if name is not None and version is not None:
            distributions[name] = version
    return distributions


def configure_embedded_runtime(runtime: Path) -> None:
    pth = runtime / "python314._pth"
    if not pth.is_file():
        raise RuntimeError(f"Official embedded runtime is missing {pth.name}")
    original_lines = pth.read_text(encoding="utf-8").splitlines()
    python_zip = next((line for line in original_lines if line == "python314.zip"), None)
    if python_zip is None:
        raise RuntimeError("Official embedded runtime _pth does not reference python314.zip")
    # Keep the runtime isolated from user/system installs and ignore arbitrary
    # `.pth` execution. Every application import root is listed explicitly.
    lines = [python_zip, ".", "../site-packages", "../app"]
    pth.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def export_and_install_dependencies(
    uv: str,
    site_packages: Path,
    manifests: Path,
    direct_dependencies: set[str],
) -> dict[str, str]:
    requirements = manifests / "runtime-requirements.txt"
    run(
        [
            uv,
            "export",
            "--quiet",
            "--frozen",
            "--no-dev",
            "--no-header",
            "--no-emit-project",
            "--format",
            "requirements.txt",
            "--output-file",
            str(requirements),
        ]
    )
    exported = requirements.read_text(encoding="utf-8")
    if "--hash=sha256:" not in exported:
        raise RuntimeError("uv export produced no dependency hashes")

    site_packages.mkdir(parents=True, exist_ok=True)
    run(
        [
            uv,
            "pip",
            "install",
            "--python",
            sys.executable,
            "--target",
            str(site_packages),
            "--require-hashes",
            "--no-deps",
            "--no-build",
            "--link-mode",
            "copy",
            "--requirements",
            str(requirements),
        ]
    )
    distributions = installed_distributions(site_packages)
    missing = sorted(direct_dependencies - set(distributions))
    if missing:
        raise RuntimeError(f"Portable site-packages is missing direct dependencies: {missing}")
    executable_pth_files = sorted(
        path.relative_to(site_packages) for path in site_packages.rglob("*.pth")
    )
    if executable_pth_files:
        raise RuntimeError(
            "Portable dependencies unexpectedly require executable .pth processing: "
            f"{executable_pth_files}"
        )
    return distributions


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def copy_msvc_runtime(source: Path, target: Path, manifests: Path) -> None:
    manifest_path = source / "MSVC_RUNTIME.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Audited Microsoft runtime manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise RuntimeError("Microsoft runtime manifest does not contain a file list")
    names = {entry.get("name") for entry in entries if isinstance(entry, dict)}
    if names != REQUIRED_MSVC_RUNTIME:
        raise RuntimeError(
            "Microsoft runtime manifest differs from the required file set: "
            f"expected={sorted(REQUIRED_MSVC_RUNTIME)}, found={sorted(str(name) for name in names)}"
        )

    target.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("Microsoft runtime manifest contains an invalid entry")
        name = entry.get("name")
        expected_hash = entry.get("sha256")
        if not isinstance(name, str) or not isinstance(expected_hash, str):
            raise RuntimeError("Microsoft runtime manifest entry is missing name/hash")
        if entry.get("architecture") != "x86_64" or entry.get("signature_status") != "Valid":
            raise RuntimeError(f"Microsoft runtime audit failed for {name}")
        if "Microsoft Corporation" not in str(entry.get("signer_subject")):
            raise RuntimeError(f"Microsoft runtime signer is not approved for {name}")
        source_file = source / name
        if not source_file.is_file() or sha256(source_file) != expected_hash:
            raise RuntimeError(f"Microsoft runtime staged file/hash mismatch: {name}")
        shutil.copy2(source_file, target / name)

    write_json(manifests / "MSVC_RUNTIME.json", manifest)


def validate_no_user_data(stage: Path) -> None:
    forbidden_roots = (stage / "data", stage / "database")
    if any(path.exists() for path in forbidden_roots):
        raise RuntimeError("Portable stage contains application database/runtime data")
    for directory in (stage / "Feed", stage / "Reports"):
        unexpected = [
            path for path in directory.rglob("*") if path.is_file() and path.name != "README.txt"
        ]
        if unexpected:
            raise RuntimeError(f"Portable stage contains operational files under {directory.name}")
    forbidden_suffixes = {".sqlite", ".sqlite3", ".duckdb", ".ducklake", ".parquet", ".log"}
    application_areas = [stage / "config", stage / "_system/app", stage / "_system/web"]
    forbidden = [
        path
        for area in application_areas
        for path in area.rglob("*")
        if path.is_file() and path.suffix.lower() in forbidden_suffixes
    ]
    if forbidden:
        raise RuntimeError(f"Portable stage contains forbidden runtime/user data: {forbidden[:10]}")


def validate_release_layout(stage: Path, cpython_native: dict[str, str]) -> None:
    expected_roots = {
        "DOCTOR.cmd",
        "Feed",
        "README-FIRST.txt",
        "Reports",
        "SHA256SUMS.txt",
        "WFMHub.cmd",
        "_system",
        "config",
    }
    actual_roots = {path.name for path in stage.iterdir()}
    if actual_roots != expected_roots:
        raise RuntimeError(
            f"Portable root differs from the approved layout: "
            f"missing={sorted(expected_roots - actual_roots)}, "
            f"extra={sorted(actual_roots - expected_roots)}"
        )
    for forbidden in ("WFMHub.exe", "wfmhub-engine.exe", "src-tauri"):
        if (stage / forbidden).exists():
            raise RuntimeError(f"Forbidden legacy desktop artifact was packaged: {forbidden}")
    runtime = stage / "_system/runtime"
    runtime_native = native_manifest(runtime)
    changed_official = {
        name: (digest, runtime_native.get(name))
        for name, digest in cpython_native.items()
        if runtime_native.get(name) != digest
    }
    if changed_official:
        raise RuntimeError(f"Official CPython native runtime changed: {changed_official}")
    extra_runtime_native = set(runtime_native) - set(cpython_native)
    if extra_runtime_native != REQUIRED_MSVC_RUNTIME:
        raise RuntimeError(
            "Embedded runtime has an unexpected supplemental native set: "
            f"{sorted(extra_runtime_native)}"
        )
    validate_no_user_data(stage)


def build_stage(args: argparse.Namespace) -> tuple[Path, str]:
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeError("Embedded portable releases must be built on Windows x64")
    if sys.version_info[:3] != (3, 14, 7):
        raise RuntimeError(f"Builder must run under CPython 3.14.7, found {sys.version.split()[0]}")

    version, direct_dependencies = project_metadata()
    build_root = ROOT / "build/embedded-portable"
    if build_root.exists():
        shutil.rmtree(build_root)
    stage = build_root / TOP_LEVEL
    runtime = stage / "_system/runtime"
    site_packages = stage / "_system/site-packages"
    manifests = stage / "_system/manifests"
    runtime.mkdir(parents=True)
    manifests.mkdir(parents=True)

    python_archive = ROOT / "build/downloads" / PYTHON_ARCHIVE
    download_verified(PYTHON_URL, python_archive, PYTHON_SHA256)
    with zipfile.ZipFile(python_archive) as archive:
        archive.extractall(runtime)
    cpython_native = native_manifest(runtime)
    configure_embedded_runtime(runtime)

    distributions = export_and_install_dependencies(
        args.uv,
        site_packages,
        manifests,
        direct_dependencies,
    )
    copy_tree(ROOT / "src/wfmhub2", stage / "_system/app/wfmhub2")
    copy_tree(Path(args.web_dist).resolve(), stage / "_system/web")

    extension_source = Path(args.ducklake_extension).resolve()
    if not extension_source.is_file() or sha256(extension_source) != DUCKLAKE_SHA256:
        raise RuntimeError("DuckLake extension is missing or does not match the reviewed binary")
    extension_target = stage / "_system/duckdb_extensions/ducklake.duckdb_extension"
    extension_target.parent.mkdir(parents=True)
    shutil.copy2(extension_source, extension_target)
    copy_msvc_runtime(
        Path(args.msvc_runtime).resolve(),
        runtime,
        manifests,
    )

    shutil.copy2(ROOT / "packaging/windows/WFMHub.cmd", stage / "WFMHub.cmd")
    shutil.copy2(ROOT / "packaging/windows/DOCTOR.cmd", stage / "DOCTOR.cmd")
    config_target = stage / "config"
    config_target.mkdir()
    shutil.copy2(ROOT / "config/services.example.yaml", config_target / "services.example.yaml")

    (stage / "Feed").mkdir()
    (stage / "Feed/README.txt").write_text(
        "Place local source extracts here. WFMHub treats source files as read-only.\n",
        encoding="utf-8",
        newline="\r\n",
    )
    (stage / "Reports").mkdir()
    (stage / "Reports/README.txt").write_text(
        "WFMHub writes generated local reports here.\n",
        encoding="utf-8",
        newline="\r\n",
    )
    (stage / "README-FIRST.txt").write_text(
        "\n".join(
            (
                "WFMHub 2 portable Windows x64 preview",
                "",
                "1. Extract the complete ZIP to a normal local writable folder.",
                "2. Run DOCTOR.cmd once to test company-policy compatibility.",
                "3. Run WFMHub.cmd to open the local browser interface.",
                "",
                "Keep every file under WFMHub-2 together.",
                "Do not run inside the ZIP and do not use GitHub's Source code ZIP.",
                "No installation, administrator rights, or runtime internet is required.",
                "All application state remains in this local WFMHub-2 folder.",
            )
        )
        + "\n",
        encoding="utf-8",
        newline="\r\n",
    )

    write_hash_manifest(manifests / "CPYTHON_NATIVE.sha256", cpython_native)
    write_hash_manifest(manifests / "NATIVE_FILES.sha256", native_manifest(stage / "_system"))
    write_json(manifests / "DISTRIBUTIONS.json", distributions)
    write_json(
        manifests / "RUNTIME_ORIGIN.json",
        {
            "archive": PYTHON_ARCHIVE,
            "archive_bytes": python_archive.stat().st_size,
            "archive_sha256": PYTHON_SHA256,
            "architecture": "amd64",
            "origin": PYTHON_URL,
            "python_version": PYTHON_VERSION,
        },
    )
    write_json(
        manifests / "BUILD_INPUTS.json",
        {
            "ducklake_sha256": DUCKLAKE_SHA256,
            "pnpm_lock_sha256": sha256(ROOT / "pnpm-lock.yaml"),
            "pyproject_sha256": sha256(ROOT / "pyproject.toml"),
            "uv_lock_sha256": sha256(ROOT / "uv.lock"),
            "version": version,
        },
    )

    payload = {
        path.as_posix(): sha256(stage / path)
        for path in relative_files(stage)
        if path.as_posix() != "SHA256SUMS.txt"
    }
    write_hash_manifest(stage / "SHA256SUMS.txt", payload)
    validate_release_layout(stage, cpython_native)
    return stage, version


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
            source = stage / relative
            info = zipfile.ZipInfo(f"{TOP_LEVEL}/{relative.as_posix()}", (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0
            with source.open("rb") as stream:
                archive.writestr(
                    info, stream.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9
                )


def verify_archive(stage: Path, archive_path: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="wfmhub2-embedded-verify-") as temporary:
        extracted_root = Path(temporary)
        with zipfile.ZipFile(archive_path) as archive:
            archive_members = sorted(name for name in archive.namelist() if not name.endswith("/"))
            archive.extractall(extracted_root)
        verified = extracted_root / TOP_LEVEL
        # WindowsPath sorts case-insensitively while ZIP member names are plain,
        # case-sensitive strings. Canonicalize both inventories as strings so
        # mixed-case dependency filenames do not create a false mismatch.
        expected_members = sorted(
            f"{TOP_LEVEL}/{path.as_posix()}" for path in relative_files(stage)
        )
        if archive_members != expected_members:
            archive_counts = Counter(archive_members)
            archive_set = set(archive_members)
            expected_set = set(expected_members)
            duplicates = sorted(name for name, count in archive_counts.items() if count > 1)
            raise RuntimeError(
                "Portable ZIP members differ from the staged payload: "
                f"missing={sorted(expected_set - archive_set)[:10]}, "
                f"unexpected={sorted(archive_set - expected_set)[:10]}, "
                f"duplicates={duplicates[:10]}"
            )
        if relative_files(verified) != relative_files(stage):
            raise RuntimeError("Expanded portable ZIP file set differs from the staged payload")
        for relative in relative_files(stage):
            if sha256(stage / relative) != sha256(verified / relative):
                raise RuntimeError(f"Expanded portable ZIP hash mismatch: {relative.as_posix()}")

        checksum_lines = (verified / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
        expected_payload = [
            path for path in relative_files(verified) if path.as_posix() != "SHA256SUMS.txt"
        ]
        if len(checksum_lines) != len(expected_payload):
            raise RuntimeError("SHA256SUMS.txt does not cover every payload file exactly once")
        seen: set[str] = set()
        for line in checksum_lines:
            match = HASH_LINE.fullmatch(line)
            if match is None:
                raise RuntimeError(f"Invalid SHA256SUMS.txt line: {line}")
            expected_hash, name = match.groups()
            if name in seen or Path(name) not in expected_payload:
                raise RuntimeError(f"Duplicate or unexpected SHA256SUMS.txt member: {name}")
            seen.add(name)
            if sha256(verified / name) != expected_hash:
                raise RuntimeError(f"SHA256SUMS.txt hash mismatch: {name}")

    return {
        "archive": archive_path.name,
        "archive_bytes": archive_path.stat().st_size,
        "archive_sha256": sha256(archive_path),
        "expanded_and_verified": True,
        "member_count": len(expected_members),
        "members": expected_members,
        "schema_version": 2,
    }


def build(args: argparse.Namespace) -> Path:
    stage, version = build_stage(args)
    archive = ROOT / f"dist/WFMHub-2-v{version}-windows-x64-portable.zip"
    write_deterministic_zip(stage, archive)
    evidence = verify_archive(stage, archive)
    checksum = archive.with_suffix(f"{archive.suffix}.sha256")
    checksum.write_text(
        f"{evidence['archive_sha256']}  {archive.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    evidence_path = ROOT / "qualification-evidence/portable-archive.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(evidence_path, evidence)
    print(f"Portable archive: {archive}")
    print(f"Archive SHA-256: {evidence['archive_sha256']}")
    print(f"Verified members: {evidence['member_count']}")
    return archive


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uv", default="uv")
    parser.add_argument(
        "--ducklake-extension",
        type=Path,
        default=ROOT / "packaging/duckdb_extensions/ducklake.duckdb_extension",
    )
    parser.add_argument("--web-dist", type=Path, default=ROOT / "web/dist")
    parser.add_argument("--msvc-runtime", type=Path, default=ROOT / "build/msvc-runtime")
    args = parser.parse_args(argv)
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
