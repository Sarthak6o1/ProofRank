# Bootstrap a local Python 3.12 venv for ProofRank (bracket-safe paths).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Tools = [System.IO.Path]::Combine($Root, ".tools")
$Venv = [System.IO.Path]::Combine($Root, ".venv")
$PyZip = [System.IO.Path]::Combine($Tools, "python-3.12.8-embed-amd64.zip")
$GetPip = [System.IO.Path]::Combine($Tools, "get-pip.py")
$EmbedUrl = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip"
$PipUrl = "https://bootstrap.pypa.io/get-pip.py"

function Test-LiteralPath([string]$Path) { Test-Path -LiteralPath $Path }

[void][System.IO.Directory]::CreateDirectory($Tools)

$wc = New-Object System.Net.WebClient
if (-not (Test-LiteralPath $PyZip)) {
    Write-Host "Downloading Python 3.12 embeddable..."
    $wc.DownloadFile($EmbedUrl, $PyZip)
}

$EmbedDir = [System.IO.Path]::Combine($Tools, "python-embed")
$EmbedPy = [System.IO.Path]::Combine($EmbedDir, "python.exe")
if (-not (Test-LiteralPath $EmbedPy)) {
    Write-Host "Extracting Python embeddable..."
    [void][System.IO.Directory]::CreateDirectory($EmbedDir)
    Expand-Archive -LiteralPath $PyZip -DestinationPath $EmbedDir -Force
    $pth = [System.IO.Path]::Combine($EmbedDir, "python312._pth")
    if (Test-LiteralPath $pth) {
        (Get-Content -LiteralPath $pth) -replace '#import site', 'import site' | Set-Content -LiteralPath $pth
    }
}

if (-not (Test-LiteralPath $GetPip)) {
    Write-Host "Downloading get-pip.py..."
    $wc.DownloadFile($PipUrl, $GetPip)
}

$EmbedPip = [System.IO.Path]::Combine($EmbedDir, "Scripts", "pip.exe")
if (-not (Test-LiteralPath $EmbedPip)) {
    Write-Host "Installing pip..."
    & $EmbedPy $GetPip --no-warn-script-location
}

$VenvPy = [System.IO.Path]::Combine($Venv, "Scripts", "python.exe")
if (-not (Test-LiteralPath $VenvPy)) {
    Write-Host "Creating virtual environment..."
    & $EmbedPy -m venv $Venv
}

$Req = [System.IO.Path]::Combine($Root, "requirements.txt")
Write-Host "Installing requirements..."
& $VenvPy -m pip install --upgrade pip
& $VenvPy -m pip install -r $Req
Write-Host "Setup complete: $VenvPy"
