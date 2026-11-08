"""Additional read-only size checks against fingerprinted planner catalogue.

Small/large mean the catalogue's smallest/largest available template for its
climate/culture group. A small native-culture island may therefore be 80/128.
"""
from pathlib import Path
import hashlib
import json
import re
import struct
import inspect_faction_save as base

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]/"ai_food/experiment_runtime"


def heights(payload):
    geometry, parts = base.island_chunks(payload)
    width,height = geometry[2:4]
    values = bytearray(width*height)
    covered = bytearray(width*height)
    for part in parts:
        if part.tag != "HEIGHT":
            continue
        base.require(len(part.payload) >= 6,"Truncated HEIGHT prefix")
        x,y,w,h = struct.unpack_from("<HHBB",part.payload)
        base.require(w and h and len(part.payload) == 6+w*h and x+w <= width and y+h <= height,"Invalid HEIGHT rectangle")
        for yy in range(h):
            for xx in range(w):
                at = (y+yy)*width+x+xx
                base.require(not covered[at],"Overlapping HEIGHT rectangles")
                covered[at] = 1
                values[at] = part.payload[6+yy*w+xx]
    base.require(all(covered),"HEIGHT rectangles do not cover saved island")
    return hashlib.sha256(values).hexdigest()


def inspect_size(data, report, size):
    base.require(size in {"small","medium","large","mixed"},"Unknown expected island-size group")
    catalogue = (SOURCE/"world_catalogue.h").read_bytes()
    factions_header = (SOURCE/"world_factions.h").read_bytes()
    base.require(base.sha(catalogue) == "2fe8bc332dff7491aeefe54bb3c219a6342fd1a8859cc5498f7b7ebe964df221","Compiled catalogue changed")
    base.require(base.sha(factions_header) == "b4668236f45fefc310412c1f8107cfdeae8c5f99874bcd0a2dd7c2b6da081764","Faction size metadata changed")
    rows = []
    for line in catalogue.decode().splitlines():
        match = re.fullmatch(r'\{("[^\"]+"),([0-9,]+),\{([0-9,]+)\}\},',line)
        if not match:
            continue
        values = [int(v) for v in match[2].split(",")]
        digest = bytes(int(v) for v in match[3].split(","))
        base.require(len(values) == 9 and len(digest) == 32,"Unsupported catalogue row")
        rows.append(dict(path=json.loads(match[1]).replace("\\","/"),width=values[0],height=values[1],climate=values[2],cultures=values[3],
                         excluded_native=values[6],size_choices=values[7],sha256=digest.hex()))
    base.require(len(rows) == 443,"Incomplete compiled template catalogue")
    def array(name):
        match = re.search(name+r'\[\]=\{([0-9,]+)\};',factions_header.decode())
        base.require(match is not None,"Missing faction size array")
        values = [int(v) for v in match[1].split(",")]
        base.require(len(values) == len(rows),"Faction size array differs")
        return values
    faction_bits = array("wsTemplateFactions")
    faction_sizes = array("wsTemplateFactionSizes")
    players = {p["id"]:p for p in report["basic_players"]}
    culture_masks = {}
    faction_masks = {}
    for state in report["saved_player_states"]:
        player = players[state["id"]]
        for city in state["cities"]:
            island = city["island_id"]
            if player["type"] == 14:
                base.require(player["volk"] in base.CULTURES,"Unknown native city culture")
                culture_masks[island] = culture_masks.get(island,0)|(1<<base.CULTURES.index(player["volk"]))
            elif player["type"] == 15:
                faction_masks[island] = faction_masks.get(island,0)|1
    bit = {"small":1,"medium":2,"large":4,"mixed":0}[size]
    root,trailer = base.read_container(data)
    base.require(not trailer,"Unexpected save trailer")
    cases = []
    climates = set()
    for island in base.chunks(data,16,root.end):
        if island.tag != "INSEL5":
            continue
        geom, children = base.island_chunks(island)
        x,y,width,height,ident = geom
        base.require(x >= 16 and y >= 16 and x+width+16 <= 1024 and y+height+16 <= 1024,"Saved island lacks required world-edge spacing")
        info = base.one([(c.tag,c.payload,c.offset) for c in children],"INFO")
        base.require(len(info) == 12 and info[0] in range(6),"Unknown saved island climate")
        climate = info[0]
        climates.add(climate)
        culture = culture_masks.get(ident,0)
        faction = faction_masks.get(ident,0)
        candidates = []
        terrain = heights(island)
        for index,row in enumerate(rows):
            if (row["width"],row["height"],row["climate"],row["cultures"],faction_bits[index]) != (width,height,climate,culture,faction):
                continue
            eligible = not row["excluded_native"] or faction
            size_match = size == "mixed" or ((faction_sizes[index] if faction else row["size_choices"])&bit)
            if not eligible or not size_match:
                continue
            source = (HERE/"alias_payload"/row["path"]) if faction else (base.ROOT/row["path"])
            original = source.read_bytes()
            base.require(base.sha(original) == row["sha256"],"Candidate source template fingerprint differs")
            source_root,_ = base.read_container(original)
            embedded = [c for c in base.chunks(original,16,source_root.end) if c.tag == "INSEL5"]
            base.require(len(embedded) == 1,"Source has ambiguous physical island")
            if heights(embedded[0]) == terrain:
                candidates.append(dict(index=index,path=row["path"],sha256=row["sha256"],size_choices=row["size_choices"],faction_size_choices=faction_sizes[index]))
        base.require(candidates,"Saved island does not match an eligible terrain/size/climate/culture template: "+str(ident))
        cases.append(dict(id=ident,width=width,height=height,climate=climate,culture_mask=culture,factions=faction,
                          height_grid_sha256=terrain,matching_eligible_source_templates=candidates))
    base.require(climates == set(range(6)),"Required climate is absent")
    return dict(expected_size=size,climate_ids=sorted(climates),observed_widths=sorted({c["width"] for c in cases}),
                compiled_catalogue_sha256=base.sha(catalogue),compiled_faction_metadata_sha256=base.sha(factions_header),
                all_saved_terrain_matches_eligible_size_templates=True,world_edge_spacing_verified=True,islands=cases)
