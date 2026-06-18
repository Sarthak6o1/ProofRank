# Start full 100K vector index build (long-running, logs to index_build.log).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".tools\python-embed\python.exe"
$Log = Join-Path $Root "index_build.log"
$Candidates = Join-Path $Root "India_runs_data_and_ai_challenge\candidates.jsonl"
$Indices = Join-Path $Root "indices"
$BuildScript = Join-Path $Root "scripts\build_index.py"

if (-not (Test-Path -LiteralPath $Py)) {
    & (Join-Path $Root "scripts\setup_env.ps1")
}

& (Join-Path $Root "scripts\clean_indices.ps1")

Write-Host "Starting index build. Log: $Log"
$job = Start-Job -ScriptBlock {
    param($Python, $Script, $Cand, $Out, $LogPath)
    & $Python $Script --candidates $Cand --out $Out *>&1 | Out-File -LiteralPath $LogPath -Encoding utf8
} -ArgumentList $Py, $BuildScript, $Candidates, $Indices, $Log

Write-Host "Index build job id: $($job.Id)"
Write-Host "Tail log with:"
Write-Host "  Get-Content -LiteralPath '$Log' -Wait"
