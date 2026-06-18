param(
    [string]$SpaceUser = "Sarthak080907",
    [string]$SpaceName = "proofrank",
    [string]$StagingDir = "",
    [string]$Token = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $StagingDir) {
    $StagingDir = Join-Path $env:TEMP ("proofrank-hf-space-" + [guid]::NewGuid().ToString("n").Substring(0, 8))
}

$SpaceUrl = "https://huggingface.co/spaces/$SpaceUser/$SpaceName"
if ($Token) {
    $GitUrl = "https://${SpaceUser}:$Token@huggingface.co/spaces/$SpaceUser/$SpaceName"
} else {
    $GitUrl = "https://huggingface.co/spaces/$SpaceUser/$SpaceName"
}

Write-Host "Packaging ProofRank HF Space -> $StagingDir"

if (Test-Path -LiteralPath $StagingDir) {
    Remove-Item -LiteralPath $StagingDir -Recurse -Force
}
New-Item -ItemType Directory -Path $StagingDir | Out-Null

$CopyItems = @(
    "app.py",
    "rank.py",
    "requirements.txt",
    "Dockerfile",
    "README_HF.md",
    "config",
    "src",
    "indices_sample",
    "India_runs_data_and_ai_challenge"
)

foreach ($item in $CopyItems) {
    $src = Join-Path $Root $item
    if (-not (Test-Path -LiteralPath $src)) {
        throw "Missing deploy artifact: $item (run scripts/build_sandbox_index.ps1 first)"
    }
    Copy-Item -LiteralPath $src -Destination (Join-Path $StagingDir $item) -Recurse -Force
}

# Drop bytecode — not needed on HF and can confuse reviewers
Get-ChildItem -LiteralPath $StagingDir -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# HF Space README must be README.md with YAML frontmatter
Copy-Item -LiteralPath (Join-Path $Root "README_HF.md") -Destination (Join-Path $StagingDir "README.md") -Force

# Trim challenge bundle to sample file only (keep validator out of Space)
$bundleDst = Join-Path $StagingDir "India_runs_data_and_ai_challenge"
Get-ChildItem -LiteralPath $bundleDst -File | Where-Object { $_.Name -ne "sample_candidates.json" } | Remove-Item -Force

$sampleIndex = Join-Path $Root "indices_sample\faiss_career.index"
if (-not (Test-Path -LiteralPath $sampleIndex)) {
    throw "indices_sample/ not built. Run: powershell -File scripts/build_sandbox_index.ps1"
}

Push-Location $StagingDir
try {
    git init
    git branch -M main
    git lfs install --local --force
    git lfs track "indices_sample/*.pkl"
    git lfs track "indices_sample/*.index"
    git lfs track "indices_sample/*.npy"
    git lfs track "indices_sample/*.parquet"

    git add .
    git commit -m "Deploy ProofRank sandbox with production-parity ranker"

    $remotes = git remote 2>$null
    if ($remotes -notcontains "space") {
        git remote add space $GitUrl
    } else {
        git remote set-url space $GitUrl
    }

    Write-Host ""
    Write-Host "Pushing to $SpaceUrl"
    Write-Host "You need HF git credentials (token with write access)."
    Write-Host "Create the Space first at https://huggingface.co/new-space if it does not exist."
    Write-Host ""
    git push --force space main
    Write-Host ""
    Write-Host "Done. Sandbox URL: $SpaceUrl"
}
finally {
    Pop-Location
}
