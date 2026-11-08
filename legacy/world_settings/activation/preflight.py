"""Read-only activation preflight: exact source Food 0.5 and restorable copy."""
from pathlib import Path
import json
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import world_mod as mod


def verify(copy_root=None):
    spec = json.loads((PACKAGE / "world_patch.json").read_bytes())
    copy = mod.resolve_copy(spec, copy_root, package=PACKAGE)
    state, edits = mod.build_edits(copy, spec, progress=lambda _:None)
    if state != mod.FINAL_STATE or edits:
        raise mod.food.fm.ModError("Install this exact development package on its marked game copy before activation")
    source = Path(spec["original_game_root"]).resolve(strict=True)
    food_spec = json.loads((PACKAGE / "food_patch.json").read_bytes())
    state, edits = mod.food.build_edits(source, food_spec, progress=lambda _:None)
    if state != mod.food.FINAL_STATE or edits:
        raise mod.food.fm.ModError("Activation requires the original game to already contain exact Food 0.5; no source installation is performed")
    native = {entry["name"]:entry["sources"][mod.food.FINAL_STATE] for entry in food_spec["native_modules"]}
    native.update(spec["source_baselines"])
    native.update(spec["unchanged_native"])
    for name,digest in native.items():
        if mod.food.fm.file_sha(source/name) != digest:
            raise mod.food.fm.ModError("Unsupported original source module: " + name)
    return dict(source=source, copy=copy.resolve(), exe_sha256=spec["exe_sha256"],
                native_sha256=native, runtime_sha256=spec["payloads"]["native/AnnoWorldSettings.dll"],
                private_native_sha256={name:spec["payloads"][payload] for name,payload in spec["introduced_files"].items()
                                       if name.startswith("WorldSettingsAI/")},
                spec_sha256=mod.food.fm.file_sha(PACKAGE/"world_patch.json"))
