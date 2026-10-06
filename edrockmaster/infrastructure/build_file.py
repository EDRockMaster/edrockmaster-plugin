"""Reads the build file the packaging puts next to the code (ADR 0016)."""

from __future__ import annotations

import logging
from pathlib import Path

from edrockmaster.application.build import (
    BUILD_FILE_NAME,
    BuildFileError,
    BuildInfo,
    development_build,
    parse_build_file,
)


def load_build(package_dir: Path, base_version: str, logger: logging.Logger) -> BuildInfo:
    """The build of the package in ``package_dir``; never fails, a clone has no build file."""
    path = package_dir / BUILD_FILE_NAME
    try:
        return parse_build_file(path.read_text(encoding="utf-8"), base_version)
    except FileNotFoundError:
        return development_build(base_version)
    except (OSError, UnicodeDecodeError, BuildFileError) as error:
        logger.warning("Ignoring the build file %s: %s", path, error)
        return development_build(base_version)
