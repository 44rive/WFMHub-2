[CmdletBinding()]
param(
  [string]$ExtensionPath = "",
  [string]$MsvcRuntime = "",
  [string]$WebDist = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $IsWindows) {
  throw "The embedded portable release must be assembled on Windows x64."
}
if ([string]::IsNullOrWhiteSpace($ExtensionPath)) {
  $ExtensionPath = Join-Path $Root "packaging/duckdb_extensions/ducklake.duckdb_extension"
}
if ([string]::IsNullOrWhiteSpace($WebDist)) {
  $WebDist = Join-Path $Root "web/dist"
}
if ([string]::IsNullOrWhiteSpace($MsvcRuntime)) {
  $MsvcRuntime = Join-Path $Root "build/msvc-runtime"
}

Push-Location $Root
try {
  uv run --frozen python packaging/windows/build_embedded_portable.py `
    --ducklake-extension $ExtensionPath `
    --msvc-runtime $MsvcRuntime `
    --web-dist $WebDist
}
finally {
  Pop-Location
}
