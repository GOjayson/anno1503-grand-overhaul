# Expanded World Settings validation — 8 November 2026

This record covers the new 0.4.0-dev.1 menu and generator extensions. Historical
combined-runtime observations and the accepted 0.3 World-only session remain
in their original [installer](INSTALLER_VALIDATION.md) and
[decoupling](DECOUPLING_VALIDATION.md) records. They are not evidence that the
new menu has completed an actual game run.

The first expanded-menu candidate recorded below is **superseded**. Independent
native-save inspection found that its new custom-cargo tools/wood good IDs
were reversed: History Edition uses good 41 for tools and good 42 for wood.
The equal 50/50 amounts in the first live test concealed that mapping error.
The repair now uses independently confirmed History Edition good identities
and unequal-cargo fixtures. Replacement native builds and the repaired
World-only live session, preset restart and native-save reload are recorded
below; broader gameplay coverage remains separate. Default fleet cargo remains
byte-exact to the preserved source.

## Implemented choices

The expanded screen has World, Players, Starting options and Presets pages,
with the preview and seed visible across the pages. The following behavior is
implemented in the newly staged native source:

| Choice | Behavior |
| --- | --- |
| Map seed | Decimal unsigned 32-bit input, including zero; Copy seed uses the clipboard; Regenerate changes the displayed seed. The displayed value is checked against the generation request and cached preview. |
| Saved presets | Named, bounded text presets contain all 23 world-setting fields and the generator identity. Parsing rejects unknown versions/generators, missing/duplicate/reordered/extra fields and invalid numeric encodings. Preset names cannot contain path components or Windows device aliases. |
| Starting position | A climate preference or an ordinary-island click chooses checked nearby water for the human starting fleet. Native and special-faction islands are excluded. Island geometry is preserved; the player establishes a settlement normally. |
| Starting cargo | Custom tools, wood and food apply to each trade ship. Every distinct 50-ton stack consumes a hold. Capacity must fit the smallest trade ship in the selected fleet; warships retain their cannon equipment. Standard fleet supplies remain when custom cargo is disabled. |
| Climate balance | Balanced or favour temperate, tropical or polar island groups. All six climates, enabled cultures and essential resources remain validated. |
| Layout style | Existing even spread, grouped archipelagos or a central ocean. All modes retain overlap, spacing, native-grid, border and ship-reservation checks; an unavailable arrangement fails instead of silently switching mode. |
| Disasters | The inspected native endless-game disaster option is bound separately from faction choices and checked after the original native profile commits. |

The same seed, settings and generator fingerprint reproduce the validated
plan, including selected island templates, placements and planned resource
availability. This reproducibility does not promise identical later AI
decisions, simulation events or every incidental native scenery detail.
Generation-option changes clear a stale preferred-island selection. A preset
load restores its seed, full settings and island index together, followed by
generation and normal validation.

Preset files belong to `WorldSettingsPresets/` inside the managed game copy.
They are separate from installer feature-profile JSON and are retained during
restoration. The preset storage code accepts regular bounded files, refuses
reparse/hardlink targets and publishes a newly written preset through a
temporary file. Replacing an existing named preset asks for confirmation inside
the game. The actual-menu checks below record these paths separately from
parser fixtures, including restoration retention and a fresh-process preset
reload.

## Source preservation and native builds

The original 43 imported compiled inputs remain byte-exact. New transformations
apply only to fresh staging dictionaries. Authored native source, reviewed
transformations and the imported closure contribute to the generator identity;
the same identity is used by both Food selections. Existing Food-only,
historical combined and 0.3 stock-host runtime profiles remain preserved.

The original 56-byte settings prefix retains its field offsets. The advanced
settings structure is 96 bytes, the island structure remains 40 bytes and the
preview snapshot is 5232 bytes. The package includes a matching strict snapshot
decoder and binds the runtime, schema and generator identity together.

Both native profiles were compiled in two independent stages with the reviewed
Zig 0.16.0 toolchain and `-Wall -Wextra -Werror`. Their canonical outputs matched
within each profile after the existing bounded compiler-metadata
normalization. Executable sections are not normalized. Every build first
verified the exact History Edition AMD64 module hashes, all nine native hook
preimages, all 173 engine-edit preimages and the reviewed chained unwind
parents for its host profile. Compilation did not install or launch a game.

