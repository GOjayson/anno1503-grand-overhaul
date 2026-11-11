# Map visibility and terra incognita validation

## 0.6.0-dev.4 performance candidate

This candidate addresses V4's remaining lag by batching remembered-sprite
capture within each current draw. It preserves the chart format, save ABI,
all existing hooks, exact line-of-sight rules, remembered appearance and exact
per-figure/per-quad animation time. It adds no cross-draw native pointers or
observation timestamp shortcut. V4's bounded ownership/scout success below
remains separate from acceptance of this new performance candidate.

| Identity | Reviewed dev.4 candidate |
| --- | --- |
| Generator | `ws6-bb6c7cd8c16e0aaa71a5693f960770dd2f85af479830ad17ca2c3527867dedfb` |
| World-only runtime SHA-256 | `95ee49834a60393f95043e3c52323f5b846bf03ecce5fbdc660971dfb1f2ab4f` |
| Food + World runtime SHA-256 | `9afe681786d84267c48d13f029194d975b8a1fef6b843b7a1c59e5e804717c5b` |

Each profile produced three byte-identical runtimes: two independently
reviewed candidates and its completed publication build. The independent
six-build audit passed **34 raw LF/index generator inputs, all 488/43 immutable
inputs, the 65-source staged closure, the unchanged 85-export ABI, all nine
native module pins and the complete 26-visibility/208-component transaction**,
including native function bounds and TLS. Canonical pins were promoted only
after the four-build pre-pin review. The full suite completed **358 tests in
195.016 seconds: 353 passed and five Windows link-privilege tests were
skipped**, with no failures or errors. Closed-game preservation and the
production installer/restoration cycle passed. The final World-only build is
installed. Fresh automatic native startup and loading `wc4` passed. The user
confirmed remembered towns look correct and saved `wc5`, but camera movement
still feels laggy while a stationary view is smooth. **This candidate has not
resolved the reported performance problem.** Food gameplay is not being repeated.

Before the cycle, the closed-game preservation check retained **43 named
worlds / 44 native saves, all 68 protected save-directory files, five presets,
41 preceding backup generations, 23 original source inputs, 297 historical
backups and all 488/43 imported inputs**. The current progressed autosave was
archived exclusively and verified byte-for-byte; no older autosave was
restored. The subsequent closed-game cycle retained that exact save tree,
all five presets, the 41 earlier backup generations and every original input.
Three new restored generations give **44**. All pre-existing validation
evidence remained byte-exact across the two full evidence-hash passes.

The final installation has **World Settings enabled and Food disabled**,
using the reviewed World-only runtime above. The automatic-launch shortcut
was updated and its preceding V4 shortcut preserved. A fresh automatic launch
passed with the exact installed runtime. The loaded `wc4` reported all **26
visibility components and 173 engine edits** active, last error **0**, and no
pending masked rows or owned copies. A separate read-only observer matched the
24-island geometry/resources and found the deployed human scout eligible for
vision. Those native checks do not establish smooth camera movement.

The independently inspected `wc5` retains the world identity, 1024-square
dimensions, Unexplored/Strict policy, all 24 island geometries/climates, the 13
interpreted crop bits and physical ore masks. All **2,320** preceding chart
bits and **8,499** known minimap bits remain, with **18** and **61** added.
All **5,252** preceding observed cells remain observed. The 178 preceding
island-0 and 113 island-7 anchors retain every recorded byte, including times;
these are bounded disk comparisons, not complete current-sight or intervening
travel proofs. Both original save files were archived exclusively. No V5
fresh-save reload or performance acceptance is claimed.

Eight new batch methods and 19 existing native methods passed. Independent
source review and a repeat of the eight batch methods passed. Original native
instruction execution passed **480 cases**, comparing **20,352 exact output
tuples** across both profiles, two relocations, all camera rotations, shared
quads, static/animated and period-zero assets, live-cell exclusion, cross-quad
footprints and exact last matching cell times. Conflicting phases and changed
asset bindings retain their refusal paths. These are CPU/helper proofs, not
GPU ordering or actual game acceptance.

Actual compiled-DLL APIs passed **72 isolated scene stages** across both Food
selections, all six policies, 512/1024/2048 worlds and two seeds, with AI zero.
They do not run Anno. In the paired synthetic Windows benchmark, actual capture
preparation for 4,000 figures fell from **4.40 to 1.34 ms** for static figures
and **5.33 to 1.26 ms** for mixed figures. Observation remained about **1.2 ms**
and is unchanged. These timings measure this specific CPU work, **not game
FPS or a demonstrated correction of the user's remaining lag**.

## V4 0.6.0-dev.3: ownership/scout checks passed, performance incomplete

The V4 source addresses three user-reported failures in V3. Automated
checks, reproduced builds, independent artifact review and the production
installation/restoration cycle passed. A fresh automatic World-only startup
loaded `wc3`. The user confirmed that foreign controls are blocked, own
controls work and a deployed scout reveals land. This is bounded hands-on
acceptance of those two repairs. The user saved `wc4`; its independent file
inspection passed, including retained exploration history. An eligible native
scout observer was also confirmed. Lag improved but remains noticeable, so
**performance is unresolved and complete repair acceptance has not passed**. No Food + World
gameplay run is being repeated, at the user's request.

| Identity | Reviewed 0.6.0-dev.3 repair |
| --- | --- |
| Generator | `ws6-0394e0a1e15da31501da912e6760f36c8ffcc1651e624c98138b46d6c3ad9375` |
| World-only runtime SHA-256 | `3dd5d6fad83c33aded8e0b8b96b0fa2cd12234601e917674fcbcb92df5cff80f` |
| Food + World runtime SHA-256 | `5ad71345ce2f23ed45c77206423052c769f921bb72fd84cedef00e44674f1207` |

Each profile has three byte-identical completed builds: two candidates and
one publication build. The independent pre/post-publication artifact audits
passed all six actual DLLs, **34 raw LF/index generator inputs, 85 exports,
11 pointer hooks, 15 code branches, 26 visibility components and all 208
transaction components**. The 173 existing engine edits remain intact.

The complete suite ran **350 tests in 182.664 seconds: 345 passed and five
Windows link-privilege tests were skipped**. It finished without failures or
errors. Actual compiled DLL APIs also passed **72 isolated scene stages**
across both Food selections, all six policies, 512/1024/2048 worlds and two
seeds, with zero ordinary AI. These checks neither start Anno nor establish
rendered behavior, gameplay performance or active-AI acceptance.

The completed production cycle restored/installed the reviewed profiles and
finished with World Settings enabled and Food disabled. It retained **42 named
worlds / 43 native saves, 56 protected save-directory files, five presets,
23 original source inputs, 297 historical backups and all 488/43 imported
inputs**. The 38 preceding backup generations remained intact; three newly
restored generations give **41**. This closed-game cycle does not establish
rendering or performance.

Automatic startup and the certified `wc3` load then passed in a fresh process,
with the bounded activation/error checks clear. The separate 96-byte chart
diagnostic initially returned busy during rendering, then passed at an idle
observation: 26 visibility components and 173 engine edits active, no error,
zero pending rows or owned copies, and equal masked/restored totals of
330,552. It reported 2,329 charted cells, 2,838 remembered anchors and 8,529
known minimap pixels for the 1024-square Terra/Strict world. The save-memory
error was empty. These counters are native state evidence, not game FPS or a
complete rendered-frame proof.

| Repair | Source and automated scope | Actual game status |
| --- | --- | --- |
| Dense building-memory lag | Mix aligned coordinate bits before hash-table indexing; preserve exact key comparisons and remembered appearance. Picking passes read history without observing or updating it, and skip presentation refresh work. Dense native lookup and full-wrapper fixtures pass. | The user reports improvement but still-noticeable lag. Performance remains unresolved; CPU-fixture speedup is not game FPS. |
| Foreign building control | Restore the ordinary native ownership-selection test at two interaction consumers. Independently authorize the two shared production/food-sale and ship-queue command interfaces using the current registered building/city/island/player ownership graph. Reveal and remembered appearance grant no command authority. Unmarked native worlds keep their original delegation. | The user confirmed foreign controls blocked and own controls working. This is a bounded check; stale selections, broader command paths and read-only information/trade still need extended coverage. |
| Missing military/scout exploration | Add eligible human-owned deployed scouts and military units to charting/current sight at the unchanged 48-tile radius. Six audited native classes share a bounded 4,096-record adapter traversal; this is not a native recruitment cap. Dead, transported, foreign, stale and malformed records are excluded. | The user confirmed a deployed scout reveals land and saved `wc4`. Independent history inspection and an eligible native scout observer check passed. Other unit classes and embarked/dead-unit behavior need broader game coverage. |

The completed targeted groups contain **40 visibility/performance/land-unit
methods**, **43 hook/branch checks** and **six ownership-command methods**.
The command tests cover all 28 positively audited native building classes,
all six policies, both native World/Frame/client types, current-owner changes,
malformed graphs, real Windows page/execute protection, legacy irregular map
dimensions, all four arguments and the complete native return value. These are
isolated fixtures; the final original command/getter invocation is a spy.

Separate exact History Edition instruction probes exercised **384 interaction
cases** using the original property getter and selection blocks, and **432
land-unit cases**. Their stock/Food module identities and original preimages
are pinned; classic-version patch addresses are not assumed. The existing
173-edit engine plan is preserved. Source tests are in
[`test_world_visibility_control.py`](../tests/test_world_visibility_control.py),
[`test_world_visibility_land_units.py`](../tests/test_world_visibility_land_units.py)
and [`test_world_visibility_performance.py`](../tests/test_world_visibility_performance.py).
The repair does not establish arbitrary multiplayer replay, every command
interface, combat/navigation behavior or full rendering/selection coverage.

V3’s user-confirmed last-seen retention and revisit updates remain bounded
positive evidence. Its later lag, foreign shipyard queues, production sleep
and food-sale controls, and absent military/scout exploration remain recorded
failures. The independently inspected `wc1`, `wc2` and `wc3` files are native
game-produced checkpoints; their validity does not establish repair acceptance.
The `wc1` to `wc2` stored-data comparison retained all 947 control anchors in
four foreign owner/island groups byte-for-byte, including observation times.
It does not prove the ship’s intervening route or a complete GPU frame.

## Historical 0.6.0-dev.2 V3 chart-memory verification

