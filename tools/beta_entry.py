"""Standalone beta entry; the bundle builder embeds its public source identity."""
from anno1503_overhaul.frozen_runner import main

TRUSTED_RELEASE_FILES_SHA256 = None
EXPECTED_WORKER_SHA256 = None

if __name__ == '__main__':
    raise SystemExit(main(trusted_release_sha256=TRUSTED_RELEASE_FILES_SHA256,
                          expected_worker_sha256=EXPECTED_WORKER_SHA256))
