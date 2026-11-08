"""Standalone policy for the dev7 town payload and its existing stock loading dummy.

These exact SCP names are data, never PE modules. The stock game sources are
read-only. A named Venetian profile imports neither a player HEAD nor COMP.
"""
from pathlib import Path
import hashlib
import re
import struct

ASSET = "WorldSettingsIslands/Nord/V_080x080_Easy_Mercoli.scp"
DUMMY = "Scenes/Islands/Nord/N_080x080_dummy.scp"
SOURCE = "Languages/Nl/Scenes/0010SingleEndlos/01_1024_easy_256.sze"
SOURCE_SHA256 = "3e0d2c72e1ae87b76cc817f0aead7198b4f0509cb11a5246463e338ccf060e05"
DUMMY_SOURCE = DUMMY
DUMMY_SOURCE_SHA256 = "e64de5cd9008a3675f26a29e8f0855a3a7eabdc237334a2f2aa4c9e9ee058f35"
RECORDS = (
    {"targetpath": ASSET, "payloadpath": "assets/"+ASSET, "sha256": "4570885e5cd49af264be541c3f0a57ba55e53dacd3bde58a32fc19ef13c9ee5d", "bytes":44399},
)
TRAILER = bytes.fromhex("00000000000000000000000000000000000000001f000000564f4c4b00000800535049454c455200414c494153000c0044554d4d59504c4159455200")


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def introduced_files():
    return {r["targetpath"]:r["payloadpath"] for r in RECORDS}


def data_payload_hashes():
    return {r["payloadpath"]:r["sha256"] for r in RECORDS}


def required_copy_inputs():
    """Existing inspected data required in the copy; never an introduced target."""
    return {DUMMY:DUMMY_SOURCE_SHA256}


def validate_required_copy(root):
    """Read and validate the stock80 dummy, without changing or backing it up."""
    for relative,expected in required_copy_inputs().items():
        data=(Path(root)/relative).read_bytes()
        _require(len(data)==27289 and _sha(data)==expected,"Required stock world data fingerprint differs: "+relative)
        inspect_dummy(data)
    return required_copy_inputs()


def _chunks(data, start, end):
    _require(0 <= start <= end <= len(data), "Invalid SCP extent")
    while start < end:
        _require(end-start >= 16, "Truncated SCP chunk")
        tag=data[start:start+12]
        _require(re.fullmatch(rb"[A-Z0-9_]{1,12}\0*",tag) is not None,"Invalid SCP chunk tag")
        n=struct.unpack_from("<I",data,start+12)[0]
        _require(n <= end-start-16,"SCP chunk crosses parent")
        yield tag.rstrip(b"\0").decode(),data[start+16:start+16+n]
        start+=16+n
    _require(start==end,"SCP child bytes remain")


def _fields(data, start):
    _require(0 <= start <= len(data),"Invalid SCP field extent")
    while start<len(data):
        _require(len(data)-start>=8,"Truncated SCP field")
        tag=data[start:start+6]
        _require(re.fullmatch(rb"[A-Z0-9_]{1,6}\0*",tag) is not None,"Invalid SCP field tag")
        n=struct.unpack_from("<H",data,start+6)[0];head=8
        if n>=0xff00:
            _require(len(data)-start>=10,"Truncated extended SCP field")
            n=((n&255)<<16)|struct.unpack_from("<H",data,start+8)[0];head=10
        _require(n<=len(data)-start-head,"SCP field crosses parent")
        yield tag.rstrip(b"\0").decode(),data[start+head:start+head+n]
        start+=head+n
    _require(start==len(data),"SCP field bytes remain")


def _one(items, tag):
    values=[p for k,p in items if k==tag]
    _require(len(values)==1,"Expected one "+tag)
    return values[0]


def _root(data, scene=False):
    _require(len(data)>=16 and data[:12].rstrip(b"\0") in {b"ANNO",b"ANNOADDON1"},"Unsupported SCP root")
    end=16+struct.unpack_from("<I",data,12)[0]
    _require(end<=len(data),"SCP root crosses file")
    if scene:
        _require(end==len(data) and data[16:28]==b"SCENE".ljust(12,b"\0") and struct.unpack_from("<I",data,28)[0]==end-32,"Unsupported stock scene root")
    return list(_chunks(data,32 if scene else 16,end)),data[end:]


def _tile_grid(parts, tag, width, height, unit):
    result=bytearray(width*height*unit);seen=bytearray(width*height)
    for key,tile in parts:
        if key!=tag:continue
        _require(len(tile)>=6,"Truncated "+tag+" tile")
        x,y,w,h=struct.unpack_from("<HHBB",tile)
        _require(w and h and x+w<=width and y+h<=height and len(tile)==6+w*h*unit,"Unsupported "+tag+" tile")
        for yy in range(h):
            for xx in range(w):
                index=(y+yy)*width+x+xx
                _require(not seen[index],"Overlapping "+tag+" tiles")
                seen[index]=1
                result[index*unit:(index+1)*unit]=tile[6+(yy*w+xx)*unit:6+(yy*w+xx+1)*unit]
    _require(all(seen),"Incomplete "+tag+" coverage")
    return bytes(result)


