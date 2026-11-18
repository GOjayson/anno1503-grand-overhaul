# Anno 1503 History Edition bugfix research

The optional **Bug Fixes** module corrects the King of Ore quest and reduces
the volume of 118 sound effects in each of the six languages shipped by
Ubisoft Connect.
The original international 1.04.02 release had more than 70 known or suspected
issues according to a contemporary FAQ. That figure describes the original
release. Surviving History Edition reports need to be checked against the
specific build and language. [Original FAQ](https://timhowgego.wordpress.com/anno_1503/technical/),
[Sir Henry's legacy list](https://www.mogelpower.de/forum/thread.php?thread_id=54227),
[Grand Overhaul beta scope](BETA_VALIDATION.md).

## Initial Dutch candidates

| Issue | Evidence | Gameplay check |
| --- | --- | --- |
| The King of Ore gives misleading instructions | The Dutch quest log, `Languages/Nl/Scenes/0200Single/Singleplayer14.htm`, twice instructs players to mine 170 tons of iron ore in each of six cities. The installed `Single_14.sze` script checks that each starting city has at least 170 tons in stock. The original walkthrough describes the same rule. [Scenario walkthrough](https://timhowgego.wordpress.com/anno_1503/scenarios/the_king_of_ore/) | The module corrects both entries. The corrected active objective appeared in the Dutch quest log on a fresh start. Scenario completion with transported ore remains untested. |
| Livestock and other effects dominate at close zoom | Taludas demonstrates the issue and provides an English/German sound fix. Bug Fixes applies the same measured gains to the original samples of every installed supported language. [Taludas's release and recordings](https://github.com/Taludas/Anno-1503-HE-Sound-Fix/releases/tag/v1.0), [independent player report](https://steamcommunity.com/app/2820110/discussions/1/4638240577738023122/) | Offline testing measured the quieter output for the installed Dutch files. In-game mixing and repeated playback remain separate observations. |
| The 500-inhabitant announcement repeats with Food 0.6 | The Dutch Food On session repeatedly created fresh own-city and other-city milestone events. With one city at 731 residents, its next milestone fell from 1,000 to values just above 500 before the game emitted another 500 event. The engine's city supply-warning routine indexed a table for goods 26–40 with Game Meat (24), whose fourth counter overlaps the saved milestone. Bread (25) and Butcher's Meat (45) also fall outside that table. | Bug Fixes bounds the native table access when installed with Food 0.6. The change applies to all languages and preserves the original voice recordings, population milestones and supported table entries. A save already affected can still produce a catch-up announcement. |
| In-game help may misstate building and resource behavior | Dutch help files `Kirche.htm`, `Kontor.htm` and `Erzvorkommen.htm` describe chapel upgrades as range-limited, imply that warehouse upgrades change capacity, and exclude polar islands from iron distribution. A Steam guide reports different behavior for each. [Steam guide, services, mines and storage](https://steamcommunity.com/sharedfiles/filedetails/?id=3738927701) | Check a chapel outside church range on the same island, measure storage before and after upgrading a warehouse, and inspect polar islands for usable iron on stock maps. Change only statements that disagree with observed behavior. |

## Localization and scene audio reports

| Issue | Evidence and next check |
| --- | --- |
| Watchtower and large city gate show inconsistent unlock tiers | The Dutch `Languages/Nl/Texte.dat` lists Settlers for the watchtower and Citizens for the large city gate in `BAUMENU_MILITAR`. The `BAUMENU_MILITAR_ADDON` section reverses those two tiers. A Steam guide reports that the watchtower unlocks at 50 Settlers and the large gate at 200 Citizens. Check both menus and the actual unlock thresholds in a clean game before patching the add-on strings. [Steam guide, building unlocks](https://steamcommunity.com/sharedfiles/filedetails/?id=3738927701) |
| Silent add-on scenario narrator | One German Steam player reports that subtitles appeared without speech and converting IMA ADPCM WAVs to PCM restored narration. All 124 Dutch WAVs in `Languages/Nl/Scenes/0201SingleAddOn` already have PCM headers. Reproduce on a German copy before considering a conversion for that locale. [Narrator report and workaround](https://steamcommunity.com/app/2820110/discussions/1/586188051673259602/) |
| Missing sound effects in certain add-on scenes | A separate report describes a workaround for sounds referenced directly by scene files. The installed Dutch `021_S30.DDF` references two present WAVs, so that scene is a candidate for a bounded playback test. [Scene audio report](https://steamcommunity.com/app/2820110/discussions/1/595135824845118843/) |

## Gameplay and engine investigations

| Issue | Evidence and next check |
| --- | --- |
| Fishery reportedly accepts shore placements where the fishing boat cannot return | The guide describes a boat disappearing without delivery when the dock lies over land. Local stock building data confirms the player fishery is a 3×4 coastal producer, and its placement masks match the inspected Food build. The files establish the footprint and intended coastal restrictions. A live comparison is needed to check whether the game accepts the failing spot and whether the boat returns. Compare two nearby placements on the same coast with road access and spare warehouse capacity. [Steam guide, fisheries](https://steamcommunity.com/sharedfiles/filedetails/?id=3738927701) |
| Pirate ships lose cannons after reload | Grand Overhaul's native fixtures reproduced that the game equips new pirate ships with up to 18 cannons and then caps them at six on load. The neutral merchant loader has an eight-cannon cap, which only merits a fix if ordinary gameplay can create above-cap ships that should retain their equipment. Verify pirate counts in a live before/after save and establish the engine's intended limits before changing either cap. [Faction activity validation](WORLD_FACTION_ACTIVITY.md#validation-at-this-development-stage) |
| Quicksaving during defeat leaves the player unable to act after reload | An HE player repeatedly reproduced loss of player control by quicksaving when their last ship sank. Reproduce with disposable saves, then check save timing and defeat state in the loader. [Player reproduction](https://www.speedrun.com/anno_1503/forums/plthl) |
| Iron deposits or markers appear missing in a fresh game | A player discussing modern ports reports missing iron and another suggests saving, returning to the menu and reloading. The exact affected edition is unclear. Compare the same stock map before and after reload to distinguish a display problem from altered deposits. World Settings already has a mineral-symbol repair for its own visibility path. [Player discussion](https://www.reddit.com/r/anno/comments/1w12svy/i_travelled_back_in_time/), [World Settings validation](WORLD_VISIBILITY_VALIDATION.md#060-dev8-mineral-symbols-and-in-game-file-loading) |
| Buildings or units sometimes ignore clicks | Two HE players report difficult selection. Record resolution, UI scale, zoom and display mode to isolate whether hit testing is offset or depends on the selected sprite. [Player reports](https://www.reddit.com/r/anno/comments/1804edb/anno_1503_history_edition_building_unit_selection/) |
| Trade-route entry fails | A Steam player on Ubuntu reports that clicking a warehouse in route setup selects the building without adding a stop. Check on the supported Windows build before investigating the route UI. [Player report](https://steamcommunity.com/app/2820110/discussions/1/4700161643034801128/) |
| Endless games return to the menu during loading | Players report the same symptom, with one tracing their case to an installation rediscovered by Ubisoft Connect. Check whether it reproduces from a verified clean install before attributing it to scenario loading. [Endless-game report](https://www.reddit.com/r/anno/comments/1q1aktc/anno_1503_endless_game_wont_start/), [existing-installation report](https://www.reddit.com/r/anno/comments/uu4jhn/anno_1503_history_edition_cannot_load_continuous/) |
| Infernal Triad can get stuck when objectives are completed out of order | The original campaign walkthrough describes a possible softlock if Peles's fortress is destroyed indirectly before the other objectives. Test direct and indirect destruction in both orders on HE before considering a script change. [Campaign walkthrough](https://timhowgego.wordpress.com/anno_1503/campaign/infernal_triad/) |

## Previous fixes and workarounds

- History Edition launched with an optional coastline-rendering correction and
  a fix for the unit-count crash associated with the FIG limit.
  [Ubisoft launch notes](https://www.anno-union.com/devblog-anno-1503-history-edition-2/)
- Updates 1.1–1.3 covered F6 audio loss, aristocrat house multi-placement,
  options background stretching, incorrect trader stock, a resolution-dependent
  Nova Fora blocker, repeat monument videos, duplicate multiplayer lobby colors
  and stability fixes.
  [1.1](https://www.anno-union.com/updates/game-update-1-1-1503-he/),
  [1.2](https://www.anno-union.com/updates/game-update-1-2-1503-he/),
  [1.3](https://www.anno-union.com/updates/game-update-1-3-1503-he/)
- Classic patch 1.05 lists fixes for harvests skipping fields, adjacent gem
  mines, units getting stuck, and crashes tied to doctor's buildings or
  warehouses near the map edge. Any similar HE symptom needs a fresh reproduction.
  [Classic patch notes archive](https://www.annoinfo.de/Anno_1503/patchnotes.html)
- The historical Moorish music path typo is absent in the inspected install.
  `Data/music.dat` uses `races\moorish\*` and the corresponding music folder
  exists. [Original music report](https://timhowgego.wordpress.com/anno_1503/technical/)
- Two players reported that disabling AMD Radeon Image Sharpening fixed purple
  rivers in fullscreen. This is a graphics setting workaround.
  [Fullscreen report](https://steamcommunity.com/app/2820110/discussions/0/4522260579672827419/)

## Implementation and validation

Bug Fixes is disabled by default and uses the common installer journal for
installation and restoration. It verifies the stock quest and scenario
fingerprints for each installed supported language. The two corrected quest
entries preserve the surrounding markup and line endings. Ubisoft Connect's
installation manifest identifies the English, French, German, Italian,
Spanish and Dutch assets. [Installer instructions](INSTALLER.md#choose-features-and-folders)
· [Ubisoft language announcement](https://www.anno-union.com/devblog-anno-1503-history-edition-2/)

Dutch is the live-checked language. For the other five languages, the authored
text and replacement logic are covered by fixtures. The installer checks the
actual local files against Ubisoft's manifest fingerprints before patching.
The multilingual release produced the same Dutch quest bytes as the live
test and passed installation, startup file verification and exact
restoration on a separate Dutch copy. The earlier Dutch installation also
passed startup file verification with the updated installer.

Before adding sound attenuation, an independent Dutch copy passed check,
install, byte-for-byte restoration, reinstall and startup file verification.
The installation journal contained one file, `Singleplayer14.htm`. Both
objective entries changed. The scenario and all five livestock samples
matched their original fingerprints throughout the cycle.
The standalone Ubisoft handoff reached the managed copy's main menu. A fresh
run of **De ertskoning** under the disposable profile showed the corrected
active objective in the **Doelstellingen** panel opened through F1 and the
checkmark. The full text rendered across two lines.

> Zorg dat je binnen de tijdslimiet in elk van je zes startsteden minstens
> 170 ton ijzererts op voorraad hebt.

The completed objective has the same wording in the installed HTML. Live
validation covered the active quest at scenario start.

### Quieter sound effects

The installer attenuates 114 clips by 10 dB and four by 20 dB in each
installed language. The four are `Axt Hit Holz.wav` and the three
`Pferd wiehert` clips. All six language packs contain the 118 target files
according to the Ubisoft Connect manifest. The installer checks the original
WAV fingerprints and derives each quieter clip from the player's own assets.
Market voices and the localized musket recordings retain their original
language, layout and duration. [Taludas's v1.0 release](https://github.com/Taludas/Anno-1503-HE-Sound-Fix/releases/tag/v1.0)

All 118 Dutch originals matched the manifest. An offline comparison of the
generated WAVs verified that each reduction was within 0.001 dB of its target
and that all WAV parameters and lengths matched. A Dutch managed copy passed
installation, startup file verification and byte-for-byte restoration of the
118 WAVs and the quest file. All of these checks ran without launching Anno.

In the earlier five-clip pilot, the stock Dutch Trade and Diplomacy tutorial
ran on an isolated copy with two
sheep farms in view. Its process audio capture contained only dither, so it
provided no in-game loudness measurement. The five trial WAVs were restored
afterward and matched their original fingerprints.
