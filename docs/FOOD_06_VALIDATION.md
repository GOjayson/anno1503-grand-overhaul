# Food 0.6 development validation

**Scope:** Food 0.6.0-dev.1, Food-only, new endless worlds on the inspected
64-bit History Edition build. World Settings is disabled. Food 0.5 and its
preserved combined profile remain separate.

**Status of the original 0.6 release:** the final shorter-label candidate passed focused
Food checks, the full-repository suite for that revision, managed-copy
restoration/reinstallation and
bounded live startup, house-display, food-purchase and save-reload checks.
All-tier playthrough and broader gameplay acceptance remain unverified.

The diet and player-facing behavior are described in [Food
overhaul](FOOD_OVERHAUL.md). Short native fingerprint prefixes identify the
checkpoints below; the exact pins are maintained in
[food_household.py](../src/anno1503_overhaul/food_household.py) and
[food_supply.py](../src/anno1503_overhaul/food_supply.py).

## Combined housing progression

The source build now scores active foods together for population growth,
food-related population loss and promotion. It uses the house's existing
delivered supply and the owner's unlock mask.

Native fixtures compare the vanilla and combined-food routines across 101
food-delivery levels for each of the five growth tables and for each of the
three residential upgrades. Separate cases exercise per-food caps, locked
and newly unlocked foods, missing non-food goods and services, and owner
unlock handling through both native entry points. These fixtures run outside
the game. Timing from matched in-game starts still needs validation.

## Evidence checkpoints

| Checkpoint | Automated evidence | Actual game evidence |
| --- | --- | --- |
| Earlier implementation, before the promotion repair | A full-repository run completed 751 tests with 5 skipped. This is historical evidence for that earlier source, not validation of the later promotion guard or shorter label. | Earlier candidates exited shortly after entering a new world. Their results do not establish current acceptance. |
| View `21fd` with World derivative `e375` | 101 focused Food tests passed. These include the repaired supply and promotion paths. | Approximately eight minutes in a new stock endless world; occupied Pioneer house, original Food icon and 43% combined supply visible; test world `fd1` saved; normal exit code 0. |
| View `b5af` with World derivative `e375` | 101 focused Food tests passed. The current full-repository suite completed 756 tests in 307.131 seconds, with 5 skipped. | Exact installed/loaded module identity checks passed. Restoration/reinstallation retained backups and the unchanged `fd1` save. One copied game process restarted normally; `fd1` loaded through both the main menu and the in-game Load menu. The occupied Pioneer row, fitting **Delivered food** caption, market artwork and basic purchase response were observed. Post-check save `fd2` passed independent structural inspection; normal exit code 0 was confirmed. |

## Automated coverage

The focused checks include:

| Area | What the checks establish |
| --- | --- |
| Tier diets | Exact five-tier data proportions; each original complete Food total; unchanged unrelated needs and unlock definitions; omission of zero-share foods; refusal of changed inputs and ambiguous structure. |
| Household measurement | Weight actual delivered household supplies by active native need rates; exclude locked, absent and zero-rate foods; clamp scores; distinguish empty houses; leave simulation memory unchanged. An independent fixture executes the exact inspected native supply getter. |
| House constructor and UI | Execute the authored constructor, registration, resource-query and refresh paths with native-shaped boundaries; verify the calculated label/bar, nonzero panel origins, retained tooltip lifetimes, resource/factory failures and unchanged household memory. Resource, allocation and graphics boundaries remain substitutes. |
| Native View derivative | Exact supported input and virtual preimages; reproducible compilation; bounded sections; retained ASLR relocations and valid exception/unwind composition; refusal of unknown native inputs. |
| Native World supply guards | Both original getters retain their valid results and empty-house behavior. Missing mappings, invalid indices and zero rates return safely. Actual native getter comparisons run after applying loader relocations to an independent in-process image. |
| Native promotion guard | The inspected original upward-tier body reproduces division by zero for newly absent next-tier foods. The actual repaired derivative permits supplied Pioneer-to-Settler and Settler-to-Citizen transitions in controlled native fixtures, while missing cloth/service supply, missing non-food requirements and checked zero-rate demands still block promotion. Chained unwind checks restore the complete native frame throughout the appended thunk. |
| Artwork | Derive the summary icon from the player's original Food artwork; preserve native palettes, transparency, supported dimensions, shared background/frame and unrelated sprites; reproduce outputs and refuse changed inputs. |
| Package, selection and startup | Exact Food-only payload/helper closure, explicit version selection, refusal of Food 0.6 plus World Settings, preserved Food 0.5 recovery and combined routes, fixture restoration, and normal-client startup through the owned source-menu handoff. |

These are automated/data/native-fixture checks, not additional game runs.
They do not establish complete renderer behavior, resident pathfinding,
long-session balance or a functioning AI food economy.

Artwork checks cover the available main 50 × 50, main low-resolution 39 × 39
and Dutch 50 × 50 UI pairs. An authored mixed 39/40 × 39 fixture checks dimension
preservation. Other language and UI combinations remain unverified.

## Original 0.6 implementation boundaries

- The new diet is composed from exact preserved Food 0.5 resident definitions.
  Complete file-level Food quantities retain each tier's original total.
  Existing production recipes, unrelated needs and native chain unlocks remain.
  Native integer rate quantization is separate from the source decimal table.
