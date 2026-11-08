"""Native container, icon and atomic-write helpers; Windows uses only the standard library."""
from __future__ import annotations
import hashlib,json,os,re,shutil,struct,tempfile
from pathlib import Path
from decimal import Decimal
FISH_GOOD="FISCH2"
class ModError(Exception): pass

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()

def safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ModError("A path leaves the game folder: " + relative) from exc
    return path

def anno_chunks(data: bytes, start: int = 16, end: int | None = None):
    end = len(data) if end is None else end
    position = start
    while position < end:
        if position + 16 > end:
            raise ModError("Incomplete ANNO chunk header")
        raw_tag = data[position:position + 12]
        if not re.fullmatch(rb"[A-Z0-9_]{1,12}\x00*", raw_tag):
            raise ModError("Invalid ANNO chunk name")
        tag = raw_tag.rstrip(b"\0").decode("ascii")
        length = struct.unpack_from("<I", data, position + 12)[0]
        following = position + 16 + length
        if following > end:
            raise ModError("ANNO chunk crosses its parent boundary")
        yield tag, position, following
        position = following

def check_anno_root(data: bytes):
    if data[:12] != b"ANNO".ljust(12, b"\0"):
        raise ModError("Not an ANNO container")
    if struct.unpack_from("<I", data, 12)[0] + 16 != len(data):
        raise ModError("ANNO container length does not match its header")

def make_chunk(tag: str, payload: bytes) -> bytes:
    return tag.encode("ascii").ljust(12, b"\0") + struct.pack("<I", len(payload)) + payload

def read_access(data: bytes) -> list[tuple[str, int]]:
    check_anno_root(data)
    parts = list(anno_chunks(data))
    if len(parts) != 1 or parts[0][0] != "ACCESS":
        raise ModError("Unsupported Fenster index layout")
    _, start, end = parts[0]
    items = []
    for value in data[start + 16:end].split(b"\0"):
        if not value:
            continue
        match = re.fullmatch(rb"([A-Za-z0-9_]+),([0-9]+)", value)
        if not match:
            raise ModError("Unsupported Fenster ACCESS entry")
        items.append((match[1].decode("ascii"), int(match[2])))
    if len(dict(items)) != len(items):
        raise ModError("Duplicate Fenster ACCESS name")
    return items

def texture_frames(data: bytes) -> dict[int, bytes]:
    check_anno_root(data)
    frames = {}
    for tag, start, end in anno_chunks(data):
        if tag != "TEXTURE":
            continue
        if end - start < 24:
            raise ModError("Incomplete TEXTURE entry")
        ident = struct.unpack_from("<I", data, start + 20)[0]
        if ident in frames:
            raise ModError("Duplicate texture ID")
        frames[ident] = data[start:end]
    return frames

def reidentify_texture(frame: bytes, ident: int) -> bytes:
    result = bytearray(frame)
    struct.pack_into("<I", result, 20, ident)
    return bytes(result)

def consumer_icon_dimensions(frame: bytes, ident: int) -> tuple[int, int]:
    parts = {}
    for tag, start, end in anno_chunks(frame, 24):
        if tag in {"HEAD", "BODY"}:
            if tag in parts:
                raise ModError(f"Consumer icon {ident} has duplicate {tag} chunks")
            parts[tag] = frame[start + 16:end]
    if len(parts.get("HEAD", b"")) < 4 or not parts.get("BODY"):
        raise ModError(f"Consumer icon {ident} is missing its header or image data")
    dimensions = struct.unpack_from("<HH", parts["HEAD"])
    if 0 in dimensions:
        raise ModError(f"Consumer icon {ident} has an invalid zero dimension: {dimensions[0]}x{dimensions[1]}")
    return dimensions

def read_palette(textures: bytes, ident: int):
    found = []
    for tag, start, end in anno_chunks(textures):
        if tag != "COLOR" or struct.unpack_from("<I", textures, start + 20)[0] != ident:
            continue
        bodies = [textures[a + 16:b] for kind, a, b in anno_chunks(textures, start + 24, end) if kind == "BODY"]
        if len(bodies) != 1 or len(bodies[0]) != 1024:
            raise ModError(f"Unsupported 8-bit colour table {ident}")
        data = bodies[0]
        found.append([(data[i + 2], data[i + 1], data[i]) for i in range(0, 1024, 4)])
    if len(found) != 1:
        raise ModError(f"Colour table {ident} is missing or duplicated")
    return found[0]