| Superseded first-candidate artifact | Identity retained for its evidence |
| --- | --- |
| World-only expanded runtime | `91435a600453a2dd945352bddb67292e24c828ac5b878f1144e6aa620d7a0d21` |
| Food + World expanded runtime | `cc8ef982129086eadc883d6ea9a359211698f0b24a702703fcc53826fb3d4f2f` |
| Shared generator | `ws4-dd34f629fa916899be2b5cdc5fb29a94f61de921569bc590eb93686ef8b1c5ae` |

The repaired source was rebuilt in four fresh stages: two stock-host builds
and two Food-host builds. Each pair produced the same canonical runtime. All
four builds retained the original 43 compiled inputs byte-exact and verified
the same nine hook and 173 engine preimages against their exact host profile.
No game was launched by these builds. The replacement reviewed identities are:

| Repaired artifact | Reviewed identity |
| --- | --- |
| World-only expanded runtime | `f7a070e6825a9269e61d2f504e0e855f38002be13ad5befedcf87bd5081f8b14` |
| Food + World expanded runtime | `23b2b69956d70e900cb0fa0aa079fdc5b7f00215b74c853c276ac90633fb837f` |
| Shared generator | `ws4-443c04febaf41fe2328c0084ad379232a6e7d6a6b049c70707f587d768cccf1a` |

Publication of a runtime profile requires the separately reviewed runtime and
generator pins. The installer uses a new package kind for these extensions;
historical package validators keep their original pins. A modified manifest
cannot authorize another runtime, helper, generator or Food selection.

## Automated and native fixture checks

Before the cargo-mapping correction, the full portable suite ran **200 tests**,
passing with five Windows
symbolic-link privilege skips. It includes the previous installer and native
guards plus the new menu, planner, starting-option, package and snapshot checks.
The repository-content/privacy check also passed. Compiler-dependent native
fixtures are distinct from running the game and report a skip if their local
compiler is unavailable.

Those results retain their recorded scope. The custom-cargo fixtures shared
the original incorrect tools/wood interpretation. The repaired tests use
unequal cargo amounts: 25 tons of tools, 75 of wood and 40 of food. They check
good 41 in a 25-ton tools hold, good 42 in 50/25-ton wood holds, and good 26 in
a 40-ton food hold. An added licensed-input fixture independently checks the
pinned native good dictionary entries `WERKZEUG`, `HOLZ` and `NAHRUNG`; it
explicitly skips when that optional local native input is unavailable.

After that repair and the replacement runtime pins, the full suite ran
**201 tests**, passing with five Windows symbolic-link privilege skips. The
unequal-cargo and independently pinned native-dictionary checks both passed
in this local run. These automated results remain separate from new live-game
acceptance of the replacement runtime.

The added checks cover:

- Compiling and executing the actual C preset codec, round-tripping every
  field, zero/high-bit/maximum seeds and negative automatic-start sentinels.
  LF and CRLF files are accepted. Malformed headers, generator mismatches,
  numeric overflow, duplicate/missing/extra/truncated fields and unsafe names
  are refused; failed decoding leaves the output structure unchanged.
- Compiling isolated native planner policies. All four climate balances and
  three layouts retain enabled cultures, all climates, essential crops and
  minerals, native placement alignment, spacing, map bounds and ship reserves.
  Weighted filler fixtures distinguish the favoured climate groups. Seed
  repetition and changes to non-map starting settings retain the map plan.
- Comparing grouped and even layouts, checking that grouped islands have
  tighter neighbours in the fixture, and independently rejecting islands in
  the central-ocean exclusion region. Impossible central-ocean geometry is
  refused without changing layout mode.
- Compiling the starting-position and cargo code. Preferred starts change the
  human spawn without changing island geometry. Culture/faction islands and
  blocked coastal space are refused. Cargo checks count rounded per-good holds
  rather than total tonnage alone and preserve stock fleet supplies.
