param(
    [ValidateSet("mock", "openhands")]
    [string]$Runtime = $env:DOCAGENT_RUNTIME,
    [string]$OpenHandsBaseUrl = $env:OPENHANDS_BASE_URL,
    [string]$OpenHandsContainerBaseUrl = $env:OPENHANDS_CONTAINER_BASE_URL,
    [int]$OpenHandsPort = 8001,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$logRoot = Join-Path $repoRoot ".local\dev"
$openHandsLog = Join-Path $logRoot "openhands.log"
$venvPython    = Join-Path $logRoot ".venv\Scripts\python.exe"
$openHandsReqs = Join-Path $PSScriptRoot "requirements-openhands.txt"

function Test-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
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
        [int]$TimeoutSeconds = 60
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

function Ensure-OpenHandsVenv {
    if (Test-Path $venvPython) { return }

    $venvDir = Join-Path $logRoot ".venv"
    $uv      = Get-Command uv     -ErrorAction SilentlyContinue
    $py      = Get-Command python -ErrorAction SilentlyContinue

    if ($null -eq $uv -and $null -eq $py) {
        throw (
            "Cannot auto-create the OpenHands venv at '$venvDir': " +
            "neither 'uv' nor 'python' was found on PATH. " +
            "Install uv (https://github.com/astral-sh/uv) or Python 3.11+, then retry."
        )
    }

    Write-Host "OpenHands venv not found — creating at $venvDir ..."
    if ($null -ne $uv) {
        Write-Host "  Using uv to create venv ..."
        & $uv.Source venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            throw "uv venv creation failed (exit $LASTEXITCODE). See output above."
        }
        Write-Host "  Installing from $openHandsReqs via uv pip ..."
        & $uv.Source pip install --python $venvPython -r $openHandsReqs
        if ($LASTEXITCODE -ne 0) {
            throw "uv pip install -r requirements-openhands.txt failed (exit $LASTEXITCODE). See output above."
        }
    } else {
        Write-Host "  uv not found — falling back to python -m venv ..."
        & $py.Source -m venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            throw "python -m venv creation failed (exit $LASTEXITCODE). See output above."
        }
        Write-Host "  Installing from $openHandsReqs via pip ..."
        & $venvPython -m pip install -r $openHandsReqs
        if ($LASTEXITCODE -ne 0) {
            throw "pip install -r requirements-openhands.txt failed (exit $LASTEXITCODE). See output above."
        }
    }
    Write-Host "OpenHands venv ready."
}

function Start-OpenHandsIfNeeded {
    if ($Runtime -ne "openhands") {
        return $null
    }
    if ([string]::IsNullOrWhiteSpace($OpenHandsBaseUrl)) {
        $script:OpenHandsBaseUrl = "http://127.0.0.1:$OpenHandsPort"
    }
    foreach ($requiredName in @("LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL")) {
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($requiredName, "Process"))) {
            Write-Error "OpenHands runtime requires $requiredName. Set it in the environment or .env.local."
            exit 1
        }
    }
    try {
        Invoke-WebRequest -Uri "$OpenHandsBaseUrl/docs" -UseBasicParsing -TimeoutSec 2 | Out-Null
        Write-Host "OpenHands Agent Server already running at $OpenHandsBaseUrl"
        return $null
    }
    catch {
        Ensure-OpenHandsVenv
        $job = Start-Job -Name "docagent-openhands" -ScriptBlock {
            param($repoRoot, $openHandsLog, $openHandsPort, $venvPython)
            Set-Location $repoRoot
            $env:OPENHANDS_SUPPRESS_BANNER = "1"
            & $venvPython -m openhands.agent_server --port $openHandsPort *>> $openHandsLog
        } -ArgumentList $repoRoot, $openHandsLog, $OpenHandsPort, $venvPython
        if (-not (Test-HttpReady "$OpenHandsBaseUrl/docs" 45)) {
            Receive-Job $job -Keep | Write-Host
            throw "OpenHands Agent Server did not become ready at $OpenHandsBaseUrl. Check $openHandsLog."
        }
        return $job
    }
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
Import-LocalEnv (Join-Path $repoRoot ".env.local")

if ([string]::IsNullOrWhiteSpace($Runtime)) {
    $Runtime = "mock"
}
if ($Runtime -eq "openhands" -and [string]::IsNullOrWhiteSpace($OpenHandsContainerBaseUrl)) {
    $OpenHandsContainerBaseUrl = "http://host.docker.internal:$OpenHandsPort"
}
if (-not (Test-Command "docker")) {
    throw "Docker is required for the local dev stack. Install Docker Desktop and start it before running start-dev.cmd."
}

$openHandsJob = $null
Push-Location $repoRoot
try {
    $openHandsJob = Start-OpenHandsIfNeeded

    $env:DOCAGENT_RUNTIME = $Runtime
    $env:DOCAGENT_QUEUE = "celery"
    $env:DOCAGENT_REPO_ROOT = "/app"
    if (-not [string]::IsNullOrWhiteSpace($OpenHandsBaseUrl)) {
        $env:OPENHANDS_BASE_URL = $OpenHandsBaseUrl
    }
    if (-not [string]::IsNullOrWhiteSpace($OpenHandsContainerBaseUrl)) {
        $env:OPENHANDS_CONTAINER_BASE_URL = $OpenHandsContainerBaseUrl
    }

    # BuildKit derives its gRPC session key from the working directory path.
    # Non-ASCII characters (e.g. the Chinese project directory) produce
    # non-printable bytes in that key, causing "non-printable ASCII characters"
    # errors. Disable BuildKit to use the legacy builder instead.
    $env:DOCKER_BUILDKIT = "0"

    # Docker's context walker on Windows calls Lstat on every directory entry
    # before checking .dockerignore; with non-ASCII paths this stat can fail
    # and abort the build. pytest.ini redirects the cache to .local/pytest-cache,
    # so .pytest_cache at the repo root is always stale and safe to remove.
    $stalePytestCache = Join-Path $repoRoot ".pytest_cache"
    if (Test-Path $stalePytestCache) {
        Remove-Item $stalePytestCache -Recurse -Force
    }

    docker compose up -d --build postgres redis api worker web

    if (-not (Test-HttpReady "http://127.0.0.1:8000/health" 90)) {
        docker compose logs api --tail 80
        throw "API did not become ready at http://127.0.0.1:8000. Check docker compose logs api."
    }
    if (-not (Test-HttpReady "http://127.0.0.1:5173" 90)) {
        docker compose logs web --tail 80
        throw "Web app did not become ready at http://127.0.0.1:5173. Check docker compose logs web."
    }

    Write-Host "DocAgent dev stack is running."
    Write-Host "Runtime: $Runtime"
    if ($Runtime -eq "openhands") {
        Write-Host "OpenHands: $OpenHandsBaseUrl"
    }
    Write-Host "API: http://127.0.0.1:8000"
    Write-Host "Web: http://127.0.0.1:5173"
    Write-Host "Logs: docker compose logs -f api worker web"
    Write-Host "Stop: docker compose down"

    if (-not $NoBrowser) {
        Start-Process "http://127.0.0.1:5173"
    }
}
finally {
    Pop-Location
    if ($null -ne $openHandsJob -and $openHandsJob.State -in @("Failed", "Stopped", "Completed")) {
        Remove-Job $openHandsJob -Force -ErrorAction SilentlyContinue
    }
}
