Automatic layout: isolated production-helper evidence
====================================================

The old packer picked the lowest legal Y then X. It deliberately compacted
islands, so a minimum spacing of zero could leave a large unused map region.

balanced_layout.inc first retains that feasible packing, then performs a
bounded number of safe whole-map relocation passes. Each island prefers a
larger distance to its nearest neighbor; a secondary crowding score breaks
ties. Grid offsets, scan order and extra candidates use a private deterministic
RNG. Template selection and resource RNG are not advanced. The requested
spacing remains a minimum, not a request to place islands as close as possible.

Every move preserves the native eight-tile grid, 1024-square bounds, requested
minimum spacing and all seven conservative stock ship reserves. Template
identity, dimensions, crop/mineral masks, climates and cultures are unchanged.
The planner's existing complete validation still runs after resource assignment.

This is a bounded improvement method, not an optimal-packing or mathematically
perfect-uniformity claim. Dense settings can still be rejected by the preceding
feasibility packer; resource/climate/culture minimums retain their existing
meaning. The native coastlines are not generated or altered by this helper.

Current tests execute the exact production include in a small Windows DLL.
Source template inputs are real exported plans from immutable dev5 runtime
6e0f2773, not invented zero-filled islands. Of640 requests,577 were feasible
in that baseline and all577 retained valid geometry, exact field identity,
deterministic repeats and changed layouts with a changed layout seed.
The other63 requests were already rejected by the old runtime and are recorded
separately; they are not passes or new geometry regressions.

All226 feasible24-island cases, across size settings and spacing0/16/32,
had at least two island centers per quadrant, at least20% of land in each
map half, a bounding extent of at least864 tiles on each axis, and no point
on a32-tile sample grid more than280 tiles from an island rectangle. The
exact observed metrics and native-only timings are in layout_results.json.
These rectangle/sample metrics do not prove navigation, farming, mining,
preview rendering, scene staging, the native loader or actual game play.
Full compiled-runtime and live preview/Start evidence is separate.

Reproduce with 64-bit Python and the inspected Zig toolchain:
  python -B build_fixture.py --tools PATH_TO_WorldSettings_Work/_tools
  python -B test_layout.py
The fixture DLL/cache lives under _build and must not be distributed as a
native product payload. No game process or copy is used by these tests.
