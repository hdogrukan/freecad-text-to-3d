# FreeCAD Text-to-3D - Windows setup and launch script

$ErrorActionPreference = "Stop"

$TestedFreeCADVersion = "1.1.1"

function Resolve-Python {
    $commands = @("py", "python")
    foreach ($command in $commands) {
        $resolved = Get-Command $command -ErrorAction SilentlyContinue
        if ($null -ne $resolved) {
            if ($command -eq "py") {
                return @{ Command = "py"; Args = @("-3") }
            }
            return @{ Command = $resolved.Source; Args = @() }
        }
    }
    return $null
}

function Resolve-FreeCADCmd {
    $explicit = @($env:FREECAD_CMD, $env:FREECAD_PATH) | Where-Object { $_ }
    foreach ($path in $explicit) {
        if (Test-Path $path) {
            return (Resolve-Path $path).Path
        }
    }

    $pathCommand = Get-Command "FreeCADCmd.exe" -ErrorAction SilentlyContinue
    if ($null -ne $pathCommand) {
        return $pathCommand.Source
    }

    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
    foreach ($root in $roots) {
        $apps = Get-ChildItem -Path $root -Directory -Filter "FreeCAD*" -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending
        foreach ($app in $apps) {
            $candidate = Join-Path $app.FullName "bin\FreeCADCmd.exe"
            if (Test-Path $candidate) {
                return $candidate
            }
        }
    }

    return $null
}

Write-Host ""
Write-Host "----------------------------------------------"
Write-Host "  FreeCAD Text-to-3D - Windows Setup & Launch"
Write-Host "----------------------------------------------"
Write-Host ""

$python = Resolve-Python
if ($null -eq $python) {
    Write-Host "[ERROR] Python 3 not found. Install it from https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

$versionArgs = @($python.Args + @("--version"))
& $python.Command @versionArgs
$versionCheckArgs = @($python.Args + @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"))
& $python.Command @versionCheckArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Python 3.10 or newer is required." -ForegroundColor Red
    exit 1
}

$freecadCmd = Resolve-FreeCADCmd
if ($freecadCmd) {
    Write-Host "[OK] FreeCADCmd detected: $freecadCmd"
    $env:FREECAD_CMD = $freecadCmd
    $env:FREECAD_HOME = Split-Path (Split-Path $freecadCmd -Parent) -Parent
    Write-Host "[INFO] Tested FreeCAD version: $TestedFreeCADVersion"
} else {
    Write-Host "[WARN] FreeCADCmd not found." -ForegroundColor Yellow
    Write-Host "       Install FreeCAD from https://www.freecad.org/downloads.php"
    Write-Host "       Or set FREECAD_HOME / FREECAD_CMD before running this script."
    Write-Host "[INFO] Tested FreeCAD version: $TestedFreeCADVersion"
}

if (!(Test-Path "venv")) {
    Write-Host ""
    Write-Host "-> Creating virtual environment..."
    $venvArgs = @($python.Args + @("-m", "venv", "venv"))
    & $python.Command @venvArgs
}

$venvPython = Join-Path (Get-Location) "venv\Scripts\python.exe"
if (!(Test-Path $venvPython)) {
    Write-Host "[ERROR] Virtual environment Python not found: $venvPython" -ForegroundColor Red
    exit 1
}

Write-Host "-> Installing dependencies..."
& $venvPython -m pip install -q --upgrade pip
& $venvPython -m pip install -q -r requirements.txt

if (-not $env:OPENAI_API_KEY -and !(Test-Path ".env")) {
    Write-Host ""
    Write-Host "[WARN] OPENAI_API_KEY is not set and .env was not found." -ForegroundColor Yellow
    Write-Host "       You can enter the API key from the web Settings panel after startup."
    Write-Host ""
}

$outputDir = if ($env:OUTPUT_DIR) { $env:OUTPUT_DIR } else { Join-Path $HOME "freecad_text_to_3d_output" }
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

Write-Host ""
Write-Host "----------------------------------------------"
Write-Host "  Starting app -> http://127.0.0.1:5000"
Write-Host "----------------------------------------------"
Write-Host ""

& $venvPython app.py
