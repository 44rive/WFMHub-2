param(
  [string]$TargetTriple = "x86_64-pc-windows-msvc"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

Write-Host "== WFMHub 2 portable build =="
Write-Host "Target: $TargetTriple"

Write-Host "[1/5] Sync Python 3.14 environment"
uv sync --extra dev

Write-Host "[2/5] Build Python engine sidecar"
uv run pyinstaller --noconfirm --clean packaging/wfmhub-engine.spec

$SourceEngine = Join-Path $Root "dist/wfmhub-engine.exe"
$TauriBinDir = Join-Path $Root "src-tauri/binaries"
$TargetEngine = Join-Path $TauriBinDir "wfmhub-engine-$TargetTriple.exe"
New-Item -ItemType Directory -Force -Path $TauriBinDir | Out-Null
Copy-Item $SourceEngine $TargetEngine -Force

Write-Host "[3/5] Verify locally bundled DuckLake extension"
$Extension = Join-Path $Root "packaging/duckdb_extensions/ducklake.duckdb_extension"
if (-not (Test-Path $Extension)) {
  throw "DuckLake extension not staged at $Extension. Release builds must bundle the exact extension matching DuckDB/platform."
}

Write-Host "[4/5] Install/build frontend"
corepack enable
pnpm install
pnpm build:web

Write-Host "[5/5] Build Tauri desktop bundle"
pnpm desktop:build

Write-Host "Portable desktop build completed."
