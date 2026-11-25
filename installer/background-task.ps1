param(
    [Parameter(Mandatory = $true)][string]$MinecraftDir,
    [ValidateSet('Register', 'Unregister', 'Status')][string]$Mode = 'Register'
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($MinecraftDir).TrimEnd('\', '/')
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$hash = [Security.Cryptography.SHA256]::Create()
try { $id = [BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($sid + '|' + $root.ToLowerInvariant()))).Replace('-', '').Substring(0, 16) }
finally { $hash.Dispose() }
$name = 'NewHorizon-AutoUpdate-' + $id
$scheduler = New-Object -ComObject 'Schedule.Service'
$scheduler.Connect()
$folder = $scheduler.GetFolder('\')
try { $existing = $folder.GetTask($name) }
catch { if ($_.Exception.HResult -ne -2147024894) { throw }; $existing = $null }
if ($Mode -eq 'Status') {
    @{ name = $name; registered = ($null -ne $existing); xml = $(if ($existing) { $existing.Xml } else { '' }) } | ConvertTo-Json -Compress
    exit 0
}
if ($Mode -eq 'Unregister') {
    # Deleting the definition does not terminate an update already in progress.
    if ($existing) { $folder.DeleteTask($name, 0) }
    exit 0
}
$script = Join-Path $root '.newhorizon/background-update.ps1'
if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw 'Atualizador em segundo plano nao encontrado.' }
$powershell = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$arguments = '-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $script + '" -MinecraftDir "' + $root + '"'
$escape = [Security.SecurityElement]
$commandXml = $escape::Escape($powershell)
$argumentsXml = $escape::Escape($arguments)
$start = (Get-Date).AddMinutes(30).ToString('yyyy-MM-ddTHH:mm:ss')
$xml = @"
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
 <RegistrationInfo><Description>Atualiza os mods do New Horizon em segundo plano, a cada 30 minutos e ao entrar no Windows. Aguarda enquanto o Minecraft estiver aberto.</Description></RegistrationInfo>
 <Triggers>
  <LogonTrigger><Enabled>true</Enabled><UserId>$sid</UserId><Delay>PT1M</Delay></LogonTrigger>
  <TimeTrigger><Repetition><Interval>PT30M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition><StartBoundary>$start</StartBoundary><Enabled>true</Enabled></TimeTrigger>
 </Triggers>
 <Principals><Principal id="User"><UserId>$sid</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
 <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><AllowHardTerminate>false</AllowHardTerminate><StartWhenAvailable>true</StartWhenAvailable><RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable><Enabled>true</Enabled><Hidden>true</Hidden><WakeToRun>false</WakeToRun><ExecutionTimeLimit>PT0S</ExecutionTimeLimit></Settings>
 <Actions Context="User"><Exec><Command>$commandXml</Command><Arguments>$argumentsXml</Arguments></Exec></Actions>
</Task>
"@
# InteractiveToken: current user only, no stored password and no elevation.
$folder.RegisterTask($name, $xml, 6, $sid, $null, 3, $null) | Out-Null
Write-Output "Atualizacoes automaticas ativadas: $name"
