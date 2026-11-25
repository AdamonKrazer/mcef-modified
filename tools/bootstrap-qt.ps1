$ErrorActionPreference = 'Stop'
$toolsDir = $PSScriptRoot
$archive = Join-Path $toolsDir 'ifw-win-x86.7z'
$url = 'https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/tools_ifw/qt.tools.ifw.47/4.7.0-0-202402150941ifw-win-x86.7z'
$sevenZip = Join-Path $env:ProgramFiles '7-Zip/7z.exe'
if (-not (Test-Path -LiteralPath $sevenZip)) { throw 'Instale o 7-Zip ou extraia manualmente o pacote do Qt IFW em tools/qtifw.' }
Invoke-WebRequest -Uri $url -OutFile $archive
$expectedHash = 'A8D18072FBCC99362E6972C924BEAAB4F0FB08A24DDE27970DE5D55F682F9B6F'
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expectedHash) {
    throw 'O SHA256 do pacote Qt IFW nao confere. A extracao foi cancelada.'
}
& $sevenZip x $archive "-o$(Join-Path $toolsDir 'qtifw')" -y
if ($LASTEXITCODE -ne 0) { throw 'Falha ao extrair o Qt Installer Framework.' }
Write-Output 'Qt Installer Framework 4.7 pronto. Execute: python tools/build.py'
