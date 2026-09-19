[CmdletBinding()]
param(
  [string]$TargetTriple = "x86_64-pc-windows-msvc"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $IsWindows) {
  throw "The portable ZIP can only be assembled on Windows."
}
if ($TargetTriple -ne "x86_64-pc-windows-msvc") {
  throw "Unsupported portable ZIP target triple: $TargetTriple"
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TauriConfig = Get-Content -LiteralPath (Join-Path $Root "src-tauri/tauri.conf.json") -Raw |
  ConvertFrom-Json
$Version = [string]$TauriConfig.version
if ($Version -notmatch '^[0-9A-Za-z][0-9A-Za-z.-]*$') {
  throw "The Tauri version '$Version' is not safe for a release archive name."
}

$ArchiveName = "WFMHub-2-v$Version-windows-x64-portable.zip"
$DistDirectory = Join-Path $Root "dist"
$ArchivePath = Join-Path $DistDirectory $ArchiveName
$ArchiveChecksumPath = "$ArchivePath.sha256"
$EvidencePath = Join-Path $Root "qualification-evidence/portable-archive.json"
$TopLevelDirectory = "WFMHub-2"

$RequiredFiles = [ordered]@{
  "WFMHub.exe" = Join-Path $Root "src-tauri/target/release/wfmhub-2.exe"
  "wfmhub-engine.exe" = Join-Path $Root "src-tauri/target/release/wfmhub-engine.exe"
  "duckdb_extensions/ducklake.duckdb_extension" = Join-Path $Root "packaging/duckdb_extensions/ducklake.duckdb_extension"
}

foreach ($RequiredFile in $RequiredFiles.GetEnumerator()) {
  if (-not (Test-Path -LiteralPath $RequiredFile.Value -PathType Leaf)) {
    throw "Portable archive input is missing: $($RequiredFile.Value)"
  }
  if ((Get-Item -LiteralPath $RequiredFile.Value).Length -eq 0) {
    throw "Portable archive input is empty: $($RequiredFile.Value)"
  }
}

$StagingDirectory = Join-Path ([System.IO.Path]::GetTempPath()) "wfmhub2-package-$([guid]::NewGuid().ToString('N'))"
$VerificationDirectory = Join-Path ([System.IO.Path]::GetTempPath()) "wfmhub2-verify-$([guid]::NewGuid().ToString('N'))"
$StagingRoot = Join-Path $StagingDirectory $TopLevelDirectory

try {
  New-Item -ItemType Directory -Force -Path $StagingRoot | Out-Null
  foreach ($RequiredFile in $RequiredFiles.GetEnumerator()) {
    $Destination = Join-Path $StagingRoot $RequiredFile.Key
    New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) | Out-Null
    Copy-Item -LiteralPath $RequiredFile.Value -Destination $Destination
  }

  $ReadmeLines = @(
    "WFMHub 2 portable Windows x64 preview",
    "",
    "1. Extract the complete ZIP to a normal local writable folder.",
    "2. Keep every file inside the WFMHub-2 folder together.",
    "3. Double-click WFMHub.exe.",
    "",
    "Do not run the app inside the ZIP and do not use GitHub's Source code ZIP.",
    "WFMHub creates Feed, Reports, and data beside the application.",
    "No installed Python, Node.js, Rust, database server, administrator rights, or runtime internet access is required.",
    "A supported Microsoft Edge WebView2 runtime is required.",
    "This Phase 0 preview qualifies the desktop stack; WFM features are still being implemented."
  )
  $Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
  [System.IO.File]::WriteAllText(
    (Join-Path $StagingRoot "README-FIRST.txt"),
    (($ReadmeLines -join "`r`n") + "`r`n"),
    $Utf8NoBom
  )

  $PayloadMembers = @($RequiredFiles.Keys) + @("README-FIRST.txt") | Sort-Object
  $ChecksumLines = foreach ($RelativePath in $PayloadMembers) {
    $PortablePath = $RelativePath.Replace('\', '/')
    $FilePath = Join-Path $StagingRoot $RelativePath
    $Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $FilePath).Hash.ToLowerInvariant()
    "$Hash  $PortablePath"
  }
  [System.IO.File]::WriteAllText(
    (Join-Path $StagingRoot "SHA256SUMS.txt"),
    (($ChecksumLines -join "`n") + "`n"),
    $Utf8NoBom
  )

  New-Item -ItemType Directory -Force -Path $DistDirectory | Out-Null
  if (Test-Path -LiteralPath $ArchivePath) {
    Remove-Item -LiteralPath $ArchivePath -Force
  }
  if (Test-Path -LiteralPath $ArchiveChecksumPath) {
    Remove-Item -LiteralPath $ArchiveChecksumPath -Force
  }

  Add-Type -AssemblyName System.IO.Compression
  $ArchiveStream = [System.IO.File]::Open(
    $ArchivePath,
    [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::None
  )
  try {
    $Archive = [System.IO.Compression.ZipArchive]::new(
      $ArchiveStream,
      [System.IO.Compression.ZipArchiveMode]::Create,
      $false
    )
    try {
      $FixedTimestamp = [DateTimeOffset]::new(1980, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
      $FilesToArchive = Get-ChildItem -LiteralPath $StagingRoot -File -Recurse |
        Sort-Object { [System.IO.Path]::GetRelativePath($StagingDirectory, $_.FullName) }
      foreach ($File in $FilesToArchive) {
        $EntryName = [System.IO.Path]::GetRelativePath($StagingDirectory, $File.FullName).Replace('\', '/')
        $Entry = $Archive.CreateEntry($EntryName, [System.IO.Compression.CompressionLevel]::Optimal)
        $Entry.LastWriteTime = $FixedTimestamp
        $Entry.ExternalAttributes = 0
        $InputStream = $File.OpenRead()
        $EntryStream = $Entry.Open()
        try {
          $InputStream.CopyTo($EntryStream)
        }
        finally {
          $EntryStream.Dispose()
          $InputStream.Dispose()
        }
      }
    }
    finally {
      $Archive.Dispose()
    }
  }
  finally {
    $ArchiveStream.Dispose()
  }

  New-Item -ItemType Directory -Force -Path $VerificationDirectory | Out-Null
  Expand-Archive -LiteralPath $ArchivePath -DestinationPath $VerificationDirectory
  $VerifiedRoot = Join-Path $VerificationDirectory $TopLevelDirectory
  $ExpectedMembers = @($PayloadMembers) + @("SHA256SUMS.txt") |
    ForEach-Object { "$TopLevelDirectory/$($_.Replace('\', '/'))" } |
    Sort-Object
  $ActualMembers = Get-ChildItem -LiteralPath $VerificationDirectory -File -Recurse |
    ForEach-Object { [System.IO.Path]::GetRelativePath($VerificationDirectory, $_.FullName).Replace('\', '/') } |
    Sort-Object
  $MemberDifference = Compare-Object -ReferenceObject $ExpectedMembers -DifferenceObject $ActualMembers
  if ($null -ne $MemberDifference) {
    throw "Portable archive members differ from the expected release layout: $($MemberDifference | Out-String)"
  }

  $ChecksumEntries = @(Get-Content -LiteralPath (Join-Path $VerifiedRoot "SHA256SUMS.txt"))
  if ($ChecksumEntries.Count -ne $PayloadMembers.Count) {
    throw "Portable archive checksum manifest has an unexpected entry count."
  }
  $ManifestMembers = @()
  foreach ($ChecksumEntry in $ChecksumEntries) {
    if ($ChecksumEntry -notmatch '^([0-9a-f]{64})  (.+)$') {
      throw "Portable archive checksum manifest contains an invalid line: $ChecksumEntry"
    }
    $ExpectedHash = $Matches[1]
    $RelativePath = $Matches[2]
    if ($RelativePath -notin $PayloadMembers) {
      throw "Portable archive checksum manifest contains an unexpected member: $RelativePath"
    }
    $ManifestMembers += $RelativePath
    $ActualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $VerifiedRoot $RelativePath)).Hash.ToLowerInvariant()
    if ($ActualHash -ne $ExpectedHash) {
      throw "Portable archive hash mismatch for $RelativePath"
    }
  }
  $ManifestDifference = Compare-Object `
    -ReferenceObject @($PayloadMembers | Sort-Object) `
    -DifferenceObject @($ManifestMembers | Sort-Object)
  if ($null -ne $ManifestDifference) {
    throw "Portable archive checksum manifest does not cover each payload exactly once."
  }

  $MemberEvidence = foreach ($Member in $ActualMembers) {
    $MemberPath = Join-Path $VerificationDirectory $Member
    [ordered]@{
      path = $Member
      bytes = (Get-Item -LiteralPath $MemberPath).Length
      sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $MemberPath).Hash.ToLowerInvariant()
    }
  }
  $Evidence = [ordered]@{
    schema_version = 1
    version = $Version
    target_triple = $TargetTriple
    archive = $ArchiveName
    archive_bytes = (Get-Item -LiteralPath $ArchivePath).Length
    archive_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArchivePath).Hash.ToLowerInvariant()
    members = @($MemberEvidence)
    expanded_and_verified = $true
  }
  [System.IO.File]::WriteAllText(
    $ArchiveChecksumPath,
    ("$($Evidence.archive_sha256)  $ArchiveName`n"),
    $Utf8NoBom
  )
  New-Item -ItemType Directory -Force -Path (Split-Path $EvidencePath -Parent) | Out-Null
  [System.IO.File]::WriteAllText(
    $EvidencePath,
    (($Evidence | ConvertTo-Json -Depth 5) + "`n"),
    $Utf8NoBom
  )

  Write-Host "Portable archive: $ArchivePath"
  Write-Host "Archive checksum: $ArchiveChecksumPath"
  Write-Host "Archive SHA-256: $($Evidence.archive_sha256)"
  Write-Host "Archive members expanded and verified: $($ActualMembers.Count)"
}
finally {
  if (Test-Path -LiteralPath $StagingDirectory) {
    Remove-Item -LiteralPath $StagingDirectory -Recurse -Force
  }
  if (Test-Path -LiteralPath $VerificationDirectory) {
    Remove-Item -LiteralPath $VerificationDirectory -Recurse -Force
  }
}
