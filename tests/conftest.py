import tkinter as tk
from collections.abc import Iterator

import pytest


@pytest.fixture
def root() -> Iterator[tk.Tk]:
    """A hidden Tk root; widget tests are skipped where no display is available (CI)."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    yield root
    root.destroy()