This preceding candidate added continuous exploration of land and sea, and
last-seen building memory. Source review, reproducible compilation, isolated
native checks, its full suite and installation/restoration passed. Its bounded
World-only building-memory checks passed, but actual lag, foreign control and
missing land-unit exploration reports prevent release acceptance. These V3
results do not certify the dev.3 repair. The accepted older r8 baseline and its
evidence below remain separate.

| Identity | Reviewed chart-memory candidate |
| --- | --- |
| Generator | `ws6-315c8830e9685ede73a466ad8ad7bd9ce39786f22446ede1de709c028cc2da5a` |
| World-only runtime SHA-256 | `2d2cfeb38245bcdd6d68bf20b42e40d039b57969f0628df96414a28ebc0b276b` |
| Food + World runtime SHA-256 | `b538559cf2c3be0a39f24db2e783370859aee5fdb4edd7d08e4cfdb8d4c70007` |

Unexplored terrain uses a permanent chart of eight-tile cells around the
human player's ships and settlements. The main view covers unknown land and
water with opaque black; the minimap conceals both uniformly, without island
outlines. Its native 160-entry palette has no separate opaque-black fog
entry, so no invented palette index is used. Unknown areas stay covered with
either enemy-activity choice. Reveal all activity applies to charted areas;
revealed geography and fully explored modes retain global activity reveal.

Strict line of sight keeps the existing 48-tile activity range. Observed
buildings remain as visual snapshots outside sight, including their last-seen
appearance and ownership colour; they update on observation. Enemy ships and
units still require current sight. Remembered draws do not create native live
objects, but V3’s interaction path still allowed foreign native buildings to
be controlled. Its renderer/picking fixtures did not establish ownership
authorization; the dev.3 repair and its bounded ownership/scout game checks
are recorded separately above.

Chart and building memory belong to each native checkpoint, using a bounded,
checksummed `WSCHART` extension rather than a sidecar. Save As carries the
current snapshot. Loading an older checkpoint restores that checkpoint's
memory; a save without the extension begins conservatively from current
human observers. Historic ship routes and city appearances cannot be
reconstructed from older native discovery bits. Verified complete checkpoint
and native-output backups are retained when augmenting a save. The final
Win32 replacement is name-based, not an atomic FileID comparison against an
unrelated external writer.

The final independent source review passed. Each profile produced three
byte-identical actual DLLs: two candidates and one publication build.
The independent six-build audit verified **33 raw LF/index generator inputs,
488 immutable imported files, 43 immutable compiled inputs, a 64-file staged
closure, 82 exports, seven pointer hooks, 13 code branches and all 202 guarded
transaction components**. The existing engine plan still contains 173 edits.
The save tail jump and final frame's 24-byte context bridge have separate
native preimage and ABI proofs. No classic-version addresses are assumed.

The final native/core fixture passed **27 methods**, including 43 earlier
memory cases, 14 new lifecycle/drawing cases and 4,096 palette comparisons.
The save/load fixture passed **28 Windows methods**; the independent save
inspector passed **15 synthetic methods**. Actual compiled DLL APIs passed
**72 isolated scene stages** across both profiles, all six visibility choices,
512/1024/2048 worlds and two seeds. All 82 copied assets stayed exact; AI was
zero only. These fixtures do not load a native game world or measure GPU output.

Native palette proofs establish asset-specific banks of 3, 27, 96 and 144,
and the exact colour-ignoring format-23 path. Remembered minimap bytes must
fit the native 160-entry lookup. Current frame/texture/palette bindings are
checked again before a matched remembered sprite is submitted. Invalid data
does not receive a live-state fallback. The native period-zero static path is
retained; the unsafe animated period-one case is refused. No guessed owner
colour range or current-player lifetime assumption replaces these checks.

The new Windows CPU benchmark retains r8's actor/coordinate callback query
counts. A single observed 3-by-3 building costs about 0.114 ms per synthetic
observation, including current context/allocation and asset checks. These
figures exclude native rasterization and GPU work; they are **not game FPS**.
The maximum codec fixture used 80 MiB of cell records plus the largest bitmap
history and produced an 88,613,000-byte payload within the 96 MiB codec bound.

Completed private records include `visibility-charted-v3-independent-source-review.json`,
`visibility-charted-v3-published-build-audit.json`,
`visibility-r9-native-core-closure-v3.json`,
`visibility-r9-chart-windows-benchmark-v3.json` and
`world-v6-charted-v3-full-runtime.json`. The two preceding candidate iterations
and their passing structural evidence remain preserved as superseded builds;
neither was installed or used to launch Anno.

The definitive post-pin suite passed **322 tests in 152.058 seconds: 317 passed
and five were skipped** because this Windows account cannot create symbolic
links. It finished `OK (skipped=5)` without failures or errors. Its completed
records are `world-v6-charted-v3-postpin-suite.txt` and the corresponding JSON.

The production installer cycle passed with Anno closed: restore accepted r8,
install/restore the new World-only profile, install/restore Food + World, then
install final World-only. The installations changed 19/41/19 managed files;
each passed the production exact-preparation no-op. Three restorations returned
the 23-file stock closure and removed 19 introduced World files. All **40 saves,
five presets, 35 prior backup generations, five separate autosave archives,
23 original source inputs, 297 historical backup files and 488/43 imported
inputs** stayed exact. Three new restored generations give **38** in total.
The completed report is
`world-v6-charted-cycle-9dcf157a68dc4116bb24dbc3473d60bd/result.json`.
This cycle launched no game and activated no hooks.

The final World-only package launched through automatic production startup,
and the existing `wv63` world loaded. The continuous main-view mask was
observed over both water and land. A read-only live observer verified all
20 visibility dispatches, the 173 engine edits, the saved Terra/Strict policy,
24 islands and the exact original preview geometry, climates and harvest bits.
The observed human player had one controllable ship and no settlements.
This verifies native state separately from the displayed image.

The current `wv63` has a valid `WSCHART` checkpoint. Its original unextended
2,783,755-byte checkpoint remains byte-exact in the exclusive complete-save
backup. A separate in-game Save As, `wc1`, passed the independent native-save
and exploration-history inspector: 2,115 charted cells, 1,973 remembered anchors,
3,624 building-footprint cells and 7,679 known minimap pixels. Save As did not
change the existing `wv63` checkpoint. These are actual game-produced saves,
not synthetic codec fixtures.

The first running-world diagnostic had equal masked/restored row counts,
zero pending rows and no error. While the native pause dialog was open, the
guarded chart getter returned busy, with 57 rows still inside the parent draw
and final-frame error 16 recorded. After resuming, the getter succeeded,
masked/restored totals matched again, pending rows and owned pending copies
were zero, and the save-memory error was empty; error 16 remained sticky.
The pause/presentation case remains under investigation and is not recorded
as an entirely error-free live run.

The user subsequently confirmed that remembered buildings stay visible when
sailing away and update on returning. Independent `wc2` and `wc3` checkpoint
checks passed. Lag, foreign production/shipyard control and missing land-unit
exploration were then reported. V3 therefore remains unaccepted; broader
rendering, fresh-world and fresh-process persistence coverage remain pending.
No additional Food-profile gameplay run is planned, as requested by the user.

## Accepted 0.6.0-dev.1 baseline

This is the **0.6.0-dev.1 development validation record**, reviewed on
**9 November 2026**. **R8 was the accepted frozen performance candidate for this baseline**:
independent source review, three matching builds per profile, targeted
checks, definitive post-pin full suite and isolated compiled-DLL checks
passed. The r8 installer/restoration cycle, automatic startup and certified
`wv63` reload also passed. **The user confirms r8 is smooth and visibility
still works in the requested large-island camera and village-range check.**
This is bounded hands-on acceptance, not measured FPS or complete coverage.
Historical r7 source/build, full-suite, installer and
isolated compiled-DLL checks passed. **Actual r7 World-only startup and certified `wv62` reload passed;
the user reports much smoother play and working visibility, but large
Pirate/AI islands still caused camera-related lag in that r7 run.** Its
`wv63` disk certificate and closed-game preservation checks passed, while
r7's playable-performance acceptance remained incomplete. The later r8
hands-on result above is separate.
R6's actual World-only startup, certified
earlier-save loads and sampled near-to-far-to-near village disappearance and
reappearance remain recorded separately. That live test produced severe lag,
so r6 was not ready for acceptance. Precise interactions, fresh Terra
creation, all-mode coverage and long-session behavior remain outside the
bounded r8 sample. Historical r4/r5 results, including
r5's static village visibility failure, remain separate. This is not a
complete-feature claim.

Food and World Settings remain independent selections. World-only and
Food + World use separately inspected native profiles and reviewed builds.
**At the user's explicit request, Food + World visibility gameplay was not
run or repeated in this iteration and is not a publication blocker.** The
user asked to skip that run because the Food overhaul works. This supplies no
new live Food-profile visibility evidence: both profiles' builds, the 72
isolated scene stages and production install/restore results remain separate
automated checks. Earlier 0.5 island-inspection, fair-start
and resource results remain in [their original record](WORLD_FAIRNESS_VALIDATION.md);
they are not evidence of new visibility behavior.

## Historical r8 candidate identity and precise scope

The accepted r8 candidate pins on 9 November 2026 were:

| Identity | Reviewed r8 candidate value |
| --- | --- |
| Generator | `ws6-0d2879f90b27860951e9a8a67245e9458d4200e6b28c5452505dd016341e31f9` |
| World-only runtime SHA-256 | `50a92fc71221fa3e8a23d97e6971a6b30197de700755da57819a0d25f11cc5f8` |
| Food + World runtime SHA-256 | `70668e10dde3fd6b61480b256dd41a2e280bcf654c573093f41f2fd91a4fc1b5` |

R8 changes only current-invocation actor readability checks and same-draw
stack-position validation. A matched actor layout uses one bounded readable
span before its raw fields; failed probes keep the guarded short-object
fallback. Vtable identity, all four getters, World backlink, owner and finite
current coordinates are checked anew on each callback. The 42 reviewed actor
layouts end no later than offset `0x278`; this is a field-extent bound, not an
engine actor-count limit.

A position uses the stack shortcut only when its entire 12-byte XYZ span
fits the certified committed, private, readable region of the current
thread's active parent draw. Values are copied anew each time. Heap,
uncertified, crossing-boundary, guard and no-access positions use the old
guarded read. No stack exemption survives parent return or transfers to a
different thread. The exact 48-tile sight policy, fresh-only Terra reset,
saved policy, categories/resources, minimap refresh and native renderer dirty
schedule remain unchanged.

