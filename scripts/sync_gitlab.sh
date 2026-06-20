#!/bin/bash
set -e

# Sync script to push clean academic builds to GitLab branches
# without cluttering the local workspace or public GitHub history.

# 1. Ensure we are inside the repository root
CDPATH="" cd -- "$(dirname -- "$0")/.."

# 2. Check if the working tree is clean
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️ Error: Working tree has unstaged changes. Please commit or stash them first."
    exit 1
fi

ACTIVE_BRANCH=$(git rev-parse --abbrev-ref HEAD)
TEMP_BRANCH="gitlab-sync-temp-$$"

echo "🔄 Starting GitLab sync from branch '$ACTIVE_BRANCH'..."

# Cleanup trap to ensure we return to the active branch no matter what
trap 'echo "🧹 Cleaning up..."; git checkout -f "$ACTIVE_BRANCH"; git branch -D "$TEMP_BRANCH" || true; echo "✅ Cleanup complete."' EXIT

# 3. Create a temporary branch for the deployment build
git checkout -b "$TEMP_BRANCH"

# 4. Copy academic Czech README to root README.md
if [ -f "nss_docs/README_CZ.md" ]; then
    echo "📄 Copying Czech academic README from nss_docs/README_CZ.md..."
    cp nss_docs/README_CZ.md README.md
else
    echo "⚠️ Warning: nss_docs/README_CZ.md not found! Root README.md will not be replaced."
fi

# 5. Modify .gitignore to allow docs/ and nss_docs/ to be tracked
echo "⚙️ Modifying .gitignore to track docs/ and nss_docs/ folders..."
grep -v -E '^(nss_docs/|docs/)$' .gitignore > .gitignore.temp
mv .gitignore.temp .gitignore

# 6. Add and commit all deployment assets
git add README.md .gitignore
# Explicitly force-add files inside ignored folders if needed
git add -f docs/ nss_docs/

git commit -m "chore: automated academic build for GitLab"

# 7. Push to GitLab branches (main, develop, and release)
echo "🚀 Pushing to gitlab/main..."
git push gitlab "$TEMP_BRANCH:main" --force

echo "🚀 Pushing to gitlab/develop..."
git push gitlab "$TEMP_BRANCH:develop" --force

echo "🚀 Pushing to gitlab/release..."
git push gitlab "$TEMP_BRANCH:release" --force

echo "🎉 Successfully synchronized all branches to GitLab!"
