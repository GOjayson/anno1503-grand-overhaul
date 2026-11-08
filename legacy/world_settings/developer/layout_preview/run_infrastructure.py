"""Record isolated copy-discovery, activation and transaction unit checks.

Tests operate on owned fixtures/doubles. They do not activate a running Anno
process, modify the shared game copy or establish actual gameplay.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sources = ["developer/test_copy_location.py", "activation/test_activation.py", "support/test_world_transactions.py"]
    source_hashes = {name: sha(PACKAGE / name) for name in sources}
    rows = []
    for name in sources:
        command = [sys.executable, "-B", str(PACKAGE / name)]
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        text = completed.stdout
        count = re.search(r"Ran (\d+) tests?", text)
        assert completed.returncode == 0 and count and re.search(r"^OK(?:\s|$)", text, re.M), text
        skipped = re.search(r"OK \(skipped=(\d+)\)", text)
        rows.append(dict(source=name, command=command, source_sha256=source_hashes[name],
                         exit_code=completed.returncode, tests_run=int(count[1]),
                         tests_skipped=int(skipped[1]) if skipped else 0, output=text))
        print(name, count[1], "checks completed", flush=True)
    assert source_hashes == {name: sha(PACKAGE / name) for name in sources}
    world = json.loads((PACKAGE / "world_patch.json").read_bytes())
    report = dict(scope=__doc__, version=world["version"],
                  runtime_sha256=world["payloads"]["native/AnnoWorldSettings.dll"],
                  executed_world_spec_sha256=sha(PACKAGE / "world_patch.json"),
                  test_sources_sha256=source_hashes, cases=rows,
                  tests_run=sum(row["tests_run"] for row in rows),
                  tests_skipped=sum(row["tests_skipped"] for row in rows),
                  game_executed=False, shared_game_copy_modified=False,
                  runner_sha256=sha(Path(__file__)), passed=True)
    out = PACKAGE / "installer_audit/preview_infrastructure_tests.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(passed=True, tests_run=report["tests_run"], tests_skipped=report["tests_skipped"], report=str(out), sha256=sha(out)), indent=2))


if __name__ == "__main__":
    main()
