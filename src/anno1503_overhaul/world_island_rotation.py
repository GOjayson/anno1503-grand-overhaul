"""Read-only reference codec for verified, uninhabited History Edition islands.

Terrain HEIGHT values describe vertices; other grids describe cells. Native
islands and definitions are inputs, never outputs of this module's file I/O.
The in-game runtime uses the independently tested C implementation.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import re
import struct

from .world_island_catalogue import IslandCatalogueError, _chunks, catalogue_rows


class IslandRotationError(IslandCatalogueError):
    pass


def dimension_header(dimensions, used):
    lines = ['/* Exact dimensions of the 281 landscape definitions used by rotatable templates.',
             ' * Independently equal in stock/Food and base/addon definitions. No texture data. */',
             '#ifndef WS_ISLAND_ROTATION_DEFINITIONS_H','#define WS_ISLAND_ROTATION_DEFINITIONS_H',
             'static const uint16_t wsRotationDimensions[4096]={']
    for ident in sorted(used):
        w,h = dimensions[ident]
        if not 0 <= ident < 4096 or not 0 < w <= 255 or not 0 < h <= 255:
            raise IslandRotationError('Unsupported landscape dimensions.')
        lines.append(' [%d]=%du,' % (ident,w|(h<<8)))
    return ('\n'.join(lines+['};','#endif',''])).encode('ascii')


def validate_rotation_metadata(catalogue, plan_header, dimensions_header, read_template, variants):
    rows = catalogue_rows(catalogue)
    eligible, used, ordinary = [], set(), 0
    for row in rows:
        data = read_template(row['path'])
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise IslandRotationError('Island rotation source fingerprint differs.')
        end = 16+struct.unpack_from('<I',data,12)[0]
        top = list(_chunks(data,16,end))
        full = [p for t,p in top if t == b'INSEL5']
        parts = list(_chunks(full[0],12,len(full[0]))) if len(full)==1 else []
        enabled = (not row['fields'][3] and not row['fields'][6] and row['fields'][0]==row['fields'][1]
                   and len(full)==1 and set(t for t,p in top)=={b'WARETYPE',b'INSEL5'}
                   and set(t for t,p in parts)<={b'INFO',b'HEIGHT',b'GFXID',b'GELAENDE',b'FRUCHTBAR',b'FLUESSE',b'BERGWERK2',b'OCCUR',b'ANBAU'})
        if enabled:
            ordinary += 1
            for tag,p in parts:
                if tag in (b'GELAENDE',b'FLUESSE'):
                    if len(p)<6 or (len(p)-6)%6:
                        raise IslandRotationError('Partial landscape record.')
                    used.update(struct.unpack_from('<H',p,i)[0]&16383 for i in range(6,len(p),6))
            # Native saves serialize N x N heights. A rotation can move the
            # first row/column to the omitted padded end boundary. Preserve
            # every nonzero edge by leaving these templates unrotated.
            n = row['fields'][0]
            grid = _grid(parts, b'HEIGHT', n, n, 1)
            enabled = not any(grid[:n]) and not any(grid[::n])
        eligible.append(int(enabled))
    values = re.search(rb'wsTemplateCanRotate\[444\]\s*=\s*\{([^}]+)\}',plan_header)
    if values is None or [int(v) for v in re.findall(rb'\d+',values[1])] != eligible or sum(eligible)!=256 or ordinary!=269 or len(used)!=281:
        raise IslandRotationError('The reviewed ordinary rotation whitelist differs.')
    if not variants or any(any(v.get(ident)!=variants[0].get(ident) for ident in used) for v in variants):
        raise IslandRotationError('Landscape dimensions differ between selected native inputs.')
    if dimensions_header != dimension_header(variants[0],used):
        raise IslandRotationError('Landscape rotation metadata differs from the selected game data.')
    return dict(template_count=444,ordinary_templates=269,rotatable_templates=256,
                nonzero_boundary_templates_retained_unrotated=13,landscape_definitions=281,
                plan_header_sha256=hashlib.sha256(plan_header).hexdigest(),
                definition_header_sha256=hashlib.sha256(dimensions_header).hexdigest(),
                original_files_modified=False,game_executed=False)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return tag.ljust(12, b'\0') + struct.pack('<I', len(data)) + data


def definition_dimensions(path: Path) -> dict[int, tuple[int, int]]:
    """Read bounded Anlagen definitions, leaving its large texture data unread."""
    with path.open('rb') as stream:
        head = stream.read(16)
        if len(head) != 16 or head[:12] != b'ANNO'.ljust(12, b'\0'):
            raise IslandRotationError('Unsupported landscape definition container.')
        end = struct.unpack_from('<I', head, 12)[0] + 16
        if end != path.stat().st_size:
            raise IslandRotationError('Landscape definition envelope differs.')
        at, body = 16, None
        while at < end:
            stream.seek(at); h = stream.read(16)
            if len(h) != 16:
                raise IslandRotationError('Truncated landscape definition chunk.')
            n = struct.unpack_from('<I', h, 12)[0]
            if n > end-at-16:
                raise IslandRotationError('Landscape definition chunk exceeds its parent.')
            if h[:12] == b'ANLAGEN'.ljust(12, b'\0'):
                if body is not None or n > 8*1024*1024:
                    raise IslandRotationError('Landscape definitions are duplicated or unbounded.')
                body = stream.read(n)
            at += 16+n
    if body is None:
        raise IslandRotationError('Missing landscape definitions.')
    result = {}
    for tag, entry in _chunks(body, 0, len(body)):
        if tag != b'ENTRY' or len(entry) < 8:
            raise IslandRotationError('Invalid landscape definition entry.')
        ident = struct.unpack_from('<I', entry, 4)[0]
        fields = list(_chunks(entry, 8, len(entry)))
        heads = [v for t,v in fields if t == b'HEAD']
        if ident in result or len(heads) != 1 or len(heads[0]) not in (36,44,48,52,56):
            raise IslandRotationError('Invalid landscape definition identity or dimensions.')
        result[ident] = tuple(heads[0][:2])
    return result


def _point(x, y, width, height, turns):
    for unused in range(turns):
        x, y, width, height = height-y, x, height, width
    return x, y


def _box(x, y, w, h, width, height, turns):
    for unused in range(turns):
        x, y, w, h, width, height = height-y-h, x, h, w, height, width
    return x, y, w, h


def _grid(parts, tag, width, height, stride):
    out, seen = bytearray(width*height*stride), bytearray(width*height)
    for name, payload in parts:
        if name != tag:
            continue
        if len(payload) < 6:
            raise IslandRotationError('Truncated island grid.')
        x,y,w,h = struct.unpack_from('<HHBB', payload)
        if not w or not h or x+w > width or y+h > height or len(payload) != 6+w*h*stride:
            raise IslandRotationError('Island grid extents differ.')
        for row in range(h):
            at = (y+row)*width+x
            if any(seen[at:at+w]):
                raise IslandRotationError('Island grid tiles overlap.')
            seen[at:at+w] = bytes([1])*w
            out[at*stride:(at+w)*stride] = payload[6+row*w*stride:6+(row+1)*w*stride]
    if not all(seen):
        raise IslandRotationError('Island grid is incomplete.')
    return out


def _rotate_grid(raw, width, height, stride, turns, *, vertex=False, graphics=False):
    dst = bytearray(len(raw))
    for y in range(height):
        for x in range(width):
            if vertex:
                nx,ny = _point(x,y,width-1,height-1,turns)
            else:
                nx,ny,unused_w,unused_h = _box(x,y,1,1,width,height,turns)
            a,b = (y*width+x)*stride,(ny*height+nx)*stride
            dst[b:b+stride] = raw[a:a+stride]
            if graphics:
                value = struct.unpack_from('<H', dst, b)[0]
                struct.pack_into('<H', dst, b, (value&~3)|((value-turns)&3))
    return bytes(dst)


def _tiles(tag, grid, width, height, stride):
    chunks = []
    for y in range(0,height,32):
        for x in range(0,width,32):
            w,h = min(32,width-x),min(32,height-y)
            rows = b''.join(grid[((y+row)*width+x)*stride:((y+row)*width+x+w)*stride] for row in range(h))
            chunks.append(_chunk(tag,struct.pack('<HHBB',x,y,w,h)+rows))
    return b''.join(chunks)


def rotate_island(data: bytes, turns: int, dimensions: dict[int,tuple[int,int]]) -> bytes:
    """Return one bounded derivative; no paths are opened or written here."""
    if type(turns) is not int or not 0 <= turns <= 3 or not isinstance(data,bytes) or not 32 <= len(data) <= 64*1024*1024:
        raise IslandRotationError('Invalid island rotation input.')
    end = 16 + struct.unpack_from('<I',data,12)[0]
    if data[:12].rstrip(b'\0') not in (b'ANNO',b'ANNOADDON1') or end > len(data):
        raise IslandRotationError('Unsupported island envelope.')
    top = list(_chunks(data,16,end))
    if [t for t,p in top].count(b'INSEL5') != 1 or set(t for t,p in top) != {b'WARETYPE',b'INSEL5'}:
        raise IslandRotationError('Only verified ordinary island containers can rotate.')
    island = next(p for t,p in top if t == b'INSEL5')
    if len(island) < 12:
        raise IslandRotationError('Truncated island geometry.')
    x,y,w,h,ident = struct.unpack_from('<4HI',island)
    if x or y or w != h or w not in (64,80,96,128,160,256):
        raise IslandRotationError('Rotation needs a verified square island.')
    parts = list(_chunks(island,12,len(island)))
    allowed = {b'INFO',b'HEIGHT',b'GFXID',b'GELAENDE',b'FRUCHTBAR',b'FLUESSE',b'BERGWERK2',b'OCCUR',b'ANBAU'}
    if any(t not in allowed for t,p in parts):
        raise IslandRotationError('Inhabited or scripted islands cannot rotate.')
    for singleton in (b'INFO',b'FRUCHTBAR',b'ANBAU'):
        if sum(t == singleton for t,p in parts) != 1:
            raise IslandRotationError('Missing or duplicated island metadata.')
    if turns == 0:
        return data
    heights = _grid(parts,b'HEIGHT',w,h,1)
    full = bytearray((w+1)*(h+1))
    for row in range(h):full[row*(w+1):row*(w+1)+w] = heights[row*w:(row+1)*w]
    heights = _rotate_grid(full,w+1,h+1,1,turns,vertex=True)
    graphics = _rotate_grid(_grid(parts,b'GFXID',w,h,2),w,h,2,turns,graphics=True)
    emitted, output = set(), []
    for tag,payload in parts:
        if tag in (b'HEIGHT',b'GFXID'):
            if tag not in emitted:
                output.append(_tiles(tag,heights if tag == b'HEIGHT' else graphics,w+1 if tag == b'HEIGHT' else w,h+1 if tag == b'HEIGHT' else h,1 if tag == b'HEIGHT' else 2))
                emitted.add(tag)
            continue
        raw = bytearray(payload)
        if tag == b'FRUCHTBAR':
            if len(raw) != w*h:
                raise IslandRotationError('Island fertility grid differs.')
            raw = _rotate_grid(raw,w,h,1,turns)
        elif tag in (b'GELAENDE',b'FLUESSE'):
            if len(raw) < 6 or (len(raw)-6)%6:
                raise IslandRotationError('Partial landscape placement record.')
            ox,oy,tw,th = struct.unpack_from('<HHBB',raw)
            if not tw or not th or ox+tw>w or oy+th>h:
                raise IslandRotationError('Landscape placement tile exceeds its island.')
            tx,ty,nw,nh = _box(ox,oy,tw,th,w,h,turns)
            struct.pack_into('<HHBB',raw,0,tx,ty,nw,nh)
            for at in range(6,len(raw),6):
                packed,flags,stage,dx,dy = struct.unpack_from('<HBBbb',raw,at)
                definition,orientation = packed&0x3fff,packed>>14
                dw,dh = dimensions.get(definition,(0,0))
                if orientation&1:dw,dh = dh,dw
                px,py = ox+dx,oy+dy
                if not dw or not dh or px<0 or py<0 or px+dw>w or py+dh>h:
                    raise IslandRotationError('Landscape footprint differs from its definition.')
                nx,ny,unused_w,unused_h = _box(px,py,dw,dh,w,h,turns)
                if not -128 <= nx-tx <=127 or not -128 <= ny-ty <=127:
                    raise IslandRotationError('Rotated landscape offset exceeds its native range.')
                struct.pack_into('<HBBbb',raw,at,definition|(((orientation+turns)&3)<<14),flags,stage,nx-tx,ny-ty)
        elif tag == b'BERGWERK2':
            if len(raw)%12:
                raise IslandRotationError('Partial mine placement record.')
            for at in range(0,len(raw),12):
                if raw[at:at+8] != b'ENTRY\0\x04\0':
                    raise IslandRotationError('Unknown mine placement record.')
                value = struct.unpack_from('<I',raw,at+8)[0]
                px,py,direction = value&4095,value>>12&4095,value>>24&3
                dw,dh = (4,3) if direction&1 else (3,4)
                if px+dw>w or py+dh>h:
                    raise IslandRotationError('Mine footprint exceeds its source island.')
                nx,ny,unused_w,unused_h = _box(px,py,dw,dh,w,h,turns)
                struct.pack_into('<I',raw,at+8,(value&0xfc000000)|nx|(ny<<12)|(((direction+turns)&3)<<24))
        elif tag == b'OCCUR':
            at = 0
            while at < len(raw):
                if len(raw)-at<8 or raw[at:at+6] != b'ENTRY2':
                    raise IslandRotationError('Unknown occurrence record.')
                size = struct.unpack_from('<H',raw,at+6)[0]
                if size<24 or at+8+size>len(raw):
                    raise IslandRotationError('Truncated occurrence payload.')
                start = at+8; definition = struct.unpack_from('<I',raw,start)[0]>>14&4095
                if definition not in (1559,1560,1561,1562,1563,1565) or (definition!=1559 and size!=24):
                    raise IslandRotationError('Unsupported occurrence type.')
                px,py,pz = struct.unpack_from('<3f',raw,start+4)
                if not all(math.isfinite(v) for v in (px,py,pz)) or not 0<=px<=w or not 0<=py<=h:
                    raise IslandRotationError('Occurrence coordinates exceed their source island.')
                nx,ny = _point(px,py,w,h,turns)
                struct.pack_into('<2f',raw,start+4,nx,ny)
                if definition==1559:
                    if raw[start+16:start+22]!=b'WHALE\0' or size-24!=struct.unpack_from('<H',raw,start+22)[0] or (size-24)%6:
                        raise IslandRotationError('Unsupported whale path transport.')
                    for p in range(start+24,start+size,6):
                        dx,dy = struct.unpack_from('<bb',raw,p+2)
                        for unused in range(turns):dx,dy = -dy,dx
                        if not -128<=dx<=127 or not -128<=dy<=127:
                            raise IslandRotationError('Whale path rotation exceeds signed native offsets.')
                        struct.pack_into('<bb',raw,p+2,dx,dy)
                at += 8+size
        output.append(_chunk(tag,bytes(raw)))
    rotated = island[:12]+b''.join(output)
    body = b''.join(_chunk(tag,rotated if tag == b'INSEL5' else payload) for tag,payload in top)
    return data[:12]+struct.pack('<I',len(body))+body+data[end:]
