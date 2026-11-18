# Installs the academic-paper-harvest plugin into your DSH user skills folder.
# Usage: .\install.ps1   (from the package root)
$ErrorActionPreference = 'Stop'
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = Join-Path $env:USERPROFILE ".agents\skills\academic-paper-harvest"

Write-Host "Installing academic-paper-harvest -> $dest"
New-Item -ItemType Directory -Path $dest -Force | Out-Null

# Copy the skill payload (not the installer/README/LICENSE/CHANGELOG/version metadata
# is fine to include, but we only need SKILL.md, references/, scripts/).
foreach ($item in @("SKILL.md", "references", "scripts")) {
  $s = Join-Path $src $item
  if (Test-Path $s) {
    if ((Get-Item $s).PSIsContainer) { Copy-Item $s (Join-Path $dest $item) -Recurse -Force }
    else { Copy-Item $s $dest -Force }
    Write-Host "  copied $item"
  }
}

# Verify
$missing = @()
foreach ($req in @("$dest\SKILL.md", "$dest\references", "$dest\scripts")) {
  if (-not (Test-Path $req)) { $missing += $req }
}
if ($missing.Count -gt 0) {
  Write-Error "Install incomplete, missing: $($missing -join ', ')"
  exit 1
}
Write-Host ""
Write-Host "Installed successfully."
Write-Host "  - SKILL.md"
Write-Host "  - references/"
Write-Host "  - scripts/ ($((Get-ChildItem (Join-Path $dest 'scripts') -Recurse -File).Count) files)"
Write-Host ""
Write-Host "Next: start CDP Chrome with  scripts\start-chrome-cdp.bat  and make sure you are"
Write-Host "logged into the paper site in that Chrome window."
