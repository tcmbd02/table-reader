# Builds the Windows app into dist\Table Reader\  (run from the project folder:  .\packaging\build.ps1)
$ErrorActionPreference = "Continue"   # PyInstaller writes progress to stderr; PowerShell 5.1 would treat that as a failure
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"

& $py packaging\make_icon.py
& $py -m PyInstaller start.py `
    --name "Table Reader" --noconfirm --clean --windowed `
    --icon "$root\packaging\table-reader.ico" `
    --add-data "$root\static;static" --add-data "$root\million;million" `
    --collect-submodules uvicorn --collect-all pypdfium2 --hidden-import multipart --hidden-import xlwt --hidden-import xlrd `
    --distpath "$root\dist" --workpath "$root\build\pyinstaller" --specpath "$root\build"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# Files that go with the app: installer + guide
Copy-Item "$root\packaging\Install Table Reader.bat" "$root\dist\Table Reader\" -Force
Copy-Item "$root\packaging\install.ps1" "$root\dist\Table Reader\" -Force
if (Test-Path "$root\packaging\Table Reader guide.pdf") { Copy-Item "$root\packaging\Table Reader guide.pdf" "$root\dist\Table Reader\" -Force }
$zip = "$root\dist\Table Reader.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "$root\dist\Table Reader" -DestinationPath $zip
Write-Host "Built: $root\dist\Table Reader\  and $zip  (give staff the zip: unzip, then double-click 'Install Table Reader')"
