# scratch/auto_release.ps1

# 1. Determine next version (simple increment of patch)
$LATEST_TAG = (git describe --tags --abbrev=0 2>$null)
if (-not $LATEST_TAG) { $LATEST_TAG = "v0.6.0" }
$PARTS = $LATEST_TAG.Split('.')
$MAJOR = $PARTS[0]
$MINOR = $PARTS[1]
$PATCH = [int]$PARTS[2]
$NEW_PATCH = $PATCH + 1
$NEW_VERSION = "$MAJOR.$MINOR.$NEW_PATCH"
$NEW_VERSION_NO_V = "$MAJOR.$MINOR.$NEW_PATCH"

Write-Host "Releasing $NEW_VERSION..."

# 2. Extract changes
$CHANGES = git log "$LATEST_TAG..HEAD" --oneline --pretty=format:"- %s"

# 3. Update pyproject.toml version
$PYPROJECT_CONTENT = Get-Content "pyproject.toml" -Raw
$PYPROJECT_CONTENT -replace 'version = ".*"', "version = `"$NEW_VERSION_NO_V`"" | Set-Content "pyproject.toml"

# 4. Update README.md version
$README_CONTENT = Get-Content "README.md" -Raw
$README_CONTENT -replace 'Latest: \*\*v[0-9]*\.[0-9]*\.[0-9]*\*\*', "Latest: **$NEW_VERSION**" | Set-Content "README.md"

# 5. Update CHANGELOG.md (prepend)
$CHANGELOG_CONTENT = Get-Content "CHANGELOG.md" -Raw
$NEW_ENTRY = "## [$NEW_VERSION] - $(Get-Date -Format 'yyyy-MM-dd')`n### Added/Changed/Fixed`n$CHANGES`n`n"
$NEW_ENTRY + $CHANGELOG_CONTENT | Set-Content "CHANGELOG.md"

# 6. Commit and Tag
git add pyproject.toml README.md CHANGELOG.md
git commit -m "chore(release): bump version to $NEW_VERSION

- Update pyproject.toml to $NEW_VERSION_NO_V
- Update README.md to $NEW_VERSION
- Add CHANGELOG entry for $NEW_VERSION"
git tag $NEW_VERSION

# 7. Push and Release
git push origin develop --tags
gh release create $NEW_VERSION --title $NEW_VERSION --notes $CHANGES

Write-Host "Successfully released $NEW_VERSION"
