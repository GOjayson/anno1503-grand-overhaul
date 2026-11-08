"""One verified backup and one rollback boundary for the complete food mod."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import tempfile
import formats as fm

VERSION = '0.5.0'
BACKUP = 'FoodMod_Backup_0_5'


@dataclass
class Edit:
    name: str
    before: bytes
    after: bytes
    file_size: int
    offset: int | None = None


def read_region(path, offset, length=None):
    if offset is None:
        return path.read_bytes()
    with path.open('rb') as stream:
        stream.seek(offset)
        return stream.read(length)


def write_region(path, offset, data):
    if offset is None:
        fm.atomic_write(path, data)
    else:
        with path.open('r+b') as stream:
            stream.seek(offset)
            if stream.write(data) != len(data):
                raise fm.ModError('Incomplete building metadata write')
            stream.flush()
            os.fsync(stream.fileno())


def save_manifest(directory, record):
    fm.atomic_write(directory / 'manifest.json', json.dumps(record, indent=2).encode('utf-8'))


def read_manifest(root):
    path = root / BACKUP / 'manifest.json'
    return json.loads(path.read_bytes()) if path.is_file() else None


def restore(root, progress=print):
    directory = root / BACKUP
    record = read_manifest(root)
    if not record or record.get('version') != VERSION:
        raise fm.ModError('No compatible combined Food Mod backup was found')
    entries = record['edits']
    if len({e['name'].casefold() for e in entries}) != len(entries):
        raise fm.ModError('Duplicate file in Food Mod backup')
    for entry in entries:
        original = fm.safe_path(directory / 'regions', entry['name'])
        target = fm.safe_path(root, entry['name'])
        if fm.file_sha(original) != entry['before_sha256']:
            raise fm.ModError('Food Mod backup is missing or changed: ' + entry['name'])
        if entry['offset'] is not None and target.stat().st_size != entry['file_size']:
            raise fm.ModError('Building archive size changed: ' + entry['name'])
        current = read_region(target, entry['offset'], entry['length'])
        if fm.sha(current) not in {entry['before_sha256'], entry['after_sha256']}:
            raise fm.ModError('Changed since installation; restore stopped: ' + entry['name'])
    record['status'] = 'restoring'
    save_manifest(directory, record)
    for entry in entries:
        progress('Restoring previous setup: ' + entry['name'])
        data = fm.safe_path(directory / 'regions', entry['name']).read_bytes()
        target = fm.safe_path(root, entry['name'])
        write_region(target, entry['offset'], data)
        if fm.sha(read_region(target, entry['offset'], entry['length'])) != entry['before_sha256']:
            raise fm.ModError('Restore verification failed: ' + entry['name'])
    record['status'] = 'restored'
    save_manifest(directory, record)
    return record['source_state']


def install(root, edits, source_state, progress=print):
    directory = root / BACKUP
    if directory.exists():
        previous = read_manifest(root)
        if not previous or previous.get('version') != VERSION or previous.get('status') not in {'restored', 'rolled_back'}:
            raise fm.ModError('A combined Food Mod backup is active; use its RESTORE.cmd before reinstalling')
        attempt = 1
        while directory.with_name(BACKUP + '.previous-' + str(attempt)).exists():
            attempt += 1
        os.replace(directory, directory.with_name(BACKUP + '.previous-' + str(attempt)))
    pending = Path(tempfile.mkdtemp(prefix=BACKUP + '.pending-', dir=root))
    record = dict(version=VERSION, source_state=source_state, status='prepared', edits=[])
    try:
        for edit in edits:
            path = fm.safe_path(root, edit.name)
            if path.stat().st_size != edit.file_size or read_region(path, edit.offset, len(edit.before)) != edit.before:
                raise fm.ModError('File changed during preflight: ' + edit.name)
            copy = fm.safe_path(pending / 'regions', edit.name)
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(edit.before)
            if fm.file_sha(copy) != fm.sha(edit.before):
                raise fm.ModError('Backup verification failed: ' + edit.name)
            record['edits'].append(dict(name=edit.name, offset=edit.offset, file_size=edit.file_size,
                length=len(edit.before), after_length=len(edit.after),
                before_sha256=fm.sha(edit.before), after_sha256=fm.sha(edit.after)))
        save_manifest(pending, record)
        os.replace(pending, directory)
    except BaseException:
        shutil.rmtree(pending, ignore_errors=True)
        raise
    touched = []
    try:
        for edit in edits:
            path = fm.safe_path(root, edit.name)
            if path.stat().st_size != edit.file_size or read_region(path, edit.offset, len(edit.before)) != edit.before:
                raise fm.ModError('File changed after backup: ' + edit.name)
            progress('Installing combined Food Mod: ' + edit.name)
            touched.append(edit)
            write_region(path, edit.offset, edit.after)
            expected_size = edit.file_size if edit.offset is not None else len(edit.after)
            if path.stat().st_size != expected_size or read_region(path, edit.offset, len(edit.after)) != edit.after:
                raise fm.ModError('Write verification failed: ' + edit.name)
        record['status'] = 'installed'
        save_manifest(directory, record)
    except BaseException as exc:
        failures = []
        for edit in reversed(touched):
            try:
                path = fm.safe_path(root, edit.name)
                write_region(path, edit.offset, edit.before)
                if path.stat().st_size != edit.file_size or read_region(path, edit.offset, len(edit.before)) != edit.before:
                    raise fm.ModError('Rollback verification failed')
            except BaseException as rollback_error:
                failures.append(edit.name + ': ' + str(rollback_error))
        record.update(status='rollback_failed' if failures else 'rolled_back', error=str(exc), rollback_errors=failures)
        try:
            save_manifest(directory, record)
        except OSError:
            pass
        if failures:
            raise fm.ModError('Installation failed; recovery files are in ' + str(directory) + '. ' + '; '.join(failures)) from exc
        raise fm.ModError('Installation failed; the previous setup was restored. ' + str(exc)) from exc
