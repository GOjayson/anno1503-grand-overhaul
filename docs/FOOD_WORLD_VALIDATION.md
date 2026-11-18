# Food 0.6 + World Settings validation

**Scope:** the separate `food06-world` development profile combines Food
0.6.0-dev.1 with World Settings 0.9.0-beta.1 on the inspected 64-bit History
Edition build and Dutch inputs. Use a new endless world. The optional Bug Fixes
combination has a separate, explicitly bound asset recipe and acceptance scope
recorded below; earlier Food + World observations did not include it.

**Food + World baseline:** native construction, instruction fixtures, package
validation and the full repository suite passed. That suite completed
817 tests in 325.674 seconds: **812 passed and five were skipped**.
Managed-copy installation, restoration, reinstallation, normal startup,
engine activation, bounded generated-world inspection, the house/market UI,
saved ship-cargo inspection and both combined save-loading routes have also
passed. Controlled purchase accounting, full tier progression and long-session
balance remain unverified. The Food-only observations remain historical
evidence for their separate profile.

The player-facing diet and house display are described in the [Food
guide](FOOD_OVERHAUL.md). Its [Food-only validation](FOOD_06_VALIDATION.md)
remains separate from this record.

## Exact profile and preservation

The combination has its own [runtime builder](../src/anno1503_overhaul/food_world_runtime.py),
[package recipe](../src/anno1503_overhaul/food_world_package.py),
[host-file policy](../src/anno1503_overhaul/food_world_policy.py) and
[installation backend](../src/anno1503_overhaul/food_world_backend.py).
It does not accept Food 0.6 hashes as alternatives in the older Food 0.5 or
stock World-only validators.

| Component | Reviewed fingerprint prefix | Scope |
| --- | --- | --- |
| Food house View derivative | `b5af6086d34a` | Existing Food 0.6 house panel and original Food summary icon. |
| Food World derivative | `e3755d8d796d` | Existing Food 0.6 household supply and promotion guards. |
| Combined World runtime | `6bf858328c35` | Separate runtime with exact Food 0.6 host pins and private AI demand bounds. |
| Combined engine plan | `e23755295539` | Existing 173 engine edits with two exception-table targets rebound to the active Food 0.6 table. |
| Private CompLogic | `73b49582fa39` | Existing faction activity policy plus bounded demand lookup. |
| Private CompLogicClassic | `70af14ff63d9` | Equivalent separate classic-rule AI derivative for this History Edition host. |

Complete hashes are pinned in the linked source. The inspected executable is
AMD64 PE32+, not the classic game's executable architecture.

The recipe prepares **21 Food edits and 19 introduced World files in one
restoration transaction**. Complete original and resulting file hashes cover
the three modified archives, in addition to their region preimages. Unknown
files, changed inputs, conflicting introduced files, missing backups and
different feature versions are refused. Installation and activation remain
bound to an independent managed copy.

The original Ubisoft game, preserved Food 0.5 recipe, stock World-only route,
Food-only route, imported compiled inputs and released archives are not
replaced by this profile. Restoration uses the retained checked originals;
existing saves and older backup generations must be preserved.

## Automated and native evidence

