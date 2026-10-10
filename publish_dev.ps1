# Publishes the draft the way "Publish dev site.bat" does, with retries for the two things that fail on this machine:
# Windows briefly blocking a file while git stages it, and the router losing the address lookup during a push.
#   powershell -NoProfile -ExecutionPolicy Bypass -File publish_dev.ps1
# Writes its steps to %TEMP%\publish_dev.txt and ends with "done ok=True" or "done ok=False".
$env:PYTHONIOENCODING = 'utf-8'
$log = "$env:TEMP\publish_dev.txt"
function Say($t) { "$t $(Get-Date -Format s)" | Out-File $log -Append -Encoding utf8 }
"start $(Get-Date -Format s)" | Out-File $log -Encoding utf8
cmd /c ".venv\Scripts\python.exe build_shell.py --ride --root site\dev >> `"$log`" 2>&1"
cmd /c ".venv\Scripts\python.exe quiet_pages.py site\dev >> `"$log`" 2>&1"
if (-not (Test-Path docs\dev)) { New-Item -ItemType Directory docs\dev | Out-Null }
robocopy "site\dev" "docs\dev" /MIR /NFL /NDL /NJH /NJS /NP /XF _companion_lab.html companions.html _tabicons_lab.html | Out-Null
Say "robocopy exit $LASTEXITCODE (below 8 is success)"
if ($LASTEXITCODE -ge 8) { Say "STOPPED: the copy failed"; "done ok=False" | Out-File $log -Append -Encoding utf8; exit 1 }
$staged = $false
foreach ($try in 1..6) {
  cmd /c "git add -A docs/dev >nul 2>&1"
  Say "git add try $try exit $LASTEXITCODE"
  if ($LASTEXITCODE -eq 0) { $staged = $true; break }
  Start-Sleep -Seconds 6
}
if (-not $staged) { Say "STOPPED: git could not stage the pages"; "done ok=False" | Out-File $log -Append -Encoding utf8; exit 1 }
cmd /c "git diff --cached --quiet"
if ($LASTEXITCODE -eq 0) { Say "nothing changed in docs/dev" }
else {
  $ver = (& .venv\Scripts\python.exe version.py current).Trim()
  cmd /c "git commit -q -m `"Publish draft v$ver`" -m `"Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`" >nul 2>&1"
  Say "commit exit $LASTEXITCODE (v$ver)"
}
$ok = $false
foreach ($try in 1..6) {
  cmd /c "git push -q origin main >nul 2>&1"
  Say "push try $try exit $LASTEXITCODE"
  if ($LASTEXITCODE -eq 0) { $ok = $true; break }
  Start-Sleep -Seconds 20
}
cmd /c "git push -q origin --tags >nul 2>&1"
Say "tags push exit $LASTEXITCODE"
"done ok=$ok" | Out-File $log -Append -Encoding utf8
