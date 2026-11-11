# Historical installer guidance

This page preserves the earlier local shortcut report and 0.6-era world-setup
guidance exactly as it appeared in the installer document. Its menu names,
exploration rules, preset format and acceptance statements describe those
historical builds, not the current beta. Use [the current installation guide](INSTALLER.md)
for beta setup and world configuration.

On the validated local installation, the existing **Anno 1503 - World
Settings** desktop shortcut now uses the repository's production
installed-copy launcher and the current installed profile. Its previous
shortcut was retained in a private backup. Exact shortcut readback passed;
updating it did not launch a second game. This is a local shortcut update,
not a shortcut automatically installed by every public checkout.

## Configure a world inside Anno

Starting a supported endless game opens the expanded World Settings screen.
Use **World**, **Players**, **Starting**, **Presets**, **Islands** and
**Visibility** to choose the world; the Starting heading remains **Starting
options**. The preview area, displayed seed, regeneration and Start remain
visible. Terra incognita covers the preview area.

Experimental 0.6.0-dev.1 adds the following choices on **Visibility**:

- **Unexplored (terra incognita):** hide undiscovered islands. Native contact
  reveals a whole island, which stays remembered after ships leave. Its setup
  preview, island metadata, start badges and resource summaries are concealed;
  preview clicks cannot inspect or select an island. Entering this mode clears
  a preceding preferred island. A preferred climate and balanced starts remain
  available; an incompatible saved manual-island choice is refused.
- **Geography revealed:** show island locations initially. This is the default.
- **Fully explored:** begin with every island discovered and its fertility
  information unlocked.
- **Enemy activity:** independently choose **Strict line of sight** (default)
  or **Reveal all activity**. Strict uses a fixed 48-tile radius around
  controllable human ships and owned settlements' building-anchor rectangles.
  Activity outside current vision becomes hidden again; remembered island
  geography remains. Reveal all activity removes this activity range limit.

The visibility policy is stored with the world save. Activate the matching
World Settings runtime before loading that save, including after a fresh
launch or restoration/reinstallation. These 0.6 features remain experimental.
R8 World-only automatic startup and certified native-save reload passed;
the user confirmed smooth camera movement and working visibility in the
requested large-island/village-range sample. This does not establish FPS,
every interaction path or fresh Terra generation. Food remains optional.
Both profiles passed build, isolated scene and production install/restore
checks; Food + World actual visibility gameplay was omitted at the user's
request and is not a publication requirement for this iteration. See the
[visibility validation record](WORLD_VISIBILITY_VALIDATION.md).

**Map seed** accepts decimal values from 0 to 4294967295. **Copy seed** puts
the displayed value on the clipboard. The same seed and the same settings,
with the matching generator version, reproduce the map preview. Regeneration
chooses another seed and clears an island selection from the preceding map.

**Climate balance** favours temperate, tropical or polar islands while keeping
the required cultures, climates and resources. **Layout style** selects even
spacing, grouped archipelagos or a central ocean. Existing overlap, map-border,
minimum-spacing and essential-resource checks still apply; an impossible
configuration is blocked with an explanation.

With Geography revealed or Fully explored selected, click any island's land
on the preview to open **Islands**. Its details show
climate, dimensions, the catalogue's fertile-land estimate, planned crops and
minerals, occupants and nearby ordinary-island resources. The fertile-land
estimate is not proof of accessible construction space or mining access.
The white outline identifies the inspected island; inspection does not change
the starting position. Native, Pirate and Venetian islands can be inspected.

Under **Starting options**, choose a preferred climate. With a revealed
preview, alternatively inspect an ordinary island and choose **Use inspected island as preferred starting
position**. The human fleet starts in checked water nearby; the player builds
the settlement normally. Native, Pirate and Venetian islands are not eligible
starting islands. **Use automatic starting position** clears both preferences.

**Balance starting islands for human and AI players** requests comparable
ordinary islands for the human and selected AI opponents. Choose close
neighbours, balanced separation or distant rivals. A revealed preview displays
**S** for the human and **1–3** for ordinary AI starts, with a summary on
**Islands**. Terra incognita withholds these assignments and the summary.
A preferred human island/climate remains a constraint, and an impossible
combination is refused. Fair starts do not enable a smarter-AI module or add
player slots.

On **World**, **Resource distribution** keeps original assignments, spreads
resources or favours specialised regions. Spread favours separation for each
resource; Specialised regions favours grouping around a seeded compatible
region. Redistribution preserves each resource's world count from the selected
fertility level while retaining native climate and ore-occurrence constraints.
Per-island availability can change, but saturated fertility or native/climate
constraints can leave modes with identical assignments. Native/special-faction
resources stay unchanged.
**Guarantee basic resources near every
player's start** can additionally provide grain, flax, potatoes, iron and salt
on ordinary islands within `max(128, worldSize / 4)` tiles of each participant's
starting island. This optional guarantee can add resources above fertility
abundance. It does not promise the entire Food-overhaul production chain.

Select **Custom cargo on every trade ship** to enter tools, wood and food in
tons. Each good occupies separate 50-ton holds. Small trade ships have four
holds and big trade ships have eight, so the same custom cargo must fit every
trade ship in the selected fleet. Warships retain their cannon equipment.
Leaving this option unchecked keeps the fleet's existing supplies.
**Enable disasters** controls the inspected native endless-game disaster
option separately from Pirates and Venetians.

On **Presets**, enter a name and choose **Save current settings** after the
preview is ready. Choose an existing preset and **Load selected preset** to
restore every world option and its seed. Replacing a named preset requires an
in-game confirmation. Presets use versioned, bounded text files in the managed
copy's `WorldSettingsPresets/` folder. They remain during restoration and are
refused when their generator fingerprint differs. Version-3 presets contain
all 29 settings, including map visibility and enemy activity. Earlier-schema
presets remain on disk and are refused rather than silently converted.
Feature-profile files still
contain installer choices only.

The 0.6 visibility choices have a separate
[validation record](WORLD_VISIBILITY_VALIDATION.md) covering automated checks
and r8's bounded World-only startup, reload and user camera/visibility sample.
Broader gameplay coverage is not implied. The 0.5 additions retain their original
[validation record](WORLD_FAIRNESS_VALIDATION.md). Earlier seven-option
acceptance remains in [World options validation](WORLD_OPTIONS_VALIDATION.md).
Seed reproducibility covers generation choices and the preview; AI decisions
and a played world's later events can differ.
