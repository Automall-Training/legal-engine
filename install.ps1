# Install the legal engine on Windows (idempotent; never deletes or overwrites a real folder). The same steps and
# output lines as install.sh; works in Windows PowerShell 5.1 and PowerShell 7, without admin rights.
#   powershell -ExecutionPolicy Bypass -File .\install.ps1     # links skills\* into %USERPROFILE%\.claude\skills,
#                                                               # Python environment, doctor
#   $env:SKILLS_DIR = "...";   ...install.ps1                   # another skills folder (Codex: $env:USERPROFILE\.agents\skills)
#   $env:NO_DEPS = "1";        ...install.ps1                   # links only: no Python environment
#   $env:WITH_PLAYWRIGHT = "1"; ...install.ps1                  # also the free browser engine for scheduled law monitoring
# why: skills are linked with directory junctions, not symlinks: a junction needs neither admin rights nor
# Developer Mode, and removing one never touches the engine folder it points to.
$Engine = $PSScriptRoot
$SkillsDir = if ($env:SKILLS_DIR) { $env:SKILLS_DIR } else { Join-Path $env:USERPROFILE ".claude\skills" }
$env:SKILLS_DIR = $SkillsDir   # doctor reads the same folder
New-Item -ItemType Directory -Force -Path $SkillsDir -ErrorAction Stop | Out-Null

function Fail([string]$What) { Write-Output "FAIL   $What"; exit 1 }

foreach ($src in Get-ChildItem -LiteralPath (Join-Path $Engine "skills") -Directory) {
    if (-not (Test-Path -LiteralPath (Join-Path $src.FullName "SKILL.md"))) { continue }
    $name = $src.Name
    $dst = Join-Path $SkillsDir $name
    $item = Get-Item -LiteralPath $dst -Force -ErrorAction SilentlyContinue
    if ($item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        # why: [IO.Directory]::Delete without recursion removes only the link itself; Remove-Item -Recurse on a
        # junction in PowerShell 5.1 can delete the files of the engine it points to.
        try { [IO.Directory]::Delete($dst) } catch { Fail "could not replace the link $dst ($($_.Exception.Message))" }
        try { New-Item -ItemType Junction -Path $dst -Target $src.FullName -ErrorAction Stop | Out-Null }
        catch { Fail "could not link $name ($($_.Exception.Message))" }
        Write-Output "link   $name (updated)"
    } elseif ($item) {
        Write-Output "SKIP   ${name}: $dst is a real folder — move it away yourself, then run again"
    } else {
        try { New-Item -ItemType Junction -Path $dst -Target $src.FullName -ErrorAction Stop | Out-Null }
        catch { Fail "could not link $name ($($_.Exception.Message))" }
        Write-Output "link   $name"
    }
}

$VenvPy = Join-Path $Engine ".venv\Scripts\python.exe"
if (-not $env:NO_DEPS) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        # why: native programs do not stop the script on failure; each step checks $LASTEXITCODE by hand
        if (-not (Test-Path -LiteralPath $VenvPy)) {
            & uv venv -q --python 3.12 (Join-Path $Engine ".venv")
            if ($LASTEXITCODE -ne 0) { Fail "could not create .venv (uv venv)" }
            Write-Output "env    .venv (Python 3.12)"
        }
        & uv pip install -q --python $VenvPy -r (Join-Path $Engine "requirements.txt")
        if ($LASTEXITCODE -ne 0) { Fail "could not install the Python packages (requirements.txt)" }
        Write-Output "env    packages"
        if ($env:WITH_PLAYWRIGHT) {
            & uv pip install -q --python $VenvPy playwright
            if ($LASTEXITCODE -ne 0) { Fail "could not install Playwright" }
            & $VenvPy -m playwright install chromium
            if ($LASTEXITCODE -ne 0) { Fail "could not download Chromium" }
            Write-Output "browser Playwright Chromium"
        }
    } else {
        Write-Output "MISS   uv — install it (https://docs.astral.sh/uv/), then run install.ps1 again"
    }
}

# doctor checks the python the skills call (python3, else python); the engine's own Python is the last resort.
# why: `python3` may be the Microsoft Store placeholder that only opens the Store, so a candidate must really run.
$Python = $null
foreach ($cmd in @("python3", "python", $VenvPy)) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { continue }
    & $cmd -c "import sys" 2>$null
    if ($LASTEXITCODE -eq 0) { $Python = $cmd; break }
}
if (-not $Python) {
    Write-Output "MISS   python3 — install Python 3.12 (uv python install 3.12 --default), then run install.ps1 again"
    if ($env:NO_DEPS) { exit 0 } else { exit 1 }
}
# NO_DEPS=1 is links only, so a missing .venv is expected there and doctor's verdict is only shown.
& $Python (Join-Path $Engine "tools\doctor.py")
if ($LASTEXITCODE -eq 0) {
    Write-Output "next   open Claude Code and say: «настрой юриста» / «configurează juristul» / «set up the lawyer»"
} elseif (-not $env:NO_DEPS) {
    exit 1
}
exit 0