- Zero-share foods are absent from that tier's need list even after another
  city unlocks the corresponding chain. This changes per-house need indices;
  **new worlds are required**. No old-save migration is provided.
- The Food row is informative. It reads delivered house buffers and actual
  active need rates, excludes locked foods from its denominator, and creates no
  additional good or saved requirement. Refreshing it does not buy food, debit
  stocks or credit money. Native individual food icons remain the breakdown.
- Fish keeps the existing first-slot hunger/starvation role. The combined
  display does not introduce food substitution or replace hunger, happiness
  or growth with a new aggregate mechanic.
- The World derivative guards the original by-good and indexed supply getters
  before their native division. Valid requests and empty houses delegate to
  the untouched original getter bodies.
- Native promotion eligibility also mapped next-tier requirements into the
  current tier and divided inline, bypassing those getter guards. Its reviewed
  mapping-block detour skips only Bread or Butcher's Meat that the current tier
  does not consume. Other absent requirements and present zero-rate demands
  fail safely. Existing scoring, non-food requirements and service rules stay
  on their native paths; next-tier-only foods do not become circular
  pre-upgrade requirements.
- The promotion thunk preserves its existing frame and chains unwind metadata
  to the exact native fragment. The native promotion body outside its reviewed
  mapping preimage, original getter bodies, exports, imports and existing
  relocation data are retained. Compatibility checks remain exact-build checks.
- Original legacy source and its compiled-source fingerprints remain unchanged.
  The published World Settings beta is not replaced by this development work.
  No game binaries, islands, saves or private test paths are published here.

## Bounded actual game observations

The View `21fd` / World `e375` run used stock endless setup without World
Settings activation. It remained running for approximately eight minutes.
Opening the building menu, placing and selecting an occupied Pioneer house
worked. The original Food summary icon and a 43% combined supply value were
visible. The second subtitle clipped at the right edge, which prompted the
**Delivered food** change in View `b5af`. Save inspection identified two CPU
players; no claim of three active AI players is made for this run.

A separate read-only inspection of live resident profiles passed: the inspected
player tables contained all five tiers, with need counts **8, 13, 16, 15, 12**.
Zero-share food absence and good-to-need lookup bounds were consistent with the
new definitions. The observer wrote no process memory, called no remote
functions and sent no game input. Stored rates were recorded as raw native
integers; this inspection is not an all-tier playthrough or a consumption-rate
or AI-balance certification.

The test world was saved as `fd1`, then Anno exited normally with code 0.

For the final View `b5af` / World `e375` candidate, the managed copy was restored
and reinstalled with 21 edits. Existing backup generations were retained, and
an independent read-only hash check confirmed that `fd1` was unchanged.
Installed and loaded native-module identity guards passed. Normal restart
produced one copied game process, and `fd1` loaded from the main menu.

The occupied eight-resident Pioneer house showed the original summary icon,
26% Food supply and the fully visible **Delivered food** caption; the supply
value subsequently declined. A newly built Food market showed all five food
icons plus Salt with consistent native backgrounds. The displayed food prices
were 45, and Salt was 38. Fish stock changed from the starting 50 to 49, and the
house's summary rose to 42% after a purchase. This demonstrates a basic supply
response, not decoded per-house buffer accounting or proof of no double debit.

Using gear → Load then reloaded `fd1` within the same process. Money returned to
499,843 and the added market was absent, consistent with loading the earlier
save. Selecting the occupied house again showed the original icon, 26% Food
supply and the fitting caption. Terrain displayed correctly, with no crash
observed. Both save-loading routes are therefore checked for this bounded
world.

The final post-check world was preserved as `fd2`. Independent read-only
inspection fully consumed its native ANNOADDON1 structure and confirmed its
internal save alias, 1024 × 1024 world, 20 bounded islands, valid basic/state
player IDs and one human-owned city. The preceding `fd1` save remained
unchanged. The final game process then closed normally with exit code 0.
Structural save inspection does not decode per-house food buffers or establish
long-session save compatibility.

## Remaining actual acceptance checks

1. Inspect the row in vacant houses and additional occupied-house states;
   retain the existing individual-needs layout. The occupied Pioneer caption
   and basic supply response have been observed on the final candidate.
2. Deliver and withhold individual foods. Compare decoded actual house supplies
   with the combined display and check that opening or refreshing the panel
   adds no purchase, stock debit or sale income. The observed market purchase
   does not replace this accounting check.
3. Play through all resident tiers and production-chain unlocks. Check actual
   promotion, tier-specific food needs, permanently absent zero-share foods and
   exclusion of locked foods. Native fixtures and live profile inspection do
   not replace this playthrough.
4. Inspect Consumer Goods and ship-loading icons at supported display sizes,
   including unrelated stands and artwork. The final candidate's Food market
   has been inspected in the bounded live run.
5. Extend save/load checks across longer sessions and further gameplay states.
   Both in-game and fresh-process loading of `fd1`, structural inspection of
   the preserved `fd2` save and normal exit already passed on the final
   candidate; these do not establish long-session save compatibility.

Long-session balance, complete AI production/consumption/trading, multiplayer,
tutorials, campaigns, other localizations and Food 0.6 plus World Settings are
outside the accepted scope. A bounded run with AI selected does not certify
AI food planning. Earlier Food 0.5 and combined-world evidence stays separate.
