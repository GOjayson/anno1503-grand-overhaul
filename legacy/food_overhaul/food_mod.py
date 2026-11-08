#!/usr/bin/env python3
"""Unified Anno 1503 HE Food Mod: one install from vanilla or the previous prototypes."""
import argparse
import base64
import csv
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE / 'support'))
import formats as fm
import transforms as tr
import artwork
import transactions as tx

VERSION = tx.VERSION
FINAL_STATE = 'combined-0.5.0'
STATE_NAMES = {
    'vanilla': 'Vanilla History Edition',
    'fish-0.1.4': 'Fish mod 0.1.4',
    'game-0.2.2': 'Fish + Game Meat 0.2.2',
    'market-0.3-full': 'Six-slot market 0.3 with the full diet',
    'market-0.3-fish-only': 'Six-slot market 0.3 with Fish-only needs',
    'combined-0.4.0': 'Combined Food Mod 0.4.0',
    'combined-0.4.1': 'Combined Food Mod 0.4.1',
    FINAL_STATE: 'Combined Food Mod 0.5.0',
}


def assert_game_closed():
    if os.name != 'nt':
        return
    run = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Anno1503.exe', '/FO', 'CSV', '/NH'],
        capture_output=True, text=True, errors='replace', timeout=20, check=False)
    if run.returncode:
        raise fm.ModError('Could not check whether the game is running. Close it and retry.')
    if any(row and row[0].casefold() == 'anno1503.exe' for row in csv.reader(run.stdout.splitlines())):
        raise fm.ModError('Close Anno 1503 before installing or restoring the mod')


def detect_state(root, spec):
    digest = fm.file_sha(fm.safe_path(root, 'Data/BGruppen.dat'))
    matches = [state for state, value in spec['files']['Data/BGruppen.dat']['sources'].items() if value == digest]
    if not matches:
        raise fm.ModError('Unsupported resident definitions. Supported: vanilla, Fish 0.1.4, Game Meat 0.2.2, Food Market 0.3 and Combined 0.4.0/0.4.1.')
    # These three versions share data; their View fingerprints distinguish them.
    native = next(m for m in spec['native_modules'] if m['name'] == 'View.dll')
    view_digest = fm.file_sha(root / 'View.dll')
    selected = [s for s in matches if native['sources'][s] == view_digest]
    if not selected:
        raise fm.ModError('Native module does not match a supported setup: View.dll')
    matches = selected
    if len(matches) != 1:
        raise fm.ModError('Ambiguous installed food-mod state')
    return matches[0]


def apply_native(data, entry):
    digest = fm.sha(data)
    if digest == entry['after_sha256']:
        return data
    change = entry['changes'].get(digest)
    if not change:
        raise fm.ModError('Unsupported native module: ' + entry['name'])
    after = fm.patched_bytes(data, change['patches'])
    after += base64.b64decode(change['append_base64'], validate=True)
    after = after[:change['result_size']]
    if fm.sha(after) != entry['after_sha256']:
        raise fm.ModError('Native module verification failed: ' + entry['name'])
    return after


