"""Extract one native Venetian town and verify its existing80-tile stock loading dummy.

The stock Easy city stores its anchor in world coordinates. Its nested city
and island records are already island-local. Normalize the two container
prefixes only; preserve every nested city/terrain byte. Native SCP profile
loading supplies the selected island rectangle and selects the existing
Venetian player by the stock VENEZIA01 alias. No player HEAD or COMP is imported.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import sys
sys.dont_write_bytecode=True

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[2]
PRIVATE = PACKAGE / "developer/source/engine_resume/ai_food/experiment_runtime"
SOURCE = "Languages/Nl/Scenes/0010SingleEndlos/01_1024_easy_256.sze"
SOURCE_SHA = "3e0d2c72e1ae87b76cc817f0aead7198b4f0509cb11a5246463e338ccf060e05"
DUMMY_SOURCE = "Scenes/Islands/Nord/N_080x080_dummy.scp"
DUMMY_SHA = "e64de5cd9008a3675f26a29e8f0855a3a7eabdc237334a2f2aa4c9e9ee058f35"
TRAILER_SOURCE = "Scenes/Islands/Nord/N_064x064_0009_0B_Pirat.scp"
ASSET = "WorldSettingsIslands/Nord/V_080x080_Easy_Mercoli.scp"
DUMMY = "Scenes/Islands/Nord/N_080x080_dummy.scp"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def chunk(tag, payload):
    require(re.fullmatch(rb"[A-Z0-9_]{1,12}", tag.encode()) is not None, "Invalid chunk tag")
    return tag.encode().ljust(12, b"\0") + struct.pack("<I", len(payload)) + payload


def chunks(data, start, end):
    at = start
    require(0 <= start <= end <= len(data), "Invalid chunk extent")
    while at < end:
        require(end-at >= 16, "Truncated native chunk")
        tag = data[at:at+12]
        require(re.fullmatch(rb"[A-Z0-9_]{1,12}\0*", tag) is not None, "Invalid native chunk tag")
        size = struct.unpack_from("<I", data, at+12)[0]
        require(size <= end-at-16, "Native chunk crosses parent")
        yield tag.rstrip(b"\0").decode(), data[at+16:at+16+size], at, at+16+size
        at += 16+size
    require(at == end, "Unconsumed native chunk bytes")


def fields(data, start=8):
    require(0 <= start <= len(data), "Invalid field extent")
    at = start
    while at < len(data):
        require(len(data)-at >= 8, "Truncated native field")
        tag = data[at:at+6]
        require(re.fullmatch(rb"[A-Z0-9_]{1,6}\0*", tag) is not None, "Invalid native field tag")
        size = struct.unpack_from("<H", data, at+6)[0]
        head = 8
        if size >= 0xff00:
            require(len(data)-at >= 10, "Truncated extended field")
            size = ((size & 255) << 16) | struct.unpack_from("<H", data, at+8)[0]
            head = 10
        require(size <= len(data)-at-head, "Native field crosses parent")
        yield tag.rstrip(b"\0").decode(), data[at+head:at+head+size], at, head
        at += head+size
    require(at == len(data), "Unconsumed native field bytes")


def field(tag, payload, extended=False):
    require(len(tag) <= 6 and len(payload) < 0xff0000, "Unsupported field output")
    if len(payload) < 0xff00 and not extended:
        return tag.encode().ljust(6, b"\0") + struct.pack("<H", len(payload)) + payload
    return tag.encode().ljust(6, b"\0") + struct.pack("<HH", 0xff00 | (len(payload) >> 16), len(payload) & 65535) + payload


def envelope(data, scene=False):
    require(len(data) >= 16, "Truncated ANNO root")
    end = 16+struct.unpack_from("<I", data, 12)[0]
    require(data[:12].rstrip(b"\0") in {b"ANNO", b"ANNOADDON1"} and end <= len(data), "Unsupported ANNO root")
    if scene:
        require(end == len(data) and data[16:28] == b"SCENE".ljust(12, b"\0") and struct.unpack_from("<I", data, 28)[0] == end-32, "Unsupported scene envelope")
    return list(chunks(data, 32 if scene else 16, end)), data[end:]


def one(parts, tag):
    selected = [p for k, p, *_ in parts if k == tag]
    require(len(selected) == 1, "Expected exactly one "+tag)
    return selected[0]


def extract(scene, trailer):
    parts, extra = envelope(scene, True)
    require(not extra and len(trailer) == 60, "Unsupported native trailer")
    island = one(parts, "INSEL5")
    require(struct.unpack_from("<HHHHI", island) == (184, 288, 80, 80, 28), "Stock Venetian island geometry changed")
    terrain = list(chunks(island, 12, len(island)))
    require(one(terrain, "INFO") == bytes.fromhex("020100000000640000010000"), "Stock Venetian climate metadata changed")
    states = [p for k,p,*_ in parts if k == "SPIELER" and p[:8] == struct.pack("<II", 0, 5)]
    require(len(states) == 2, "Stock Venetian basic/state pair changed")
    basic = next(p for p in states if next(fields(p))[0] == "HEAD")
    state = next(p for p in states if next(fields(p))[0] != "HEAD")
    require(one(list(fields(basic)), "VOLK") == b"VENECIA\0" and one(list(fields(basic)), "ALIAS") == b"VENEZIA01\0", "Stock Venetian identity changed")
    require(struct.unpack_from("<I", one(list(fields(basic)), "HEAD"))[0] == 16, "Stock Venetian owner type changed")
    city = one(list(fields(state)), "STADT2")
    require(len(city) == 13198 and sha(city) == "2d243035e8ff687095c31b558e5001dab36bd27795767b3bba16ba58ca7fc1b0", "Stock Venetian city changed")
    require(city[:6] == struct.pack("<HHH", 0, 212, 321), "Stock city anchor changed")
    city_fields = list(fields(city, 6))
    require([p[0] for p in city_fields] == ["HEAD2", "ID3", "WARE", "BAUMAT", "VK", "EK", "PROD", "STAT2", "STST2"], "Stock city schema changed")
    require(len(one(city_fields, "HEAD2")) == 64, "Stock city HEAD2 changed")
    entries = list(fields(one(city_fields, "PROD"), 0))
    require(entries and all(k == "ENTRY" and len(v) in {4,5,14,18,20} for k,v,*_ in entries), "Unsupported city building entries")
    anchors = [struct.unpack_from("<HH", v) for k,v,*_ in entries]
    require(all(x < 80 and y < 80 for x,y in anchors), "City building anchor is not island-local")
    normalized_island = struct.pack("<HHHHI", 0, 0, 80, 80, 0) + island[12:]
    normalized_city = struct.pack("<HHH", 0, 28, 33) + city[6:]
    profile = bytes(8)+field("VOLK", b"VENECIA\0")+field("ALIAS", b"VENEZIA01\0")+field("STADT2", normalized_city, True)
    output = chunk("ANNO", chunk("WARETYPE", one(parts, "WARETYPE"))+chunk("INSEL5", normalized_island)+chunk("SPIELER", profile))+trailer
    return output, dict(source_island_geometry=[184,288,80,80,28], normalized_island_geometry=[0,0,80,80,0], source_city_anchor=[212,321], normalized_city_anchor=[28,33], nested_city_bytes=len(city)-6, nested_city_sha256=sha(city[6:]), unchanged_island_body_sha256=sha(island[12:]), city_building_entry_count=len(entries), island_local_building_anchors=[list(a) for a in anchors], controller_imported=False, player_head_imported=False, profile_alias="VENEZIA01", native_owner_type=16, native_culture=12)


def write_or_check(path, data, check):
    if check: require(path.read_bytes()==data, "Generated output differs: "+str(path))
    else:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir",type=Path,required=True)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    game=args.game_dir.resolve(strict=True)
    scene=(game/SOURCE).read_bytes();dummy=(game/DUMMY_SOURCE).read_bytes();pirate=(game/TRAILER_SOURCE).read_bytes()
    require(sha(scene)==SOURCE_SHA and sha(dummy)==DUMMY_SHA,"Original source fingerprint differs")
    _,trailer=envelope(pirate)
    require(trailer == bytes.fromhex("00000000000000000000000000000000000000001f000000564f4c4b00000800535049454c455200414c494153000c0044554d4d59504c4159455200"),"Native dummy trailer differs")
    sys.path.insert(0,str(PACKAGE/'support'))
    import package_world_assets as policy
    policy.validate_required_copy(game)
    asset,detail=extract(scene,trailer)
    files=[]
    for relative,data in [(ASSET,asset)]:
        payload="assets/"+relative
        write_or_check(PACKAGE/payload,data,args.check)
        files.append(dict(targetpath=relative,payloadpath=payload,sha256=sha(data),bytes=len(data)))
    catalogue=PRIVATE/"world_catalogue.h";text=catalogue.read_text()
    pattern=re.compile(r'^\{"([^"\r\n]*)",(\d+(?:,\d+){8}),\{([\d,]+)\}\},?$',re.M)
    rows=list(pattern.finditer(text));require(len(rows)in{443,444},"Unexpected catalogue count")
    row='{'+json.dumps(ASSET.replace('/','\\'))+',80,80,2,0,0,0,1,7,924,{'+','.join(map(str,bytes.fromhex(sha(asset))))+'}},'
    if len(rows)==444:
        require(rows[-1][1]==ASSET.replace('/','\\').replace('\\','\\\\'),"Unexpected appended template")
        text=text[:rows[-1].start()]+row+text[rows[-1].end():]
    else: text=text[:rows[-1].end()]+"\n"+row+text[rows[-1].end():]
    write_or_check(catalogue,text.replace('\n','\r\n').encode(),args.check)
    factions=PRIVATE/"world_factions.h";ft=factions.read_text()
    for name,value in [("wsTemplateFactions",2),("wsTemplateFactionSizes",7)]:
        p=re.compile(r'(static const unsigned char '+name+r'\[\]=\{)([\d,]+)(\};)')
        m=p.search(ft);require(m is not None,"Missing faction array")
        values=list(map(int,m[2].split(',')));require(len(values)in{443,444},"Unexpected faction count")
        if len(values)==444:require(values.pop()==value,"Unexpected appended faction")
        ft=ft[:m.start(2)]+','.join(map(str,values+[value]))+ft[m.end(2):]
    write_or_check(factions,ft.replace('\n','\r\n').encode(),args.check)
    manifest=dict(scope=__doc__,catalogue_count=444,template_index=443,files=files,required_copy_inputs=policy.required_copy_inputs(),source_files=[dict(path=SOURCE,sha256=sha(scene),bytes=len(scene)),dict(path=DUMMY_SOURCE,sha256=sha(dummy),bytes=len(dummy)),dict(path=TRAILER_SOURCE,sha256=sha(pirate),bytes=len(pirate))],transform=detail,loading_dummy_policy="Use the existing fingerprinted stock80Norddummy unchanged; bounded dimensions/climate/complete tiles/empty production validated. It is required input, never an introduced or replaced target.",fixed_special_island_size_exception="The native80x80Venetian town is selectable in all ordinary island size modes; it is never rescaled.",catalogue_sha256=sha(catalogue.read_bytes()),factions_sha256=sha(factions.read_bytes()),generator_sha256=sha(Path(__file__).read_bytes()),original_game_files_modified=False,actual_game_executed=False)
    write_or_check(HERE/"venetian_assets.json",(json.dumps(manifest,indent=2)+"\n").encode(),args.check)
    print(json.dumps(dict(passed=True,check_only=args.check,catalogue_count=444,files=files),indent=2))


if __name__=="__main__":main()
