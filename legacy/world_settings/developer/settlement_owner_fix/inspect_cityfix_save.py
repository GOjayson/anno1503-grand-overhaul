"""Strict read-only saved-faction inspection for a fingerprinted game test.

Saved player/controller/city records establish serialized ownership and options.
They do not establish controller activity, trading, combat or Food production.
"""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import re
import struct
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = next((p for p in HERE.parents if (p / "Anno1503.exe").is_file()
             and not (p / ".anno1503-worldsettings-test-copy.json").exists()), None)
if ROOT is None:
    raise RuntimeError("Place this developer inspector under the original Anno game folder")
WORK = ROOT / "WorldSettings_Work"
CATALOGUE_ROOT = next((p for p in (HERE / "engine_resume/ai_food/experiment_runtime",
                                  HERE / "candidate/engine_resume/ai_food/experiment_runtime")
                       if (p / "world_catalogue.h").is_file()), None)
if CATALOGUE_ROOT is None:
    raise RuntimeError("The fingerprinted local catalogue is missing")
sys.path[:0] = [str(HERE / "fixture_data"), str(WORK / "world_data")]
from scene_catalogue import read_container, chunks, island_chunks, geometry_errors, CULTURES



def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fields(payload, start):
    at = start
    result = []
    require(0 <= at <= len(payload), "Invalid native field start")
    while at < len(payload):
        require(len(payload)-at >= 8, "Truncated native field header")
        raw = payload[at:at+6]
        require(re.fullmatch(rb"[A-Z0-9_]{1,6}\x00*", raw) is not None, "Invalid native field tag")
        size = struct.unpack_from("<H", payload, at+6)[0]
        header = 8
        if size >= 0xff00:
            require(len(payload)-at >= 10, "Truncated extended native field header")
            size = ((size & 255) << 16) | struct.unpack_from("<H", payload, at+8)[0]
            header = 10
        stop = at+header+size
        require(stop <= len(payload), "Native field crosses parent")
        result.append((raw.rstrip(b"\0").decode("ascii"), payload[at+header:stop], at))
        at = stop
    return result


def one(items, tag):
    selected = [value for key, value, _ in items if key == tag]
    require(len(selected) == 1, "Expected one native field: "+tag)
    return selected[0]


def text(value):
    require(value and value.endswith(b"\0") and b"\0" not in value[:-1], "Invalid native text")
    return value[:-1].decode("ascii")


class NativeImage:
    """Bounded PE reader for the exact existing DLL instruction proof."""
    def __init__(self, path):
        self.data = path.read_bytes()
        require(len(self.data) >= 64 and self.data[:2] == b"MZ", "Invalid native DOS header")
        pe, = struct.unpack_from("<I", self.data, 60)
        require(pe <= len(self.data)-24 and self.data[pe:pe+4] == b"PE\0\0", "Invalid native PE header")
        self.machine, count = struct.unpack_from("<HH", self.data, pe+4)
        optional_size, = struct.unpack_from("<H", self.data, pe+20)
        optional = pe+24
        require(optional_size >= 112 and optional+optional_size+count*40 <= len(self.data), "Truncated native PE sections")
        self.magic, = struct.unpack_from("<H", self.data, optional)
        require(self.machine == 0x8664 and self.magic == 0x20b, "Native proof requires AMD64 PE32+")
        self.base, = struct.unpack_from("<Q", self.data, optional+24)
        image_size, headers_size = struct.unpack_from("<II", self.data, optional+56)
        require(headers_size <= len(self.data) and 0 < image_size <= 64*1024*1024, "Unsupported native image dimensions")
        image = bytearray(image_size)
        image[:headers_size] = self.data[:headers_size]
        ranges = []
        for i in range(count):
            at = optional+optional_size+i*40
            virtual_size, rva, raw_size, raw = struct.unpack_from("<IIII", self.data, at+8)
            require(raw_size <= len(self.data)-raw and raw_size <= image_size-rva, "Native section leaves file/image")
            require(all(rva+raw_size <= start or end <= rva for start,end in ranges), "Overlapping native image sections")
            image[rva:rva+raw_size] = self.data[raw:raw+raw_size]
            ranges.append((rva,rva+raw_size))
        self.image = bytes(image)


