"""Read original inputs; write only an audit report beside this script.

This does not invoke the game, alter the runtime, or prove production/pathfinding.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / 'engine_audit'))
sys.path.insert(0, str(HERE.parent / 'world_data'))
from audit import Module
from scene_catalogue import read_island

EXPECTED_GAME = 'e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea'


def main():
    game = Module(str(ROOT / 'AnnoGame.dll'))
    assert hashlib.sha256(game.data).hexdigest() == EXPECTED_GAME
    assert game.pe.FILE_HEADER.Machine == 0x8664
    names = []
    for i in range(17):
        ptr = struct.unpack_from('<Q', game.image, 0x23400 + 8 * i)[0]
        at = ptr - game.base
        assert 0 <= at < len(game.image)
        names.append(game.image[at:at + 64].split(b'\0')[0].decode('cp1252'))
    assert names == ['GETREIDE', 'TABAKBAUM', 'GEWUERZBAUM', 'FLACHSBAUM',
                     'ZUCKERROHR', 'BAUMWOLLE', 'WEINTRAUBEN', 'KAKAOBAUM',
                     'HOPFENBAUM', 'SEIDENRAUPE', 'FARBBAUM', 'KRÄUTER',
                     'KARTOFFEL', 'GRAS', 'BAUM', 'FISCH', 'EISFISCH']
    catalogue = json.loads((HERE.parent / 'world_data/catalogue.json').read_text())
    summaries = []
    definitions = Counter()
    hashes = 0
    whale_bounds = 0
    for climate in range(6):
        ts = [t for t in catalogue['templates'] if t['climate_index'] == climate]
        fertile = []
        whales = []
        for t in ts:
            data = (ROOT / t['path']).read_bytes()
            assert hashlib.sha256(data).hexdigest() == t['sha256'], t['path']
            actual = read_island(data)
            assert actual['occurrences'] == t['occurrences'], t['path']
            hashes += 1
            fertile.append(sum(int(v) for k, v in t['land_fertility_low_nibble_histogram'].items() if int(k)))
            whales.append(sum(o['native_definition_id'] == 1559 for o in actual['occurrences']))
            for o in actual['occurrences']:
                definitions[o['native_definition_id']] += 1
                if o['native_definition_id'] == 1559:
                    # Welt5c074..5c0b4 reads serialized x/y/height and
                    # builds the native x/height/y vector consumed by b0/c0.
                    x, y, _ = o['floats']
                    assert t['x'] <= x < t['x'] + t['width'], t['path']
                    assert t['y'] <= y < t['y'] + t['height'], t['path']
                    assert climate in (0, 1), t['path']
                    whale_bounds += 1
        summaries.append(dict(climate=climate, templates=len(ts),
                              templates_with_fertile_land=sum(v > 0 for v in fertile),
                              fertile_land_min=min(fertile), fertile_land_max=max(fertile),
                              templates_with_ore=sum(bool(t['verified_mineral_counts']) for t in ts),
                              templates_with_mountain_entries=sum(bool(t['mine_entries']) for t in ts),
                              templates_with_whales=sum(v > 0 for v in whales), whales=sum(whales),
                              templates_with_native_profiles=sum(bool(t['cultures']) for t in ts)))
    assert hashes == 443 and whale_bounds == 367
    report = dict(scope='Read-only original data and native table audit; no game or production simulation.',
                  game_sha256=EXPECTED_GAME, game_machine='AMD64', growth_name_table_rva='0x23400',
                  growth_names=names, verified_template_hashes=hashes,
                  verified_source_whale_bounds=whale_bounds,
                  source_occurrence_definition_counts=dict(sorted(definitions.items())),
                  climates=summaries)
    (HERE / 'resource_coverage_audit.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'PASS: {hashes} original template hashes; {whale_bounds} whale bounds; 17 native growth names.')


if __name__ == '__main__':
    main()
