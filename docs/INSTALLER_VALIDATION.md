# Installer 0.2.0 validation — 8 November 2026

## Automated checks

The local Windows suite ran 104 tests successfully, with four skipped tests
requiring Windows symbolic-link privileges. Coverage includes feature
dependencies, independent-copy boundaries, pinned local packages, exact native
composition, whole-file backups, archive-region edits, rollback, changed-file
refusal and restoration after the original source and prepared package move.
These fixture tests do not execute the game.

## Real local file integration

A separate managed copy containing 8,194 game files (4,003,708,503 bytes) was
created outside the installed game. The existing Food source and historical
backups supplied verified originals for 21 inspected modified files. No old
restoration scripts were executed on the source.

The complete local integration passed:

- Food + World installed as one transaction affecting 41 files. Installed
  native, Food, private AI and island outputs matched the expected build;
  repeated World preparation returned an exact installed state with no edits.
- The actual activation preflight accepted the explicit new copy, source Food
  modules and common restoration journal without starting a game.
- An intentionally altered installed data file caused restoration to stop
  before changing any other target. The test alteration was then reverted.
- Combined restoration returned all inspected feature inputs to verified
  vanilla originals and removed introduced native/AI/island payloads.
- Food-only installed in a separate transaction affecting 21 files, using a
  public-source Food package with no World payloads. Repeated Food preparation
  returned the exact installed state with no edits.
- Food restoration returned to the same verified vanilla inputs. Both restore
  generations retained an unrelated save-file sentinel and their backups.
- Combined installation succeeded again after restoration, retaining two
  preceding backup generations.
- Before/after SHA-256 comparisons matched for all 8,359 protected source-game,
  historical-backup and selected original test-copy inputs checked by the
  integration exercise. This comparison preceded the separate startup check.

The inspected runtime remained the previously tested AMD64 binary:
`2f9d1156f3ac53d92a900e41c38a169138c2b4ac7145f2dc92b93c48736cf089`.
No native runtime source or imported compiled input changed for this installer.

## User interface

The Windows installer was opened and inspected. World Settings could be
unchecked to make Food independently selectable. Selecting World Settings
again enabled and locked Food, including after both choices had been cleared.
The initial layout, folder controls, review area and installation/restoration
buttons were visible. Native file lifecycle checks above used the same backend
through its API rather than automated clicks on Install or Restore.

## Actual startup and in-game menu

The final combined copy was started through the modular launch command and
the normal registered Ubisoft handler in a fresh game process. The automatic
launcher verified its exact process identity and main menu, then completed
one activation attempt. Its result verified all 173 expanded engine edits,
nine hook sites, the expected runtime and engine-plan fingerprints, and the
explicit new managed-copy root. It reported no installed source files modified
by activation.

Selecting a new endless game opened the existing in-game World Settings
screen. The world options, all native cultures, Pirates, Venetians and map
preview were visible. This establishes startup and menu observation for the
new integration; no world was started or saved during that check.

## Limits of the result

Vanilla verification covers the inspected feature files and their whole
archives/UI outputs. It does not certify every copied asset or remove arbitrary
files belonging to another mod. Source game files and local payloads are not
included in GitHub.

No new endless world, save/reload comparison, Food economy session, combat,
multiplayer or extended gameplay test is established by these installation
checks. Historical World Settings gameplay evidence retains its original scope.