| Area | Verified evidence | What this does not establish |
| --- | --- | --- |
| Full repository suite | The current suite completed 817 tests in 325.674 seconds, with 812 passing and five skipped. | Skipped coverage, managed installation or actual combined gameplay. |
| Reproducible runtime | Two fresh builds produced identical reviewed runtime bytes and staged C-source closures. Ten new runtime tests passed. | Successful game activation or rendered-world behavior. |
| Preserved runtime | Eleven existing runtime tests passed, and the original Food 0.5 combined runtime was rebuilt to its unchanged reviewed fingerprint. | New gameplay acceptance for the old profile. |
| Native preimages | Exact host hashes, nine base hooks, all 173 engine edits, visibility and ownership dispatches, scene-factory import, disaster sites and island readers passed their bounded checks. All **218 World write spans** are disjoint from the **eight Food 0.6 mutations** in original mapped sections. | Renderer correctness, camera performance or sustained simulation. |
| Active exception table | The loader-active Food 0.6 table starts at RVA `0x153140`. The two existing World exception edits move from `0x14be8c` and `0x14be94` to `0x157b18` and `0x157b20`. Unique complete function tuples identify those targets; matching bytes in retained inactive tables are not accepted. | Broader exception behavior outside the checked native paths. |
| Food promotion unwind | Nine supply tests passed. The registered native function-table fixture checks all 125 promotion-thunk byte offsets and all 14 original entry-patch byte offsets. Native return address, stack and saved registers restore correctly. | Actual progression through every population tier. |
| Private AI demand bounds | Five tests passed, including 60 complete native evaluator cases at two image bases, 1,080 good-metric comparisons, 20 unchanged valid-input regressions and 122 registered Windows unwind comparisons. | Complete AI food production, trade, expansion or economy balance. |
| Package and selection | The combination uses its own closed inventory, manifest and explicit Food version. Changed runtimes, private AI, helpers, native hosts or frozen inputs cannot be accepted merely by editing manifest hashes. Food-only and World-only packages cannot masquerade as the combined profile. | Installation success on a user's particular game copy. |

The native evaluator and unwind checks execute instructions or inspect
structures in independent test allocations. They do not attach to a game,
install hooks in a game process or count as an actual game run. See the
[runtime tests](../tests/test_food_world_runtime.py),
[AI tests](../tests/test_food_world_ai.py),
[supply tests](../tests/test_food_supply.py) and
[package tests](../tests/test_food_world_package.py).

## Managed-copy installation and restoration

The validated copy-bound package installed **40 changes** on a new independent
managed copy. The restoration round trip returned all 21 Food targets to their
checked original hashes and removed the 19 introduced World files. The same
40 changes were then reinstalled, retaining the earlier backup generation.

An independent read-only verification after reinstallation checked all 21
Food outputs and 19 introduced outputs against their exact pins. Both the
installed and retained restored journals contain the expected 40 targets;
each generation retains 21 verified original backup files. This inspection
confirms the retained journals and current files; the restoration itself was
performed by the installation test, not repeated by the independent observer.

The same verification confirmed that 17 protected original-game files and 18
checked native/data/installation-record files across the three pre-existing
managed copies were unchanged. A final independent inspection rechecked these
files, all 40 installed outputs and the 21 original files in each of the two
backup generations, including complete hashes and sizes. The generations'
edit records matched. All ten existing source backup directories retained
their exact name inventory; the older source backups' contents were not
separately compared to a historical content baseline. No game process or game
controls were accessed by these independent file inspections.

## Combined behavior boundaries

Food keeps its five tier-specific foods and read-only house summary. The
summary adds no traded good, purchase or consumption. The existing Fish
starvation path remains; the aggregate percentage does not make different
foods interchangeable.

Starting cargo good 26 is **Fish** when Food is enabled, so the combined
Starting options page labels it **Fish (tons)**. The nearby-resource guarantee
still covers grain, flax, potatoes, iron and salt. It does not guarantee the
complete Food diet or every production-chain input.

The separate [AI guard](../src/anno1503_overhaul/food_world_ai.py) is necessary
because an absent need maps to the native need-count sentinel. The inherited
demand loop could read an unused rate at that index. The new guard checks the
reviewed count limit and requires `index < count` before reading a rate.
Absent or invalid mappings contribute no demand; valid rates, including zero,
retain the native arithmetic. Poisoned unused slots reproduce the earlier
behavior in fixtures and no longer affect the guarded result. Existing
faction activity policies and older private AI derivatives remain separate.

World visibility and ownership checks retain their original native building
interfaces. They do not use the newly changed Food supply-getter slots. The
house-display hooks and World scene-factory import hook occupy different
locations; no shared house buffer or saved-object layout is enlarged.