`visibility-r8-independent-source-audit.json` passed against runtime source
SHA-256 `0f56392abcd766112bada4ef7f29123efc2b4a41c6c94c2d2ae6f7974fb71110`
and vision source SHA-256
`a572e1eefe8131e5c370070bb442dbff1e7a3181bfa2e1e2a23bc882a326802b`.
The independent current-thread Windows stack-region audit passed **16
bounded API cases**. The targeted run passed **13 methods**, including
**378 slow/fast actor pairs**. These source, synthetic-memory and own-process
API checks do not run Anno or prove GPU or live performance.

Each profile produced three byte-identical actual DLLs: two independent
candidates and its completed publication build, with reviewed-profile
registration. The final `visibility-r8-independent-build-audit.json` passed
all six builds, **28 raw index/worktree
inputs**, **488 immutable imported / 43 compiled inputs**, original 43/staged
59 compiled-source closures, **68 exports**, TLS, nine exact native-profile
module pins and the unchanged **15 visibility / 197 total guarded
components**. All actual hashes match the canonical r8 pins above.

The definitive post-pin suite passed **267 tests in 154.107 seconds: 262
passed and five were skipped** for unavailable Windows symlink privileges.
It finished `OK (skipped=5)` with no errors or failures; the report is
`world-v6-strict-r8-postpin-suite.txt`. Repository privacy passed across
**584 public files**, and the whitespace check passed.

The earlier `world-v6-strict-r8-suite.txt` attempt ran **217.233 seconds** and
had **five package-pin errors** because it began before new-pin promotion.
Those guarded refusals and that report remain preserved; the earlier attempt
did not pass. The later post-pin suite above is the definitive result.

The actual compiled r8 DLL fixture passed **72 scene stages**: all six map/
activity combinations, 512/1024/2048 worlds, two seeds and both profiles.
All **82 copied fixture assets** remained exact; AI was **0 only**. The
isolated report `world-v6-strict-r8-full-runtime.json` does not open Anno,
inject a runtime, load a native game world or bypass activation/configuration
guards. These passes do not establish live rendering or performance. The
r8 production installer cycle and automatic activation/save reload passed
separately, as recorded below. The user's sampled range/camera check also
passed; broader rendered-transition and performance acceptance remain pending.

The paired real-Windows report
`visibility-r8-scoped-reads-windows-benchmark.json` uses the same certified
r7 fixture graph and **100,000 invocations per case**:

| Synthetic callback | R7 / r8 wall time | R7 / r8 memory-range queries after preflight |
| --- | --- | --- |
| Resident actor | 497.87 / 76.37 ms | 1,000,000 / 200,000 |
| Occurrence actor | 416.56 / 38.47 ms | 800,000 / 100,000 |
| Current-draw stack position | 46.59 / 8.85 ms | 100,000 / 0 |
| Heap-position fallback | 45.94 / 42.55 ms | 100,000 / 100,000 |

Module-lookup calls within the timed actor loops fell from 100,000 to zero;
native actor spies retained 100,000 calls in both versions. Parent-draw
preflight is outside these timed loops. Renderer rasterization and cache
repaint are excluded: **these timings are not game FPS or proof that the
remaining large-island lag is corrected**. The r8 installation cycle,
automatic startup and certified earlier-save reload are verified; fresh
Terra generation remains untested. Food-profile gameplay was omitted at the
user's request, as scoped above.

## Completed r8 installer/restoration cycle

The reviewed production cycle completed with Anno closed: restore the
preceding r7 World-only installation, install/restore r8 World-only,
install/restore r8 Food + World, then install final r8 World-only. World-only
made **19 managed-file changes** and Food + World **41**; each installation
passed its exact production preparation no-op. All **three restorations**
returned the exact **23-file stock closure** and removed **19 introduced
World files**.

All **40 native saves, five presets and 32 prior backup generations** stayed
exact. Three newly restored generations were retained separately, giving
**35**. The original **23 source inputs, 297 historical backup files, 488
legacy files and 43 compiled inputs**, all protected r4-r7 private evidence,
the prior progressed-autosave archives and restored original `Lastgame`
remained exact.

The final managed copy has **r8 World Settings enabled and Food disabled**.
The cycle launched no game, activated no hooks, controlled no process/UI and
bypassed no production closed-game guard. The subsequent normal production
launcher **33048** is a separate attempt; its verified automatic startup and
save load are recorded next and are not installer-cycle results. The
completed private report is
`world-v6-r8-cycle-3595511f44b74db8b6f1f8121d7786ab/result.json` under
`.local/validation/`.

## Actual r8 World-only automatic startup and certified reload

The production launcher completed the normal client/source handoff and
closed its owned source main menu normally, followed by **exactly one guarded
activation**, with no manual retry. The managed World-only host was **PID
35060**, creation identity **134387299577980988**. Its actual runtime matched
the reviewed r8 World-only hash above; the world-spec SHA-256 was
`1be30f99ca2ca74f6c65f7dc792df7e8d2e6611f94fda340bf71f19b83dda23f`.
The inspected engine plan remained unchanged. Fresh-menu diagnostics passed
**15 visibility / 173 engine** readiness, with last error **0** and pending
modified rows **0**. Unobserved renderer delegate targets were zero at the
main menu, as expected before native world drawing.

The actual game UI then loaded **wv63** with its explicit earlier-generation
SHA-pinned certificate. The current r8 executable/package/runtime/native
identities and complete **197-component transaction** were checked
independently; the old certificate identity was not reused for the host.
The successful bounded observer matched **all 24 island geometries, climates
and 13 interpreted harvest-crop bits**, saved policy **`0x1000`**, **five
remembered known / 19 unknown islands**, and **Food disabled**. The supplied
native disk certificate separately retains the positive physical mineral
masks; this is not a live mining-accessibility check or a fresh Terra reset.

Loaded diagnostics reported **15 / 173**, empty factory/hook/AI error strings,
last error **0** and zero pending modified rows. Both original Display
delegates were observed at **`0x49410` / `0x49BD0`**.

An earlier detailed read-only island-8 inspection refused certification with
**"Static physical tile data changed during inspection."** Its failed report
is retained. No coherent detailed static-island result or cause of the
changing bytes is inferred. The successful **v2** observer omits that
changing detailed tile span and certifies only its declared bounded scope;
it does not turn the refusal into a successful static/GPU result.

After the requested camera pan/zoom over a large Pirate/AI island and
sailing away from and back to the native village, the user reported
**"Smooth now; visibility still works."** This is qualified user-observed
acceptance of that r8 camera/visibility sample. It does not establish FPS,
every renderer or interaction path, all populations/world sizes, or
long-session performance. The separate failed detailed static-span read
above remains a refusal and is not replaced by this hands-on result.

This World-only run was then closed normally. The reviewed closed-game
preservation helper passed with **40 native saves, five presets and 35
retained backup generations**, plus **23 original source inputs, 297
historical backup files, 488 legacy files and 43 compiled inputs**, all exact.
The four older r4/r5/r6/r7 autosave archives remained unchanged.

The exclusively archived r8 disk `Lastgame` and the restored original both
have SHA-256
`68d21293558d935333cc24f94cf6466a23a2f4f1cb50a53095e70c4f518de963`.
**The disk autosave had not advanced in this run.** The report's historical
`progressed_*` field names do not mean a newly progressed world was saved:
the existing unchanged disk autosave was archived and the same original
bytes restored. The saved **wv63** checkpoint remains retained; the later
live camera/visibility interactions were **not captured in a new save**.
The completed report is `world-v6-r8-stock-autosave-restoration.json`.

The planned fresh **Food + World Terra**
actual run was omitted at the user's explicit request. It is not a required
follow-up or publication gate for this iteration; the r8 native sources and
canonical pins are unchanged.
The records under `.local/validation/` are
`world-v6-r8-stock-fresh-main-menu.json`,
`world-v6-r8-stock-fresh-menu-visibility-diagnostics.json`,
`world-v6-r8-wv63-reloaded-{identity,diagnostics}.json`,
`world-v6-r8-wv63-reloaded-memory-v2.json` and
`world-v6-r8-wv63-static-observer-refusal.json`.

## In-game choices

| Choice | Behavior |
| --- | --- |
| Unexplored / terra incognita | Cover the setup preview and, once during fresh-world creation, remove inherited human discovery bits. Normal native ship contact then reveals whole islands, which stay remembered. Reloading does not repeat the clear. This is whole-island discovery, not per-tile fog. |
| Geography revealed | Show island locations initially. This is the default map mode. Native discovery and fertility information remain separate. |
| Fully explored | Add the human owner-0 discovery bit to every island, retaining other owners' discovery bits. Native fertility information is then unlocked. Enemy activity remains a separate choice. |
| Strict line of sight | Default enemy-activity mode. Show activity within a fixed 48-tile current-vision area around controllable human ships and owned settlements' building-anchor rectangles. Out-of-range activity becomes hidden again while known islands stay remembered. |
| Reveal all activity | Remove the current-vision range limit for other players' activity, independently of island discovery. |

These settings are inside the game. The screen has **World**, **Players**,
**Starting**, **Presets**, **Islands** and **Visibility** tabs; the Starting
page heading remains **Starting options**. Existing world generation,
resources, fleets, cargo, cultures, opponents and disaster settings remain.
The 48-tile range is the selected mod policy, not a claimed native sight
radius or a new user-adjustable setting.

## Concealed setup and preferred starts

Unexplored covers the preview immediately from the **live dropdown**, before
querying or painting cached island geometry, faction markers or start badges.
It does not wait for regeneration. A missing or invalid selection also covers
the preview, including when a ready revealed preview remains cached.

While concealed:

- Preview clicks cannot inspect an island or choose a preferred island.
- Island metadata, resource summaries, human/AI assignments and start badges
  are withheld; the preferred-island button is disabled.
- Entering Unexplored clears the inspected and preferred island indices.
- Climate preferences, balanced starts, resource guarantees, seed reuse,
  regeneration and validation remain available without exposing the map.

Shared validation refuses Unexplored combined with a preferred island index.
Loading an incompatible preset does not silently rewrite it. Changing enemy
activity or switching between the two revealed map modes retains a valid
preferred island. These setup checks do not establish actual game rendering
or exploration after Start.

## Settings, presets and saved policy

The appended signed 32-bit fields preserve the preceding settings' offsets:

