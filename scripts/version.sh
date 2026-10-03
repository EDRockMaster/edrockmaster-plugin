#!/bin/sh
# Print the plugin version, as declared in pyproject.toml (tests check it matches VERSION).
set -eu
sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml | head -n 1
