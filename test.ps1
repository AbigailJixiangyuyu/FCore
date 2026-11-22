param([switch]$Full)

$ErrorActionPreference = 'Stop'
$PytestArgs = @('pytest', '-q')
if (-not $Full) {
    $PytestArgs += @('-m', 'not hardware')
}

uv run --no-sync --directory (Join-Path $PSScriptRoot 'backend') @PytestArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

npm --prefix (Join-Path $PSScriptRoot 'frontend') test
exit $LASTEXITCODE
