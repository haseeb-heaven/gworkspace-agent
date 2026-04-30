param(
    [string]$SourceBranch = "develop",
    [string]$DestBranch   = "",          # if provided => single branch sync, else loop all
    [int]$DelaySeconds    = 3
)

$EXCLUDE = @("master", "main", "develop")

$Repo = (git remote get-url origin) -replace ".*github\.com[:/]", "" -replace "\.git$", ""

$ghAvailable = $null -ne (Get-Command gh -ErrorAction SilentlyContinue)

# ─────────────────────────────────────────
# Resolve branch list
# ─────────────────────────────────────────
if ($DestBranch -ne "") {
    $BRANCHES = @($DestBranch)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Repo   : $Repo"                        -ForegroundColor Cyan
    Write-Host "  Source : [$SourceBranch]"              -ForegroundColor Cyan
    Write-Host "  Target : [$DestBranch]  (single)"      -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
} else {
    if ($ghAvailable) {
        $BRANCHES = @(gh api "repos/$Repo/branches" --paginate --jq ".[].name" 2>&1 |
                      Where-Object { $_ -and ($EXCLUDE -notcontains $_) })
    } else {
        $BRANCHES = @(git ls-remote --heads origin 2>&1 |
                      ForEach-Object { ($_ -split "\s+")[1] -replace "^refs/heads/", "" } |
                      Where-Object { $_ -and ($EXCLUDE -notcontains $_) })
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Repo   : $Repo"                        -ForegroundColor Cyan
    Write-Host "  Source : [$SourceBranch]"              -ForegroundColor Cyan
    Write-Host "  Found  : $($BRANCHES.Count) branches"  -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    $BRANCHES | ForEach-Object { Write-Host "  - $_" -ForegroundColor DarkGray }
    Write-Host ""
}

$total   = $BRANCHES.Count
$success = 0
$failed  = @()

# ─────────────────────────────────────────
# FIX 1: Force-pull develop before anything else
# --ff-only first (safe); falls back to hard reset
# if local develop has diverged from remote.
# Guarantees we always spread the true latest
# develop — never a stale local copy.
# ─────────────────────────────────────────
git fetch --all --prune 2>&1 | Out-Null
git checkout $SourceBranch 2>&1 | Out-Null

git pull origin $SourceBranch --ff-only 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARN] $SourceBranch diverged from remote. Hard-resetting to origin/$SourceBranch..." -ForegroundColor DarkYellow
    git reset --hard "origin/$SourceBranch" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [FATAL] Could not update $SourceBranch from remote. Aborting." -ForegroundColor Red
        exit 1
    }
}
Write-Host "[$SourceBranch] force-pulled from remote." -ForegroundColor Green
Write-Host ""

# Auto-stash uncommitted changes
$stashNeeded = (git status --porcelain 2>&1) -ne $null
if ($stashNeeded) {
    Write-Host "  --> Stashing local changes..." -ForegroundColor DarkCyan
    git stash push -u -m "sync-script-autostash" 2>&1 | Out-Null
}

