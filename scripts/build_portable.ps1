param(
  [string]$TargetTriple = "x86_64-pc-windows-msvc",
  [string]$DuckDBVersion = "1.5.5",
  [switch]$UseStagedDuckLake
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

Write-Host "== WFMHub 2 portable build =="
Write-Host "Target: $TargetTriple"

if (-not $IsWindows) {
  throw "The portable release build currently supports Windows only. Run the source-quality workflow on other platforms."
}

Write-Host "[1/7] Sync the frozen Python 3.14 environment"
uv sync --frozen --extra dev

Write-Host "[2/7] Stage and compatibility-test the pinned DuckLake extension"
$StageArguments = @(
  "-DuckDBVersion", $DuckDBVersion,
  "-Platform", "windows_amd64"
)
if ($UseStagedDuckLake) {
  $StageArguments += "-UseExisting"
}
& (Join-Path $Root "scripts/stage_ducklake.ps1") @StageArguments

$Extension = Join-Path $Root "packaging/duckdb_extensions/ducklake.duckdb_extension"
uv run --frozen python scripts/verify_ducklake.py `
  --extension $Extension `
  --expected-duckdb $DuckDBVersion `
  --expected-sha256 "4546a5c6d9bc52cc122bc76e521c996e1ac31e71a25e01c531db8d3bb65e2ef0"

Write-Host "[3/7] Exercise native analytical dependencies"
uv run --frozen python scripts/probe_native_stack.py

Write-Host "[4/7] Build Python engine sidecar"
uv run --frozen pyinstaller --noconfirm --clean packaging/wfmhub-engine.spec

$SourceEngine = Join-Path $Root "dist/wfmhub-engine.exe"
if (-not (Test-Path $SourceEngine -PathType Leaf)) {
  throw "PyInstaller did not produce the expected sidecar at $SourceEngine"
}
$TauriBinDir = Join-Path $Root "src-tauri/binaries"
$TargetEngine = Join-Path $TauriBinDir "wfmhub-engine-$TargetTriple.exe"
New-Item -ItemType Directory -Force -Path $TauriBinDir | Out-Null
Copy-Item $SourceEngine $TargetEngine -Force

Write-Host "[5/7] Install the frozen frontend dependency graph"
corepack enable
pnpm install --frozen-lockfile

Write-Host "[6/7] Build frontend and validate the locked Rust graph"
pnpm build:web
cargo metadata --manifest-path src-tauri/Cargo.toml --locked --format-version 1 | Out-Null

Write-Host "[7/7] Build Tauri desktop bundle"
pnpm exec tauri build --ci

Write-Host "Portable desktop build completed."
Write-Host "Engine SHA-256: $((Get-FileHash -Algorithm SHA256 -Path $SourceEngine).Hash.ToLowerInvariant())"
Write-Host "DuckLake SHA-256: $((Get-FileHash -Algorithm SHA256 -Path $Extension).Hash.ToLowerInvariant())"
