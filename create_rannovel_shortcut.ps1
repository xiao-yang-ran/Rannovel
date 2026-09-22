param(
    [string]$EnvironmentPath = "C:\Users\21626\miniconda3\envs\novel",
    [string]$ShortcutPath = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$pythonwPath = Join-Path $EnvironmentPath "pythonw.exe"
$entryPoint = Join-Path $projectRoot "RanNovel.pyw"
$quotedEntryPoint = '"' + $entryPoint + '"'
$iconFile = Get-ChildItem -LiteralPath $projectRoot -Filter "*.ico" | Select-Object -First 1
$iconPath = if ($null -ne $iconFile) { $iconFile.FullName } else { "" }

if (-not (Test-Path -LiteralPath $pythonwPath -PathType Leaf)) {
    throw "The novel environment interpreter was not found: $pythonwPath"
}
if (-not (Test-Path -LiteralPath $entryPoint -PathType Leaf)) {
    throw "The RanNovel entry point was not found: $entryPoint"
}
if ([string]::IsNullOrWhiteSpace($ShortcutPath)) {
    $ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "RanNovel.lnk"
}

$shell = New-Object -ComObject WScript.Shell
try {
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $pythonwPath
    $shortcut.Arguments = $quotedEntryPoint
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.IconLocation = if (Test-Path -LiteralPath $iconPath) { $iconPath } else { $pythonwPath + ",0" }
    $shortcut.Description = "Launch RanNovel 1.0 with the novel Conda environment"
    $shortcut.WindowStyle = 1
    $shortcut.Save()
    $verification = $shell.CreateShortcut($ShortcutPath)
    if ($verification.TargetPath -ne $pythonwPath -or $verification.Arguments -ne $quotedEntryPoint) {
        throw "Shortcut verification failed after saving."
    }
}
finally {
    if ($null -ne $verification) {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($verification)
    }
    if ($null -ne $shortcut) {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shortcut)
    }
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)
}

Write-Output $ShortcutPath
Write-Output ("Target=" + $pythonwPath)
Write-Output ("Arguments=" + $quotedEntryPoint)