| Field | Values | Default |
| --- | --- | --- |
| `mapVisibility` | `0`: Unexplored; `1`: Geography revealed; `2`: Fully explored | `1` |
| `enemyVisibility` | `0`: Strict line of sight; `1`: Reveal all activity | `0` |

Settings are **120 bytes**; the preview snapshot is **5256 bytes**. Island
rows remain 40 bytes and read-only island details remain 44 bytes. Preset
format **3** records all **29 choices**, including the seed, with the matching
`ws6-` generator identity. Old files remain user data: preceding schemas and
mismatching generator fingerprints are refused, not silently converted or
overwritten.

All six visibility combinations are encoded in inspected native world-header
transport bits. Loaded marked worlds reapply the selected policy; older
unmarked worlds retain their native visibility behavior. Invalid marked
policy or unsafe presentation state is refused. Native instruction fixtures
prove the transport representation. The historical r4 `wv61` native save and
r5 `wv61r` resave and r6 `wv62` resave have passed independent disk certification. Actual r5/r6
loads of these explicitly certified earlier saves are recorded separately
below; the certificates themselves are not restart proofs. A fresh r7 Terra
world and complete visibility acceptance remain unproven. A saved policy
needs its compatible World Settings runtime after restoring/reinstalling
game files.

## Why r5 supersedes the r4 game run

The r4 village case exposed a mismatch between the static classification
assumptions and the **Game catalogue definition classes** actually used by
the native world. R5 reads the inspected Game kind and ware-0 representation
and follows the native `CDF10` category/exception behavior, including the
`0xE2` next-definition rule. The actual r5 run confirmed the Game definitions
are recognized, but found further unfiltered rendering paths and a graphics
centre/anchor lookup defect. The r5 classification correction therefore does
not establish complete village concealment; see the failure record below.

Separately, all 15 copied Pirate templates were found to carry a literal
initial human discovery bit in their editor `DISCOVER` data. The original
loader copies that word, and the native village-transfer selector is not a
general reset for directly aliased Pirate templates. R4's elapsed four-known
island snapshot could therefore not establish a correctly concealed fresh
start.

R5 preflights every target, then clears **only human bit 0** on all loaded
islands **once**, after fresh template/ownership/starting-position setup and
before gameplay, for Unexplored only. Other owners' discovery bits and the
adjacent word remain unchanged. The pending fresh-world token is consumed;
ordinary drawing and saved-world loading do not invoke this normalization.
Geography revealed and Fully explored retain their distinct native behavior.
The copied templates themselves are not edited.

The ordinary native active-ship update repeats a **14-tile island-contact
query**, including for a stationary ship; it can restore legitimate local
discovery on a subsequent normal tick. That native discovery query is
independent of the mod's **48-tile current activity sight**. R5 does not
replace permanent island discovery with its activity-range predicate.

## Historical r6–r8 native implementation

The implementation uses exact History Edition **AMD64** interfaces and
profile-specific preimages. It does not assume classic-version addresses.
Runtime activation guards six modules: **AnnoWelt.dll**, **AnnoFrame.dll**,
**AnnoScene.dll**, **AnnoGame.dll**, **View.dll** and **AnnoDisplay.dll**.

Terra incognita wraps the two native World draw methods, preserving their
five-argument and six-argument ABIs. It masks only the presentation rows'
quadrant-valid and clipping flags for undiscovered islands, calls the native
draw, then restores the flags inside the **same invocation**. No modified row
or live object pointer survives the draw return. Producer/update ownership,
quad payloads, physical terrain, resources and pathfinding grids remain
unchanged. The quadrant gate also skips native island-node scenery, rather
than merely drawing empty terrain beneath visible trees or rocks.

Current vision is a bounded read-only snapshot of the human's native player
ship list and settlements. Each controllable native ship supplies a point;
each owned settlement supplies the rectangle enclosing its building anchors.
The predicate measures distance to that point or rectangle and admits points
within 48 tiles. It is not an entire-owned-island vision guarantee. The
snapshot admits at most 512 ships and 255 settlement list entries; these are
adapter safety bounds, **not verified engine player or fleet maxima**.
Ownership, object identity, list links, coordinates and storage spans are
checked before use.

Three common actor-call bridges apply the same predicate to reviewed resident
and occurrence drawing paths, including the global actor passes that bypass
quadrant flags. Native actor interfaces have different layouts; reviewed
polymorphic getters/owner representations are used rather than treating ships
as wildlife. Unknown dispatch targets are not blindly cast to a known class.

R6 retains the four static-sprite call bridges and additionally wraps the
DD11 renderer's two actual sprite dispatches, `+0x180` and `+0x188`. This
adds the native mode-1 static route that bypassed r5's call sites. The
call-site wrappers recognize the hooked entries and reach the exact original
Display delegates without self-recursion. The six sprite arguments,
including WorldXYZ, are preserved. The separate **five-argument `+0x160`
dirty/invalidation notifications remain untouched and unconditional**; they
are not routed through the sprite filter.

A graphics point on a footprint continuation cell now follows **one bounded
native anchor hop**. The candidate anchor must have the root flag, zero
continuation offsets, the same definition ID, rotation and city identity;
underflow, mismatching anchors and unsafe reads are refused. This follows
the inspected native resolver rather than editing the physical footprint.
The resulting positive-building classification uses the inspected Game
kind/ware-0 and Display branches, including the `0xE2` next-definition rule.
Claimed territory alone still does not classify a neutral tree or rock.
Physical tile data, ownership and simulation state remain read-only for
these render predicates. The source/native-fixture evidence is supplemented
by the sampled r6 visible-near / absent-far / visible-on-return actual-game
result below; broader coverage remains pending and severe live lag blocks
acceptance.

The native minimap bitmap adapter hides undiscovered island geography and
filters all non-sea owner/activity colours outside the common current-vision
area. It has no human-colour exception: native NPCs can share that colour,
so exempting it would disclose their activity. A
separate Frame bridge excludes out-of-vision foreign ship markers before
native coordinate conversion, while preserving the original exclusion
result. The own-ship and own-unit marker passes remain native, as does the
1500-marker append bound. The reviewed producer has no foreign land-unit
point pass; this does not establish marker behavior in every unrelated UI.

The reviewed minimap correction tracks newly discovered islands and unions
their world-space rectangles into a required geography refresh, even while
the observer remains stationary. Changed vision refreshes the old and new
activity areas; first-use geography recovery is performed once. Scalar memo
identities are compared only, and a generation reset invalidates them; stale
world/map/pixel addresses are not used as write targets. Synthetic native
cases cover these transitions. Historical r4 sailing snapshots are recorded
below; they do not establish corrected r5 discovery or rendered visibility. A full Huge-world terrain refresh can require roughly
17 million native height queries, so unchanged callbacks do not rebuild the
whole terrain bitmap.

## R6 current-viewport cache repair

Native mode 1 asks the renderer's dirty query (`+0x138`) which quadrants need
static enumeration. An unchanged native physical quad does not encode a
change to the mod's current sight, so filtering future sprite submissions
alone cannot remove already cached pixels. R6 invokes the inspected DD11
**`+0x170` current-viewport dirty method before the original World mode-1
selection**, leaving the native `+0x160` physical-change notifications intact.

The render memo records scalar world/renderer/table identities, lifetime
generation, policy, current observer sources, the human island-discovery bits
and viewport. Cached addresses are compared, never later dereferenced as
owners. A relevant change dirties the **whole current display viewport**, not
the whole game world. Identical unchanged frames do not repeat this work.
Empty initialization/offscreen viewports produce no dirty call or error,
leave the memo invalid and retry when bounds become nonempty. Invalid state
fails closed, and an abort after refresh invalidates the memo so a later
identical-context draw must refresh again.

Before calling native `+0x170`, the adapter checks the exact DD11 class,
method targets, current viewport and the entire writable native record table:
**16,384 records at 416 bytes each**. The admitted viewport domain is a
sufficient native-table safety bound, not proof that every possible native
viewport lies within it. The source preserves physical world/pathing data.
Native dirty-write and ordering fixtures are completed. The sampled actual
near-to-far-to-near run below showed village parts disappear and reappear,
but **the user reported severe lag**. R6 therefore fails live performance
acceptance despite its automated passes. Repeated memory-range checks per
sprite/list and full current-viewport dirtying when vision changes are being
investigated for r7; they are suspects, not measured causes. Complete
GPU/cache coverage and longer-session performance remain unestablished.

## One guarded activation transaction

The r6/r7/r8 plan contains **197 edits**: the existing nine code hooks and
173 engine edits, plus **15 visibility components**:

| Visibility components | Count |
| --- | ---: |
| World terrain-draw dispatch pointers | 4 |
| Minimap bitmap dispatch pointer | 1 |
| Display `+0x180` / `+0x188` sprite dispatch pointers | 2 |
| Common resident/occurrence actor calls | 3 |
| Foreign ship minimap exclusion call | 1 |
| Static-sprite submission calls | 4 |
| Total | **15: seven pointers and eight calls** |

The eight calls use checked registered leaf bridges and join the same
preflight, paused-thread commit, readiness check and rollback as the pointer
and engine edits. Exact call bytes, padding, targets, overlaps and capacity
are validated. The complete plan now **fills capacity 197 exactly**; missing,
excess or partial components must be refused. There is no second partial visibility
installation. The original installed game and existing backup generations
remain preserved, as do all **488 imported legacy source files** and **43
original compiled-source inputs**.

## Historical r7 performance correction and automated checks

R7 keeps the **48-tile sight rule**, saved policy, fresh-only discovery reset,
map masking and r6 viewport-dirty schedule. It optimizes repeated validation
inside one active native draw; it does not quantize vision, throttle dirty
refreshes or retain live object pointers across draws. The per-active-draw
heap cache is released on normal exit and every post-allocation abort.
Cached bindings are checked before their dependent data is followed.

List masking/restoration now validates each complete current list span in
bulk. Two-phase preflight preserves refusal before partial row writes,
including a readable first page followed by a read-only second page. Native
terrain/pathing and simulation ownership remain read-only to these filters.

`visibility-r7-independent-source-audit.json` passed against the closed
runtime source SHA-256
`70c52553c7200925bb27255053a47da06d6b4c8cab274f3d4521dbf19673b786`
and vision source SHA-256
`36801dd4f0884d8d07a88fd3d6ad5679c5304fa5efd24fba0e2100883ab3b244`.
It confirms the unchanged policy/map-refresh functions, cache lifetime,
binding checks, native catalogue bounds and full-span preflight. It opens no
game and does not prove GPU behavior or playable performance.

