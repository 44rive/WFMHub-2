[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$DesktopPath,
  [int]$TimeoutSeconds = 60,
  [string]$EvidencePath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-DescendantProcessIds {
  param([int]$ParentProcessId)

  $Children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentProcessId" |
    Select-Object -ExpandProperty ProcessId
  foreach ($ChildProcessId in $Children) {
    [int]$ChildProcessId
    Get-DescendantProcessIds -ParentProcessId $ChildProcessId
  }
}

$DesktopPath = (Resolve-Path $DesktopPath).Path
$PortableRoot = Split-Path $DesktopPath -Parent
$Desktop = $null
$EngineProcessIds = @()
$StartedAt = [DateTimeOffset]::UtcNow

try {
  $Desktop = Start-Process `
    -FilePath $DesktopPath `
    -WorkingDirectory $PortableRoot `
    -PassThru

  $Deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
  $ControlDatabase = Join-Path $PortableRoot "data/control.sqlite"
  $DuckLakeCatalog = Join-Path $PortableRoot "data/lake/catalog.ducklake"
  $ParquetFiles = @()

  do {
    $Desktop.Refresh()
    if ($Desktop.HasExited) {
      throw "Packaged desktop exited before its engine and UI stack became ready (code $($Desktop.ExitCode))."
    }

    $DescendantIds = @(Get-DescendantProcessIds -ParentProcessId $Desktop.Id)
    $EngineProcessIds = @(
      foreach ($ProcessId in $DescendantIds) {
        $Process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId"
        if ($null -ne $Process -and $Process.Name -like "wfmhub-engine*.exe") {
          [int]$Process.ProcessId
        }
      }
    )
    $ParquetFiles = @(Get-ChildItem (Join-Path $PortableRoot "data/lake/files") -Filter *.parquet -File -Recurse -ErrorAction SilentlyContinue)
    $StorageActivity = (
      $EngineProcessIds.Count -gt 0 -and
      (Test-Path -LiteralPath $ControlDatabase -PathType Leaf) -and
      (Test-Path -LiteralPath $DuckLakeCatalog -PathType Leaf) -and
      $ParquetFiles.Count -gt 0
    )
    if (-not $StorageActivity) {
      Start-Sleep -Milliseconds 250
    }
  } while (-not $StorageActivity -and [DateTimeOffset]::UtcNow -lt $Deadline)

  if (-not $StorageActivity) {
    throw "Packaged desktop did not initiate its authenticated SQLite/DuckLake UI probe within $TimeoutSeconds seconds."
  }

  # Parquet creation occurs before the backend finishes its catalog reopen/read.
  # Keep the desktop alive through a stabilization window; the following direct
  # engine smoke is the authoritative HTTP-200 completion check.
  Start-Sleep -Seconds 3
  $Desktop.Refresh()
  if ($Desktop.HasExited) {
    throw "Packaged desktop exited while its storage probe was stabilizing."
  }
  $SurvivingProbeEngines = @(
    $EngineProcessIds |
      Where-Object { $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue) }
  )
  if ($SurvivingProbeEngines.Count -eq 0) {
    throw "Packaged desktop engine exited while its storage probe was stabilizing."
  }

  $StorageActivityAt = [DateTimeOffset]::UtcNow
  $Evidence = [ordered]@{
    desktop_path = $DesktopPath
    desktop_bytes = (Get-Item -LiteralPath $DesktopPath).Length
    portable_root = $PortableRoot
    desktop_process_id = $Desktop.Id
    engine_process_ids = @($EngineProcessIds)
    control_database_exists = $true
    ducklake_catalog_exists = $true
    parquet_file_count = $ParquetFiles.Count
    ui_started_authenticated_storage_probe = $true
    stabilization_seconds = 3
    desktop_to_stable_storage_activity_milliseconds = [math]::Round(($StorageActivityAt - $StartedAt).TotalMilliseconds)
  }

  Stop-Process -Id $Desktop.Id
  $Desktop.WaitForExit()
  $ShutdownDeadline = [DateTimeOffset]::UtcNow.AddSeconds(15)
  do {
    $SurvivingEngineIds = @(
      $EngineProcessIds |
        Where-Object { $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue) }
    )
    if ($SurvivingEngineIds.Count -gt 0) {
      Start-Sleep -Milliseconds 100
    }
  } while ($SurvivingEngineIds.Count -gt 0 -and [DateTimeOffset]::UtcNow -lt $ShutdownDeadline)
  if ($SurvivingEngineIds.Count -gt 0) {
    throw "Packaged desktop left engine processes after shutdown: $SurvivingEngineIds"
  }
  $Evidence["desktop_shutdown_clean"] = $true

  $Serialized = $Evidence | ConvertTo-Json -Depth 4
  Write-Host $Serialized
  if (-not [string]::IsNullOrWhiteSpace($EvidencePath)) {
    $EvidenceDirectory = Split-Path $EvidencePath -Parent
    if (-not [string]::IsNullOrWhiteSpace($EvidenceDirectory)) {
      New-Item -ItemType Directory -Force -Path $EvidenceDirectory | Out-Null
    }
    $Serialized | Set-Content -Path $EvidencePath -Encoding utf8
  }
}
finally {
  if ($null -ne $Desktop) {
    $Desktop.Refresh()
    if (-not $Desktop.HasExited) {
      & taskkill.exe /PID $Desktop.Id /T /F | Out-Null
      $Desktop.WaitForExit()
    }
  }
  foreach ($EngineProcessId in $EngineProcessIds) {
    if ($null -ne (Get-Process -Id $EngineProcessId -ErrorAction SilentlyContinue)) {
      & taskkill.exe /PID $EngineProcessId /T /F | Out-Null
    }
  }
}