Zero-share needs are removed from lower tiers, changing per-house saved need
indices. Vanilla and Food 0.5 saves are not migrated or automatically blocked.
The earlier Food-only `fd1` and `fd2` observations do not establish combined
save compatibility.

## Actual combined game checks

**Startup and activation passed.** The installed route started Anno through
the normal Ubisoft client, closed its exact owned source main menu and left
one managed game process. Activation reported the reviewed runtime and engine
plan, all instruction bytes for the 173 engine edits verified, count/status 173 and
nine base hook sites installed. The custom in-game World Settings menu opened.
These are actual startup observations. No AI-profile status is claimed from
the activation result itself.

**Fresh Huge world passed bounded native checks.** The captured setup uses
seed 123456789, Huge 2048 × 2048, 24 mixed islands and spacing 16. Read-only
inspection of the generated world confirmed its dimensions and all 24 island
positions, dimensions and climates against the captured preview. All 173
engine instruction edits remained verified in the running world. This
structural comparison does not replace visual terrain or performance checks.

The human and four ordinary CPU placeholder profiles contained all five
resident tiers, with need counts **8, 13, 16, 15 and 12** and the expected
tier-specific food mappings. Owners 1–3 were active native CPU controllers;
owner 4 was suspended and not thinking. This establishes three
active opponents, not four, and does not certify their food planning or
long-session economy. The read-only observer used exact module/getter
identities, wrote no process memory, called no remote functions, controlled
no game input and performed no arbitrary heap scan.

The captured setup has **Fully explored** and **Reveal all activity**. It does
not establish strict-line-of-sight behavior in the combined build.

**House and market displays passed bounded live checks.** An occupied Pioneer
house showed eight residents, the original Food summary icon, a fully fitting
**Delivered food** caption and individual Fish, Game meat and Potatoes needs.
Bread and Butcher's meat were absent from the Pioneer panel. The combined
value was initially observed at 37%; after the in-game reload it showed 45%,
with a full Fish bar and Game meat/Potatoes missing. The 45% value matches the
configured Pioneer Fish share and remained visible after a full restart.
This is a basic observed supply/display response, not decoded per-house
buffers or a controlled food-purchase accounting test.

The Food market displayed all five food icons plus Salt with consistent
native teal backgrounds and frames. All six entries had sale controls and
prices: foods 45, Salt 40. Fish stock was four tons and the other foods were
zero. Sale-toggle response, isolated sale income and stock debits were not
tested under controlled conditions.

**Saved cargo and policies passed structural inspection.** The Merchant fleet
selection requested 25 tons of tools, 75 tons of wood and 40 tons of Fish.
Both untouched small trade ships retained those exact totals, filling their
four holds as Tools 25, Wood 50, Wood 25 and Fish 40. The large trade ship had
already supplied the user's warehouse, house and Food market; its saved
remaining totals were Tools 13, Wood 53 and Fish 34. These observations do not
claim that the large ship's untouched initial cargo was captured.

The native saves `fc1`, `fc1r` and `fc2` passed complete-container inspection.
Each retained the Huge world's 24 island rectangles and climates matching the
preview, three active ordinary AI opponents, the saved visibility/disaster
policies and the three human ship identities. `fc2` retained the same ship
positions, cargo and health as `fc1r`; `fc1` and `fc1r` remained unchanged.
Household food buffers and the original starting-money balance were not
decoded or established by these post-building saves.

**Both loading routes passed.** The user loaded `fc1` through the in-game Load
menu, confirmed a successful reload, and saved `fc1r`. The settlement rendered
without a black map or reported error. Independent read-only checks again
verified all 173 engine edits, the preview-matching Huge geometry, the Food
need counts and three active AI opponents.

A fresh Anno process then loaded `fc1r` from the main menu. The settlement and
eight-resident house rendered correctly, with the original Food icon, 45%
summary and fitting caption. The restart receipt and an independent current
byte check verified the exact runtime/engine pins, all 173 engine edits and
nine base hooks. The receipt contained one activation attempt, one result and
one success, together with the owned source-menu close and managed-copy
launch. The final `fc2` save passed independent inspection, and the managed
game was left open for the user.

