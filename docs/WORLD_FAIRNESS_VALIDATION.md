# Island inspection, fair starts and resource distribution validation

This record covers **0.5.0-dev.1**, reviewed on **8 November 2026**. The seven
earlier expanded-menu features
retain their own [0.4 validation record](WORLD_OPTIONS_VALIDATION.md). Earlier
compilation, installation, live gameplay and save/reload observations do not
certify the new generator.

## Feature contract

All world choices remain inside Anno. The installer independently selects
World Settings with or without the Food overhaul; it does not configure worlds.
The five menu pages are **World**, **Players**, **Starting options**, **Presets**
and **Islands**, beside the persistent seed and exact cached map preview.

| Addition | Intended behavior and limits |
| --- | --- |
| Island inspection | Clicking any island inspects it without changing the starting position. Details include climate, dimensions, catalogue fertile-land estimate, planned crop/mineral availability, inhabitants/special faction, template ore and whale occurrences, starting eligibility/assignment and nearby ordinary-island resources. |
| Area estimate | The catalogue's `fertileLand` count is an estimate of fertile terrain. It is not a guarantee of buildable area, coastal accessibility, a valid building footprint or accessible mines. |
| Explicit preferred start | A separate button prefers an eligible inspected ordinary island. Native, Pirate and Venetian islands remain inspectable but cannot be selected as starts. Existing climate preference and safe coastal-water checks remain. |
| Balanced starts | Optionally assign distinct ordinary starting islands to the human and selected AI opponents. Compare fertile-land estimates and resources, honour a preferred human island/climate, and apply close/balanced/distant separation. Refuse impossible requests rather than silently reducing requirements. |
| Resource distribution | Original distribution, Spread resources and Specialised regions relocate planned resource assignments within native climate support and actual ore-occurrence capacity. Spread favours separation; Specialised regions favours grouping around a compatible seeded region. Both preserve each resource's world count from the selected fertility level; per-island availability can change. Saturated fertility or native/climate constraints can leave modes with the same assignment. Native/special-faction assignments stay untouched. Essential world coverage remains required. |
| Optional nearby basics | Grain, flax, potatoes, iron and salt must be present on ordinary islands within `max(128, worldSize / 4)` tiles of each participant's starting island. Crop access counts fertile terrain rather than polar raw flags. This can add resources above the fertility-selected world abundance. It is not a promise that every Food-overhaul production chain is local. |
| Preview markers | A white outline identifies inspection; **S** marks the human start and **1–3** mark assigned ordinary AI starts. Pirate/Venetian badges remain distinct. |
| Presets | Version-2 bounded text includes all 27 settings and the new generator identity. Older preset files are preserved and refused when their fingerprint/schema differs. No silent migration is performed. |

Fair starts use the existing inspected ordinary-player range. They do not
increase player capacity or implement the planned smarter-AI module. Native
special-faction roles, Food changes, checked vanilla behavior in World-only,
original installed files, backups and saves remain preservation requirements.

## Source and ABI

The existing 96-byte settings structure gains four signed 32-bit fields:
`fairStarts`, `startSeparation`, `resourceDistribution`, `guaranteeBasics`.
The original prefix remains at the same offsets. The new settings size is
**112 bytes**; the exact cached preview is **5248 bytes** with the unchanged
40-byte island rows. The island-details read-only query is a separate bounded
44-byte structure, so inspection does not mutate the cached plan.

Defaults keep the original start/resource policy: fair starts disabled,
balanced separation selected but inactive, original distribution, nearby-basic
guarantee disabled. The authored source is staged onto copies of the immutable
43 imported compiled inputs. Stock and Food builds retain their separate
native preimages and runtime identities.

## Reviewed native builds

The current generator fingerprint is
`ws5-9763e325b88da3c2e60d75368626888fe5effa444071076c45bb3683dada1808`.

| Native profile | Canonical SHA-256 |
| --- | --- |
| World only | `3ae9e17383ff7aa4405fe0a39274f81e443d545f10582c395cc97c138554f371` |
| Food and World | `f2eab1d1a9dcb7aaa35f2e28b277101e94d0b538a9b77583f59d031cad1d381b` |

