"""Build, verify, or launch a separate Culture Buildings prototype copy."""
from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from . import append_entries, archive_entries, categories, plan_culture_menu, require_endpoint_rules
from .culture_menu import LANGUAGES
from .fountain import _entry_id
from .full_cultures import save_targets
from .menu import ATLAS_HASHES, INDEX_HASHES
from .. import city_statistics, client_context, food_launch, installer, packages, world_runtime_build
from ..filesystem import (
    COPY_MARKER, atomic_json, checked_path, clone_game, file_sha, operation_lock,
    read_copy_marker, safe_child, update_copy_marker, validate_roots,
)
from ..food06_package import VERSION as FOOD_VERSION
from ..food_diet import FOOD06_BGRUPPEN_SHA256
from ..food_household import FOOD06_VIEW_SHA256
from ..food_supply import FOOD06_WELT_SHA256, FOOD_PROGRESSION_WELT_SHA256
from ..processes import require_game_closed


MANIFEST = ".culture-buildings.json"
RESIDENTS = "Data/BGruppen.dat"
WORLD = "AnnoWelt.dll"
FOOD_CITY_GUARD_HASHES = {
    # The first Food 0.6 build predates the combined housing progression update.
    FOOD06_WELT_SHA256: "20cda6bfdcd7b21b704e058f06aabba760b39acf8311621ec50823b4b8e76741",
    FOOD_PROGRESSION_WELT_SHA256: city_statistics.FOOD06_GUARDED_WELT_SHA256,
}
ARCHIVE_HASHES = {
    "off": {
        "Anlagen.dat": "bcbaf29c584bbd4d4a892500e28bfe3249c809f2c00a1463ae62804602faaec4",
        "Anlagen.addon": "b2317a5c24b8c9fe796cf40f3fedaefcfa30ad3f185df9e69b2dca6a03d8dd75",
        "Anlagen.classic": "0f356a649cc6eab98e8239d3077882383ddab9e983f3222458d74b83e5bf2c46",
    },
    "on": {
        "Anlagen.dat": "a0dc15e7671817adb8c44a7a563202b56a9ebc594ac3bdb3017fc98d27a52158",
        "Anlagen.addon": "f981f90abce0e0a73eee102bd50aa41431bde29233ebe62a787ad844c911504f",
        "Anlagen.classic": "d2e101e8d0d81400f92dd5762d12e260eff8963347c995e286a23267917716bd",
    },
}
MENU_FILES = {"View.dll", *(path.as_posix() for path in (*ATLAS_HASHES, *INDEX_HASHES, *LANGUAGES))}


@dataclass(frozen=True)
class Inputs:
    original: Path
    donor: Path
    profile: str
    executable: str
    source_modules: dict[str, str]
    donor_modules: dict[str, str]
    residents: str

    @property
    def city_guard_hash(self) -> str | None:
        return FOOD_CITY_GUARD_HASHES.get(self.donor_modules[WORLD]) if self.profile == "on" else None

    @property
    def output_files(self) -> set[str]:
        result = MENU_FILES | ARCHIVE_HASHES[self.profile].keys()
        if self.city_guard_hash is not None:
            result.add(WORLD)
        return result


def _check_file(root: Path, name: str, expected: str) -> None:
    if file_sha(safe_child(root, name, exists=True)) != expected:
        raise ValueError(f"{root.name} has an unrecognized {name}.")


