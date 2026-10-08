"""``python -m edrockmaster.desktop``: the desktop application (ADR 0020)."""

import sys

from edrockmaster.desktop.window import main

sys.exit(main(sys.argv[1:]))
