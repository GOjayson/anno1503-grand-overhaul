"""Automated private alias-policy checks; no game execution or installed writes."""
from pathlib import Path
import hashlib
import json
import struct
import package_alias_assets as alias

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def rejects(call, text=None):
    try:
        call()
    except ValueError as error:
        require(text is None or text in str(error), str(error))
        return
    raise RuntimeError("Unexpected validation acceptance")


manifest = json.loads((HERE/"FROZEN_ALIAS_MANIFEST.json").read_text())
require(hashlib.sha256((HERE/"FROZEN_ALIAS_MANIFEST.json").read_bytes()).hexdigest() == alias.FROZEN_MANIFEST_SHA256,
        "Frozen manifest changed")
for path, digest in manifest["files"].items():
    require(hashlib.sha256((HERE/path).read_bytes()).hexdigest() == digest, "Frozen input changed: "+path)
hashes = alias.validate_source_bundle(ROOT, HERE/"alias_payload", (HERE/"alias_runtime/world_catalogue.h").read_bytes())
require(len(hashes) == len(alias.introduced_files()) == 15, "Incomplete payload mapping")
require(len({name.casefold() for name in hashes}) == 15, "Case-insensitive payload collision")
for record in alias.RECORDS:
    source = (ROOT/record["source"]).read_bytes()
    copy = (HERE/"alias_payload"/record["copy_relative_path"]).read_bytes()
    name = alias.PAYLOAD_PREFIX+record["copy_relative_path"]
    alias.validate_data_payload(name, copy)
    alias.validate_source_copy(record, source, copy)
    rejects(lambda: alias.validate_data_payload(name, copy[:-1]+bytes([copy[-1]^1])), "fingerprint")
    rejects(lambda: alias.validate_data_payload(name.upper(), copy), "Unexpected pirate data payload")
    rejects(lambda: alias.validate_data_payload("assets/../"+record["copy_relative_path"], copy), "Unexpected pirate data payload")

record = alias.RECORDS[0]
data = (HERE/"alias_payload"/record["copy_relative_path"]).read_bytes()
position = alias.inspect_alias(data)
cases = []


def malformed(name, mutation, message):
    out = bytearray(data)
    mutation(out)
    rejects(lambda: alias.inspect_alias(bytes(out)), message)
    cases.append(name)


malformed("root overflow", lambda out: struct.pack_into("<I", out, 12, len(out)), "crosses parent")
malformed("truncated trailer", lambda out: out.pop(), "trailer length")
malformed("profile crosses root", lambda out: struct.pack_into("<I", out, position["profile_offset"]+12, len(out)), "crosses parent")
malformed("unexpected player prefix", lambda out: out.__setitem__(position["profile_offset"]+16, 1), "prefix")
malformed("top-level player HEAD", lambda out: out.__setitem__(slice(position["alias_offset"], position["alias_offset"]+6), b"HEAD\0\0"), "player HEAD")
malformed("wrong alias", lambda out: out.__setitem__(position["alias_offset"]+8, ord("X")), "ALIAS")
malformed("extended field overflow", lambda out: struct.pack_into("<HH", out, position["alias_offset"]+6, 0xffff, 0xffff), "crosses parent")
rejects(lambda: alias.inspect_alias(b""), "Truncated")
cases.append("empty SCP")
rejects(lambda: alias.validate_source_bundle(ROOT, HERE/"alias_payload", b"bad catalogue"), "catalogue differs")
result = dict(scope=__doc__,frozen_inputs_verified=len(manifest["files"]),valid_source_copy_cases=15,
              exact_data_payload_cases=15,changed_data_rejections=15,path_name_rejections=30,
              bounded_structure_rejections=cases,catalogue_mismatch_rejections=1,
              helper_sha256=hashlib.sha256((HERE/"package_alias_assets.py").read_bytes()).hexdigest(),
              actual_game_runs=0)
(HERE/"package_alias_test_results.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2))