The r7 targeted run passed **11 methods**. Its Game-catalogue equivalence
fixture covers **450 slow/fast pairs (900 predicate calls)** plus **nine
changed-binding refusals**. All five inspected Display neighbour-definition
classes exercise bad getters before and after cache creation. The list
fixture refuses a read-only second page before row mutation. These synthetic
objects and renderer boundaries do not replace a game run.

These are the historical r7 pins; current r8 candidate pins are above:

| Identity | Historical reviewed r7 value |
| --- | --- |
| Generator | `ws6-8fa8a4e9b8729c48629c053befaa714d917b8f2451478d4f104a0e63357e8427` |
| World-only runtime SHA-256 | `b1dcfaf4dd0fad6979e6f22dba32160ce55261db1e3f39655859b2b166c45e70` |
| Food + World runtime SHA-256 | `03c67d8e1d2dfe46e38e3efbc5fa4c0b9647ced47f5e68c0ef4570467dea487c` |

Each profile produced three matching actual DLLs: two independent candidates
and its publication build. Both the pre-pin candidate audit and the final
`visibility-r7-independent-build-audit.json` passed all 28 raw
index/worktree generator inputs, the immutable 488 imported/43 compiled
inputs, original 43/staged 59 compiled-source closures, 68 exports and TLS,
nine exact native-profile module pins, and the unchanged **15 visibility /
197 total guarded components**. The final audit checks the canonical
generator/runtime pins across all six builds. New private packages are
prepared for both profiles (**116 World-only / 111 Food + World files**).
The r7 full suite completed **265 tests in 169.649 seconds: 260 passed and
five were skipped** for unavailable Windows symlink privileges. It finished
`OK (skipped=5)` with no errors or failures; the retained report is
`world-v6-strict-r7-suite.txt`. The public-repository privacy checker also
passed across **584 public files**. These automated checks do not establish
playable performance. The completed closed-game installer cycle and actual
startup/reload are recorded below; complete game acceptance remains pending.

The actual compiled r7 DLL fixture passed **72 scene stages**: all six map/
activity combinations across 512/1024/2048 worlds, two seeds and both
profiles. All **82 copied fixture assets** stayed unchanged. AI was **0**
only; configuration/activation guards were not bypassed. The report,
`world-v6-strict-r7-full-runtime.json`, runs isolated DLL APIs and scene
serialization, not Anno, a native loaded world or the game UI.

The isolated real-Windows benchmark
`visibility-r7-windows-hotpath-benchmark-final.json` executes real memory-range
queries and module-lookup APIs with synthetic native objects and renderer
spies. Final batch timings were about **8.90 ms for 20,000 valid-catalogue
neutral sprites**, **9.19 ms for 20,000 foreign-building sprites**, and
**1.69 ms for 40 list mask/restore iterations of 512 rows each**. Paired with
`visibility-r6-windows-hotpath-benchmark-representative.json` on the same
representative synthetic graph, those timings are approximately **35 / 45 /
406 times faster** in this isolated validation work. Memory-range query
counts fell from **240,050 to 20,082** for the neutral batch, **520,050 to
20,084** for the building batch, and **226,920 to 1,720** for list masking.
The earlier initial r6 benchmark is preserved separately. Unrecognised
catalogues and calls outside an active parent draw retain the guarded slow
path. The fixture excludes actual rasterization and viewport cache repaint;
**these ratios are not game FPS, a measured explanation of the live lag, or
proof that r7 fixes it**. Actual r7 startup, certified `wv62` reload and the
qualified hands-on result are recorded below; further comparable performance
checks and fresh Terra creation remain outside that historical sample. No
new Food-profile live result is claimed; that run was later omitted at the
user's request.

## Completed r7 installer/restoration cycle

The reviewed helper completed the production cycle with Anno closed: restore
the preceding r6 World-only installation, install/restore r7 World-only,
install/restore r7 Food + World, then install final r7 World-only. Each
installation passed its exact production preparation no-op, with **19
managed-file changes** for World-only and **41** for Food + World. Every
restoration returned the exact **23-file stock closure** and removed the
**19 introduced World files**.

All **39 current native saves, five presets and 29 preceding backup
generations** remained exact; three new restored generations were retained,
giving **32**. The original **23 source inputs, 297 historical backup files,
488 imported legacy files and 43 compiled inputs** stayed unchanged. All
protected r6 private evidence and the r4/r5/r6 progressed-autosave archives
remained exact, together with the restored original `Lastgame`.

The final managed copy has **r7 World Settings enabled and Food disabled**.
The cycle launched no game, controlled no process/UI, activated no hooks and
bypassed no closed-game guard. A subsequent normal launcher **39748** is a
separate startup attempt; its subsequent actual activation and reload checks
are recorded below and are not installer-cycle results.
The completed private report is
`world-v6-r7-cycle-7eb0614308bc46fbb2737884e01fd50b/result.json` under
`.local/validation/`.

## Actual r7 World-only startup and certified save reload

Normal startup completed the source-bootstrap handoff and automatic source
menu close, followed by one guarded activation. The sole managed-copy host
was **PID 21260**, creation identity **134387273890406250**. Its actual DLL
matched the reviewed r7 World-only runtime above; the world-spec SHA-256 was
`f89ddc75249c1e26a8b4739ea8d15fa824890875d173ba9c5c670d916b36e559`.
The executable, package and native profiles matched. All **197 guarded
components** were verified, with readiness **15 visibility / 173 engine**
and empty factory/hook/AI error strings. Food remained disabled.

The actual game UI loaded **wv62** using its explicit earlier-generation
SHA-pinned certificate. The current r7 host identity was checked separately;
the absent current preview was not filled with the old save's identity.
All **24 islands' geometry, climate and 13 interpreted harvest-crop bits**
matched the certified world. Saved policy **`0x1000`** remained Terra/Strict,
with **4 remembered human-known / 20 unknown islands**; no fresh-world clear
ran on this explored save.

The human ship was near **`(509.035736, 238.380905)`**, with no owned
settlement. On island 7, the owner-14 Market **3700** at `(506, 205)` and
Warehouse **3712** at `(510, 206)` were approximately **33.519 / 32.395 tiles**
away, inside 48. The sampled physical tile read was stable during that
observation; this is not an immutable full-world comparison across elapsed
gameplay. Minimap metadata contained **80 owner/activity tint pixels inside
sight, zero outside**, and zero unknown-island geography/owner pixels. These
are bounded CPU reads, not a GPU-frame or range-transition test.

Both original renderer delegates resolved to the inspected Display targets
**`0x49410` / `0x49BD0`**. Loaded diagnostics reported last error **0**, pending
modified rows **0** and readiness **15 / 173**. A short process-CPU sample
used approximately one core (**2.96875 CPU seconds over 3.000242 wall
seconds**). This measures neither FPS nor improved responsiveness and does
not establish a meaningful reduction from the earlier r6 sample.

The subsequent hands-on report says r7 is **much smoother and visibility
works**, while moving the camera over a large **Pirate or AI island still
causes lag**. This is a qualified user-observed improvement, not a measured
FPS comparison or complete renderer/performance acceptance. It does not
establish every range boundary, footprint, retained-selection or hover path.

R8's source, installation, reload and qualified hands-on improvement are
recorded separately above. They do not establish a measured cause of r7's
lag or comprehensive performance coverage. The remaining r7 large-island
lag blocked that historical profile's acceptance. Fresh Terra creation and
other map/activity modes were not exercised there. Food + World actual
visibility gameplay was not performed and was later omitted at the user's request.
The private startup/reload reports are
`world-v6-r7-stock-fresh-main-menu.json` and
`world-v6-r7-wv62-reloaded-{identity,diagnostics,memory}.json` under
`.local/validation/`.

The user saved **wv63**, whose independent disk certificate passed. Its
native save identifier is **`edcfd30c-392-4029-abec604d2a113756`**, size
**2,783,755 bytes**, SHA-256
`4a5111ec2f925a473840b54b01488e401a8478a11ae854c9870aa708d8682dd9`.
All **24 island geometries, climates, 13 interpreted harvest-crop bits and
positive physical mineral masks** match, with saved policy **`0x1000`**.
Human-known islands are **0, 7, 8, 10 and 11**, retaining the prior four;
this disk certificate does not establish a live GPU discovery transition,
initial discovery provenance or a fresh-process reload.

After normal game closure, the reviewed r7-stock autosave helper passed.
The progressed `Lastgame` was exclusively archived with SHA-256
`6ebbb82826c3667bfd2b4a189289e7c59195d7921f53203394a2176fa94603be`,
and exact original SHA-256
`68d21293558d935333cc24f94cf6466a23a2f4f1cb50a53095e70c4f518de963`
was restored. All **40 native saves, five presets and 32 retained backup
generations**, plus **23 original source inputs, 297 historical backup
files, 488 legacy files and 43 compiled inputs**, were protected. Earlier
r4/r5/r6 progressed archives stayed exact. The reports are
`world-v6-r7-wv63-save-certificate.json` and
`world-v6-r7-stock-autosave-restoration.json`. These earlier r7 preservation
results are separate from the completed r8 installer cycle above.

## Historical r6 targeted automated checks

The r6 targeted visibility run passed **43 public test methods**: eight
call-bridge, 25 hook, nine native-method and one Game-catalogue method. This
includes the continuation, Display-dispatch and current-viewport corrections:

| Layer | Recorded result and scope |
| --- | --- |
| Native call bridges | **8 tests passed**: exact call/preimage staging, bridge linkage and ABI/guard behavior. |
| Guarded dispatch hooks | **25 tests passed**: exact World/Display identities and seven pointer targets, call linkage, 197-of-197 transaction capacity, completeness, readiness, reversibility and refusal of changed inputs. |
| Authored native methods | **9 methods passed**, including **42 draw/policy synthetic-memory/ABI cases and 8 fresh-discovery cases**. Coverage includes stationary discovery requiring flags `3`, owner-1 activity as vision changes, one-time geography recovery, scalar-generation reset, shared activity colour 0, fresh-only bit clearing, continuation ownership, current-viewport refresh/idle/retry and refusal before partial writes. |
| Authored Game catalogue branches | **1 method passed**, exercising **8 Game-definition branches** with positive buildings, neutral/ware exceptions and the next-definition rule. This is separate from the original-native audit below. |
| Menu and presets | **14 tests passed** in the recorded targeted menu run: 29-field format-3 round trips, boundaries and invalid inputs, staged painter/details/click/change functions, covered stale/invalid previews and retained revealed paths. |
| Other shared representation/generation checks | Recorded targeted runs passed **7 snapshot**, **8 planner** and **16 start-policy** tests. They are separate from actual game acceptance. |
| Actual compiled runtime APIs | Both **r6** DLL profiles passed **72 scene stages**: all six map/enemy combinations, 512/1024/2048 worlds and two seeds. All **82 copied fixture assets** stayed unchanged. AI count was **0** only, with no configuration/activation guard bypass; no Anno process, native world or game UI was launched. |

