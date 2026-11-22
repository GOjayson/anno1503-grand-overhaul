"""Render native building sprites into the existing menu button frames."""

from functools import lru_cache
from struct import unpack_from

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from . import menu
from .structure_art import StructureArt


def _backdrop(width, height):
    """A subdued, textured green behind the sprite keeps fine details visible."""
    image = Image.new("RGBA", (width, height))
    pixels = []
    for y in range(height):
        for x in range(width):
            distance = ((x - width * 0.49) / width) ** 2 + ((y - height * 0.47) / height) ** 2
            grain = ((17 * x + 31 * y + 13 * x * y) % 11) - 5
            light = round(23 * max(0, 1 - 2.5 * distance)) + grain
            pixels.append((61 + light, 66 + light, 50 + light, 255))
    image.putdata(pixels)
    return image


def _compose(sprite, size, aristocrat):
    width, height = size
    picture = _backdrop(width, height)
    bounds = sprite.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("Culture building sprite has no visible pixels")
    sprite = sprite.crop(bounds)
    sprite = ImageOps.contain(sprite, (width - 4, height - 4), Image.Resampling.LANCZOS)
    x = (width - sprite.width) // 2
    y = (height - sprite.height) // 2
    alpha = sprite.getchannel("A")
    shadow = Image.new("RGBA", sprite.size, (30, 24, 18))
    shadow.putalpha(alpha.filter(ImageFilter.GaussianBlur(0.8)).point(lambda value: value // 3))
    picture.alpha_composite(shadow, (x + 1, y + 1))
    picture.alpha_composite(sprite, (x, y))
    if aristocrat:
        # The gilded corner identifies the separately gated housing option.
        draw = ImageDraw.Draw(picture)
        x = width - 6
        draw.polygon([(x, 1), (x + 4, 5), (x, 9), (x - 4, 5)], fill=(57, 39, 24))
        draw.polygon([(x, 2), (x + 3, 5), (x, 8), (x - 3, 5)], fill=(226, 172, 66))
        draw.point((x, 4), fill=(255, 233, 157))
    return picture.convert("RGB")


class BuildingIcons:
    """Share one native sprite lookup across all three UI texture atlases."""

    def __init__(self, native: StructureArt, sources: dict[int, tuple[int, bool]]):
        self.native = native
        self.sources = sources
        self.render = lru_cache(maxsize=None)(self._render)

    def _render(self, source, width, height, aristocrat):
        return _compose(self.native.sprite(source), (width, height), aristocrat)

    def paint(self, frame, ident, state, palettes):
        formats = menu.formats
        width, height, source_pixels = formats._decode(frame)
        if width != height or width not in (39, 50) or -1 in source_pixels:
            raise ValueError(f"Unsupported culture thumbnail frame for {ident}")
        palette_id = next(unpack_from("<H", frame, start + 20)[0]
                          for tag, start, _ in formats._chunks(frame, 24) if tag == "HEAD")

        border = (4 if width == 50 else 3) if state == 1 else 2
        source, aristocrat = self.sources[ident]
        # All three states reserve the same interior, so the image never jumps.
        inset = 4 if width == 50 else 3
        inner = width - 2 * inset
        rendered = self.render(source, inner, inner, aristocrat)
        if state == 2:
            rendered = ImageEnhance.Brightness(ImageOps.grayscale(rendered)).enhance(0.75).convert("RGB")
        indexed = rendered.quantize(palette=palettes(palette_id), dither=Image.Dither.NONE)

        pixels = bytearray(source_pixels)
        backdrop = indexed.getpixel((0, 0))
        for y in range(border, height - border):
            start = y * width + border
            pixels[start:start + width - 2 * border] = bytes([backdrop]) * (width - 2 * border)
        rows = indexed.tobytes()
        for y in range(inner):
            start = (y + inset) * width + inset
            pixels[start:start + inner] = rows[y * inner:(y + 1) * inner]
        return formats._replace_body(frame, list(pixels))


def indexed_palette(colors):
    palette = Image.new("P", (1, 1))
    palette.putpalette([value for color in colors for value in color])
    return palette
