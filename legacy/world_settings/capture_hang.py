#!/usr/bin/env python3
"""Capture numeric thread locations from the user's hung Anno 1503 process."""
from __future__ import annotations

import argparse
import csv
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import io
import json
import ntpath
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

import collect_crash as cc

VERSION = '1.0.0'


class CaptureError(Exception):
    pass


def parse_snapshot(data: bytes):
    """Read standard minidump streams; export no strings from stack memory."""
    def span(at, size):
        if at < 0 or size < 0 or at + size > len(data):
            raise CaptureError('A minidump record exceeds the file boundary')
        return data[at:at + size]

    def unpack(fmt, at):
        return struct.unpack(fmt, span(at, struct.calcsize(fmt)))

    if len(data) < 32 or data[:4] != b'MDMP':
        raise CaptureError('Windows did not produce a valid minidump')
    count, directory = unpack('<II', 8)
    if count > 4096:
        raise CaptureError('Unreasonable minidump stream count')
    streams = {}
    for i in range(count):
        kind, size, at = unpack('<III', directory + i * 12)
        span(at, size)
        # Only these streams are consumed. Ignore reserved/unknown entries,
        # including repeated unused directory slots.
        if kind not in {3, 4, 7, 17}:
            continue
        if kind in streams:
            raise CaptureError('Duplicate minidump stream type')
        streams[kind] = (at, size)
    if 7 not in streams or unpack('<H', streams[7][0])[0] != 9:
        raise CaptureError('This collector expects the 64-bit x86 History Edition process')
    if 3 not in streams or 4 not in streams:
        raise CaptureError('The snapshot is missing thread/module streams')

    at, length = streams[4]
    module_count, = unpack('<I', at)
    if module_count > 10000 or 4 + module_count * 108 > length:
        raise CaptureError('Invalid minidump module table')
    modules = []
    for i in range(module_count):
        base, size, checksum, stamp, name_rva = unpack('<QIIII', at + 4 + i * 108)
        name_size, = unpack('<I', name_rva)
        if name_size > 32768 or name_size % 2:
            raise CaptureError('Invalid minidump module name')
        name = ntpath.basename(span(name_rva + 4, name_size).decode('utf-16-le', errors='replace'))
        modules.append({'name': name, 'base': base, 'image_size': size,
                        'checksum': checksum, 'timestamp': stamp})

    def locate(address):
        for m in modules:
            if m['base'] <= address < m['base'] + m['image_size']:
                return {'module': m['name'], 'rva': hex(address - m['base'])}
        return {'module': None, 'address': hex(address)}

    times = {}
    if 17 in streams:
        at, length = streams[17]
        header, stride, entries = unpack('<III', at)
        if header < 12 or stride < 64 or entries > 100000 or header + stride * entries > length:
            raise CaptureError('Invalid minidump thread-info table')
        for i in range(entries):
            ident, flags, error, status, created, exited, kernel, user, start, affinity = unpack('<IIIIQQQQQQ', at + header + i * stride)
            times[ident] = {'flags': flags, 'dump_error': hex(error),
                           'cpu_100ns': kernel + user, 'start': locate(start)}

    at, length = streams[3]
    thread_count, = unpack('<I', at)
    if thread_count > 100000 or 4 + thread_count * 48 > length:
        raise CaptureError('Invalid minidump thread table')
    threads = []
    for i in range(thread_count):
        ident, suspend, priority_class, priority, teb, stack_start, stack_size, stack_rva, ctx_size, ctx_rva = unpack('<IIIIQQIIII', at + 4 + i * 48)
        thread = {'id': ident, 'priority': priority}
        if ident in times:
            thread.update(times[ident])
        if ctx_size < 256:
            thread['context_error'] = 'Thread context unavailable'
            threads.append(thread)
            continue
        span(ctx_rva, ctx_size)
        flags, = unpack('<I', ctx_rva + 48)
        if not flags & 0x100000:
            thread['context_error'] = 'Unexpected context architecture'
            threads.append(thread)
            continue
        rsp, = unpack('<Q', ctx_rva + 152)
        rip, = unpack('<Q', ctx_rva + 248)
        thread['instruction'] = locate(rip)
        thread['stack_module_values'] = []
        # These are module-valued stack words, NOT an unwound call stack.
        # Restrict export to module/RVA pairs and positions; never export raw
        # stack bytes, strings or addresses outside loaded modules.
        if stack_size:
            stack = span(stack_rva, stack_size)
            offset = max(0, rsp - stack_start)
            offset = (offset + 7) & ~7
            for position in range(offset, min(len(stack) - 7, offset + 65536), 8):
                address, = struct.unpack_from('<Q', stack, position)
                location = locate(address)
                if location['module']:
                    thread['stack_module_values'].append({'stack_offset': hex(stack_start + position - rsp), **location})
                    if len(thread['stack_module_values']) >= 128:
                        break
        threads.append(thread)
    return {'modules': modules, 'threads': threads,
            'stack_interpretation': 'Module-valued stack words are candidates, not unwound call frames.'}


