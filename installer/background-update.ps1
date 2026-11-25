param(
    [Parameter(Mandatory = $true)][string]$MinecraftDir,
    [string]$RepositoryUrl = ''
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($MinecraftDir).TrimEnd('\', '/')
$state = Join-Path $root '.newhorizon-state'
$lock = $null
$process = $null

function Save-Status([string]$Status, [string]$Message) {
    $value = @{ status = $Status; message = $Message; checked_at = [DateTime]::UtcNow.ToString('o') }
    [IO.File]::WriteAllText((Join-Path $state 'status.json'), ($value | ConvertTo-Json), [Text.Encoding]::UTF8)
}

try {
    if (-not (Test-Path -LiteralPath (Join-Path $root 'newhorizon-components.xml'))) { exit 0 }
    [IO.Directory]::CreateDirectory($state) | Out-Null
    try { $lock = [IO.File]::Open((Join-Path $state 'update.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch [IO.IOException] { exit 0 }

    # Unknown Java command lines are treated conservatively (for example, a
    # game launched by another user/elevated launcher). Do not kill the game.
    $java = @(Get-CimInstance Win32_Process -Filter "Name = 'java.exe' OR Name = 'javaw.exe'" -ErrorAction Stop)
    if (@($java | Where-Object { -not $_.CommandLine -or $_.CommandLine -match 'minecraft|forge|cpw\.mods|net\.fabricmc|net\.quiltmc' }).Count -gt 0) {
        Save-Status 'deferred' 'Minecraft aberto. A atualizacao sera tentada na proxima verificacao.'
        exit 0
    }
    if (-not $RepositoryUrl) {
        $manifest = Get-Content -LiteralPath (Join-Path $root '.newhorizon/manifest.json') -Raw | ConvertFrom-Json
        $RepositoryUrl = $manifest.repository_url
    }
    if (-not $RepositoryUrl) { throw 'Endereco de atualizacao nao configurado.' }
    $RepositoryUrl = $RepositoryUrl.TrimEnd('/')
    $maintenance = Join-Path $root 'NewHorizonMaintenance.exe'
    if (-not (Test-Path -LiteralPath $maintenance -PathType Leaf)) { throw 'Mecanismo de atualizacao nao encontrado.' }
    $arguments = @('--cache-path', (Join-Path $state 'cache'), '--set-temp-repository', $RepositoryUrl,
        '--auto-answer', 'installationErrorWithCancel=Cancel,installationErrorWithIgnore=Cancel,archiveDownloadError=Cancel,OverwriteTargetDirectory=Yes',
        '--reject-messages', '--accept-licenses', '--confirm-command', 'update')
    $quoted = foreach ($argument in $arguments) {
        if ($argument.Contains('"') -or $argument.Contains("`n") -or $argument.Contains("`r")) { throw 'Argumento de atualizacao invalido.' }
        '"' + $argument + '"'
    }
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $maintenance
    $start.Arguments = $quoted -join ' '
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    Save-Status 'checking' 'Conferindo e instalando atualizacoes do New Horizon.'
    $process = [Diagnostics.Process]::Start($start)
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $output = $stdout.Result + "`n" + $stderr.Result
    [IO.File]::WriteAllText((Join-Path $state 'update.log'), $output, [Text.Encoding]::UTF8)
    if ($process.ExitCode -eq 0) {
        Save-Status 'updated' 'Mods atualizados automaticamente.'
    } elseif ($process.ExitCode -eq 3 -and $output -match 'No updates available' -and $output -notmatch 'Cannot retrieve|No package sources|Cannot download|network error') {
        Save-Status 'current' 'Os mods ja estao atualizados.'
    } else {
        throw "Nao foi possivel atualizar (codigo $($process.ExitCode)). Uma nova tentativa sera feita automaticamente. Consulte .newhorizon-state/update.log."
    }
    exit 0
} catch {
    if ($lock) { Save-Status 'error' $_.Exception.Message }
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
} finally {
    if ($process) { $process.Dispose() }
    if ($lock) { $lock.Dispose() }
}
