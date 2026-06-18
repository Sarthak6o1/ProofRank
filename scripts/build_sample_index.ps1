# Quick smoke test: index first 500 candidates from full jsonl
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

& $Py (Join-Path $Root "scripts\build_index.py") `
  --candidates (Join-Path $Root "India_runs_data_and_ai_challenge\candidates.jsonl") `
  --out (Join-Path $Root "indices_sample") `
  --limit 500
