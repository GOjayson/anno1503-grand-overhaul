"""Build simplified preview coastlines from exact catalogue template HEIGHT data.

Read-only for the original game and all private alias assets. The 64 by 64
thumbnail marks a cell when any native tile in that cell has HEIGHT >=0x30.
These are simplified top-down land silhouettes, not resource/harvest previews.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[2]
PRIVATE = PACKAGE / "developer/source/engine_resume/ai_food/experiment_runtime"
SIZE = 64


def sha(data):
    return hashlib.sha256(data).hexdigest()


def chunks(data, start, end):
    at = start
    while at < end:
        assert 0 <= at <= end <= len(data) and end-at >= 16, "Truncated native chunk"
        tag = data[at:at+12]
        assert re.fullmatch(rb"[A-Z0-9_]{1,12}\0*", tag), "Unsupported chunk tag"
        n = struct.unpack_from("<I", data, at+12)[0]
        assert n <= end-at-16, "Chunk crosses its parent"
        yield tag.rstrip(b"\0").decode("ascii"), data[at+16:at+16+n]
        at += 16+n
    assert at == end


def height_tiles(data, width, height):
    root = list(chunks(data, 0, len(data)))
    assert root and root[0][0] in {"ANNO", "ANNOADDON1"}
    # Catalogue assets can retain an original native trailer after the root.
    body = list(chunks(root[0][1], 0, len(root[0][1])))
    islands = [p for tag, p in body if tag == "INSEL5"]
    assert len(islands) == 1
    island = islands[0]
    assert len(island) >= 12
    _, _, actual_width, actual_height, _ = struct.unpack_from("<HHHHI", island)
    assert (actual_width, actual_height) == (width, height)
    heights, seen = bytearray(width*height), bytearray(width*height)
    for tag, tile in chunks(island, 12, len(island)):
        if tag != "HEIGHT":
            continue
        assert len(tile) >= 6
        x, y, w, h = struct.unpack_from("<HHBB", tile)
        assert w and h and x+w <= width and y+h <= height and len(tile) == 6+w*h
        for yy in range(h):
            for xx in range(w):
                index = (y+yy)*width+x+xx
                assert not seen[index], "Overlapping native HEIGHT tile"
                seen[index] = 1
                heights[index] = tile[6+yy*w+xx]
    assert all(seen), "Incomplete HEIGHT coverage"
    return heights


def mask_for(heights, width, height):
    bitmap = bytearray(SIZE*SIZE//8)
    for y in range(SIZE):
        top, bottom = y*height//SIZE, (y+1)*height//SIZE
        for x in range(SIZE):
            left, right = x*width//SIZE, (x+1)*width//SIZE
            land = any(heights[yy*width+xx] >= 0x30
                       for yy in range(top, bottom) for xx in range(left, right))
            if land:
                bit = y*SIZE+x
                bitmap[bit//8] |= 1 << (bit % 8)
    return bytes(bitmap)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    game = args.game_dir.resolve(strict=True)
    catalogue = PRIVATE / "world_catalogue.h"
    text = catalogue.read_text(encoding="utf-8")
    pattern = re.compile(r'^\{"([^"\r\n]*)",(\d+(?:,\d+){8}),\{([\d,]+)\}\},?$', re.M)
    rows, masks = [], []
    for index, match in enumerate(pattern.finditer(text)):
        relative = json.loads('"' + match[1] + '"').replace("\\", "/")
        width, height, climate, *_ = map(int, match[2].split(","))
        expected = bytes(map(int, match[3].split(","))).hex()
        source = PACKAGE / "assets" / relative if relative.startswith("WorldSettingsIslands/") else game / relative
        data = source.read_bytes()
        assert sha(data) == expected, "Template differs from the inspected catalogue: " + relative
        # Read the first complete ANNO root; native trailer bytes are not chunks.
        assert len(data) >= 16
        end = 16+struct.unpack_from("<I", data, 12)[0]
        assert end <= len(data)
        heights = height_tiles(data[:end], width, height)
        bitmap = mask_for(heights, width, height)
        assert len(bitmap) == 512
        masks.append(bitmap)
        rows.append(dict(index=index, path=relative, width=width, height=height,
                         climate=climate, template_sha256=expected, height_sha256=sha(heights),
                         native_land_tiles=sum(v >= 0x30 for v in heights),
                         preview_land_cells=sum(v.bit_count() for v in bitmap), mask_sha256=sha(bitmap)))
    assert len(rows) == 444
    assert rows[-1]["path"] == "WorldSettingsIslands/Nord/V_080x080_Easy_Mercoli.scp"
    assert (rows[-1]["width"], rows[-1]["height"], rows[-1]["climate"]) == (80, 80, 2)
    header = ["/* Generated from exact History Edition HEIGHT tiles. Simplified top-down land. */",
              "#ifndef WS_WORLD_PREVIEW_COASTS_H", "#define WS_WORLD_PREVIEW_COASTS_H",
              "#define WS_PREVIEW_COAST_SIZE 64u", "#define WS_PREVIEW_COAST_BYTES 512u",
              f"#define WS_PREVIEW_COAST_COUNT {len(rows)}u",
              "static const unsigned char wsPreviewCoasts[WS_PREVIEW_COAST_COUNT][WS_PREVIEW_COAST_BYTES] = {"]
    header.extend("{"+",".join(map(str, data))+"}," for data in masks)
    header.extend(["};", "#endif", ""])
    header_bytes = "\n".join(header).encode("ascii")
    output = PRIVATE / "world_preview_coasts.h"
    manifest = dict(scope=__doc__, resolution=SIZE, bytes_per_template=512,
                    land_height_threshold=48, cell_reduction="any native land tile",
                    template_count=len(rows), catalogue_sha256=sha(catalogue.read_bytes()),
                    generated_header_sha256=sha(header_bytes), generator_sha256=sha(Path(__file__).read_bytes()),
                    all_template_hashes_verified=True, original_game_or_alias_assets_modified=False,
                    actual_game_run=False, templates=rows)
    manifest_bytes = (json.dumps(manifest, indent=2)+"\n").encode("utf-8")
    report = HERE / "coastline_manifest.json"
    if args.check:
        assert output.read_bytes() == header_bytes and report.read_bytes() == manifest_bytes
    else:
        output.write_bytes(header_bytes)
        report.write_bytes(manifest_bytes)
    print(json.dumps(dict(passed=True, check_only=args.check, templates=len(rows),
                         header_sha256=sha(header_bytes), manifest_sha256=sha(manifest_bytes)), indent=2))


if __name__ == "__main__":
    main()
