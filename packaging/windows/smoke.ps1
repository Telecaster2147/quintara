$ErrorActionPreference = "Stop"
$gui = Join-Path $PSScriptRoot "..\..\dist\Quintara.exe"
$cli = Join-Path $PSScriptRoot "..\..\dist\quintara-cli.exe"

# Run this from a clean Windows user session while Process Explorer/UI automation
# records that no conhost.exe, powershell.exe or WindowsTerminal.exe window appears.
$before = @(Get-Process conhost, powershell, pwsh, WindowsTerminal -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$process = Start-Process $gui -PassThru
$newConsole = @()
for ($sample = 0; $sample -lt 16; $sample++) {
    Start-Sleep -Milliseconds 250
    $after = @(Get-Process conhost, powershell, pwsh, WindowsTerminal -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $newConsole += @($after | Where-Object { $_ -notin $before })
}
$newConsole = @($newConsole | Sort-Object -Unique)
if ($newConsole.Count -ne 0) { throw "GUI launch created console processes: $newConsole" }
Stop-Process -Id $process.Id -Force

$output = & $cli --version
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($output)) { throw "CLI stdout/exit-code regression" }
$piped = (& $cli --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $piped -ne $output.Trim()) { throw "CLI pipe regression" }
"ok"