def transform_file(name, data, state, spec):
    item = spec['files'][name]
    if fm.sha(data) != item['sources'][state]:
        raise fm.ModError('File does not match the detected setup: ' + name)
    if name == 'Data/BGruppen.dat':
        if state == 'vanilla': data = fm.split_food_demand(data)
        if state in {'vanilla', 'fish-0.1.4'}: data = tr.add_definition(data)
        if state in {'vanilla', 'fish-0.1.4', 'game-0.2.2'}: data = tr.diet(data)
        elif state == 'market-0.3-fish-only':
            # Recreate the same diet blocks from Fish's unsplit total, using
            # the existing header and unlock definitions without adding IDs.
            header, tail = data.decode('cp1252').split('[BGRUPPE]', 1)
            populations, footer = tail.split('[BAUSTUFEN]', 1)
            pattern = re.compile(r'(?m)^  Ware:[ \t]+NAHRUNG[^\r\n]*\r?\n[ \t]*Menge:[ \t]+([0-9.]+)[^\r\n]*\r?\n[ \t]*Priority:[^\r\n]*\r?\n[ \t]*Force:[^\r\n]*\r?\n')
            from decimal import Decimal
            def split(match):
                return ''.join(re.sub(r'(Menge:[ \t]+)[0-9.]+', lambda m: m[1] + format((Decimal(match[1])*Decimal(fraction)).normalize(), 'f'), match[0].replace('NAHRUNG', good)) for good, fraction in tr.GOODS)
            populations, count = pattern.subn(split, populations)
            if count != 5: raise fm.ModError('Expected five Fish-only resident groups')
            data = (header + '[BGRUPPE]' + populations + '[BAUSTUFEN]' + footer).encode('cp1252')
    elif name in spec['text_files']:
        if state == 'vanilla': data = fm.update_labels(data)
        if state in {'vanilla', 'fish-0.1.4'}: data = tr.game_labels(data)
        if state in {'vanilla', 'fish-0.1.4', 'game-0.2.2'}: data = tr.food_labels(data)
    elif name in spec['icon_source_files']:
        if state == 'vanilla': data = fm.update_icon_sources(data)
        if state in {'vanilla', 'fish-0.1.4'}: data = tr.game_icon_sources(data)
        text = data.decode('cp1252')
        for group, old, new in [('WARENICONS_ROHSTOFF',22,23),('WARENICONS_ROHSTOFF_GREY',22,23),
                                ('WARENICONS_BAUMATERIAL',4,5),('WARENICONS_BAUMATERIAL_GREY',4,5)]:
            if state in {FINAL_STATE, 'combined-0.4.0', 'combined-0.4.1'}: continue
            pattern = re.compile(r'(Access:[ \t]*"' + group + r'"(?:(?!Access:).)*?Segments:[ \t]*)' + str(old) + r'([ \t]*,[ \t]*1)', re.S)
            text, count = pattern.subn(r'\g<1>' + str(new) + r'\2', text)
            if count != 1: raise fm.ModError('Could not update source icon count: ' + group)
        data = text.encode('cp1252')
    if fm.sha(data) != item['after_sha256']:
        raise fm.ModError('Food data transformation failed verification: ' + name)
    return data


def ui_pairs(root):
    folders = [root / 'ToolGfx']
    languages = root / 'Languages'
    if languages.is_dir():
        folders += [p / 'ToolGfx' for p in sorted(languages.iterdir()) if p.is_dir()]
    result = []
    for folder in folders:
        for stem in ['fenster', 'fenster8']:
            index, texture = folder / (stem + '.inc'), folder / (stem + '.tex')
            if not index.exists() and not texture.exists(): continue
            if not index.is_file() or not texture.is_file():
                raise fm.ModError('Incomplete UI pair: ' + str(index.relative_to(root)))
            result.append((index.relative_to(root).as_posix(), texture.relative_to(root).as_posix()))
    if ('ToolGfx/fenster.inc', 'ToolGfx/fenster.tex') not in result:
        raise fm.ModError('The main game UI was not found')
    return result


def transform_ui(index, texture, state, assets):
    expected = {'vanilla':(21,14,4),'fish-0.1.4':(21,15,4),'game-0.2.2':(22,15,4),
                'market-0.3-full':(23,15,5),'market-0.3-fish-only':(23,15,5),
                'combined-0.4.0':(23,15,5),'combined-0.4.1':(23,15,5),FINAL_STATE:(23,15,5)}[state]
    access = dict(fm.read_access(index))
    counts = tuple(access[g + '_GREY'] - access[g] for g in ['WARENICONS_ROHSTOFF','WARENICONS_BEDARF','WARENICONS_BAUMATERIAL'])
    if counts != expected:
        raise fm.ModError('UI icon counts do not match the detected setup: ' + str(counts))
    if state == 'vanilla': index, texture = fm.extend_fish_ui(index, texture, icon_asset=assets['fish'])
    if state in {'vanilla','fish-0.1.4'}: index, texture = tr.game_extend_ui(index, texture)
    if state in {'vanilla','fish-0.1.4','game-0.2.2'}: index, texture = tr.food_extend_ui(index, texture)
    return index, artwork.paint(index, texture, assets)


