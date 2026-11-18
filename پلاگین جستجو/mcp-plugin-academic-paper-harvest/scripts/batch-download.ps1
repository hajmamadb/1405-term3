# Batch download of papers from a paper site (e.g. Academia.edu) via the user's logged-in Chrome (CDP).
# The paper list is a parameter — replace the $papers array with your own candidates.
#
# Usage:
#   .\batch-download.ps1 -TabId <TAB> -TargetDir <downloadDir> [-PapersJson <papers.json>]
#
# papers.json format (array of {url, name}):
#   [ { "url": "https://www.academia.edu/123/Title", "name": "01_Author_Year_Title" }, ... ]
# If -PapersJson is omitted, edit the $papers array below and re-save.
param(
  [Parameter(Mandatory=$true)][string]$TabId,
  [Parameter(Mandatory=$true)][string]$TargetDir,
  [string]$PapersJson,
  [int]$MinPause = 35,
  [int]$MaxPause = 50
)
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null

if ($PapersJson -and (Test-Path $PapersJson)) {
  $papers = & python -c "
import json
with open(r'$PapersJson', encoding='utf-8') as f:
    for p in json.load(f):
        print(p['url'] + '|' + p.get('name',''))
"
  $papers = $papers | ForEach-Object {
    $i = $_.IndexOf([char]124)
    [pscustomobject]@{ Url = $_.Substring($i+1); Name = $_.Substring(0, $i) }
  }
} else {
  # Fallback: edit this array.
  $papers = @(
    @{Url="https://www.academia.edu/123/Example_Title"; Name="01_Example_Author_Year"}
  )
}

$completed = 0; $failed = 0
for ($i = 0; $i -lt $papers.Count; $i++) {
  $p = $papers[$i]; $idx = ($i + 1)
  Write-Output "=== [$idx/$($papers.Count)] $($p.Name) ==="
  Write-Output "URL: $($p.Url)"
  try {
    $output = & node (Join-Path $scriptDir "download-pdf3.mjs") $TabId $p.Url $TargetDir 2>&1
    $outputText = $output -join "`n"
    if ($outputText -match 'completed' -and $outputText -notmatch 'EXC|error|No PDF|no single') {
      Write-Output "OK: downloaded"; $completed++
    } else {
      Write-Output "ISSUE: $($outputText.Substring(0, [Math]::Min(300, $outputText.Length)))"; $failed++
    }
  } catch {
    Write-Output "ERROR: $_"; $failed++
  }
  if ($i -lt ($papers.Count - 1)) {
    $pause = $MinPause + (Get-Random -Max ($MaxPause - $MinPause + 1))
    Write-Output "Waiting ${pause}s before next download (Cloudflare rate-limit)..."; Start-Sleep -Seconds $pause
  }
}
Write-Output ""
Write-Output "=== SUMMARY ==="
Write-Output "Completed: $completed"
Write-Output "Failed: $failed"
Write-Output "Files in folder:"
Get-ChildItem $TargetDir -File | ForEach-Object { Write-Output "  $($_.Name) ($($_.Length) bytes)" }