The original-native instruction audits supply additional, distinct evidence:

| Native audit | Result and limits |
| --- | --- |
| Static sprites and ownership predicates | **468 cases passed**: 8 sprite submissions, 20 catalogue lookups, 80 tile-owner cases and 360 static-predicate cases. Original instructions run against synthetic objects; graphics services are spies. |
| Continuation and static/animated routing | **2,048 original native continuation-resolver cases and 32 FigurePoints/helper calls passed**. They establish one-hop anchor offsets and native static/animated route arithmetic with synthetic frames, not the final contents of a live GPU frame. |
| Native World dirty differences | **12 original quad-comparison cases passed**. Identical physical metadata produces no native invalidation; a null previous quad enumerates static parts through the separate five-argument `+0x160` dirty boundary. The renderer boundary is a spy. |
| Mode-1 dirty gate and ordering | **20 native cases passed** for the original DD11 dirty query and World selection branch. Invalidation must precede cached quadrant selection/static enumeration. Screen projection is a fixture boundary; GPU clearing is not executed. |
| Complete Display `+0x170` writes | **12 complete original native calls passed**, checking **all 16,384 records**, unrelated bytes and outer canaries at relocated bases. These verify the dirty-table writes and sufficient bounds, not surface clearing or actual drawing. |
| Independent r6 render/cache review | `visibility-r6-render-cache-independent-review.json` passed exact native preimage/source checks, pre-selection invalidation ordering, complete-table guarding, scalar memo ownership, empty/retry and post-abort recovery, original `+0x160` preservation and nonrecursive hooked delegates. It opened no game and claims no GPU acceptance. |
| Native Game catalogue correction | **1,024 ware-0 getter cases and 6,480 original `CDF10` Game-catalogue cases passed** across exact stock/Food profiles. Synthetic objects distinguish Game kind/ware fields from Display definitions and exercise native category/next-definition exceptions. No GPU presentation is established. |
| Inherited fresh discovery | **64 native template-loader, 52 culture-selection and 24 first-contact-prefix cases passed**. All 15 copied Pirate templates were independently reread; native loader/selection behavior explains why editor human bits can survive initial construction. These prefixes do not execute complete gameplay startup. |
| Recurring native ship contact | **12 original stationary ship updates passed**, in four stock/Food/load-base cases. Native status/owner/query/discovery-prefix instructions reissued the 14-tile contact query and restored discovery after a test clear. Later callback side effects and actual gameplay scheduling remain outside the fixture. |
| `0xE2` mixed-neighbour rule | **72 additional predicate cases passed**, separating this building's definition from the next definition's subtype exceptions. Repeated supporting catalogue/sprite cases are not counted again here. |
| Minimap refresh contract | **8 cases passed** for original full/partial rectangle loops, scaling, writes and null-pointer behavior, with bounded synthetic geometry and a flat-height spy. The native method has no null-pointer full-map convention. This is not proof of the new dirty-region planner. |
| Native bitmap bounds | **16 cases passed** across both profiles, two load bases and 256/512/1024/2048 world sizes. The actual native minimap is 256 by 256; original prefix arithmetic maps explicit world bounds to bitmap bounds. Execution stops before the expensive terrain-sampling loops. |
| Human observers | **64 original-native cases passed** for player/ship/settlement sources and building bounds, with declared definition-size service spies. They do not infer a native sight radius. |
| Actor interfaces | **96 original-native getter cases passed**, distinguishing ship, ground actor and wildlife layouts and owner objects. |
| Foreign ship markers | **16 original-native cases passed** for the Frame foreign-player loop, ship getters and existing exclusions. Projection/interface boundaries are spies; the new bridge result was modelled after the original getter return. |
| Renderer factory and submission provenance | **14 static instruction assertions per profile passed**. The exact Display factory constructs `tDrawSegmentDD11`; Frame stores and passes that renderer into World drawing. Sprite slots `0x180`/`0x188` resolve to the reviewed Display delegates and retain the sixth WorldXYZ argument. This is static proof, not observed live renderer selection or a GPU frame. |

These instruction audits use pinned stock/Food originals at distinct load
bases without opening Anno. They do not exercise Windows-native installation,
actual GPU frames, menu focus, live movement, discovery messages or saves.
Earlier geometry-consumer and concealed-quadrant fixtures likewise remain
instruction-level evidence, not screenshots from a game run.

## Historical r6 builds and full-suite result

These are the historical r6 pins; current r8 and historical r7 pins appear
in their separate tables above:

| Identity | Reviewed r6 value |
| --- | --- |
| Generator | `ws6-efed296126c4532902ed0e2f83d7444d23f449b496e1059f4aa9b94561e5b0dc` |
| World-only runtime SHA-256 | `c7947002afdffec35b2c264d711087f9e155eafe6903fd543390a744fee0cb23` |
| Food + World runtime SHA-256 | `eb2b410bb5bd579b4cbee1ab250880134d32b770f9ecac523481a4b03666110d` |

Each profile produced its identical canonical DLL **three times**: two
independent candidates and a completed publication build. All six actual
hashes match the table; both publications report a reviewed-runtime match.
Compilation and publication did not install or launch Anno.

The independent `visibility-r6-independent-build-audit.json` passed **28 raw
index/worktree generator-input checks**, all **488 immutable imported files**
and **43 immutable compiled inputs**, and every build's original 43-source /
staged 59-source closure. All six actual DLLs have **68 recorded exports** and
checked TLS. The audit verified nine exact native-profile module pins, five
World plus two Display pointer hooks, eight visibility call bridges and the
complete **15-component visibility / 197-of-197 total transaction**. These
source/artifact checks do not execute native gameplay or prove GPU clearing.

The r6 full suite ran **264 tests in 167.680 seconds: 259 passed and five
were skipped** for unavailable Windows symlink privileges. It finished
`OK (skipped=5)`, with no errors or failures. The exact record is
`world-v6-strict-r6-suite.txt` under `.local/validation/`. The completed
closed-game installer cycle and bounded actual observations are separate
below; complete actual-game acceptance remains pending.

The actual compiled r6 DLL fixture passed **72 scene stages**, all six map/
activity combinations across 512/1024/2048 worlds and two seeds, under both
profiles. All **82 copied fixture assets** stayed unchanged; AI count was
**0 only**, with no configuration/activation guard bypass. No Anno process,
native world load or UI was exercised. The report is
`world-v6-strict-r6-full-runtime.json` under `.local/validation/`.

## Completed production r6 installer/restoration cycle

The reviewed r6 helper completed the production cycle with Anno closed and
all original guards retained: restore r5 World-only, install/restore r6
World-only, install/restore r6 Food + World, then install final r6 World-only.
Each installation matched its canonical package and produced an **exact
production preparation no-op** on recheck: **19 managed-file changes** for
World-only and **41** for Food + World.

Every restoration returned the exact **23-file stock closure** and removed
all **19 introduced World files**. All **38 current native saves and five
presets** stayed exact, including the original 36-save/four-preset subset.
The **297 original-game backup files, 23 original source inputs, 488 legacy
files and 43 compiled inputs** remained unchanged. All **26 prior managed
backup generations** were retained together with **three newly restored
generations**, giving **29** after the final installation. The archived
progressed autosaves and restored original `Lastgame.sav` stayed exact.

The final copy has **World Settings enabled and Food disabled**, using the
r6 World-only runtime above. The cycle launched no game, activated no hooks,
wrote no process memory, controlled no UI/process and bypassed no closed-game
guard. A separate launcher process **15112** was started **after** completion.
The subsequent fresh-host activation and bounded near/far observations are
recorded below; the cycle itself did not launch or verify native gameplay.

The exact private report is
`world-v6-r6-cycle-b71ae7936fec424693dd6232a9fc4ea3/result.json` under
`.local/validation/`. The following r5 evidence is historical and retains its
actual static-coverage failure.

## Actual r6 World-only startup, reload and near/far/return sample

The automatically launched managed World-only process **26904**, creation
identity **134387242433971573**, was observed at its fresh main menu. Its
runtime SHA-256 matched the pinned r6 World-only DLL above, with exact
executable/package/native-profile checks and empty factory/hook/AI error
strings. Main-menu readiness reported **15 visibility components and 173
engine edits**. The independent observer also verified the complete guarded
**197-component transaction**, including the nine original hooks. These are
actual-process checks, separate from the closed-game installer and compiled
fixtures.

The game UI successfully loaded certified **wv61r** under r6 using its
explicit SHA-pinned earlier-generation certificate. The loaded 24-island
geometry, climates and interpreted crop data matched the certificate; the
old preview/runtime identity was not substituted for the current r6 host.
This is a bounded earlier-save load, not a new Terra-world test.

For the near/far comparison, the actual UI then loaded certified **wv61**.
The same owner-14 village on known island 7 was inspected at two ship ranges:

| Observation | Actual screenshot and independent native evidence |
| --- | --- |
| Near | Human ship approximately `(501.500244, 251.500015)`. The Market **3700** at `(506, 205)` and Warehouse **3712** at `(510, 206)` were about **46.7 / 46.3 tiles** from the ship, within 48. Actual game screenshot inspection showed the village buildings present. |
| Far | After sailing, the same human ship was near `(513.500183, 285.499908)`, about **80.8 / 79.6 tiles** from those anchors. Screenshot inspection of the same tropical islet showed its land, neutral trees and rocks retained while the sampled village's static and animated building parts were absent. |
| Return near | The user confirmed **"Buildings reappear; saved as wv62"**. Subsequent actual Save-page screenshot inspection showed the village fully drawn again with the human ship nearby and `wv62` as the newest save alias. This completes the sampled r6 visual near-to-far-to-near transition. The new disk certificate passed; the later fresh-process r7 reload is recorded separately above. |
| Physical anchors and memory | Both original owner/definition/anchor identities remained present. Island 7's remembered native discovery word stayed **`0x402D`**; the `wv61` comparison still had **4 known / 20 unknown islands**. Full physical-tile hashes differed during elapsed gameplay, so this is **not** an immutable whole-terrain byte comparison. |
| Minimap | Owner/activity tint pixels inside current sight changed **46 to 0**. Outside-sight tint was **0 in both captures**; unknown-island geography/owner pixels were also 0. These counts are CPU bitmap reads paired with separate screenshot inspection. |
| Native renderer diagnostics | Original sprite delegates were observed at **AnnoDisplay.dll + `0x49410` / `0x49BD0`**. Near and far diagnostics reported last error **0**, zero pending modified rows and balanced **136,500 masked / 136,500 restored** rows, with readiness **15 / 173**. |

