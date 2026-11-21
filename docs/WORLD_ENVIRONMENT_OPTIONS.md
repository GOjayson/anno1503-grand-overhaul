# Island counts, sizes, variety, rotation and disasters

## Current source update: separate climates and island sizes

The in-game Islands page now treats the six engine climates separately:
**Polar, Tundra, Northern, Prairie, Jungle and Steppe**. Each climate has its
own minimum and maximum island count, plus independent minimum and maximum
counts for small, medium and large islands in that climate. Set a minimum and
maximum to the same number for an exact count. A range of 0–128 leaves a limit
unrestricted; the existing essential-resource checks still require at least
one island of every climate.

Size refers to the template's longest dimension: small is 64 or 80 tiles,
medium is 128 tiles, and large is 256 tiles. These limits refine the overall
Island size choice on Map; choose **Mixed** to allow every size. The Polar
catalogue has no large template, so a positive minimum for large Polar islands
cannot be satisfied. Large Prairie templates exist in the source catalogue,
but the reviewed ordinary-world eligibility rules exclude them; a positive
large Prairie minimum is also refused. Counts include native cultures, Pirates and Venetians.
Rotation changes orientation, not size class.

The planner rejects conflicting ranges, counts that do not fit the total,
unavailable eligible template sizes and choices that would lose essential
resources. A valid mathematical range does not guarantee enough physical map
space: world dimensions, spacing, cultures and special factions still apply.
Variety preferences may relax during bounded retries; climate and size limits
remain hard constraints.

The settings ABI retains its original 176-byte prefix and appends the new
limits, giving 368-byte settings and a 6,016-byte preview snapshot. New presets
use version 6. Supported preceding presets migrate in memory with unrestricted
new limits; their files and the preceding pairwise climate constraints remain
preserved. Imported paired constraints are shown in the menu and can be
removed with **Clear old paired limits**, without changing the independent
limits. Reusing a seed across a generator change does not promise the same
islands.

The historical game checks below apply to the preceding environment build.
They do not establish live acceptance or long-session stability for the new
independent climate and size limits.

Offline validation for this source update compiled four AMD64 candidates:
World-only, preserved Food 0.5, Food 0.6 and Food 0.6 with the population
announcement fix. Each retained all 43 immutable imported compiled inputs and
verified its existing nine hook sites and 173 engine edits. The generator
change adds no engine patch addresses. All four compiled DLLs passed 13
isolated planning checks each, including exact six-climate/18-size counts,
seed replay, resources, balanced human starts and invalid-request rejection.
Matching settings produced identical plans across the four profiles. These
checks call local generator exports; they do not activate hooks, stage a scene,
run AI players or start Anno. Actual menu rendering, world loading and save/reload
checks for this update remain pending. Existing installed copies and releases
have not been updated by these checks.

The full local regression run completed 928 tests: 923 passed and five were
skipped. A fresh public-input build with the reviewed-runtime guard enabled
also reproduced the exact World-only candidate. Audit monitoring refused
access to private baseline/runtime stores and recorded zero access attempts;
previous input caches were preserved.

## Preserved environment build

World Settings 0.8.0-dev.4 adds these choices inside Anno. This is a development
candidate: compilation and native fixtures are separate from actual game
loading, rendering and save/reload acceptance. All prior runtimes and packages remain preserved. A corrected activation
transaction counts all eight additional disaster hooks and rechecks their
complete instructions and callbacks before reporting engine readiness. The
first world-load test exposed a second handoff problem: scene completion ran
before player settings were committed and cleared the pending disaster policy.
Dev.4 retains those choices until the certified player-start scope completes;
failed or stale scopes cannot commit them.

## Islands

The Islands page offers Allow repeated templates, Prefer unique templates and
Prefer varied island shapes. Preferences operate within the eligible size,
climate, culture, special-faction and resource pools. They are soft preferences:
the bounded planner can fall back to ordinary selection while retaining hard
constraints. A shape preference cannot create a missing eligible template.

