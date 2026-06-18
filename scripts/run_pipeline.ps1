# Full ProofRank pipeline using embed Python (bracket-safe paths).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".tools\python-embed\python.exe"
$Candidates = Join-Path $Root "India_runs_data_and_ai_challenge\candidates.jsonl"
$Indices = Join-Path $Root "indices"
$Out = Join-Path $Root "submission.csv"
$Validator = Join-Path $Root "India_runs_data_and_ai_challenge\validate_submission.py"

if (-not (Test-Path -LiteralPath $Py)) {
    throw "Python not found. Run scripts\setup_env.ps1 first."
}

Write-Host "=== Step 1: Build vector indexes ==="
& $Py (Join-Path $Root "scripts\build_index.py") --candidates $Candidates --out $Indices

Write-Host "=== Step 2: Rank top 100 ==="
& $Py (Join-Path $Root "rank.py") --candidates $Candidates --indices $Indices --out $Out

Write-Host "=== Step 3: Validate CSV ==="
& $Py $Validator $Out

Write-Host "=== Step 4: Audit submission ==="
& $Py (Join-Path $Root "scripts\audit_submission.py") $Out --candidates $Candidates

Write-Host "Done. Rename submission.csv to team_xxx.csv before upload."
