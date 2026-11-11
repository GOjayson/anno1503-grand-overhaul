"""Read-only coastal-shape metadata proof for the exact History Edition catalogue.

No native island bytes are generated or distributed. Equal groups mean equal
height-derived coastal masks under rotation/reflection, not equal resources,
buildable area, ownership or navigation.
"""
from __future__ import annotations

import hashlib
from pathlib import Path, PureWindowsPath
import re
import struct
from typing import Callable

CATALOGUE_SHA256 = '5a41a82a47d314a89fb774a74945b3f7a2960083f66b17a055ff17abb48d30d4'
TEMPLATE_COUNT = 444
SHAPE_COUNT = 347
_ROW = re.compile(rb'^\{"([^"\r\n]+)",(\d+(?:,\d+){8}),\{([\d,]+)\}\},?$', re.M)
_TAG = re.compile(rb'[A-Z0-9_]{1,12}\x00*')


class IslandCatalogueError(ValueError):
    """A source island or derived metadata differs from the reviewed input."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _chunks(data: bytes, start: int, end: int):
    if not isinstance(data, bytes) or not 0 <= start <= end <= len(data):
        raise IslandCatalogueError('Island chunk bounds differ.')
    at = start
    while at < end:
        if at + 16 > end or not _TAG.fullmatch(data[at:at+12]):
            raise IslandCatalogueError('Island chunk header is malformed.')
        size = struct.unpack_from('<I', data, at+12)[0]
        finish = at + 16 + size
        if finish > end:
            raise IslandCatalogueError('Island chunk crosses its parent.')
        yield data[at:at+12].rstrip(b'\0'), data[at+16:finish]
        at = finish


def coastal_shape(data: bytes) -> dict:
    """Inspect one bounded native SCP without running the game or loading code."""
    if not isinstance(data, bytes) or len(data) > 64*1024*1024 or len(data) < 16:
        raise IslandCatalogueError('Island input is absent or unbounded.')
    root_end = 16 + struct.unpack_from('<I', data, 12)[0]
    if data[:12].rstrip(b'\0') not in (b'ANNO', b'ANNOADDON1') or root_end > len(data):
        raise IslandCatalogueError('Island container is unsupported.')
    islands = [payload for tag, payload in _chunks(data, 16, root_end) if tag == b'INSEL5']
    if len(islands) != 1 or len(islands[0]) < 12:
        raise IslandCatalogueError('Expected exactly one full native island.')
    island = islands[0]
    x, y, width, height, unused_id = struct.unpack_from('<4HI', island)
    if x or y or not 0 < width <= 512 or not 0 < height <= 512:
        raise IslandCatalogueError('Island template origin or dimensions differ.')
    parts = list(_chunks(island, 12, len(island)))
    infos = [payload for tag, payload in parts if tag == b'INFO']
    if len(infos) != 1 or len(infos[0]) != 12 or infos[0][0] > 5:
        raise IslandCatalogueError('Island climate metadata differs.')
    heights = bytearray(width*height)
    seen = bytearray(width*height)
    for tag, tile in parts:
        if tag != b'HEIGHT':
            continue
        if len(tile) < 6:
            raise IslandCatalogueError('Truncated HEIGHT tile.')
        tx, ty, tw, th = struct.unpack_from('<HHBB', tile)
        if not tw or not th or tx+tw > width or ty+th > height or len(tile) != 6+tw*th:
            raise IslandCatalogueError('HEIGHT tile extents differ.')
        for yy in range(th):
            at = (ty+yy)*width+tx
            if any(seen[at:at+tw]):
                raise IslandCatalogueError('HEIGHT tiles overlap.')
            seen[at:at+tw] = bytes([1])*tw
            heights[at:at+tw] = tile[6+yy*tw:6+(yy+1)*tw]
    if not all(seen):
        raise IslandCatalogueError('HEIGHT tiles do not cover the island.')
    mask = bytes(value >= 0x30 for value in heights)
    rows = [mask[y*width:(y+1)*width] for y in range(height)]
    forms = []
    for mirror in (False, True):
        rotated = [row[::-1] for row in rows] if mirror else rows
        for unused_rotation in range(4):
            forms.append(struct.pack('<HH', len(rotated[0]), len(rotated)) + b''.join(rotated))
            rotated = [bytes(row) for row in zip(*rotated[::-1])]
    prefix = struct.pack('<HH', width, height)
    return dict(width=width, height=height, climate=infos[0][0], land_cells=sum(mask),
                height_sha256=_sha(prefix+heights), coast_sha256=_sha(prefix+mask),
                shape_sha256=_sha(min(forms)))


def catalogue_rows(catalogue: bytes) -> list[dict]:
    if not isinstance(catalogue, bytes) or _sha(catalogue) != CATALOGUE_SHA256:
        raise IslandCatalogueError('Island catalogue is not the exact reviewed input.')
    rows = []
    for index, (raw_path, raw_fields, raw_digest) in enumerate(_ROW.findall(catalogue.replace(b'\r\n', b'\n'))):
        path = raw_path.decode('ascii').replace('\\\\', '\\')
        relative = PureWindowsPath(path)
        fields = list(map(int, raw_fields.split(b',')))
        digest = bytes(map(int, raw_digest.split(b','))).hex()
        if (relative.is_absolute() or relative.drive or '..' in relative.parts or
                relative.suffix.lower() != '.scp' or len(digest) != 64):
            raise IslandCatalogueError('Island catalogue path or digest differs.')
        rows.append(dict(index=index, path=relative.as_posix(), sha256=digest, fields=fields))
    if len(rows) != TEMPLATE_COUNT or len({r['sha256'] for r in rows}) != TEMPLATE_COUNT:
        raise IslandCatalogueError('Island catalogue count or content identities differ.')
    return rows


def derive_shape_ids(catalogue: bytes, read_template: Callable[[str], bytes]) -> dict:
    """Validate every island fingerprint and derive ordered, deterministic groups.

    The resolver receives a catalogue-relative path. Callers may resolve stock
    files in their checked host and private aliases in preserved package assets.
    It must not substitute an unverified shape merely because a path matches.
    """
    rows = catalogue_rows(catalogue)
    for row in rows:
        data = read_template(row['path'])
        if not isinstance(data, bytes) or _sha(data) != row['sha256']:
            raise IslandCatalogueError('Exact source island fingerprint differs: '+row['path'])
        shape = coastal_shape(data)
        if (shape['width'], shape['height'], shape['climate']) != tuple(row['fields'][:3]):
            raise IslandCatalogueError('Source geometry/climate differs from catalogue metadata.')
        row.update(shape)
    keys = sorted({row['shape_sha256'] for row in rows})
    if len(keys) != SHAPE_COUNT:
        raise IslandCatalogueError('Reviewed coastal shape census differs.')
    groups = {key: index for index, key in enumerate(keys)}
    ids = [groups[row['shape_sha256']] for row in rows]
    return dict(catalogue_sha256=CATALOGUE_SHA256, template_count=len(rows),
                unique_content_count=len({row['sha256'] for row in rows}),
                shape_count=len(keys), shape_ids=ids, templates=rows,
                game_executed=False, original_files_modified=False)


def shape_header(shape_ids: list[int]) -> bytes:
    if (len(shape_ids) != TEMPLATE_COUNT or any(type(value) is not int or not 0 <= value < SHAPE_COUNT for value in shape_ids)
            or set(shape_ids) != set(range(SHAPE_COUNT))):
        raise IslandCatalogueError('Coastal group identities are incomplete.')
    lines = ['/* Exact reviewed History Edition catalogue; coastal landmask (HEIGHT >= 48).',
             ' * Rotations and reflections share a group; resources and occupants do not define shape.',
             ' * Catalogue SHA256 '+CATALOGUE_SHA256+'. No native terrain bytes are embedded. */',
             '#ifndef WS_ISLAND_SHAPES_H', '#define WS_ISLAND_SHAPES_H',
             'static const uint16_t wsTemplateShapeIds[444] = {']
    lines += [' '+','.join(map(str, shape_ids[at:at+24]))+',' for at in range(0, len(shape_ids), 24)]
    lines += ['};', '#define WS_TEMPLATE_SHAPE_COUNT 347u',
              '_Static_assert(sizeof wsTemplateShapeIds/sizeof wsTemplateShapeIds[0]==WS_COUNT,"Island shape metadata count differs");',
              '#endif', '']
    return '\n'.join(lines).encode('ascii')


def validate_island_shapes(catalogue: bytes, header: bytes, read_template: Callable[[str], bytes]) -> dict:
    proof = derive_shape_ids(catalogue, read_template)
    if header != shape_header(proof['shape_ids']):
        raise IslandCatalogueError('Authored coastal shape metadata differs from source islands.')
    proof['shape_header_sha256'] = _sha(header)
    return proof


def template_resolver(*roots: Path) -> Callable[[str], bytes]:
    """Resolve only explicit directories; digest validation remains mandatory."""
    bases = tuple(Path(root).resolve(strict=True) for root in roots)
    def read(relative: str) -> bytes:
        path = PureWindowsPath(relative)
        if path.is_absolute() or path.drive or '..' in path.parts:
            raise IslandCatalogueError('Island path leaves its explicit source roots.')
        for base in bases:
            candidate = base.joinpath(*path.parts)
            if candidate.is_file():
                if candidate.is_symlink() or not candidate.resolve(strict=True).is_relative_to(base):
                    raise IslandCatalogueError('Island source redirects outside its explicit root.')
                return candidate.read_bytes()
        raise IslandCatalogueError('Exact island source is unavailable: '+relative)
    return read
