"""Draw the desktop application's icon (ADR 0053): a placeholder until a designed one.

An orange rock on a dark tile, in every size Windows asks of an icon, for the executable
and the installer. Drawn at a large size, then reduced, so that every size is smooth.

Usage: python3 scripts/make_icons.py <directory>
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

BACKGROUND = (13, 15, 18, 255)
ROCK = (255, 140, 0, 255)
FACET = (255, 179, 71, 255)
SHADOW = (178, 92, 0, 255)
SIZE = 1024

# The rock's outline and two facets, on a 0..1 square
OUTLINE = [
    (0.30, 0.22),
    (0.58, 0.16),
    (0.80, 0.34),
    (0.84, 0.60),
    (0.64, 0.82),
    (0.34, 0.84),
    (0.16, 0.60),
    (0.18, 0.36),
]
LIGHT_FACET = [(0.30, 0.22), (0.58, 0.16), (0.52, 0.42), (0.18, 0.36)]
DARK_FACET = [(0.52, 0.42), (0.84, 0.60), (0.64, 0.82), (0.46, 0.60)]

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def draw() -> Image.Image:
    """The rock on its dark tile."""
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas = ImageDraw.Draw(image)
    canvas.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=SIZE // 6, fill=BACKGROUND)

    def points(shape: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [(x * SIZE, y * SIZE) for x, y in shape]

    canvas.polygon(points(OUTLINE), fill=ROCK)
    canvas.polygon(points(LIGHT_FACET), fill=FACET)
    canvas.polygon(points(DARK_FACET), fill=SHADOW)
    return image


def write(directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    icon = directory / "EDRockMaster.ico"
    draw().save(icon, sizes=ICO_SIZES)
    return [icon]


def main(arguments: list[str]) -> int:
    if len(arguments) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    for path in write(Path(arguments[0])):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
