"""Build candidate in-game World options; publication requires reviewed pins."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul.world_options_build import build_options_runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('world-only', 'food-world'), required=True)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--tools', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    report = build_options_runtime(args.profile, args.game, args.tools, output=args.output, publish=args.publish)
    print(json.dumps({key: report[key] for key in ('built', 'profile', 'generator_id', 'runtime_path',
          'runtime_sha256', 'matches_reviewed_runtime', 'output_root', 'game_executed', 'installed')}, indent=2))


if __name__ == '__main__':
    main()
