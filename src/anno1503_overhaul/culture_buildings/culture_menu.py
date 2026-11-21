"""Culture construction pages inside the History Edition Ornaments tab."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import struct
from ..world_native import _align, checksum
from ..world_runtime_build import PE
from . import menu


# Each detour replaces complete stock instructions in both reviewed View.dll builds.
CAPTURE = 0x35D4A, "488b8ec8070000"  # Bind an ornament view to its current world.
SELECT = 0x35DC1, "480f44d1488bce"  # Pick a grid, icon group, tooltip group and size.
CLICK = 0x3398B, "488b8bb0070000"  # Native selected definition is at [rsp+0x38].
FLUSH = 0x35C88, "488b5c2440"      # The page's mouse dispatcher has finished.
ORNAMENTS_VTABLE = 0xA8EA8
CLEAR_GRID = 0x32760
REBUILD_GRID = 0x35CD0
EXIT_CLICK = 0x339FB


@dataclass(frozen=True)
class CultureBuilding:
    ident: int
    labels: dict[str, str]
    icon: str = "ornament"
    alternate_ids: tuple[int, ...] = ()
    art_source: int | None = None


@dataclass(frozen=True)
class CultureCategory:
    key: str
    labels: dict[str, str]
    buildings: tuple[CultureBuilding, ...]


@dataclass(frozen=True)
class _Cell:
    ident: int
    labels: dict[str, str]
    icon: tuple[str, int]
    marker: str = ""


@dataclass(frozen=True)
class _Grid:
    key: str
    cells: tuple[_Cell, ...]

    @property
    def art(self):
        return "THUMBNAILSTYLE_" + self.key

    @property
    def tooltip(self):
        return "TOOLTIP:BAUMENU_STYLE_" + self.key


@dataclass(frozen=True)
class _Selector:
    main_link: _Cell
    grids: tuple[_Grid, ...]
    routes: dict[int, int]
    names: dict[int, dict[str, str]]


LANGUAGES = {
    Path("Texte.dat"): ("de", "Zurück zu Ziergebäuden"),
    Path("Languages/Texte.dat"): ("en", "Back to Ornaments"),
    Path("Languages/Nl/Texte.dat"): ("nl", "Terug naar siergebouwen"),
}

SELECTOR_ID = 520
ORNAMENTS_ID = 511
CULTURE_IDS = (521, 522, 540, 541, 542, 543, 503, 505, 507, 509)
PREVIOUS_ID, NEXT_ID = 513, 501
PREVIOUS, NEXT = -1, -2
MAX_BUILDINGS_PER_GRID = 29
# The small African selector button uses a one-pixel taller stock frame.
MARKER_ADDITIONAL_SIZES = ((39, 40),)

ICONS = {
    "residence": ("THUMBNAILDIVERSES", 0),
    "aristocrat": ("THUMBNAILDIVERSES", 1),
    "ornament": (menu.ADDON_ORNAMENTS, 14),
    "industry": ("THUMBNAILHANDWERK", 0),
    "public": ("THUMBNAILDIVERSES", 8),
    "road": ("THUMBNAILWEG", 0),
}
SELECTOR_ICONS = (
    (menu.ADDON_ORNAMENTS, 3), (menu.ADDON_ORNAMENTS, 7),
    ("THUMBNAILDIVERSES", 0), ("THUMBNAILLANDWIRTSCHAFT", 0),
    ("THUMBNAILSEEFAHRT", 0), ("THUMBNAILDIVERSES", 8),
    (menu.ADDON_ORNAMENTS, 12), ("THUMBNAILHANDWERK", 0),
    ("THUMBNAILMILITAR", 0), (menu.ADDON_ORNAMENTS, 19),
)
MARKER_FONT = {
    "A": (2, 5, 7, 5, 5), "B": (6, 5, 6, 5, 6), "C": (3, 4, 4, 4, 3),
    "D": (6, 5, 5, 5, 6), "E": (7, 4, 6, 4, 7), "F": (7, 4, 6, 4, 4),
    "G": (3, 4, 5, 5, 3), "H": (5, 5, 7, 5, 5), "I": (7, 2, 2, 2, 7),
    "J": (1, 1, 1, 5, 2), "K": (5, 5, 6, 5, 5), "L": (4, 4, 4, 4, 7),
    "M": (5, 7, 7, 5, 5), "N": (5, 7, 7, 7, 5), "O": (2, 5, 5, 5, 2),
    "P": (6, 5, 6, 4, 4), "Q": (2, 5, 5, 7, 3), "R": (6, 5, 6, 5, 5),
    "S": (3, 4, 2, 1, 6), "T": (7, 2, 2, 2, 2), "U": (5, 5, 5, 5, 7),
    "V": (5, 5, 5, 5, 2), "W": (5, 5, 7, 7, 5), "X": (5, 5, 2, 5, 5),
    "Y": (5, 5, 2, 2, 2), "Z": (7, 1, 2, 4, 7), "<": (1, 2, 7, 2, 1),
    ">": (4, 2, 7, 2, 4),
}


def _labelset(labels):
    if set(labels) != {"de", "en", "nl"}:
        raise ValueError("Every culture name and entry needs German, English and Dutch labels")
    for value in labels.values():
        if (not isinstance(value, str) or not value or len(value.encode("cp1252")) > 72
                or any(c in value for c in "\r\n\0[]%")):
            raise ValueError(f"Invalid construction menu label {value!r}")


def _selector(categories):
    if not 1 <= len(categories) <= len(CULTURE_IDS):
        raise ValueError("The culture selector needs one to ten cultures")
    title = {"de": "Kulturgebäude", "en": "Cultural Buildings", "nl": "Culturele gebouwen"}
    return_to_selector = {"de": "Zurück zur Kulturauswahl", "en": "Back to Cultural Buildings",
                          "nl": "Terug naar culturele gebouwen"}
    previous = {"de": "Vorherige Seite", "en": "Previous Page", "nl": "Vorige pagina"}
    following = {"de": "Nächste Seite", "en": "Next Page", "nl": "Volgende pagina"}
    back_to_ornaments = {lang: label for lang, label in LANGUAGES.values()}
    main = _Cell(SELECTOR_ID, title, (menu.ADDON_ORNAMENTS, 3), "CULT")
    back = _Cell(SELECTOR_ID, return_to_selector, (menu.ADDON_ORNAMENTS, 3), "<")
    previous_cell = _Cell(PREVIOUS_ID, previous, (menu.ADDON_ORNAMENTS, 3), "<")
    next_cell = _Cell(NEXT_ID, following, (menu.ADDON_ORNAMENTS, 3), ">")
    routes = {SELECTOR_ID: 1, ORNAMENTS_ID: 0, PREVIOUS_ID: PREVIOUS, NEXT_ID: NEXT}
    culture_links, building_grids, names = [], [], {}
    used_keys = set()
    reserved_ids = {*routes, *CULTURE_IDS}
    markers = set()

    for ordinal, category in enumerate(categories):
        if (not re.fullmatch(r"[A-Z]{3,12}", category.key)
                or category.key in used_keys or category.key[:3] in markers):
            raise ValueError(f"Invalid, repeated or visually ambiguous culture key {category.key!r}")
        if not category.buildings:
            raise ValueError(f"The {category.key} page needs at least one building")
        _labelset(category.labels)
        used_keys.add(category.key)
        marker = category.key[:3]
        markers.add(marker)
        link = CULTURE_IDS[ordinal]
        routes[link] = 2 + len(building_grids)
        culture_links.append(_Cell(link, category.labels, SELECTOR_ICONS[ordinal], marker))

        items = []
        for building in category.buildings:
            _labelset(building.labels)
            for ident in (building.ident, *building.alternate_ids):
                if type(ident) is not int or not 1 < ident < 4000 or ident in names or ident in reserved_ids:
                    raise ValueError(f"Invalid or repeated culture building ID {ident}")
                names[ident] = building.labels
            if building.icon not in ICONS:
                raise ValueError(f"Unknown culture building icon {building.icon}")
            items.append(_Cell(building.ident, building.labels, ICONS[building.icon]))
        for page, pos in enumerate(range(0, len(items), MAX_BUILDINGS_PER_GRID), 1):
            cells = items[pos:pos + MAX_BUILDINGS_PER_GRID]
            if pos:
                cells.append(previous_cell)
            if pos + MAX_BUILDINGS_PER_GRID < len(items):
                cells.append(next_cell)
            cells.append(back)
            building_grids.append(_Grid(f"{category.key}{page}", tuple(cells)))

    culture_links.append(_Cell(ORNAMENTS_ID, back_to_ornaments, (menu.ADDON_ORNAMENTS, 3), "<"))
    grids = (_Grid("CULTURES", tuple(culture_links)), *building_grids)
    if len(grids) > 60:
        raise ValueError("The prototype supports up to 59 construction pages plus the culture selector")
    return _Selector(main, grids, routes, names)


class _Branches:
    """Encode the few position-relative instructions in the checked detours."""

    def __init__(self, start):
        self.start = start
        self.data = bytearray()
        self.labels = {}
        self.fixups = []

    @property
    def at(self):
        return self.start + len(self.data)

    def label(self, name):
        self.labels[name] = self.at

    def emit(self, instruction):
        self.data.extend(bytes.fromhex(instruction))

    def reference(self, instruction, target, tail=b""):
        self.emit(instruction)
        self.fixups.append((len(self.data), target, len(tail)))
        self.data.extend(bytes(4) + tail)

    def jump(self, address):
        self.reference("e9", address)

    def branch(self, condition, address):
        self.reference("0f " + condition, address)

    def call(self, address):
        self.reference("e8", address)

    def close(self):
        for offset, target, tail_length in self.fixups:
            address = self.labels[target] if isinstance(target, str) else target
            displacement = address - (self.start + offset + 4 + tail_length)
            struct.pack_into("<i", self.data, offset, displacement)
        return bytes(self.data)


def _menu_data(base, pages):
    """Give page entries writable art IDs, as required by native grid setup."""
    states = {"view": base, "world": base + 8, "current": base + 16, "pending": base + 20}
    data = bytearray(struct.pack("<QQii", 0, 0, 0, -1))
    page_data = []
    for page in pages:
        first = base + len(data)
        ids = tuple(cell.ident for cell in page.cells)
        for ident in ids:
            data.extend(struct.pack("<II", ident, 0))
        art = base + len(data)
        data.extend(page.art.encode("ascii") + b"\0")
        tooltip = base + len(data)
        data.extend(page.tooltip.encode("ascii") + b"\0")
        data.extend(bytes(_align(len(data), 8) - len(data)))
        page_data.append((first, art, tooltip, len(ids)))
    return bytes(data), states, page_data


def _stub_capture(code, state):
    code.reference("48 39 35", state["view"])   # cmp [view], rsi
    code.branch("85", "capture_reset")
    code.reference("48 39 1d", state["world"])  # cmp [world], rbx
    code.branch("84", "capture_done")
    code.label("capture_reset")
    code.reference("c7 05", state["current"], struct.pack("<i", 0))
    code.reference("c7 05", state["pending"], struct.pack("<i", -1))
    code.reference("48 89 35", state["view"])   # mov [view], rsi
    code.reference("48 89 1d", state["world"])  # mov [world], rbx
    code.label("capture_done")
    code.emit(CAPTURE[1])
    code.jump(CAPTURE[0] + len(bytes.fromhex(CAPTURE[1])))


def _stub_select(code, state, page_data):
    code.emit("48 0f 44 d1")                    # Preserve stock classic icon selection.
    code.emit("85 c0")                          # test eax, eax (addon mode)
    code.branch("84", "select_done")
    code.reference("8b 05", state["current"])
    for page_index in range(len(page_data)):
        code.emit(f"83 f8 {page_index + 1:02x}")  # cmp eax, page_index
        code.branch("84", f"select_page_{page_index}")
    code.jump("select_done")
    for page_index, (entries, art, tooltip, size) in enumerate(page_data):
        code.label(f"select_page_{page_index}")
        code.reference("48 8d 1d", entries)     # lea rbx, [entries]
        code.reference("48 8d 15", art)         # lea rdx, [art]
        code.reference("4c 8d 05", tooltip)     # lea r8, [tooltip]
        code.emit("bf " + struct.pack("<I", size).hex())  # mov edi, size
        code.emit("48 89 5c 24 20 89 7c 24 28")
        code.jump("select_done")
    code.label("select_done")
    code.emit("48 8b ce")                       # mov rcx, rsi
    code.jump(SELECT[0] + len(bytes.fromhex(SELECT[1])))


def _selector_click(code, state, routes):
    code.reference("48 39 1d", state["view"])
    code.branch("85", "click_original")
    code.reference("4c 8d 15", ORNAMENTS_VTABLE)
    code.emit("4c 39 13")
    code.branch("85", "click_original")
    for ident in routes:
        code.emit("81 7c 24 38 " + struct.pack("<I", ident).hex())
        code.branch("84", f"click_route_{ident}")
    code.label("click_original")
    code.emit(CLICK[1])
    code.jump(CLICK[0] + len(bytes.fromhex(CLICK[1])))
    for ident, target in routes.items():
        code.label(f"click_route_{ident}")
        if target in (PREVIOUS, NEXT):
            code.reference("8b 05", state["current"])
            code.emit("ff c8" if target == PREVIOUS else "ff c0")
        else:
            code.emit("b8 " + struct.pack("<I", target).hex())
        code.jump("click_queue")
    code.label("click_queue")
    code.emit("40 f6 c7 01")
    code.branch("84", EXIT_CLICK)
    code.reference("89 05", state["pending"])
    code.jump(EXIT_CLICK)


def _stub_flush(code, state):
    code.reference("48 39 1d", state["view"])
    code.branch("85", "flush_original")
    code.reference("8b 05", state["pending"])
    code.emit("83 f8 ff")
    code.branch("84", "flush_original")
    code.reference("89 05", state["current"])
    code.reference("c7 05", state["pending"], struct.pack("<i", -1))
    # The view reuses its grid container. Native child removal leaves the
    # active row indices intact, and the next input dereferences that old
    # slot before hit testing. Send the native reset (the same command as
    # View's teardown path) while all old widgets are still present.
    code.emit("48 8b 83 50 07 00 00")          # mov rax, [rbx + 0x750]
    code.emit("48 8b 08 48 8b 01")             # get the menu and its vtable
    code.emit("33 d2 41 b8 04 00 00 00 45 33 c9")
    code.emit("48 c7 44 24 20 00 00 00 00")
    code.emit("ff 90 40 01 00 00")             # menu command 4 clears both row indices
    code.emit("48 8b cb")                       # mov rcx, rbx
    code.call(CLEAR_GRID)
    code.reference("48 8b 15", state["world"])  # mov rdx, [world]
    code.emit("48 8b cb")
    code.call(REBUILD_GRID)
    code.label("flush_original")
    code.emit(FLUSH[1])
    code.jump(FLUSH[0] + len(bytes.fromhex(FLUSH[1])))


def _build_view(view, pages, *, selector):
    image = PE(view)
    section_align, file_align = image.unpack("<II", image.optional + 32)
    code_rva = _align(image.image_size, section_align)
    code = _Branches(code_rva)
    state_rva = code_rva + section_align
    state_bytes, state, page_data = _menu_data(state_rva, pages)
    stubs = (
        (CAPTURE, _stub_capture, (state,)),
        (SELECT, _stub_select, (state, page_data)),
        (CLICK, _selector_click, (state, selector.routes)),
        (FLUSH, _stub_flush, (state,)),
    )
    result = bytearray(view)
    originals = image.function_table()
    unwind = []
    for (site, preimage_hex), emit, args in stubs:
        preimage = bytes.fromhex(preimage_hex)
        if image.read(site, len(preimage)) != preimage:
            raise ValueError(f"Unexpected View submenu preimage at {site:#x}")
        parents = [entry for entry in originals if entry[0] <= site < entry[1]]
        if len(parents) != 1:
            raise ValueError(f"Expected one unwind parent for {site:#x}")
        stub_start = code.at
        emit(code, *args)
        unwind.append((stub_start, code.at, parents[0]))
        patch = image.offset(site, len(preimage))
        detour = b"\xe9" + struct.pack("<i", stub_start - site - 5)
        result[patch:patch + len(preimage)] = detour.ljust(len(preimage), b"\x90")

    code_bytes = code.close()
    if len(code_bytes) > section_align:
        raise ValueError("Submenu executable section exceeds its mapped bounds")

    payload = bytearray(state_bytes)
    entries = set(originals)
    for first, last, parent in unwind:
        if not code_rva <= first < last <= code_rva + len(code_bytes):
            raise ValueError("Invalid submenu unwind extent")
        entries.add((first, last, state_rva + len(payload)))
        payload.extend(b"\x21\x00\x00\x00" + struct.pack("<III", *parent))
    table = state_rva + len(payload), len(entries) * 12
    payload.extend(b"".join(struct.pack("<III", *entry) for entry in sorted(entries)))

    # The original Ornaments still uses its native table. Only its empty cells
    # become navigation links.
    slot = image.offset(menu.MENU_SLOT_RVA, len(menu.EMPTY_SLOTS))
    if result[slot:slot + len(menu.EMPTY_SLOTS)] != menu.EMPTY_SLOTS:
        raise ValueError("The stock Ornaments are missing their unused cells")
    struct.pack_into("<I", result, slot, selector.main_link.ident)

    section_size = image.unpack("<H", image.pe + 20)[0]
    header = image.optional + section_size + 40 * len(image.sections)
    if header + 80 > image.header_size or result[header:header + 80] != bytes(80):
        raise ValueError("No room for two submenu PE sections")
    for section_index, (name, rva, body, flags) in enumerate((
        (b".venmenu", code_rva, code_bytes, 0x60000020),
        (b".venvars", state_rva, payload, 0xC0000040),
    )):
        raw = _align(len(result), file_align)
        raw_size = _align(len(body), file_align)
        struct.pack_into("<8sIIIIIIHHI", result, header + 40 * section_index,
                         name, len(body), rva, raw_size, raw, 0, 0, 0, 0, flags)
        result.extend(bytes(raw - len(result)) + body + bytes(raw_size - len(body)))
        opt_size = image.optional + 4 + section_index * 4
        struct.pack_into("<I", result, opt_size, image.unpack("<I", opt_size)[0] + raw_size)
    struct.pack_into("<H", result, image.pe + 6, len(image.sections) + 2)
    struct.pack_into("<I", result, image.optional + 56, _align(state_rva + len(payload), section_align))
    struct.pack_into("<II", result, image.optional + 112 + 3 * 8, *table)
    struct.pack_into("<I", result, image.optional + 64, checksum(bytes(result)))

    updated = PE(bytes(result))
    if updated.function_table() != entries or any(
        updated.directory(i) != image.directory(i) for i in range(16) if i != 3
    ):
        raise ValueError("Submenu changed an unexpected native directory")
    return updated.data


def _localized_selector(data, path, selector):
    language, _ = LANGUAGES[path]
    start, end = menu._section(data, b"[TOOLTIP:BAUMENU_WIGWAMS_ADDON]")
    if sha256(data[start:end]).hexdigest() != menu.TOOLTIP_HASHES[path]:
        raise ValueError(f"Unexpected original ornament tooltips in {path}")
    tooltips = [selector.main_link.labels[language]]
    for grid in selector.grids:
        tooltips.append(f"[{grid.tooltip}]")
        tooltips.extend(cell.labels[language] for cell in grid.cells)
    data = data[:end] + ("\r\n".join(tooltips) + "\r\n").encode("cp1252") + data[end:]
    start, end = menu._section(data, b"[ANLAGEN]")
    prefixes = tuple(f"{ident}:".encode("ascii") for ident in selector.names)
    if any(line.startswith(prefixes) for line in data[start:end].splitlines()):
        raise ValueError(f"A culture building name already exists in {path}")
    names = "".join(f"{ident}:{labels[language]}\r\n" for ident, labels in selector.names.items())
    return data[:end] + names.encode("cp1252") + data[end:]


def _paint_marker(frame, marker, palette):
    formats = menu.formats
    width, height, pixels = formats._decode(frame, additional_sizes=MARKER_ADDITIONAL_SIZES)
    scale = 2
    label_width = (len(marker) * 4 - 1) * scale
    x0 = (width - label_width) // 2
    y0 = height - 5 * scale - 3
    if x0 < 2 or y0 < 2 or -1 in pixels:
        raise ValueError("Culture marker needs a complete native icon large enough for its lettering")

    def nearest(rgb):
        return min(range(len(palette)),
                   key=lambda i: sum((sample - wanted) ** 2 for sample, wanted in zip(palette[i], rgb)))

    background = nearest((33, 25, 19))
    foreground = nearest((246, 231, 183))
    for y in range(y0 - 2, height - 1):
        start = y * width + x0 - 2
        pixels[start:start + label_width + 4] = [background] * (label_width + 4)
    for letter, character in enumerate(marker):
        for row, bits in enumerate(MARKER_FONT[character]):
            for col in range(3):
                if bits & (4 >> col):
                    x = x0 + (letter * 4 + col) * scale
                    for dy in range(scale):
                        start = (y0 + row * scale + dy) * width + x
                        pixels[start:start + scale] = [foreground] * scale
    return formats._replace_body(frame, pixels, additional_sizes=MARKER_ADDITIONAL_SIZES)


def _texture_selector(index, textures, selector, building_icons=None):
    formats = menu.formats
    entries = formats._access(index)
    access = dict(entries)
    frames = formats._frames(textures)
    art_base = max(frames) + 1
    palettes, indexed, painted = {}, {}, {}

    def colors(palette):
        if palette not in palettes:
            palettes[palette] = formats._palette(textures, palette)[1]
        return palettes[palette]

    def indexed_colors(palette):
        if palette not in indexed:
            from .building_icons import indexed_palette

            indexed[palette] = indexed_palette(colors(palette))
        return indexed[palette]

    def icon(cell, state, ident):
        group, slot = cell.icon
        source = access[group] + slot * 3 + state
        frame = frames[source]
        if building_icons is not None and cell.ident in building_icons.sources:
            frame = building_icons.paint(frame, cell.ident, state, indexed_colors)
        if cell.marker:
            key = source, cell.marker
            if key not in painted:
                head = next(frame[start + 16:end] for tag, start, end in
                            formats._chunks(frame, 24) if tag == "HEAD")
                palette = struct.unpack_from("<H", head, 4)[0]
                painted[key] = _paint_marker(frame, cell.marker, colors(palette))
            frame = painted[key]
        return formats._identify(frame, ident)

    main_start = access[menu.ADDON_ORNAMENTS] + 30 * 3
    replaced = {main_start + state: icon(selector.main_link, state, main_start + state) for state in range(3)}
    payload = bytearray()
    for tag, start, end in formats._chunks(textures):
        chunk = textures[start:end]
        if tag == "TEXTURE":
            ident = struct.unpack_from("<I", chunk, 20)[0]
            chunk = replaced.get(ident, chunk)
        payload.extend(chunk)
    for grid in selector.grids:
        entries.append((grid.art, art_base))
        for cell in grid.cells:
            for state in range(3):
                payload.extend(icon(cell, state, art_base))
                art_base += 1
    index_payload = b"".join(f"{name},{ident}".encode("ascii") + b"\0" for name, ident in entries)
    return formats._chunk("ANNO", formats._chunk("ACCESS", index_payload)), formats._chunk("ANNO", bytes(payload))


def _selector_atlases(game_root, selector, building_icons=None):
    outputs = {}
    for path, hashes in menu.ATLAS_HASHES.items():
        index_path = path.with_suffix(".inc")
        index = menu._verified_source(game_root, index_path, menu.INDEX_HASHES[index_path])
        textures = menu._verified_source(game_root, path, hashes)
        outputs[index_path], outputs[path] = _texture_selector(index, textures, selector, building_icons)
    return outputs


def plan_building_icons(game_root, cultures):
    """Build the same culture atlases with native art in every building slot."""
    try:
        from .building_icons import BuildingIcons, StructureArt
    except ModuleNotFoundError as error:
        if error.name != "PIL":
            raise
        raise RuntimeError("Building icon generation requires Pillow. Use the bundled Python with Pillow.") from error

    sources = {building.ident: (building.art_source, building.icon == "aristocrat")
               for category in cultures for building in category.buildings}
    if any(source is None for source, _ in sources.values()):
        raise ValueError("Every culture building needs an in-game art source")
    with StructureArt(game_root / "Anlagen.addon") as native:
        return _selector_atlases(game_root, _selector(cultures), BuildingIcons(native, sources))


def _plan_selector(game_root: Path, cultures, *, render_buildings=False) -> dict[Path, bytes]:
    selector = _selector(cultures)
    path = Path("View.dll")
    view = menu._verified_source(game_root, path, menu.VIEW_HASHES)
    outputs = {path: _build_view(view, selector.grids, selector=selector)}
    outputs.update(plan_building_icons(game_root, cultures) if render_buildings
                   else _selector_atlases(game_root, selector))
    for path in LANGUAGES:
        outputs[path] = _localized_selector((game_root / path).read_bytes(), path, selector)
    return outputs


def plan_culture_menu(
    game_root: Path,
    *,
    cultures: tuple[CultureCategory, ...],
    render_buildings: bool = False,
) -> dict[Path, bytes]:
    """Stage a culture construction selector on reviewed game inputs."""
    return _plan_selector(game_root, cultures, render_buildings=render_buildings)
