param(
  [string]$Destination,
  [switch]$Force
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir
$skillName = Split-Path -Leaf $skillDir

if (-not (Test-Path -LiteralPath (Join-Path $skillDir "SKILL.md"))) {
  throw "SKILL.md was not found. Run this script from inside the unpacked skill package."
}

if (-not $Destination) {
  $Destination = Join-Path $HOME ".codex\skills"
}

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$target = Join-Path $Destination $skillName

if (Test-Path -LiteralPath $target) {
  if (-not $Force) {
    throw "Target already exists: $target. Re-run with -Force to replace it."
  }
  Remove-Item -LiteralPath $target -Recurse -Force
}

Copy-Item -LiteralPath $skillDir -Destination $Destination -Recurse -Force

Write-Host "Installed skill: $skillName"
Write-Host "Destination: $target"
Write-Host "Invoke it with: `$wechat-official-batch-download"

