# Build sandbox indexes from sample_candidates.json (same pipeline as full 100K build).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".tools\python-embed\python.exe"
if (-not (Test-Path -LiteralPath $Py)) {
    $Py = Join-Path $Root ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $Py)) {
    & (Join-Path $Root "scripts\setup_env.ps1")
    $Py = Join-Path $Root ".tools\python-embed\python.exe"
}

$Sample = Join-Path $Root "India_runs_data_and_ai_challenge\sample_candidates.json"
$Out = Join-Path $Root "indices_sample"

if (-not (Test-Path -LiteralPath $Sample)) {
    throw "Missing sample file: $Sample"
}

Write-Host "Building sandbox indexes from sample_candidates.json -> indices_sample/"
& $Py (Join-Path $Root "scripts\build_index.py") --candidates $Sample --out $Out
Write-Host "Done. Streamlit sandbox will use the same hybrid ranker as rank.py."