A sampled click on land at screen point **`(750, 950)`** while the village
was hidden produced an empty sidebar. This is **one sampled click**, not a
precise test of every building footprint, hovering, a previously retained
selection, or all interaction paths. **wv62** is the reported 39th current
save and is visible as the newest Save-page alias. Its bounded read-only disk
certificate passed: native save identifier **`5a1a13df-d426-47a6-81295de9a0db7efc`**, **2,782,461
bytes**, SHA-256
`a7499776fcc132e26269300bd92f07029b08448d4f5b908ca02ecdecd6cc7342`.
The native saved policy is **`0x1000`** (Terra/Strict), and all 24 islands'
geometry, climate, 13 interpreted harvest-crop bits and positive physical
mineral masks match. The previously human-discovered islands **7, 8, 10 and
11** remain discovered. This is disk proof, not a fresh-process `wv62` reload
or proof of r7 behavior. The subsequent closed-game preservation check below
passed with all 39 saves retained.

The same user report described the game as **"super laggy"**. This is a
critical actual-game performance failure, not an untested hypothetical.
**R6 is not ready.** Repeated per-sprite/list memory-range checks and
full-viewport dirty refreshes during vision changes were investigated as
suspects. R7's isolated validation benchmark improved, but it retains the
same dirty schedule and has not been tested in game. No measured cause of
the actual lag or playable-performance correction is claimed.

The read-only observer did not send UI input, invoke setters or change game
configuration/physical state. Its native report does not inspect GPU pixels;
the visible-near / absent-far / visible-on-return result comes from separate
actual screenshot inspection and the user's return confirmation. The result
supports this sampled village/range case only. It does
not complete fresh Terra normalization, all modes/fertility UI, Food + World,
performance acceptance or general GPU/interaction acceptance.

The game was then closed normally with Alt+F4, and no Anno process remained.
The reviewed closed-game autosave helper subsequently passed: the progressed
`Lastgame` was preserved exclusively with SHA-256
`63796249aadc0de4bbb41950a0c583d8b253b87e26eb4671d43434bb25aa9f0e`,
and the exact original `Lastgame` SHA-256
`68d21293558d935333cc24f94cf6466a23a2f4f1cb50a53095e70c4f518de963`
was restored. All **39 native saves, five presets and 29 retained backup
generations** were protected, including the original 36-save/four-preset
subset and earlier r4/r5 progressed-autosave archives. The **23 original
source inputs, 297 historical backup files, 488 legacy files and 43 compiled
inputs** remained unchanged. The independent original-baseline comparison
also passed. This preservation result does not repair r6's performance
failure or establish any r7 gameplay behavior.

Private records under `.local/validation/` include
`world-v6-r6-stock-fresh-main-menu.json`,
`world-v6-r6-stock-fresh-menu-visibility-diagnostics.json`,
`world-v6-r6-wv61r-live-island7.json`, the
`world-v6-r6-wv61-near-{identity,diagnostics,memory}.json` and corresponding
`world-v6-r6-wv61-far-*.json` reports, and
`world-v6-r6-wv61-near-far-native-comparison.json` and
`world-v6-r6-wv62-save-certificate.json` and
`world-v6-r6-autosave-restoration.json`.

## Historical r5 build status

These are the preceding historical r5 pins; current r8 and historical r7/r6
pins are in their separate tables above:

| Identity | Reviewed value |
| --- | --- |
| Generator | `ws6-b395c5824a4c478d32f121e33b7ab4d68a57eb7302af600161ed1f7c48dcc2fd` |
| World-only runtime SHA-256 | `95096886d9bfbfbcd21cf3cc03daa2b617134b0d5147bad2a37fa6395bc29a2d` |
| Food + World runtime SHA-256 | `08081ccf34cb47d0eae4b0df2c5856abd237293c1dcf68dd90a67a6f48d76528` |

Each profile produced its identical canonical runtime **three times**: two
independent candidates and a completed publication build. All six actual DLL
hashes match the table; both publication reports have
`matches_reviewed_runtime: true`. The original 43-source and staged 59-source
closures were independently cross-checked for all six builds. Compilation
and publication do not install or launch Anno.

The independent `visibility-r5-independent-build-audit.json` passed. It checked
all **28 authored generator inputs as exact raw index/worktree bytes**, all
**488 immutable imported files** and **43 immutable compiled inputs**, and
the six actual DLL artifacts, including TLS and exports. Each artifact has
66 recorded exports, the nine exact native-profile module pins and
the complete **195-edit transaction within capacity 197**. The six-module
visibility runtime checks described above cover a subset of that broader
nine-module profile inventory. These are source/artifact/static
native checks, not executed game or renderer evidence.

The r5 full suite ran **254 tests in 169.428 seconds: 249 passed and five
were skipped** for unavailable Windows symlink privileges. It finished
`OK (skipped=5)`, with no errors or failures. The result is retained in
`world-v6-strict-r5-suite.txt` under `.local/validation/`. The completed
production r5 installation/restoration cycle is recorded separately below.

The actual compiled r5 DLL fixture passed all 72 scene stages with 82 copied
assets unchanged, AI count 0 and no configuration/activation guard bypass.
It did not start Anno, load a native world, operate the UI or exercise active
AI gameplay. Its private report is
`world-v6-strict-r5-full-runtime.json` under `.local/validation/`.

## Completed production r5 installer/restoration cycle

The production cycle passed with Anno closed and the unmodified closed-game
guard active throughout. It restored the preceding r4 World-only build,
installed and restored r5 World-only, installed and restored r5 Food + World,
and finished with r5 World-only installed. Every installation matched its
canonical runtime and was an **exact production preparation no-op** when
checked again: **19 managed-file changes** for World-only and **41** for
Food + World.

Every restoration returned the exact **23-file stock closure** and removed
all **19 introduced World files**. The fresh dynamic baseline of **37 current
native saves and five presets** remained exact, including the separately
retained original 36-save/four-preset subset. The **297 original-game backup
files, 23 original source inputs, 488 imported legacy files and 43 original
compiled inputs** remained unchanged. All **23 pre-existing managed backup
generations** were retained with **three newly restored generations**, for
**26** previous generations after the final installation.

The original `Lastgame.sav` had been restored before this cycle, with the
progressed r4 autosave preserved separately, as recorded in
`world-v6-r4-autosave-restoration.json`. This cycle checked and retained both
that restored original and the separate progressed archive. It did not
replace either as part of feature installation.

The final managed copy has **World Settings enabled and Food disabled**,
using the r5 World-only runtime pinned above. The cycle itself launched no
game, activated no native hooks, made no process-memory writes and performed
no process/UI control or guard bypass. A separate launcher invocation
followed the completed cycle. Its guarded activation and certified-save load
were subsequently observed as recorded below; the cycle itself does not
establish that live behavior or complete feature acceptance.

The exact private result is
`world-v6-r5-cycle-5f1f274d0dd6447886dd629854f09562/result.json`, with console
record `world-v6-strict-r5-cycle-console.txt`, under `.local/validation/`.

## Actual r5 startup and certified earlier-save load

After the installer cycle, launcher process **8756** performed the guarded
normal-client handoff. The source bootstrap closed normally and the managed
World-only host ran as fresh process **18628**, creation identity
**134387216085971574**. The executable, r5 runtime, package and exact native
module identities were independently checked. All nine original hooks,
173 engine edits and 13 visibility components remained in the exact guarded
195-component plan. Factory, hook, AI-loader and AI-profile error strings
were empty; fresh-menu visibility diagnostics reported last error 0 and no
pending modified rows.

The actual game UI loaded the earlier r4 save **wv61** successfully in this
fresh r5 process. The current preview was **absent**; it was not invented or
relabelled as a new r5 preview to validate the loaded world. The private
read-only observer instead required the explicit earlier-save certificate
with SHA-256
`86450111c240de96adec8f4876c8c0427564f6108b5f70b3a5b5a501171806e6`, while
separately rechecking the actual r5 package/runtime/modules and exact hooks.
The old runtime/process identity was not reused for the new process. This
is a bounded certified earlier-generation save case, not general migration
support for arbitrary saves or older preset fingerprints.

| R5 observation | Verified scope |
| --- | --- |
| Loaded policy and discovery | Saved flags `0x1000` / policy code 1 decode to Unexplored and Strict (`mapVisibility=0`, `enemyVisibility=0`). The native activity byte is 1, which is distinct from the enemy-setting value. All **4 previously human-known islands remained known; 20 remained unknown** at the reload observation. The fresh-only clear did not run on this old save. |
| World data | All **24 islands**, geometry, climates and **13 interpreted harvest-crop bits** matched the certified saved world. Positive native saved ore/mineral masks remained matched. This does not prove accessibility of harvesting or mines, or the semantics of upper crop/adjacent discovery flags. |
| Minimap metadata | The captured bitmap had **zero owner/activity-colour pixels outside current sight**, zero unknown-island geography pixels and zero unknown-island owner-colour pixels. This is a CPU bitmap read, not proof of complete scene/GPU concealment. |
| Production diagnostics after load | **13 visibility components and 173 engine edits** were active, with last error 0 and zero pending modified rows. Slot `0x188` resolved to the reviewed Display delegate; these diagnostics do not cover the unwrapped static path identified below. |

The evidence is retained in `world-v6-r5-stock-fresh-main-menu.json`,
`world-v6-r5-stock-fresh-menu-visibility-diagnostics.json`,
`world-v6-r5-wv61-reloaded-identity.json`,
`world-v6-r5-wv61-reloaded-diagnostics.json` and
`world-v6-r5-wv61-reloaded-memory.json` under `.local/validation/`.

## R5 actual failure: static village coverage

