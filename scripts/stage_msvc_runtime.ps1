[CmdletBinding()]
param(
  [string]$OutputDirectory = "",
  [string]$EvidencePath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $IsWindows -or -not [Environment]::Is64BitOperatingSystem) {
  throw "Microsoft runtime staging requires Windows x64."
}
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
  $OutputDirectory = Join-Path $Root "build/msvc-runtime"
}
if ([string]::IsNullOrWhiteSpace($EvidencePath)) {
  $EvidencePath = Join-Path $Root "qualification-evidence/msvc-runtime.json"
}

function Assert-X64PortableExecutable {
  param([string]$Path)

  $Bytes = [System.IO.File]::ReadAllBytes($Path)
  if ($Bytes.Length -lt 64) {
    throw "Native runtime file is too small to be a PE image: $Path"
  }
  $PeOffset = [BitConverter]::ToInt32($Bytes, 0x3c)
  if ($PeOffset -lt 0 -or ($PeOffset + 6) -gt $Bytes.Length) {
    throw "Native runtime file has an invalid PE header offset: $Path"
  }
  $Signature = [BitConverter]::ToUInt32($Bytes, $PeOffset)
  $Machine = [BitConverter]::ToUInt16($Bytes, $PeOffset + 4)
  if ($Signature -ne 0x00004550 -or $Machine -ne 0x8664) {
    throw "Native runtime file is not a Windows x64 PE image: $Path"
  }
}

$LockedLibraryDirectory = Join-Path $Root ".venv/Lib/site-packages/sklearn/.libs"
if (-not (Test-Path -LiteralPath $LockedLibraryDirectory -PathType Container)) {
  throw "Locked scikit-learn runtime directory is missing: $LockedLibraryDirectory"
}
$RequiredFiles = @("msvcp140.dll", "vcomp140.dll")
$ManifestFiles = @()

if (Test-Path -LiteralPath $OutputDirectory) {
  Remove-Item -LiteralPath $OutputDirectory -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
foreach ($Name in $RequiredFiles) {
  $Source = Join-Path $LockedLibraryDirectory $Name
  if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
    throw "Required Microsoft runtime file is missing from the locked scikit-learn wheel: $Source"
  }
  Assert-X64PortableExecutable -Path $Source
  $Signature = Get-AuthenticodeSignature -LiteralPath $Source
  if ($Signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    throw "Microsoft runtime signature is not valid for $Source ($($Signature.Status))."
  }
  if ($null -eq $Signature.SignerCertificate -or $Signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') {
    throw "Microsoft runtime signer is not Microsoft Corporation for $Source."
  }

  $Destination = Join-Path $OutputDirectory $Name
  Copy-Item -LiteralPath $Source -Destination $Destination -Force
  $SourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Source).Hash.ToLowerInvariant()
  $DestinationHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Destination).Hash.ToLowerInvariant()
  if ($DestinationHash -ne $SourceHash) {
    throw "Copied Microsoft runtime hash mismatch for $Name."
  }

  $Version = (Get-Item -LiteralPath $Source).VersionInfo.FileVersion
  $ManifestFiles += [ordered]@{
    architecture = "x86_64"
    file_version = $Version
    name = $Name
    sha256 = $SourceHash
    signature_status = [string]$Signature.Status
    signer_subject = $Signature.SignerCertificate.Subject
    signer_thumbprint = $Signature.SignerCertificate.Thumbprint
    source = "site-packages/sklearn/.libs/$Name"
  }
}

$Manifest = [ordered]@{
  files = $ManifestFiles
  origin = "Microsoft-signed runtime copies inside the hash-locked scikit-learn Windows wheel"
  schema_version = 1
}
$Serialized = $Manifest | ConvertTo-Json -Depth 5
$ManifestPath = Join-Path $OutputDirectory "MSVC_RUNTIME.json"
$Serialized | Set-Content -LiteralPath $ManifestPath -Encoding utf8
New-Item -ItemType Directory -Force -Path (Split-Path $EvidencePath -Parent) | Out-Null
$Serialized | Set-Content -LiteralPath $EvidencePath -Encoding utf8

Write-Host "Staged audited Microsoft x64 runtime files: $($RequiredFiles -join ', ')"
foreach ($File in $ManifestFiles) {
  Write-Host "$($File.name) $($File.file_version) SHA-256 $($File.sha256)"
}
