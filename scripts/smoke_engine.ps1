[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$EnginePath,
  [Parameter(Mandatory = $true)]
  [string]$ExtensionPath,
  [string]$HomePath = "",
  [int]$TimeoutSeconds = 45,
  [string]$EvidencePath = "",
  [switch]$BlockOutbound
)

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

$EnginePath = (Resolve-Path $EnginePath).Path
$ExtensionPath = (Resolve-Path $ExtensionPath).Path
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([string]::IsNullOrWhiteSpace($HomePath)) {
  $HomePath = Join-Path $Root "qualification-evidence/portable-home"
}
New-Item -ItemType Directory -Force -Path $HomePath | Out-Null

$RuleName = "WFMHub2-Phase0-$([guid]::NewGuid().ToString('N'))"
$FirewallInstalled = $false
$Engine = $null
$Owner = $null
$OutputLog = Join-Path $HomePath "engine.stdout.log"
$ErrorLog = Join-Path $HomePath "engine.stderr.log"
$StartedAt = [DateTimeOffset]::UtcNow
$TokenBytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Fill($TokenBytes)
$SessionToken = [Convert]::ToHexString($TokenBytes).ToLowerInvariant()
$PriorSessionToken = $env:WFMHUB2_SESSION_TOKEN
$PriorParentPid = $env:WFMHUB2_PARENT_PID

