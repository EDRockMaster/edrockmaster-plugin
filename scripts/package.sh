#!/bin/sh
# Build <dist>/EDRockMaster-v<version>.zip: the folder players extract into EDMC's plugins folder.
# The zip carries edrockmaster/build.json: full version, commit and channel (ADR 0016).
# Usage: scripts/package.sh <version> <channel> [<dist directory, default dist>]
#   production: scripts/package.sh 0.3.0 production
#   candidate:  scripts/package.sh 0.3.0-rc.2 candidate
#   dev:        scripts/package.sh 0.3.0-dev+2606b47 dev
set -eu
version="$1"
channel="$2"
dist="${3:-dist}"
rm -rf "$dist"
mkdir -p "$dist/EDRockMaster"
cp -r load.py edrockmaster L10n LICENSE README.md README.fr.md CHANGELOG.md CHANGELOG.fr.md \
    "$dist/EDRockMaster/"
find "$dist" -name __pycache__ -type d -prune -exec rm -rf {} +
find "$dist" -name .gitkeep -delete
PYTHONPATH=. python3 scripts/build_file.py "$version" "$channel" "$(git rev-parse HEAD)" \
    > "$dist/EDRockMaster/edrockmaster/build.json"
(cd "$dist" && python3 -m zipfile -c "EDRockMaster-v$version.zip" EDRockMaster)
echo "$dist/EDRockMaster-v$version.zip"
