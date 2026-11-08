# Combined Food Mod 0.5.0

The installer preflights incoming hashes, builds the result, backs up and
writes in one transaction. Seven incoming states converge to one target.
`compat-0.4.0.json` and `compat-0.4.1.json` retain earlier native deltas for reproducible upgrades
and regression execution. Original binaries are not distributed. The new
backup prefix is `FoodMod_Backup_0_5`; earlier active backups stay intact.

Diet/building data, resource IDs, saved switch bits, artwork, AnnoGame and
both guarded AI modules are retained. From 0.4.1 only View.dll changes.
The World/Frame repairs below remain byte-identical to the tested 0.4.1 modules.

## Native changes

* World `88b10`, house virtual `1b0`, scores only slots 0/1. The inhabited-house
  vtable at `f9ee8+1b0` now selects a six-good helper. Ordinary markets call the
  untouched original body. It retains native `88120` scoring, strict stock
  thresholds, sale flags and exclusion of cargo carried by four house workers.
  Empty needs/population cannot enter the native division.
* Frame local command `78630` and network decoding validate against count(0),
  still two. Only the count calls at `78667` and `7fa7e` change. The helper
  returns six for Food/Salt and delegates the original virtual otherwise.
  Global production counts, definition size and packet format stay intact.
* World city sale `b4fb0` admits only 26..40. A leaf gate additionally admits
  dedicated food IDs 24,25,45, then enters the untouched body `b4fb8` for stock
  debit and counters. All indices fit the existing 56-good records.
* City tick `ad350` unrolls income for 26..40. Its block `ad3df..ad65a` calls
  a sum/clear helper for those 15 plus 24,25,45, returning the original +128
  rounding numerator. The caller still divides, credits native player cash,
  smooths totals, deducts costs and updates the timestamp. No array is enlarged.
* Old View creation omitted native `58d0`, which resolves/attaches the separate
  red-cross child of each extra `b07` button. Original event `51e0` sets checked
  state and draw `59f0` can submit that child's empty graphics reference. New
  controls call `58d0` using the original Fish button child's resolved cross
  sprite ID. Native resolution/localization lookup is preserved.

## Market panel

Original init/selection/layout/refresh still run. Good indices remain
6,7,16,17,18,19. Six price frames occupy 20..25; six price texts occupy
26..31. The native registration routine grows its widget vector; object size
is unchanged. Native root draw `1f150` iterates this vector in ascending order.
Resource parent 710 versus 730 does NOT establish separate render layers:
0.4.1 frames 24..29 covered texts 8/9/20..23. The new vector draws every frame
before every text; Food hides the old two labels. Frames resolve the native
`MARKTSTAND_RAHMEN_1` by name. Text creation matches native `b1c`/alignment 2.

50x50 icons: x22/97/172, y278/362. 71x34 frames: x12/87/162, y328/412.
40x15 texts: x37/112/187, y338/422. Food moves preview/backdrop widgets 5/4
up 20px (55,123 / 60,133), clearing the top icon row. Bottom frames end at
446 before footer 453. Connectors 2/3 and double frame 15 are parked offscreen.
Ordinary markets explicitly restore every affected preview/decorative/text
position and text width; all extra controls are hidden. Origins apply once.

Prices mirror View `4ab90`: each 26-byte good record contributes the u16 at
`4+2*climate` plus `18+2*world-price-level`. All six use this formula, without
hardcoded prices. UI property variant tags are initialized.

## Consumer categories

All stock/save IDs stay unchanged. `categories.inc` enumerates presentation
order 26,24,40,25,45,27..39: the five foods, then the other native needs.
No fixed engine/AI array is widened, and original resource sheet groups keep
their existing counts. Per-good lookup in `ce490` resolves icons across groups.

* General goods chooser `391d0`: replace the five-byte inc/cmp at `39677`
  with the internal EDI advance helper; the original JLE consumes its flags.
  `39621` uses per-good gfx instead of a sequential consumer-sheet index.
* City inventory `78ad0`: equivalent ESI advance at `78edc`, gfx at `78e0a`.
* Corresponding raw loops end at 23 (`39ea2`, `7a1c8`); material loops end
  at 44 (`38a0d`, `789b0`). All original filters/layout/stock properties remain.
* Ship consumer chooser `66120` keeps its original 16-entry object member and
  scroll state at 840. Search (`659bc`), selection (`65a82`) and redraw
  (`65c98`) read the immutable 20-cell list, including two trailing zeroes.
  Search length is 20; all scroll clamps are 12 (eight visible cells).
  Selecting the cell immediately past the page now scrolls correctly.
* Ship raw/material constructors stop at 23/44 (`66fc5`, `65878`). They keep
  their original object capacities, native unused/stone filters and IDs.

`category_check.py` executes nine native constructors, per-good icon/property
writes, all ship pages and automatic selection of each item/empty option.
The Game good-name lookup/resource/factory boundaries are test doubles.

## Build and testing

World, Frame and View rebuild from original modules instead of stacking new
sections over old extensions. Existing vtable relocations remain valid; new
code uses relative addressing. PE metadata/checksums and exception/unwind
records are updated. Structs and serialized records keep their original size.

The harness reconstructs the actual old View from inverse deltas and
reproduces the 0.4.0 unresolved cross and 0.4.1 hidden prices. It executes
the actual root/text draw path, native click/draw and local
commands, plus original worker, stock, house receipt and full city income
paths. Object lookup, graphics submission and OS services are mocked; purchase
choice, stock removal and cash calculation are native. VALIDATION.txt records
scope and counts. A Windows game run is still required for full integration.
