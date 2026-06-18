# Remove stale vector-store artifacts before a fresh re-ingestion build.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Targets = @(
    (Join-Path $Root "indices"),
    (Join-Path $Root "indices_smoke"),
    (Join-Path $Root "index_build.log"),
    (Join-Path $Root "index_build.err.log")
)

foreach ($target in $Targets) {
    if (Test-Path -LiteralPath $target) {
        if ((Get-Item -LiteralPath $target).PSIsContainer) {
            Remove-Item -LiteralPath $target -Recurse -Force
            Write-Host "Removed directory: $target"
        } else {
            Remove-Item -LiteralPath $target -Force
            Write-Host "Removed file: $target"
        }
    }
}

Write-Host "Vector store clean. Model cache in models/ was kept for faster rebuild."