# ─────────────────────────────────────────
# Main sync loop
# FIX: Direct foreach instead of 0..($BRANCHES.Count-1)
# which produces range 0,-1 (two iterations) on empty array
# ─────────────────────────────────────────
foreach ($branch in $BRANCHES) {
    $num = $BRANCHES.IndexOf($branch) + 1

    Write-Host "[$num/$total] $branch" -ForegroundColor Yellow

    # Checkout or create local tracking branch
    git checkout $branch 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        git checkout -b $branch "origin/$branch" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  [FAIL] checkout failed" -ForegroundColor Red
            $failed += $branch
            continue
        }
        Write-Host "  --> Created local tracking branch" -ForegroundColor DarkCyan
    } else {
        Write-Host "  --> Checked out OK" -ForegroundColor Green
    }

    git pull origin $branch --no-rebase 2>&1 | Out-Null

    # ── Step 1: Try clean patience merge ──────────────────────
    git merge $SourceBranch --no-edit --strategy-option=patience 2>&1 | Out-Null

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [CONFLICT] Auto-resolving..." -ForegroundColor Magenta

        $conflictFiles = @(git diff --name-only --diff-filter=U 2>&1)
        $conflictFiles | ForEach-Object { Write-Host "    - $_" -ForegroundColor DarkMagenta }

        git merge --abort 2>&1 | Out-Null

        # ── Step 2: Re-merge using ours as base ───────────────
        git merge $SourceBranch --no-edit --strategy=ours 2>&1 | Out-Null

        if ($LASTEXITCODE -ne 0) {
            Write-Host "  [FAIL] Could not auto-resolve" -ForegroundColor Red
            git merge --abort 2>&1 | Out-Null
            git checkout $SourceBranch 2>&1 | Out-Null
            $failed += $branch
            continue
        }

        # ── Step 3: Selective theirs for pipeline/lock files ──
        foreach ($file in $conflictFiles) {
            $isPipeline = ($file -match "\.(yml|yaml)$") -and ($file -match "\.github")
            $isLockFile = $file -match "(package-lock\.json|poetry\.lock|Pipfile\.lock|requirements.*\.txt)$"

            if ($isPipeline -or $isLockFile) {
                Write-Host "    [theirs] $file (trust $SourceBranch)" -ForegroundColor DarkYellow
                git checkout "origin/$SourceBranch" -- $file 2>&1 | Out-Null
                git add $file 2>&1 | Out-Null
            } else {
                Write-Host "    [ours  ] $file (trust feature branch)" -ForegroundColor DarkCyan
            }
        }

        $dirty = git status --porcelain 2>&1
        if ($dirty) { git commit --amend --no-edit 2>&1 | Out-Null }

        Write-Host "  --> Conflicts auto-resolved!" -ForegroundColor Green
    } else {
        Write-Host "  --> Merge clean" -ForegroundColor Green
    }

    # ─────────────────────────────────────────
    # FIX 2: Force-sync ENTIRE .github/ recursively
    # Old: only .github/scripts/ + .github/workflows/
    # New: full .github/ tree in one command — covers
    # CODEOWNERS, dependabot.yml, ISSUE_TEMPLATE/, etc.
    # ─────────────────────────────────────────
    Write-Host "  --> Force-syncing .github/ (full) from [$SourceBranch]..." -ForegroundColor DarkCyan
    git checkout "origin/$SourceBranch" -- .github/ 2>&1 | Out-Null
    git add .github/ 2>&1 | Out-Null

    $githubDirty = git status --porcelain 2>&1
    if ($githubDirty) {
        git commit -m "ci: force-sync .github/ (full) from $SourceBranch" 2>&1 | Out-Null
        Write-Host "  --> .github/ synced and committed" -ForegroundColor Green
    } else {
        Write-Host "  --> .github/ already in sync" -ForegroundColor DarkGray
    }

    # ── Push ──────────────────────────────────────────────────
    git push origin $branch 2>&1 | Out-Null

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [FAIL] push failed" -ForegroundColor Red
        git checkout $SourceBranch 2>&1 | Out-Null
        $failed += $branch
    } else {
        Write-Host "  [OK] synced!" -ForegroundColor Green
        $success++
    }

    Write-Host ""
    if (($num -lt $total) -and ($DestBranch -eq "")) {
        Start-Sleep -Seconds $DelaySeconds
    }
}

# ─────────────────────────────────────────
# Restore
# ─────────────────────────────────────────
git checkout $SourceBranch 2>&1 | Out-Null

if ($stashNeeded) {
    Write-Host "  --> Restoring stashed changes..." -ForegroundColor DarkCyan
    git stash pop 2>&1 | Out-Null
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DONE: $success/$total synced"          -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host "Failed:" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}

exit 0