def inspect_venetian(data):
    parts,trailer=_root(data)
    _require([k for k,p in parts]==["WARETYPE","INSEL5","SPIELER"] and trailer==TRAILER,"Unexpected Venetian SCP contents")
    island=_one(parts,"INSEL5")
    _require(len(island)>=12 and struct.unpack_from("<HHHHI",island)==(0,0,80,80,0),"Venetian island is not normalized80x80")
    terrain=list(_chunks(island,12,len(island)))
    _require(_one(terrain,"INFO")==bytes.fromhex("020100000000640000010000"),"Venetian climate metadata differs")
    heights=_tile_grid(terrain,"HEIGHT",80,80,1)
    _tile_grid(terrain,"GFXID",80,80,2)
    _require(len(_one(terrain,"FRUCHTBAR"))==6400,"Venetian fertility dimensions differ")
    profile=_one(parts,"SPIELER")
    _require(profile[:8]==bytes(8),"Unexpected named Venetian profile prefix")
    values=list(_fields(profile,8))
    _require([k for k,p in values]==["VOLK","ALIAS","STADT2"],"Venetian profile must import only culture/alias/city")
    _require(_one(values,"VOLK")==b"VENECIA\0" and _one(values,"ALIAS")==b"VENEZIA01\0","Venetian profile identity differs")
    city=_one(values,"STADT2")
    _require(len(city)==13198 and city[:6]==struct.pack("<HHH",0,28,33),"Venetian city anchor differs")
    fs=list(_fields(city,6))
    _require([k for k,p in fs]==["HEAD2","ID3","WARE","BAUMAT","VK","EK","PROD","STAT2","STST2"],"Venetian city schema differs")
    entries=list(_fields(_one(fs,"PROD"),0));anchors=[]
    for k,v in entries:
        _require(k=="ENTRY" and len(v) in {4,5,14,18,20},"Unsupported Venetian building entry")
        x,y=struct.unpack_from("<HH",v)
        _require(x<80 and y<80,"Venetian building leaves local island")
        anchors.append((x,y))
    _require(len(anchors)==73,"Venetian building count differs")
    return dict(profile=profile,city=city,island=island,heights=heights,building_anchors=anchors,terrain=terrain)


def inspect_dummy(data):
    parts,trailer=_root(data)
    _require(not trailer and _one(parts,"INSEL4")==struct.pack("<HHI",80,80,0),"Unexpected80x80dummy envelope")
    info=_one(parts,"INFO")
    _require(len(info)==12 and info[0]==2 and struct.unpack_from("<H",info,6)[0]==100,"Dummy grid metadata differs")
    _require(len(_one(parts,"FRUCHTBAR"))==6400,"Dummy fertility dimensions differ")
    for tag,unit in [("HEIGHT",1),("GFXID",2),("GELAENDE",0),("PROD2",0)]:_tile_grid(parts,tag,80,80,unit)
    _require(not any(k in {"SPIELER","INSEL5"} for k,p in parts),"Dummy contains a player or full-world island")
    _one(parts,"STAEDTE");_require(_one(parts,"LOCKED")==b"\0","Dummy lock differs")
    return parts


def validate_data_payload(payload_name,data):
    records=[r for r in RECORDS if r["payloadpath"]==payload_name]
    _require(len(records)==1,"Unexpected world data payload: "+payload_name)
    record=records[0]
    _require(len(data)==record["bytes"] and _sha(data)==record["sha256"],"World data payload fingerprint differs: "+payload_name)
    inspect_venetian(data)
    return record


def validate_source_bundle(game,payload_root,catalogue_bytes):
    scene=(Path(game)/SOURCE).read_bytes()
    _require(_sha(scene)==SOURCE_SHA256,"Original world data source fingerprint differs")
    validate_required_copy(game)
    # As with the pirate module, payload_root denotes the assets directory.
    payload_root=Path(payload_root)
    new={r["targetpath"]:(payload_root/r["targetpath"]).read_bytes() for r in RECORDS}
    for r in RECORDS:validate_data_payload(r["payloadpath"],new[r["targetpath"]])
    info=inspect_venetian(new[ASSET]);parts,_=_root(scene,True)
    original_island=_one(parts,"INSEL5")
    _require(info["island"][12:]==original_island[12:],"Venetian terrain changed beyond normalized prefix")
    states=[p for k,p in parts if k=="SPIELER" and p[:8]==struct.pack("<II",0,5) and next(_fields(p,8))[0]!="HEAD"]
    _require(len(states)==1,"Original Venetian state is ambiguous")
    original_city=_one(list(_fields(states[0],8)),"STADT2")
    _require(info["city"][6:]==original_city[6:],"Venetian city changed beyond normalized anchor")
    _require(_one(_root(new[ASSET])[0],"WARETYPE")==_one(parts,"WARETYPE"),"Venetian goods dictionary changed")
    rows=re.findall(rb'^\{"([^"\r\n]*)",(\d+(?:,\d+){8}),\{([\d,]+)\}\},?$',catalogue_bytes.replace(b'\r\n',b'\n'),re.M)
    _require(len(rows)==444 and rows[-1][0]==ASSET.replace('/','\\').replace('\\','\\\\').encode(),"Venetian catalogue entry is missing")
    _require(rows[-1][1]==b"80,80,2,0,0,0,1,7,924" and bytes(map(int,rows[-1][2].split(b','))).hex()==RECORDS[0]["sha256"],"Venetian catalogue metadata differs")
    return data_payload_hashes()
