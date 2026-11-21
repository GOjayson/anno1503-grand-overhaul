"""Read the original colored building sprites from a local Anno 1503 archive."""

from __future__ import annotations

from mmap import ACCESS_READ, mmap
from pathlib import Path
from struct import iter_unpack, unpack_from
from typing import TYPE_CHECKING

from .fountain import _archive_catalogue, _catalogue_entries, _chunks, entry_fields

if TYPE_CHECKING:
    from PIL.Image import Image

SUPPORTED = {b"BSH_RGBZ", b"BSH_RGBAZ"}
MAX_SIDE = 2048


class StructureArt:
    """Access native isometric building sprites with their archive palettes."""

    def __init__(self, archive: Path):
        with Path(archive).open("rb") as stream:
            self._archive = mmap(stream.fileno(), 0, access=ACCESS_READ)
        try:
            self._entries = _catalogue_entries(self._archive, *_archive_catalogue(self._archive))
            self._palettes: dict[int, tuple[bytes, ...]] = {}
            self._textures: dict[int, tuple[int, int]] = {}
            self._index_graphics()
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> StructureArt:
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        self._archive.close()

    def _index_graphics(self) -> None:
        raw = self._archive
        for tag, start, end in _chunks(raw, 16, len(raw)):
            if tag == b"TEXTURES":
                if end - start < 24:
                    raise ValueError("Truncated native texture header")
                zoom, count = unpack_from("<II", raw, start + 16)
                if zoom in self._textures or not count:
                    raise ValueError("Invalid native texture range")
                self._textures[zoom] = (start + 24, end)
            if tag != b"COLORS":
                continue
            for kind, begin, stop in _chunks(raw, start + 16, end):
                if kind != b"ENTRY" or stop - begin < 0x420:
                    raise ValueError("Truncated native color table")
                ident = unpack_from("<I", raw, begin + 20)[0]
                if ident in self._palettes or raw[begin + 24:begin + 32] != b"BODY\x00\x00\x00\x04":
                    raise ValueError("Unexpected native color table")
                body = raw[begin + 32:begin + 0x420]
                self._palettes[ident] = tuple(
                    bytes((red, green, blue)) for blue, green, red, _ in iter_unpack("<4B", body)
                )
        if set(self._textures) != {0, 1, 2} or not self._palettes:
            raise ValueError("Incomplete native building graphics")

    def sprite(self, source_id: int, *, rotation: int = 0, zoom: int = 0) -> Image:
        """Return the cropped, transparent RGBA front model at the given native angle."""
        from PIL import Image

        if zoom not in self._textures or not 0 <= rotation <= 3:
            raise ValueError("Expected zoom 0–2 and rotation 0–3")
        fields = entry_fields(self._entries[source_id])
        models = fields[b"HAEUSER"]
        tag, start, end = next(_chunks(models, 0, len(models)))
        if tag != b"ENTRY" or end - start < 32:
            raise ValueError(f"Building {source_id} lacks its base model")
        palettes = [ident for (ident,) in iter_unpack("<I", fields[b"COLORS"])]
        for tag, begin, stop in _chunks(models, start + 32, end):
            if tag != b"TEXTURES":
                continue
            if stop - begin < 24:
                raise ValueError(f"Building {source_id} has a truncated texture table")
            native_zoom, count = unpack_from("<II", models, begin + 16)
            if native_zoom != zoom:
                continue
            if not count or stop - begin != 24 + count * 36:
                raise ValueError(f"Building {source_id} has an unexpected base texture table")
            record = begin + 24 + (rotation % count) * 36
            table_slot, = unpack_from("<H", models, record + 4)
            encoding = models[record + 8:record + 20].rstrip(b"\0")
            offset, length = unpack_from("<II", models, record + 24)
            first, last = self._textures[zoom]
            if encoding not in SUPPORTED or not length or offset + length > last - first:
                raise ValueError(f"Building {source_id} uses an unsupported sprite frame")
            if table_slot >= len(palettes) or palettes[table_slot] not in self._palettes:
                raise ValueError(f"Building {source_id} lacks the frame's native palette")
            body = self._archive[first + offset:first + offset + length]
            palette = self._palettes[palettes[table_slot]]
            size, pixels = _decode_frame(body, palette, encoding == b"BSH_RGBAZ")
            sprite = Image.frombytes("RGBA", size, pixels)
            return sprite.crop(sprite.getbbox())
        raise ValueError(f"Building {source_id} lacks sprite zoom {zoom}")


def _decode_frame(body: bytes, palette: tuple[bytes, ...], alpha: bool) -> tuple[tuple[int, int], bytes]:
    runs = []
    x = y = offset = width = height = 0
    while offset < len(body):
        skip = body[offset]
        offset += 1
        if skip == 255:
            break
        if skip == 254:
            x = 0
            y += 1
            if y >= MAX_SIDE:
                raise ValueError("Native sprite exceeds the expected height")
            continue
        if offset == len(body):
            raise ValueError("Truncated native sprite run")
        x += skip
        control = body[offset]
        offset += 1
        count = control & 63 if alpha else control
        if x + count > MAX_SIDE:
            raise ValueError("Unexpected native sprite run")
        end = offset + count * 2
        if end > len(body):
            raise ValueError("Truncated native sprite pixels")
        if count:
            # The renderer reads a depth byte followed by the palette index.
            # RGBAZ uses the two high run bits for 25/50/75/100 percent foreground.
            opacity = (64, 128, 191, 255)[control >> 6] if alpha else 255
            runs.append((x, y, body[offset + 1:end:2], opacity))
            width = max(width, x + count)
            height = max(height, y + 1)
        offset = end
        x += count
    else:
        raise ValueError("Native sprite has no terminator")
    if not runs or offset != len(body):
        raise ValueError("Unexpected native sprite terminator or empty frame")
    pixels = bytearray(width * height * 4)
    for x, y, indexes, opacity in runs:
        start = (y * width + x) * 4
        alpha_channel = bytes((opacity,))
        pixels[start:start + len(indexes) * 4] = b"".join(
            palette[index] + alpha_channel for index in indexes
        )
    return (width, height), bytes(pixels)
