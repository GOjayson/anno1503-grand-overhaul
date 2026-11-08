"""Private subprocess entry point: legacy validation and output preparation only."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True


def _event(kind, **values):
    print(json.dumps({"event": kind, **values}, ensure_ascii=True), flush=True)


def prepare(kind: str, package: Path, game: Path, output: Path) -> dict:
    package, game = package.resolve(strict=True), game.resolve(strict=True)
    sys.path.insert(0, str(package))
    module_name = "world_mod" if kind == "world" else "food_mod"
    module = importlib.import_module(module_name)
    if Path(module.__file__).resolve() != package / (module_name + ".py"):
        raise RuntimeError("Unexpected legacy preparation module")
    spec_name = "world_patch.json" if kind == "world" else "food_patch.json"
    spec = json.loads((package / spec_name).read_bytes())
    if kind == "world":
        # Retain both the source-only guard and path-bound marked-copy policy.
        game = module.resolve_copy(spec, game, package=package)
    state, edits = module.build_edits(game, spec, progress=lambda text: _event("progress", message=str(text)))
    output.mkdir(parents=True, exist_ok=False)
    (output / "before").mkdir()
    (output / "after").mkdir()
    entries = []
    for index, edit in enumerate(edits):
        if not isinstance(edit.after, bytes) or edit.before is not None and not isinstance(edit.before, bytes):
            raise RuntimeError("Legacy preparation returned mutable or invalid payloads")
        entry = dict(name=edit.name, before_file=None, before_sha256=None,
                     after_file=f"after/{index:04d}.bin", after_sha256=hashlib.sha256(edit.after).hexdigest(),
                     file_size=edit.file_size, offset=edit.offset)
        if edit.before is not None:
            entry["before_file"] = f"before/{index:04d}.bin"
            entry["before_sha256"] = hashlib.sha256(edit.before).hexdigest()
            with (output / entry["before_file"]).open("xb") as stream:
                stream.write(edit.before)
        with (output / entry["after_file"]).open("xb") as stream:
            stream.write(edit.after)
        entries.append(entry)
    report = dict(schema_version=1, kind=kind, game_root=str(game),
                  package=str(package), prepared_dir=str(output), state=state, edits=entries)
    with (output / "prepared.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("food", "world"), required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = prepare(args.kind, args.package, args.game, args.output)
        _event("complete", prepared_dir=report["prepared_dir"], changes=len(report["edits"]))
        return 0
    except Exception as exc:
        _event("error", message=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
