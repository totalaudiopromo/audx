#!/bin/bash
# Full release script for audx
# Bumps version, builds Python package, publishes to npm

set -e

echo "=== audx full release ==="
echo ""

# Check versions
PY_VERSION=$(grep '^version = ' pyproject.toml | head -1 | cut -d'"' -f2)
NPM_VERSION=$(grep '"version"' package.json | head -1 | cut -d'"' -f2)

echo "Current versions:"
echo "  Python: $PY_VERSION"
echo "  npm:    $NPM_VERSION"

if [ "$PY_VERSION" != "$NPM_VERSION" ]; then
    echo ""
    echo "ERROR: Version mismatch between pyproject.toml and package.json"
    exit 1
fi

read -p "Release v$PY_VERSION? (type version to confirm): " confirm
if [ "$confirm" != "$PY_VERSION" ]; then
    echo "Aborted."
    exit 0
fi

# Build Python distributions
echo ""
echo "=== Step 1: Build Python package ==="
bash scripts/build.sh

# Git commit
echo ""
echo "=== Step 2: Git commit ==="
git add -A
git commit -m "release: audx v$PY_VERSION

- Bump version to $PY_VERSION
- Build Python wheel and sdist
- Prepare npm publish"
git tag "v$PY_VERSION"

# Publish to npm
echo ""
echo "=== Step 3: Publish to npm ==="
bash scripts/publish-npm.sh

echo ""
echo "=== Step 4: Push to GitHub ==="
git push origin main --tags

echo ""
echo "✅ Full release complete!"
echo "   npm:  https://www.npmjs.com/package/audx"
echo "   PyPI: (upload manually with twine if desired)"