Both profiles compiled three times from separate staging directories to
byte-identical outputs with the reviewed Zig 0.16.0 toolchain. The third
builds published the matching local runtime profiles. Every build checked
the original 43 compiled-source fingerprints, exact profile-specific AMD64
executable/module fingerprints, all nine native hook preimages, all 173 engine
edit preimages and both chained-unwind parent records. The required exports,
new settings/snapshot schema and canonical metadata also passed.

An independent read-only staging audit exercised both native profile recipes:
112-byte settings, 5248-byte previews, all 27 preset fields, unchanged imported
source dictionaries and resource/start/details helper ordering matched the
shared contract. The separate island-details structure is 44 bytes and its
query requires the caller's size to match; a non-ready or invalid-index request
is refused without modifying the output.

These are compilation and native-input proofs. No game is executed by the
builder or staging audit, and publishing a runtime profile does not install it.

## Evidence status

Each result below is bound to this build and the stated evidence layer.

| Layer | Current scope |
| --- | --- |
| Menu/parser fixtures | Ten targeted tests passed for source staging, all-field version-2 round trips, unsigned seeds, malformed/truncated/foreign presets, safe preset names and the native island-description formatter. |
| Shared settings, planner and start policy | Public suite passed: 216 tests run, 211 passed and five Windows symlink-privilege skips. Native fixtures include fair starts and eight resource-policy tests. |
| Exact AMD64 native compilation | Both profiles compiled three times with identical canonical hashes; exact profile-specific native preimages and frozen source checks passed. |
| Full compiled-runtime API fixtures | Both real compiled profiles passed the 192-profile-plan distribution matrix, repeatability/detail comparisons, fair human starts, feasible/infeasible basic guarantees and 60 actual scene-serialization checks outside Anno. AI count was zero; no activation guard was bypassed. |
| Installer/restoration | Production closed-game restoration/install cycle passed for both 0.5 profiles, preserving all checked source inputs, existing saves/presets and historical backup generations; see the separate lifecycle scope below. |
| Actual game UI/world/save/restart | World-only passed its five-page menu, 27-field Fair1 preset, new 1024 world with three active ordinary AI opponents, independent ws51 save comparison and a distinct-process preset/save reload. Food + World reproduced Fair1's exact preview, loaded Fair2 with one validated AI, saved ws52, reloaded it in a fresh process and resaved as ws52r. Saved-resource guarantees, persistent physical mineral masks and live Food-diet/controller criteria passed. Fresh Fair2-preview reproduction is not claimed. |
| Final preservation and installed selection | Production return to World-only passed with Food disabled. All 32 pretest saves, two older presets, 12 original backup generations and checked source/legacy inputs remained exact; all new test saves/presets and 17 previous restoration generations were retained. |
| Extended gameplay | Not established by short menu, generation or save checks. |

The menu/parser fixtures execute native C outside Anno. They do not establish
actual in-game layout, control focus, loaded-world assignments, mining access,
Food economy behavior or live AI settlement.

## Automated checks and native policy fixtures

The full public suite completed in 173.910 seconds on Windows: **216 tests
run, 211 passed, five skipped** because Windows symlink creation privileges
were unavailable. The private complete log is retained locally. The suite
includes existing package/profile/copy/restoration refusal checks, new ABI
validation, native scene-owner evidence and the new settings policies.

Eight resource tests execute native C against the real reviewed template
catalogue. They check deterministic modes, world resource counts, unchanged
geometry and native/special islands, geographic clustering/spreading, guarantees
for each selected player, full-slot mineral swaps, impossible-request rollback,
polar nonplant exclusions and invalid native-capacity rejection. Fair-start
fixtures check distinct safe deterministic starts, preferred-human constraints,
inactive-owner preservation, infeasible land/separation refusal and summaries.
Those policy fixtures model their scene/resource boundaries outside the game;
their results do not establish native AI settlement or simulation behavior.

