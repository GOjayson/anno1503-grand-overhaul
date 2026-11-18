"""Prepare local installer inputs from preserved complete mod packages."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anno1503_overhaul.packages import (
    prepare_bug_fixes_package, prepare_food_package, validate_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baselines", type=Path, default=ROOT / ".local/baselines")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-game", type=Path, required=True)
    parser.add_argument("--copy-game", type=Path)
    selection=parser.add_mutually_exclusive_group()
    selection.add_argument("--food-only", action="store_true", help="Prepare preserved Food 0.5 from public source without private World Settings inputs")
    selection.add_argument("--food06", action="store_true", help="Prepare Food 0.6 only for NEW worlds; no Food 0.5 save migration or combined World Settings profile")
    selection.add_argument("--food06-world", action="store_true", help="Prepare the separate Food 0.6 + World Settings development profile for NEW worlds")
    selection.add_argument("--world-only", action="store_true", help="Prepare World Settings with stock food and native host modules")
    selection.add_argument("--bug-fixes-only", action="store_true", help="Prepare the standalone localized Bug Fixes module")
    parser.add_argument("--bug-fixes", action="store_true", help="Include Bug Fixes with --food06, --food06-world, or --world-only")
    parser.add_argument("--compiler", type=Path, help="Reviewed Food 0.6 compiler (with --food06 or --food06-world)")
    args = parser.parse_args()
    if args.bug_fixes and not (args.food06 or args.food06_world or args.world_only):
        parser.error('--bug-fixes requires --food06, --food06-world, or --world-only; use --bug-fixes-only for the standalone module')
    if args.compiler is not None and not (args.food06 or args.food06_world):
        parser.error('--compiler is currently a Food 0.6 preparation option; use --food06')
    try:
        if args.food06_world:
            if args.copy_game is None:
                parser.error('Food 0.6 + World Settings requires --copy-game')
            from anno1503_overhaul.food_world_package import prepare_food_world_package
            root = prepare_food_world_package(args.baselines, args.output, args.source_game, args.copy_game,
                                               compiler_path=args.compiler,
                                               **({'bug_fixes_enabled': True} if args.bug_fixes else {}))
        elif args.food06:
            from anno1503_overhaul.food06_package import prepare_food06_package
            root = prepare_food06_package(args.output, args.source_game, args.copy_game,
                                           compiler_path=args.compiler,
                                           **({'city_statistics_guard': True} if args.bug_fixes else {}))
        elif args.bug_fixes_only:
            if args.copy_game is None:
                parser.error('Bug Fixes requires --copy-game')
            root = prepare_bug_fixes_package(args.output, args.source_game, args.copy_game)
        elif args.food_only:
            root = prepare_food_package(args.output, args.source_game, args.copy_game)
        else:
            if args.copy_game is None:
                parser.error('World Settings requires --copy-game')
            from anno1503_overhaul.world_options_package import prepare_options_package
            root=prepare_options_package(args.baselines,args.output,args.source_game,args.copy_game,
                                         food_enabled=not args.world_only,
                                         **({'bug_fixes_enabled': True} if args.bug_fixes else {}))
        result = validate_package(root, args.source_game)
        print(json.dumps({"package": str(root), "verified_files": len(result["files"]),
                          "kind": result["kind"], "runtime_sha256": result.get("runtime_sha256"),
                          "new_world_required": result.get("new_world_required"),
                          "bug_fixes_enabled": result.get("bug_fixes_enabled", args.bug_fixes or args.bug_fixes_only),
                          "game_executed": False}, indent=2))
    except (ValueError, RuntimeError, OSError) as exc:
        print("Cannot prepare installer package: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