- Serializing the exact embedded original scenes for all three stock
  difficulties, all three fleets and custom-cargo on/off. The fixture verifies
  money, ship definitions/counts, positions, hold contents and cannon fields.
  The loaded-cargo certificate is executed against reconstructed inspected
  native fields, then rejects a deliberately corrupted cargo slot. These are
  isolated fixture objects, not a loaded game world.
- Strict expanded-snapshot decoding, including unsigned seeds, automatic-start
  sentinels, settings/seed agreement, cargo capacity and island overlap.
- Package recipe recomputation and refusal of substituted old runtimes,
  mismatched Food selections, altered helpers, changed generator source,
  foreign path bindings and unexpected files.

A further automated integration exercise loaded the actual compiled DLLs for
both native profiles and called their real planner, preview and scene-staging
APIs against isolated copied fixture assets. It passed **48 plan cases**,
**48 scene-staging cases** and **12 custom-cargo/preferred-start staging cases**
across the two profiles, with the 96-byte settings and 5232-byte snapshot ABIs.
This exercised the complete compiled runtime APIs and serialization. It did
not open Anno, activate hooks, display a menu or load a native game world.

That whole-DLL exercise was repeated successfully on the repaired `f7a070…`
and `23b2b699…` runtimes. Its 48 plans and 48 staged scenes cover two seeds,
three layout styles and four climate balances across both profiles. Twelve
additional island/climate-preference stages cover all three fleets with
unequal cargo: independent serialized-field parsing confirms native goods
41/42/26 as 25 tons tools, 75 wood and 40 food, split into 50-ton holds within
the four/eight-hold limits. Warship holds remain empty, cannon fields are
retained, and starting preferences preserve island geometry. This is repaired
compiled-runtime evidence, separate from the earlier candidate and from a
running game.

## Verified native disaster mechanism

The existing History Edition Frame option byte at `0xc7a78` supplies the native
disaster choice. The ordinary native commit path and World property 6 getter
and setter establish the corresponding option-mask behavior. The new code
reuses that option path and verifies the result after the original profile
commit; it does not introduce an assumed classic-version patch address.

An isolated instruction fixture executed the exact inspected AMD64 Frame and
World code from both stock and Food profiles at different mapped bases. All
**384 cases** passed across selected disasters/factions, initial flag states
and native world kinds. The disaster mask is `0x86`, while the separately
preserved pirate mask is `0x20`. Unrelated flag bits were preserved. Only empty
player enumeration was doubled in this fixture; no live process was opened.

A separate compiled binder fixture confirms that only the two inspected Frame
option bytes are changed and that invalid choices fail before writes. These
checks establish the native option mapping and certificate behavior. They do
not establish long-session disaster-event frequency or every possible scripted
mission event.

## Superseded candidate: first World-only menu and world

The high-level installer restored the preceding stock-host installation and
installed the new World-only profile with 19 introduced files. The inspected
23 stock inputs and 239 protected-input fingerprints remained unchanged in
that upgrade exercise.

The packaged automatic launcher then started the independent stock host and
activated runtime `91435a…`. All nine hook sites and all 173 engine edits were
verified, with no installed-file patching. The new four-page menu opened with
a valid default 24-island Mixed 1024-square preview and displayed seed
`2524160867`.

The user configured and saved the in-game preset `Ocean1` with:

- Seed `123456789`, world size 1024 × 1024, Mixed islands, 24 islands and
  minimum spacing 16.
- Climate balance favouring tropical islands and grouped archipelagos.
- Zero ordinary AI opponents, all eight cultures, Pirates and Venetians.
- Merchant fleet, custom cargo of 50 tons each of tools, wood and food on every
  trade ship, and disasters disabled.
- Preferred starting island index 15, corresponding to island 16 in the menu.

The written preset matched the strict versioned schema, all 23 settings and
the current generator identity. **Copy seed** displayed its success status;
this records the in-game clipboard operation's result rather than an external
paste/readback test.

Regeneration displayed seed `3153883735` and produced a different validated
plan. Loading `Ocean1` inside the same process restored both the original
complete preview snapshot and island plan byte-for-byte:

| Checkpoint | SHA-256 |
| --- | --- |
| Original and preset-loaded ready snapshot | `0a855e473f10acfd07f0be915779720f63703389166ce573872394a4bc957382` |
| Original and preset-loaded island plan | `75ee51160d6f14faf46dc21f1f7d69876490426879804855692cf3bff0197afe` |
| Regenerated island plan | `750be16b2853d68654c576554d2b0f8dcede43bbef616814084e2ed4232c3342` |

