param(
    [ValidateSet("mock", "mock-acp", "openhands", "openhands-acp")]
    [string]$Runtime,
    [string]$AcpRuntimeUrl,
    [string]$AcpContainerRuntimeUrl,
    [int]$OpenHandsPort = 8001,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$logRoot = Join-Path $repoRoot ".local\dev"

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

function Start-OpenHandsIfNeeded {
    if ($Runtime -ne "openhands-acp") {
        return $null
    }
    if ([string]::IsNullOrWhiteSpace($AcpRuntimeUrl)) {
        $script:AcpRuntimeUrl = "http://127.0.0.1:$OpenHandsPort"
    }
    foreach ($requiredName in @("LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL")) {
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($requiredName, "Process"))) {
            Write-Error "OpenHands runtime requires $requiredName. Set it in the environment or .env.local."
            exit 1
        }
    }
    return $null
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
Import-LocalEnv (Join-Path $repoRoot ".env")
Import-LocalEnv (Join-Path $repoRoot ".env.local")

if ([string]::IsNullOrWhiteSpace($Runtime)) {
    $Runtime = $env:DOCAGENT_RUNTIME
}
if ([string]::IsNullOrWhiteSpace($AcpRuntimeUrl)) {
    $AcpRuntimeUrl = $env:DOCAGENT_ACP_RUNTIME_URL
    if ([string]::IsNullOrWhiteSpace($AcpRuntimeUrl)) {
        $AcpRuntimeUrl = $env:OPENHANDS_BASE_URL
    }
}
if ([string]::IsNullOrWhiteSpace($AcpContainerRuntimeUrl)) {
    $AcpContainerRuntimeUrl = $env:DOCAGENT_ACP_CONTAINER_RUNTIME_URL
}

if ([string]::IsNullOrWhiteSpace($Runtime)) {
    $Runtime = "mock-acp"
}
if ($Runtime -eq "mock") {
    $Runtime = "mock-acp"
}
if ($Runtime -eq "openhands") {
    $Runtime = "openhands-acp"
}
if ($Runtime -eq "openhands-acp" -and [string]::IsNullOrWhiteSpace($AcpContainerRuntimeUrl)) {
    $AcpContainerRuntimeUrl = "http://openhands:$OpenHandsPort"
}
if ($Runtime -ne "openhands-acp") {
    $AcpContainerRuntimeUrl = ""
}
if (-not (Test-Command "docker")) {
    throw "Docker is required for the local dev stack. Install Docker Desktop and start it before running start-dev.cmd."
}

Push-Location $repoRoot
try {
    Start-OpenHandsIfNeeded | Out-Null

    $env:DOCAGENT_RUNTIME = $Runtime
    $env:DOCAGENT_QUEUE = "celery"
    $env:DOCAGENT_REPO_ROOT = "/app"
    if ($Runtime -eq "openhands-acp" -and -not [string]::IsNullOrWhiteSpace($AcpRuntimeUrl)) {
        $env:DOCAGENT_ACP_RUNTIME_URL = $AcpRuntimeUrl
        $env:OPENHANDS_BASE_URL = $AcpRuntimeUrl
    } elseif ($Runtime -ne "openhands-acp") {
        [Environment]::SetEnvironmentVariable("DOCAGENT_ACP_RUNTIME_URL", $null, "Process")
        [Environment]::SetEnvironmentVariable("DOCAGENT_ACP_CONTAINER_RUNTIME_URL", $null, "Process")
        [Environment]::SetEnvironmentVariable("OPENHANDS_BASE_URL", $null, "Process")
    }
    if ($Runtime -eq "openhands-acp" -and -not [string]::IsNullOrWhiteSpace($AcpContainerRuntimeUrl)) {
        $env:DOCAGENT_ACP_CONTAINER_RUNTIME_URL = $AcpContainerRuntimeUrl
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

    if ($Runtime -eq "openhands-acp") {
        docker compose --profile openhands up -d --build postgres redis openhands api worker web
    } else {
        docker compose up -d --build postgres redis api worker web
    }

    if ($Runtime -eq "openhands-acp" -and -not (Test-HttpReady "$AcpRuntimeUrl/docs" 90)) {
        docker compose logs openhands --tail 80
        throw "OpenHands Agent Server did not become ready at $AcpRuntimeUrl. Check docker compose logs openhands."
    }
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
    if ($Runtime -eq "openhands-acp") {
        Write-Host "ACP runtime: $AcpRuntimeUrl"
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
}
