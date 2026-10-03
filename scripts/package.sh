#!/bin/sh
# Build dist/EDRockMaster-v<version>.zip: the folder players extract into EDMC's plugins folder.
# Usage: scripts/package.sh <version>
set -eu
version="$1"
rm -rf dist
mkdir -p dist/EDRockMaster
cp -r load.py edrockmaster L10n LICENSE README.md README.fr.md CHANGELOG.md CHANGELOG.fr.md \
    dist/EDRockMaster/
find dist -name __pycache__ -type d -prune -exec rm -rf {} +
find dist -name .gitkeep -delete
(cd dist && python3 -m zipfile -c "EDRockMaster-v$version.zip" EDRockMaster)
echo "dist/EDRockMaster-v$version.zip"
