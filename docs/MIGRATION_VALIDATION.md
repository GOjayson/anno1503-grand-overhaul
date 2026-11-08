# Migration validation — 8 November 2026

## Preserved inputs

The import records 488 public source files and keeps all 43 native-runtime
compiled inputs byte-exact. Git attributes disable newline conversion for the
imported legacy tree so that a fresh checkout preserves those fingerprints.
The provenance manifest records the explicit source-snapshot transformations
separately from unchanged files.

The ignored local baseline store contains 1,239 checked package files and the
two preserved release ZIPs. Each copied file was compared with its original.
The installed game, working copy, backups, native saves and existing desktop
shortcut were left in place.

The public World Settings specification removes machine paths and raw private
evidence. Its source-only marker blocks installation/activation before target
paths are accessed. The complete original specification, payloads and evidence
remain in the private local baseline.

## Build outside the game directory

The imported World Settings runtime was compiled successfully under the new
repository's ignored `.local/builds/` tree using a separately copied Zig 0.16.0
toolchain. No installed game module was written, loaded or activated by this
build.

The preserved tested runtime has SHA-256:

`2f9d1156f3ac53d92a900e41c38a169138c2b4ac7145f2dc92b93c48736cf089`

The first repository build candidate has SHA-256:

`c3825d25421590d0abe59a36527a39e1c8afe12aa53c6d5f3456b04da02d1cd8`

Both files are 690,688 bytes and are AMD64 PE32+ images. The 20 differing bytes
are confined to the COFF timestamp and `.buildid` metadata. The `.text`,
`.rdata`, `.data`, `.pdata`, `.tls` and `.reloc` section bytes match the tested
runtime exactly. The candidate is still a different whole-file fingerprint;
it was **not installed or tested in a running game** during this migration.

The existing exact-build activation guards are not relaxed to accept it.
Preparing a complete new package and its matching fingerprints is a separate
integration task. The verified original artifact remains the playable baseline.

## Automated checks

Portable profile tests cover unavailable features, strict data types,
dependencies, dependency cycles, bounded JSON, duplicate keys and safe storage.
Migration tests cover the public import boundary, sanitization order, the
source-only guard, exact private copies and refusal to overwrite baselines.
The repository-content check rejects game/native payloads, saved games,
credentials, private directories and personal machine paths.

The local Windows run passed all 37 test methods with one platform-privilege
skip for creating a symlink. The default profile was created and loaded through
the CLI. The graphical selector's code was parsed; no manual interactive GUI
acceptance is claimed by those checks. GitHub Actions is configured to repeat
the portable checks on Windows and Linux.

## Actual game evidence

No new Anno gameplay session, save/reload test, Food economy test, multiplayer
session or player-capacity test was performed for this repository migration.
Historical World Settings and launcher observations retain their original
runtime fingerprints and scope in the preserved local packages and the feature
documentation. Eight AI opponents and eight human players remain unverified
research targets.