Despite passing the build, automated and closed-game installer checks,
**the village remained visibly present after the human ship was away near
`(445.5, 229.5)`**, outside 48 tiles of its building anchors. No owned human
settlement was supplying another sight source in that observation. This is
an actual visibility failure, not a missing validation label. A zero-error
runtime and concealed minimap do not establish that the main scene is hidden.

Read-only native/code and current-graphics investigations identified two
concrete gaps:

- In native rendering mode 1, graphics parts whose virtual `+0xC8` getter
  returns zero can use a static path that bypasses the wrapped sprite calls.
  The native village parts included those zero-valued cases, while a separate
  animated Market part had a nonzero value.
- Market definition **3700** is anchored at `(506, 205)`, but its graphics
  centre and part offsets land on a continuation cell. At the sampled centre,
  the occupied/static bit 31 is clear. The r5 point-based classification can
  consequently miss the positive building at its anchor and allow that part.

The retained read-only reports are
`world-v6-r5-wv61-graphics-points-investigation.json` and
`world-v6-r5-wv61-static-animated-split-investigation.json`. The per-part
orientation candidates in these reports are explicitly derived, not a GPU
draw trace. They support the continuation-cell finding without certifying
every final screen coordinate or a complete corrected renderer path.

The **r6 repair source, three builds per profile, full suite and closed-game
installer cycle have now passed their separate checks**. Actual-game
validation of that repair remains pending. No corrected static-coverage result is
claimed. The actual fresh-world Terra reset has **not** been tested, the
Food + World actual-game profile has **not** been tested, and full
GPU/visibility acceptance has **not** passed.

### Completed r5 resave disk certificate and preservation

The user's investigation resave **wv61r** has passed independent read-only
certification. Its native filename/world identifier is
`fabc6d74-9b16-448a-b65ba65f664d9751` and its save SHA-256 is
`cd963184483fb157d4db1fdfafdd6017d9d46313cec2f2648b8fcd83fa72df07`.
The comparison against certified `wv61` retained the world dimensions and
Unexplored/Strict policy, all **24 island geometries/climates**, all **13
interpreted harvest-crop bits**, positive mineral masks, and the unordered
deposit definition IDs, positions and quantities. Record serialization order
changed; physical deposit contents did not.

All **four old human discoveries remain**, with **island 0 additionally known**
in the resave. This is disk evidence of retained/new discovery state, **not
an observed GPU reveal transition**, a fresh-start test or proof that the
remaining static visibility defect is fixed. The v1 comparison was order
sensitive and failed; it remains preserved. The passing v2 comparison
explicitly accounts for native occurrence-record serialization ordering.
The exact reports are `world-v6-r5-wv61r-save-certificate.json` and
`world-v6-r5-wv61-to-wv61r-comparison-v2.json` under `.local/validation/`.

After the user saved, r5 closed normally. The progressed autosave was archived
separately and the original `Lastgame.sav` restored, as recorded in
`world-v6-r5-autosave-restoration.json`. Other saves were unchanged. The closed
preservation state contains **38 native saves, five presets and 26 retained
managed backup generations**. The original and progressed autosaves remain
separate. This is the pre-r6 closed baseline; the later r6 cycle raised the
retained generation count to 29 without changing those save/preset files.
Neither preservation snapshot establishes corrected r6 game rendering.

## Historical r4 build, suite and installer results

The superseded r4 profiles each had three identical builds. Their full suite
ran **249 tests in 166.188 seconds: 244 passed and five were skipped** because
Windows symlink privileges were unavailable, with no errors or failures.
Those results preceded the live-discovered classification and inherited
initial-discovery corrections. They are not the r5 suite/build result.

The closed-game r4 installer cycle passed through restoration of the preceding
development build, World-only installation/restoration, Food + World
installation/restoration, and a final World-only installation. Each install
matched its exact package and was a production no-op when checked again.
World-only changed 19 managed files; Food + World changed 41. Restoration
returned the 23-file stock closure and removed the 19 introduced World files.

All 36 pre-existing native saves, four presets, 297 original-game backup files,
23 original source inputs, 488 imported files and 43 compiled inputs remained
exact. The 20 preceding managed backup generations were retained alongside
three newly restored generations. That cycle ended with World Settings enabled and Food disabled. These
historical installer results involved no game process or native hook
activation; they do not certify an r5 installation.

## Historical r4 actual-game observation: Fog1

This is a **superseded r4 run, not corrected r5 acceptance**. The
**World-only** r4 managed copy was observed at its in-game Visibility
screen with the preview covered. The captured **Fog1** preset/ready snapshot
selected Unexplored and Strict line of sight, seed **2053342348**, a
**1024 by 1024** world, **24 Mixed islands**, spacing **16**, three AI
opponents, all eight native cultures, Pirates and Venetians, Medium stock
and fertility options, 30,000 money and a single starting ship. It retained
an automatic starting island. This does not test every visibility option or
all preset round-trip behavior.

The world loaded with 24 islands and empty factory, hook, AI-loader and
AI-profile error strings. The committed plan retained those choices.
Independent current-state reads matched the preview geometry, climates and
interpreted harvest-crop bits; they do not claim semantics for the remaining
upper crop flags. Native controller reads found **three active ordinary AI
owners (1, 2, 3)** and a separately allocated inactive slot. Optional unloaded
AI modules were not certified.

| Observed layer | Bounded result |
| --- | --- |
| Process/runtime identity | The running executable, copied World-only runtime and native profile matched the reviewed r4 input identities. |
| Native activation diagnostics | **13 visibility components and 173 engine edits** reported active. At the captured diagnostic instant, **109,080 rows were masked and 109,080 restored**, with **zero pending rows** and **last error 0**. These counters are presentation diagnostics, not a complete GPU-frame proof. |
| Actual sprite delegate | Slot `0x188` was observed resolving to **AnnoDisplay.dll + `0x49BD0`**, matching the reviewed Display module. Slot `0x180` had not been observed in that capture; its target remained zero in the diagnostic. |
| Discovery/current bitmap | The current world had **4 known and 20 unknown islands**. Its sampled 256-square minimap bitmap contained **zero undiscovered-island geography pixels**, **zero undiscovered-island owner-colour pixels** and **zero owner/activity-colour pixels outside the current 48-tile vision area**. These are CPU display-metadata reads, not independent verification of the final rendered image. |
| Sailing snapshots | The same human ship was read near `(486.40, 236.40)`, then `(425.83, 209.50)` and `(425.50, 209.50)`. Minimap owner-colour pixels inside sight changed from 64 to 0, while outside-sight colour remained 0. Discovery stayed 4 known / 20 unknown; no new whole-island discovery transition is claimed. No owned-settlement source existed in these snapshots. |

This is current-state evidence from an already running game, **not a
fresh-initial-state capture**, complete visual acceptance, or a proof that an
enemy was visibly revealed and then hidden at the range boundary. The
independent observer used read-only process access, with no remote function,
settings, discovery, terrain or activation writes. The separate production
diagnostic used the bounded inert session interface; it was not a visibility
setter. Full scene/GPU presentation remains to be assessed.

The r4 native save `wv61`, world identifier
`389af543-f8b2-4ed9-a4f5a837ddd9857d`, has passed an independent read-only disk
certificate. Its saved policy is `0x1000` (Unexplored/Strict); all 24 island
geometries, climates, 13 interpreted harvest-crop bits and positive physical
mineral masks match the captured preview. Previously human-discovered islands
remain discovered in that save. Upper adjacent discovery words and owner
contact records are not reinterpreted as map settings. The certificate does
not establish initial discovery provenance, harvest/mine accessibility,
initial fleet/money, a GPU frame or a fresh-process restart.

The village-definition and inherited Pirate-template findings have the
source/native explanations above. R5's bounded old-save reload succeeded,
but its actual village visibility still failed through additional static
paths. Fresh Terra creation and a repaired renderer remain untested. R4's
certificate does not retroactively make its initial discovery/classification
behavior correct.

Private evidence is retained as `world-v6-r4-fog1-preview.json`,
`world-v6-r4-fog1-loaded-identity.json`,
`world-v6-r4-fog1-loaded-diagnostics.json`,
`world-v6-r4-fog1-current-memory-v2.json`, and the corresponding
`sailing-before`, `sailing-after` and `sailing-end` reports under
`.local/validation/`. The completed disk certificate is
`world-v6-r4-wv61-save-certificate.json`. These historical observations are
separate from the r5 automated fixture reports.

## Further validation and limits

These are directions for broader future coverage, beyond the completed
bounded r8 acceptance recorded above.

1. Extend the successful r8 camera/visibility sample to broader populations,
   world sizes and longer play, keeping measured performance separate from
   the user's smoothness report. The `wv63` disk certificate and r8 reload
   passed, and closing preservation retained the saved checkpoint and original
   `Lastgame`. Later live interactions were not captured in a new save.
   Retain earlier r6/r7 results separately.
2. Test precise hidden building footprints, hovering, previously selected
   objects and retained sidebars. The one far land click with an empty
   sidebar does not establish those interaction behaviors. Extend actual
   rendered samples to other buildings, neutral scenery, actors and markers.
3. Capture an actual fresh Terra world at the post-construction boundary,
   including remote Pirate/native islands. Verify once-only human-bit
   clearing, normal stationary/local contact, remote whole-island reveal,
   remembered geography and preservation of other owners' knowledge. No
   fresh reset may run on a loaded explored save.
4. Exercise all three map modes and both activity choices, additional range
   crossings and settlement building extents. Test all six menu pages, stale
   covered previews, invalid settings, generation and current format-3 preset
   round trips. Verify Fully explored fertility information in the actual UI.
5. Recheck the exact runtime/transaction and retained user data around
   subsequent launches/saves, and measure longer-session behavior/performance.
   Keep native instruction, CPU display-metadata, actual screenshots and
   save/reload evidence distinct.

Food + World actual visibility gameplay was **not performed or repeated in
this iteration, per the user's request**. It is not required before this
iteration's publication. Its reviewed profile builds, isolated scene checks
and production installation/restoration remain separate evidence; the
World-only smoothness/visibility sample does not stand in for a Food live
test. The 14-tile native discovery query remains distinct from the 48-tile
current activity sight in both profiles.

The historical r8 baseline above has whole-island discovery rather than the
new charted-cell implementation. Neither baseline establishes multiplayer
visibility support. Long-session economy, AI strategy, combat, navigation and
performance are not established by the targeted fixtures above.