def template_path(relative, faction):
    if not faction:
        return ROOT/relative
    package = next((p for p in HERE.parents if (p/"world_patch.json").is_file()), None)
    choices = ([package/"assets"/relative] if package else []) + [
        WORK/"game_copy"/relative,
        WORK/"engine_resume/faction_options/pirate_transfer/alias_payload"/relative]
    source = next((p for p in choices if p.is_file()), None)
    require(source is not None, "The exact pirate template payload is missing")
    return source


def native_proof():
    w = NativeImage(ROOT/"AnnoWelt.dll")
    g = NativeImage(ROOT/"AnnoGame.dll")
    require(sha(w.data) == "ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9", "Original Welt fingerprint changed")
    require(sha(g.data) == "e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea", "Original Game fingerprint changed")
    for m in [w, g]:
        require(m.machine == 0x8664 and m.magic == 0x20b, "Expected original AMD64 PE32+")
    # This is the native culture dictionary read by Game E49A, not a culture
    # number inferred from textual order or ordinary-culture checkbox bits.
    enums = {}
    for ident, name in [(11, "PIRATEN"), (12, "VENECIA")]:
        pointer = struct.unpack_from("<Q", g.image, 0x23c90+ident*8)[0]-g.base
        require(0 <= pointer < len(g.image), "Culture dictionary pointer leaves image")
        require(g.image[pointer:pointer+len(name)+1] == name.encode()+b"\0", "Native culture dictionary differs")
        enums[name] = ident
    expected = {
        0x9bd5f: "4c8be9",       # parent player RCX -> R13 in PlayerLoad
        0x9d9c5: "423a8c18a4a50e00", # STADT2 dispatch against native tag
        0x9dac7: "498bd5",       # RDX = same parent player
        0x9dacd: "ff90f0010000", # island virtual create-city +1F0
        0x9e1eb: "4c8bf9",       # parent player RCX -> R15 in PlayerSave
        0x9fe37: "498b9f18030000", # iterate parent's city membership list
        0xa0052: "410fb7460a",   # saved city anchor X from figure+0A
        0xa0061: "6689442452",   # six-byte prefix +2
        0xa0080: "410fb7460c",   # saved city anchor Y from figure+0C
        0xa008e: "6689442454",   # six-byte prefix +4
    }
    for at, value in expected.items():
        require(w.image[at:at+len(bytes.fromhex(value))] == bytes.fromhex(value), "Native ownership instruction changed: "+hex(at))
    require(w.image[0xea5a4:0xea5ab] == b"STADT2\0", "Native city field tag changed")
    return dict(original_amd64_sha256={"AnnoWelt.dll": sha(w.data), "AnnoGame.dll": sha(g.data)},
                culture_dictionary_rva="0x23c90",culture_enums=enums,
                saved_city_owner="The STADT2 field belongs to its parent SPIELER state ID; native PlayerLoad passes that player as the city creator's owner.",
                ownership_instruction_bytes={hex(at): value for at,value in expected.items()},
                anchor_coordinate_scope="Full-world save anchors match the saved island coordinates; no packed ID3 building fields are decoded.")


