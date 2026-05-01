#!/bin/bash
set -e

echo "🎛️  audx — installation"

# System dependencies
echo "→ brew install ffmpeg sox carla"
brew install ffmpeg sox carla

# Python deps
echo "→ uv sync"
uv sync

# Ensure config dir
mkdir -p ~/.audx

echo "✓ Installation complete."
echo ""
echo "Next steps:"
echo "  1. Index your samples: daw samples index ~/Samples/"
echo "  2. Launch: daw launch"
