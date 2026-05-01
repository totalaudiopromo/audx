#!/bin/bash
# audx npm publish script
# Reserves the 'audx' npm namespace and publishes CLI wrapper

set -e  # Exit on error

echo "=== audx npm publish ==="
echo "Date: $(date)"
echo ""

# Check we're in the right directory
if [ ! -f "package.json" ]; then
    echo "ERROR: package.json not found. Run from audx root."
    exit 1
fi

# Read version from pyproject.toml (sync with Python package)
PY_VERSION=$(grep '^version = ' pyproject.toml | head -1 | cut -d'"' -f2)
NPM_VERSION=$(grep '"version"' package.json | head -1 | cut -d'"' -f2)

echo "Python package version: $PY_VERSION"
echo "npm package version:    $NPM_VERSION"

if [ "$PY_VERSION" != "$NPM_VERSION" ]; then
    echo "WARNING: Version mismatch! Consider syncing package.json with pyproject.toml"
fi

# Verify npm credentials
echo ""
echo "=== Checking npm auth ==="
if ! npm whoami &>/dev/null; then
    echo "Not logged in to npm. Run: npm login"
    exit 1
fi
echo "Logged in as: $(npm whoami)"

# Show package info
echo ""
echo "=== Package metadata ==="
npm pack --dry-run 2>/dev/null | head -20

# Safety check: confirm publish
echo ""
read -p "Publish 'audx' v$NPM_VERSION to npm? (type 'yes' to confirm): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# Publish
echo ""
echo "=== Publishing... ==="
npm publish

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Success! audx v$NPM_VERSION is live on npm"
    echo "   https://www.npmjs.com/package/audx"
else
    echo ""
    echo "❌ Publish failed. Check errors above."
    exit 1
fi
