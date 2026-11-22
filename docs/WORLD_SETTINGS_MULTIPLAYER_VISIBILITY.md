# World Settings multiplayer visibility

The optional visibility-capable World Settings companion implements per-seat
Unexplored and Geography revealed display modes with strict current sight.
It derives each view from that player's ships, units, and settlements. The
selection-only companion uses the base game's visibility behavior.

## Native discovery participates in lockstep

The following findings apply to the AMD64 History Edition binaries with these
stock SHA-256 hashes. Function and vtable addresses below are RVAs.

| Module | Stock SHA-256 |
| --- | --- |
| `AnnoFrame.dll` | `7ad47cfec98da6600c0d589d199a29387f363c34d7992b7bfb8888a836f7ee45` |
| `AnnoWelt.dll` | `95951b5712848cd005f009115fafddb10e2c79ae5cf79501753a9938503ae4dc` |
| `AnnoScene.dll` | `f7d0685cf6156ff25c518f2f558863b351d7738280467e48dd585a1fefa9537a` |

| Stage | Verified native behavior |
| --- | --- |
| Lockstep checkpoint | `AnnoFrame+0x7600D` enables the World checkpoint flag through vtable slot `+0x398`. Both World classes dispatch that slot to `AnnoWelt+0xC7CB0`, which writes World `+0x6EFC`. `AnnoFrame+0x76021` passes `0x8FFFD` to World serializer slot `+0x100` at `+0x7602C`. `+0x7603B` clears the checkpoint flag. |
| Common World serializer | The `tWelt` vtable `0xFF1D8` dispatches slot `+0x100` directly to `0xD1330`. The server World vtable `0xFF650` dispatches that slot to `0xE1530`, whose `0xE1DF5` masks the flags with `0x780167` and whose `0xE1E02` calls `0xD1330`. The mask retains `0x100` in the checkpoint flags. |
| Island serialization | `0xD137D` selects the island table at World `+0x6640`. `0xD147D` forwards the flags to island serializer slot `+0x1C8` at `0xD1486`. The concrete `tInsel` vtables `0xF2DA8` and `0xF33E8` use `0x4C390` there. `0x4D0F5` gates `DISCOVER` on flag `0x100`. `0x4D192` passes the address of island `+0x12E`, with a four-byte payload length written at `0x4D14E`. |
| Discovery load and update | `0x4BEB2` matches `DISCOVER` at `0xF26E8`. `0x4BF10` copies the payload's low word to island `+0x12E`. On native discovery, `0xD8C41` reads that word, `0xD8C4E` asks the discovering player for its ID, and `0xD8C5A`–`0xD8C77` OR `1 << player_id` into the same word. The adjacent word remains part of the serialized payload. |

Two archived host and guest desync-save pairs independently confirm a four-byte
`INSEL5/DISCOVER` record for every serialized island. Those saves are evidence
of the record layout. The checkpoint call chain above establishes that the
live lockstep checksum also reads the field. Clearing, revealing, or projecting
island bits per seat in native memory can therefore desynchronize the session.

## Local view identity

The direct match retains a `tFrameGame` or `tFrameGameFull` with vtable
`AnnoFrame+0xA0CE8` or `AnnoFrame+0xA1788`. For an active game frame, the
existing read-only match observer validates the HWND's native user pointer
and the frame vtable, then reads its local `tSpieler*` from `frame+0x48`.
Host and guest have been observed with different native IDs in the same match.

A renderer must corroborate this native reference before using it.

- Validate the approved module identities and active frame, then verify the
  player vtable `AnnoWelt+0xFABE0`, its ID at `player+0x8`, and its backlink at
  `player+0x10` to the World being drawn.
- Validate the World vtable and the player-table vtable `AnnoWelt+0xFDBC0`.
  Require the same pointer at `*(world+0x210)+0x8+8*id`. Restrict the supported
  ID range to `0..15` for the 16-bit island mask. The table itself can hold
  more entries.
- Check the native viewer at `world+0x1E4` before using a stock renderer that
  depends on it. Both World vtables expose the native setter and getter at
  slots `+0x228` and `+0x230` through `0xD1A10` and `0xD1A20`. This proves the
  field interface. It does not establish that each live multiplayer render
  path supplies the expected viewer. Verify agreement on each peer, and
  decline custom drawing when the frame, World, and viewer disagree.
