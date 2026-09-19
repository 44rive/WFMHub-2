[CmdletBinding()]
param(
  [string]$DuckDBVersion = "1.5.5",
  [string]$Platform = "windows_amd64",
  [string]$OutputDirectory = "",
  [switch]$UseExisting
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
  $OutputDirectory = Join-Path $Root "packaging/duckdb_extensions"
}

$ArtifactKey = "$DuckDBVersion/$Platform"
$PinnedArtifacts = @{
  "1.5.5/windows_amd64" = @{
    ArchiveSha256 = "4a5180e1654cbbc3fd58afe8c70b3f98187d18e8d8e8c9bf386c3d48e9b8a116"
    ExtensionSha256 = "4546a5c6d9bc52cc122bc76e521c996e1ac31e71a25e01c531db8d3bb65e2ef0"
  }
}

if (-not $PinnedArtifacts.ContainsKey($ArtifactKey)) {
  throw "No reviewed DuckLake artifact is pinned for $ArtifactKey. Add verified hashes before changing the build target."
}

$Pinned = $PinnedArtifacts[$ArtifactKey]
$ExtensionPath = Join-Path $OutputDirectory "ducklake.duckdb_extension"
$ManifestPath = Join-Path $OutputDirectory "ducklake.manifest.json"
$Url = "https://extensions.duckdb.org/v$DuckDBVersion/$Platform/ducklake.duckdb_extension.gz"

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

if (-not $UseExisting) {
  $TemporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("wfmhub2-ducklake-" + [guid]::NewGuid().ToString("N"))
  $ArchivePath = Join-Path $TemporaryDirectory "ducklake.duckdb_extension.gz"
  $TemporaryExtension = Join-Path $TemporaryDirectory "ducklake.duckdb_extension"
  New-Item -ItemType Directory -Path $TemporaryDirectory | Out-Null

  try {
    Write-Host "Downloading pinned DuckLake $ArtifactKey"
    Invoke-WebRequest -Uri $Url -OutFile $ArchivePath

    $ArchiveHash = (Get-FileHash -Algorithm SHA256 -Path $ArchivePath).Hash.ToLowerInvariant()
    if ($ArchiveHash -ne $Pinned.ArchiveSha256) {
      throw "DuckLake archive hash mismatch. Expected $($Pinned.ArchiveSha256), received $ArchiveHash."
    }

    $InputStream = [System.IO.File]::OpenRead($ArchivePath)
    try {
      $GzipStream = [System.IO.Compression.GzipStream]::new(
        $InputStream,
        [System.IO.Compression.CompressionMode]::Decompress
      )
      try {
        $OutputStream = [System.IO.File]::Create($TemporaryExtension)
        try {
          $GzipStream.CopyTo($OutputStream)
        }
        finally {
          $OutputStream.Dispose()
        }
      }
      finally {
        $GzipStream.Dispose()
      }
    }
    finally {
      $InputStream.Dispose()
    }

    $ExtensionHash = (Get-FileHash -Algorithm SHA256 -Path $TemporaryExtension).Hash.ToLowerInvariant()
    if ($ExtensionHash -ne $Pinned.ExtensionSha256) {
      throw "DuckLake extension hash mismatch. Expected $($Pinned.ExtensionSha256), received $ExtensionHash."
    }

    Move-Item -Path $TemporaryExtension -Destination $ExtensionPath -Force
  }
  finally {
    if (Test-Path $TemporaryDirectory) {
      Remove-Item -Path $TemporaryDirectory -Recurse -Force
    }
  }
}

if (-not (Test-Path $ExtensionPath -PathType Leaf)) {
  throw "DuckLake extension is missing at $ExtensionPath. Run this script without -UseExisting on a networked build machine."
}

$InstalledHash = (Get-FileHash -Algorithm SHA256 -Path $ExtensionPath).Hash.ToLowerInvariant()
if ($InstalledHash -ne $Pinned.ExtensionSha256) {
  throw "Staged DuckLake extension is not the reviewed $ArtifactKey artifact. Expected $($Pinned.ExtensionSha256), received $InstalledHash."
}

$Manifest = [ordered]@{
  duckdb_version = $DuckDBVersion
  platform = $Platform
  source_url = $Url
  archive_sha256 = $Pinned.ArchiveSha256
  extension_sha256 = $Pinned.ExtensionSha256
  extension_bytes = (Get-Item $ExtensionPath).Length
}
$Manifest | ConvertTo-Json | Set-Content -Path $ManifestPath -Encoding utf8

Write-Host "Staged verified DuckLake extension: $ExtensionPath"
Write-Host "SHA-256: $InstalledHash"
