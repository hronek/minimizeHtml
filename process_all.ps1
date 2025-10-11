# Batch-process all HTML files to create aggressive.flat outputs if missing
# Usage:
#   1) From project root: C:\git\minimizeHtml
#   2) Optionally: .\.venv\Scripts\Activate.ps1
#   3) Run: powershell -ExecutionPolicy Bypass -File .\process_all.ps1

$ErrorActionPreference = 'Stop'

# Resolve project root = script location
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

# Prefer venv python, else fall back to system python
$VenvPython = Join-Path $ProjectRoot ".venv/Scripts/python.exe"
if (Test-Path $VenvPython) {
  $Python = $VenvPython
} else {
  $Python = "python"
}

# Ensure requirements are installed (optional safety)
# You can comment this out if not needed on repeated runs
$Req = Join-Path $ProjectRoot "requirements.txt"
if (Test-Path $Req) {
  Write-Host "[INFO] Ensuring dependencies are installed..."
  & $Python -m pip install -r $Req | Out-Null
}

# Find all .html files excluding ones already ending with .aggressive.flat.html
$files = Get-ChildItem -File -Filter *.html -Recurse |
  Where-Object { $_.Name -notmatch '\.aggressive\.flat\.html$' }

if (-not $files) {
  Write-Host "[INFO] No HTML files found to process."
  exit 0
}

$processed = 0
$skipped = 0
$failed = 0

foreach ($f in $files) {
  $full = $f.FullName
  # Build output path: <base>.aggressive.flat.html
  $baseNoExt = [System.IO.Path]::Combine($f.DirectoryName, [System.IO.Path]::GetFileNameWithoutExtension($f.Name))
  $outPath = "$baseNoExt.aggressive.flat.html"

  if (Test-Path $outPath) {
    Write-Host "[SKIP] Exists: $outPath"
    $skipped++
    continue
  }

  Write-Host "[RUN ] Aggressive flatten -> $outPath"
  try {
    & $Python (Join-Path $ProjectRoot "minimize_html.py") `
      "$full" `
      --mode aggressive `
      --flatten-inputs `
      --keep-images `
      -o "$outPath"

    if ($LASTEXITCODE -ne 0) {
      throw "minimize_html.py exited with code $LASTEXITCODE for $full"
    }

    $processed++
  }
  catch {
    Write-Host "[FAIL] $_"
    $failed++
  }
}

Write-Host "`n=== Summary ==="
Write-Host "Processed: $processed"
Write-Host "Skipped:   $skipped"
Write-Host "Failed:    $failed"
