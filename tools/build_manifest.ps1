# Regenerate MANIFEST.sha256 for this archive.
# Verify afterwards with:  python tools/verify_archive.py
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$destination = Join-Path $root 'MANIFEST.sha256'

$files = Get-ChildItem -LiteralPath $root -Recurse -File -Force | Where-Object {
    $_.Name -ne 'MANIFEST.sha256' -and
    $_.FullName -notmatch '\\\.git\\' -and
    $_.FullName -notmatch '__pycache__' -and
    $_.Name -notlike '*.pyc'
} | Sort-Object FullName

$lines = foreach ($file in $files) {
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLower()
    $relative = $file.FullName.Substring($root.Length + 1) -replace '\\', '/'
    "$hash  $relative"
}

$header = @(
    '# SHA256 manifest for the research archive of',
    "# 'When Diversity Means Outliers: Geographic Allocation for Selecting Training Images",
    '#  in Low-Budget Land Cover Segmentation''.',
    '#',
    '# Verify with:  python tools/verify_archive.py',
    '# Regenerate:  powershell -File tools/build_manifest.ps1',
    '# Excluded from the archive and therefore from this manifest: raw RGB/label PNGs,',
    '# 192 DINOv2 feature caches (*.npz), one trained checkpoint (*.pt), and compiled',
    '# manuscript exports (*.docx/*.pdf/*.zip). See README.md.',
    ''
)

$content = (($header + $lines) -join "`n") + "`n"
[System.IO.File]::WriteAllText($destination, $content, (New-Object System.Text.UTF8Encoding($false)))
"wrote $($lines.Count) entries to $destination"