Starting that restored preview loaded a world successfully, with three ships
visible. Post-load inspection found empty factory, hook, AI-loader and
AI-profile error reports and a validated ordinary-AI count of zero. The user
saved this world as `wo4`.

Independent live readback then confirmed all 24 island rectangles, climates
and crop masks against the `Ocean1` plan. The main ship was beside the chosen
island index 15 in native-verified clear water. All three human merchant ships
had full health and the correct four/eight-hold definitions, with 50 tons each
of tools, wood and food in separate 50-ton stacks. Native flags were exactly
`0x86`, matching disasters disabled and Pirates enabled. Stock food requirements
were confirmed for all five population levels in the human and AI-placeholder
profiles; this remains a zero-active-AI session.

That inspector performed read-only observation: no target-memory writes, game
function calls, UI input or process control. The game was subsequently closed
normally after the user's save.

Offline inspection of `wo4` also matched the historical candidate's 24 island
rectangles, `0x86` flags, ship positions and equal 50-ton cargo against its live
readback. This establishes the recorded state in that saved file; it does not
validate the replacement runtime or unequal custom-cargo mapping.

## Repaired-runtime installation and restoration cycle

The production high-level installer completed a separate closed-game upgrade
and feature cycle using the repaired runtime pins:

1. Restore the superseded World-only installation from its checked retained
   whole-file journal, without needing or reauthorizing the old prepared
   runtime package.
2. Install the repaired World-only profile: 19 introduced files, runtime
   `f7a070…`, with all 23 inspected stock inputs unchanged.
3. Restore, install the repaired Food + World profile with 41 changes and
   runtime `23b2b699…`, then restore it again.
4. Install the repaired World-only profile again, leaving Food disabled and
   the 23 inspected stock inputs unchanged.

Across that cycle, the 23 protected source inputs, all 297 source-backup files,
31 native saves and the existing `Ocean1` preset remained unchanged. All eight
pre-existing historical copy-backup generations were retained unchanged; three
additional restored generations were preserved, leaving eleven previous
generations. The original 43 compiled inputs and generator identity also
remained unchanged.

The real closed-game guard was used throughout and stayed byte-exact. This
exercise did not launch a game, operate the UI, terminate processes or bypass
that guard. It establishes installation, restoration and preset-file retention
for the repaired profiles; it is separate from actual gameplay and from
loading a preset after restart.

## Repaired World-only live acceptance

A fresh automatic launch activated repaired runtime `f7a070…`, again verifying
all nine hooks and 173 engine edits. In the new menu, loading the old `Ocean1`
preset correctly refused its different generator identity while preserving the
file and current preview seed.

The user configured `Ocean2` with seed `123456789`, 1024 × 1024 world size,
Mixed islands, 24 islands, spacing 16, tropical climate balance and grouped
archipelagos. It retained zero ordinary AI opponents, all eight cultures,
Pirates and Venetians, the Merchant fleet, disasters disabled and preferred
island index 15. Custom cargo now used unequal amounts: **25 tons tools,
75 tons wood and 40 tons food per trade ship**. Saving/replacing the test
preset and strict file readback confirmed all 23 fields, the selected island
and the repaired generator identity.

Copy seed displayed its success status. Regenerate selected seed `3908185400`
and changed the validated plan; loading `Ocean2` restored the complete ready
snapshot and island plan byte-for-byte:

| Repaired-runtime checkpoint | SHA-256 |
| --- | --- |
| Original and preset-loaded ready snapshot | `9045f876c616b8a6f5df80acd4ada18083992c0ac0542477069100b8c488a315` |
| Original and preset-loaded island plan | `75ee51160d6f14faf46dc21f1f7d69876490426879804855692cf3bff0197afe` |
| Regenerated island plan | `c6e69ae9c26d5e85b7b61c9248fb601bc6512ce949305a116aa2d712c562bb1d` |