def parse_save(data, expected_name, ai_count, pirates, venetians, island_count=24, spacing=0, difficulty="easy", cultures=255):
    require(difficulty in {"easy","medium","hard"}, "Unknown selected difficulty")
    require(type(spacing) is int and 0 <= spacing <= 256, "Invalid selected spacing")
    require(type(island_count) is int and 1 <= island_count <= 128, "Invalid selected island count")
    require(type(cultures) is int and 0 <= cultures <= 255, "Invalid selected culture mask")
    require(ai_count in range(4), "Selected AI count exceeds conservative supported range")
    stock_cpu_count = 3 if difficulty == "easy" else 4
    root, trailer = read_container(data)
    require(root.tag == "ANNOADDON1" and not trailer, "Expected one fully consumed native save root")
    parts = list(chunks(data, 16, root.end))
    alias = one([(p.tag,p.payload,p.offset) for p in parts], "ALIASNAME")
    require(len(alias) == 128 and alias.split(b"\0")[0] == expected_name.encode("ascii"), "Save alias differs")
    islands = [dict(zip(("x","y","width","height","id"), island_chunks(p)[0])) for p in parts if p.tag == "INSEL5"]
    require(len(islands) == island_count and {i["id"] for i in islands} == set(range(island_count)), "Island count or IDs differ")
    require(not geometry_errors(islands, 1024, 1024, spacing=spacing), "Saved islands overlap, leave bounds or violate spacing")
    require(all(i["x"]%8 == i["y"]%8 == 0 and i["width"] == i["height"] for i in islands), "Saved island grid differs")
    require(not [p for p in parts if p.tag in {"INSELLNK", "INSELDUMMY"}], "Save contains external island links")
    require(b"WorldSettings_" not in data and b"WorldSettingsIslands" not in data, "Save retains an external generated/template filename")
    basics = {}
    states = {}
    for chunk in parts:
        if chunk.tag != "SPIELER":
            continue
        require(len(chunk.payload) >= 8, "Truncated player prefix")
        version, ident = struct.unpack_from("<II", chunk.payload)
        require(version == 0 and ident < 32, "Unsupported player prefix")
        values = fields(chunk.payload, 8)
        if values and values[0][0] == "HEAD":
            require(ident not in basics, "Duplicate basic player")
            head = one(values,"HEAD")
            require(len(head) == 108, "Unsupported basic player HEAD")
            basics[ident] = dict(id=ident,type=struct.unpack_from("<I",head)[0],volk=text(one(values,"VOLK")),
                                alias=text(one(values,"ALIAS")),chunk_offset=chunk.offset)
        else:
            require(ident not in states, "Duplicate player state")
            controllers = [(value,offset) for tag,value,offset in values if tag == "COMP"]
            require(len(controllers) <= 1, "Ambiguous player controller")
            controller = None
            if controllers:
                value,offset = controllers[0]
                require(len(value) >= 8, "Truncated controller prefix")
                typ, owner = struct.unpack_from("<II",value)
                require(owner == ident, "Controller owner differs from parent")
                controller = dict(type=typ,owner=owner,field_offset=chunk.offset+16+offset,bytes=len(value))
                if len(value) > 8:
                    require(value.endswith(b"\0"), "Unterminated controller options")
                    options = {}
                    for line in value[8:].rstrip(b"\0").split(b"\0"):
                        key, separator, setting = line.partition(b"=")
                        require(separator and key, "Invalid saved controller option")
                        options.setdefault(key.decode("ascii"),[]).append(setting.decode("ascii"))
                    require(options.get("SUSPEND") in [["0"],["1"]], "Missing/ambiguous saved suspension")
                    controller["saved_suspend"] = int(options["SUSPEND"][0])
            cities = []
            for tag,value,offset in values:
                if tag != "STADT2":
                    continue
                require(len(value) >= 14 and value[6:12] == b"HEAD2\0", "Unsupported city state prefix")
                city_fields = fields(value,6)
                require(len(one(city_fields,"HEAD2")) == 64, "Unsupported city HEAD2")
                x,y = struct.unpack_from("<HH",value,2)
                matching = [i["id"] for i in islands if i["x"] <= x < i["x"]+i["width"] and i["y"] <= y < i["y"]+i["height"]]
                require(len(matching) == 1, "Saved city anchor does not identify one embedded island")
                cities.append(dict(owner_player_id=ident,field_offset=chunk.offset+16+offset,bytes=len(value),
                                   prefix_hex=value[:6].hex(),anchor_x=x,anchor_y=y,island_id=matching[0],sha256=sha(value)))
            states[ident] = dict(id=ident,controller=controller,cities=cities,chunk_offset=chunk.offset)
    require(set(states) == set(basics), "Basic/state player IDs differ")
    for ident,player in basics.items():
        controller = states[ident]["controller"]
        require(not controller or controller["type"] == player["type"], "Controller/basic type mismatch")
    natives = [p for p in basics.values() if p["type"] == 14]
    require(Counter(p["volk"] for p in natives) == Counter(name for i,name in enumerate(CULTURES) if cultures & (1<<i)), "Selected native cultures differ")
    for player in natives:
        require(len(states[player["id"]]["cities"]) == 1, "A selected native culture lacks its unique owned settlement")
    script = one([(p.tag,p.payload,p.offset) for p in parts], "BIGBROTHER").decode("ascii")
    mapper = {}
    for line in script.splitlines():
        match = re.fullmatch(r'"([^\"]+)" ([0-9]+)',line)
        if match:
            key,owner = match.groups()
            require(key not in mapper, "Duplicate script player mapping")
            mapper[key] = int(owner)
    specials = {}
    for label, enabled, typ, volk, nickname, enum in [
            ("pirates",pirates,15,"PIRATEN","PIRAT01",11),
            ("venetians",venetians,16,"VENECIA","VENEZIA01",12)]:
        players = [p for p in basics.values() if p["type"] == typ or p["volk"] == volk or p["alias"] == nickname]
        controller_states = [s for s in states.values() if s["controller"] and s["controller"]["type"] == typ]
        if not enabled:
            require(not players and not controller_states and nickname not in mapper, "Disabled faction remains serialized: "+label)
            specials[label] = dict(enabled=False,basic_records=0,controller_records=0,script_mapping_absent=True)
            continue
        require(len(players) == len(controller_states) == 1, "Expected one paired special faction: "+label)
        player = players[0]
        require((player["type"],player["volk"],player["alias"]) == (typ,volk,nickname), "Special faction identity differs")
        state = states[player["id"]]
        require(state is controller_states[0] and state["controller"].get("saved_suspend") == 0, "Special controller is missing/suspended")
        require(mapper.get(nickname) == player["id"], "Special script mapping differs")
        if label == "pirates":
            require(len(state["cities"]) == 1, "Expected the one generated pirate settlement")
        else:
            require(not state["cities"], "Unexpected map-bound Venetian settlement remains")
        specials[label] = dict(enabled=True,basic_player=player,volk_engine_enum=enum,controller=state["controller"],
                               owned_cities=state["cities"],owned_island_ids=sorted({c["island_id"] for c in state["cities"]}))
    cpus = []
    for player in basics.values():
        if player["type"] != 12:
            continue
        controller = states[player["id"]]["controller"]
        require(controller and controller.get("saved_suspend") in [0,1], "CPU controller suspension missing")
        cpus.append(dict(id=player["id"],saved_suspend=controller["saved_suspend"],controller_field_offset=controller["field_offset"]))
    enabled_ids = sorted(c["id"] for c in cpus if c["saved_suspend"] == 0)
    require(len(cpus) == stock_cpu_count and enabled_ids == list(range(1,ai_count+1)), "Saved selected CPU count/IDs differ")
    require(len(basics) == 2+stock_cpu_count+cultures.bit_count()+bool(pirates)+bool(venetians), "Unexpected stock-difficulty player count")
    return dict(save_name=expected_name,embedded_islands=islands,basic_players=list(basics.values()),
                saved_player_states=list(states.values()),saved_cpu_profiles=cpus,saved_enabled_cpu_ids=enabled_ids,
                special_factions=specials,script_player_mapper=mapper,
                checks=dict(full_native_root_and_fields_consumed=True,bounds_spacing_grid_and_ids=True,
                            no_external_template_or_generated_filename=True,exact_selected_native_cultures_and_owned_cities=True,
                            all_eight_native_cultures=(cultures == 255),
                            exact_selected_cpu_saved_enabled_count=True,separate_pirate_and_venetian_toggle_checks=True,
                            pirate_owned_city_and_unique_embedded_island=bool(pirates)))