The local C fixtures used the existing reviewed Zig toolchain. No independent
GCC/Clang installation was available on the local Windows PATH, and no local
Linux fixture execution was performed. Separately, all four GitHub Actions
checks passed for commit `244aa2ae65cd1cb87adb4828fca8da88bbed1336` in
[run 42516955171](https://github.com/GOjayson/anno1503-grand-overhaul/actions/runs/42516955171).
The local test count and skips above are not asserted to be identical to every
CI environment. Repository privacy/content checks passed for 569 public files;
the scoped whitespace check also passed. Licensed native inputs, copied island
assets, saves and complete private reports remain ignored and unuploaded.

## Actual compiled DLL APIs outside Anno

Both reviewed DLLs were loaded by an isolated fixture process and their real
planner, cached-preview, island-details, summary and scene-staging exports were
called. The private report records these results separately from game runs:

- **96 shared distribution scenarios / 192 profile plans**, each checked for
  exact repeatability and cross-profile identity. The matrix covers all three
  resource modes, four fertility levels, seeds zero and `4294967295`, worlds
  512/1024/2048 and several layout/climate combinations. Resource counts,
  geometry and the 44-byte island details matched between profiles.
- **12 fair human-start scenarios**, including explicit preferred-island
  application without changing geometry. This matrix uses zero AI opponents;
  active native AI owner allocation remains a separate game check.
- **12 feasible nearby-basic cases** and **12 infeasible nearby-basic
  refusals** across the two profiles. The feasible cases independently
  established native grain/flax/potatoes/iron/salt availability within the
  reported island-edge radius. Incompatible preferred starts were also refused.
- **60 scene stages** serialized the exact cached preview into real native
  scene chunks. Island links and expected human ship positions matched. A
  change to any new settings field was refused before creating a scene file;
  staged-state details queries were refused without output mutation.
- Bounds and structure-size guards on the details API rejected invalid calls
  without changing caller output.

The fixture used 111 verified copies of island/dummy assets in a separate
ignored directory and verified them unchanged afterwards. It did not write
the managed working copy, start Anno, install/activate hooks, bypass AI
configuration guards, load a native world or exercise the game UI. This proves
real compiled policy/serialization behavior, not an actual game session or
the complete Food economy.

## Isolated multi-player-count policy fixture

A separate private fixture copied the exact staged planner prefix into an
isolated native test library. It deliberately substituted the **AI
configuration gate only inside that fixture** so selected-player policies
could be inspected without starting Anno. The published DLLs, native
activation guards and original sources remained unchanged. Eighteen zero-AI
cases matched the actual reviewed DLL's plans exactly, bounding the effect of
that fixture substitution.

The fixture found feasible settings at seed `123456789` for a stock profile
with three selected AI opponents and Spread resources, and a combined profile
with one selected AI opponent, Specialised regions and guaranteed basics. It
recorded the expected starts, positions, resource masks and balance summary
for later comparison. These are **policy predictions**. They do not prove
native controller allocation, activation, game loading, live AI behavior or
save/reload compatibility with active opponents.

## Production installer/restoration cycle

With Anno closed, the high-level production installer completed this sequence
on the independent managed copy: restore the accepted 0.4 journal, install and
restore World-only 0.5, install and restore Food + World 0.5, then reinstall
World-only 0.5. Both fresh prepared packages matched the current native runtime,
generator and Food selection. Reapplying each installed selection passed the
production exact-no-op check.

The stock installation changed 19 managed files; the combined installation
changed 41. Every restoration returned the 23 inspected stock inputs and
removed the 19 introduced payload files. The original installed source's 23
checked native/data inputs, its 297 historical backup files, all **32 existing
native saves**, both older preset files and all **12 older restoration
generations** remained byte-exact. Three new restored generations were retained,
giving 15 previous generations at the end. The legacy source inventory and
all 43 compiled inputs also remained unchanged.

The cycle used the production closed-game guard without substituting or
bypassing it. It did not launch Anno, operate its UI, write process memory or
terminate processes. These are real installation/restoration comparisons,
separate from actual in-game acceptance of the new options. The existing
presets' older schema/generator identities remain preserved on disk; they are
not silently converted by installation or restoration.

## Actual World-only game: Fair1 and ws51

The independently managed World-only copy launched through the production
automatic path with the current `3ae9e173...` runtime. The actual copied game
process passed its executable/module identities, all nine hook checks and all
173 engine-byte checks. Installed disk inputs remained unchanged by in-memory
activation. The original installed Ubisoft game remained a preserved input.

The actual in-game screen displayed **World**, **Players**, **Starting options**,
**Presets** and **Islands**. The user configured and saved **Fair1** with all 27
settings: seed `123456789`, 1024-square world, Mixed islands, 24 islands, spacing
zero, three ordinary AI opponents, Medium stock preset, 30,000 starting money,
Single ship, Easy AI, Medium plant/mineral fertility, Balanced climate, Evenly
spread layout, all eight native cultures, Pirates, Venetians and disasters
enabled. Fair starts and Balanced separation were selected; resource
distribution was **Spread resources**, nearby basics were disabled and custom
cargo was disabled.

The on-disk preset matched every field of the independently captured ready
preview. Its SHA-256 was
`3c534a0073380367af49691c82a35e7927f1f5465124b6699b115f6f83680263`;
the island plan was
`c766954043cb25d5c5fd5869e374bafc899f82d47a076c6e7141b63de8ac4b06`.
The actual preview agreed with the earlier isolated policy prediction. Stored
custom-cargo numbers differed from that prediction only because custom cargo
was disabled, so those inactive values did not change the map or fleet.

The observed **Islands** page displayed four fair starts, estimated fertile
land **739–1169 tiles**, nearby resource scores **5–10** and nearest starting
fleets **377 tiles** apart. Both documented balance ratios passed 2:1. Clicking
island 23 displayed its Steppe climate, resource information and assignment to
ordinary AI opponent 3 without changing the preferred human start. This
establishes the observed inspection UI for that case, not every DPI setting or
every possible island selection.

Clicking **Start** loaded a native world and completed the native commit with
no factory, hook, AI-loader or profile errors. The profile status was 4 and the
validated ordinary-AI count was three. A separate read-only inspection of the
actual controllers confirmed active owner IDs **1, 2 and 3**, with owner 4
disabled/suspended and not thinking. All 24 island geometries/climates and the
native crop availability matched the captured plan under the original native
initialisation rules. Stock diet profiles for the human and ordinary-player
records passed all five checked levels; the Food overhaul was disabled.

The human's single small trade ship was at **104.5, 984.5**, the assigned
coastal position. Its four 50-ton holds contained the preserved Medium-preset
supplies: 50 wood, 10 food and 80 tools in two stacks. Capacity, full health and
zero cannons matched the default fleet. The AI ships were already moving by
the read-only observation, so that observation does **not** prove their exact
initial spawn coordinates or subsequent settlement quality.

The user saved the world as **ws51**. An independent offline parser verified
the native save alias, 1024 dimensions, all 24 island geometries/climates,
harvest-crop masks and positive-quantity mineral masks against the preview and
corresponding live evidence, accounting for native crop initialisation/save
normalisation. It also matched the human ship's position, cargo/capacity/health,
disaster flag word `0x0` and ordinary-player suspension states. The selected
stock diet was established separately by the live inspection, not inferred
from the save. The save's SHA-256 was
`91d9760b36945ae6c1b19f950ef446db7a5e48e39989156903d9f3f102faccd9`.
Physical mineral quantities prove serialized positive deposits, not mine
accessibility or later depletion behavior. Polar nonplant flags follow the
unchanged native save rules described in the earlier validation record.

The save comparison does not infer initial cash from elapsed gameplay, exact
initial AI positions or AI food/economy quality.

## World-only fresh-process preset and ws51 reload

After the first game closed normally, a fresh production launch created a
distinct process and creation identity. Loading **Fair1** through the in-game
Presets page reproduced all 27 settings and the **entire decoded ready
preview** exactly. Its ready-snapshot SHA-256 remained
`1b88a7049212fa5284d084c1204ebd260fec49485103da2e918d671692018c65`,
and its island-plan hash remained the Fair1 value above. This is actual
fresh-process preset reproducibility, beyond the earlier isolated API fixture.

The actual native game then loaded **ws51** successfully in that fresh process.
Diagnostics again verified all nine hooks, all 173 engine edits and clear
factory/hook/AI-loader/profile errors. A separate read-only comparison passed
all 24 island geometries/climates and all 13 serialized harvest-crop bits,
the exact human fleet's position/cargo/capacity/health, world flags and the
selected stock-diet criteria across all five checked resident levels. It
confirmed active ordinary owners 1–3 and owner 4 suspended, not thinking and
inactive.

Two native load normalisations remain explicitly outside byte-equality claims:
polar islands 6, 12, 15 and 20 lost only the previously documented high
nonharvest flags; inactive owner 4's internal `disabled` field changed from
one to zero while its suspension/thinking state and observed inactivity stayed
unchanged. Raw diet-profile byte equality is not claimed; the actual stock
diet criteria passed independently before and after reload. Moving AI ships
were not expected to remain stationary between observations.

The native ws51 save independently established physical positive mineral masks
equal to the preview. This restart comparison does **not** claim enumeration
of live physical ore objects after reload or proof of mining access.

## Food-enabled in-game preview

After a normal close and production feature switch, the Food + World runtime
opened the actual World Settings screen. Loading **Fair1** reproduced the
**exact same complete preview and all 27 settings** as World-only, with the
combined `f2eab1d1...` runtime instead of the stock `3ae9e173...` runtime. This
is an actual cross-profile menu/preset observation, separate from the earlier
compiled-DLL comparison.

Enabling nearby basics on the loaded three-AI Spread configuration visibly
cleared the preview and refused Start with the native-capacity explanation
that no compatible free iron or salt deposit was available in a starting
region. The screen did not silently relax the requested guarantee.

Preview equality and visible validation are distinct from the actual
combined-world loading and save checks below.

## Food-enabled Fair2 world and ws52 saved-resource proof

The user configured and saved **Fair2** inside the Food-enabled game. An
independent preset/preview comparison verified all 27 fields and exactly three
changes from Fair1: **one AI opponent**, **Specialised regions** and **nearby
basic resources enabled**. Its preset SHA-256 was
`0ce6d0b74802b5462d69bba1f36df26bfc2eb7c9e2fb8d1b129ee49ddc967ed8`;
the ready-snapshot hash was
`0b401d77faf9ddb2ee1aa3bc0dab26f16c39db7e338b295e4b7afb1c9413ae04`;
and the exact plan hash was
`3b548b42710c741ad63ec488504b745b9fa41e98e611ebda913d010de1c71674`.
The human start was island index 11 (UI island 12) and the ordinary AI start
was index 23 (UI island 24), matching the bounded policy prediction.

Clicking **Start** loaded a native world under the exact combined runtime and
reached committed preview state 3. Native diagnostics reported a validated AI
count of one, profile status 2, all nine hooks and all 173 engine edits verified,
clear factory/hook/AI-loader/profile errors and no installed-file changes from
activation. This establishes actual loading with the selected combined native
profile; Food demand data and controller state were checked separately by the
read-only live-memory observer described below.

The user saved the world as **ws52**, SHA-256
`3045fde07a63c9103deafd52d67d482b79a9b48f3a8fa59358107941e7b1b88d`.
A separate read-only inspector used frozen native-save parsing and faction
metadata, without importing the current resource policy, attaching to a game
process or changing the save. It verified the alias, all 24 saved island
geometries/crop assignments and physical positive-quantity mineral masks
against the captured preview. It independently recomputed ordinary-island
resource unions within the **256-tile Euclidean island-edge radius** of both
selected starting islands:

| Selected start | Nearby growing-crop mask | Nearby positive mineral mask | Basic-resource result |
| --- | --- | --- | --- |
| Human, island index 11 | 6217 | 37 | Grain, flax, potatoes, iron and salt present |
| AI opponent 1, island index 23 | 5837 | 5 | Grain, flax, potatoes, iron and salt present |

Crop access required native climate compatibility and positive saved fertile
terrain; native and special-faction islands were excluded from the unions.
The independent global unions were `0x1fff` for harvest crops and `0x2f` for
positive minerals. Positive saved deposits included four iron, two salt, three
gold, two gem and one marble occurrences; zero-quantity persistent iron records
were excluded from positive resource availability.

This proves the saved availability guarantee around the selected starting
islands, not harvesting/mining access, shipping-route navigability, exact
initial AI ship positions, long-term deposit tonnage or the complete Food
production economy. The human ship moved before ws52 was saved, so no separate
first-frame human-position observation is claimed either. The native at-start
certificate passed its expected initial fleet/coastal checks; later save/reload
comparisons must use the actual saved fleet position.

## Food-enabled read-only live inspection

A separate inspector read the actual Food-enabled game without target writes,
remote function calls, UI input or process control. It passed all 24 island
geometries/climates and all 13 harvest-crop bits. The human and ordinary-player
records passed the selected **five-food demand criteria at all five checked
resident levels**. Actual ordinary owner **1** was active, unsuspended and
thinking; owners **2–4** were suspended and not thinking. This is observed
native profile/controller evidence, not proof of a complete AI food economy.

The game had progressed and the human ship had moved before this observation.
The inspector recorded its current in-world coordinates, four 50-ton holds, full
health and current cargo: zero wood, three food and 65 tools. That elapsed
cargo differs from the earlier ws52 save's 50 wood, ten food and 80 tools.
Current gameplay is not used as evidence of initial fleet coordinates, and a
ws52 restart comparison must compare against ws52's actual saved fleet/cargo.

Island 11's current raw crop field included an additional upper bit 24 while
all 13 harvest bits remained equal to the planned availability. The upper
flags were recorded without interpreting their cause. Full raw crop-field
equality after elapsed gameplay, a discovery-state explanation or a production
engine change is not claimed. The native at-start certificate and independent
saved harvest/resource checks remain separate evidence.

These short observations do not establish mining accessibility, long-session
AI settlement, trade/combat stability or the complete Food overhaul economy.

## Food-enabled fresh-process ws52 reload

A new production Food-enabled launch created a distinct game process with the
same reviewed combined runtime. The actual native game loaded **ws52**
successfully. Diagnostics verified all nine hook sites, all 173 engine edits,
the expected executable/module identities and clear factory/hook/AI-loader/
profile errors. This was an original native save load, rather than a new-world
generation attempt; its new-world profile-status counter was not used as proof
of controller state.

The separate read-only observer and independent evidence comparison passed
all 24 island geometries/climates and all 13 harvest bits, world dimensions and
flags, the human fleet's composition/capacity/cannons/health, and the **actual
ws52 saved position and cargo**. Reloaded cargo was 50 wood, ten food and 80
tools. Those saved values are deliberately compared with ws52, not with the
later elapsed-play observation in which the human had moved and used cargo.

The five-food criteria passed at all five checked resident levels both before
and after restart, without asserting equality of raw diet-profile bytes.
Ordinary owner 1 remained active; owners 2–4 remained suspended, not thinking
and inactive. Their internal `disabled` fields changed from one to zero on
initialisation; those fields are reported separately from the preserved
suspension/thinking/activity criteria. AI movement between observations was
not treated as a persistence failure or proof of initial spawn stationarity.

Polar islands 6, 12, 15 and 20 followed the documented original native
nonharvest-flag load rules. The extra upper crop bit 24 seen during elapsed
play on island 11 was absent after reloading the older ws52 state; its cause
was left uninterpreted and every harvest bit matched. No full raw crop-field
byte-equality claim or engine change follows from that difference.

The original ws52 saved physical mineral masks and both selected starting
regions' resource guarantees were independently proved above. Enumeration of
live physical ores after reload is not claimed; the subsequent native resave
and independent physical-mineral comparison are recorded below. Fair1's
fresh-process preview and cross-profile equality were observed separately;
an exact fresh-process **Fair2** preview reproduction has not been retested.

## Food-enabled native ws52r resave and availability persistence

After the fresh-process ws52 load, the actual in-game save interface created
**ws52r**, SHA-256
`24207e84245146f3b70bee648fc9494b0c00e5c8b0ccf41bd2ea674a5d9e1e0a`.
Separate offline readers verified its native alias, 1024 dimensions, all 24
island geometries/climates, all 13 harvest bits and physical positive-quantity
mineral masks against both ws52 and the captured Fair2 preview. The saved
human/controller fields were checked with their corresponding observed scope;
elapsed positions, cash and cargo were not required to remain equal to the
original selected starting supplies.

The independently computed resource unions around both selected starting
islands remained exactly equal to the ws52 values in the table above. Grain,
flax, potatoes, positive iron and positive salt were still present within the
256-tile island-edge radius, counting ordinary growing land and excluding
native/special islands. The positive saved occurrence counts remained four
iron, two salt, three gold, two gems and one marble. Zero-quantity persistent
absence records retained their positions. Thus the availability guarantee
survived actual native load and resave, beyond the original generated-save
proof.

This comparison does not require or claim equality of ore tonnage after
elapsed gameplay, accessible mining sites, successful harvesting or navigable
shipping routes. It also does not replace the separate live diet/controller
criteria or assert stationarity of initial AI/human ships.

## Test saves and autosave preservation

The native ws52 and separate progress save **ws52p** remained byte-exact while
ws52r was created. An independent final read-only check verified their hashes
again. No accepted test save was overwritten to create the new resave.

Normal gameplay had advanced the shared **Lastgame** autosave during the first
Food-enabled session. Before restoring the pretest autosave, the advanced
version was retained as private evidence with SHA-256
`99fb9a65426752618ed98a652667569934d47e24d38b58926d2eb385f097c7db`;
the separate native ws52p progress save was retained as well. With the
production closed-game guard satisfied, the pretest autosave was restored
byte-for-byte to SHA-256
`68d21293558d935333cc24f94cf6466a23a2f4f1cb50a53095e70c4f518de963`.

After the final normal Food-enabled game close, another guarded preservation
check found that the current Lastgame was already identical to that pretest
hash, retained another private copy and rechecked ws52/ws52p unchanged. This
distinguishes a naturally changed gameplay autosave from the preserved
pretest data and the retained test progress.

## Final managed-copy selection and preservation comparison

After the Food-enabled game closed normally, the production closed-game guard
passed. The installer restored the combined journal and installed the reviewed
World-only 0.5 profile, changing 19 managed files. The final managed selection
was **World Settings enabled, Food overhaul disabled**, with the canonical
`3ae9e173...` runtime. Anno was closed at completion of this check.

The final switch preserved all **36 native saves**, all **four presets** and
all existing previous restoration generations. A separate comparison against
the pretest baseline then verified all **32 pretest native saves**, including
the restored Lastgame, both older presets, all **12 original restoration
generations**, the installed source's **23 checked native/data inputs**, its
**297 existing backup files**, all **488 legacy source files** and the **43
compiled-input fingerprints** unchanged. The new ws51, ws52, ws52p and ws52r
saves and Fair1/Fair2 presets remained alongside the originals. There were
**17 retained previous restoration generations** at the end.

This final lifecycle is separate from the earlier closed-game cycle ending
with 15 previous generations. It uses the production restoration/install
logic and guard, not a replacement native patch or a manual target-file
overwrite. Public native/generator code remained unchanged after commit
`244aa2ae65cd1cb87adb4828fca8da88bbed1336`; the remaining updates record
observed validation scope. Repository privacy/content and scoped whitespace
checks passed again.

## Acceptance checklist

The evidence sections above distinguish completed checks from remaining scope;
the list below states the acceptance requirements without extending any result
beyond its observed profile, settings and evidence layer.

1. Verify immutable source closure and exact AMD64 executable/module
   architecture, native hook/engine preimages and unwind metadata separately
   for the World-only and Food + World profiles. Compile reproducibly and bind
   packages to the exact reviewed runtime, generator and snapshot identities.
2. Exercise deterministic seeds across distribution modes, fertility choices,
   climates, supported world sizes and active-player counts. Independently
   check world/resource coverage, ore-slot capacity, per-resource world counts,
   spacing, non-overlap and border limits.
3. Check fair starts with each separation mode, preferred human island/climate,
   one to four actual participants and impossible combinations. Verify distinct
   ordinary islands, measured fairness constraints, coastal water and the
   exact selected-player/native-owner mapping.
4. Check the nearby-basic guarantee around every actual participant, including
   impossible iron/salt capacity cases. Confirm it may add only valid native
   resources and that disabled guarantees do not inflate fertility-selected
   world abundance.
5. Compare ready preview, staged scene, loaded world and a saved/reloaded world.
   Check human and ordinary-AI ship positions, resource masks, special factions,
   selected Food/stock diet and retained existing starting options.
6. Observe the five actual menu pages at the supported display scale. Inspect
   ordinary/native/Pirate/Venetian islands, confirm selection does not alter a
   preferred start, test the explicit start button and rejected starts, and
   exercise new settings through preset save/reload and a fresh process.
7. Restore/reinstall each supported selection on managed copies and compare
   original inputs, stock backups, all existing native saves and preset files.
   Keep every older backup generation and ensure the installed Ubisoft source
   is unchanged.

Do not infer long-session AI quality, harvesting/mining accessibility or Food
economy correctness merely from mask, scene or serializer checks.
