"""Loading the scripts of scripts/ in tests: they are files, not a package."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before running it: dataclasses look their module up in sys.modules
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
