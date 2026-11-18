# Food overhaul

**Food 0.6.0-dev.1 has separate Food-only and Food + World Settings development
profiles. Start a new endless world.** Bounded Food-only and combined live
checks passed, including both save-loading routes. Complete tier progression
and long-session economy balance remain unverified.
See the separate [Food-only validation](FOOD_06_VALIDATION.md) and
[Food + World Settings validation](FOOD_WORLD_VALIDATION.md).

Food remains optional. Leaving it unchecked keeps the standard food economy.
This candidate targets the inspected AMD64 History Edition build and Dutch UI
inputs; unknown builds or modified inputs are refused.

## Five foods, with diets for each population tier

The original game's producers contribute to one shared Food good. The Food
overhaul separates their output into Fish, Potatoes, Game meat, Bread and
Butcher's meat. Existing production chains, inputs, timings and building costs
remain unchanged. The hunting lodge keeps its hides output, and the small farm
keeps alcohol production.

Food 0.6 uses these shares of each tier's original total food requirement:

| Population tier | Fish | Potatoes | Game meat | Bread | Butcher's meat |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pioneers / peasants | 45% | 45% | 10% | — | — |
| Settlers | 40% | 35% | 10% | — | 15% |
| Citizens | 30% | 25% | 10% | 20% | 15% |
| Merchants | 20% | 20% | 10% | 25% | 25% |
| Aristocrats | 15% | 10% | 15% | 25% | 35% |

The complete configured quantities retain each tier's original Food total.
Other resident needs remain unchanged. A house uses its own population tier;
unlocking Bread elsewhere does not add Bread to pioneer or settler houses.
Zero-share foods are omitted from those tiers' need records.

Bread and Butcher's meat retain their existing production-chain unlock gates.
Locked foods are excluded from the informative Food bar, whose remaining
weights are normalized to 100%. This is display calculation, not a runtime
redistribution of consumption quantities between foods.

## Informative Food bar in houses

The house information panel adds a combined **Food** icon, percentage and bar.
It reads that household's actual delivered supply through the native supply
getter, weighted by its active food requirements. Warehouse stock alone does
not establish that a particular house is supplied. A fully supplied house can
reach 100% before later foods unlock. Vacant houses show **No residents**.

For example, a pioneer house fully supplied with Fish and Potatoes but missing
Game meat shows 90%. Existing individual food icons and bars remain available
for the detailed supply information.

The combined Food category is read-only. It has no market price, cargo, stock
slot, purchase order or extra consumption. Residents still purchase and
consume the individual foods; the summary does not consume anything twice or
create sales income. It is derived when the house information is refreshed
and adds no saved need or traded-good ID.

**Fish still follows the existing staple/starvation path.** The summary does
not make foods interchangeable or change the starvation, happiness or
advancement rules to use its combined percentage. Those would be separate
gameplay changes.

## Icons and markets

- The informative Food category reuses the original game's Food icon. Its
  colour and grey frames are copied locally, with only their texture IDs
  changed and their original palettes retained.
- All five individual food icons use one consistent consumer background and
  native frame, derived locally from the player's original Food artwork. The
  authored food foregrounds retain their distinct appearances. Native colour,
  grey and low-resolution formats are handled separately.
- All five foods remain together in Consumer Goods and in ship-loading menus.
- The Food market still sells the five actual foods plus Salt, with separate
  sale switches, displayed prices, stock deductions and city sale income.
  Jewelry and Wine stands retain their normal goods.

Original game artwork is reconstructed from the player's supported files at
preparation time; it is not added to this public repository.

## Installation and saves

Use the Windows source installer on a separate managed game copy. Select
**Food overhaul** and explicitly choose **Food 0.6**, then choose the profile:

- **Food only:** leave **World Settings** unchecked. This uses the Food-only
  startup route and does not activate World Settings.
- **Food + World Settings:** check both features. This uses its own reviewed
  combined profile. All world-generation choices remain inside the game,
  including the preview and starting options.
- **Bug Fixes:** optionally select this alongside either Food profile. With
  Food + World Settings it uses an explicitly bound package that also checks
  the quest correction and quieter sound effects. All selected changes share
  one restoration journal; the native Food and World fingerprints stay exact.

Run **Check installation** before **Install selected features**, then use
**Start installed game** to launch the installed profile through the normal
Ubisoft client. Food 0.6 preparation requires the reviewed offline compiler.
The combined profile also requires the preserved local development inputs and
its separately reviewed, version-matched World runtime. Keep the preserved
inputs in the local baseline store or select their folder under **Advanced**.
The reviewed runtime must be available in its separate local runtime-profile
store. Missing or changed inputs are refused.

When Food is enabled, the starting cargo option labelled **Fish (tons)** loads
Fish. It does not load a combined Food good or a mixture of the five foods.
The nearby-resource guarantee retains its existing scope; it does not guarantee
the complete five-food diet.

The published World Settings beta ZIP, stock World-only route and preserved
Food 0.5 recipes remain unchanged. These Food 0.6 source profiles have their own
native fingerprints and validation; the public beta ZIP does not install them.

**Start a new world.** Food 0.6 removes zero-share needs, which changes the
ordering of per-house need buffers. It does not migrate vanilla or Food 0.5
saves. Keep those saves with a matching original or Food 0.5 installation;
do not load them into Food 0.6 to test compatibility. This is a compatibility
requirement; the game does not automatically block older saves.
Start a new world for the combined profile even if you already have Food-only
0.6 saves. Loading saves across those profiles has not been accepted.

Close Anno and use **Restore original game** before changing the installed
feature set or Food version. Restoration uses the managed copy's checked
original files and retained backup journal. Existing saves, older backup
generations and the original Ubisoft installation are preserved.

Food 0.5 remains available through its preserved recipe, including its separate
legacy combined World Settings development profile. Selecting Food 0.6 with
World Settings selects the new combined profile; neither version's fingerprints
are accepted as the other's.
Read [installer details](INSTALLER.md) for the common copy and restoration
rules.

## Current limits

The tier data, native household calculation, icon composition and installer
selection have automated checks. On an independent Food-only copy, basic live
checks passed for new-world creation, an occupied pioneer house's Food row, all five
market icons, a Fish purchase and the resulting Food-bar response. The new
save also loaded through both the in-game menu and a fresh game process.
Complete tier advancement, sustained sales/consumption and long-session
economy balance still need gameplay checks.

The new Food 0.6 + World Settings profile has passed automated package,
selection and restoration fixtures, reproducible native construction and
bounded native instruction checks. On a separate managed copy, installation,
restoration and reinstallation passed. Its live check generated a Huge world
with 24 preview-matching islands and three active AI opponents. Saved ships
preserved the selected custom cargo. The occupied pioneer house displayed
the original Food summary icon and reached 45% with Fish supplied; the market
showed all five foods plus Salt with matching backgrounds. The world and
house display survived both an in-game reload and a fresh process. Follow
the [combined validation record](FOOD_WORLD_VALIDATION.md) for the precise
scope, remaining purchase checks and untested feature combinations.

Complete AI food planning and long-session economy balance remain unfinished.
The stock endless test's human and AI resident definitions were inspected in
memory, but that does not establish complete AI production or trade behavior.
Existing Food 0.5 instruction checks and earlier combined-world observations
do not certify this changed candidate. Multiplayer, tutorial and campaign
compatibility are not established by this work.
