param(
    [string]$AcpUiDir = "",
    [switch]$Install
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $AcpUiDir) {
    $AcpUiDir = Join-Path $repoRoot ".local\reference\acp-ui"
}

$patchPath = Join-Path $PSScriptRoot "patches\docagent-query-bootstrap.patch"
$upstreamUrl = "https://github.com/formulahendry/acp-ui.git"

function Invoke-CheckedNative {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path $patchPath)) {
    throw "Patch file not found: $patchPath"
}

if (-not (Test-Path $AcpUiDir)) {
    $parent = Split-Path -Parent $AcpUiDir
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Invoke-CheckedNative git clone --depth 1 $upstreamUrl $AcpUiDir
}

if (-not (Test-Path (Join-Path $AcpUiDir ".git"))) {
    throw "ACP UI directory is not a git checkout: $AcpUiDir"
}

git -C $AcpUiDir apply --reverse --check --unidiff-zero $patchPath 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "DocAgent acp-ui bootstrap patch is already applied."
} else {
    Invoke-CheckedNative git -C $AcpUiDir apply --check --unidiff-zero $patchPath
    Invoke-CheckedNative git -C $AcpUiDir apply --unidiff-zero $patchPath
    Write-Host "Applied DocAgent acp-ui bootstrap patch."
}

if ($Install) {
    Push-Location $AcpUiDir
    try {
        npm install
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Start acp-ui with:"
Write-Host "  Push-Location `"$AcpUiDir`""
Write-Host "  npm run dev:web -- --host 127.0.0.1 --port 4173"
Write-Host "  Pop-Location"
Write-Host ""
Write-Host "Then start DocAgent web with:"
Write-Host "  `$env:VITE_ACP_UI_URL = `"http://127.0.0.1:4173/`""
