"""Strict, standalone policy for the 15 private pirate-owner alias SCP copies.

No original game file is edited. Native payloads still require their AMD64
validation; only the exact data names returned here may use this validator.
"""
from pathlib import Path
import hashlib
import re
import struct

CATALOGUE_SHA256 = "5a41a82a47d314a89fb774a74945b3f7a2960083f66b17a055ff17abb48d30d4"
FROZEN_MANIFEST_SHA256 = "27e1cd2c6fa73cc4dc7eca6ee221fb33e855ba4ee54a96f47cbe70e4e870014b"
PAYLOAD_PREFIX = "assets/"
# Filled from the fingerprint-bound alias_manifest.json by the preparation step.
RECORDS = ({'template_index': 135,
  'source': 'Scenes/Islands/Nord/N_064x064_0009_0B_Pirat.scp',
  'source_sha256': 'f7436e56a6626a4f1d4a5d4dacce233a482af29fac9ff27c79eb59a7edb7aa6c',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_064x064_0009_0B_Pirat.scp',
  'copy_sha256': 'd436d1a1174bdc35dc7a0cc76fc71a1039d6dc2b3e53ab0ddc7dfd0667c6845c',
  'source_bytes': 30465,
  'copy_bytes': 30472,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 137,
  'source': 'Scenes/Islands/Nord/N_064x064_0011_3B_Piraten.scp',
  'source_sha256': 'ea5ef57fe5e45e56d6eacf4570202588e3d2d6945fc1368541c182600f82d937',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_064x064_0011_3B_Piraten.scp',
  'copy_sha256': 'a95ac1dbccc32540010b2a23e170dabfc91d2b06b3fc8356a4e9e9aba59da3ae',
  'source_bytes': 32024,
  'copy_bytes': 32031,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 138,
  'source': 'Scenes/Islands/Nord/N_064x064_0012_3B_Piraten.scp',
  'source_sha256': '3aab36cbd553405b5fbda5e8d2fa334df7897f7b3d5c15d7bb40ae2c1bb7d7d2',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_064x064_0012_3B_Piraten.scp',
  'copy_sha256': '0d1580231ce069dd4387a95a82cae33392be7cc5ce446dc8b244116c1796113e',
  'source_bytes': 29756,
  'copy_bytes': 29763,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 156,
  'source': 'Scenes/Islands/Nord/N_128x128_0001_4B_Piraten.scp',
  'source_sha256': '5f1961f0ad1145b655fdfb00efbcac960a82b5fbfd265ee4adb2fde41192f339',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_128x128_0001_4B_Piraten.scp',
  'copy_sha256': 'a5de7fe021e73c609a54d5412b06aca0c31a2cc6f925939e264aa1edc7eb04a8',
  'source_bytes': 115667,
  'copy_bytes': 115674,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 160,
  'source': 'Scenes/Islands/Nord/N_128x128_0003_2B_Piraten.scp',
  'source_sha256': 'a002e59cc3aa816770be915a325280aa21f9fdeaef2671a3dfff5c5dfd1e3bf8',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_128x128_0003_2B_Piraten.scp',
  'copy_sha256': '589aec1055202b621ef4a652a779550d004fdaa807b421d19cab77d0c1818858',
  'source_bytes': 100661,
  'copy_bytes': 100668,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 164,
  'source': 'Scenes/Islands/Nord/N_128x128_0005_1B_Piraten.scp',
  'source_sha256': '9a23fa81f6d30c39a328eb84c5e44848596b7abb5f3599d82e16deefb75d1e91',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_128x128_0005_1B_Piraten.scp',
  'copy_sha256': '678a6c0035e929948478c6fa7baaf0b3b4350c768bbcc8da867f8c6ba98c3b2a',
  'source_bytes': 101549,
  'copy_bytes': 101556,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 176,
  'source': 'Scenes/Islands/Nord/N_128x128_0012_1B_Piraten.scp',
  'source_sha256': '47de3bf02d518181cfa34e59c57c9fba81d99ba23c347e2a21f72e29be400ff6',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_128x128_0012_1B_Piraten.scp',
  'copy_sha256': '775ba5480685967ac032e643a32b2b5f92373f2c0804e6488ff7e47efe9a8b87',
  'source_bytes': 92477,
  'copy_bytes': 92484,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 181,
  'source': 'Scenes/Islands/Nord/N_128x128_0015_1B_Piraten.scp',
  'source_sha256': '1b2f6798a2f2970223897a936c127328401cb4c80cce6b53fd6e878860904e42',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_128x128_0015_1B_Piraten.scp',
  'copy_sha256': 'e21d7df8a4f46227d24339d9a2782c500d1419da813bdebc509b0c46dbe6516f',
  'source_bytes': 95429,
  'copy_bytes': 95436,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 190,
  'source': 'Scenes/Islands/Nord/N_128x128_0020_1B_Piraten.scp',
  'source_sha256': '5dcc88158391e1ad29f3f8437a2e4a006c8b666b9851fa7b9aa19d81a9aeea22',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_128x128_0020_1B_Piraten.scp',
  'copy_sha256': 'd5e1c70a2d1705fd7b0c4804b6c59e2ed3b52dbb5080ee3e83d22757f9b1bb89',
  'source_bytes': 126770,
  'copy_bytes': 126777,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 194,
  'source': 'Scenes/Islands/Nord/N_128x128_0022_1BPiraten.scp',
  'source_sha256': 'c06c94e962f1d88341e82e5be33f307f706db5f3af653da4b6658014423017d3',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_128x128_0022_1BPiraten.scp',
  'copy_sha256': 'c5ce23d37c778c78cf604e1a293293a0a0bc4401090d00f9e6b7d85971f2ea8e',
  'source_bytes': 113073,
  'copy_bytes': 113080,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 230,
  'source': 'Scenes/Islands/Nord/N_128x128_0068_2B_Piraten.scp',
  'source_sha256': 'b8f34e919dded30a4bb728294f8129a9fd7955f07007d3023c824abca247f650',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_128x128_0068_2B_Piraten.scp',
  'copy_sha256': '04934651d43449e2f8994699beed37fff788840e393f873e3bfd104b84d74a65',
  'source_bytes': 118834,
  'copy_bytes': 118841,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 231,
  'source': 'Scenes/Islands/Nord/N_128x128_0069_1B_Piraten.scp',
  'source_sha256': 'e835ba47154f7e271c5c0f39d4f2db11ddda8c685099956c2701c3ca380cfd81',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_128x128_0069_1B_Piraten.scp',
  'copy_sha256': '796e5e8099b138c1e99bed571cb83ef306fe78cab3b1c328b745cf7f07541c55',
  'source_bytes': 113598,
  'copy_bytes': 113605,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 233,
  'source': 'Scenes/Islands/Nord/N_128x128_0072_2B_Piraten.scp',
  'source_sha256': '493036f56183e39e06bae98128238588bb3f972ae0ace502d96ca84cdcd9a784',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_128x128_0072_2B_Piraten.scp',
  'copy_sha256': '0e98d6233264cb959c4219dfa4011bc42e75db77d4db7cf20935cc6b086d373f',
  'source_bytes': 129571,
  'copy_bytes': 129578,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 234,
  'source': 'Scenes/Islands/Nord/N_128x128_0073_1B_Piraten.scp',
  'source_sha256': 'fcd43faf2164ee737d029bf95ceb9fffd890b6bbaf47340740d7418a97b0ebff',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_128x128_0073_1B_Piraten.scp',
  'copy_sha256': '9c85bac68f999683f754f109d16a31fed337676678de760b188bfbb0118260bf',
  'source_bytes': 135512,
  'copy_bytes': 135519,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'},
 {'template_index': 242,
  'source': 'Scenes/Islands/Nord/N_256x256_0014_2B_Piraten.scp',
  'source_sha256': 'c3c5f34969c8d1cbafe2d0990a8674c9161c4898295dd674a8d004c723f3b012',
  'copy_relative_path': 'WorldSettingsIslands/Nord/N_256x256_0014_2B_Piraten.scp',
  'copy_sha256': 'fcc508db0ba3e930b0834dd33c53351141c82dacd978e5ac42e8e66e99bf73ce',
  'source_bytes': 414626,
  'copy_bytes': 414633,
  'top_level_player_head_absent': True,
  'old_alias': '',
  'new_alias': 'PIRAT01',
  'unchanged_trailer_sha256': '614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39'})


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def introduced_files():
    return {r["copy_relative_path"]: PAYLOAD_PREFIX+r["copy_relative_path"] for r in RECORDS}


def data_payload_hashes():
    return {PAYLOAD_PREFIX+r["copy_relative_path"]: r["copy_sha256"] for r in RECORDS}


def _chunk(data, at, end):
    _require(0 <= at <= end <= len(data) and end-at >= 16, "Truncated SCP chunk header")
    raw = data[at:at+12]
    _require(re.fullmatch(rb"[A-Z0-9_]{1,12}\x00*", raw) is not None, "Invalid SCP chunk tag")
    length = struct.unpack_from("<I", data, at+12)[0]
    stop = at+16+length
    _require(stop <= end, "SCP chunk crosses parent")
    return raw.rstrip(b"\0").decode("ascii"), at+16, stop


def _fields(data, begin, end):
    _require(end-begin >= 8 and data[begin:begin+8] == bytes(8), "Unexpected player profile prefix")
    at = begin+8
    values = []
    while at < end:
        _require(end-at >= 8, "Truncated player profile field")
        raw = data[at:at+6]
        _require(re.fullmatch(rb"[A-Z0-9_]{1,6}\x00*", raw) is not None, "Invalid player profile field tag")
        length = struct.unpack_from("<H", data, at+6)[0]
        header = 8
        if length >= 0xff00:
            _require(end-at >= 10, "Truncated extended profile length")
            length = ((length & 255) << 16) | struct.unpack_from("<H", data, at+8)[0]
            header = 10
        stop = at+header+length
        _require(stop <= end, "Player profile field crosses parent")
        values.append((raw.rstrip(b"\0").decode("ascii"), at, header, stop, data[at+header:stop]))
        at = stop
    return values


def inspect_alias(data, expected_alias=b"PIRAT01\0"):
    """Bounded structural inspection; returns offsets only inside the profile."""
    tag, start, end = _chunk(data, 0, len(data))
    _require(tag in {"ANNO", "ANNOADDON1"}, "Unsupported SCP container")
    _require(len(data)-end == 60, "Unexpected SCP trailer length")
    found = []
    at = start
    while at < end:
        child_tag, begin, stop = _chunk(data, at, end)
        if child_tag == "SPIELER":
            fs = _fields(data, begin, stop)
            cultures = [f[4] for f in fs if f[0] == "VOLK"]
            if cultures == [b"PIRATEN\0"]:
                _require(not any(f[0] == "HEAD" for f in fs), "Named pirate profile must not import a player HEAD")
                aliases = [f for f in fs if f[0] == "ALIAS"]
                _require(len(aliases) == 1 and aliases[0][2] == 8 and aliases[0][4] == expected_alias,
                         "Unexpected pirate profile ALIAS")
                _require(any(f[0] == "STADT2" and f[4] for f in fs), "Pirate profile has no settlement")
                found.append({"root_end": end, "profile_offset": at,
                              "profile_size": stop-begin, "alias_offset": aliases[0][1],
                              "alias_end": aliases[0][3]})
        at = stop
    _require(len(found) == 1, "Expected exactly one PIRATEN profile")
    return found[0]


def validate_data_payload(name, data):
    records = [r for r in RECORDS if PAYLOAD_PREFIX+r["copy_relative_path"] == name]
    _require(len(records) == 1, "Unexpected pirate data payload: "+name)
    record = records[0]
    _require(len(data) == record["copy_bytes"] and _sha(data) == record["copy_sha256"],
             "Pirate alias payload fingerprint differs: "+name)
    inspect_alias(data)
    _require(_sha(data[-60:]) == record["unchanged_trailer_sha256"], "Pirate dummy trailer changed")
    return record


def validate_source_copy(record, source, copy):
    """Prove the entire copy is exactly the permitted ALIAS/length adjustment."""
    _require(record in RECORDS, "Unexpected pirate source record")
    _require(len(source) == record["source_bytes"] and _sha(source) == record["source_sha256"],
             "Pirate original source fingerprint differs: "+record["source"])
    position = inspect_alias(source, b"\0")
    at, stop = position["alias_offset"], position["alias_end"]
    out = bytearray(source[:at] + b"ALIAS\0" + struct.pack("<H", 8) + b"PIRAT01\0" + source[stop:])
    struct.pack_into("<I", out, 12, position["root_end"]-16+7)
    struct.pack_into("<I", out, position["profile_offset"]+12, position["profile_size"]+7)
    _require(bytes(out) == copy, "Pirate data edit changes bytes beyond ALIAS and containing lengths")
    validate_data_payload(PAYLOAD_PREFIX+record["copy_relative_path"], copy)


def validate_source_bundle(source_root, data_root, catalogue):
    """Build-time verification against originals, private assets and new header."""
    _require(len(RECORDS) == 15 and len(introduced_files()) == 15, "Pirate data policy is incomplete")
    _require(_sha(catalogue) == CATALOGUE_SHA256, "Pirate catalogue differs from reviewed data-only change")
    for record in RECORDS:
        source = (Path(source_root)/record["source"]).read_bytes()
        copy = (Path(data_root)/record["copy_relative_path"]).read_bytes()
        validate_source_copy(record, source, copy)
    return data_payload_hashes()