def decode_bsh8(frame: bytes):
    """Validate the game's 8-bit skip/run stream; return pixel indices (-1 = clear)."""
    parts = {tag: frame[start + 16:end] for tag, start, end in anno_chunks(frame, 24)}
    head, body = parts.get("HEAD", b""), parts.get("BODY", b"")
    if len(head) < 8 or struct.unpack_from("<H", head, 6)[0] != 8:
        raise ModError("Unsupported consumer icon pixel depth; expected native 8-bit pixels")
    width, height = struct.unpack_from("<HH", head)
    if not width or not height:
        raise ModError("Invalid zero-sized icon")
    pixels = [-1] * (width * height)
    position = 0
    for y in range(height):
        x = 0
        while True:
            if position >= len(body):
                raise ModError("Incomplete native icon pixel stream")
            skip = body[position]
            position += 1
            if skip >= 254:
                if skip == 255:
                    if position != len(body):
                        raise ModError("Unexpected bytes after native icon terminator")
                    return width, height, pixels
                break
            if position >= len(body):
                raise ModError("Incomplete native icon run")
            count = body[position]
            position += 1
            x += skip
            if x + count > width or position + count > len(body):
                raise ModError("Native icon run exceeds its image boundary")
            pixels[y * width + x:y * width + x + count] = body[position:position + count]
            position += count
            x += count
    if position != len(body):
        raise ModError("Unexpected trailing native icon data")
    return width, height, pixels

def encode_bsh8(width: int, height: int, pixels: bytes):
    if width <= 0 or height <= 0 or len(pixels) != width * height:
        raise ModError("Invalid native icon pixels")
    body = bytearray()
    for y in range(height):
        for x in range(0, width, 250):
            part = pixels[y * width + x:y * width + min(x + 250, width)]
            body.extend([0, len(part)])
            body.extend(part)
        body.append(255 if y == height - 1 else 254)
    return bytes(body)

