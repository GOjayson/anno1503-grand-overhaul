"""Prepare local installer inputs from preserved complete mod packages."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anno1503_overhaul.packages import PackageError, prepare_package, prepare_food_package, validate_package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baselines", type=Path, default=ROOT / ".local/baselines")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-game", type=Path, required=True)
    parser.add_argument("--copy-game", type=Path)
    parser.add_argument("--food-only", action="store_true", help="Prepare Food from public source without private World Settings inputs")
    args = parser.parse_args()
    try:
        if args.food_only:
            root = prepare_food_package(args.output, args.source_game, args.copy_game)
        else:
            root = prepare_package(args.baselines, args.output, args.source_game, args.copy_game)
        result = validate_package(root, args.source_game)
        print(json.dumps({"package": str(root), "verified_files": len(result["files"]),
                          "kind": result["kind"], "runtime_sha256": result.get("runtime_sha256"),
                          "game_executed": False}, indent=2))
    except (PackageError, OSError) as exc:
        print("Cannot prepare installer package: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
