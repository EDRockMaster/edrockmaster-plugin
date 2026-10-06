"""Print the build file the packaging puts in the zip (ADR 0016).

The plugin reads it to know its full version, its commit and its channel. The file
is checked with the plugin's own rules: a build it would refuse is never packaged.

Usage: PYTHONPATH=. python3 scripts/build_file.py <version> <channel> <commit>
"""

from __future__ import annotations

import sys

from edrockmaster import VERSION
from edrockmaster.application.build import BuildFileError, build_file_content


def main(arguments: list[str]) -> int:
    if len(arguments) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    version, channel, commit = arguments
    try:
        sys.stdout.write(build_file_content(version, channel, commit, VERSION))
    except BuildFileError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