## Optional Bug Fixes acceptance — 2026-11-18

The source installer can explicitly select Food 0.6, World Settings and Bug
Fixes 1.2 together. Its optional asset recipe is recomputed from supported
original quest, scenario and sound files. Package metadata, installation
selection, current outputs, original backups and the complete restoration
journal must agree before launch. Unknown additional targets are refused.
The isolated launcher stages a closed set of five support modules; an actual
child-interpreter fixture checks that dependency closure. The native Food and
World fingerprints above are unchanged.

**Automated checks passed.** The updated full repository suite completed 869
tests in 372.636 seconds: 864 passed and five Windows symbolic-link privilege
checks were skipped. The final repository-content check passed all 718 public files,
including the immutable imported-source checks. A subsequent Food catalogue
wording update passed the 34 profile and 11 CLI selection checks (one of the
profile checks has the same symbolic-link privilege skip). Automated and native
instruction fixtures do not count as game runs.

**Installation and restoration passed on another independent copy.** The
Dutch all-three selection installed 159 file changes: the existing 40 Food +
World changes, one quest text file and 118 quieter WAV files. Exact restoration
returned every original target to its complete hash and size and removed the
introduced files. Reinstallation passed. Both retained journal generations
contain the same 159 targets, with 140 verified original backup files each.
Independent file inspection rechecked every output and both sets of originals.
Seventeen protected source files and 41 checked files across seven preceding
copies remained unchanged. All ten original source-backup directory names
were retained; their historical contents were not separately audited.

**A fresh all-three world passed a bounded game check.** Automatic startup
reached the in-game custom World Settings screen, and a new 1024 × 1024 world
loaded with 24 mixed islands, spacing 16 and zero AI opponents. Read-only
inspection verified all 173 active engine edits, the selected dimensions,
every island rectangle/climate against its captured preview, non-overlap and
the expected Food need counts of 8, 13, 16, 15 and 12. The user saved this world
as `am1`. Complete-container inspection retained its map and policies, zero
active AI and one full-health trade ship carrying 80 tools, 50 wood and 10
Fish within its holds. The post-upkeep balance is not evidence of the untouched
initial money amount.

**In-game loading of the preceding compatible Food + World save passed.** The
user loaded `fc2` through the in-game Load menu in the same all-three process.
Read-only checks confirmed the 2048 × 2048 world, three active ordinary AI,
all 173 engine edits and Food tier definitions. Its 24 island geometries match
the original captured preview and preserved native save. Cross-copy preview
guards were kept intact; the geometry comparison was performed separately.
The occupied eight-resident Pioneer house displayed the original Food icon,
a 45% summary and the fitting Delivered food caption. The market displayed
the five foods plus Salt with matching frames/backgrounds and its sale controls.
The original `fc2` file remained unchanged. The managed game was left open.

The stock World Settings + Bug Fixes selection with Food unchecked also passed
backend, package, selection and restoration fixtures and independent review.
Those checks preserve the stock diet, UI and native host pins; they do not
establish an actual Food-disabled game run with Bug Fixes. The preserved Food
0.5 + World + Bug Fixes combination is explicitly unsupported.

The all-three quick check did not trigger the King of Ore quest, measure
perceived sound mixing, replay a full campaign or establish long-session
economy/stability. Those observations are separate from the exact installed
quest and WAV file checks and the preceding standalone Bug Fixes evidence.

## Remaining gameplay acceptance

Controlled purchase and sale-toggle tests, decoded household supply accounting,
food withholding, vacant-house display, full population progression,
sustained production/sales, AI food planning and long-session balance remain
unverified. Strict line of sight, camera performance and the complete World
Settings feature matrix were not revalidated by this Fully explored/Reveal
all test. Multiplayer, tutorials, campaigns, other localizations and additional
feature combinations require separate gameplay acceptance.
