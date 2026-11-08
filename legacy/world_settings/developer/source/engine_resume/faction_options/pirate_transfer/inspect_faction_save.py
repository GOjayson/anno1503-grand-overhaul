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
WORK = HERE.parents[2]
ROOT = WORK.parent
sys.path[:0] = [str(WORK/"world_data"), str(WORK/"engine_audit"), str(WORK/"_tools")]
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


def native_proof():
    from audit import Module
    w = Module(str(ROOT/"AnnoWelt.dll"))
    g = Module(str(ROOT/"AnnoGame.dll"))
    require(sha(w.data) == "ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9", "Original Welt fingerprint changed")
    require(sha(g.data) == "e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea", "Original Game fingerprint changed")
    for m in [w, g]:
        require(m.pe.FILE_HEADER.Machine == 0x8664 and m.pe.OPTIONAL_HEADER.Magic == 0x20b, "Expected original AMD64 PE32+")
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


def parse_save(data, expected_name, ai_count, pirates, venetians, island_count=24, spacing=16):
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
    require(Counter(p["volk"] for p in natives) == Counter(CULTURES), "Expected every native culture exactly once")
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
    require(len(cpus) == 4 and enabled_ids == list(range(1,ai_count+1)), "Saved selected CPU count/IDs differ")
    require(len(basics) == 14+bool(pirates)+bool(venetians), "Unexpected medium-difficulty player count")
    return dict(save_name=expected_name,embedded_islands=islands,basic_players=list(basics.values()),
                saved_player_states=list(states.values()),saved_cpu_profiles=cpus,saved_enabled_cpu_ids=enabled_ids,
                special_factions=specials,script_player_mapper=mapper,
                checks=dict(full_native_root_and_fields_consumed=True,bounds_spacing_grid_and_ids=True,
                            no_external_template_or_generated_filename=True,all_eight_native_cultures=True,
                            exact_selected_cpu_saved_enabled_count=True,separate_pirate_and_venetian_toggle_checks=True,
                            pirate_owned_city_and_unique_embedded_island=bool(pirates)))


def inspect(save, digest, name="ws8", ai_count=3, pirates=True, venetians=True):
    require(re.fullmatch(r"[0-9a-f]{64}",digest) is not None, "Exact expected SHA256 required")
    require(ai_count in range(4), "Expected CPU selection outside verified stock range")
    before = save.stat()
    data = save.read_bytes()
    after = save.stat()
    require((before.st_size,before.st_mtime_ns,before.st_ino) == (after.st_size,after.st_mtime_ns,after.st_ino), "Save changed while reading")
    require(sha(data) == digest, "Save fingerprint differs")
    proof = native_proof()
    report = parse_save(data,name,ai_count,pirates,venetians)
    require(sha(save.read_bytes()) == digest, "Save changed during inspection")
    report.update(scope=__doc__,save_path=str(save),save_sha256=digest,bytes=len(data),native_ownership_proof=proof,
                  operator_selected_settings=dict(difficulty="medium",size="mixed",island_count=24,spacing=16,cultures=255,
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
    parser.add_argument("--name",default="ws8")
    parser.add_argument("--ai",type=int,default=3)
    parser.add_argument("--pirates",choices=["on","off"],default="on")
    parser.add_argument("--venetians",choices=["on","off"],default="on")
    parser.add_argument("--out",type=Path,default=HERE/"ws8_save_results.json")
    args = parser.parse_args()
    result = inspect(args.save,args.sha256,args.name,args.ai,args.pirates=="on",args.venetians=="on")
    args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in {"embedded_islands","basic_players","saved_player_states"}},indent=2))
