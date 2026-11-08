# Independent World Settings validation — 8 November 2026

This record concerns the new World-only stock-host profile. It is separate from
the preserved Food/World combined runtime and the earlier modular installer
checks in [installer validation](INSTALLER_VALIDATION.md).

## Selection behavior

The feature catalogue no longer declares Food as a World Settings dependency.
Portable profile tests cover all four Food/World flag combinations with and
without dependency resolution. World-only profiles keep Food disabled when
other flags are omitted and after saving/reloading. Generic dependency and
unavailable-module checks remain in place for modules that declare them.

The installer UI no longer selects or locks Food when World Settings is
checked. Changing an installed selection requires restoration and a fresh
installation/launch; no feature is swapped into a running world.

A Windows UI check also confirmed that Food can be unchecked while World
Settings stays selected. Turning World Settings off and on again left Food
unchecked, with both controls still editable.

## Stock native/data profile

The independent profile uses the copied executable as its actual host and the
same managed folder as its world data root. The original Ubisoft installation
is a separate read-only input, even when it contains Food changes. Original
native/data/archive/UI bytes are recovered only through the reviewed stock
fingerprints and retained originals.

The World-only installation recipe introduces World runtime, private
World-policy AI and island payloads. It does not apply Food's resident diet,
market, icon, goods-index or native-host transformations. Its backend verifies
the inspected stock closure before preparing or accepting installed outputs.
Derived disk Frame/Scene/Welt overlays are not installed on this stock host.

The private AI modules derive from the exact stock controllers with one
World-policy flag-preservation hook, its 92-byte helper and matched unwind
metadata. Other original mapped bytes remain stock. These are distinct from
the frozen combined build's Food-adapted private AI modules.

## Controlled runtime build

The original 43 compiled-source inputs were verified before staging and again
after compilation. Their public legacy bytes remain unchanged. Only four
staged compiled inputs were transformed:

- `runtime_test_blobs.h`: bind Frame/Welt hooks to exact stock module hashes.
- `ai_loader.c`: bind stock source AI and the separately derived World-only
  private AI, retaining exact-hash and candidate-path checks.
- `WorldSettings.c`: allow the actual executable host as world root only under
  the regular managed-copy guard and matching directory identity/spelling.
- `engine_patch_plan.h`: rebind two unwind-table field locations to stock.

The nine hook preimages and all 173 engine-edit preimages were verified against
the exact stock AMD64 PE inputs. Both chained Scene unwind parents were matched
to their original exception-function table records.

The frozen Food-derived plan contained two Welt `.pdata` field locations beyond
the stock image. The derivative resolves their unique original function tuples
and changes only those two edit addresses:

| Frozen combined RVA | Verified stock RVA | Field |
| --- | --- | --- |
| `0x14be8c` | `0x1389d8` | First function's end |
| `0x14be94` | `0x1389e0` | Following function's begin/end |

The before/after instruction bytes and the other 171 edit addresses remain
unchanged. The derivative JSON plan has its own profile and fingerprint;
matching edit counts do not authorize reuse of the combined plan.

Two clean staging builds using Zig 0.16.0 produced the same canonical AMD64
runtime after bounded timestamp/CodeView metadata normalization. Executable
sections are not normalized. The output has 41 exports, including all required
activation exports, and is 691,712 bytes.

| Artifact | SHA-256 |
| --- | --- |
| World-only canonical runtime | `4ede7aefddeb78319328f9de7e4597e49d6d1652739539c29afe5439024a86e9` |
| World-only engine plan | `71940166c7131f78d1b5efd68c1e6dff0299ea8d3334ed811420da4a53fa1f4e` |
| World-only CompLogic | `bbf15a8aa0a06f2fb484cb38df741ff8f8d63f479de9d05afbf0c453b2c96fd9` |
| World-only CompLogicClassic | `7592ca081ac7fe8d3011b64c5ea868b125a8b5e358c0c4a9e365b1329d0a1dcd` |
| Preserved combined runtime | `2f9d1156f3ac53d92a900e41c38a169138c2b4ac7145f2dc92b93c48736cf089` |

The builder refuses a different canonical runtime or engine-plan output before
publishing a runtime profile. Previous native candidates and combined artifacts
are preserved. No game was started or installed by these compilation checks.

## Startup handoff and privacy

World-only startup retains normal Ubisoft authentication. The handoff accepts
only a fresh source process positively identified at its ordinary main menu,
captures the existing startup context in memory and rechecks the owned menu.
It starts the identical independent executable once while retaining the source
menu for normal client SDK initialization. Both exact menu identities must be
verified before requesting the source menu's normal close. The copied host
must survive alone at its verified menu before native activation. The handoff
does not adopt an existing game or close an unknown process/world.

