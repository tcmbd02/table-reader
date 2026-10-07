# Installs Table Reader for the current user: copies the app to %LOCALAPPDATA%\Table Reader and adds a desktop shortcut.
# Run by "Install Table Reader.bat" (the .bat bypasses the PowerShell script policy for this one script only).
$ErrorActionPreference = "Stop"
$source = $PSScriptRoot
$target = if ($env:TABLE_READER_INSTALL_DIR) { $env:TABLE_READER_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA "Table Reader" }   # (the override is for testing)
$exe = Join-Path $target "Table Reader.exe"

if (-not (Test-Path (Join-Path $source "Table Reader.exe"))) {
    Write-Host "Table Reader.exe was not found next to this installer. Unzip the whole folder first, then run the installer again." -ForegroundColor Red
    exit 1
}

# If it is running, ask it to quit first so its files can be replaced.
$listening = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -ge 8765 -and $_.LocalPort -le 8784 } | ForEach-Object { $_.LocalPort })
foreach ($port in $listening) {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/ping" -TimeoutSec 2
        if ($r.app -eq "table-reader") {
            try { Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$port/api/quit" -TimeoutSec 15 | Out-Null } catch {}
            Start-Sleep -Seconds 2
        }
    } catch {}
}

if ($source -ne $target) {
    New-Item -ItemType Directory -Force $target | Out-Null
    Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force
}

$shell = New-Object -ComObject WScript.Shell
$desktop = if ($env:TABLE_READER_SHORTCUT_DIR) { $env:TABLE_READER_SHORTCUT_DIR } else { [Environment]::GetFolderPath("Desktop") }
$link = $shell.CreateShortcut((Join-Path $desktop "Table Reader.lnk"))
$link.TargetPath = $exe
$link.WorkingDirectory = $target
$link.Description = "Read tables from scans and photos"
$link.Save()

Write-Host ""
Write-Host "Table Reader is installed. Double-click 'Table Reader' on your desktop to open it." -ForegroundColor Green

$claude = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claude -and -not (Test-Path (Join-Path $env:USERPROFILE ".local\bin\claude.exe"))) {
    Write-Host ""
    Write-Host "Note: Claude Code was not found on this computer. Table Reader needs it (install it from claude.com/claude-code and sign in)." -ForegroundColor Yellow
}
