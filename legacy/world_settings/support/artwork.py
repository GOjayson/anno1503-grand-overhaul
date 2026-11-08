"""Encode each commodity's colour and disabled artwork in every native UI pair."""
import json
from pathlib import Path
import struct
import formats as fm

ICON_SLOTS = {
    'fish': ('WARENICONS_BEDARF', 0),
    'game-meat': ('WARENICONS_ROHSTOFF', 21),
    'potatoes': ('WARENICONS_BEDARF', 14),
    'bread': ('WARENICONS_ROHSTOFF', 22),
    'butcher-meat': ('WARENICONS_BAUMATERIAL', 4),
}


def load_assets(package: Path, hashes):
    assets = {}
    for name in ICON_SLOTS:
        data = (package / 'assets' / (name.replace('-', '_') + '_icon.json')).read_bytes()
        if fm.sha(data) != hashes[name]:
            raise fm.ModError('Food artwork is missing or changed: ' + name)
        item = json.loads(data)
        width, height = item['width'], item['height']
        palette = bytes.fromhex(item['palette_bgra'])
        pixels = bytes.fromhex(item['pixels'])
        if (item.get('format') != 'anno1503-indexed-icon-v1' or (width, height) != (50, 50)
                or len(palette) != 1024 or len(pixels) != width * height):
            raise fm.ModError('Invalid food artwork: ' + name)
        assets[name] = dict(width=width, height=height, pixels=pixels,
            palette=[(palette[i+2], palette[i+1], palette[i]) for i in range(0, 1024, 4)])
    return assets


def paint(index, textures, assets):
    access = dict(fm.read_access(index))
    if (access['WARENICONS_ROHSTOFF_GREY'] - access['WARENICONS_ROHSTOFF'] != 23
            or access['WARENICONS_BEDARF_GREY'] - access['WARENICONS_BEDARF'] != 15
            or access['WARENICONS_BAUMATERIAL_GREY'] - access['WARENICONS_BAUMATERIAL'] != 5):
        raise fm.ModError('The final food artwork needs 23 raw, 15 consumer and 5 material slots')
    frames = fm.texture_frames(textures)
    replacements = {}
    for name, (group, ordinal) in ICON_SLOTS.items():
        for suffix, grey in [('', False), ('_GREY', True)]:
            ident = access[group + suffix] + ordinal
            frame = frames[ident]
            head = {tag: frame[a+16:b] for tag, a, b in fm.anno_chunks(frame, 24)}['HEAD']
            palette = fm.read_palette(textures, struct.unpack_from('<H', head, 4)[0])
            replacements[ident] = fm.reidentify_texture(
                fm.fish_frame(frame, palette, assets[name], grey), ident)
    parts = []
    for tag, a, b in fm.anno_chunks(textures):
        ident = struct.unpack_from('<I', textures, a+20)[0] if tag == 'TEXTURE' else None
        parts.append(replacements.get(ident, textures[a:b]))
    result = fm.make_chunk('ANNO', b''.join(parts))
    after = fm.texture_frames(result)
    if set(after) != set(frames) or any(after[i] != frame for i, frame in frames.items() if i not in replacements):
        raise fm.ModError('Food artwork changed an unrelated sprite')
    return result