Starting the restored preview loaded successfully with empty factory, hook,
AI-loader and AI-profile error reports and a validated ordinary-AI count of
zero. Independent read-only inspection matched all 24 island rectangles,
climates and crop masks to the preview, verified the preferred coastal start,
stock resident diets and native flags `0x86`. It confirmed each human trade
ship's unequal cargo against native good identities: **41 tools, 42 wood,
26 food**, with the correct four/eight 50-ton holds. This verifies the repaired
mapping independently of equal-amount cargo tests.

The user saved `wo5`. Offline parsing verified its native alias, all 24 island
rectangles, `0x86` flags, ship positions and cargo against the corresponding
live readback. The inspected save SHA-256 is
`bd17be027cfd66efb386ab692ee655f1e5be69f3067228709a58700e763106dc`.
Neither the inspector nor save parser wrote target memory, called game
functions, operated the UI or modified the save. The game was closed normally
after that save and inspection.

A final production World-only restore/reinstall then retained the new `Ocean2`
preset and `wo5` save byte-for-byte. All 32 native saves, both preset files,
23 inspected stock-copy inputs, 23 source inputs and 297 source-backup files
remained unchanged. Eleven existing historical copy-backup generations were
retained unchanged and one restored generation was added, leaving twelve.
The original 43 compiled inputs, generator identity and real closed-game guard
also remained unchanged. The copy was left with the same repaired `f7a070…`
runtime, World Settings enabled and Food disabled. This file-lifecycle check
did not launch or control a game; the separate restart checks follow.

A fresh automatic launch after that restoration/reinstall again verified all
nine hooks and 173 engine edits on `f7a070…`. Its process creation identity
differs from the earlier live session. The user loaded the preserved `Ocean2`
through the in-game Presets page. All 23 settings, including preferred island
15 and unequal 25/75/40 cargo, matched the original preset. The complete ready
snapshot (`9045f876…`) and island plan (`75ee5116…`) matched their earlier
SHA-256 values byte-for-byte. This completes preset persistence and deterministic
preview comparison across both restoration and an actual process restart.

The restarted game also loaded `wo5` through Anno's native load menu, with three
ships visible and empty factory, hook, AI-loader and AI-profile errors. The
runtime and all 173 engine edits remained verified. Independent read-only
inspection then matched all 24 island geometries and all 13 harvestable-plant
bits against the original world and serialized save. It confirmed the same
three Merchant ships, unequal native-ID cargo, preferred coast, five stock
diet levels and `0x86` disaster/faction flags.

This reload comparison accounts for native crop-mask normalization rather than
claiming every raw mask byte survives saving. On two polar islands, the initial
native mask `0x1f009` reloads as `0x1009`; the changed bits are outside the
13-bit harvest mask `0x1fff`. An independent comparison verified that the
original 95-byte `ANBAU` writer and 1180-byte loader instruction spans, and all
17 crop dictionary entries, are identical in the pinned stock and Food hosts.
The native writer serializes only bits 0–12; the loader restores default
non-harvest flags only for nonpolar climates. The four omitted dictionary bits
are grass, trees, fish and ice fish. The serialized polar `ANBAU` value is
`0x1009`, matching reload. No engine, generator or runtime change was made for
this existing native save behavior.

## Remaining actual-game coverage

The first candidate's runtime identities `91435a…` and `cc8ef982…`, generator
identity and `Ocean1` observations above remain historical development evidence.
They must not be relabelled as validation of the repaired runtime. Its strict
preset generator binding also requires the matching old generator for that
recorded comparison.

Replacement builds, the installation/restoration cycle and the repaired
unequal-cargo World-only session are complete, including retention of the new
`Ocean2` preset and `wo5` save through a final restoration/reinstall. The fresh
process reproduced `Ocean2` byte-for-byte and loaded `wo5`, with independent
world-state readback accounting for native crop-save normalization. The new
Food + World profile has build, compiled-runtime and installation/restoration
coverage, but no actual expanded-menu game session. Other world sizes retain
their historical 0.11 acceptance and were not rerun with the 0.4 menu.

The package manifest retains `actual_game_test_performed` false because package
preparation itself is not a game session. Accepted observations are recorded
here with their selected native profile and scope. Food remains optional.
Extended trade, combat, active-AI economy and long-session disaster behavior
need broader play coverage.
