#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "Building MemoryVault..."

rm -rf build/ dist/

pyinstaller memoryvault.spec --clean

echo ""
echo "Build complete!"
ls -lh dist/MemoryVault*
