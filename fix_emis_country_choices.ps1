param(
    [string]$root = "E:\DJANGO\ASMS\asms"
)

$root = $root.TrimEnd('\', '/')
$target = Join-Path $root "apps\core\models.py"

if (-not (Test-Path $target)) {
    Write-Host "ERROR: '$target' not found. Edit `$root and re-run." -ForegroundColor Red
    return
}

# Always back up before touching the file
$backup = "$target.bak_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item $target $backup
Write-Host "Backup saved to: $backup"

$content = Get-Content $target -Raw

$pattern = "(?s)(class EMISCountryChoices\(models\.TextChoices\):\r?\n).*?(\r?\n[ \t]*UGANDA[ \t]*=[ \t]*'uganda_moes')"

if ($content -notmatch $pattern) {
    Write-Host "Could not find both anchors ('class EMISCountryChoices' and the UGANDA choice line) -- nothing was changed." -ForegroundColor Yellow
    Write-Host "Paste lines 95-115 of apps\core\models.py here and I'll adjust the fix." -ForegroundColor Yellow
    return
}

$replacement = @'
${1}        # Which ministry template this school reports to. Separate from the
        # free-text country field below (address/display) -- this one drives
        # apps.emis's exporter selection and student-registration field logic.
${2}
'@

$fixed = [regex]::Replace($content, $pattern, $replacement)
Set-Content -Path $target -Value $fixed -NoNewline

Write-Host "`nFixed region now reads:" -ForegroundColor Green
Select-String -Path $target -Pattern "class EMISCountryChoices" -Context 0,8 | Out-String

Write-Host "Checking the file is now valid Python..." -ForegroundColor Green
$py = python -m py_compile "$target" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK -- $target compiles cleanly." -ForegroundColor Green
} else {
    Write-Host "Still not compiling -- output below. Backup is at $backup if you want to revert." -ForegroundColor Red
    $py
}