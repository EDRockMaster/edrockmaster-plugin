#!/bin/sh
# Print the release notes of a version: its English, then French, changelog section.
# Usage: scripts/release_notes.sh <version>
set -eu
version="$1"
section() {
    awk -v heading="## [$version]" '
        index($0, heading) == 1 { found = 1; next }
        found && /^## \[/ { exit }
        found && /^\[/ { exit }
        found { print }
    ' "$1"
}
notes_en=$(section CHANGELOG.md)
notes_fr=$(section CHANGELOG.fr.md)
if [ -z "$notes_en" ] || [ -z "$notes_fr" ]; then
    echo "no changelog entry for $version" >&2
    exit 1
fi
printf '%s\n\n---\n\n*Français*\n\n%s\n' "$notes_en" "$notes_fr"
