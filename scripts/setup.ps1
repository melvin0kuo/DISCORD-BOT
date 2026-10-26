$ErrorActionPreference = 'Stop'
$wizardRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $wizardRoot
$wizardPython = $null
foreach ($version in @('3.11', '3.12')) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try { $candidate = & py "-$version" -c 'import sys; print(sys.executable)' 2>$null }
        catch { continue }
        if ($LASTEXITCODE -eq 0) { $wizardPython = $candidate; break }
    }
}
if (-not $wizardPython -and (Get-Command python -ErrorAction SilentlyContinue)) {
    try { $candidate = & python -c 'import sys; print(sys.executable if sys.version_info[:2] in ((3,11),(3,12)) else "")' 2>$null }
    catch { $candidate = $null }
    if ($LASTEXITCODE -eq 0 -and $candidate) { $wizardPython = $candidate }
}
if (-not $wizardPython) {
    Write-Host 'Python 3.11 or 3.12 is required. Install Python 3.11 from the official WinGet package?'
    if ((Read-Host 'Type Y to install, or any other key to exit') -ne 'Y') { exit 1 }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Start-Process 'https://www.python.org/downloads/windows/'
        Write-Host 'Install Python 3.11/3.12, then run setup.bat again.'
        exit 1
    }
    & winget install --id Python.Python.3.11 --exact --source winget
    Write-Host 'Close this window, then run setup.bat again after installation.'
    exit 0
}
& $wizardPython (Join-Path $wizardRoot 'setup_wizard.py')
exit $LASTEXITCODE