def _inputs(original: Path, donor: Path, profile: str) -> Inputs:
    original = checked_path(original)
    donor = checked_path(donor)
    if profile not in ARCHIVE_HASHES:
        raise ValueError("Choose Food Overhaul on or off.")
    food = json.loads(food_launch._imported_source("legacy/world_settings/food_patch.json"))
    executable = food["exe_sha256"]
    _check_file(original, "Anno1503.exe", executable)
    _, source_modules = food_launch.verified_ubisoft_native(original, food)
    if profile == "on":
        marker = read_copy_marker(donor)
        record = installer._read_install(donor)
        selection = record.get("profile") if record else None
        features = selection.get("features") if isinstance(selection, dict) else None
        if (marker["phase"] != "installed" or Path(marker["source_root"]) != original
                or not record or record["status"] != "installed"
                or record.get("source_root") != str(original) or record.get("food_version") != FOOD_VERSION
                or not isinstance(features, dict)
                or features.get("food_overhaul") is not True or features.get("world_settings") is not False):
            raise ValueError("Choose a managed Food 0.6-only copy from this original game.")
        # Verify the installed files directly. A donor can predate unrelated
        # updates to the archived installer recipe without changing its bytes.
        world_hash = file_sha(safe_child(donor, WORLD, exists=True))
        if world_hash not in FOOD_CITY_GUARD_HASHES and world_hash not in FOOD_CITY_GUARD_HASHES.values():
            raise ValueError("The Food Overhaul donor has an unrecognized city statistics module.")
        donor_modules = {entry["name"]: entry["after_sha256"] for entry in food["native_modules"]}
        donor_modules.update({WORLD: world_hash, "View.dll": FOOD06_VIEW_SHA256,
                              "AnnoScene.dll": world_runtime_build.STOCK_SHA256["AnnoScene.dll"]})
        residents = FOOD06_BGRUPPEN_SHA256
    else:
        donor_modules = {entry["name"]: entry["sources"]["vanilla"] for entry in food["native_modules"]}
        donor_modules["AnnoScene.dll"] = world_runtime_build.STOCK_SHA256["AnnoScene.dll"]
        donor_modules.update({
            name: digest for name, digest in world_runtime_build.STOCK_SHA256.items()
            if name.lower().endswith(".dll") and (donor / name).is_file()
        })
        residents = food["files"][RESIDENTS]["sources"]["vanilla"]
    for name, expected in {
        "Anno1503.exe": executable, RESIDENTS: residents, **donor_modules, **ARCHIVE_HASHES[profile],
    }.items():
        _check_file(donor, name, expected)
    require_endpoint_rules(safe_child(donor, RESIDENTS, exists=True))
    return Inputs(original, donor, profile, executable, source_modules, donor_modules, residents)


def _stage(inputs: Inputs, staged: Path) -> dict:
    paths = {}
    for name in inputs.output_files:
        paths[name] = safe_child(inputs.donor, name, exists=True)
    before = {name: file_sha(path) for name, path in paths.items()}
    edits = {}

    def stage_file(name: str, content: bytes) -> None:
        target = staged / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        edits[name] = {"before": before[name], "after": sha256(content).hexdigest()}

    catalog = categories()
    for path, content in plan_culture_menu(inputs.donor, cultures=catalog, render_buildings=True).items():
        stage_file(path.as_posix(), content)
    declared_ids = set(save_targets())
    for name in ARCHIVE_HASHES[inputs.profile]:
        path = paths[name]
        additions = archive_entries(path)
        if {_entry_id(entry) for entry in additions} != declared_ids:
            raise ValueError(f"The building IDs in {path.name} differ from the menu.")
        stage_file(name, append_entries(path, additions))
    city_guard_hash = inputs.city_guard_hash
    if city_guard_hash is not None:
        guarded = city_statistics.bound_supply_statistics(paths[WORLD].read_bytes())
        if sha256(guarded).hexdigest() != city_guard_hash:
            raise ValueError("The city supply statistics fix differs from the reviewed Food Overhaul module.")
        stage_file(WORLD, guarded)
    if edits.keys() != paths.keys():
        raise ValueError("The staged Culture Buildings file list differs from the expected profile.")
    for name, preimage in before.items():
        _check_file(inputs.donor, name, preimage)
    return {
        "schema": 1,
        "food_overhaul": inputs.profile,
        "building_ids": sorted(declared_ids),
        "building_icons": sum(len(category.buildings) for category in catalog),
        "files": edits,
    }


