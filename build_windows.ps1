[CmdletBinding()]
param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

$Python = (Get-Command python -ErrorAction Stop).Source
$IconPath = Join-Path $ProjectRoot "assets\icon.ico"
$LogoPath = Join-Path $ProjectRoot "assets\images\dmk_logo.png"

if (-not (Test-Path -LiteralPath $IconPath)) {
    & $Python -c "from PIL import Image; from pathlib import Path; src=Path(r'$LogoPath'); dst=Path(r'$IconPath'); im=Image.open(src).convert('RGBA'); canvas=Image.new('RGBA',(256,256),'white'); im.thumbnail((224,224),Image.Resampling.LANCZOS); canvas.alpha_composite(im,((256-im.width)//2,(256-im.height)//2)); canvas.save(dst,format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
}

& $Python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install build requirements (exit code $LASTEXITCODE)."
}

& $Python -m PyInstaller --noconfirm --clean SleepSense.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed (exit code $LASTEXITCODE)."
}

if (-not (Test-Path -LiteralPath "dist\SleepSense\SleepSense.exe")) {
    throw "PyInstaller completed without creating dist\SleepSense\SleepSense.exe"
}

if (-not $SkipInstaller) {
    $IsccCandidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $Iscc = $IsccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $Iscc) {
        throw "Inno Setup 6 was not found. Install it, then run this script again."
    }
    & $Iscc "setup.iss"
}

Write-Host "Build complete: dist\SleepSense\SleepSense.exe"
if (-not $SkipInstaller) {
    Write-Host "Installer complete: installer\SleepSense_Setup_3.0.0.exe"
}
