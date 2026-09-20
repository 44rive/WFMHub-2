[CmdletBinding()]
param(
  [string]$DuckDBVersion = "1.5.5",
  [switch]$UseStagedDuckLake
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

if (-not $IsWindows) {
  throw "The embedded portable release must be built on Windows x64."
}
if (-not [Environment]::Is64BitOperatingSystem) {
  throw "The embedded portable release requires Windows x64."
}

Write-Host "== WFMHub 2 official-CPython portable build =="

Write-Host "[1/7] Sync the frozen Python 3.14.7 build environment"
uv sync --frozen --extra dev --python 3.14.7

Write-Host "[2/7] Install and build the frozen React frontend"
corepack enable
pnpm install --frozen-lockfile
pnpm build:web

Write-Host "[3/7] Stage and verify the pinned offline DuckLake extension"
if ($UseStagedDuckLake) {
  & (Join-Path $Root "scripts/stage_ducklake.ps1") `
    -DuckDBVersion $DuckDBVersion `
    -Platform "windows_amd64" `
    -UseExisting
}
else {
  & (Join-Path $Root "scripts/stage_ducklake.ps1") `
    -DuckDBVersion $DuckDBVersion `
    -Platform "windows_amd64"
}

$Extension = Join-Path $Root "packaging/duckdb_extensions/ducklake.duckdb_extension"
uv run --frozen python scripts/verify_ducklake.py `
  --extension $Extension `
  --expected-duckdb $DuckDBVersion `
  --expected-sha256 "4546a5c6d9bc52cc122bc76e521c996e1ac31e71a25e01c531db8d3bb65e2ef0"

Write-Host "[4/7] Exercise the complete locked analytical dependency graph"
uv run --frozen python scripts/probe_native_stack.py

Write-Host "[5/7] Stage signed Microsoft native support libraries"
& (Join-Path $Root "scripts/stage_msvc_runtime.ps1")

Write-Host "[6/7] Assemble the official embedded CPython runtime"
uv run --frozen python packaging/windows/build_embedded_portable.py `
  --ducklake-extension $Extension `
  --msvc-runtime (Join-Path $Root "build/msvc-runtime") `
  --web-dist (Join-Path $Root "web/dist")

Write-Host "[7/7] Confirm the release contains no custom desktop executable"
$Stage = Join-Path $Root "build/embedded-portable/WFMHub-2"
$Forbidden = @(
  (Join-Path $Stage "WFMHub.exe"),
  (Join-Path $Stage "wfmhub-engine.exe")
)
foreach ($Path in $Forbidden) {
  if (Test-Path -LiteralPath $Path) {
    throw "Forbidden legacy executable was packaged: $Path"
  }
}

$RuntimePython = Join-Path $Stage "_system/runtime/python.exe"
if (-not (Test-Path -LiteralPath $RuntimePython -PathType Leaf)) {
  throw "Official embedded python.exe is missing from the portable stage."
}

Write-Host "Embedded portable build completed."
Write-Host "Embedded Python SHA-256: $((Get-FileHash -Algorithm SHA256 -LiteralPath $RuntimePython).Hash.ToLowerInvariant())"
Write-Host "DuckLake SHA-256: $((Get-FileHash -Algorithm SHA256 -LiteralPath $Extension).Hash.ToLowerInvariant())"
