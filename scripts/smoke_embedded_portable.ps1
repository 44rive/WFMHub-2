[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$PortableRoot,
  [int]$TimeoutSeconds = 120,
  [string]$EvidencePath = "",
  [switch]$BlockOutbound
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PortableRoot = (Resolve-Path -LiteralPath $PortableRoot).Path
$PythonPath = Join-Path $PortableRoot "_system/runtime/python.exe"
$ExtensionPath = Join-Path $PortableRoot "_system/duckdb_extensions/ducklake.duckdb_extension"
$WebRoot = Join-Path $PortableRoot "_system/web"

foreach ($RequiredFile in @($PythonPath, $ExtensionPath, (Join-Path $WebRoot "index.html"))) {
  if (-not (Test-Path -LiteralPath $RequiredFile -PathType Leaf)) {
    throw "Embedded portable smoke input is missing: $RequiredFile"
  }
}
foreach ($ForbiddenFile in @("WFMHub.exe", "wfmhub-engine.exe")) {
  if (Test-Path -LiteralPath (Join-Path $PortableRoot $ForbiddenFile)) {
    throw "Legacy custom executable is forbidden in the embedded release: $ForbiddenFile"
  }
}

function Get-DescendantProcessIds {
  param([int]$ParentProcessId)

  $Children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentProcessId" |
    Select-Object -ExpandProperty ProcessId
  foreach ($ChildProcessId in $Children) {
    [int]$ChildProcessId
    Get-DescendantProcessIds -ParentProcessId $ChildProcessId
  }
}

$TokenBytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Fill($TokenBytes)
$SessionToken = [Convert]::ToHexString($TokenBytes).ToLowerInvariant()
$RuleName = "WFMHub2-Embedded-$([guid]::NewGuid().ToString('N'))"
$FirewallInstalled = $false
$Process = $null
$DescendantIds = @()
$OutputLog = Join-Path $PortableRoot "embedded-smoke.stdout.log"
$ErrorLog = Join-Path $PortableRoot "embedded-smoke.stderr.log"
$StartedAt = [DateTimeOffset]::UtcNow
$PriorSessionToken = $env:WFMHUB2_SESSION_TOKEN
$PriorPythonHome = $env:PYTHONHOME
$PriorPythonPath = $env:PYTHONPATH

try {
  if ($BlockOutbound) {
    New-NetFirewallRule `
      -DisplayName $RuleName `
      -Direction Outbound `
      -Program $PythonPath `
      -Action Block | Out-Null
    $FirewallInstalled = $true
  }

  $env:WFMHUB2_SESSION_TOKEN = $SessionToken
  $env:PYTHONHOME = ""
  $env:PYTHONPATH = ""

  $DoctorOutput = @(
    & $PythonPath -I -m wfmhub2.portable_doctor `
      --home $PortableRoot `
      --ducklake-extension $ExtensionPath `
      --full --require-offline --json
  )
  if ($LASTEXITCODE -ne 0) {
    throw "The exact embedded Python failed its full offline doctor: $($DoctorOutput -join [Environment]::NewLine)"
  }
  $Doctor = $DoctorOutput[-1] | ConvertFrom-Json
  if ($Doctor.status -ne "ok") {
    throw "The exact embedded Python doctor returned an unexpected status."
  }
  $RuntimeIsolation = @($Doctor.checks | Where-Object { $_.name -eq "runtime_isolation" })
  if ($RuntimeIsolation.Count -ne 1 -or $RuntimeIsolation[0].status -ne "pass") {
    throw "The embedded runtime-isolation probe did not pass exactly once."
  }
  $AllowedPythonPaths = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
  )
  foreach ($AllowedPath in @(
    (Join-Path $PortableRoot "_system/runtime/python314.zip"),
    (Join-Path $PortableRoot "_system/runtime"),
    (Join-Path $PortableRoot "_system/site-packages"),
    (Join-Path $PortableRoot "_system/app")
  )) {
    [void]$AllowedPythonPaths.Add([System.IO.Path]::GetFullPath($AllowedPath))
  }
  foreach ($ObservedPath in @($RuntimeIsolation[0].details.path)) {
    $NormalizedPath = [System.IO.Path]::GetFullPath([string]$ObservedPath)
    if (-not $AllowedPythonPaths.Contains($NormalizedPath)) {
      throw "Embedded Python sys.path escaped the portable payload: $NormalizedPath"
    }
  }

  $Arguments = @(
    "-I",
    "-m", "wfmhub2",
    "--home", ('"' + $PortableRoot + '"'),
    "--ducklake-extension", ('"' + $ExtensionPath + '"'),
    "portable",
    "--no-browser"
  )
  $Process = Start-Process `
    -FilePath $PythonPath `
    -ArgumentList $Arguments `
    -WorkingDirectory $PortableRoot `
    -RedirectStandardOutput $OutputLog `
    -RedirectStandardError $ErrorLog `
    -PassThru

  $Deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
  $Port = $null
  do {
    $Process.Refresh()
    if ($Process.HasExited) {
      $StandardOutput = if (Test-Path -LiteralPath $OutputLog) { Get-Content -LiteralPath $OutputLog -Raw } else { "" }
      $StandardError = if (Test-Path -LiteralPath $ErrorLog) { Get-Content -LiteralPath $ErrorLog -Raw } else { "" }
      throw "Embedded Python exited before readiness ($($Process.ExitCode)). stdout=$StandardOutput stderr=$StandardError"
    }
    if (Test-Path -LiteralPath $OutputLog) {
      foreach ($Line in Get-Content -LiteralPath $OutputLog) {
        if ($Line -match '^WFMHUB2_READY \{"port":([0-9]+)\}$') {
          $Port = [int]$Matches[1]
          break
        }
      }
    }
    if ($null -eq $Port) {
      Start-Sleep -Milliseconds 100
    }
  } while ($null -eq $Port -and [DateTimeOffset]::UtcNow -lt $Deadline)
  if ($null -eq $Port) {
    throw "Embedded Python did not emit readiness within $TimeoutSeconds seconds."
  }

  $BaseUrl = "http://127.0.0.1:$Port"
  $Headers = @{ "X-WFMHub-Token" = $SessionToken }
  $Health = Invoke-RestMethod -Uri "$BaseUrl/api/health" -TimeoutSec 15
  if ($Health.status -ne "ok") {
    throw "Embedded health endpoint returned an unexpected status."
  }
  $Unauthorized = Invoke-WebRequest `
    -Uri "$BaseUrl/api/stack/probe" `
    -SkipHttpErrorCheck `
    -TimeoutSec 15
  if ($Unauthorized.StatusCode -ne 401) {
    throw "Protected API accepted an unauthenticated request."
  }
  $Stack = Invoke-RestMethod -Uri "$BaseUrl/api/stack/probe" -Headers $Headers -TimeoutSec 120
  if ($Stack.status -ne "ok") {
    throw "Embedded authenticated storage probe failed."
  }
  $Refresh = Invoke-RestMethod -Uri "$BaseUrl/api/refresh/plan" -Headers $Headers -TimeoutSec 30
  if ($Refresh.status -ne "planned") {
    throw "Embedded refresh-plan endpoint returned an unexpected status."
  }
  $Index = Invoke-WebRequest -Uri "$BaseUrl/" -TimeoutSec 30
  if ($Index.StatusCode -ne 200 -or $Index.Content -notmatch '<div id="root"') {
    throw "Embedded server did not serve the compiled React entrypoint."
  }

  $DescendantIds = @(Get-DescendantProcessIds -ParentProcessId $Process.Id)
  $Evidence = [ordered]@{
    architecture = "official-embedded-cpython-local-browser"
    blocked_outbound = [bool]$BlockOutbound
    ducklake_catalog_exists = Test-Path -LiteralPath (Join-Path $PortableRoot "data/lake/catalog.ducklake")
    health = $Health.status
    legacy_custom_executables_absent = $true
    full_doctor = $Doctor.status
    parquet_file_count = @(Get-ChildItem -LiteralPath (Join-Path $PortableRoot "data/lake/files") -Filter "*.parquet" -File -Recurse).Count
    python_path = $PythonPath
    react_entrypoint_served = $true
    ready_milliseconds = [math]::Round(([DateTimeOffset]::UtcNow - $StartedAt).TotalMilliseconds)
    refresh_plan = $Refresh.status
    stack_probe = $Stack.status
    unauthenticated_probe_status = $Unauthorized.StatusCode
  }

  Stop-Process -Id $Process.Id
  $Process.WaitForExit()
  $ShutdownDeadline = [DateTimeOffset]::UtcNow.AddSeconds(15)
  do {
    $Survivors = @(
      $DescendantIds |
        Where-Object { $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue) }
    )
    if ($Survivors.Count -gt 0) {
      Start-Sleep -Milliseconds 100
    }
  } while ($Survivors.Count -gt 0 -and [DateTimeOffset]::UtcNow -lt $ShutdownDeadline)
  if ($Survivors.Count -gt 0) {
    throw "Embedded portable runtime left child processes after shutdown: $Survivors"
  }
  $Evidence["shutdown_clean"] = $true

  $Serialized = $Evidence | ConvertTo-Json -Depth 4
  Write-Host $Serialized
  if (-not [string]::IsNullOrWhiteSpace($EvidencePath)) {
    $EvidenceDirectory = Split-Path $EvidencePath -Parent
    if (-not [string]::IsNullOrWhiteSpace($EvidenceDirectory)) {
      New-Item -ItemType Directory -Force -Path $EvidenceDirectory | Out-Null
    }
    $Serialized | Set-Content -LiteralPath $EvidencePath -Encoding utf8
  }
}
finally {
  $env:WFMHUB2_SESSION_TOKEN = $PriorSessionToken
  $env:PYTHONHOME = $PriorPythonHome
  $env:PYTHONPATH = $PriorPythonPath
  if ($null -ne $Process) {
    $Process.Refresh()
    if (-not $Process.HasExited) {
      Stop-Process -Id $Process.Id -Force
      $Process.WaitForExit()
    }
  }
  foreach ($DescendantId in $DescendantIds) {
    if ($null -ne (Get-Process -Id $DescendantId -ErrorAction SilentlyContinue)) {
      Stop-Process -Id $DescendantId -Force
    }
  }
  if ($FirewallInstalled) {
    Remove-NetFirewallRule -DisplayName $RuleName | Out-Null
  }
}
