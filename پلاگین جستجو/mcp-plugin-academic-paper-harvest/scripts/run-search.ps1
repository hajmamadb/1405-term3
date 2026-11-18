# Runs an Academia.edu search via the user's logged-in Chrome (CDP 9222).
# Usage: .\run-search.ps1 -TabId XXX -Query "some query" [-WaitSec 10]
param(
  [Parameter(Mandatory=$true)][string]$TabId,
  [Parameter(Mandatory=$true)][string]$Query,
  [int]$WaitSec = 10
)
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Build the window-var file using a JS single-quoted string (escape single quotes in query)
$escaped = $Query.Replace('\','\\').Replace("'",'\''')
$varFile = Join-Path $dir "js\__query.js"
$content = "window.__searchQuery = '${escaped}'; JSON.stringify({set: window.__searchQuery})"
[System.IO.File]::WriteAllText($varFile, $content, (New-Object System.Text.UTF8Encoding $false))
node (Join-Path $dir "cdp-file.mjs") eval $TabId $varFile | Out-Null
node (Join-Path $dir "cdp-file.mjs") eval $TabId (Join-Path $dir "js\type-search.js") | Out-Null
Start-Sleep -Seconds $WaitSec
node (Join-Path $dir "cdp-file.mjs") eval $TabId (Join-Path $dir "js\extract-results.js")
