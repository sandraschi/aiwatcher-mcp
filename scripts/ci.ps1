$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot\..
uv sync --group dev
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run ruff check src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run ruff format --check src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run pytest -q --tb=short -m "not slow"
exit $LASTEXITCODE
