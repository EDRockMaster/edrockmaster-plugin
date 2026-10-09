"""Draw the desktop application's icons (ADR 0022): a placeholder until a designed one.

An orange rock on a dark tile, in the sizes the MSIX package and the executable ask,
and the images the Store listing asks (``store/``): the app tile icon, the box art and
the poster with the name. Drawn at a large size, then reduced, so that every size is
smooth.

Usage: python3 scripts/make_icons.py <directory>
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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

PNG_SIZES = {
    "Square44x44Logo.png": 44,
    "Square150x150Logo.png": 150,
    "StoreLogo.png": 50,
}
# The taskbar and Start ask the small logo at exact sizes; "unplated" ones go on any background
TARGET_SIZES = (16, 24, 32, 48, 256)
STORE_SQUARES = {"app-tile-300.png": 300, "box-art-1080.png": 1080, "box-art-2160.png": 2160}
POSTER = (720, 1080)
TEXT = (230, 230, 230, 255)
FONTS = (
    "C:/Windows/Fonts/segoeuib.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def draw(tile: bool = True) -> Image.Image:
    """The rock, on its dark tile or alone (on a transparent background)."""
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas = ImageDraw.Draw(image)
    if tile:
        canvas.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=SIZE // 6, fill=BACKGROUND)

    def points(shape: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [(x * SIZE, y * SIZE) for x, y in shape]

    canvas.polygon(points(OUTLINE), fill=ROCK)
    canvas.polygon(points(LIGHT_FACET), fill=FACET)
    canvas.polygon(points(DARK_FACET), fill=SHADOW)
    return image


def write(directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    image = draw()
    written = []
    for name, size in PNG_SIZES.items():
        path = directory / name
        image.resize((size, size), Image.Resampling.LANCZOS).save(path)
        written.append(path)
    rock = draw(tile=False)
    for size in TARGET_SIZES:
        for suffix in ("", "_altform-unplated"):
            path = directory / f"Square44x44Logo.targetsize-{size}{suffix}.png"
            (rock if suffix else image).resize((size, size), Image.Resampling.LANCZOS).save(path)
            written.append(path)
    icon = directory / "EDRockMaster.ico"
    image.save(icon, sizes=ICO_SIZES)
    written.append(icon)
    return written + store_images(directory / "store")


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONTS:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def store_images(directory: Path) -> list[Path]:
    """What the Store listing asks: the app tile icon, the box art, the poster."""
    directory.mkdir(parents=True, exist_ok=True)
    image = draw()
    written = []
    for name, size in STORE_SQUARES.items():
        path = directory / name
        image.resize((size, size), Image.Resampling.LANCZOS).save(path)
        written.append(path)
    width, height = POSTER
    poster = Image.new("RGBA", POSTER, BACKGROUND)
    rock = draw(tile=False).resize((width * 3 // 4, width * 3 // 4), Image.Resampling.LANCZOS)
    poster.alpha_composite(rock, ((width - rock.width) // 2, height // 8))
    canvas = ImageDraw.Draw(poster)
    for text, size, colour, top in (
        ("EDRockMaster", 84, ROCK, height * 0.72),
        ("Companion", 56, TEXT, height * 0.82),
    ):
        canvas.text((width / 2, top), text, font=_font(size), fill=colour, anchor="mm")
    path = directory / "poster-720x1080.png"
    poster.save(path)
    written.append(path)
    return written


def main(arguments: list[str]) -> int:
    if len(arguments) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    for path in write(Path(arguments[0])):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
