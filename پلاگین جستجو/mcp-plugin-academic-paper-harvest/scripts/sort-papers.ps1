# Sorts papers into three folders based on a classification JSON.
# Folders, the weak-list, and paths are all parameters (no hardcoded project paths).
#
# classification.json format:
#   { "related":   [ {"rel":"a\\b.pdf","reason":"..."} ],
#     "weak":      [ {"rel":"c.pdf","reason":"..."} ],      # optional middle bucket
#     "unrelated": [ {"rel":"d.pdf","reason":"..."} ] }
#
# Usage:
#   .\sort-papers.ps1 -Root <archiveRoot> -ClassFile <classification.json> `
#     -FolderRelated "مرتبط" -FolderWeak "کم_ارتباط" -FolderUnrelated "نامرتبط" [-WeakFiles "x.pdf","y.pdf"]
param(
  [Parameter(Mandatory=$true)][string]$Root,
  [Parameter(Mandatory=$true)][string]$ClassFile,
  [string]$FolderRelated   = "related",
  [string]$FolderWeak      = "weak",
  [string]$FolderUnrelated = "unrelated",
  [string[]]$WeakFiles = @(),
  [string]$PyExe = "python"
)
$ErrorActionPreference = 'Stop'

# Build classification map from JSON via python (handles non-ASCII correctly).
$classJson = & $PyExe -c "
import json
with open(r'$ClassFile', encoding='utf-8') as f: d = json.load(f)
m = {}
for e in d.get('related',[]):   m[e['rel']] = 'related'
for e in d.get('weak',[]):      m[e['rel']] = 'weak'
for e in d.get('unrelated',[]): m[e['rel']] = 'unrelated'
for k,v in m.items(): print(v + '|' + k)
"

$map = @{}
foreach ($line in $classJson) {
  $idx = $line.IndexOf([char]124)
  if ($idx -lt 0) { continue }
  $map[$line.Substring($idx+1)] = $line.Substring(0, $idx)
}

$moved = @{related=0; weak=0; unrelated=0}
$logs = @()

foreach ($rel in $map.Keys) {
  $src = Join-Path $Root $rel
  if (-not (Test-Path $src)) { $logs += "MISSING: $rel"; continue }
  $cat = $map[$rel]
  $leaf = Split-Path $rel -Leaf
  if ($WeakFiles -contains $leaf)        { $destDir = $FolderWeak }
  elseif ($cat -eq 'related')            { $destDir = $FolderRelated }
  elseif ($cat -eq 'weak')               { $destDir = $FolderWeak }
  else                                   { $destDir = $FolderUnrelated }
  $dest = Join-Path $Root (Join-Path $destDir $leaf)
  if (Test-Path $dest) {
    $i = 2
    $base = [System.IO.Path]::GetFileNameWithoutExtension($leaf)
    $ext  = [System.IO.Path]::GetExtension($leaf)
    while (Test-Path $dest) {
      $dest = Join-Path $Root (Join-Path $destDir ("{0}_{1}{2}" -f $base, $i, $ext))
      $i++
    }
    $logs += "COLLISION: $rel -> $dest"
  }
  Move-Item $src $dest
  if ($destDir -eq $FolderRelated)   { $moved.related++ }
  elseif ($destDir -eq $FolderWeak)  { $moved.weak++ }
  else                               { $moved.unrelated++ }
  $logs += "MOVED: $rel -> $destDir"
}

Write-Output "=== MOVE SUMMARY ==="
Write-Output "$FolderRelated : $($moved.related)"
Write-Output "$FolderWeak    : $($moved.weak)"
Write-Output "$FolderUnrelated: $($moved.unrelated)"
Write-Output ""
Write-Output "=== LOG ==="
$logs | ForEach-Object { Write-Output $_ }
Write-Output ""
Write-Output "=== FINAL TREE ==="
Get-ChildItem $Root -Recurse -File | ForEach-Object { $r = $_.FullName.Substring($Root.Length).TrimStart('\'); Write-Output $r }
Write-Output "=== REMAINING AT ROOT (should be none except empty dirs) ==="
Get-ChildItem $Root -File | ForEach-Object { Write-Output $_.Name }