- Discard the view on change of match or World generation, loss of the frame,
  change of local player, load, or return to setup. A seat ID, color, address,
  or display name alone cannot identify a native view.

## Implemented presentation adapter

For terra incognita, read the shared discovery bit `1 << local_player_id` on
each island and use it only in the local presentation predicate. For current
line of sight, use read-only snapshots from the local player's ships, units,
and settlements. The existing single-player geometry predicates and validated
observer traversal can supply the basis for these calculations once the
hard-coded player-zero lookup is replaced with the verified view. Changes in
view must invalidate the relevant local render and minimap cache. Pointer
lifetime and display-thread ownership must be established for each hook.

The opt-in build stages a subset of the existing reviewed renderer hooks.
The chosen policy lives in adapter memory. The installation transaction
checks the exact loaded native modules and original display pointers or call
instructions before committing. The adapter matches the active game frame,
network instance, World, and local player before it customizes the draw.
Unexplored uses a process-local exploration chart bound to the activation and
the seat's native island discovery bit. Synthetic renderer tests exercise
seats `0` and `7` against the same native discovery masks and verify that all
World and island bytes survive rendering unchanged.

An armed match withholds World rendering until the local view is verified.
If the active viewer becomes temporarily unavailable, or the protected
renderer receives a different World, the adapter suppresses the World draw
and blacks the certified viewport after native renderer workers finish. It
also clears the selected World's validated minimap bitmap while binding is
pending. Geography revealed and Fully explored rebuild that bitmap's native
terrain when the local view is verified. Reveal all activity also rebuilds
the ownership colours. Later draws reuse the recovered bitmap until its
identity or generation changes. A stock World can use its own renderer
during a protected match.
Disarming or observing the end of the bound frame and network instance
releases the World and renderer scope. A synthetic Windows test covers these
transitions, including a draw on the wrong thread.

An automatic resync can replace the native World and player while
retaining the game window and network client. The optional companion
observes the successful reload return at `AnnoFrame+0x76D8A`. It
verifies the same window, frame, network, World class and dimensions,
scenario GUID, and native local seat before drawing the replacement
World. A new view generation rebuilds the local chart from that seat's
restored discovery and observers, discarding exploration from the
rolled-back interval. A Windows fixture covers both test seats,
invalid candidate identities, and replacement at the same World address.

The single-player activation functions also set World `+0x6EE9`, modify island
discovery, intercept native commands, and augment saves with a viewer-bound
`WSCHART` payload. The multiplayer adapter leaves World mutation, commands,
and saves on their stock paths. Each draw uses the verified local seat's
exploration. The adapter supports strict sight and Reveal all activity with
all three map modes. Reveal all activity shows current activity within the
charted area.

`WorldSettingsMultiplayerVisibilityView` returns a packed 64-bit observation
after a completed draw. Zero means there is no completed view. The low byte is
the native seat ID plus one, the second byte is the map mode, the third is the
count of islands discovered by that seat, and the fourth is the activity mode.
The upper 32 bits are the active generation. The diagnostic can corroborate the active seat during a live
match without comparing local chart state as a simulation checksum.

## Fully explored and Reveal all activity

Fully explored also unlocks native island fertility information. The
single-player implementation enables that behavior by setting the discovery
bit on every island. In Fully explored multiplayer, both peers build the
same linked SCP files with the New Earth human seat bits (`0x0381`) in
each island's native `DISCOVER` record. The verified native link loader
reads those masks before simulation. The visibility adapter checks the
masks before its first draw. Strict sight still uses each local player's
own view. The island-discovery getter is `tInsel` slot `+0x190`, selector
14, implemented by `AnnoWelt+0x49500` with the discovery read at `0x49533`.
The engine uses this selector during settlement updates at `0x47667` and
`0xB5A2D`, and reads and changes it in scene logic at `AnnoScene+0xC9D4`.
The Boolean helper `AnnoScene+0x2E610` tests the local player's bit for its
two direct callers at `0x13BDE` and `0x15F31`, which branch on it in scenario
conditions. The common initial discovery state lets those native calls
serve fertility information to each human seat with the same simulation
inputs on both peers.

