#!/usr/bin/env python3
"""Collect existing Anno 1503 crash details without changing game files."""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile

PACKAGE = Path(__file__).resolve().parent
VERSION = "1.0.0"
MAX_REPORT_BYTES = 1024 * 1024
WINDOW_SECONDS = 3 * 24 * 60 * 60


def decode_text(data: bytes):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16', errors='replace')
    if b'\0' in data[:200]:
        return data.decode('utf-16-le', errors='replace')
    return data.decode('utf-8-sig', errors='replace')


def redact(value: str, game: Path | None = None):
    replacements = [(str(game), '%GAME_DIR%')] if game is not None else []
    for key in ['USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'PROGRAMDATA']:
        if os.environ.get(key):
            replacements.append((os.environ[key], '%' + key + '%'))
    for old, new in sorted(replacements, key=lambda x: len(x[0]), reverse=True):
        if old:
            value = re.sub(re.escape(old), lambda m: new, value, flags=re.IGNORECASE)
    return value


def clean_tree(value, game):
    if isinstance(value, str):
        return redact(value, game)
    if isinstance(value, list):
        return [clean_tree(v, game) for v in value]
    if isinstance(value, dict):
        return {k: clean_tree(v, game) for k, v in value.items()}
    return value


def is_game(values):
    # Includes both compact and spaced names used by reports. Only matching
    # Anno 1503 records leave memory; unrelated application errors are discarded.
    return any(re.search(r'anno[ _-]*1503', v, re.IGNORECASE) for v in values)


def leaf_name(element):
    return element.tag.rsplit('}', 1)[-1]


def event_records(data: bytes, game=None):
    text = decode_text(data).strip()
    if not text:
        return []
    tree = ET.fromstring(text)
    events = [e for e in tree.iter() if leaf_name(e) == 'Event']
    result = []
    for event in events:
        system = next((e for e in event if leaf_name(e) == 'System'), None)
        body = next((e for e in event if leaf_name(e) == 'EventData'), None)
        if body is None:
            continue
        fields = {}
        for i, item in enumerate(body):
            fields[item.get('Name') or f'Field{i}'] = (item.text or '')[:8192]
        if not is_game(fields.values()):
            continue
        summary = {'fields': fields}
        if system is not None:
            for e in system:
                tag = leaf_name(e)
                if tag in {'EventID', 'EventRecordID', 'Level'}:
                    summary[tag] = e.text
                elif tag == 'Provider':
                    summary['provider'] = e.get('Name')
                elif tag == 'TimeCreated':
                    summary['time_utc'] = e.get('SystemTime')
        # Computer name, Security/UserID and raw XML are deliberately omitted.
        result.append(clean_tree(summary, game))
    return result


def collect_events(game):
    if os.name != 'nt':
        return {'status': 'unavailable', 'reason': 'Windows Event Log requires Windows', 'events': []}
    windir = Path(os.environ.get('SystemRoot', r'C:\Windows'))
    executable = windir / 'System32/wevtutil.exe'
    query = ('*[System[(EventID=1000 or EventID=1001 or EventID=1002) and '
             'TimeCreated[timediff(@SystemTime) <= 259200000]]]')
    command = [str(executable), 'qe', 'Application', '/q:' + query,
               '/rd:true', '/c:500', '/f:xml', '/e:Events', '/uni:true']
    try:
        run = subprocess.run(command, capture_output=True, timeout=25, check=False)
        if run.returncode:
            return {'status': 'unavailable', 'exit_code': run.returncode,
                    'reason': redact(decode_text(run.stderr).strip(), game), 'events': []}
        events = event_records(run.stdout, game)
        return {'status': 'ok' if events else 'no_matching_events', 'days': 3,
                'maximum_events_examined': 500, 'events': events}
    except (OSError, subprocess.TimeoutExpired, ET.ParseError) as exc:
        return {'status': 'unavailable', 'reason': redact(str(exc), game), 'events': []}


def wer_record(data, source, modified_utc):
    text = decode_text(data)
    values = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
    if not is_game(values.values()):
        return None
    # Standard WER signature pairs hold the application/module versions,
    # exception code and offset. Do not copy memory dumps or whole reports.
    selected = {k: v for k, v in values.items()
                if k in {'EventType', 'AppName', 'AppVersion', 'FriendlyEventName'}
                or re.fullmatch(r'Sig\[\d+\]\.(Name|Value)', k)}
    return {'source': source, 'modified_utc': modified_utc, 'fields': selected}


def collect_wer(game, roots=None):
    if roots is None:
        roots = []
        for key, label in [('LOCALAPPDATA', 'User'), ('PROGRAMDATA', 'System')]:
            value = os.environ.get(key)
            if value:
                for folder in ['ReportArchive', 'ReportQueue']:
                    roots.append((Path(value) / 'Microsoft/Windows/WER' / folder, label + ' WER ' + folder))
    records, issues, examined = [], [], 0
    cutoff = time.time() - WINDOW_SECONDS
    for directory, label in roots:
        try:
            if not directory.is_dir():
                continue
            # One known report level only. Never traverse general user folders.
            for folder in directory.iterdir():
                if examined >= 1000:
                    issues.append('Report scan reached its 1000-folder limit')
                    break
                examined += 1
                if not folder.is_dir():
                    continue
                path = folder / 'Report.wer'
                try:
                    if not path.is_file():
                        continue
                    info = path.stat()
                    if info.st_mtime < cutoff or info.st_size > MAX_REPORT_BYTES:
                        continue
                    record = wer_record(path.read_bytes(), label,
                        datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat())
                    if record:
                        records.append(clean_tree(record, game))
                except OSError:
                    issues.append(label + ': a report could not be read')
        except OSError:
            issues.append(label + ': directory unavailable')
    return {'reports': records, 'issues': issues, 'folders_examined': examined}


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def within(root, name):
    path = (root / name).resolve()
    path.relative_to(root.resolve())
    return path


def read_json(path):
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Metadata file exceeds collection limit')
    return json.loads(path.read_bytes())


def collect_state(game):
    spec = read_json(PACKAGE / 'food_patch.json')
    result = {'current_files': [], 'building_regions': [], 'mod_records': {}, 'issues': []}
    small_names = set(spec['files']) | {m['name'] for m in spec['native_modules']} | {'Anno1503.exe'}
    installed_hashes = {**{n:e['after_sha256'] for n,e in spec['files'].items()},
                        **{m['name']:m['after_sha256'] for m in spec['native_modules']}}
    original_hashes = {**{n:e['sources']['vanilla'] for n,e in spec['files'].items()},
                       **{m['name']:m['sources']['vanilla'] for m in spec['native_modules']}}
    for folder, filename in [('FishMod_Backup_0_1', 'backup-manifest.json'),
                             ('GameMeat_Test_Backup_0_2', 'manifest.json'),
                             ('FoodMarket_Backup_0_3', 'manifest.json'),
                             ('FoodMod_Backup_0_4', 'manifest.json'),
                             ('FoodMod_Backup_0_4_1', 'manifest.json'),
                             ('FoodMod_Backup_0_5', 'manifest.json')]:
        try:
            record = read_json(game / folder / filename)
            result['mod_records'][folder] = record
            if folder in {'FoodMarket_Backup_0_3', 'FoodMod_Backup_0_4', 'FoodMod_Backup_0_4_1', 'FoodMod_Backup_0_5'}:
                small_names.update(e['name'] for e in record.get('edits', []) if e.get('offset') is None)
            if folder in {'FoodMod_Backup_0_4', 'FoodMod_Backup_0_4_1', 'FoodMod_Backup_0_5'} and record.get('status') == 'installed':
                installed_hashes.update({e['name']:e['after_sha256'] for e in record.get('edits',[])
                    if e.get('offset') is None and (folder == 'FoodMod_Backup_0_5' or e['name'] not in installed_hashes)})
            if folder == 'FishMod_Backup_0_1':
                small_names.update(e['name'] for e in record.get('files', [])
                    if re.search(r'/fenster8?\.(inc|tex)$', e['name'], re.IGNORECASE))
        except (OSError, ValueError, KeyError) as exc:
            result['issues'].append(folder + ': ' + redact(str(exc), game))
    # Include installed UI pairs even without an older Fish backup record.
    folders=[game/'ToolGfx']
    if (game/'Languages').is_dir():
        folders += [p/'ToolGfx' for p in (game/'Languages').iterdir() if p.is_dir()]
    for folder in folders:
        for stem in ['fenster','fenster8']:
            for suffix in ['.inc','.tex']:
                path=folder/(stem+suffix)
                if path.is_file():small_names.add(path.relative_to(game).as_posix())
    for name in sorted(small_names):
        try:
            path = within(game, name)
            entry = {'name': name, 'size': path.stat().st_size, 'sha256': digest_file(path)}
            if name in original_hashes:
                entry['matches_vanilla'] = entry['sha256'] == original_hashes[name]
            if name in installed_hashes:
                entry['matches_combined_food_mod'] = entry['sha256'] == installed_hashes[name]
            result['current_files'].append(entry)
        except (OSError, ValueError) as exc:
            result['issues'].append(name + ': ' + redact(str(exc), game))
    for archive in spec['archives']:
        try:
            path = within(game, archive['name'])
            with path.open('rb') as stream:
                stream.seek(archive['region_offset'])
                data = stream.read(archive['region_size'])
            digest = hashlib.sha256(data).hexdigest()
            result['building_regions'].append({'name': archive['name'], 'file_size': path.stat().st_size,
                'offset': archive['region_offset'], 'length': len(data), 'sha256': digest,
                'matches_vanilla': digest == archive['sources']['vanilla'],
                'matches_combined_food_mod': digest == archive['after_sha256']})
        except (OSError, ValueError) as exc:
            result['issues'].append(archive['name'] + ': ' + redact(str(exc), game))
    return clean_tree(result, game)


def make_summary(report):
    events = report['windows_events']['events']
    lines = ['Anno 1503 combined Food Mod crash collection',
             'Windows game-related events: ' + str(len(events)),
             'Windows Error Reporting signatures: ' + str(len(report['windows_error_reports']['reports'])),
             'Event query: ' + report['windows_events']['status'], '']
    for event in events:
        lines.append('Event ' + str(event.get('EventID')) + ' at ' + str(event.get('time_utc')))
        for name, value in event['fields'].items():
            if value:
                lines.append('  ' + name + ': ' + value)
    for wer in report['windows_error_reports']['reports']:
        lines.append('WER report at ' + wer['modified_utc'])
        for name, value in wer['fields'].items():
            lines.append('  ' + name + ': ' + value)
    if not events and not report['windows_error_reports']['reports']:
        lines += ['No matching crash signature was found. This can happen if the game',
                  'handled the error itself, hung without a crash report, or Windows',
                  'removed/never created the report. File-state data is still included.']
    lines += ['', 'Current state:']
    for file in report['game_state']['current_files']:
        if file['name'] in {'AnnoGame.dll', 'AnnoWelt.dll', 'AnnoFrame.dll', 'View.dll', 'Data/BGruppen.dat'}:
            lines.append('  ' + file['name'] + ': matches combined Food Mod = ' + str(file.get('matches_combined_food_mod')))
    lines += ['', 'Only game-related event fields, WER signatures and game-file hashes',
              'are included. No saved games, memory dumps or game binaries are copied.',
              'No game, mod, registry or event-log settings were changed.']
    return '\n'.join(lines) + '\n'


def output_candidates(explicit):
    if explicit is not None:
        return [explicit]
    candidates = []
    if os.name == 'nt':
        # Resolve a redirected Desktop as well; never pass an empty path.
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buffer) == 0 and buffer.value:
            candidates.append(Path(buffer.value))
    candidates += [Path.home() / 'Desktop', Path.home() / 'Documents', PACKAGE, Path(tempfile.gettempdir())]
    return list(dict.fromkeys(candidates))


