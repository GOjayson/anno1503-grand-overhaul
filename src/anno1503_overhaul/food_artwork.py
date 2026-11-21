"""Food 0.6 native icon composition from the player's own consumer artwork.

No Ubisoft pixels are shipped with this module.  The shared background and the
two summary icons are derived from the checked stock UI at preparation time.
Only the existing authored food foregrounds are redistributed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct


class FoodArtworkError(ValueError):
    """The native inputs cannot be composed without changing unrelated art."""


SUMMARY_ACCESS = "OVERHAUL_FOOD_SUMMARY"
SUMMARY_GREY_ACCESS = "OVERHAUL_FOOD_SUMMARY_GREY"
FOOD_SLOTS = {
    "fish": ("WARENICONS_BEDARF", 0),
    "game-meat": ("WARENICONS_ROHSTOFF", 21),
    "potatoes": ("WARENICONS_BEDARF", 14),
    "bread": ("WARENICONS_ROHSTOFF", 22),
    "butcher-meat": ("WARENICONS_BAUMATERIAL", 4),
}
ASSET_SHA256 = {
    "fish": "8e135b6f941708038f2271f7b711c1936da0f5f4659d552f642ec911e90592da",
    "game-meat": "7eefdb6bc8a655af9df48b3d62595916d757e3e66c4e0ef2a77528bc440e2c16",
    "potatoes": "91076c41749d3d414c772a041886b614a9a141e2d7e051eddde01bc3790ba6c3",
    "bread": "e9a04141a2ff977a1a7de75b100b1a324be6463b83fc8afe6612a6644ddfeb24",
    "butcher-meat": "6c6f526e2f7780869c3d491afadf95f67426e29bca333b443596d7e1bc68e496",
}
# Authored coordinates describe the commodity silhouettes, not native artwork.
# Hue checks within these bounds remove the generated green background as well
# as its generated frame.  The native frame is never recolored or resampled.
_BOUNDS = {
    "fish": ((45, 3), (47, 7), (43, 15), (41, 24), (34, 30),
             (27, 34), (18, 40), (9, 45), (3, 45), (2, 38),
             (9, 30), (15, 24), (23, 20), (32, 14), (41, 9)),
    "game-meat": ((7, 25), (26, 14), (33, 11), (37, 7), (39, 3),
                  (44, 3), (46, 8), (41, 13), (38, 18), (34, 24),
                  (32, 36), (25, 45), (18, 46), (10, 42), (3, 35)),
    "potatoes": ((4, 18), (10, 9), (21, 6), (28, 8), (32, 12),
                 (40, 14), (45, 22), (47, 31), (43, 38), (35, 43),
                 (23, 44), (14, 41), (10, 34), (6, 29), (3, 23)),
    "bread": ((5, 25), (14, 13), (25, 6), (35, 4), (42, 7),
              (45, 13), (45, 22), (41, 31), (32, 39), (20, 44),
              (12, 45), (4, 40), (3, 33)),
    "butcher-meat": ((7, 18), (24, 13), (33, 11), (37, 4),
                     (43, 3), (47, 8), (45, 15), (43, 19),
                     (43, 28), (39, 36), (32, 42), (25, 44),
                     (17, 42), (8, 36), (3, 29), (3, 22)),
}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _chunk(tag, payload):
    return tag.encode("ascii").ljust(12, b"\0") + struct.pack("<I", len(payload)) + payload


def _chunks(data, start=16):
    position = start
    while position < len(data):
        if position + 16 > len(data):
            raise FoodArtworkError("Truncated native chunk header.")
        tag = data[position:position + 12]
        if not re.fullmatch(rb"[A-Z0-9_]{1,12}\x00*", tag):
            raise FoodArtworkError("Invalid native chunk name.")
        end = position + 16 + struct.unpack_from("<I", data, position + 12)[0]
        if end > len(data):
            raise FoodArtworkError("Native chunk leaves its parent.")
        yield tag.rstrip(b"\0").decode("ascii"), position, end
        position = end


def _root(data):
    if (len(data) < 16 or data[:12] != b"ANNO".ljust(12, b"\0")
            or struct.unpack_from("<I", data, 12)[0] != len(data) - 16):
        raise FoodArtworkError("Invalid native UI container.")


def _access(data):
    _root(data)
    parts = list(_chunks(data))
    if len(parts) != 1 or parts[0][0] != "ACCESS":
        raise FoodArtworkError("Expected one native ACCESS table.")
    entries = []
    for item in data[parts[0][1] + 16:parts[0][2]].split(b"\0"):
        if not item:
            continue
        match = re.fullmatch(rb"([A-Za-z0-9_]+),([0-9]+)", item)
        if not match:
            raise FoodArtworkError("Invalid native ACCESS entry.")
        entries.append((match[1].decode("ascii"), int(match[2])))
    if len(dict(entries)) != len(entries):
        raise FoodArtworkError("Duplicate native ACCESS name.")
    return entries


def _frames(data):
    _root(data)
    result = {}
    for tag, a, b in _chunks(data):
        if tag != "TEXTURE":
            continue
        if b - a < 24:
            raise FoodArtworkError("Truncated native texture.")
        ident = struct.unpack_from("<I", data, a + 20)[0]
        if ident in result:
            raise FoodArtworkError("Duplicate native texture identifier.")
        result[ident] = data[a:b]
    return result


def _parts(frame):
    result = {}
    for tag, a, b in _chunks(frame, 24):
        if tag in result:
            raise FoodArtworkError("Duplicate native texture field.")
        result[tag] = frame[a + 16:b]
    head = result.get("HEAD", b"")
    if len(head) < 8 or struct.unpack_from("<H", head, 6)[0] != 8:
        raise FoodArtworkError("Expected an indexed native icon.")
    return result


def _palette(data, ident):
    found = []
    for tag, a, b in _chunks(data):
        if tag == "COLOR" and b - a >= 24 and struct.unpack_from("<I", data, a + 20)[0] == ident:
            parts = list(_chunks(data[a:b], 24))
            bodies = [data[a + c + 16:a + d] for name, c, d in parts if name == "BODY"]
            if len(bodies) != 1 or len(bodies[0]) != 1024:
                raise FoodArtworkError("Invalid native palette.")
            found.append(bodies[0])
    if len(found) != 1:
        raise FoodArtworkError("Native palette is missing or duplicated.")
    raw = found[0]
    return raw, [(raw[n + 2], raw[n + 1], raw[n]) for n in range(0, 1024, 4)]


def _decode(frame, *, additional_sizes=()):
    parts = _parts(frame)
    width, height = struct.unpack_from("<HH", parts["HEAD"])
    if ((width, height) not in ((50, 50), (39, 39), (40, 39))
            and (width, height) not in additional_sizes):
        raise FoodArtworkError("Unsupported native commodity icon dimensions.")
    body = parts.get("BODY", b"")
    pixels = [-1] * (width * height)
    pos = 0
    for y in range(height):
        x = 0
        while True:
            if pos >= len(body):
                raise FoodArtworkError("Truncated native icon scanline.")
            skip = body[pos]
            pos += 1
            if skip >= 254:
                if skip == 255:
                    if pos != len(body):
                        raise FoodArtworkError("Trailing native icon pixels.")
                    return width, height, pixels
                break
            if pos >= len(body):
                raise FoodArtworkError("Truncated native icon run.")
            count = body[pos]
            pos += 1
            x += skip
            if x + count > width or pos + count > len(body):
                raise FoodArtworkError("Native icon run leaves its scanline.")
            pixels[y * width + x:y * width + x + count] = body[pos:pos + count]
            pos += count
            x += count
    raise FoodArtworkError("Native icon is missing its terminator.")


def _encode(width, height, pixels):
    body = bytearray()
    for y in range(height):
        x = 0
        row = pixels[y * width:(y + 1) * width]
        while x < width:
            first = x
            while x < width and row[x] < 0:
                x += 1
            skip = x - first
            if x == width:
                break
            first = x
            while x < width and row[x] >= 0:
                x += 1
            run = row[first:x]
            body.extend((skip, len(run)))
            body.extend(run)
        body.append(255 if y == height - 1 else 254)
    return bytes(body)


def _replace_body(frame, pixels, palette_id=None, *, additional_sizes=()):
    width, height, _ = _decode(frame, additional_sizes=additional_sizes)
    body = _encode(width, height, pixels)
    parts = []
    for tag, a, b in _chunks(frame, 24):
        if tag == "BODY":
            parts.append(_chunk("BODY", body))
        elif tag == "HEAD" and palette_id is not None:
            head = bytearray(frame[a + 16:b])
            struct.pack_into("<H", head, 4, palette_id)
            parts.append(_chunk("HEAD", bytes(head)))
        else:
            parts.append(frame[a:b])
    payload = frame[16:24] + b"".join(parts)
    result = _chunk("TEXTURE", payload)
    if _decode(result, additional_sizes=additional_sizes) != (width, height, pixels):
        raise FoodArtworkError("Native icon composition failed its roundtrip.")
    return result


def _identify(frame, ident):
    result = bytearray(frame)
    struct.pack_into("<I", result, 20, ident)
    return bytes(result)


def _plate(frames, first, palette):
    """Repeat a clean native Food background patch inside its exact frame.

    Commodity icons do not share a stored blank consumer tile.  Sampling the
    known clean upper-right background of the original Food icon avoids both
    generated green backdrops and fragments of another commodity.  Reflected
    repetition joins patch edges without introducing new palette colors.
    """
    width, height, original = _decode(frames[first])
    sources = [original]
    left, right = 34 * width // 50, 46 * width // 50
    top, bottom = 4 * height // 50, 15 * height // 50
    patch = [original[y * width + x] for y in range(top, bottom) for x in range(left, right)]
    if (not patch or any(value < 0 for value in patch)
            or any(not (green >= red + 4 and green >= blue - 4
                        and 40 <= green <= 200 and max(rgb) - min(rgb) <= 80)
                   for value in patch for rgb in (palette[value],)
                   for red, green, blue in (rgb,))):
        raise FoodArtworkError("The checked native Food background patch changed.")

    def reflected(position, size):
        position %= size * 2
        return position if position < size else size * 2 - position - 1

    donors = []
    result = original[:]
    border = max(1, (3 * width) // 50)
    for n, value in enumerate(original):
        x, y = n % width, n // width
        if min(x, y, width - x - 1, height - y - 1) < border or value < 0:
            donors.append((0, n))
            continue
        source = (top + reflected(y - border, bottom - top)) * width + left + reflected(x - border, right - left)
        result[n] = original[source]
        donors.append((0, source))
    return width, height, result, donors, sources


def _inside(x, y, points):
    inside = False
    previous = points[-1]
    for current in points:
        ax, ay = previous
        bx, by = current
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
        previous = current
    return inside


def _foreground(name, asset):
    points = _BOUNDS[name]
    mask = []
    for y in range(50):
        for x in range(50):
            red, green, blue = asset["palette"][asset["pixels"][y * 50 + x]]
            if name == "fish":
                commodity = blue >= green - 4 or red > green + 3
            else:
                commodity = red > green + 2
            mask.append(_inside(x + .5, y + .5, points) and commodity)
    if sum(mask) < 100:
        raise FoodArtworkError("Authored commodity foreground is unexpectedly empty: " + name)
    return mask


def load_assets(folder=None):
    """Load only the five pinned, original authored JSON assets."""
    if folder is None:
        candidates = [Path(__file__).resolve().parents[1] / "assets",
                      Path(__file__).resolve().parents[2] / "legacy/food_overhaul/assets"]
        folder = next((p for p in candidates if (p / "fish_icon.json").is_file()), None)
    if folder is None:
        raise FoodArtworkError("The preserved Food artwork is unavailable.")
    result = {}
    for name, digest in ASSET_SHA256.items():
        raw = (Path(folder) / (name.replace("-", "_") + "_icon.json")).read_bytes()
        if _sha(raw) != digest:
            raise FoodArtworkError("The preserved Food artwork changed: " + name)
        item = json.loads(raw)
        palette = bytes.fromhex(item["palette_bgra"])
        result[name] = dict(width=item["width"], height=item["height"],
                            pixels=bytes.fromhex(item["pixels"]),
                            palette=[(palette[n + 2], palette[n + 1], palette[n])
                                     for n in range(0, len(palette), 4)])
    return result


def transform(stock_index, stock_tex, food05_index, food05_tex, assets=None):
    """Compose Food icons and add byte-preserved, non-good summary sprites.

    The caller must first authenticate whole stock and Food 0.5 inputs against
    its reviewed installation recipe.  Structural, palette and unchanged-frame
    proofs here are additional checks, not replacement compatibility checks.
    """
    assets = load_assets() if assets is None else assets
    for name in FOOD_SLOTS:
        asset = assets.get(name, {})
        if ((asset.get("width"), asset.get("height")) != (50, 50)
                or len(asset.get("pixels", b"")) != 2500
                or len(asset.get("palette", [])) != 256
                or any(not isinstance(v, int) or not 0 <= v <= 255
                       for rgb in asset["palette"] for v in rgb)):
            raise FoodArtworkError("Invalid authored commodity source: " + name)
    stock_access, target_entries = dict(_access(stock_index)), _access(food05_index)
    target_access = dict(target_entries)
    for values, counts in ((stock_access, (21, 14, 4)), (target_access, (23, 15, 5))):
        for group, count in zip(("WARENICONS_ROHSTOFF", "WARENICONS_BEDARF", "WARENICONS_BAUMATERIAL"), counts):
            if values.get(group + "_GREY", 0) - values.get(group, 0) != count:
                raise FoodArtworkError("Unexpected native commodity group layout.")
    if SUMMARY_ACCESS in target_access or SUMMARY_GREY_ACCESS in target_access:
        raise FoodArtworkError("Food summary icons are already present.")
    original, current = _frames(stock_tex), _frames(food05_tex)
    first = stock_access["WARENICONS_BEDARF"]
    head = _parts(original[first])["HEAD"]
    palette_id = struct.unpack_from("<H", head, 4)[0]
    palette_bytes, palette = _palette(stock_tex, palette_id)
    if _palette(food05_tex, palette_id)[0] != palette_bytes:
        raise FoodArtworkError("Stock and Food palettes differ; byte-exact summary copy is unsafe.")
    width, height, colour_plate, donors, sources = _plate(original, first, palette)
    grey_first = stock_access["WARENICONS_BEDARF_GREY"]
    grey_palette_id = struct.unpack_from("<H", _parts(original[grey_first])["HEAD"], 4)[0]
    grey_palette_bytes, grey_palette = _palette(stock_tex, grey_palette_id)
    if _palette(food05_tex, grey_palette_id)[0] != grey_palette_bytes:
        raise FoodArtworkError("Stock and Food disabled palettes differ.")
    grey_sources = [_decode(original[grey_first])[2]]
    grey_plate = [grey_sources[i][n] for i, n in donors]
    masks = {name: _foreground(name, assets[name]) for name in FOOD_SLOTS}
    replacements, proof_icons = {}, {}
    for name, (group, ordinal) in FOOD_SLOTS.items():
        asset = assets[name]
        mapping = {}
        for grey in (False, True):
            ident = target_access[group + ("_GREY" if grey else "")] + ordinal
            frame = current[ident]
            tw, th, _ = _decode(frame)
            if (tw, th) != (width, height):
                raise FoodArtworkError("Food icon no longer has its native consumer dimensions.")
            target_palette_id = struct.unpack_from("<H", _parts(frame)["HEAD"], 4)[0]
            # Reclassified raw/material foods originally referenced another
            # native palette.  Point these five icons at the intact native
            # consumer palette; do not change or invent any palette pixels.
            _palette(food05_tex, target_palette_id)
            selected_palette_id = grey_palette_id if grey else palette_id
            selected_palette = grey_palette if grey else palette
            plate = grey_plate if grey else colour_plate
            pixels = plate[:]
            mask = []
            for y in range(height):
                for x in range(width):
                    source = min(49, y * 50 // height) * 50 + min(49, x * 50 // width)
                    visible = masks[name][source]
                    mask.append(visible)
                    if not visible:
                        continue
                    old = asset["pixels"][source]
                    if old not in mapping or mapping[old][0] != grey:
                        red, green, blue = asset["palette"][old]
                        if grey:
                            red = green = blue = (77 * red + 150 * green + 29 * blue + 128) // 256
                        nearest = min(range(256), key=lambda p: (2 * (selected_palette[p][0] - red) ** 2
                                      + 4 * (selected_palette[p][1] - green) ** 2 + (selected_palette[p][2] - blue) ** 2, p))
                        mapping[old] = (grey, nearest)
                    pixels[y * width + x] = mapping[old][1]
            replacements[ident] = _replace_body(frame, pixels, selected_palette_id)
            if any(pixels[n] != plate[n] for n, foreground in enumerate(mask) if not foreground):
                raise FoodArtworkError("A food background left the shared native plate.")
            proof_icons[name + ("-grey" if grey else "")] = dict(
                texture_id=ident, foreground_pixels=sum(mask), background_pixels=len(mask) - sum(mask),
                background_matches_native_plate=True, dimensions=[width, height],
                palette_id=selected_palette_id,
                frame_sha256=_sha(replacements[ident]))
    next_id = max(current) + 1
    additions = []
    summaries = {}
    for offset, (access_name, original_id) in enumerate(((SUMMARY_ACCESS, first), (SUMMARY_GREY_ACCESS, grey_first))):
        ident = next_id + offset
        frame = original[original_id]
        original_palette_id = struct.unpack_from("<H", _parts(frame)["HEAD"], 4)[0]
        if _palette(stock_tex, original_palette_id)[0] != _palette(food05_tex, original_palette_id)[0]:
            raise FoodArtworkError("Summary icon palette changed.")
        added = _identify(frame, ident)
        if _identify(added, original_id) != frame:
            raise FoodArtworkError("Summary icon is not an exact original Food copy.")
        additions.append(added)
        target_entries.append((access_name, ident))
        summaries[access_name] = dict(texture_id=ident, stock_texture_id=original_id,
                                     stock_frame_sha256=_sha(frame), frame_sha256=_sha(added),
                                     palette_id=original_palette_id, palette_unchanged=True,
                                     original_payload_preserved=True)
    texture = _chunk("ANNO", b"".join(
        replacements.get(struct.unpack_from("<I", food05_tex, a + 20)[0], food05_tex[a:b])
        if tag == "TEXTURE" else food05_tex[a:b] for tag, a, b in _chunks(food05_tex)) + b"".join(additions))
    index = _chunk("ANNO", _chunk("ACCESS", b"".join(
        f"{name},{ident}".encode("ascii") + b"\0" for name, ident in target_entries)))
    after = _frames(texture)
    if any(after[ident] != frame for ident, frame in current.items() if ident not in replacements):
        raise FoodArtworkError("Food composition changed an unrelated native sprite.")
    proof = dict(version="0.6.0", dimensions=[width, height], icons=proof_icons,
                 summary=summaries, native_palette_sha256=_sha(palette_bytes),
                 native_grey_palette_sha256=_sha(grey_palette_bytes),
                 colour_plate_sha256=_sha(struct.pack("<" + "h" * len(colour_plate), *colour_plate)),
                 grey_plate_sha256=_sha(struct.pack("<" + "h" * len(grey_plate), *grey_plate)),
                 stock_index_sha256=_sha(stock_index), stock_texture_sha256=_sha(stock_tex),
                 input_index_sha256=_sha(food05_index), input_texture_sha256=_sha(food05_tex),
                 output_index_sha256=_sha(index), output_texture_sha256=_sha(texture),
                 native_background_derived_locally=True, unrelated_sprites_preserved=True,
                 summary_is_traded_good=False)
    return index, texture, proof
