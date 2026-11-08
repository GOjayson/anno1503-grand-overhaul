VENETIAN TOWN DATA AND AUTOMATED EVIDENCE
========================================

The earlier toggle retained a native Venetian player/controller but did not
place a Venetian island. Easy's existing map-bound town was removed because
its absolute coordinates could put it on a newly generated foreign island.
The Medium and Hard stock scenes contain no serialized Venetian town.

This revision extracts Easy's actual island28 (184,288,80,80) and its Mercoli
town. The private SCP changes the island prefix to(0,0,80,80,0) and the town
anchor from(212,321) to its island-local(28,33). Every nested terrain and city
byte remains exact. All73 production-entry anchors are already island-local.
The native named profile contains only VOLK=VENECIA, ALIAS=VENEZIA01 and STADT2.
It imports no player HEAD, controller COMP, ships or unrelated player state.
Easy's original STADT2 is removed from the scene before this single SCP town
is imported. The exact selected preset controller remains intact for all
three presets, including Medium and Hard.

The actual History Edition AMD64 CEB00 importer selects native player5 by
VENEZIA01. Native PlayerLoad adds the planned island rectangle origin to the
town anchor, and native production-entry loading adds it to building anchors.
The strict loaded-world certificate requires exactly one Venetian city on the
dedicated faction2 island, type16/culture12, the correct alias, native main
player-table membership and the same loaded world. Other foreign city owners
remain rejected. One fixed80x80 native town is available in all island-size
modes; the template is never enlarged or resampled.

generate_venetian_assets.py verifies fingerprinted original source files and
reproduces the new town asset. Its80-tile loading dummy already exists in the
stock game and marked copy. The exact27289-byte e64de5cd... file has bounded
80x80 geometry, climate2, complete tile coverage and empty production tiles.
It is a required copy input and is never introduced, backed up, overwritten
or removed by this revision. support/package_world_assets.py hard-pins the
new town payload and required stock dummy fingerprints, validates bounded
format and verifies the town source-to-copy relationship.
venetian_assets.json records source provenance, one installation target/payload
name and the separate required-existing-input policy.

Automated results:
-12 compiled stock scene/controller preservation cases and23 rejections.
-Four actual native x64 alias-selection cases at two image bases.
-Ten native anchor-relocation cases and730 native building-coordinate cases.
-Two synthetic save-inspector positive cases and13 malformed-save rejections.
The scene fixture compiles actual special_scene.inc and the exact production
Venetian owner helper. File/controller/native allocation/construction boundaries
are explicit. These tests do not launch Anno and do not establish gameplay.

inspect_venetian_save.py checks a real saved world against the selected preview
island: native owner5/type16/VENECIA/VENEZIA01, one town, correct relocated
anchor, exact HEIGHT terrain, all73 original local production-entry anchors,
serialized SUSPEND=0 and absence of foreign towns on that island. It does not
claim current controller activity, trading or later behavior. Those require
separate live diagnostics and observed game checks. Save/reload of this changed
runtime remains pending until a separate actual-game report records it.

Earlier package proofs remain historical and unchanged. No classic executable
address or i386 DLL is used by these new proofs.
