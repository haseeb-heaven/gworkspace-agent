#!/bin/bash
# scratch/auto_release.sh

set -e

# 1. Determine next version (simple increment of minor patch)
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.6.0")
MAJOR=$(echo $LATEST_TAG | cut -d. -f1)
MINOR=$(echo $LATEST_TAG | cut -d. -f2)
PATCH=$(echo $LATEST_TAG | cut -d. -f3)
NEW_PATCH=$((PATCH + 1))
NEW_VERSION="$MAJOR.$MINOR.$NEW_PATCH"
NEW_VERSION_NO_V="${MAJOR}.${MINOR}.${NEW_PATCH}"

echo "Releasing $NEW_VERSION..."

# 2. Extract changes
CHANGES=$(git log $LATEST_TAG..HEAD --oneline --pretty=format:"- %s")

# 3. Update pyproject.toml version
sed -i "s/version = \".*\"/version = \"$NEW_VERSION_NO_V\"/" pyproject.toml

# 4. Update README.md version
sed -i "s/Latest: \*\*v[0-9]*\.[0-9]*\.[0-9]*\*\*/Latest: \*\*$NEW_VERSION\*\*/" README.md

# 5. Update CHANGELOG.md (prepend)
TEMP_CHANGELOG=$(mktemp)
echo -e "## [$NEW_VERSION] - $(date +%Y-%m-%d)\n### Added/Changed/Fixed\n$CHANGES\n\n$(cat CHANGELOG.md)" > "$TEMP_CHANGELOG"
mv "$TEMP_CHANGELOG" CHANGELOG.md

# 6. Commit and Tag
git add pyproject.toml README.md CHANGELOG.md
git commit -m "chore(release): bump version to $NEW_VERSION

- Update pyproject.toml to $NEW_VERSION_NO_V
- Update README.md to $NEW_VERSION
- Add CHANGELOG entry for $NEW_VERSION"
git tag "$NEW_VERSION"

# 7. Push and Release
git push origin develop --tags
gh release create "$NEW_VERSION" --title "$NEW_VERSION" --notes "$CHANGES"

echo "Successfully released $NEW_VERSION"
