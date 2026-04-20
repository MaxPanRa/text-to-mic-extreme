@echo off
setlocal

cd /d "%~dp0"

set "DIST_ENV=dist\.env"
set "DIST_EXE=%CD%\dist\text-to-mic.exe"
set "ENV_BACKUP=%TEMP%\text-to-mic-dist-env.bak"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$exe=[System.IO.Path]::GetFullPath('%DIST_EXE%'); $procs=Get-Process text-to-mic -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $exe }; if ($procs) { Write-Host 'Closing running packaged app before build...'; $procs | Stop-Process -Force }"

if exist "%DIST_ENV%" (
    echo Preserving existing dist\.env...
    copy /y "%DIST_ENV%" "%ENV_BACKUP%" >nul
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Local virtual environment not found at .venv\Scripts\python.exe
    echo Create or restore .venv before running this builder.
    exit /b 1
)

echo Checking PyInstaller in .venv...
".venv\Scripts\python.exe" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing into .venv...
    ".venv\Scripts\python.exe" -m pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller.
        exit /b 1
    )
)
if not errorlevel 1 (
    echo PyInstaller already installed in .venv.
)

if exist build (
    echo Removing previous build folder...
    rmdir /s /q build
)

if exist dist (
    echo Removing previous dist folder...
    rmdir /s /q dist
)

echo Building EXE from text-to-mic.spec...
".venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm text-to-mic.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    exit /b 1
)

if exist ".env.example" if exist "dist" (
    copy /y ".env.example" "dist\.env.example" >nul
)

if exist "LICENSE.md" if exist "dist" (
    copy /y "LICENSE.md" "dist\LICENSE.md" >nul
)

if exist "%ENV_BACKUP%" if exist "dist" (
    copy /y "%ENV_BACKUP%" "dist\.env" >nul
    del /q "%ENV_BACKUP%" >nul 2>&1
)

echo.
echo Build complete.
echo EXE output: dist\text-to-mic.exe
echo dist\.env is preserved across rebuilds when it already exists.
exit /b 0
