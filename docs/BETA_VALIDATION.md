# World Settings 0.9.0-beta.1 validation

This beta targets the inspected AMD64 History Edition build with Dutch scene
and UI data. Public preparation supports World Settings alone; Food remains
optional and its combined development profile requires matching preserved
inputs. Tests below distinguish automated checks from actual game observations.

## Release identity

- Windows archive: `Anno1503GrandOverhaul-Beta.zip`, 137,114,241 bytes.
- Archive SHA256: `13edd60b98207cdd4e440342aa9a21f8dda61ae472cf92934a4649d1aaa8b85b`.
- World-only runtime SHA256: `91f0d2acbd3ad17f23cd4bfe4e0813c5e55c394ca06426b835b0015b3b926140`.
- Food + World development runtime SHA256: `1b7248098910f550d7cb5ffc74bcb415f41b47a34f6ac8585bd67f9b79869677`.
- Generator: `ws6-a2d7e8ee018ab1e6a18a933efbb8482391c78e35a54e29b05523e5af24a6ea2e`.

The ZIP contains the mod's frontend, public source and licensed preparation
tools. Game executables, game DLLs, native islands and saves are reconstructed
from the player's own supported installation and are not distributed.

## Automated checks

The final complete regression run executed **652 tests: 647 passed and five
skipped**. All five skips require Windows symbolic-link privileges. The log's
SHA256 is `8cacad152f5b45c38fd367d216039bb460e90cd36ad8a456d339d2e96a4924fb`.

Coverage includes the Original/Custom return protocol, cancellation and native
setup restoration, supported preset migration, native rendering passthrough,
marked-save identity checks, faction policy isolation and installation guards.
An isolated rendering fixture exercises 50,000 normal and 50,000 clipped
callbacks without per-callback operating-system memory queries. That measures
the removed overhead; it is not a game FPS benchmark.

Two fresh public World-only builds produce identical DLL bytes, all 84 staged
inputs, 43 imported compiled inputs and 95 exports. Those builds refuse reads
from the historical private input stores. A historical stock-host build matches
them. Two Food + World builds and their strict published development profile
also match. Both engine plans retain 173 verified edits; AI derivatives are
unchanged. All 488 imported files and 43 compiled inputs remain byte-exact.

The standalone archive's 21,213 files, source closure, six third-party license
components, AMD64 executables and embedded source/worker seals were checked.
Frozen imports were executed for the real launcher, activation helper and
legacy worker without calling their main, game or UI functions. This includes
the regression for preserving the frozen standard-library ZIP in child paths.

## Installer and restoration

Production restoration and installation were exercised on a managed copy,
including the exact frozen beta worker. The installed World-only profile
introduces 19 owned files and leaves the 23 checked stock files unchanged.

The final preservation proof retained all eight existing presets, every named
save, the original source files and backups, and all 65 preceding backup
generations. The repaired installation retained a 66th generation. Current
Lastgame checkpoints were archived before restoration. Both preceding launcher
versions and desktop shortcuts were retained as evidence.

Installer actions used the frozen command interface and its production backend.
The graphical setup layout was inspected separately; this is not a claim that
every graphical installer interaction was automated.

## Actual game checks

The final installed World-only build passed these bounded observations:

| Check | Observed result |
| --- | --- |
| Desktop shortcut | Automatic activation succeeded with all 173 engine edits verified. The temporary Ubisoft source menu was hidden before copy initialization, closed normally, and one copied Anno process remained. |
| Original game | A new endless world loaded and saved as `bn1`. Its 1024-square, 20-island save has zero World Settings policy bits and neither a custom chart nor a disaster-policy extension. |
| Existing preset | `Environment1` loaded without rewriting the preset. Its complete preview, all 43 choices and all 24 island plans match the preceding working build exactly. |
| Custom world | The captured preview started and saved as `bc1`. Disk checks match all 24 island boxes, resource/geometry constraints and disaster policy; all ten rotated islands have zero height or texture differences. |
| Custom to Original reload | Loading `bn1` through the in-game Load menu displayed correctly and saved as `bn1r`, still without custom policy extensions. |
| Original to Custom reload | Loading `bc1` through the in-game Load menu displayed correctly and saved as `bc1r`. The same terrain, resource and disaster checks pass. The user reported no black map or loading error. |

Tutorial and first main-campaign starts were user-confirmed to bypass World
Settings and feel smooth on the preceding beta candidate. The final build keeps
that candidate's exact native drawing path; only the custom faction-load check
was subsequently moved behind the authenticated custom-checkpoint gate. Those
levels were not rerun on the exact final archive.

No new live Food-overhaul gameplay test was performed. Its evidence for this
release is automated compilation and compatibility coverage; earlier Food
gameplay observations retain their original scope.

## Remaining beta scope

Bounded starts, save comparisons and reloads do not establish long-session
stability, every option combination or a complete campaign playthrough. The
final custom world was reloaded within the running game; a full process restart
of that new save was not repeated for this release. Earlier restart checks
remain documented with their original versions.

Huge 2048 worlds remain experimental. Other localizations need exact-file
verification. Up to three ordinary AI opponents are currently exposed; eight
AI players and local-host multiplayer remain research goals. Long-session
disaster rates, pirate raid behaviour and trade rates require further play.

The launcher still uses two temporary authenticated SDK sessions during startup.
It hides and normally closes its owned source menu; it does not replace Ubisoft
authentication or claim to eliminate that initialization requirement.

Detailed native checkpoints, local paths and saves remain private. The public
test sources and pinned build recipes are in this repository. Earlier feature
evidence is linked from the [changelog](CHANGELOG.md) and [environment
guide](WORLD_ENVIRONMENT_OPTIONS.md).