Reveal all activity also requires the activities to reach the renderer.
Native `AnnoFrame+0x20F45` queries slot `+0x200` on the current game client.
For the base `tNetClient` this returns zero at `0x4E10`. For `tNetClientNet`
it reads its `tConnectClientSock*` from `+0xB00` at `0x7A150`. `0x20F4E`
skips the stock visibility toggle when that transport is present. The
toggle would call the World property-5 setter at `0x20F73` and refresh
through World slot `+0x1D8` at `0x20F96`. The refresh, `AnnoWelt+0xCDF10`,
consults World `+0x6EE9` at `0xCE081` and can write bit 31 of a native tile
word through the island's backing tile pointer at `0xCE2C6` and `0xCE30D`.
The minimap separately queries property 5 at `0xD2992` and uses the result
to select a viewer-bit mask or an all-owner mask. Removing the adapter's
48-tile filter alone leaves those native submission rules in effect.

The multiplayer companion marks the render-only producer calls at
`AnnoWelt+0xCAC9C` and `+0xCC3EE` for the selected World. The producer keeps
the native construction preview layer and retains the renderer's tile-source
choice. When it reads current island tiles, the display-only branch ignores
their hidden activity bit. A separate minimap hook at
`AnnoWelt+0xD2992` enables all-owner activity for that view. The World
viewport and minimap still apply the local chart in Unexplored mode.

The native fixture exercised independent discovery for two seats with
Reveal all activity active and verified that rendering left World and tile
memory unchanged. The construction preview regression runs the pinned
native tile producer with and without the preview layer. It covers both
native tile-source choices and verifies that source tiles stay unchanged.

## Acceptance evidence for enabling the controls

1. Verify the local `tSpieler` and native viewer IDs during an actual two-seat
   match. Include a nonzero seat ID. Exercise World and frame recreation, both
   stock World classes, and the invalid identity path. Require that no cached
   presentation survives a World or local-seat change.
2. Move one ship near a neutral island and away again while the other peer's
   observers stay elsewhere. Verify that island discovery persists only for
   the discovering player and that current foreign activity disappears when
   out of range. Check the world view and minimap, and audit the relevant
   selection and information panels for inconsistent exposure.
3. Verify several matching native checksum checkpoints after these transitions
   and after a command from each player. Inspect the same-sequence native
   discovery on both peers, which must have identical bitfields even when the
   local screens differ. Repeat across a native multiplayer save and load, and
   any supported resync path before claiming those flows.

The seed 37 linked-scene control ran with both seats on the generated
24-island map, Terra Incognita, and Strict line of sight. The host observer
corroborated renderer and native viewer 0. Its shared discovery counts
changed from 0/0 to 1/0 for seats 0 and 7 after the host reached a coast.
The VM's minimap still showed no islands. The VM ship then reached a
different coast and the counts changed to 1/1. The VM rendered the new
coastline and the host's local visibility count stayed one. The VM saw
the host ship during an approach. Both peers matched five native
checkpoints, including a checkpoint after both command sequences.

The test did not pin the VM's native viewer with a process observer.
Holding the same charted area in view across the sight boundary and
repeating save, load and resync remain open checks.

The following in-game build ran a Fully explored, Strict line of sight
match on a 24-island New Earth. The host observer registered mode 2 and
24 discovered islands on both active native seats. The VM displayed
its own starting ship and the populated minimap. The host displayed
fertility icons for a remote charted island, and both peers submitted
four matching native checksums with Wi-Fi connected.

See the [single-player visibility validation](WORLD_VISIBILITY_VALIDATION.md),
[multiplayer setup and match evidence](MULTIPLAYER.md),
[native visibility observers](../src/anno1503_overhaul/native/world_options/start_visibility_vision.inc),
[visibility activation and draw paths](../src/anno1503_overhaul/native/world_options/start_visibility_runtime.inc),
[native checkpoint augmentation](../src/anno1503_overhaul/native/world_options/start_visibility_memory_io.inc),
and [multiplayer preview controls](../src/anno1503_overhaul/native/world_settings_multiplayer/menu_multiplayer_export.inc).
