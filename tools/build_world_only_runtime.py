"""Build an uninstalled World-only runtime from exact stock inputs."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul.world_runtime_build import RuntimeBuildError, build_world_only_runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vanilla-game', type=Path, required=True)
    parser.add_argument('--tools', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--frozen-world-package', type=Path)
    parser.add_argument('--profile-output', type=Path)
    args = parser.parse_args()
    try:
        result = build_world_only_runtime(args.vanilla_game, args.tools, args.output,
                                          frozen_world_package=args.frozen_world_package,
                                          profile_output=args.profile_output,
                                          progress=lambda message: print(message, file=sys.stderr, flush=True))
        print(json.dumps({key: result[key] for key in ('built', 'runtime_path', 'runtime_sha256', 'output_root', 'profile_root',
                                                     'game_executed', 'installed', 'game_files_modified')}, indent=2))
        return 0
    except (RuntimeBuildError, OSError, ValueError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
