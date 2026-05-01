#!/bin/bash
# Build Python distributions (wheel + sdist) for audx

set -e

echo "=== Building audx Python package ==="

# Clean previous builds
rm -rf dist/ build/ audx.egg-info/

# Build with uv (preferred) or pip
if command -v uv &>/dev/null; then
    echo "Using uv to build..."
    uv pip install build
    uv run python -m build --wheel --sdist
else
    echo "Using standard pip..."
    python -m pip install build --upgrade
    python -m build --wheel --sdist
fi

echo ""
echo "✅ Built artifacts in dist/:"
ls -lh dist/

echo ""
echo "To upload to PyPI (test):"
echo "  twine upload --repository testpypi dist/*"
echo ""
echo "To upload to PyPI (production):"
echo "  twine upload dist/*"
