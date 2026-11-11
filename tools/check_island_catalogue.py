"""Verify authored coastal groups against explicit, read-only native island roots."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from anno1503_overhaul.world_island_catalogue import template_resolver, validate_island_shapes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', action='append', required=True, type=Path,
                        help='Checked host or preserved private island assets; repeat for both.')
    args = parser.parse_args()
    catalogue = ROOT/'legacy/world_settings/developer/source/engine_resume/ai_food/experiment_runtime/world_catalogue.h'
    header = ROOT/'src/anno1503_overhaul/native/world_options/island_shapes.h'
    proof = validate_island_shapes(catalogue.read_bytes(), header.read_bytes(),
                                  template_resolver(*args.source_root))
    print(json.dumps({key: proof[key] for key in ('catalogue_sha256', 'shape_header_sha256',
        'template_count', 'unique_content_count', 'shape_count', 'game_executed', 'original_files_modified')}, indent=2))


if __name__ == '__main__':
    main()