def build_edits(root, spec, progress=print):
    if spec.get('version') != VERSION:
        raise fm.ModError('Installer and specification versions differ')
    if not (root / 'Anno1503.exe').is_file():
        raise fm.ModError('Extract anno1503_food_mod beside Anno1503.exe first')
    if fm.file_sha(root / 'Anno1503.exe') != spec['exe_sha256']:
        raise fm.ModError('Unsupported Anno1503.exe version')
    state = detect_state(root, spec)
    progress('Detected: ' + STATE_NAMES[state])
    assets = artwork.load_assets(PACKAGE, spec['artwork_hashes'])
    edits = []
    for entry in spec['native_modules']:
        name = entry['name']; before = fm.safe_path(root, name).read_bytes()
        if fm.sha(before) != entry['sources'][state]:
            raise fm.ModError('Native module does not match the detected setup: ' + name)
        after = apply_native(before, entry)
        edits.append(tx.Edit(name, before, after, len(before)))
    for name in spec['files']:
        before = fm.safe_path(root, name).read_bytes()
        after = transform_file(name, before, state, spec)
        edits.append(tx.Edit(name, before, after, len(before)))
    for entry in spec['archives']:
        path = fm.safe_path(root, entry['name'])
        if path.stat().st_size != entry['source_size']:
            raise fm.ModError('Unsupported building archive size: ' + entry['name'])
        before = tx.read_region(path, entry['region_offset'], entry['region_size'])
        if fm.sha(before) != entry['sources'][state]:
            raise fm.ModError('Building definitions differ from the detected setup: ' + entry['name'])
        after = fm.patched_bytes(before, entry['changes'][fm.sha(before)], entry['region_offset'])
        if fm.sha(after) != entry['after_sha256']:
            raise fm.ModError('Building transformation failed verification: ' + entry['name'])
        edits.append(tx.Edit(entry['name'], before, after, path.stat().st_size, entry['region_offset']))
    for index_name, texture_name in ui_pairs(root):
        before, texture = (fm.safe_path(root, n).read_bytes() for n in [index_name, texture_name])
        progress('Preparing food artwork: ' + index_name)
        after, new_texture = transform_ui(before, texture, state, assets)
        edits += [tx.Edit(index_name, before, after, len(before)), tx.Edit(texture_name, texture, new_texture, len(texture))]
    if len({e.name.casefold() for e in edits}) != len(edits):
        raise fm.ModError('A file was selected twice')
    return state, [e for e in edits if e.before != e.after]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check','install','restore'])
    parser.add_argument('--game-dir', type=Path, default=PACKAGE.parent)
    args = parser.parse_args(argv); root = args.game_dir.resolve()
    print('Anno 1503 combined Food Mod ' + VERSION)
    try:
        if args.action == 'restore':
            assert_game_closed()
            state = tx.restore(root)
            print('Restored: ' + STATE_NAMES.get(state, state))
        else:
            spec = json.loads((PACKAGE / 'food_patch.json').read_bytes())
            state, edits = build_edits(root, spec)
            print('Validated ' + str(len(edits)) + ' file changes; all five food needs included.')
            record = tx.read_manifest(root)
            if state == FINAL_STATE and not edits:
                print('The combined Food Mod is already installed and verified.')
            elif args.action == 'install':
                assert_game_closed()
                if record and record.get('status') not in {'restored','rolled_back'}:
                    raise fm.ModError('An active combined Food Mod backup exists; use RESTORE.cmd before reinstalling')
                tx.install(root, edits, state)
                print('Installed. All five foods and Salt share one six-slot Food market.')
                if state in {'market-0.3-full', 'combined-0.4.0', 'combined-0.4.1'}:
                    print('Your existing full-diet save keeps the same goods and resident requirements.')
                else:
                    print('Start a NEW sandbox without AI for the full food requirements.')
                print('RESTORE.cmd returns to the setup detected above.')
        return 0
    except (OSError, ValueError, KeyError, struct.error, subprocess.SubprocessError, fm.ModError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
