[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

Write-Host "== WFMHub 2 Phase 0.4 hybrid compatibility spike =="

Write-Host "[1/4] Install frozen browser dependencies"
corepack enable
pnpm install --frozen-lockfile

Write-Host "[2/4] Stage verified self-hosted Pyodide packages"
uv run --no-project --python 3.13.7 python scripts/stage_browser_runtime.py

Write-Host "[3/4] Build the browser compatibility interface"
pnpm build:web

Write-Host "[4/4] Assemble and verify the official-CPython hybrid ZIP"
uv run --no-project --python 3.13.7 python packaging/windows/build_hybrid_spike.py `
  --web-dist web/dist