def heights(payload):
    geometry, parts = island_chunks(payload)
    width,height = geometry[2:4]
    values = bytearray(width*height)
    covered = bytearray(width*height)
    for part in parts:
        if part.tag != "HEIGHT":
            continue
        require(len(part.payload) >= 6,"Truncated HEIGHT prefix")
        x,y,w,h = struct.unpack_from("<HHBB",part.payload)
        require(w and h and len(part.payload) == 6+w*h and x+w <= width and y+h <= height,"Invalid HEIGHT rectangle")
        for yy in range(h):
            for xx in range(w):
                at = (y+yy)*width+x+xx
                require(not covered[at],"Overlapping HEIGHT rectangles")
                covered[at] = 1
                values[at] = part.payload[6+yy*w+xx]
    require(all(covered),"HEIGHT rectangles do not cover saved island")
    return hashlib.sha256(values).hexdigest()


def inspect_size(data, report, size, spacing):
    require(size in {"small","medium","large","mixed"},"Unknown expected island-size group")
    catalogue = (CATALOGUE_ROOT/"world_catalogue.h").read_bytes()
    factions_header = (CATALOGUE_ROOT/"world_factions.h").read_bytes()
    require(sha(catalogue) == "2fe8bc332dff7491aeefe54bb3c219a6342fd1a8859cc5498f7b7ebe964df221","Compiled catalogue changed")
    require(sha(factions_header) == "b4668236f45fefc310412c1f8107cfdeae8c5f99874bcd0a2dd7c2b6da081764","Faction size metadata changed")
    rows = []
    for line in catalogue.decode().splitlines():
        match = re.fullmatch(r'\{("[^\"]+"),([0-9,]+),\{([0-9,]+)\}\},',line)
        if not match:
            continue
        values = [int(v) for v in match[2].split(",")]
        digest = bytes(int(v) for v in match[3].split(","))
        require(len(values) == 9 and len(digest) == 32,"Unsupported catalogue row")
        rows.append(dict(path=json.loads(match[1]).replace("\\","/"),width=values[0],height=values[1],climate=values[2],cultures=values[3],
                         excluded_native=values[6],size_choices=values[7],sha256=digest.hex()))
    require(len(rows) == 443,"Incomplete compiled template catalogue")
    def array(name):
        match = re.search(name+r'\[\]=\{([0-9,]+)\};',factions_header.decode())
        require(match is not None,"Missing faction size array")
        values = [int(v) for v in match[1].split(",")]
        require(len(values) == len(rows),"Faction size array differs")
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
                require(player["volk"] in CULTURES,"Unknown native city culture")
                culture_masks[island] = culture_masks.get(island,0)|(1<<CULTURES.index(player["volk"]))
            elif player["type"] == 15:
                faction_masks[island] = faction_masks.get(island,0)|1
    bit = {"small":1,"medium":2,"large":4,"mixed":0}[size]
    root,trailer = read_container(data)
    require(not trailer,"Unexpected save trailer")
    cases = []
    climates = set()
    for island in chunks(data,16,root.end):
        if island.tag != "INSEL5":
            continue
        geom, children = island_chunks(island)
        x,y,width,height,ident = geom
        require(x >= spacing and y >= spacing and x+width+spacing <= 1024 and y+height+spacing <= 1024,"Saved island lacks required world-edge spacing")
        info = one([(c.tag,c.payload,c.offset) for c in children],"INFO")
        require(len(info) == 12 and info[0] in range(6),"Unknown saved island climate")
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
            source = template_path(row["path"], faction)
            original = source.read_bytes()
            require(sha(original) == row["sha256"],"Candidate source template fingerprint differs")
            source_root,_ = read_container(original)
            embedded = [c for c in chunks(original,16,source_root.end) if c.tag == "INSEL5"]
            require(len(embedded) == 1,"Source has ambiguous physical island")
            if heights(embedded[0]) == terrain:
                candidates.append(dict(index=index,path=row["path"],sha256=row["sha256"],size_choices=row["size_choices"],faction_size_choices=faction_sizes[index]))
        require(candidates,"Saved island does not match an eligible terrain/size/climate/culture template: "+str(ident))
        cases.append(dict(id=ident,width=width,height=height,climate=climate,culture_mask=culture,factions=faction,
                          height_grid_sha256=terrain,matching_eligible_source_templates=candidates))
    require(climates == set(range(6)),"Required climate is absent")
    return dict(expected_size=size,climate_ids=sorted(climates),observed_widths=sorted({c["width"] for c in cases}),
                compiled_catalogue_sha256=sha(catalogue),compiled_faction_metadata_sha256=sha(factions_header),
                all_saved_terrain_matches_eligible_size_templates=True,world_edge_spacing_verified=True,islands=cases)


