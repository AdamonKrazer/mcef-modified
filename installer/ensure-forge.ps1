param([Parameter(Mandatory = $true)][string]$MinecraftDir, [switch]$RestoreBackup)
$ErrorActionPreference = 'Stop'

function Get-Digest {
    param([string]$Path, [string]$Algorithm)
    $stream = [System.IO.File]::OpenRead($Path)
    $hasher = [System.Security.Cryptography.HashAlgorithm]::Create($Algorithm)
    try { return [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $hasher.Dispose() }
}

function Backup-Mods {
    $root = [System.IO.Path]::GetFullPath($MinecraftDir)
    $backup = Join-Path $root '.newhorizon-backups'
    $statePath = Join-Path $backup 'state.json'
    if (Test-Path -LiteralPath $statePath) { throw 'Existe um backup pendente em .newhorizon-backups. Restaure a instalacao anterior antes de continuar.' }
    $manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
    $names = @($manifest.files | Where-Object { $_.path.StartsWith('mods/') } | ForEach-Object { [System.IO.Path]::GetFileName($_.path) })
    $existing = @($names | Where-Object { Test-Path -LiteralPath (Join-Path $root "mods/$_") -PathType Leaf })
    [System.IO.Directory]::CreateDirectory($backup) | Out-Null
    # Journal first, then move. Undo can recover even if a later file is locked.
    [System.IO.File]::WriteAllText($statePath, (ConvertTo-Json -InputObject $existing))
    foreach ($name in $existing) {
        [System.IO.File]::Move((Join-Path $root "mods/$name"), (Join-Path $backup $name))
    }
}

function Restore-Mods {
    $root = [System.IO.Path]::GetFullPath($MinecraftDir)
    $backup = Join-Path $root '.newhorizon-backups'
    $statePath = Join-Path $backup 'state.json'
    if (-not (Test-Path -LiteralPath $statePath)) { return }
    $names = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    foreach ($name in $names) {
        if ($name -notmatch '^[A-Za-z0-9][A-Za-z0-9._+-]*\.jar$') { throw 'Nome de arquivo invalido no registro de backup.' }
        $source = Join-Path $backup $name
        if (Test-Path -LiteralPath $source -PathType Leaf) {
            [System.IO.Directory]::CreateDirectory((Join-Path $root 'mods')) | Out-Null
            [System.IO.File]::Copy($source, (Join-Path $root "mods/$name"), $true)
            [System.IO.File]::Delete($source)
        }
    }
    [System.IO.File]::Delete($statePath)
    # Non-recursive: never remove unexpected content.
    if ([System.IO.Directory]::GetFileSystemEntries($backup).Length -eq 0) { [System.IO.Directory]::Delete($backup) }
}

function Test-ForgeReady {
    param([string]$Root, $Manifest)
    $versionPath = Join-Path $Root "versions/$($Manifest.forge_profile)/$($Manifest.forge_profile).json"
    if (-not (Test-Path -LiteralPath $versionPath -PathType Leaf)) { return $false }
    try {
        $profile = Get-Content -LiteralPath $versionPath -Raw | ConvertFrom-Json
        # Some launchers flatten inheritsFrom into the profile. Accept that representation too.
        if ($profile.id -ne $Manifest.forge_profile -or $profile.mainClass -ne 'cpw.mods.bootstraplauncher.BootstrapLauncher') { return $false }
        # Use the bundled official profile, not an untrusted installed list of libraries.
        $expected = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'forge-version.json') -Raw | ConvertFrom-Json
        foreach ($library in $expected.libraries) {
            $artifact = $library.downloads.artifact
            if (-not $artifact) { continue }
            $path = Join-Path $Root ('libraries/' + $artifact.path)
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $false }
            if ((Get-Item -LiteralPath $path).Length -eq 0) { return $false }
            if ($artifact.sha1 -and (Get-Digest $path 'SHA1') -ne $artifact.sha1) { return $false }
        }
        return $true
    } catch { return $false }
}

