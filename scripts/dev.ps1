param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$webRoot = Join-Path $repoRoot "apps\web"
$logRoot = Join-Path $repoRoot ".local\dev"
$venvRoot = Join-Path $logRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$apiLog = Join-Path $logRoot "api.log"
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
    Get-Job -Name "docagent-api", "docagent-web" -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Job $_ -ErrorAction SilentlyContinue
        Remove-Job $_ -Force -ErrorAction SilentlyContinue
    }
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

if (-not (Test-Command "npm")) {
    throw "npm is required. Install Node.js 22+ before starting the dev stack."
}

$python = Get-PythonCommand

Push-Location $repoRoot
try {
    if (-not (Test-Path $venvPython)) {
        & $python -m venv $venvRoot
    }
    & $venvPython -m pip install --upgrade fastapi uvicorn httpx | Tee-Object -FilePath $apiLog
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

$pythonPath = @(
    Join-Path $repoRoot "packages\contracts"
    Join-Path $repoRoot "packages\workspace"
    Join-Path $repoRoot "packages\timeline"
    Join-Path $repoRoot "tools\import"
    Join-Path $repoRoot "services\api"
    Join-Path $repoRoot "agent\runtime-adapters\mock"
) -join [IO.Path]::PathSeparator

$apiJob = Start-Job -Name "docagent-api" -ScriptBlock {
    param($repoRoot, $pythonPath, $apiLog, $venvPython)
    Set-Location $repoRoot
    $env:PYTHONPATH = $pythonPath
    & $venvPython -m uvicorn docagent_api.app:app --reload --host 127.0.0.1 --port 8000 *>> $apiLog
} -ArgumentList $repoRoot, $pythonPath, $apiLog, $venvPython

$webJob = Start-Job -Name "docagent-web" -ScriptBlock {
    param($webRoot, $webLog)
    Set-Location $webRoot
    $env:VITE_API_BASE = "http://127.0.0.1:8000"
    npm run dev -- --host 127.0.0.1 --port 5173 *>> $webLog
} -ArgumentList $webRoot, $webLog

Write-Host "DocAgent dev stack starting..."
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
        foreach ($job in @($apiJob, $webJob)) {
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
