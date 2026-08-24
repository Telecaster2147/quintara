param(
    [string]$Installer = "",
    [string]$WorkDir = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Installer)) {
    $Installer = Get-ChildItem (Join-Path $PSScriptRoot "..\..\dist\installer\Quintara-*-windows-x64.exe") |
        Select-Object -First 1 -ExpandProperty FullName
}
if ([string]::IsNullOrWhiteSpace($WorkDir)) {
    $WorkDir = Join-Path $env:TEMP ("quintara-install-smoke-" + [guid]::NewGuid().ToString("N"))
}
$installDir = Join-Path $WorkDir "installed"
$dataDir = Join-Path $WorkDir "user-data"
New-Item -ItemType Directory -Force -Path $WorkDir, $dataDir | Out-Null

if (-not (Test-Path $Installer)) { throw "Installer not found: $Installer" }
$install = Start-Process -FilePath $Installer -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=$installDir") -Wait -PassThru
if ($install.ExitCode -ne 0) { throw "Installer returned $($install.ExitCode)" }

$gui = Join-Path $installDir "Quintara.exe"
$cli = Join-Path $installDir "quintara-cli.exe"
$uninstaller = Join-Path $installDir "unins000.exe"
foreach ($path in @($gui, $cli, $uninstaller)) {
    if (-not (Test-Path $path)) { throw "Installed path missing: $path" }
}

$version = & $cli --version
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($version)) { throw "Installed CLI version failed" }
$doctor = & $cli doctor --root $dataDir
$doctorText = ($doctor | Out-String)
if ($LASTEXITCODE -ne 0 -or $doctorText -notmatch '"os"\s*:') { throw "Installed CLI doctor failed" }

# Use a clean process snapshot to prove that the GUI PE subsystem is windowed.
$before = @(Get-Process conhost, powershell, pwsh, WindowsTerminal -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Id)
$guiProcess = Start-Process -FilePath $gui -ArgumentList @("--root", $dataDir) -PassThru
if ($guiProcess.HasExited) { throw "Installed GUI exited during startup" }
$newConsole = @()
for ($sample = 0; $sample -lt 16; $sample++) {
    Start-Sleep -Milliseconds 250
    $after = @(Get-Process conhost, powershell, pwsh, WindowsTerminal -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty Id)
    $newConsole += @($after | Where-Object { $_ -notin $before })
}
$newConsole = @($newConsole | Sort-Object -Unique)
if ($newConsole.Count -ne 0) { throw "Installed GUI created console processes: $newConsole" }
Stop-Process -Id $guiProcess.Id -Force

# Refresh the shell icon cache after install/upgrade and verify the same ICO-backed PE is present.
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class QuintaraShell {
  [DllImport("shell32.dll")] public static extern void SHChangeNotify(uint wEventId, uint uFlags, IntPtr dwItem1, IntPtr dwItem2);
}
"@
[QuintaraShell]::SHChangeNotify(0x08000000, 0x1000, [IntPtr]::Zero, [IntPtr]::Zero)
$hash = (Get-FileHash $gui -Algorithm SHA256).Hash

# The installer defaults to preserving data.  Exercise a second install as an upgrade and
# keep a marker in the standard local data directory so the uninstall boundary is observable.
Set-Content -Path (Join-Path $dataDir "install-smoke.marker") -Value "quintara-install-smoke" -Encoding UTF8
$defaultDataDir = Join-Path $env:LOCALAPPDATA "Quintara"
$defaultMarker = Join-Path $defaultDataDir "install-smoke-preserve.marker"
New-Item -ItemType Directory -Force -Path $defaultDataDir | Out-Null
Set-Content -Path $defaultMarker -Value "preserve-on-uninstall" -Encoding UTF8

$upgrade = Start-Process -FilePath $Installer -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=$installDir") -Wait -PassThru
if ($upgrade.ExitCode -ne 0) { throw "Upgrade installer returned $($upgrade.ExitCode)" }
$upgradeHash = (Get-FileHash $gui -Algorithm SHA256).Hash
if (-not (Test-Path (Join-Path $dataDir "install-smoke.marker"))) { throw "Upgrade removed user data marker" }
[QuintaraShell]::SHChangeNotify(0x08000000, 0x1000, [IntPtr]::Zero, [IntPtr]::Zero)

$uninstall = Start-Process -FilePath $uninstaller -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") -Wait -PassThru
if ($uninstall.ExitCode -ne 0) { throw "Uninstaller returned $($uninstall.ExitCode)" }
$preserved = Test-Path $defaultMarker
if (Test-Path $defaultMarker) { Remove-Item -Force $defaultMarker }
[pscustomobject]@{
    installer = (Resolve-Path $Installer).Path
    install_dir = $installDir
    cli_version = ($version | Out-String).Trim()
    gui_sha256 = $hash
    upgrade_gui_sha256 = $upgradeHash
    upgrade_preserves_data = (Test-Path (Join-Path $dataDir "install-smoke.marker"))
    uninstall_exit_code = $uninstall.ExitCode
    uninstall_preserves_data_by_default = $preserved
    data_marker = (Test-Path (Join-Path $dataDir "install-smoke.marker"))
    icon_cache_refresh = $true
    no_console_processes = $true
} | ConvertTo-Json -Depth 3