def build(original: Path, donor: Path, output: Path, profile: str) -> Path:
    """Create and patch a new managed copy. The donor and original are read-only inputs."""
    inputs = _inputs(original, donor, profile)
    _, output = validate_roots(inputs.original, output, repo=packages.ROOT)
    validate_roots(inputs.donor, output, repo=packages.ROOT)
    if os.path.lexists(output):
        raise ValueError("Choose a new output folder for Culture Buildings.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".culture-buildings-", dir=output.parent) as temporary:
        staged = Path(temporary)
        report = _stage(inputs, staged)
        marker = clone_game(inputs.donor, output, repo=packages.ROOT)
        with operation_lock(output):
            try:
                for name, digest in {RESIDENTS: inputs.residents, **inputs.donor_modules}.items():
                    _check_file(output, name, digest)
                _check_file(output, "Anno1503.exe", inputs.executable)
                for name, edit in report["files"].items():
                    _check_file(output, name, edit["before"])
                for name, edit in report["files"].items():
                    os.replace(staged / name, safe_child(output, name, exists=True))
                    _check_file(output, name, edit["after"])
                atomic_json(output / MANIFEST, report)
                marker.update(source_root=str(inputs.original), donor_root=str(inputs.donor),
                              phase="installed", culture_buildings=True)
                atomic_json(output / COPY_MARKER, marker)
            except BaseException:
                update_copy_marker(output, phase="failed")
                raise
    return output


def verify(output: Path) -> tuple[Inputs, dict[str, str]]:
    """Verify a Culture Buildings copy and reconstruct the startup module fingerprints."""
    output = checked_path(output)
    marker = read_copy_marker(output)
    if marker.get("phase") != "installed" or marker.get("culture_buildings") is not True:
        raise ValueError("Select a built Culture Buildings copy.")
    report = packages._json(packages._read(output, MANIFEST), "Culture Buildings manifest")
    profile = report.get("food_overhaul")
    donor = marker.get("donor_root")
    if report.get("schema") != 1 or not isinstance(profile, str) or not isinstance(donor, str):
        raise ValueError("The Culture Buildings manifest is incomplete.")
    inputs = _inputs(Path(marker["source_root"]), Path(donor), profile)
    if marker["source_exe_sha256"] != inputs.executable:
        raise ValueError("The copy and original executable fingerprints differ.")
    edits = report.get("files")
    if (not isinstance(edits, dict) or edits.keys() != inputs.output_files
            or report.get("building_ids") != sorted(save_targets())
            or report.get("building_icons") != sum(len(category.buildings) for category in categories())):
        raise ValueError("The copy does not have the complete Culture Buildings catalogue.")
    city_guard_hash = inputs.city_guard_hash
    if city_guard_hash is not None and edits[WORLD] != {
        "before": inputs.donor_modules[WORLD], "after": city_guard_hash,
    }:
        raise ValueError("The copy has an unexpected Food Overhaul city statistics fix.")
    modules = dict(inputs.donor_modules)
    for name, edit in edits.items():
        if not isinstance(edit, dict) or edit.keys() != {"before", "after"}:
            raise ValueError(f"Invalid file identity in the Culture Buildings manifest: {name}")
        _check_file(inputs.donor, name, edit["before"])
        _check_file(output, name, edit["after"])
        if name in modules:
            modules[name] = edit["after"]
    for name, expected in {"Anno1503.exe": inputs.executable, RESIDENTS: inputs.residents, **modules}.items():
        _check_file(output, name, expected)
    return inputs, modules


def launch(output: Path, progress) -> int:
    """Relay an ordinary registered Ubisoft launch to the verified copy."""
    food_launch._require_source_host()
    require_game_closed()
    output = checked_path(output)
    inputs, modules = verify(output)
    uri = food_launch.find_registered_uri(inputs.original)
    source_probe, copy_probe = food_launch._make_probes({
        "package_root": Path(__file__).parent,
        "source_inputs": food_launch.menu_observer_inputs(inputs.original, inputs.executable, inputs.source_modules),
        "copy_inputs": food_launch.menu_observer_inputs(output, inputs.executable, modules),
    })
    try:
        process = client_context.start_game(uri, inputs.original, output, source_probe,
                                            copy_probe=copy_probe, progress=progress, timeout=150)
        return process.pid
    finally:
        source_probe.close()
        copy_probe.close()


def main(argv=None) -> int:
    parser = ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    builder = commands.add_parser("build", help="Create a new copy and generate its culture-building icons.")
    builder.add_argument("--original-game", type=Path, required=True)
    builder.add_argument("--donor", type=Path, required=True)
    builder.add_argument("--food-overhaul", choices=ARCHIVE_HASHES, required=True)
    for command in (builder, commands.add_parser("verify"), commands.add_parser("launch")):
        command.add_argument("--copy", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            print(build(args.original_game, args.donor, args.copy, args.food_overhaul))
        elif args.command == "verify":
            verify(args.copy)
            print(f"Verified Culture Buildings copy at {args.copy}.")
        else:
            pid = launch(args.copy, lambda message: print(message, file=sys.stderr, flush=True))
            print(f"Verified Culture Buildings main menu in process {pid}.")
    except (ValueError, RuntimeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