def fish_frame(template: bytes, palette, asset, grey: bool):
    width, height, _ = decode_bsh8(template)
    mapped = []
    for red, green, blue in asset["palette"]:
        if grey:
            red = green = blue = (77 * red + 150 * green + 29 * blue + 128) // 256
        mapped.append(min(range(256), key=lambda i: 2 * (palette[i][0] - red) ** 2
                          + 4 * (palette[i][1] - green) ** 2 + (palette[i][2] - blue) ** 2))
    source_width, source_height = asset["width"], asset["height"]
    pixels = bytes(mapped[asset["pixels"][min(source_height - 1, y * source_height // height) * source_width
                                         + min(source_width - 1, x * source_width // width)]]
                   for y in range(height) for x in range(width))
    body = encode_bsh8(width, height, pixels)
    payload = bytearray(template[16:24])
    for tag, start, end in anno_chunks(template, 24):
        payload.extend(make_chunk("BODY", body) if tag == "BODY" else template[start:end])
    result = make_chunk("TEXTURE", bytes(payload))
    if decode_bsh8(result) != (width, height, list(pixels)):
        raise ModError("Fish icon encoder validation failed")
    return result

def paint_fish_icons(index: bytes, textures: bytes, asset):
    access = dict(read_access(index))
    colour, grey, materials = (access[name] for name in ["WARENICONS_BEDARF", "WARENICONS_BEDARF_GREY",
                                                       "WARENICONS_BAUMATERIAL"])
    if grey - colour != 15 or materials - grey != 15:
        raise ModError("Fish icon update needs the installed 15-good UI layout")
    frames = texture_frames(textures)
    replacements = {}
    for first, is_grey in [(colour, False), (grey, True)]:
        target = first + 14
        if first not in frames or target not in frames:
            raise ModError("Fish or Food icon is missing from the installed UI")
        food = frames[first]
        parts = {tag: food[start + 16:end] for tag, start, end in anno_chunks(food, 24)}
        if len(parts.get("HEAD", b"")) < 8:
            raise ModError("Incomplete Food icon header")
        palette = read_palette(textures, struct.unpack_from("<H", parts["HEAD"], 4)[0])
        replacements[target] = reidentify_texture(fish_frame(food, palette, asset, is_grey), target)
    payload = bytearray()
    for tag, start, end in anno_chunks(textures):
        ident = struct.unpack_from("<I", textures, start + 20)[0] if tag == "TEXTURE" else None
        payload.extend(replacements.get(ident, textures[start:end]))
    result = make_chunk("ANNO", bytes(payload))
    updated = texture_frames(result)
    if set(updated) != set(frames):
        raise ModError("Fish icon update changed texture IDs")
    if any(updated[ident] != frame for ident, frame in frames.items() if ident not in replacements):
        raise ModError("Fish icon update changed an unrelated sprite")
    return result

def extend_fish_ui(index: bytes, textures: bytes, progress=None, icon_asset=None) -> tuple[bytes, bytes]:
    """Insert Fish slots, optionally painting their own colour and grey icons."""
    entries = read_access(index)
    access = dict(entries)
    try:
        colour = access["WARENICONS_BEDARF"]
        grey = access["WARENICONS_BEDARF_GREY"]
        materials = access["WARENICONS_BAUMATERIAL"]
    except KeyError as exc:
        raise ModError("Consumer-good icon groups are missing") from exc
    if grey - colour != 14 or materials - grey != 14:
        raise ModError("Expected 14 original consumer-good icons; UI may already be modded")
    frames = texture_frames(textures)
    if any(i not in frames for i in range(colour, materials + 1)):
        raise ModError("A consumer-good texture is missing")
    # Native sprites can have different dimensions even within a group.
    # Validate their structure without requiring a fixed or uniform size.
    # No image is decoded, resized, or padded: the new placeholder is a
    # byte-for-byte copy of its own group's Food sprite, with a new ID.
    sizes = {ident: consumer_icon_dimensions(frames[ident], ident)
             for ident in range(colour, materials)}
    if progress:
        progress("  Food placeholders copied at native size: colour " + "x".join(map(str, sizes[colour]))
                 + ", grey " + "x".join(map(str, sizes[grey])))

    def shifted(ident: int) -> int:
        return ident + int(ident >= grey) + int(ident >= materials)

    payload = bytearray()
    for tag, start, end in anno_chunks(textures):
        part = textures[start:end]
        if tag == "TEXTURE":
            ident = struct.unpack_from("<I", part, 20)[0]
            if ident == grey:
                payload.extend(reidentify_texture(frames[colour], grey))
            if ident == materials:
                payload.extend(reidentify_texture(frames[grey], materials + 1))
            part = reidentify_texture(part, shifted(ident))
        payload.extend(part)
    new_textures = make_chunk("ANNO", bytes(payload))
    new_entries = [(name, shifted(ident)) for name, ident in entries]
    new_index = make_chunk("ANNO", make_chunk("ACCESS", b"".join(
        f"{name},{ident}".encode("ascii") + b"\0" for name, ident in new_entries
    )))
    new_frames = texture_frames(new_textures)
    if len(new_frames) != len(frames) + 2:
        raise ModError("UI validation failed: incorrect texture count")
    for ident, frame in frames.items():
        if reidentify_texture(new_frames[shifted(ident)], ident) != frame:
            raise ModError("UI validation failed: an existing icon changed")
    if icon_asset is not None:
        new_textures = paint_fish_icons(new_index, new_textures, icon_asset)
    return new_index, new_textures

def add_fish_definition(data: bytes) -> bytes:
    text = data.decode("cp1252")
    if re.search(r"(?m)^[ \t]*Id:[ \t]*" + FISH_GOOD + r"[ \t]*\r?$", text):
        raise ModError(FISH_GOOD + " already exists in BGruppen.dat")
    definition = re.search(
        r"(?m)^[ \t]*Id:[ \t]*NAHRUNG[ \t]*\r?$", text
    )
    if not definition:
        raise ModError("Food definition was not found")
    next_definition = re.search(r"(?m)^[ \t]*Id:", text[definition.end():])
    if not next_definition:
        raise ModError("The following goods definition was not found")
    insert_at = definition.end() + next_definition.start()
    food_definition = text[definition.start():insert_at]
    fish_definition = re.sub(r"(?m)(Id:[ \t]*)NAHRUNG", r"\g<1>" + FISH_GOOD, food_definition, count=1)
    text = text[:insert_at] + fish_definition + text[insert_at:]
    return text.encode("cp1252")

def split_food_demand(data: bytes) -> bytes:
    text = add_fish_definition(data).decode("cp1252")
    header, populations = text.split("[BGRUPPE]", 1)
    populations, footer = populations.split("[BAUSTUFEN]", 1)
    pattern = re.compile(
        r"(?m)(^[ \t]*Ware:[ \t]*NAHRUNG[^\r\n]*\r?\n)"
        r"([ \t]*Menge:[ \t]*)([0-9.]+)([^\r\n]*\r?\n)"
        r"([ \t]*Priority:[ \t]*HIGH[^\r\n]*\r?\n"
        r"[ \t]*Force:[ \t]*TRUE[^\r\n]*\r?\n)"
    )
    count = 0

    def change(match):
        nonlocal count
        count += 1
        value = Decimal(match[3]) / Decimal(2)
        half = format(value.normalize(), "f")
        food = match[1] + match[2] + half + match[4] + match[5]
        fish = food.replace("NAHRUNG", FISH_GOOD, 1)
        return food + "\r\n" + fish

    populations = pattern.sub(change, populations)
    if count != 5:
        raise ModError(f"Expected five population food needs; found {count}")
    return (header + "[BGRUPPE]" + populations + "[BAUSTUFEN]" + footer).encode("cp1252")

def update_labels(data: bytes, rename_stall: bool = True) -> bytes:
    text = data.decode("cp1252")
    pattern = re.compile(r"(?ms)(^\[WARE_BEDARF\]\r?\n)(.*?)(?=^\[|\Z)")
    match = pattern.search(text)
    if not match:
        raise ModError("Consumer-good text section is missing")
    goods = [line for line in match[2].splitlines() if line.strip()]
    if len(goods) != 14:
        raise ModError("Expected 14 original consumer-good labels")
    if goods[0].casefold() in {"nahrung"}:
        fish, stall = "Fisch", "Fisch-/Weinstand"
    elif goods[0].casefold() in {"voedsel", "voeding"}:
        fish, stall = "Vis", "Vis-/wijnkraam"
    elif goods[0].casefold() == "food":
        fish, stall = "Fish", "Fish / wine stall"
    else:
        raise ModError("Unsupported text language: " + goods[0])
    updated = match[1] + match[2].rstrip("\r\n") + "\r\n" + fish + "\r\n"
    text = text[:match.start()] + updated + text[match.end():]
    if rename_stall:
        text, count = re.subn(r"(?m)^1316:[^\r\n]*", "1316:" + stall, text)
        if count != 1:
            raise ModError("The wine-stall name was not found exactly once")
    return text.encode("cp1252")

def update_icon_sources(data: bytes) -> bytes:
    text = data.decode("cp1252")
    for label in ["WARENICONS_BEDARF", "WARENICONS_BEDARF_GREY"]:
        expression = re.compile(
            r'(?ms)(Access:[ \t]*"' + label + r'"(?:(?!Access:).)*?Segments:[ \t]*)14([ \t]*,[ \t]*1)'
        )
        text, count = expression.subn(r"\g<1>15\2", text)
        if count != 1:
            raise ModError("Could not update icon source group " + label)
    return text.encode("cp1252")

def patched_bytes(original: bytes, patches: list[dict], origin: int = 0) -> bytes:
    result = bytearray(original)
    touched = []
    for patch in patches:
        offset = patch["offset"] - origin
        before, after = bytes.fromhex(patch["before"]), bytes.fromhex(patch["after"])
        if len(before) != len(after) or offset < 0 or offset + len(before) > len(result):
            raise ModError("Invalid patch span")
        if any(offset < end and offset + len(before) > start for start, end in touched):
            raise ModError("Overlapping patch spans")
        if original[offset:offset + len(before)] != before:
            raise ModError("A patch's original bytes do not match")
        result[offset:offset + len(before)] = after
        touched.append((offset, offset + len(before)))
    return bytes(result)

def atomic_write(path: Path, data: bytes):
    descriptor, temporary_name = tempfile.mkstemp(prefix=".fishmod-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            shutil.copystat(path, temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
