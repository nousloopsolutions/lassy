[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,
    [Parameter(Mandatory = $true)]
    [string]$ControlUrl,
    [Parameter(Mandatory = $true)]
    [string]$RunnerId,
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceConfig,
    [Parameter(Mandatory = $true)]
    [string]$DataDir,
    [string]$TaskName = "LASSY Remote Runner"
)

$ErrorActionPreference = "Stop"
$resolvedRepo = (Resolve-Path -LiteralPath $RepoRoot).Path
$resolvedWorkspaceConfig = (Resolve-Path -LiteralPath $WorkspaceConfig).Path
$resolvedDataDir = (Resolve-Path -LiteralPath $DataDir).Path
$uv = (Get-Command uv -ErrorAction Stop).Source
$venv = Join-Path $resolvedDataDir "venv"
$python = Join-Path $venv "Scripts\python.exe"
$lassy = Join-Path $venv "Scripts\lassy.exe"

& $uv venv $venv --python 3.12
if ($LASTEXITCODE -ne 0) { throw "Failed to create the managed LASSY environment." }
& $uv pip install --python $python $resolvedRepo
if ($LASTEXITCODE -ne 0) { throw "Failed to install LASSY into its managed environment." }

$arguments = @(
    "runner",
    "--control-url", ('"' + $ControlUrl + '"'),
    "--runner-id", ('"' + $RunnerId + '"'),
    "--workspace-config", ('"' + $resolvedWorkspaceConfig + '"'),
    "--data-dir", ('"' + $resolvedDataDir + '"')
) -join " "

$action = New-ScheduledTaskAction -Execute $lassy -Argument $arguments -WorkingDirectory $resolvedRepo
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -Hidden `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Outbound-only signed LASSY job runner" `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