def compare_samples(samples):
    if len(samples) < 2:
        return []
    first = {t['id']: t for t in samples[0]['threads']}
    result = []
    for thread in samples[-1]['threads']:
        old = first.get(thread['id'])
        if old is None:
            continue
        entry = {'id': thread['id'], 'first_instruction': old.get('instruction'),
                 'last_instruction': thread.get('instruction')}
        if 'cpu_100ns' in old and 'cpu_100ns' in thread and not ((old.get('flags', 0) | thread.get('flags', 0)) & 0x09):
            entry['cpu_delta_ms'] = max(0, thread['cpu_100ns'] - old['cpu_100ns']) / 10000
        result.append(entry)
    return sorted(result, key=lambda t: t.get('cpu_delta_ms', -1), reverse=True)


class WindowsCapture:
    def __init__(self, game):
        if os.name != 'nt':
            raise CaptureError('Run CAPTURE_MARKET_HANG.cmd on the Windows PC running Anno 1503')
        if struct.calcsize('P') != 8:
            raise CaptureError('A 64-bit Python installation is required to capture the 64-bit game')
        self.game = game.resolve()
        system = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32'
        self.kernel = ctypes.WinDLL(str(system / 'kernel32.dll'), use_last_error=True)
        self.debug = ctypes.WinDLL(str(system / 'dbghelp.dll'), use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.debug.MiniDumpWriteDump.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.HANDLE, wintypes.DWORD,
                                               ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        self.debug.MiniDumpWriteDump.restype = wintypes.BOOL
        run = subprocess.run([str(system / 'tasklist.exe'), '/FI', 'IMAGENAME eq Anno1503.exe', '/FO', 'CSV', '/NH'],
                             capture_output=True, timeout=20, check=False)
        if run.returncode:
            raise CaptureError('Windows could not list the running Anno 1503 process')
        pids = []
        for row in csv.reader(io.StringIO(cc.decode_text(run.stdout))):
            if len(row) > 1 and row[0].casefold() == 'anno1503.exe' and row[1].isdigit():
                pids.append(int(row[1]))
        if not pids:
            raise CaptureError('Anno1503.exe is not running. Start a new game, leave it stuck on the loading screen, then run this capture.')
        if len(pids) != 1:
            raise CaptureError('More than one Anno1503.exe is running. Leave only the stuck game open and retry.')
        self.pid = pids[0]
        self.handle = self.kernel.OpenProcess(0x0400 | 0x0010, False, self.pid)
        if not self.handle:
            error = ctypes.get_last_error()
            raise CaptureError(f'Cannot read the game process (Windows error {error}). Run the collector with the same privilege level as the game.')
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(buffer))
            if not self.kernel.QueryFullProcessImageNameW(self.handle, 0, buffer, ctypes.byref(length)):
                raise CaptureError('Could not verify the running game path')
            if os.path.normcase(str(Path(buffer.value).resolve())) != os.path.normcase(str(self.game / 'Anno1503.exe')):
                raise CaptureError('The running Anno1503.exe belongs to a different game folder; use this collector beside that installation.')
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None

    def snapshot(self, directory, number):
        import msvcrt
        path = directory / f'temporary-{number}.dmp'
        try:
            with path.open('w+b') as stream:
                handle = msvcrt.get_osfhandle(stream.fileno())
                ok = self.debug.MiniDumpWriteDump(self.handle, self.pid, handle, 0x1000, None, None, None)
                if not ok:
                    error = ctypes.get_last_error()
                    raise CaptureError(f'Windows could not capture the game threads (HRESULT 0x{error & 0xffffffff:08x})')
            result = parse_snapshot(path.read_bytes())
            result['captured_utc'] = datetime.now(timezone.utc).isoformat()
            return result
        finally:
            path.unlink(missing_ok=True)


