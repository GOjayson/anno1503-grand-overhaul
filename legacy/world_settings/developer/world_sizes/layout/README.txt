DEV7 selection and balanced-layout proof

Run build_fixture.py with Python and the bundled Zig compiler, then
test_layout.py, then make_review.py. The compiler produces only an isolated
AMD64 Windows DLL under _build. This is not the game's32-bit runtime DLL.

The fixture compiles the exact production balanced_layout.inc,
selection_policy.inc and world_ship_reserves.h, the current444-template
catalogue/faction arrays and56-byte settings header. It accesses no Anno
process, hook, native loader, scene files, game copy or backup.

SelectPlan reproduces only the selection prelude to supply real template
inputs to the production helpers. It does not execute runtime fertility,
scene rewriting, native tWelt creation or game play. Those require separate
runtime tests and live game acceptance. Successful helper geometry does
not establish an engine limit or prove a world will load in Anno.

The accepted dimensions in this release are256,512 and1024.2048 is rejected
before planning because the inspected native island-lookup buffer is too
small, as documented by the separate world-size engine evidence.

Strict Big retains the existing largest-available-per-climate/exact-native-
culture catalogue size choice. Polar, prairie and some cultures top out at
128, so Strict Big does not mean every physical island is256. Lenient Big
first selects the largest native templates, then admits smaller real
templates after unsuccessful attempts; no template is rescaled. The last
attempt selects the smallest matching widths. An impossible requested
count/spacing still fails closed. The verified stock80x80 Venetian town is
an explicit fixed-size special-faction exception in every size mode.

Fillers select among the least represented available climates before
choosing a template, avoiding source-file-count bias. Culture, faction and
essential-resource anchors are placed first and can force an unequal
climate distribution. This does not promise equal climate acreage.

Reports include repeat determinism, seed variation, native-grid bounds,
minimum gaps, exact current ship-reserve exclusion, real template sizes,
all climate/culture/essential-resource anchors, strict/lenient contrasts,
disabled-culture/faction exclusion and independence of layout from money,
AI, stock difficulty, fleet and fertility controls. Geometry quality uses
real template rectangular bounds; ocean gaps are sampled on a32x32 grid,
not measured against the exact coastline. Timings describe this machine's
isolated fixture, not Anno loading time or a permanent performance bound.

Existing copied dev6 proof under developer/layout_preview/layout remains
historical and is not relabelled as evidence for these new helpers.
