# Installed island catalogue and coastal variety

This audit reads the installed History Edition assets without running the game
or changing original files. It separates playable island templates from loading
placeholders, scenario state and multiple files with the same coastline.

## What the installed game contains

| Source | Audited result |
| --- | --- |
| Loose `Scenes/Islands` SCP files | 464 files: 443 full island templates and 21 loading placeholders with no `INSEL5` island. |
| Current World Settings catalogue | 444 full templates: all 443 original templates, with 15 pirate templates addressed through the preserved ownership-repaired private copies, plus the existing extracted Venetian town. |
| Historical loose files | One valid `.scp.bak` has an already represented coastline. One `.scp.bug` has an invalid container header. Neither is an active SCP template. |
| Endless, multiplayer, campaign, single scenarios and tutorials | 55 installed scenes, including 50 under the installed Dutch language directory. They contain 669 embedded island records. |
| Native scene index | All 55 `Scenes.cach` entries resolve to those same 55 scenes exactly once; the index contains metadata, not additional embedded islands. |
| Additional embedded coastlines | 86 embedded instances represent 61 distinct coastal shapes absent from the current catalogue. These are not automatically safe standalone island templates. |
| History Edition resource archive | The complete `ahe/a2he0.rda` index contains 2,044 shader, UI, text and configuration entries; no SCP, SZE or island entries. |
| `Data/Data.zip` | All 15 entries were listed; none is a scene or island template. |

The resource archive was checked using its actual V2.2 header, bounded block
chain and directory records, following the [published extractor's format description](https://github.com/metacrito/rda).
The audit covers the assets installed on this machine; it does not infer the
contents of uninstalled languages, editions or user-created maps.

No missing ordinary loose template needs to be unlocked. Existing size, climate,
culture, special-faction, fertile-land and packing constraints can make a
catalogued template ineligible for a particular world. Large strict selection
also deliberately restricts the available size within each matching group.

## Why different island files can look alike

The 444 catalogue files have 444 distinct complete-file hashes, but only **347
distinct coastal masks**. Native settlements, resources and other content can
differ while the outline stays the same. Comparing filenames or dimensions
alone therefore overstates visual variety.

The authored `island_shapes.h` records one small group ID per catalogue entry,
in the original 444-entry order. Its derivation reads every exact source file,
checks its SHA256 and dimensions/climate, and assembles the complete native
`HEIGHT` grid. Height values of at least 48 form the coastal land mask. The
canonical mask includes dimensions and considers all four rotations and their
reflections equal. It does not classify resource richness, buildability,
navigation or settlement quality.

For these original templates there are also 347 distinct masks before that
canonicalisation: the repeated shapes generally retain the same orientation.
The equivalence rule prepares variety selection to recognise rotated versions;
it does not rotate an island in the engine.

The new variety modes can distinguish exact-template reuse from coastal-shape
reuse. Preferences still obey required cultures, special factions, resources,
climate limits, selected size and physical packing. The catalogue-wide total of
347 shapes is not a promise that every configuration has 347 eligible choices.

## Additional scenario islands

The 61 additional unique coastal shapes comprise:

| Dimensions | Unique shapes |
| --- | --- |
| 64 × 64 | 9 |
| 80 × 80 | 23 |
| 128 × 128 | 14 |
| 256 × 256 | 14 |
| 400 × 400 | 1 |

They occur in campaign, single/add-on scenarios, add-on endless worlds,
tutorials, multiplayer and one original endless scene. Embedded records can
carry discovery, locked-area, town association, production and island-event
state. Seven first representatives include a `LOCKED` record. Their graphics,
river, mine, occurrence and ownership coordinates also belong to the source
scene. Copying these records unchanged into endless generation would import
state that has not been certified for a fresh world.

The 60 shapes no larger than 256 are candidates for terrain-only extraction,
not approved additions. The 400-square shape additionally needs a matching
loading placeholder and proof through the current normal-engine loading path;
its presence in an add-on scene alone does not establish that compatibility.
All 61 candidates have complete, non-overlapping height/graphics grids and a
correctly sized fertility array. All also have discovery, town-reference,
wildlife and island-event records; these checks do not certify removal of their
scene state. The 60 smaller candidates have matching installed loading dummies.
The current catalogue, source data, private island payloads and historical
backups remain unchanged. No extra scenario island is activated by this audit.

## Validation and reproducibility

Nine catalogue test methods passed with no skips. They cover rotation/reflection
equivalence, different same-size coastlines, height threshold boundaries, tile
partitioning, malformed/overlapping/incomplete grids, exact source provenance,
changed or substituted native files and authored group tampering. Every one of
the 444 real inputs was checked against the production group table.

A separate existing native-record parser independently inspected every
catalogue entry. Its complete-file hash, geometry, climate, height-grid hash,
exact coastal hash and canonical coastal hash match the public validator for
all 444 entries. These are automated data checks. They do not establish native
loading, harvesting or pathfinding for a newly extracted or rotated island.

The public read-only checker accepts explicit source roots:

```text
python -B tools/check_island_catalogue.py --source-root <checked-game-copy> --source-root <preserved-private-island-assets>
```

The second root supplies the existing private pirate and Venetian data copies;
it is independent of whichever private AI runtime is currently installed.

| Evidence | SHA256 |
| --- | --- |
| Preserved compiled catalogue | `5a41a82a47d314a89fb774a74945b3f7a2960083f66b17a055ff17abb48d30d4` |
| Authored coastal group header | `96c56825b64f23793c41fe5b189065515b3196a4bc0ee10891a63745471ca0fd` |
| Local full-game inventory: `island-full-catalogue-v1-20261111.json` | `87e820b83935218312747bf5c5e4f6ba16fa4ce9fbfe6de25abe456ecf451640` |
| Local public-validator tests and independent crosscheck: `island-shapes-public-proof-20261111.json` | `5f73df2a862907d87c3a0012f0e56147833b5ab133f7cb2ca92d6b37a1c0ec92` |
| Local scene-index coverage: `island-scene-cache-coverage-20261111.json` | `88596dbe08f1cef1fdc7b48e34fbf752a28f829db5d2d85e23cba5a5bb1ef460` |
| Local extraction feasibility: `island-embedded-extraction-feasibility-20261111.json` | `fbac1318ff42930e73a092b65aef91041783dffe69091914466ec98694836743` |

Native islands, scenes, private reports and extracted game data remain in
ignored local storage. The public repository contains only source, the small
derived group table and documentation.
