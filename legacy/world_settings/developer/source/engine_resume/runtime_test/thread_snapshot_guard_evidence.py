"""Source-branch evidence only: no compilation, OS calls or process attachment.

Checks ordering and evaluates the exact extracted C guard predicate for complete,
partial/error and already-aborted enumeration cases. This is not a native/API
failure-injection test; compile and native fixture coverage remain separate.
"""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent


def verify(text):
    start = text.index('static int wsSuspendThreads(')
    end = text.index('static int wsRestorePatches(', start)
    body = text[start:end]
    next_at = body.index('}while(Thread32Next(snapshot,&entry));')
    guard = re.search(r'DWORD enumerationError=GetLastError\(\);\s*'
                      r'if\((ok&&enumerationError!=ERROR_NO_MORE_FILES)\)\{\s*'
                      r'SetLastError\(enumerationError\);wsWinError\("([^"\n]+)"\);ok=0;\s*\}', body)
    assert guard, 'Missing reviewed fail-closed enumeration guard'
    close_at = body.index('CloseHandle(snapshot);if(!ok)return 0;', next_at)
    suspend_at = body.index('DWORD previous=SuspendThread(')
    assert next_at < guard.start() < guard.end() < close_at < suspend_at
    # The regex accepts only this bounded, side-effect-free expression. Using
    # its translated text ties the truth table to the source predicate itself.
    predicate = compile(guard.group(1).replace('&&', ' and '), '<C snapshot predicate>', 'eval')
    cases = []
    for ok in (False, True):
        for error, label in [(18, 'ERROR_NO_MORE_FILES'), (299, 'ERROR_PARTIAL_COPY'),
                             (5, 'ERROR_ACCESS_DENIED'), (6, 'ERROR_INVALID_HANDLE'),
                             (0, 'unexpected zero error'), (24, 'ERROR_BAD_LENGTH')]:
            rejected_here = bool(eval(predicate, {'__builtins__': {}},
                                      dict(ok=ok, enumerationError=error, ERROR_NO_MORE_FILES=18)))
            after_ok = ok and not rejected_here
            assert after_ok == (ok and error == 18), (ok, error, rejected_here)
            cases.append(dict(previous_ok=ok, enumeration_error=error, error_name=label,
                              guard_rejects=rejected_here, suspension_phase_reachable=after_ok))
    return dict(scope=__doc__, predicate=guard.group(1), diagnostic=guard.group(2),
                preserves_last_error_before_close=True, rejects_before_suspending=True, cases=cases)


def main():
    path = HERE / 'install_test_hooks.c'
    data = path.read_bytes()
    result = verify(data.decode('utf-8'))
    result['source_sha256'] = hashlib.sha256(data).hexdigest()
    (HERE / 'thread_snapshot_guard_evidence.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS:12 source-predicate branches; incomplete snapshots cannot reach suspension. No compile or native run performed.')


if __name__ == '__main__':
    main()