Separate minimum and maximum fields cover Polar (polar/tundra), Temperate
(north/prairie) and Tropical (jungle/steppe). Counts include every placed island,
including cultures, Pirates and Venetians. Zero minimum and maximum 128 retain
automatic allocation. Each group must permit at least two islands because all
six native climates and essential resources remain required. Impossible ranges
are refused. A bounded search failure asks for regeneration; it does not prove
that no mathematical arrangement exists.

Random rotation is optional and deterministic for the seed and settings. It
uses 0, 90, 180 or 270 degree turns of **256 save-safe ordinary templates**.
Native towns, Pirates, Venetians and templates carrying production/scenario
state keep their original orientation. Rotation does not change dimensions,
island count, resource masks or the layout random-number stream. Paint and
preview selection use the same rotated coastal projection. Terra incognita
still conceals the preview and its summaries.

Rotation transforms terrain vertices, texture orientation, fertility cells,
landscape and river footprints, mine anchors and natural occurrences. It
preserves the complete padded height boundary, including nonzero edge vertices.
The codec was checked on all 269 ordinary templates. Thirteen have nonzero
first-edge vertices that rotation can move to the padded end boundary; the
native save format omits that boundary. They remain unrotated, so saving and
reloading cannot discard those values.

Selected derivatives use exclusive temporary files only inside the managed
copy. Original islands are never edited. Cleanup checks file identity and hash;
it preserves a file that has been replaced, modified or hard-linked.

The [complete installed-catalogue audit](WORLD_ISLAND_CATALOGUE.md) found all
443 original loose game templates already represented, plus the existing
private Venetian town. Their 444 distinct files contain 347 distinct coastal
shapes. Another 61 shapes exist inside scenes but carry scenario state; this
version does not activate them.

## Disasters

Every native automatic type has its own checkbox and frequency. The master
checkbox disables all five while preserving individual choices. No new random
event scheduler is introduced. An early investigation incorrectly classified
drought as scripted-only; tracing the actual History Edition instructions found
its automatic island trigger as well.

| Type | Rare / Normal / Frequent | Severity |
| --- | --- | --- |
| Fire | Approximately half / native / double native random chance | Normal only |
| Plague | Approximately half / native / double native random chance | Normal only |
| Volcanic eruption | Twice / native / half native waiting interval | Half / native / double new-event duration |
| Earthquake | Twice / native / half native elapsed threshold | Half / native / double new-event duration |
| Drought | Twice / native / half native elapsed threshold | New native extent 3 / 6 / 9 |

Frequency still depends on native prerequisites and simulation progress. It
does not promise a fixed real-time interval. Eruptions require a volcano.
The chance adapter reuses the native random word and does not advance the RNG.
Fire and plague severity is disabled in the menu because a safe independent
severity control has not been established. Existing events are not resized.

The policy is attached to a certified world identity. A separate 64-byte
WSDISAST root payload is authenticated by the existing WSCHART checkpoint
checksum. The WSCHART1 format, reserved fields and exploration rules are
unchanged. Unknown, malformed, duplicate, detached or cross-world policies are
refused. Old saves without the extension use native Normal behavior and cannot
inherit a different world's policy. Global policy persistence is covered by
Windows file fixtures. Preservation of the remaining duration/extent of an
already active disaster through the game's own loader is not yet established.

## Compatibility and checks

In the preceding environment build, settings extend the unchanged 132-byte prefix to 176 bytes. Preview islands
extend their unchanged 40-byte prefix to 44 bytes; the full snapshot is 5,824
bytes. Named presets use version 5. Exact preceding version-4 and version-3
generator identities migrate in memory with the new choices defaulted; their
files are retained. The exact preceding dev.3 version-5 identity also loads
without changing its 43 choices or rewriting the preset. Unrecognized
identities are refused.

World-only and Food + World use separate native fingerprints and runtime
builds. Food data and the 43 imported compiled inputs remain unchanged. Food
gameplay is not being retested at the user's request. These additions do not
raise the supported ordinary-AI choice above three.

Automated evidence includes all-template metadata checks, compiled C versus
independent Python rotation comparisons, exclusive Windows-file fixtures,
native mesh texture instructions for both exact hosts, disaster scheduler and
damage instructions, actual Windows unwind checks, and preset/preview privacy
fixtures. Those checks cannot establish correct live cliffs, rivers, mineral
placement, navigation or long-session disaster rates. Bounded game acceptance
is recorded separately below.

