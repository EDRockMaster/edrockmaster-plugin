"""``python -m edrockmaster.desktop``: the desktop application (ADR 0020)."""

import sys

import velopack

# Velopack's hooks (install, update, uninstall) come first, and may end the process (ADR 0053);
# an application it did not install goes on
velopack.App().run()

from edrockmaster.desktop.window import main  # noqa: E402 - after Velopack's hooks

sys.exit(main(sys.argv[1:]))
