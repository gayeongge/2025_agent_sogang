param(
    [string]$Version = "2.51.0",
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$distDir = Join-Path $scriptRoot 'dist'
$extractDir = Join-Path $scriptRoot 'windows'
$zipName = "prometheus-$Version.windows-amd64.zip"
$zipPath = Join-Path $distDir $zipName
$downloadUrl = "https://github.com/prometheus/prometheus/releases/download/v$Version/$zipName"
$targetDir = Join-Path $extractDir "prometheus-$Version.windows-amd64"

Write-Host "Prometheus version : $Version"
Write-Host "Download URL      : $downloadUrl"

New-Item -ItemType Directory -Path $distDir -Force | Out-Null
New-Item -ItemType Directory -Path $extractDir -Force | Out-Null

if (-not (Test-Path $zipPath) -or $Force) {
    Write-Host "Downloading archive to $zipPath..."
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath
} else {
    Write-Host "Archive already exists at $zipPath. Use -Force to re-download."
}

if (Test-Path $targetDir) {
    if ($Force) {
        Write-Host "Removing existing directory $targetDir..."
        Remove-Item -Recurse -Force $targetDir
    } else {
        Write-Host "Target directory already exists. Use -Force to overwrite."
        return
    }
}

Write-Host "Extracting to $extractDir..."
Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force

Write-Host "Prometheus extracted to $targetDir"
Write-Host "Run the following to start Prometheus:"
Write-Host "    $targetDir\\prometheus.exe --config.file=../prometheus.yml"