Argument/environment values are not logged or persisted, and no authentication
data are created. No executable, Ubisoft registration, permanent installation
path or security setting is changed. The copied host still needs its own exact
process, menu, stock-native, runtime, engine-plan and one-attempt activation
checks. Passing a context parser fixture is not a successful game launch.

## Real local file checks

A low-level World-only preparation/install/preflight/restore exercise passed
on a confirmed non-running independent copy:

- Preparation selected exactly 19 introduced World files and no stock-file
  replacements.
- Installation and repeat validation matched the pinned outputs and common
  journal while all 23 inspected stock inputs remained unchanged.
- The actual read-only activation preflight accepted the same stock host and
  world-root folder with its matching markers and journal.
- Restoration removed all 19 introduced outputs and retained the checked stock
  inputs. Before/after fingerprints matched for all 161 protected original
  source/backups checked by that exercise.

This was a direct low-level file lifecycle test, not the high-level installer's
closed-game workflow. Its game-closed guard was not modified, and no game was
started by that exercise.

After the first actual World-only game was saved and normally closed, the
high-level installer also restored all 19 World-only outputs, retained backups
and the save, then completed a fresh 19-file World-only installation. A stock
baseline check now precedes removal of World payloads, so an externally changed
unowned stock file causes refusal before restoration writes.

A final high-level cycle on that same closed copy also passed: restore
World-only, install exact Food 0.5 (21 changes and no World payloads), restore,
install the preserved combined profile (41 changes and its original runtime),
restore, then install World-only again (19 introduced files and all 23 stock
inputs unchanged). The real closed-game guard remained unchanged and was used
throughout; this cycle did not launch a game.

That cycle preserved the 23 checked source files, all 297 source-backup files
found recursively, both pre-existing historical copy-backup generations and
all 30 native save files, including `wo3`. Three additional restored backup
generations were retained. The copy was left with World Settings enabled and
Food disabled. A corrected label assertion in the private test harness is
recorded separately from the successful installer operations.

## Actual host startup and native activation

A separate controlled normal-client context handoff reached the copied stock
host's main menu. Keeping the verified source menu alive during copied client
SDK initialization succeeded; closing it before that initialization had failed
and was not accepted as a working route. The copied host remained alive alone
after the owned source menu closed.

Native activation on that actual copied host passed with runtime `4ede7a…`,
derived engine plan `71940166…`, all nine hook sites and all 173 engine edits
verified. Activation reported no installed source-file patching.

The final packaged automatic launcher then passed separately through its full
production entry point: normal client startup, copied-host initialization,
closure of only the owned source menu, sole surviving copied host, and automatic
one-attempt activation with all nine hooks and 173 engine edits verified. This
used the newly installed stock-host copy and the pinned World-only runtime.

## Actual world, stock diet and fresh-process reload

The in-game World Settings screen opened with its preview. A new 1024 × 1024
world loaded with Mixed islands, 24 islands, spacing 16 and zero ordinary AI
opponents, with all eight cultures, Pirates and Venetians enabled.

A read-only live inspection of the parsed resident requirements passed for all
five population levels: stock `NAHRUNG` good 26 had positive demand, and Food
overhaul goods 24, 25, 40 and 45 were absent from their diet requirements. This
covered the human and existing AI placeholder profiles; zero ordinary AI
opponents were selected, so this is not an active-AI economy test. The probe
read memory and inspected the known native getter's bytes without calling game
code or changing the world.

The user saved the world as `wo3`; it appeared in the native save listing. After
normal game exit, restoration/reinstallation and the final packaged automatic
launch into a fresh process, loading that save through the native UI succeeded.
The live read-only check again found 1024 × 1024 dimensions and the stock diet
across all five population levels. This establishes the stated reload and diet
observations, not a complete byte-for-byte world-state comparison.

## Portable regression suite

The current full portable suite ran 162 tests successfully with five Windows
symbolic-link privilege skips. It includes independent selections, checked
native derivation and package recipes, stock instruction/unwind preimage
checks, startup-context parsing and process/menu handoff state, installation,
restoration and changed-file refusal. The repository-content/privacy check also
passed. These checks do not substitute for actual world or save observations.

## Remaining gameplay scope

Extended food production/consumption, trade, combat, active ordinary-AI behavior
and a new Huge World-only world were not tested in this run. The accepted
stock-host world/reload used 1024 × 1024 dimensions and zero ordinary AI.
Historical combined-runtime Huge observations retain their original scope and
must not be relabelled as new World-only evidence. Changing feature selection
does not convert saves between stock and Food overhaul diets.
