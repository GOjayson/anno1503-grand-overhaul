"""Strict read-only ANNO scene/island inspection, with no game-state writes.

Verified fields are named. Unmapped native bit fields retain their raw values;
their existence must not be presented as a guarantee of playable resources.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import struct

CULTURES = ("MAUREN", "MONGOLEN", "BEDUINEN", "AZTEKEN", "AFRIKANER",
            "INDIANER", "ESKIMOS", "SUEDSEE")
MINERAL_FIGURES = {1560:"EISENERZ", 1561:"GOLD", 1562:"SALZSTEIN",
                   1563:"EDELSTEINE", 1564:"MAMORSTEIN", 1661:"EISENERZ"}
# AnnoScene.dll d1c0/d4c0, verified against the current x64 History binary.
CLIMATE_CROP_MASKS = {0:0x18000,1:0xf009,2:0xf949,3:0xf06b,4:0xf6b9,5:0xf04d}
CLIMATE_MINERALS = {0:(),1:("EISENERZ","SALZSTEIN"),
                    2:("EISENERZ","SALZSTEIN","MAMORSTEIN"),3:("EISENERZ",),
                    4:("EISENERZ","GOLD"),5:("EISENERZ","GOLD","EDELSTEINE")}
TAG = re.compile(rb"[A-Z0-9_]{1,12}\x00*")


class SceneError(ValueError):
    pass


@dataclass(frozen=True)
class Chunk:
    tag: str
    offset: int
    length: int
    payload: bytes

    @property
    def end(self):
        return self.offset + 16 + self.length


def read_chunk(data: bytes, offset: int, end: int | None = None) -> Chunk:
    end = len(data) if end is None else end
    if offset < 0 or end > len(data) or offset + 16 > end:
        raise SceneError("Truncated chunk header")
    raw = data[offset:offset+12]
    if not TAG.fullmatch(raw):
        raise SceneError(f"Invalid chunk tag at {offset:#x}")
    size = struct.unpack_from("<I", data, offset+12)[0]
    if offset + 16 + size > end:
        raise SceneError(f"Chunk crosses parent at {offset:#x}")
    return Chunk(raw.rstrip(b"\0").decode("ascii"), offset, size,
                 data[offset+16:offset+16+size])


def chunks(data: bytes, start: int, end: int):
    position = start
    while position < end:
        item = read_chunk(data, position, end)
        yield item
        position = item.end
    if position != end:
        raise SceneError("Child chunks do not consume their parent")


def make_chunk(tag: str, payload: bytes) -> bytes:
    raw = tag.encode("ascii")
    if not TAG.fullmatch(raw) or len(raw) > 12:
        raise SceneError("Invalid output chunk tag")
    return raw.ljust(12, b"\0") + struct.pack("<I", len(payload)) + payload


def read_container(data: bytes):
    root = read_chunk(data, 0)
    if root.tag not in {"ANNO", "ANNOADDON1"}:
        raise SceneError("Unsupported ANNO container version")
    return root, data[root.end:]


def island_chunks(item: Chunk):
    if item.tag != "INSEL5" or len(item.payload) < 12:
        raise SceneError("Unsupported embedded island record")
    # The prefix has x,y,width,height as u16, then the island ID as u32.
    geometry = struct.unpack_from("<HHHHI", item.payload)
    if not geometry[2] or not geometry[3]:
        raise SceneError("Island has a zero dimension")
    parts = list(chunks(item.payload, 12, len(item.payload)))
    return geometry, parts


def read_link(item: Chunk):
    if item.tag != "INSELLNK" or len(item.payload) < 14:
        raise SceneError("Unsupported island link record")
    x, y, width, height, ident = struct.unpack_from("<HHHHI", item.payload)
    raw = item.payload[12:]
    if not width or not height or not raw.endswith(b"\0") or b"\0" in raw[:-1]:
        raise SceneError("Invalid island link dimensions/path")
    path = raw[:-1].decode("ascii")
    if not path.lower().startswith("islands\\") or not path.lower().endswith(".scp"):
        raise SceneError("Island link is not a relative islands SCP path")
    if ".." in path.split("\\") or ":" in path:
        raise SceneError("Island link leaves the scene directory")
    return dict(x=x, y=y, width=width, height=height, id=ident, path=path,
                chunk_offset=item.offset)


def _profile_cultures(data):
    found = []
    # Native profile fields use 6-byte VOLK\0\0 + u16 size, unlike 16-byte chunks.
    for match in re.finditer(b"VOLK\0\0", data):
        at = match.start() + 6
        if at + 2 > len(data):
            continue
        size = struct.unpack_from("<H", data, at)[0]
        value = data[at+2:at+2+size]
        if len(value) == size and value.endswith(b"\0"):
            name = value[:-1].decode("ascii", "replace")
            if name in CULTURES:
                found.append(name)
    return sorted(set(found))


def read_island(data: bytes):
    root, trailer = read_container(data)
    parts = list(chunks(data, 16, root.end))
    items = [x for x in parts if x.tag == "INSEL5"]
    if len(items) != 1:
        raise SceneError("Template must contain exactly one INSEL5")
    geom, child = island_chunks(items[0])
    by_tag = {}
    for part in child:
        by_tag.setdefault(part.tag, []).append(part)
    infos = by_tag.get("INFO", [])
    if len(infos) != 1 or infos[0].length != 12:
        raise SceneError("Template INFO is missing or unsupported")
    info = infos[0].payload
    heights = [0] * (geom[2] * geom[3])
    covered = set()
    for part in by_tag.get("HEIGHT", []):
        if part.length < 6:
            raise SceneError("Truncated HEIGHT tile")
        tx, ty, tw, th = struct.unpack_from("<HHBB", part.payload)
        if part.length != 6+tw*th or tx+tw > geom[2] or ty+th > geom[3]:
            raise SceneError("Invalid HEIGHT tile extents")
        for yy in range(th):
            for xx in range(tw):
                at = (ty+yy)*geom[2]+tx+xx
                if at in covered:
                    raise SceneError("Overlapping HEIGHT tile records")
                covered.add(at)
                heights[at] = part.payload[6+yy*tw+xx]
    if len(covered) != len(heights):
        raise SceneError("HEIGHT records do not cover the template")
    fertility = by_tag.get("FRUCHTBAR", [])
    if len(fertility) != 1 or fertility[0].length != geom[2]*geom[3]:
        raise SceneError("Missing or invalid FRUCHTBAR array")
    crop = by_tag.get("ANBAU", [])
    if len(crop) != 1 or (crop[0].payload and not crop[0].payload.endswith(b"\0")):
        raise SceneError("Missing or unterminated crop-name table")
    crop_names = [v.decode("cp1252") for v in crop[0].payload.split(b"\0") if v]
    mines = []
    for part in by_tag.get("BERGWERK2", []):
        payload = part.payload
        at = 0
        while at < len(payload):
            if at+8 > len(payload) or payload[at:at+6] != b"ENTRY\0":
                raise SceneError("Unsupported BERGWERK2 entry header")
            size = struct.unpack_from("<H", payload, at+6)[0]
            if size != 4 or at+8+size > len(payload):
                raise SceneError("Unsupported BERGWERK2 entry size")
            packed = struct.unpack_from("<I", payload, at+8)[0]
            mines.append(dict(x=packed & 0xfff, y=(packed >> 12) & 0xfff,
                              native_type=(packed >> 24) & 3, raw=packed))
            at += 8+size
    occurrences = []
    for part in by_tag.get("OCCUR", []):
        at = 0
        while at < part.length:
            payload = part.payload
            if at+8 > len(payload) or payload[at:at+6] != b"ENTRY2":
                raise SceneError("Unsupported OCCUR entry header")
            size = struct.unpack_from("<H", payload, at+6)[0]
            if size < 24 or at+8+size > len(payload):
                raise SceneError("Unsupported OCCUR entry size")
            raw = payload[at+8:at+8+size]
            # World.dll 5bfe7..5bffa shifts the packed DWORD by 14, masks
            # 0xfff, then calls the native Figure definition lookup.
            packed = struct.unpack_from("<I", raw)[0]
            ident = (packed >> 14) & 0xfff
            floats = struct.unpack_from("<fff", raw, 4)
            occurrences.append(dict(native_definition_id=ident,
                                    verified_mineral_good=MINERAL_FIGURES.get(ident),
                                    packed_flags=packed,
                                    payload_offset=items[0].offset+16+part.offset+16+at+8,
                                    floats=list(floats), raw_hex=raw.hex(),
                                    extension_hex=raw[24:].hex()))
            at += 8+size
    land = [i for i, value in enumerate(heights) if value >= 0x30]
    fertility_histogram = Counter(fertility[0].payload[i] & 15 for i in land)
    # ANBAU is almost identical across climates. It is a name dictionary/mask,
    # and alone does not establish that a crop can grow on this island.
    return dict(x=geom[0], y=geom[1], width=geom[2], height=geom[3], id=geom[4],
                climate_index=info[0], info_raw_hex=info.hex(),
                crop_names=crop_names, cultures=_profile_cultures(data[:root.end]),
                mine_entries=mines, occurrences=occurrences,
                verified_mineral_counts=dict(Counter(o["verified_mineral_good"] for o in occurrences
                                                      if o["verified_mineral_good"])),
                land_cells_height_at_least_48=len(land),
                land_fertility_low_nibble_histogram=dict(sorted(fertility_histogram.items())),
                top_level_tags=[dict(tag=x.tag,offset=x.offset,length=x.length) for x in parts],
                island_tags=[dict(tag=x.tag, offset=items[0].offset+16+x.offset,
                                  length=x.length) for x in child],
                root_declared_end=root.end, trailer_length=len(trailer),
                trailer_sha256=hashlib.sha256(trailer).hexdigest())


def read_scene(data: bytes):
    root, trailer = read_container(data)
    if trailer:
        raise SceneError("Unexpected bytes outside scene root")
    outer = list(chunks(data, 16, root.end))
    if len(outer) != 1 or outer[0].tag != "SCENE":
        raise SceneError("Scene container must have one SCENE record")
    parts = list(chunks(data, 32, root.end))
    heads = [x for x in parts if x.tag == "HEAD"]
    if len(heads) != 1 or heads[0].length != 32:
        raise SceneError("Missing or unsupported scene HEAD")
    width, height = struct.unpack_from("<II", heads[0].payload)
    links = [read_link(x) for x in parts if x.tag == "INSELLNK"]
    embedded = []
    for item in parts:
        if item.tag == "INSEL5":
            geom, _ = island_chunks(item)
            embedded.append(dict(zip(("x","y","width","height","id"),geom)))
    return dict(width=width, height=height, links=links, embedded_islands=embedded,
                cultures=_profile_cultures(data), head_raw_hex=heads[0].payload.hex(),
                tags=[dict(tag=x.tag,offset=x.offset,length=x.length) for x in parts])


def geometry_errors(islands, width, height, spacing=0):
    errors = []
    seen_ids = set()
    for index, a in enumerate(islands):
        if a["id"] in seen_ids:
            errors.append(f"Duplicate island ID {a['id']}")
        seen_ids.add(a["id"])
        if (a["width"] <= 0 or a["height"] <= 0 or a["x"] < 0 or a["y"] < 0
                or a["x"]+a["width"] > width or a["y"]+a["height"] > height):
            errors.append(f"Island {a['id']} is outside world bounds")
        for b in islands[:index]:
            if (a["x"] < b["x"]+b["width"]+spacing
                    and b["x"] < a["x"]+a["width"]+spacing
                    and a["y"] < b["y"]+b["height"]+spacing
                    and b["y"] < a["y"]+a["height"]+spacing):
                errors.append(f"Islands {b['id']} and {a['id']} overlap or lack spacing")
    return errors


def build_catalogue(root: Path):
    result = dict(format_version=1, cultures=list(CULTURES),
                  mineral_figure_ids=MINERAL_FIGURES,
                  native_climate_crop_masks=CLIMATE_CROP_MASKS,
                  native_climate_minerals=CLIMATE_MINERALS,
                  templates=[], scenes=[], failures=[])
    for path in sorted((root/"Scenes/Islands").rglob("*")):
        if path.suffix.lower() != ".scp" or "dummy" in path.name.lower():
            continue
        try:
            data = path.read_bytes()
            record = read_island(data)
            record.update(path=path.relative_to(root).as_posix(), size=len(data),
                          sha256=hashlib.sha256(data).hexdigest())
            result["templates"].append(record)
        except (SceneError, OSError, struct.error) as exc:
            result["failures"].append(dict(path=str(path.relative_to(root)),error=str(exc)))
    for path in sorted(root.rglob("*.sze")):
        if "WorldSettings_Work" in path.parts or not any("endlos" in p.lower() for p in path.parts):
            continue
        try:
            data = path.read_bytes()
            record = read_scene(data)
            record.update(path=path.relative_to(root).as_posix(),size=len(data),
                          sha256=hashlib.sha256(data).hexdigest())
            record["geometry_errors"] = geometry_errors(record["links"]+record["embedded_islands"],
                                                        record["width"],record["height"])
            result["scenes"].append(record)
        except (SceneError, OSError, struct.error) as exc:
            result["failures"].append(dict(path=str(path.relative_to(root)),error=str(exc)))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_root",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    result=build_catalogue(args.game_root.resolve())
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(dict(templates=len(result["templates"]), scenes=len(result["scenes"]),
                          failures=result["failures"]),ensure_ascii=True))
    return bool(result["failures"])


if __name__ == "__main__":
    raise SystemExit(main())