The full dev.2 suite completed 424 methods: 423 passed and one Windows
symbolic-link method was skipped. After the save-safe whitelist refinement,
all 98 targeted dev.3 methods passed with zero skips, including 768 compiled
rotation derivatives and exact metadata/source checks. The portable installer
suite passed 77 methods with three privilege-related symbolic-link skips.

Dev.4 passed all 145 targeted methods with zero skips, including three compiled
scene-to-player lifecycle checks. Three matching dev.4 builds per native
profile passed the closed-source and PE audit. Six actual compiled-runtime
staging fixtures passed across both profiles and all layouts. Both planners
reproduce the user's captured Environment1 preview exactly, including all 43
options and 24 island rows. These fixtures do not run Anno.

World-only restoration/reinstallation passed with all 53 named saves, seven
presets and preceding backups retained; 63 backup generations now remain. The
updated desktop shortcut was promoted with its predecessor archived.

## Actual dev.4 game checks

Automatic activation passed in two independently launched, verified game
processes. The in-game Environment1 preset reproduced its preceding captured
preview exactly: all 43 choices, 24 island rows, ten nonzero rotations, and
Polar/Temperate/Tropical totals of 6/8/10. World creation passed with zero AI
opponents and no factory, hook or player-profile errors. Owned temporary island
derivatives were removed after loading.

The user inspected islands, rivers and mineral symbols and reported correct
appearance. Native checkpoint `we1`, the in-game reload/resave `we1r`, and the
fresh-process reload/resave `we2` all passed independent disk inspection:

- The same native world identity and authenticated disaster payload persist.
- All 24 island boxes/climates, crop masks and positive physical mineral masks
  match the actual preview.
- Every saved height vertex and texture cell matches the independently rotated
  exact source, including the ten rotated islands. Differences are zero before
  and after both reload paths.
- All 53 pre-existing named saves remain byte-exact. Environment1 and the other
  presets remain preserved.

The global disaster choice used Fire Frequent, Plague off, Volcano Rare/Severe,
Earthquake off and Drought Frequent/Mild. It persists exactly in all three
checkpoints. This run does not establish long-session event rates or remaining
duration/extent retention for an already active disaster. It also does not
establish mine construction and navigation on all 256 rotatable templates.
Food was built and checked automatically, without a new Food gameplay run.

| Frozen evidence | SHA256 |
| --- | --- |
| World-only runtime | `5fa1a3f72ca8432a4052bdd80789a6e1f60957daca0efd2633d1cec839b3673a` |
| Food + World runtime | `e197c8bffcad870df3491c7065858914d8ffafa1b20d130a51c402219216e2b3` |
| Dev.4 targeted 145-method suite | `48a0a7ccc4dd882b55faec9df0266e7a0ba80606b12f09dd243c359db2ec22b8` |
| Six-build post-pin source/PE audit | `f5a2a1f946bc01a0be4581b30b273edeca05276dd031a19a2321bdb55b7f596f` |
| Six actual-runtime staging fixtures, without Anno | `2efe0e7ede99a6d171ff503cb61fd38eeed1ac0d0f4fc85850a06b7291564d87` |
| Actual Environment1 preview | `8c6e787c3010b0a1a398f765c6b13f08765ffc2cf2c99b30ded6cf2b05bac74c` |
| Initial `we1` native save certificate | `f464c8f213f33431aee027f60d085b36465bf55bdc4a0e18bfe3defcd6a7122c` |
| In-game reload `we1r` native save certificate | `72c6b7d025e62fd9162ff95bc4b6766661280ed83821b0db078676fa93d1b5ae` |
| Fresh-process reload `we2` native save certificate | `be1bbce0f325499becfa508e9655a9584ba14aa57f86c86ab8b980d507d7f2d8` |
| Combined bounded live acceptance record | `b669d1701b81a4c14635739ae064808c46112f1a9cdc27edb785c029f78a0432` |

The native files, saved checkpoints and private evidence remain in ignored
local storage. Only mod source, tests and this scoped evidence record are
published.
