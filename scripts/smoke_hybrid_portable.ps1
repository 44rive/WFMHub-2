[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$PortableRoot,
  [string]$EvidencePath = "qualification-evidence/hybrid-browser-report.json",
  [int]$TimeoutSeconds = 480
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$PortableRoot = (Resolve-Path -LiteralPath $PortableRoot).Path
$Python = Join-Path $PortableRoot "_system/runtime/python.exe"
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
  throw "Embedded Python is missing: $Python"
}

$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("wfmhub2-hybrid-" + [Guid]::NewGuid())
New-Item -ItemType Directory -Path $TempRoot | Out-Null
$Stdout = Join-Path $TempRoot "host.stdout.log"
$Stderr = Join-Path $TempRoot "host.stderr.log"
$EdgeProfile = Join-Path $TempRoot "edge-profile"
$HostProcess = $null
$BrowserProcess = $null
$PreviousToken = $env:WFMHUB2_COMPAT_SESSION_TOKEN

try {
  $Token = "ci-hybrid-smoke-token"
  $env:WFMHUB2_COMPAT_SESSION_TOKEN = $Token
  $HostProcess = Start-Process -FilePath $Python -ArgumentList @(
    "-I",
    "-m",
    "wfmhub2_compat",
    "--home",
    ('"' + $PortableRoot + '"'),
    "--no-browser"
  ) -PassThru -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr

  $Deadline = (Get-Date).AddSeconds(60)
  $Port = $null
  while ((Get-Date) -lt $Deadline -and -not $HostProcess.HasExited) {
    Start-Sleep -Milliseconds 250
    if (Test-Path -LiteralPath $Stdout) {
      $Ready = Get-Content -LiteralPath $Stdout -Raw
      if ($Ready -match 'WFMHUB2_COMPAT_READY \{"port":(?<port>\d+)\}') {
        $Port = [int]$Matches.port
        break
      }
    }
  }
  if ($null -eq $Port) {
    $HostError = if (Test-Path $Stderr) { Get-Content $Stderr -Raw } else { "" }
    throw "Hybrid host did not become ready. $HostError"
  }

  $Listener = [System.Net.Sockets.TcpListener]::new(
    [System.Net.IPAddress]::Loopback,
    0
  )
  $Listener.Start()
  $DebugPort = ([System.Net.IPEndPoint]$Listener.LocalEndpoint).Port
  $Listener.Stop()

  $EdgeCandidates = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
  )
  $Edge = $EdgeCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    Select-Object -First 1
  if (-not $Edge) {
    throw "Microsoft Edge was not found on the Windows runner."
  }

  New-Item -ItemType Directory -Path $EdgeProfile | Out-Null
  $Url = "http://127.0.0.1:$Port/#wfmhub_token=$Token"
  $BrowserProcess = Start-Process -FilePath $Edge -ArgumentList @(
    "--headless=new",
    "--disable-gpu",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-default-apps",
    "--disable-domain-reliability",
    "--disable-sync",
    "--metrics-recording-only",
    "--no-first-run",
    "--host-resolver-rules=`"MAP * 0.0.0.0, EXCLUDE 127.0.0.1`"",
    "--remote-debugging-address=127.0.0.1",
    "--remote-debugging-port=$DebugPort",
    "--user-data-dir=`"$EdgeProfile`"",
    $Url
  ) -PassThru

  $Deadline = (Get-Date).AddSeconds(30)
  while ((Get-Date) -lt $Deadline) {
    try {
      $null = Invoke-RestMethod -Uri "http://127.0.0.1:$DebugPort/json/list" -TimeoutSec 2
      break
    }
    catch {
      Start-Sleep -Milliseconds 250
    }
  }

  node scripts/smoke_hybrid_browser.mjs $DebugPort ($TimeoutSeconds * 1000)
  if ($LASTEXITCODE -ne 0) {
    throw "Real-browser hybrid capability smoke failed."
  }

  $Report = Join-Path $PortableRoot "data/compatibility/last-browser-report.json"
  if (-not (Test-Path -LiteralPath $Report -PathType Leaf)) {
    throw "Browser smoke passed the page but no local report was saved."
  }
  $Parsed = Get-Content -LiteralPath $Report -Raw | ConvertFrom-Json
  $ExpectedProbes = @(
    "duckdb_opfs",
    "highs_mip",
    "host_sqlite",
    "pyodide_forecasting",
    "wasm_worker"
  )
  $ActualProbes = @($Parsed.probes | ForEach-Object { $_.name } | Sort-Object)
  $AllPassed = @($Parsed.probes | Where-Object { $_.status -ne "pass" }).Count -eq 0
  if (
    $Parsed.profile -ne "phase0.4-hybrid-compatibility-spike" -or
    $Parsed.overallStatus -ne "pass" -or
    @($Parsed.probes).Count -ne 5 -or
    -not $AllPassed -or
    ($ActualProbes -join ",") -ne ($ExpectedProbes -join ",")
  ) {
    throw "Saved browser report did not pass all five probes."
  }
  $EvidenceParent = Split-Path -Parent $EvidencePath
  if ($EvidenceParent) {
    New-Item -ItemType Directory -Force -Path $EvidenceParent | Out-Null
  }
  Copy-Item -LiteralPath $Report -Destination $EvidencePath -Force
}
finally {
  $env:WFMHUB2_COMPAT_SESSION_TOKEN = $PreviousToken
  foreach ($Process in @($BrowserProcess, $HostProcess)) {
    if ($null -ne $Process -and -not $Process.HasExited) {
      Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
      $Process.WaitForExit(10000)
    }
  }
  Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
