param(
    [string]$Python = 'D:\Workshop\Python310\python.exe'
)

$ErrorActionPreference = 'Stop'
$BackendRoot = Join-Path $PSScriptRoot 'backend'
$EnvironmentRoot = Join-Path $BackendRoot '.venv'
$ProjectPython = Join-Path $EnvironmentRoot 'Scripts/python.exe'
$Python = (Resolve-Path -LiteralPath $Python).Path

& $Python -c 'import sys, torch; assert sys.version_info[:2] == (3, 10), "Python 3.10 is required"; assert torch.__version__ == "2.8.0+cu128", "Expected the existing torch 2.8.0+cu128"; assert torch.cuda.is_available(), "CUDA is unavailable"; print("Base Python:", sys.executable); print("Shared PyTorch:", torch.__file__)'
if ($LASTEXITCODE -ne 0) { throw 'The selected base Python does not provide the required CUDA PyTorch.' }

if (-not (Test-Path -LiteralPath $EnvironmentRoot)) {
    uv venv --directory $BackendRoot --python $Python --system-site-packages
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create the project environment.' }
}

$EnvironmentConfig = Get-Content -LiteralPath (Join-Path $EnvironmentRoot 'pyvenv.cfg') -Raw
if ($EnvironmentConfig -notmatch '(?im)^include-system-site-packages\s*=\s*true\s*$') {
    throw 'The existing .venv must use Python 3.10 with --system-site-packages. Preserve or remove it before recreating the environment.'
}
& $ProjectPython -c 'import sys; assert sys.version_info[:2] == (3, 10), "Existing .venv is not Python 3.10"'
if ($LASTEXITCODE -ne 0) { throw 'The existing project interpreter is incompatible.' }

# pyproject.toml excludes the externally supplied torch from uv installation.
uv sync --directory $BackendRoot --locked
if ($LASTEXITCODE -ne 0) { throw 'Failed to install project dependencies.' }
uv run --directory $BackendRoot python -c 'import sys, torch; from algorithms.anomaly.runtime import runtime_info; assert torch.__version__ == "2.8.0+cu128"; print("Project Python:", sys.executable); print("PyTorch source:", torch.__file__); print(runtime_info())'
if ($LASTEXITCODE -ne 0) { throw 'Project CUDA validation failed.' }