try {
  if ($BlockOutbound) {
    New-NetFirewallRule -DisplayName $RuleName -Direction Outbound -Program $EnginePath -Action Block | Out-Null
    $FirewallInstalled = $true
  }

  $PowerShellExecutable = (Get-Process -Id $PID).Path
  $Owner = Start-Process `
    -FilePath $PowerShellExecutable `
    -ArgumentList @("-NoProfile", "-NonInteractive", "-Command", "Start-Sleep -Seconds 120") `
    -WindowStyle Hidden `
    -PassThru
  $env:WFMHUB2_SESSION_TOKEN = $SessionToken
  $env:WFMHUB2_PARENT_PID = $Owner.Id.ToString()
  $Engine = Start-Process -FilePath $EnginePath -ArgumentList @(
    "--home", $HomePath,
    "--ducklake-extension", $ExtensionPath,
    "serve", "--host", "127.0.0.1", "--port", "0"
  ) -RedirectStandardOutput $OutputLog -RedirectStandardError $ErrorLog -PassThru
  $env:WFMHUB2_SESSION_TOKEN = $PriorSessionToken
  $env:WFMHUB2_PARENT_PID = $PriorParentPid

  $Deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
  $Ready = $null
  do {
    $Engine.Refresh()
    if ($Engine.HasExited) {
      $ErrorText = if (Test-Path $ErrorLog) { Get-Content $ErrorLog -Raw } else { "" }
      throw "Packaged engine exited before readiness (code $($Engine.ExitCode)). $ErrorText"
    }
    if (Test-Path $OutputLog) {
      $ReadyLine = Get-Content $OutputLog | Where-Object { $_ -match '^WFMHUB2_READY\s+\{' } | Select-Object -Last 1
      if ($ReadyLine -match '^WFMHUB2_READY\s+(\{.*\})$') {
        $Ready = $Matches[1] | ConvertFrom-Json
      }
    }
    if ($null -eq $Ready) {
      Start-Sleep -Milliseconds 250
    }
  } while ($null -eq $Ready -and [DateTimeOffset]::UtcNow -lt $Deadline)

  if ($null -eq $Ready -or $Ready.port -lt 1) {
    throw "Packaged engine did not emit a valid WFMHUB2_READY line within $TimeoutSeconds seconds"
  }

  $BaseUri = "http://127.0.0.1:$($Ready.port)"
  $Health = Invoke-RestMethod -Uri "$BaseUri/api/health" -TimeoutSec 5
  if ($Health.status -ne "ok") {
    throw "Packaged engine health probe did not return status=ok"
  }

  $UnauthenticatedStatus = 0
  try {
    Invoke-RestMethod -Uri "$BaseUri/api/stack/probe" -TimeoutSec 5 | Out-Null
  }
  catch {
    if ($null -ne $_.Exception.Response) {
      $UnauthenticatedStatus = [int]$_.Exception.Response.StatusCode
    }
  }
  if ($UnauthenticatedStatus -ne 401) {
    throw "Protected stack probe returned $UnauthenticatedStatus without authentication; expected 401"
  }

  $Probe = Invoke-RestMethod `
    -Uri "$BaseUri/api/stack/probe" `
    -Headers @{ "X-WFMHub-Token" = $SessionToken } `
    -TimeoutSec 30
  if ($Probe.status -ne "ok") {
    throw "Authenticated stack probe did not return status=ok"
  }

  $ReadyAt = [DateTimeOffset]::UtcNow
  $Engine.Refresh()
  $EngineTreeIds = @($Engine.Id) + @(Get-DescendantProcessIds -ParentProcessId $Engine.Id)
  $EngineTree = $EngineTreeIds |
    ForEach-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue }
  $Evidence = [ordered]@{
    engine_path = $EnginePath
    engine_bytes = (Get-Item $EnginePath).Length
    extension_sha256 = (Get-FileHash -Algorithm SHA256 -Path $ExtensionPath).Hash.ToLowerInvariant()
    home_path = (Resolve-Path $HomePath).Path
    control_database_exists = Test-Path (Join-Path $HomePath "data/control.sqlite")
    ducklake_catalog_exists = Test-Path (Join-Path $HomePath "data/lake/catalog.ducklake")
    dynamic_port = $Ready.port
    health_status = $Health.status
    unauthenticated_probe_status = $UnauthenticatedStatus
    authenticated_stack_probe = $Probe.status
    stack_probe = $Probe
    outbound_blocked = $FirewallInstalled
    cold_start_milliseconds = [math]::Round(($ReadyAt - $StartedAt).TotalMilliseconds)
    process_tree_ids = $EngineTreeIds
    working_set_bytes = ($EngineTree | Measure-Object -Property WorkingSet64 -Sum).Sum
    private_memory_bytes = ($EngineTree | Measure-Object -Property PrivateMemorySize64 -Sum).Sum
  }

  Stop-Process -Id $Owner.Id
  $Owner.WaitForExit()
  $WatchdogDeadline = [DateTimeOffset]::UtcNow.AddSeconds(10)
  do {
    $Engine.Refresh()
    if (-not $Engine.HasExited) {
      Start-Sleep -Milliseconds 100
    }
  } while (-not $Engine.HasExited -and [DateTimeOffset]::UtcNow -lt $WatchdogDeadline)
  if (-not $Engine.HasExited) {
    throw "Packaged engine did not exit after its declared owner stopped"
  }
  $SurvivingChildren = $EngineTreeIds |
    Where-Object { $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue) }
  if ($SurvivingChildren.Count -gt 0) {
    throw "Packaged engine left descendant processes after owner shutdown: $SurvivingChildren"
  }
  $Evidence["parent_watchdog_exit"] = $true

  $Serialized = $Evidence | ConvertTo-Json
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
  $env:WFMHUB2_SESSION_TOKEN = $PriorSessionToken
  $env:WFMHUB2_PARENT_PID = $PriorParentPid
  if ($null -ne $Owner -and -not $Owner.HasExited) {
    Stop-Process -Id $Owner.Id -Force
    $Owner.WaitForExit()
  }
  $EngineStillRunning = $false
  if ($null -ne $Engine -and -not $Engine.HasExited) {
    & taskkill.exe /PID $Engine.Id /T /F | Out-Null
    $Engine.WaitForExit()
  }
  if ($null -ne $Engine) {
    $Engine.Refresh()
    $EngineStillRunning = -not $Engine.HasExited
  }
  if ($FirewallInstalled) {
    Remove-NetFirewallRule -DisplayName $RuleName
  }
  if ($EngineStillRunning) {
    throw "Packaged engine remained alive after termination"
  }
}
