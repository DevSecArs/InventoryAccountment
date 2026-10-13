param(
    [ValidatePattern('^[a-z0-9][a-z0-9_-]*$')]
    [string]$ProjectName = 'inventory-manual'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$stagingRoot = Join-Path ([IO.Path]::GetTempPath()) ('inventory-build-' + [guid]::NewGuid().ToString('N'))
$previousContext = $env:INVENTORY_BUILD_CONTEXT
$excludedNames = @('node_modules', '.git', '.venv', 'venv', '__pycache__', 'dist', '.pytest_cache', '.mypy_cache', '.ruff_cache')

function Copy-BuildSource([string]$Source, [string]$Destination) {
    $item = Get-Item -LiteralPath $Source -Force
    if ($item.Name -in $excludedNames -or $item.Name.StartsWith('.env') -or
        ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        $item.Extension -in @('.pyc', '.tsbuildinfo')) { return }
    if ($item.PSIsContainer) {
        New-Item -ItemType Directory -Path $Destination -Force | Out-Null
        foreach ($child in Get-ChildItem -LiteralPath $Source -Force) {
            # Filter dependency directories before examining their targets.
            if ($child.Name -in $excludedNames -or $child.Name.StartsWith('.env') -or
                ($child.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
            Copy-BuildSource $child.FullName (Join-Path $Destination $child.Name)
        }
    } else {
        Copy-Item -LiteralPath $Source -Destination $Destination
    }
}

try {
    New-Item -ItemType Directory -Path $stagingRoot | Out-Null
    foreach ($name in @('Dockerfile', 'pyproject.toml', 'uv.lock', 'README.md', 'alembic.ini', 'app', 'alembic', 'scripts', 'frontend')) {
        Copy-BuildSource (Join-Path $repoRoot $name) (Join-Path $stagingRoot $name)
    }
    $env:INVENTORY_BUILD_CONTEXT = $stagingRoot
    & docker compose -p $ProjectName -f (Join-Path $repoRoot 'compose.manual.yaml') build app frontend
    if ($LASTEXITCODE -ne 0) { throw "Docker build failed (exit code $LASTEXITCODE)." }
} finally {
    $env:INVENTORY_BUILD_CONTEXT = $previousContext
    if (Test-Path -LiteralPath $stagingRoot) {
        $resolved = (Resolve-Path -LiteralPath $stagingRoot).Path
        if ($resolved -ne [IO.Path]::GetFullPath($stagingRoot) -or
            (Split-Path -Leaf $resolved) -notmatch '^inventory-build-[0-9a-f]{32}$' -or
            (Split-Path -Parent $resolved) -ne [IO.Path]::GetTempPath().TrimEnd('\', '/')) {
            throw 'Unexpected staging path; cleanup refused.'
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

