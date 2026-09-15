param(
  [string]$PythonVersion = "3.13.7",
  [string]$Output = "dist/WFMHub-2-Portable"
)

$ErrorActionPreference = "Stop"
Write-Host "Portable build skeleton for WFMHub 2"
Write-Host "Python: $PythonVersion"
Write-Host "Output: $Output"
Write-Host "TODO: download verified embeddable CPython + hashed wheels, install app, build React, copy runtime layout."