def capture_samples(game, progress=print, factory=WindowsCapture):
    reader = factory(game)
    try:
        with tempfile.TemporaryDirectory(prefix='anno1503-thread-capture-') as tmp:
            samples = []
            for number in range(2):
                progress(f'Capturing thread locations ({number + 1}/2)...')
                samples.append(reader.snapshot(Path(tmp), number))
                if number == 0:
                    time.sleep(0.75)
            return reader.pid, samples
    finally:
        reader.close()


def summary(report):
    lines = ['Anno 1503 live loading-hang capture',
             'Two snapshots of the same running game process.',
             'Offsets are relative to the named loaded module.',
             'Stack values are candidates; they are not an unwound call stack.', '']
    for thread in report['thread_comparison']:
        lines.append(f"Thread {thread['id']}: CPU delta {thread.get('cpu_delta_ms', 'unknown')} ms")
        for label, location in [('first', thread.get('first_instruction')), ('last', thread.get('last_instruction'))]:
            if location:
                lines.append('  ' + label + ': ' + str(location.get('module')) + '+' + str(location.get('rva', location.get('address'))))
    lines += ['', 'The ZIP contains JSON and this summary only. Temporary minidumps were',
              'parsed on this PC and deleted. No game files or process settings were changed.']
    return '\n'.join(lines) + '\n'


def write_report(report, candidates):
    name = 'Anno1503-Live-Hang-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%SZ') + '-' + uuid.uuid4().hex[:8] + '.zip'
    for directory in candidates:
        if not directory.is_dir():
            continue
        path = directory / name
        created = False
        try:
            with path.open('xb') as stream:
                created = True
                with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr('thread-locations.json', json.dumps(report, indent=2))
                    archive.writestr('SUMMARY.txt', summary(report).replace('\n', '\r\n'))
            return path
        except OSError:
            if created:
                path.unlink(missing_ok=True)
    raise CaptureError('The live-hang report could not be saved to an available output folder')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-dir', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    game = args.game_dir.resolve()
    print('Anno 1503 live loading-hang collector ' + VERSION)
    print('Leave the game OPEN on the stuck loading screen while this runs.')
    try:
        pid, samples = capture_samples(game)
        print('Reading current game-file fingerprints...')
        report = {'collector_version': VERSION, 'created_utc': datetime.now(timezone.utc).isoformat(),
                  'process_id': pid, 'samples': samples, 'thread_comparison': compare_samples(samples),
                  'game_state': cc.collect_state(game)}
        output = write_report(report, cc.output_candidates(args.output_dir))
        print('Created: ' + str(output))
        print('Attach that ZIP. You can now close the game and run this package\'s RESTORE.cmd.')
        return 0
    except (CaptureError, OSError, ValueError, KeyError, struct.error, subprocess.TimeoutExpired) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