def inspect(save, digest, name="wscity1", ai_count=0, pirates=True, venetians=True, difficulty="easy", size="large", island_count=24, spacing=0, cultures=255):
    require(re.fullmatch(r"[0-9a-f]{64}",digest) is not None, "Exact expected SHA256 required")
    require(ai_count in range(4), "Expected CPU selection outside verified stock range")
    before = save.stat()
    data = save.read_bytes()
    after = save.stat()
    require((before.st_size,before.st_mtime_ns,before.st_ino) == (after.st_size,after.st_mtime_ns,after.st_ino), "Save changed while reading")
    require(sha(data) == digest, "Save fingerprint differs")
    proof = native_proof()
    require(difficulty in {"easy","medium","hard"},"Unknown operator-selected difficulty")
    report = parse_save(data,name,ai_count,pirates,venetians,island_count,spacing,difficulty,cultures)
    report["size_geometry_verification"] = inspect_size(data,report,size,spacing)
    report["checks"]["all_terrain_matches_selected_size_catalogue"] = True
    require(sha(save.read_bytes()) == digest, "Save changed during inspection")
    report.update(scope=__doc__,save_path=str(save),save_sha256=digest,bytes=len(data),native_ownership_proof=proof,
                  operator_selected_settings=dict(difficulty=difficulty,size=size,island_count=island_count,spacing=spacing,cultures=cultures,
                                                  ai_count=ai_count,pirates=pirates,venetians=venetians),
                  limitations=["Serialized SUSPEND and record presence do not prove current or future controller activity.",
                               "Venetian trading, pirate combat, diplomacy and Food production require actual game observation.",
                               "City ownership is decoded from the native player-state relationship; packed ID3 building ownership is not decoded.",
                               "Geometry/save checks supplement the runtime resource and ownership certificate; they do not replace it."],
                  game_executed_by_this_script=False,process_access_by_this_script=False,save_written_by_this_script=False)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save",type=Path,required=True)
    parser.add_argument("--sha256",required=True)
    parser.add_argument("--name",default="wscity1")
    parser.add_argument("--ai",type=int,default=0)
    parser.add_argument("--island-count",type=int,default=24)
    parser.add_argument("--spacing",type=int,default=0)
    parser.add_argument("--cultures",type=lambda value:int(value,0),default=255)
    parser.add_argument("--difficulty",choices=["easy","medium","hard"],default="easy")
    parser.add_argument("--size",choices=["small","medium","large","mixed"],default="large")
    parser.add_argument("--pirates",choices=["on","off"],default="on")
    parser.add_argument("--venetians",choices=["on","off"],default="on")
    parser.add_argument("--out",type=Path,default=HERE/"wscity1_save_results.json")
    args = parser.parse_args()
    result = inspect(args.save,args.sha256,args.name,args.ai,args.pirates=="on",args.venetians=="on",args.difficulty,args.size,args.island_count,args.spacing,args.cultures)
    args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in {"embedded_islands","basic_players","saved_player_states","size_geometry_verification"}},indent=2))
