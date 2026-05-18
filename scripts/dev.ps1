param(
    [ValidateSet("mock", "mock-acp", "openhands", "openhands-acp")]
    [string]$Runtime,
    [string]$AcpRuntimeUrl,
    [string]$AcpContainerRuntimeUrl,
    [string]$AcpUiUrl,
    [int]$ApiPort = 18000,
    [int]$OpenHandsPort = 18001,
    [int]$AcpUiPort = 4173,
    [switch]$ExternalAcpUi,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$logRoot = Join-Path $repoRoot ".local\dev"
$openHandsContainerPort = 8001

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

function Assert-OpenHandsLlmModel {
    $model = [Environment]::GetEnvironmentVariable("LLM_MODEL", "Process")
    $baseUrl = [Environment]::GetEnvironmentVariable("LLM_BASE_URL", "Process")
    if (
        -not [string]::IsNullOrWhiteSpace($model) -and
        -not [string]::IsNullOrWhiteSpace($baseUrl) -and
        $baseUrl -notmatch "litellm:4000|127\.0\.0\.1:4000|localhost:4000" -and
        -not $model.Contains("/")
    ) {
        Write-Error (
            "OpenAI-compatible LLM_BASE_URL values require an LLM_MODEL with a LiteLLM provider prefix. " +
            "For example, use openai/kimi-k2-0905-preview instead of kimi-k2-0905-preview."
        )
        exit 1
    }
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
    Assert-OpenHandsLlmModel
    return $null
}

function Start-ExternalAcpUiIfNeeded {
    $effectiveAcpUiUrl = $AcpUiUrl
    if ([string]::IsNullOrWhiteSpace($effectiveAcpUiUrl)) {
        $effectiveAcpUiUrl = $env:VITE_ACP_UI_URL
    }
    if ($ExternalAcpUi -and [string]::IsNullOrWhiteSpace($effectiveAcpUiUrl)) {
        $effectiveAcpUiUrl = "http://127.0.0.1:$AcpUiPort/"
    }
    if ([string]::IsNullOrWhiteSpace($effectiveAcpUiUrl)) {
        $script:AcpUiUrl = ""
        [Environment]::SetEnvironmentVariable("VITE_ACP_UI_URL", $null, "Process")
        return
    }

    if (-not $effectiveAcpUiUrl.EndsWith("/")) {
        $effectiveAcpUiUrl = "$effectiveAcpUiUrl/"
    }
    $script:AcpUiUrl = $effectiveAcpUiUrl
    $env:VITE_ACP_UI_URL = $effectiveAcpUiUrl

    if (-not $ExternalAcpUi) {
        return
    }

    $acpUiDir = Join-Path $repoRoot ".local\reference\acp-ui"
    $prepareScript = Join-Path $repoRoot "tools\acp_ui\prepare_acp_ui.ps1"
    $prepareArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $prepareScript)
    if (-not (Test-Path (Join-Path $acpUiDir "node_modules"))) {
        $prepareArgs += "-Install"
    }
    & powershell.exe @prepareArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to prepare acp-ui. Check tools\acp_ui\prepare_acp_ui.ps1."
    }

    if (Test-HttpReady $effectiveAcpUiUrl 2) {
        return
    }

    $acpUiLog = Join-Path $logRoot "acp-ui.log"
    $cmdArgs = "/c npm run dev:web -- --host 127.0.0.1 --port $AcpUiPort > `"$acpUiLog`" 2>&1"
    Start-Process -FilePath "cmd.exe" -ArgumentList $cmdArgs -WorkingDirectory $acpUiDir -WindowStyle Hidden | Out-Null
    if (-not (Test-HttpReady $effectiveAcpUiUrl 45)) {
        throw "ACP UI did not become ready at $effectiveAcpUiUrl. Check $acpUiLog."
    }
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
Import-LocalEnv (Join-Path $repoRoot ".env")
Import-LocalEnv (Join-Path $repoRoot ".env.local")

$openHandsPortWasProvided = $PSBoundParameters.ContainsKey("OpenHandsPort")
$openHandsHostPortFromEnv = $false
$apiPortWasProvided = $PSBoundParameters.ContainsKey("ApiPort")
if (-not $apiPortWasProvided) {
    $envApiHostPort = $env:API_HOST_PORT
    if (-not [string]::IsNullOrWhiteSpace($envApiHostPort)) {
        $parsedApiHostPort = 0
        if (-not [int]::TryParse($envApiHostPort, [ref]$parsedApiHostPort)) {
            throw "API_HOST_PORT must be an integer TCP port."
        }
        if ($parsedApiHostPort -lt 1 -or $parsedApiHostPort -gt 65535) {
            throw "API_HOST_PORT must be between 1 and 65535."
        }
        $ApiPort = $parsedApiHostPort
    }
}
if (-not $openHandsPortWasProvided) {
    $envOpenHandsHostPort = $env:OPENHANDS_HOST_PORT
    if (-not [string]::IsNullOrWhiteSpace($envOpenHandsHostPort)) {
        $parsedOpenHandsHostPort = 0
        if (-not [int]::TryParse($envOpenHandsHostPort, [ref]$parsedOpenHandsHostPort)) {
            throw "OPENHANDS_HOST_PORT must be an integer TCP port."
        }
        if ($parsedOpenHandsHostPort -lt 1 -or $parsedOpenHandsHostPort -gt 65535) {
            throw "OPENHANDS_HOST_PORT must be between 1 and 65535."
        }
        $OpenHandsPort = $parsedOpenHandsHostPort
        $openHandsHostPortFromEnv = $true
    }
}

if ([string]::IsNullOrWhiteSpace($Runtime)) {
    $Runtime = $env:DOCAGENT_RUNTIME
}
if ([string]::IsNullOrWhiteSpace($AcpRuntimeUrl)) {
    if (-not $openHandsPortWasProvided -and -not $openHandsHostPortFromEnv) {
        $AcpRuntimeUrl = $env:DOCAGENT_ACP_RUNTIME_URL
        if ([string]::IsNullOrWhiteSpace($AcpRuntimeUrl)) {
            $AcpRuntimeUrl = $env:OPENHANDS_BASE_URL
        }
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
    $AcpContainerRuntimeUrl = "http://openhands:$openHandsContainerPort"
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
    Start-ExternalAcpUiIfNeeded

    $env:DOCAGENT_RUNTIME = $Runtime
    $env:DOCAGENT_QUEUE = "celery"
    $env:DOCAGENT_REPO_ROOT = "/app"
    $env:API_HOST_PORT = "$ApiPort"
    $env:OPENHANDS_HOST_PORT = "$OpenHandsPort"
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
    if (-not (Test-HttpReady "http://127.0.0.1:$ApiPort/health" 90)) {
        docker compose logs api --tail 80
        throw "API did not become ready at http://127.0.0.1:$ApiPort. Check docker compose logs api."
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
    if (-not [string]::IsNullOrWhiteSpace($AcpUiUrl)) {
        Write-Host "External ACP UI: $AcpUiUrl"
    }
    Write-Host "API: http://127.0.0.1:$ApiPort"
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