function Find-Java17 {
    param([string]$Root)
    $candidates = @()
    if ($env:NEW_HORIZON_JAVA) { $candidates += $env:NEW_HORIZON_JAVA }
    if ($env:JAVA_HOME) { $candidates += Join-Path $env:JAVA_HOME 'bin/java.exe' }
    $onPath = Get-Command java.exe -ErrorAction SilentlyContinue
    if ($onPath) { $candidates += $onPath.Source }
    $searchRoots = @(
        (Join-Path $Root 'runtime'),
        (Join-Path $env:ProgramFiles 'Eclipse Adoptium'),
        (Join-Path $env:ProgramFiles 'Java'),
        (Join-Path $env:ProgramFiles 'Microsoft'),
        (Join-Path $env:LOCALAPPDATA 'Packages/Microsoft.4297127D64EC6_8wekyb3d8bbwe/LocalCache/Local/runtime')
    )
    foreach ($searchRoot in $searchRoots) {
        if (Test-Path -LiteralPath $searchRoot) {
            $candidates += @(Get-ChildItem -LiteralPath $searchRoot -Filter java.exe -Recurse -ErrorAction SilentlyContinue | ForEach-Object FullName)
        }
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        # Java prints -version to stderr. Capture it without PowerShell 5 treating it as a terminating error.
        $start = New-Object System.Diagnostics.ProcessStartInfo
        $start.FileName = $candidate
        $start.Arguments = '-version'
        $start.UseShellExecute = $false
        $start.CreateNoWindow = $true
        $start.RedirectStandardError = $true
        $process = [System.Diagnostics.Process]::Start($start)
        $versionOutput = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        $exitCode = $process.ExitCode
        $process.Dispose()
        if ($exitCode -eq 0 -and $versionOutput -match 'version "17[.\"]') { return $candidate }
    }
    throw 'Java 17 nao encontrado. Instale Java 17 ou defina NEW_HORIZON_JAVA com o caminho completo de java.exe e execute novamente.'
}

function Invoke-EnsureForge {
    $root = [System.IO.Path]::GetFullPath($MinecraftDir)
    $manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
    foreach ($file in $manifest.files) {
        $path = Join-Path $PSScriptRoot $file.path
        if ((Get-Digest $path 'SHA256') -ne $file.sha256) {
            throw "Arquivo corrompido: $($file.path). Baixe novamente o instalador."
        }
    }
    if (Test-ForgeReady $root $manifest) {
        Write-Output "Forge $($manifest.forge_profile) ja instalado e verificado."
        return
    }
    $vanilla = Join-Path $root "versions/$($manifest.minecraft)/$($manifest.minecraft).json"
    if (-not (Test-Path -LiteralPath $vanilla)) {
        throw "Execute Minecraft $($manifest.minecraft) uma vez pelo launcher, feche o jogo e tente novamente. Pasta selecionada: $root"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $root 'launcher_profiles.json')) -and
        -not (Test-Path -LiteralPath (Join-Path $root 'launcher_profiles_microsoft_store.json'))) {
        throw 'Abra o Minecraft Launcher antes de instalar o Forge. Nenhum launcher_profiles foi encontrado na pasta selecionada.'
    }
    $java = Find-Java17 $root
    $forgeJar = Join-Path $PSScriptRoot 'forge-installer.jar'
    Write-Output "Instalando Forge $($manifest.forge_profile) com $java. O download das bibliotecas pode levar alguns minutos."
    Push-Location -LiteralPath $PSScriptRoot
    try {
        & $java '-jar' $forgeJar '--installClient' $root
        if ($LASTEXITCODE -ne 0) { throw "O instalador oficial do Forge retornou codigo $LASTEXITCODE. Consulte .newhorizon/forge-installer.jar.log." }
    } finally { Pop-Location }
    if (-not (Test-ForgeReady $root $manifest)) {
        throw 'O Forge terminou sem criar uma instalacao completa. Verifique a conexao e os detalhes do instalador.'
    }
    Write-Output 'Forge instalado e verificado.'
}

try {
    if ($RestoreBackup) { Restore-Mods }
    else { Invoke-EnsureForge; Backup-Mods }
    exit 0
}
catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }
