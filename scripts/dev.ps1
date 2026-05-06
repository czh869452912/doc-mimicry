param(
    [ValidateSet("mock", "openhands")]
    [string]$Runtime = $env:DOCAGENT_RUNTIME,
    [string]$OpenHandsBaseUrl = $env:OPENHANDS_BASE_URL,
    [int]$OpenHandsPort = 8001,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$webRoot = Join-Path $repoRoot "apps\web"
$logRoot = Join-Path $repoRoot ".local\dev"
$venvRoot = Join-Path $logRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$apiLog = Join-Path $logRoot "api.log"
$openHandsLog = Join-Path $logRoot "openhands.log"
$setupLog = Join-Path $logRoot "setup.log"
$webLog = Join-Path $logRoot "web.log"

function Test-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-PythonVersion {
    param([Parameter(Mandatory = $true)][string]$Python)
    try {
        $version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        return [version]$version -ge [version]"3.11"
    }
    catch {
        return $false
    }
}

function Get-PythonCommand {
    $bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    $candidates = @($bundledPython, "python")
    foreach ($candidate in $candidates) {
        if ((Test-Path $candidate) -or (Test-Command $candidate)) {
            if (Test-PythonVersion $candidate) {
                return $candidate
            }
        }
    }
    throw "Python 3.11+ is required. Install Python 3.11+ or run inside the Codex workspace runtime."
}

function Stop-DevJobs {
    Get-Job -Name "docagent-api", "docagent-web", "docagent-openhands" -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Job $_ -ErrorAction SilentlyContinue
        Remove-Job $_ -Force -ErrorAction SilentlyContinue
    }
}

function Import-LocalEnv {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path $Path)) {
        return
    }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line.Length -eq 0 -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $parts = $line.Split("=", 2)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($name -and [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name, "Process"))) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Test-HttpReady {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 30
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
            return $true
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
Import-LocalEnv (Join-Path $repoRoot ".env.local")

if (-not (Test-Command "npm")) {
    throw "npm is required. Install Node.js 22+ before starting the dev stack."
}

$python = Get-PythonCommand
if ([string]::IsNullOrWhiteSpace($Runtime)) {
    $Runtime = "mock"
}

if ($Runtime -eq "openhands") {
    if ([string]::IsNullOrWhiteSpace($OpenHandsBaseUrl)) {
        $OpenHandsBaseUrl = "http://127.0.0.1:$OpenHandsPort"
    }
    foreach ($requiredName in @("LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL")) {
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($requiredName, "Process"))) {
            Write-Error "OpenHands runtime requires $requiredName. Set it in the environment or .env.local."
            exit 1
        }
    }
}

Push-Location $repoRoot
try {
    if (-not (Test-Path $venvPython)) {
        & $python -m venv $venvRoot
    }
    & $venvPython -m pip install --upgrade fastapi uvicorn httpx | Tee-Object -FilePath $setupLog
}
finally {
    Pop-Location
}

if (-not (Test-Path (Join-Path $webRoot "node_modules"))) {
    Push-Location $webRoot
    try {
        npm ci | Tee-Object -FilePath $webLog
    }
    finally {
        Pop-Location
    }
}

Stop-DevJobs

$openHandsJob = $null
if ($Runtime -eq "openhands") {
    try {
        Invoke-WebRequest -Uri "$OpenHandsBaseUrl/docs" -UseBasicParsing -TimeoutSec 2 | Out-Null
        Write-Host "OpenHands Agent Server already running at $OpenHandsBaseUrl"
    }
    catch {
        $openHandsJob = Start-Job -Name "docagent-openhands" -ScriptBlock {
            param($repoRoot, $openHandsLog, $venvPython, $openHandsPort)
            Set-Location $repoRoot
            $env:OPENHANDS_SUPPRESS_BANNER = "1"
            & $venvPython -m openhands.agent_server --port $openHandsPort *>> $openHandsLog
        } -ArgumentList $repoRoot, $openHandsLog, $venvPython, $OpenHandsPort
        if (-not (Test-HttpReady "$OpenHandsBaseUrl/docs" 45)) {
            Receive-Job $openHandsJob -Keep | Write-Host
            throw "OpenHands Agent Server did not become ready at $OpenHandsBaseUrl. Check $openHandsLog."
        }
    }
}

$pythonPath = @(
    Join-Path $repoRoot "packages\contracts"
    Join-Path $repoRoot "packages\workspace"
    Join-Path $repoRoot "packages\timeline"
    Join-Path $repoRoot "tools\import"
    Join-Path $repoRoot "services\api"
    Join-Path $repoRoot "agent\runtime-adapters\mock"
    Join-Path $repoRoot "agent\runtime-adapters\openhands"
) -join [IO.Path]::PathSeparator

$apiJob = Start-Job -Name "docagent-api" -ScriptBlock {
    param($repoRoot, $pythonPath, $apiLog, $venvPython, $runtime, $openHandsBaseUrl)
    Set-Location $repoRoot
    $env:PYTHONPATH = $pythonPath
    $env:DOCAGENT_RUNTIME = $runtime
    if (-not [string]::IsNullOrWhiteSpace($openHandsBaseUrl)) {
        $env:OPENHANDS_BASE_URL = $openHandsBaseUrl
    }
    & $venvPython -m uvicorn docagent_api.app:app --host 127.0.0.1 --port 8000 *>> $apiLog
} -ArgumentList $repoRoot, $pythonPath, $apiLog, $venvPython, $Runtime, $OpenHandsBaseUrl

$webJob = Start-Job -Name "docagent-web" -ScriptBlock {
    param($webRoot, $webLog)
    Set-Location $webRoot
    $env:VITE_API_BASE = "http://127.0.0.1:8000"
    npm run dev -- --host 127.0.0.1 --port 5173 *>> $webLog
} -ArgumentList $webRoot, $webLog

Write-Host "DocAgent dev stack starting..."
Write-Host "Runtime: $Runtime"
if ($Runtime -eq "openhands") {
    Write-Host "OpenHands: $OpenHandsBaseUrl"
}
Write-Host "API: http://127.0.0.1:8000"
Write-Host "Web: http://127.0.0.1:5173"
Write-Host "Logs: $logRoot"
Write-Host "Press Ctrl+C to stop."

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:5173"
}

try {
    while ($true) {
        Start-Sleep -Seconds 2
        foreach ($job in @($openHandsJob, $apiJob, $webJob)) {
            if ($null -eq $job) {
                continue
            }
            if ($job.State -in @("Failed", "Stopped", "Completed")) {
                Receive-Job $job -Keep | Write-Host
                throw "Dev job '$($job.Name)' exited with state $($job.State). Check logs in $logRoot."
            }
        }
    }
}
finally {
    Stop-DevJobs
}
