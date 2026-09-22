param(
    [string]$EnvironmentPath = "C:\Users\21626\miniconda3\envs\novel",
    [string]$ShortcutPath = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $projectRoot "create_rannovel_shortcut.ps1") -EnvironmentPath $EnvironmentPath -ShortcutPath $ShortcutPath