def write_report(report, candidates):
    name = 'Anno1503-Crash-Report-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%SZ') + '-' + uuid.uuid4().hex[:8] + '.zip'
    failures = []
    for directory in candidates:
        if not directory.is_dir():
            continue
        path = directory / name
        created = False
        try:
            with path.open('xb') as stream:
                created = True
                with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr('crash-report.json', json.dumps(report, indent=2, ensure_ascii=False))
                    archive.writestr('SUMMARY.txt', make_summary(report).replace('\n', '\r\n'))
            return path
        except OSError as exc:
            if created:
                path.unlink(missing_ok=True)
            failures.append(str(exc))
    raise OSError('Could not create the report ZIP in an available output folder: ' + '; '.join(failures))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-dir', type=Path, default=PACKAGE.parent)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    game = args.game_dir.resolve()
    print('Anno 1503 crash collector ' + VERSION)
    print('Reads existing reports without changing the game or launching it.')
    try:
        if not (game / 'Anno1503.exe').is_file():
            raise ValueError('Put anno1503_food_mod beside Anno1503.exe, then run COLLECT_CRASH.cmd inside it.')
        print('Checking current game and mod file fingerprints...')
        state = collect_state(game)
        print('Reading recent Anno 1503 Windows crash/hang events...')
        events = collect_events(game)
        print('Reading existing Anno 1503 Windows Error Reporting signatures...')
        reports = collect_wer(game)
        report = {'collector_version': VERSION, 'created_utc': datetime.now(timezone.utc).isoformat(),
                  'game_state': state, 'windows_events': events, 'windows_error_reports': reports}
        output = write_report(report, output_candidates(args.output_dir))
        print('Matching events: ' + str(len(events['events'])) + '; WER reports: ' + str(len(reports['reports'])))
        print('Created: ' + str(output))
        print('Attach that ZIP in the chat.')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
